"""Testes de 13º, férias e rescisão pelo motor de rubricas (cálculo puro + API)."""
import random
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.services import payroll_engine as pe
from backend.services import payroll_special as ps
from backend.services.payroll_tables import builtin_tables

client = TestClient(app)
T = builtin_tables("2025-12")


def ctx(**kw):
    base = dict(employee_id=1, nome="Teste", salario=3000.0, admissao=date(2020, 3, 10))
    base.update(kw)
    return ps.Contexto(**base)


def valor(res, codigo):
    return sum(l["valor"] for l in res["lines"] if l["codigo"] == codigo)


# ── 13º ──────────────────────────────────────────────────────────────────────
def test_avos_decimo_regra_dos_15_dias():
    assert ps.avos_decimo(date(2020, 1, 1), 2025) == 12
    assert ps.avos_decimo(date(2025, 3, 17), 2025) == 10   # 15 dias em março conta
    assert ps.avos_decimo(date(2025, 3, 18), 2025) == 9    # 14 dias não conta
    assert ps.avos_decimo(date(2020, 1, 1), 2025, date(2025, 6, 14)) == 5
    assert ps.avos_decimo(date(2026, 1, 1), 2025) == 0


def test_avos_decimo_desconta_afastamento_inss():
    def inss(a, b):  # afastado de 01/05 a 31/07
        ini, fim = max(a, date(2025, 5, 1)), min(b, date(2025, 7, 31))
        return (fim - ini).days + 1 if fim >= ini else 0
    assert ps.avos_decimo(date(2020, 1, 1), 2025, None, inss) == 9


def test_decimo_primeira_parcela_sem_descontos():
    res = ps.calc_decimo(ctx(), T, None, 1, 12)
    assert valor(res, "0020") == 1500.0
    assert res["total_descontos"] == 0.0 and res["liquido"] == 1500.0
    assert res["fgts"] == 120.0


def test_decimo_segunda_parcela_desconta_adiantamento_e_inss_proprio():
    res = ps.calc_decimo(ctx(), T, None, 2, 12, 0.0, 1500.0)
    assert valor(res, "0010") == 3000.0
    assert valor(res, "0120") == 1500.0
    assert res["inss"] == 253.41 and valor(res, "0121") == 253.41
    assert res["liquido"] == 1246.59
    assert res["fgts"] == 120.0            # só sobre a diferença: 1ª parcela já recolheu
    assert not res["avisos"]


def test_decimo_proporcional_com_media_e_aviso_sem_adiantamento():
    res = ps.calc_decimo(ctx(), T, None, 2, 6, media=600.0)
    assert valor(res, "0010") == 1500.0
    assert valor(res, "0021") == 300.0
    assert res["avisos"]


def test_decimo_irrf_exclusivo_faixa_alta():
    res = ps.calc_decimo(ctx(salario=10000.0, dependentes=1), T, None, 2, 12, 0.0, 5000.0)
    inss = pe.calc_inss(10000.0, T)
    assert res["irrf"] == round((10000.0 - inss - 189.59) * 0.275 - 908.73, 2)
    assert valor(res, "0122") == res["irrf"]


# ── Férias ───────────────────────────────────────────────────────────────────
def test_direito_ferias_por_faltas():
    assert [ps.direito_ferias(f) for f in (0, 5, 6, 14, 15, 23, 24, 32, 33)] == [30, 30, 24, 24, 18, 18, 12, 12, 0]


def test_ferias_30_dias_com_terco():
    res = ps.calc_ferias(ctx(), T, None, 30)
    assert valor(res, "0008") == 3000.0 and valor(res, "0009") == 1000.0
    assert res["inss"] == pe.calc_inss(4000.0, T)
    assert res["fgts"] == 320.0
    assert res["liquido"] == round(4000.0 - res["inss"] - res["irrf"], 2)


def test_ferias_com_abono_pecuniario_fora_das_bases():
    res = ps.calc_ferias(ctx(), T, None, 20, 10)
    assert valor(res, "0008") == 2000.0 and valor(res, "0009") == 666.67
    assert valor(res, "0030") == 1000.0 and valor(res, "0031") == 333.33
    assert res["total_proventos"] == 4000.0
    assert res["base_inss"] == 2666.67      # abono não tem INSS
    assert res["base_fgts"] == 2666.67      # nem FGTS


