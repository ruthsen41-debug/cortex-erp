"""Testes do motor de folha por rubricas (cálculo puro + API)."""
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.services import payroll_engine as pe
from backend.services.formula_engine import FormulaError, evaluate
from backend.services.payroll_tables import builtin_tables, default_seed

client = TestClient(app)

T2025 = builtin_tables("2025-06")
T2026 = builtin_tables("2026-03")


def linha(res, codigo):
    return next((l for l in res["lines"] if l["codigo"] == codigo), None)


def valor(res, codigo):
    l = linha(res, codigo)
    return l["valor"] if l else 0.0


def emp(**kw):
    base = dict(employee_id=1, nome="Teste", salario=3000.0)
    base.update(kw)
    return pe.EmployeeInput(**base)


# ── Tabelas ──────────────────────────────────────────────────────────────────
def test_tabelas_por_vigencia():
    assert builtin_tables("2025-03").irrf[0][0] == 2259.20      # antes de maio/2025
    assert builtin_tables("2025-05").irrf[0][0] == 2428.80
    assert builtin_tables("2025-03").salario_minimo == 1518.00
    assert builtin_tables("2026-01").irrf_reducao is not None
    assert builtin_tables("2025-12").irrf_reducao is None


def test_inss_progressivo_2025():
    # 1518*7,5% + (2793,88-1518)*9% + (3000-2793,88)*12%
    assert pe.calc_inss(3000.0, T2025) == 253.41
    assert pe.calc_inss(1518.0, T2025) == 113.85
    assert pe.calc_inss(20000.0, T2025) == pe.calc_inss(8157.41, T2025) == 951.63


def test_inss_prolabore_11_por_cento_com_teto():
    assert pe.calc_inss(5000.0, T2025, prolabore=True) == 550.00
    assert pe.calc_inss(50000.0, T2025, prolabore=True) == round(8157.41 * 0.11, 2)


def test_irrf_usa_simplificado_quando_melhor():
    ir = pe.calc_irrf(3000.0, 253.41, 0, 0.0, T2025)
    assert ir["simplificado"] == 1.0
    assert ir["irrf"] == 0.0  # base 2392,80 fica na faixa isenta


def test_irrf_deducoes_legais_faixa_alta():
    inss = pe.calc_inss(10000.0, T2025)
    ir = pe.calc_irrf(10000.0, inss, 2, 0.0, T2025)
    base = 10000.0 - inss - 2 * 189.59
    assert ir["simplificado"] == 0.0
    assert ir["irrf"] == round(base * 0.275 - 908.73, 2)


def test_irrf_2026_isencao_ate_5000_e_reducao_parcial():
    assert pe.calc_irrf(5000.0, pe.calc_inss(5000.0, T2026), 0, 0.0, T2026)["irrf"] == 0.0
    parcial = pe.calc_irrf(6000.0, pe.calc_inss(6000.0, T2026), 0, 0.0, T2026)
    assert parcial["reducao"] == round(978.62 - 0.133145 * 6000.0, 2)
    assert parcial["irrf"] > 0
    acima = pe.calc_irrf(8000.0, pe.calc_inss(8000.0, T2026), 0, 0.0, T2026)
    assert acima["reducao"] == 0.0


# ── Fórmulas ─────────────────────────────────────────────────────────────────
def test_formula_basica_e_condicional():
    v = {"salario_base": 2000.0, "dias_trabalhados": 15.0}
    assert evaluate("salario_base * 0.30 * dias_trabalhados / 30", v) == 300.0
    assert evaluate("se(dias_trabalhados >= 30, 150, 150 * dias_trabalhados / 30)", v) == 75.0
    assert evaluate("min(salario_base * 0.06, 100)", v) == 100.0


@pytest.mark.parametrize("expr", [
    "__import__('os').system('dir')",
    "salario_base.__class__",
    "open('x')",
    "[1,2,3]",
    "'texto'",
    "lambda: 1",
    "salario_base ** 999",
    "variavel_que_nao_existe + 1",
    "",
])
def test_formula_rejeita_expressoes_perigosas_ou_invalidas(expr):
    with pytest.raises(FormulaError):
        evaluate(expr, {"salario_base": 1000.0})


def test_formula_divisao_por_zero():
    with pytest.raises(FormulaError):
        evaluate("salario_base / 0", {"salario_base": 1000.0})


# ── Motor ────────────────────────────────────────────────────────────────────
def test_folha_simples_bate_com_soma_das_linhas():
    res = pe.calculate_employee(emp(), T2025)
    assert valor(res, "0001") == 3000.0
    assert res["inss"] == 253.41 and valor(res, "0100") == 253.41
    assert res["fgts"] == 240.0
    assert res["liquido"] == round(res["total_proventos"] - res["total_descontos"], 2)
    proventos = sum(l["valor"] for l in res["lines"] if l["tipo"] == "provento")
    descontos = sum(l["valor"] for l in res["lines"] if l["tipo"] == "desconto")
    assert round(proventos, 2) == res["total_proventos"]
    assert round(descontos, 2) == res["total_descontos"]


def test_horas_extras_e_dsr_entram_nas_bases():
    res = pe.calculate_employee(emp(salario=2200.0, he50=10, he100=4, dias_uteis=25, dias_dsr=5), T2025)
    assert valor(res, "0002") == 150.0   # 10h * R$10 * 1,5
    assert valor(res, "0003") == 80.0    # 4h * R$10 * 2
    assert valor(res, "0011") == 46.0    # (150+80)/25*5
    assert res["base_inss"] == 2476.0
    assert res["base_fgts"] == 2476.0
    assert res["fgts"] == 198.08


def test_faltas_reduzem_bases_e_perdem_dsr():
    res = pe.calculate_employee(emp(faltas_dias=2, dsr_perdidos=1, horas_faltantes=2.2, horas_mes=220), T2025)
    assert valor(res, "0106") == 200.0
    assert valor(res, "0107") == 100.0
    assert valor(res, "0108") == 30.0
    assert res["base_inss"] == 2670.0
    assert res["base_fgts"] == 2670.0


def test_admissao_e_afastamento_proporcionais():
    res = pe.calculate_employee(emp(dias_direito=20, dias_afastado_inss=5), T2025)
    assert res["dias_pagos"] == 15
    assert valor(res, "0001") == 1500.0


def test_vt_limitado_a_6_por_cento_ou_ao_custo():
    assert valor(pe.calculate_employee(emp(vt_mensal=400.0), T2025), "0102") == 180.0
    assert valor(pe.calculate_employee(emp(vt_mensal=90.0), T2025), "0102") == 90.0


def test_insalubridade_sobre_minimo_e_nao_acumula_com_periculosidade():
    res = pe.calculate_employee(emp(insalubridade_grau="medio"), T2025)
    assert valor(res, "0005") == round(1518.0 * 0.20, 2)
    ambos = pe.calculate_employee(emp(insalubridade_grau="maximo", periculosidade=True), T2025)
    assert valor(ambos, "0006") == 900.0 and valor(ambos, "0005") == 0.0
    assert ambos["avisos"]


def test_salario_familia_respeita_limite_e_nao_integra_base():
    baixo = pe.calculate_employee(emp(salario=1800.0, filhos_sal_familia=2), T2025)
    assert valor(baixo, "0012") == 130.0
    assert baixo["base_inss"] == 1800.0
    alto = pe.calculate_employee(emp(salario=3000.0, filhos_sal_familia=2), T2025)
    assert valor(alto, "0012") == 0.0


def test_prolabore_sem_fgts_e_inss_11():
    res = pe.calculate_employee(emp(salario=5000.0, is_prolabore=True, he50=10, vt_mensal=300), T2025)
    assert valor(res, "0013") == 5000.0 and valor(res, "0001") == 0.0
    assert res["inss"] == 550.0 and res["fgts"] == 0.0
    assert valor(res, "0002") == 0.0 and valor(res, "0102") == 0.0


def test_pensao_percentual_sobre_liquido_converge():
    pens = [{"modalidade": "percentual", "percentual": 30, "base_calculo": "liquido", "beneficiario": "Filho"}]
    res = pe.calculate_employee(emp(salario=10000.0, pensoes=pens), T2025)
    p = valor(res, "0104")
    assert p > 0
    # a pensão é 30% de (rendimento - INSS - IRRF) com o IRRF já considerando a própria pensão
    assert abs(p - 0.30 * (10000.0 - res["inss"] - res["irrf"])) < 0.02
    sem = pe.calculate_employee(emp(salario=10000.0), T2025)
    assert res["irrf"] < sem["irrf"]  # pensão é dedutível