def test_ferias_em_dobro_e_media():
    res = ps.calc_ferias(ctx(), T, None, 30, 0, media=300.0, dias_dobro=30)
    assert valor(res, "0022") == 300.0
    assert valor(res, "0009") == 1100.0
    assert valor(res, "0032") == 4400.0     # (3000+300) × 4/3, indenizatória
    assert res["base_inss"] == 4400.0
    assert res["avisos"]


def test_pensao_fixa_nao_entra_em_ferias_mas_percentual_entra():
    fixa = ctx(pensoes=[{"modalidade": "valor_fixo", "valor_fixo": 500.0}])
    res = ps.calc_ferias(fixa, T, None, 30)
    assert valor(res, "0104") == 0.0 and res["avisos"]
    pct = ctx(pensoes=[{"modalidade": "percentual", "percentual": 20, "base_calculo": "bruto"}])
    assert valor(ps.calc_ferias(pct, T, None, 30), "0104") == 800.0


def test_periodos_aquisitivos_e_situacoes():
    ps_ = ps.periodos_aquisitivos(date(2022, 3, 10), date(2025, 6, 20), {"2022-03-10": 30})
    assert [p["status"] for p in ps_] == ["quitado", "vencido_dobro", "a_gozar", "em_aquisicao"]
    assert ps_[1]["limite_concessivo"] == "2025-03-09"
    assert ps_[3]["avos"] == 3 and ps_[3]["saldo"] == 0.0
    breve = ps.periodos_aquisitivos(date(2024, 1, 1), date(2025, 11, 20))
    assert breve[0]["status"] == "vence_em_breve"
    faltas = ps.periodos_aquisitivos(date(2023, 1, 1), date(2024, 6, 1), None, {"2023-01-01": 10})
    assert faltas[0]["direito"] == 24 and faltas[0]["saldo"] == 24


def test_avos_ferias():
    assert ps.avos_ferias(date(2025, 3, 10), date(2025, 8, 4)) == 5
    assert ps.avos_ferias(date(2025, 3, 10), date(2025, 3, 23)) == 0
    assert ps.avos_ferias(date(2025, 3, 10), date(2025, 3, 24)) == 1
    assert ps.avos_ferias(date(2025, 1, 31), date(2026, 5, 1)) == 12


# ── Rescisão ─────────────────────────────────────────────────────────────────
def test_aviso_previo_proporcional():
    assert ps.dias_aviso_previo(date(2025, 1, 10), date(2025, 12, 1)) == 30
    assert ps.dias_aviso_previo(date(2020, 3, 10), date(2025, 6, 20)) == 45
    assert ps.dias_aviso_previo(date(1990, 1, 1), date(2025, 6, 20)) == 90


def test_plano_sem_justa_causa_projeta_aviso():
    gozados = {f"{a}-03-10": 30 for a in (2020, 2021, 2022, 2023)}
    pl = ps.planejar_rescisao(date(2020, 3, 10), date(2025, 6, 20), "sem_justa_causa", "indenizado", gozados)
    assert pl["aviso_indenizado_dias"] == 45 and pl["data_projetada"] == "2025-08-04"
    assert pl["saldo_dias"] == 20
    assert pl["avos_13"] == 6 and pl["avos_13_indenizado"] == 1
    assert pl["ferias_vencidas_dias"] == 30 and pl["ferias_dobro_dias"] == 0
    assert pl["avos_ferias"] == 5 and pl["multa_pct"] == 0.40


def test_plano_por_tipo_de_rescisao():
    adm, sai = date(2023, 1, 2), date(2025, 9, 30)
    justa = ps.planejar_rescisao(adm, sai, "com_justa_causa", "trabalhado")
    assert justa["avos_13"] == 0 and justa["avos_ferias"] == 0 and justa["multa_pct"] == 0
    assert justa["ferias_vencidas_dias"] == 60 and justa["saldo_dias"] == 30
    pedido = ps.planejar_rescisao(adm, sai, "pedido_demissao", "nao_cumprido")
    assert pedido["aviso_indenizado_dias"] == 0 and pedido["aviso_desconto_dias"] == 30
    assert pedido["avos_13"] == 9 and pedido["multa_pct"] == 0
    acordo = ps.planejar_rescisao(adm, sai, "acordo", "indenizado")
    assert acordo["aviso_indenizado_dias"] == 18 and acordo["multa_pct"] == 0.20   # metade de 36


def test_plano_aviso_que_vira_o_ano():
    pl = ps.planejar_rescisao(date(2024, 1, 2), date(2025, 12, 10), "sem_justa_causa", "indenizado")
    assert pl["data_projetada"] == "2026-01-12"
    assert pl["avos_13"] == 11 and pl["avos_13_indenizado"] == 1   # dezembro entra pela projeção


def test_rescisao_sem_justa_causa_verbas_e_encargos():
    gozados = {f"{a}-03-10": 30 for a in (2020, 2021, 2022, 2023)}
    pl = ps.planejar_rescisao(date(2020, 3, 10), date(2025, 6, 20), "sem_justa_causa", "indenizado", gozados)
    res = ps.calc_rescisao(ctx(), T, None, pl, saldo_fgts=15000.0)
    assert valor(res, "0040") == 2000.0      # saldo 20 dias
    assert valor(res, "0041") == 4500.0      # aviso 45 dias
    assert valor(res, "0042") == 1500.0      # 13º 6/12
    assert valor(res, "0043") == 250.0       # 13º indenizado 1/12
    assert valor(res, "0044") == 3000.0      # férias vencidas
    assert valor(res, "0045") == 1250.0      # proporcionais 5/12
    assert valor(res, "0046") == 1416.67     # 1/3
    assert valor(res, "0100") == pe.calc_inss(2000.0, T)   # INSS só sobre o saldo
    assert valor(res, "0121") == 112.5                      # INSS do 13º: só a parte não indenizada
    assert res["fgts"] == 660.0              # 8% de saldo + aviso + 13º
    assert res["multa_fgts"] == 6264.0       # 40% de (15.000 + 660)
    mov = [l for l in res["lines"] if l["tipo"] != "informativo"]
    assert res["liquido"] == round(sum(l["valor"] if l["tipo"] == "provento" else -l["valor"] for l in mov), 2)
    assert valor(res, "0210") == 6264.0 and res["liquido"] < res["total_proventos"]


def test_rescisao_pedido_demissao_desconta_aviso_e_adiantamento_13():
    pl = ps.planejar_rescisao(date(2023, 1, 2), date(2025, 9, 30), "pedido_demissao", "nao_cumprido")
    res = ps.calc_rescisao(ctx(admissao=date(2023, 1, 2)), T, None, pl, adiantamento_13=1500.0, saldo_fgts=9000.0)
    assert valor(res, "0130") == 3000.0
    assert valor(res, "0120") == 1500.0
    assert valor(res, "0041") == 0.0 and res["multa_fgts"] == 0.0
    assert valor(res, "0042") == 2250.0


# ── API ──────────────────────────────────────────────────────────────────────
def _headers():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _cpf():
    n = [random.randint(0, 9) for _ in range(9)]
    for _ in range(2):
        n.append((sum(d * w for d, w in zip(n, range(len(n) + 1, 1, -1))) * 10 % 11) % 10)
    return "".join(map(str, n))


@pytest.fixture()
def funcionario():
    h = _headers()
    r = client.post("/api/dp/employees", headers=h, json={
        "name": f"Especial Teste {random.randint(1000, 9999)}", "cpf": _cpf(),
        "admission_date": "2015-02-02", "role": "Analista", "salary": 3000.0})
    assert r.status_code in (200, 201), r.text
    emp_id = r.json()["id"]
    yield h, emp_id
    for rota in ("ferias", "rescisao"):
        for reg in client.get(f"/api/dp/{rota}", headers=h).json():
            if reg["employee_id"] == emp_id:
                client.delete(f"/api/dp/especiais/{reg['id']}", headers=h)
    for ano in (2016,):
        regs = [r for r in client.get(f"/api/dp/decimo?ano={ano}", headers=h).json() if r["employee_id"] == emp_id]
        for reg in sorted(regs, key=lambda r: r["tipo"], reverse=True):  # 2ª parcela antes da 1ª
            client.delete(f"/api/dp/especiais/{reg['id']}", headers=h)
    client.delete(f"/api/dp/employees/{emp_id}", headers=h)