def test_descontos_diversos():
    res = pe.calculate_employee(emp(
        adiantamentos=1200.0, cct_percentual=1.0,
        beneficios=[{"nome": "VA Empresa", "tipo": "vale_alimentacao", "desconto": 50.0},
                    {"nome": "Plano de Saúde", "tipo": "plano_saude", "desconto": 120.0}]), T2025)
    assert valor(res, "0105") == 1200.0
    assert valor(res, "0109") == 30.0
    assert valor(res, "0103") == 50.0
    assert valor(res, "0110") == 120.0
    assert res["base_inss"] == 3000.0  # descontos comuns não reduzem a base


RUBRICAS = {
    "0300": {"codigo": "0300", "nome": "Gratificação 10%", "tipo": "provento", "ativo": 1,
             "incide_inss": 1, "incide_irrf": 1, "incide_fgts": 1, "formula": "salario_base * 0.10", "aplica_todos": 1},
    "0301": {"codigo": "0301", "nome": "Comissão", "tipo": "provento", "ativo": 1,
             "incide_inss": 1, "incide_irrf": 1, "incide_fgts": 1, "formula": "", "aplica_todos": 0},
    "0302": {"codigo": "0302", "nome": "Ajuda de Custo", "tipo": "provento", "ativo": 1,
             "incide_inss": 0, "incide_irrf": 0, "incide_fgts": 0, "formula": "25 * quantidade", "aplica_todos": 0},
    "0400": {"codigo": "0400", "nome": "Desc. Uniforme", "tipo": "desconto", "ativo": 1,
             "incide_inss": 0, "incide_irrf": 0, "incide_fgts": 0, "formula": "rubrica_0001 * 0.01", "aplica_todos": 1},
    "0401": {"codigo": "0401", "nome": "Quebrada", "tipo": "provento", "ativo": 1,
             "incide_inss": 1, "incide_irrf": 1, "incide_fgts": 1, "formula": "salario_base / faltas_dias", "aplica_todos": 1},
}


def test_rubricas_da_empresa_com_formula_valor_e_incidencia():
    res = pe.calculate_employee(emp(lancamentos=[
        {"codigo": "0301", "quantidade": 0, "valor": 500.0},
        {"codigo": "0302", "quantidade": 4, "valor": 0},
        {"codigo": "0999", "quantidade": 1, "valor": 10},   # não cadastrada
        {"codigo": "0100", "quantidade": 0, "valor": 10},   # rubrica de sistema
    ]), T2025, RUBRICAS)
    assert valor(res, "0300") == 300.0          # aplica_todos
    assert valor(res, "0301") == 500.0          # valor informado
    assert valor(res, "0302") == 100.0          # fórmula com quantidade, sem incidência
    assert valor(res, "0400") == 30.0           # desconto referenciando outra rubrica
    assert res["base_inss"] == 3800.0           # 3000 + 300 + 500 (ajuda de custo fora)
    assert res["base_fgts"] == 3800.0
    assert valor(res, "0401") == 0.0            # divisão por zero vira aviso, não derruba a folha
    assert len(res["avisos"]) == 3
    assert linha(res, "0301")["origem"] == "lancamento"


def test_lancamento_de_horas_em_rubrica_de_sistema():
    res = pe.calculate_employee(emp(salario=2200.0, lancamentos=[{"codigo": "0004", "quantidade": 20, "valor": 0}]), T2025)
    assert valor(res, "0004") == 40.0  # 20h * R$10 * 20%


def test_seed_de_tabelas_e_continuo():
    seed = default_seed(2025)
    assert seed["inss"][0] == (0.0, 1518.00, 7.5, 0)
    assert seed["inss"][1][0] == 1518.01
    assert seed["irrf"][-1][1] is None
    assert seed["salario_minimo"][0][2] == 1518.00


# ── API ──────────────────────────────────────────────────────────────────────
def _headers():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _cpf_aleatorio() -> str:
    import random
    n = [random.randint(0, 9) for _ in range(9)]
    for _ in range(2):
        soma = sum(d * w for d, w in zip(n, range(len(n) + 1, 1, -1)))
        n.append((soma * 10 % 11) % 10)
    return "".join(map(str, n))