def test_api_decimo_primeira_e_segunda_parcela(funcionario):
    h, emp_id = funcionario
    corpo = {"ano": 2016, "parcela": 1, "employee_ids": [emp_id]}
    prev = client.post("/api/dp/decimo/preview", headers=h, json=corpo)
    assert prev.status_code == 200, prev.text
    assert prev.json()["results"][0]["liquido"] == 1500.0
    assert prev.json()["prazo_legal"] == "2016-11-30"

    assert client.post("/api/dp/decimo/run", headers=h, json=corpo).status_code == 201
    assert client.post("/api/dp/decimo/run", headers=h, json=corpo).status_code == 400  # não duplica

    seg = client.post("/api/dp/decimo/run", headers=h, json={**corpo, "parcela": 2})
    assert seg.status_code == 201, seg.text
    regs = {r["tipo"]: r for r in client.get("/api/dp/decimo?ano=2016", headers=h).json() if r["employee_id"] == emp_id}
    assert set(regs) == {"decimo_1", "decimo_2"}
    codigos = {l["codigo"]: l["valor"] for l in regs["decimo_2"]["lines"]}
    assert codigos["0010"] == 3000.0 and codigos["0120"] == 1500.0
    # a 1ª parcela não pode ser excluída enquanto a 2ª a estiver descontando
    assert client.delete(f"/api/dp/especiais/{regs['decimo_1']['id']}", headers=h).status_code == 400


def test_api_ferias_baixa_saldo_e_reduz_dias_da_folha(funcionario):
    h, emp_id = funcionario
    per = client.get(f"/api/dp/ferias/periodos/{emp_id}", headers=h)
    assert per.status_code == 200, per.text
    primeiro = per.json()["periodos"][0]
    assert primeiro["inicio"] == "2015-02-02" and primeiro["saldo"] == 30

    corpo = {"employee_id": emp_id, "data_inicio": "2016-06-06", "dias_gozo": 20, "dias_abono": 10,
             "periodo_inicio": "2015-02-02"}
    prev = client.post("/api/dp/ferias/preview", headers=h, json=corpo)
    assert prev.status_code == 200, prev.text
    p = prev.json()
    assert p["data_fim"] == "2016-06-25" and p["data_pagamento_limite"] == "2016-06-04"
    assert p["total_proventos"] == 4000.0 and p["dias_dobro"] == 0

    excesso = client.post("/api/dp/ferias/preview", headers=h, json={**corpo, "dias_gozo": 30})
    assert excesso.status_code == 400
    assert client.post("/api/dp/ferias/preview", headers=h, json={**corpo, "dias_abono": 11}).status_code == 422

    criado = client.post("/api/dp/ferias", headers=h, json=corpo)
    assert criado.status_code == 201, criado.text
    assert client.post("/api/dp/ferias", headers=h, json={**corpo, "dias_gozo": 5, "dias_abono": 0,
                                                           "periodo_inicio": "2016-02-02",
                                                           "data_inicio": "2016-06-20"}).status_code == 400
    depois = client.get(f"/api/dp/ferias/periodos/{emp_id}", headers=h).json()
    assert depois["periodos"][0]["saldo"] == 0 and depois["periodos"][0]["status"] == "quitado"

    # a folha de junho/2016 paga só os 10 dias fora das férias
    hol = client.get(f"/api/dp/employees/{emp_id}/holerite-preview?competencia=2016-06", headers=h).json()["holerite"]
    assert hol["dias_pagos"] == 10
    assert {l["codigo"]: l["valor"] for l in hol["lines"]}["0001"] == 1000.0


def test_api_rescisao_grava_desliga_e_exclusao_reativa(funcionario):
    h, emp_id = funcionario
    corpo = {"employee_id": emp_id, "data_desligamento": "2016-08-15", "tipo": "sem_justa_causa",
             "aviso_modo": "indenizado", "saldo_fgts": 4000}
    prev = client.post("/api/dp/rescisao/preview", headers=h, json=corpo)
    assert prev.status_code == 200, prev.text
    p = prev.json()
    assert p["plano"]["aviso_indenizado_dias"] == 33 and p["plano"]["saldo_dias"] == 15
    assert p["plano"]["ferias_vencidas_dias"] == 30
    assert p["multa_fgts"] > 1600 and p["saldo_fgts_origem"] == "informado"

    assert client.post("/api/dp/rescisao/preview", headers=h, json={**corpo, "tipo": "xyz"}).status_code == 422
    assert client.post("/api/dp/rescisao/preview", headers=h,
                       json={**corpo, "data_desligamento": "2010-01-01"}).status_code == 400

    criado = client.post("/api/dp/rescisao", headers=h, json=corpo)
    assert criado.status_code == 201, criado.text
    assert criado.json()["desligado"] is True
    assert client.get(f"/api/dp/employees/{emp_id}", headers=h).json()["active"] == 0
    assert client.post("/api/dp/rescisao", headers=h, json=corpo).status_code == 400

    apagado = client.delete(f"/api/dp/especiais/{criado.json()['id']}", headers=h)
    assert apagado.status_code == 200 and apagado.json()["funcionario_reativado"] is True
    assert client.get(f"/api/dp/employees/{emp_id}", headers=h).json()["active"] == 1


def test_api_simulacoes_antigas_continuam_respondendo(funcionario):
    h, emp_id = funcionario
    d = client.get(f"/api/dp/employees/{emp_id}/thirteenth?months_worked=12", headers=h)
    assert d.status_code == 200 and d.json()["gross_value"] == 3000.0
    f = client.get(f"/api/dp/employees/{emp_id}/vacation?days=30", headers=h)
    assert f.status_code == 200 and f.json()["gross_total"] == 4000.0
    r = client.post(f"/api/dp/employees/{emp_id}/termination", headers=h,
                    json={"termination_date": "2016-08-15", "termination_type": "pedido_demissao"})
    assert r.status_code == 200 and r.json()["total_bruto"] > 0


def test_api_recibo_ferias_trct_e_s2299_por_rubrica(funcionario):
    h, emp_id = funcionario
    fer = client.post("/api/dp/ferias", headers=h, json={
        "employee_id": emp_id, "data_inicio": "2016-06-06", "dias_gozo": 20, "dias_abono": 10,
        "periodo_inicio": "2015-02-02",
    })
    assert fer.status_code == 201, fer.text
    fer_id = fer.json()["id"]
    doc_fer = client.get(f"/api/dp/especiais/{fer_id}/documento", headers=h)
    assert doc_fer.status_code == 200
    assert "RECIBO DE FÉRIAS" in doc_fer.text and "0008" in doc_fer.text

    # Verifica soma progressiva de INSS das férias na folha mensal de 2016-06
    hol = client.get(f"/api/dp/employees/{emp_id}/holerite-preview?competencia=2016-06", headers=h).json()["holerite"]
    assert any("férias" in a for a in hol["avisos"])

    resc = client.post("/api/dp/rescisao", headers=h, json={
        "employee_id": emp_id, "data_desligamento": "2016-08-15", "tipo": "sem_justa_causa",
        "aviso_modo": "indenizado", "saldo_fgts": 4000,
    })
    assert resc.status_code == 201, resc.text
    resc_id = resc.json()["id"]
    doc_trct = client.get(f"/api/dp/especiais/{resc_id}/documento", headers=h)
    assert doc_trct.status_code == 200
    assert "TRCT" in doc_trct.text and "0040" in doc_trct.text

    s2299 = client.get(f"/api/dp/especiais/{resc_id}/esocial/s2299", headers=h)
    assert s2299.status_code == 200
    assert "<verbasResc>" in s2299.text and "<codRubr>0040</codRubr>" in s2299.text