def test_api_folha_por_rubricas_ponta_a_ponta():
    h = _headers()
    comp = "2019-03"  # competência antiga, para não colidir com dados reais
    for run in client.get("/api/dp/payroll", headers=h).json():
        if run["competence"] == comp:
            assert client.delete(f"/api/dp/payroll/{run['id']}", headers=h).status_code == 200

    sufixo = uuid.uuid4().hex[:6]
    r = client.post("/api/dp/employees", headers=h, json={
        "name": f"Motor Teste {sufixo}", "cpf": _cpf_aleatorio(), "admission_date": "2018-01-02",
        "role": "Analista", "salary": 2200.0, "vt_monthly": 100.0})
    assert r.status_code in (200, 201), r.text
    emp_id = r.json()["id"]

    try:
        # fórmula inválida é recusada
        bad = client.post("/api/dp/rubrics", headers=h, json={
            "codigo": f"X{sufixo}", "nome": "Ruim", "formula": "__import__('os')"})
        assert bad.status_code == 422
        assert client.post("/api/dp/rubrics/validate-formula", headers=h,
                           json={"formula": "salario_base * 0.1"}).json()["ok"] is True

        cod = f"T{sufixo[:3]}"
        r = client.post("/api/dp/rubrics", headers=h, json={
            "codigo": cod, "nome": "Prêmio Teste", "tipo": "provento",
            "incide_inss": 1, "incide_irrf": 1, "incide_fgts": 1, "formula": "100 * quantidade"})
        assert r.status_code == 201, r.text
        rubric_id = r.json()["id"]

        r = client.post("/api/dp/employee-rubrics", headers=h, json={
            "employee_id": emp_id, "rubric_id": rubric_id, "competencia": comp, "quantidade": 3})
        assert r.status_code == 201, r.text
        lanc_id = r.json()["id"]

        # ponto: 2h extras num dia útil (segunda, 04/03/2019)
        r = client.post("/api/dp/ponto", headers=h, json={
            "employee_id": emp_id, "data": "2019-03-04", "entrada": "08:00",
            "saida_almoco": "12:00", "retorno_almoco": "13:00", "saida": "19:00"})
        assert r.status_code == 201, r.text
        extras = r.json()["horas_extras"]

        prev = client.get(f"/api/dp/employees/{emp_id}/holerite-preview?competencia={comp}", headers=h)
        assert prev.status_code == 200, prev.text
        hol = prev.json()["holerite"]
        codigos = {l["codigo"]: l["valor"] for l in hol["lines"]}
        assert codigos["0001"] == 2200.0
        assert codigos[cod] == 300.0
        assert codigos["0102"] == 100.0
        if extras:
            assert codigos["0002"] == round(extras * 10 * 1.5, 2)
        assert hol["base_inss"] >= 2500.0

        run = client.post("/api/dp/payroll/run", headers=h, json={"competence": comp})
        assert run.status_code == 201, run.text
        body = run.json()
        run_id = body["run"]["id"]
        item = next(i for i in body["items"] if i["employee_id"] == emp_id)
        assert item["gross_salary"] == hol["gross_salary"]
        assert item["net_salary"] == hol["net_salary"]
        assert {l["codigo"] for l in item["lines"]} >= {"0001", cod, "0100", "0102"}

        again = client.post("/api/dp/payroll/run", headers=h, json={"competence": comp})
        assert again.status_code == 400

        got = client.get(f"/api/dp/payroll/{run_id}", headers=h)
        assert got.status_code == 200 and got.json()["items"]
        assert client.get(f"/api/dp/payroll/items?competencia={comp}", headers=h).status_code == 200

        assert client.delete(f"/api/dp/payroll/{run_id}", headers=h).status_code == 200
        assert client.get(f"/api/dp/payroll/{run_id}", headers=h).status_code == 404
        assert client.delete(f"/api/dp/employee-rubrics/{lanc_id}", headers=h).status_code == 200
        assert client.delete(f"/api/dp/rubrics/{rubric_id}", headers=h).status_code == 200
    finally:
        client.delete(f"/api/dp/employees/{emp_id}", headers=h)


def test_api_competencia_invalida():
    h = _headers()
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2025-13"}).status_code == 422
    assert client.post("/api/dp/payroll/preview", headers=h, json={"competence": "abc"}).status_code == 422


def test_inss_soma_ferias_e_multivinculo():
    # Soma de base das férias na folha mensal
    inss_ferias = pe.calc_inss(2000.0, T2025)
    res_fer = pe.calculate_employee(
        emp(salario=3000.0, dias_ferias=20, base_inss_ferias=2000.0, inss_ferias=inss_ferias),
        T2025,
    )
    assert res_fer["base_inss"] == 1000.0
    assert res_fer["inss"] == round(pe.calc_inss(3000.0, T2025) - inss_ferias, 2)
    assert any("férias" in a for a in res_fer["avisos"])

    # Multi-vínculo: somado com outro vínculo que já atingiu o teto
    teto = T2025.inss_teto
    inss_outro = pe.calc_inss(teto, T2025)
    res_mv = pe.calculate_employee(
        emp(salario=3000.0, base_inss_outros_vinculos=teto, inss_outros_vinculos=inss_outro),
        T2025,
    )
    assert res_mv["inss"] == 0.0
    assert any("outros vínculos" in a for a in res_mv["avisos"])


def test_esocial_s1200_detalhado_por_rubrica():
    from backend.services.esocial_generator import gerar_s1200
    xml = gerar_s1200(
        {"id": 1, "cnpj": "45123789000190"},
        {"cpf": "12345678909", "pis_pasep": "12345678901"},
        "2025-05",
        {"gross_salary": 3500.0, "base_inss": 3500.0},
        lines=[
            {"codigo": "0001", "tipo": "provento", "referencia": "30d", "valor": 3000.0},
            {"codigo": "0002", "tipo": "provento", "referencia": "10h", "valor": 500.0},
            {"codigo": "0100", "tipo": "desconto", "referencia": "tabela", "valor": 313.41},
            {"codigo": "0200", "tipo": "informativo", "referencia": "", "valor": 280.0},
        ],
    )
    assert "<codRubr>0001</codRubr>" in xml
    assert "<codRubr>0002</codRubr>" in xml
    assert "<codRubr>0100</codRubr>" in xml
    assert "<codRubr>0200</codRubr>" not in xml


def test_api_afd_e_cnab240():
    h = _headers()
    comp = "2018-07"
    for run in client.get("/api/dp/payroll", headers=h).json():
        if run["competence"] == comp:
            client.delete(f"/api/dp/payroll/{run['id']}", headers=h)

    cpf = _cpf_aleatorio()
    r = client.post("/api/dp/employees", headers=h, json={
        "name": f"AFD CNAB {uuid.uuid4().hex[:5]}", "cpf": cpf, "admission_date": "2017-01-10",
        "role": "Operador", "salary": 2200.0, "bank_name": "341", "bank_agency": "0001", "bank_account": "123456",
    })
    assert r.status_code in (200, 201), r.text
    emp_id = r.json()["id"]
    try:
        # Importação AFD: formato Portaria 1510 e formato delimitado
        afd_txt = (
            f"0000000013020720180800{cpf.zfill(12)}\n"
            f"0000000023020720181200{cpf.zfill(12)}\n"
            f"0000000033020720181300{cpf.zfill(12)}\n"
            f"0000000043020720181900{cpf.zfill(12)}\n"
            f"{cpf};2018-07-03;08:00;12:00;13:00;17:00\n"
        )
        imp = client.post("/api/dp/ponto/importar-afd", headers=h, json={"conteudo": afd_txt, "competencia": comp})
        assert imp.status_code == 201, imp.text
        body_imp = imp.json()
        assert body_imp["registros_importados"] == 2
        assert body_imp["horas_extras_totais"] == 2.0

        # Folha + S-1200 + CNAB 240
        run = client.post("/api/dp/payroll/run", headers=h, json={"competence": comp})
        assert run.status_code == 201, run.text
        run_id = run.json()["run"]["id"]

        s1200 = client.get(f"/api/dp/payroll/{run_id}/employee/{emp_id}/esocial/s1200", headers=h)
        assert s1200.status_code == 200 and "<codRubr>0001</codRubr>" in s1200.text

        cnab = client.get(f"/api/dp/payroll/{run_id}/cnab240", headers=h)
        assert cnab.status_code == 200, cnab.text
        linhas = [ln for ln in cnab.text.splitlines() if ln]
        assert len(linhas) >= 6
        assert all(len(ln) == 240 for ln in linhas)
        assert linhas[0][7] == "0" and linhas[-1][7] == "9"

        client.delete(f"/api/dp/payroll/{run_id}", headers=h)
    finally:
        for rec in client.get(f"/api/dp/ponto?employee_id={emp_id}&mes={comp}", headers=h).json():
            client.delete(f"/api/dp/ponto/{rec['id']}", headers=h)
        client.delete(f"/api/dp/employees/{emp_id}", headers=h)
