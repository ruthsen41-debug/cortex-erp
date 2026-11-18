"""Folha complementar, dissídio retroativo (com S-1200 infoPerAnt) e escalas cíclicas 12x36."""
import random
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.database import get_conn  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services import escalas  # noqa: E402
from backend.services import payroll_complementar as pc  # noqa: E402
from backend.services import payroll_engine as pe  # noqa: E402
from backend.services.payroll_tables import builtin_tables  # noqa: E402

client = TestClient(app)

EMP = {"name": "Carlos Plantão", "sexo": "M", "birth_date": "1990-03-10", "raca_cor": "3", "estado_civil": "1",
       "grau_instrucao": "07", "logradouro": "Rua Teste", "numero": "10", "bairro": "Centro", "cep": "78200-000",
       "cod_municipio": "5102504", "uf": "MT", "admission_date": "2026-01-05", "sindicato_cnpj": "12.345.678/0001-95",
       "role": "Vigilante", "cbo": "517330", "salary": 3000.0}


def _cpf():
    n = [random.randint(0, 9) for _ in range(9)]
    for t in (9, 10):
        n.append((sum(n[i] * (t + 1 - i) for i in range(t)) * 10 % 11) % 10)
    return "".join(map(str, n))


def _empresa_nova():
    admin = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"}).json()
    h_admin = {"Authorization": f"Bearer {admin['access_token']}"}
    email = f"compl_{uuid.uuid4().hex[:8]}@teste.com.br"
    cid = client.post("/api/auth/register-company", json={
        "company_name": "Empresa Complementar", "admin_name": "Dono", "email": email,
        "password": "senha123"}).json()["company"]["id"]
    client.post(f"/api/superadmin/companies/{cid}/approve", headers=h_admin)
    conn = get_conn()
    conn.execute("UPDATE companies SET cnpj = ?, cnae_principal = ?, regime_tributario = 'simples_nacional' WHERE id = ?",
                 ("45.123.789/0001-90", "6201501", cid))
    conn.commit()
    conn.close()
    tok = client.post("/api/auth/login", json={"email": email, "password": "senha123"}).json()["access_token"]
    return cid, {"Authorization": f"Bearer {tok}"}


def _linhas(item, codigo):
    return [l for l in item["lines"] if l["codigo"] == codigo]


# ── Escalas: cálculo puro ────────────────────────────────────────────────────
def test_plantao_noturno_12x36_hora_reduzida_e_prorrogacao():
    t = escalas.horas_turno("19:00", "07:00", 60)
    assert t["horas"] == 11.0
    assert t["noturnas_relogio"] == 8.0      # 22h-5h (7h) - 1h de intervalo + 2h prorrogadas (5h-7h)
    assert t["prorrogadas"] == 2.0
    assert t["noturnas"] == round(8 * 60 / 52.5, 2)
    sem_prorrog = escalas.horas_turno("19:00", "07:00", 60, prorrogacao=False)
    assert sem_prorrog["noturnas_relogio"] == 6.0
    assert escalas.horas_turno("07:00", "19:00", 60)["noturnas"] == 0.0
    # Jornada que não cobre todo o período noturno não tem prorrogação
    assert escalas.horas_turno("23:00", "07:00", 0)["prorrogadas"] == 0.0


def test_calendario_12x36_e_turmas():
    s = {"tipo": "ciclica", "ciclo": "12x36", "data_inicio_ciclo": "2026-09-01",
         "hora_entrada": "19:00", "hora_saida": "07:00", "intervalo_min": 60}
    a = escalas.calendario(s, "2026-09")
    b = escalas.calendario(s, "2026-09", inicio_func="2026-09-02")
    assert a["resumo"]["plantoes"] == 15 and b["resumo"]["plantoes"] == 15
    assert a["dias"][0]["trabalha"] and not b["dias"][0]["trabalha"]
    assert all(x["trabalha"] != y["trabalha"] for x, y in zip(a["dias"], b["dias"]))
    assert escalas.parse_ciclo("24x72") == [True, False, False, False]
    with pytest.raises(ValueError):
        escalas.parse_ciclo("FF")


def test_irrf_rra_multiplica_a_tabela_pelos_meses():
    t = builtin_tables("2026-11")
    assert pc.irrf_rra(0, 0, 3, t) == 0.0
    # 3 meses de R$ 9.000 tributáveis = 3 × IRRF de R$ 3.000 sem deduções
    mensal = 0.0
    for limite, aliq, parcela in t.irrf:
        if 3000 <= limite:
            mensal = max(0.0, 3000 * aliq - parcela)
            break
    esperado = round(mensal * 3, 2)
    assert pc.irrf_rra(9000, 0, 3, t) == (esperado if esperado > 10 else 0.0)


# ── Folha complementar e dissídio pela API ───────────────────────────────────
def test_complementar_opcoes_e_rubrica_de_sistema_bloqueada():
    cid, h = _empresa_nova()
    eid = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf()}).json()["id"]
    fora = client.post("/api/dp/employees", headers=h, json={**EMP, "name": "Admitido Depois", "cpf": _cpf(),
                                                              "admission_date": "2026-09-01"}).json()["id"]
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-08"}).status_code == 201

    op = client.get("/api/dp/payroll/complementar/opcoes?competence=2026-08", headers=h).json()
    ids = [f["id"] for f in op["funcionarios"]]
    assert eid in ids and fora not in ids
    assert "0001" in op["rubricas_bloqueadas"] and "0002" not in op["rubricas_bloqueadas"]
    assert client.get("/api/dp/payroll/complementar/opcoes?competence=2026-06", headers=h).json()["funcionarios"] == []

    # Salário base (rubrica de sistema) não é aceito: volta explicado em "ignorados"
    lanc = {"competence": "2026-08", "lancamentos": [{"employee_id": eid, "codigo": "0001", "valor": 500}]}
    prev = client.post("/api/dp/payroll/complementar/preview", headers=h, json=lanc).json()
    assert prev["results"] == []
    assert prev["ignorados"][0]["employee_name"] == EMP["name"] and "Dissídio" in prev["ignorados"][0]["motivo"]
    grava = client.post("/api/dp/payroll/complementar", headers=h, json=lanc)
    assert grava.status_code == 400 and "0001" in grava.json()["detail"]


def test_complementar_dissidio_e_esocial_info_per_ant():
    cid, h = _empresa_nova()
    emp = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf()}).json()
    eid = emp["id"]
    for comp in ("2026-07", "2026-08"):
        assert client.post("/api/dp/payroll/run", headers=h, json={"competence": comp}).status_code == 201

    # Complementar sem folha mensal da competência é recusada
    r = client.post("/api/dp/payroll/complementar/preview", headers=h,
                    json={"competence": "2026-06", "lancamentos": [{"employee_id": eid, "codigo": "0002", "quantidade": 10}]})
    assert r.status_code == 400 and "mensal" in r.json()["detail"]

    lanc = {"competence": "2026-08", "lancamentos": [{"employee_id": eid, "codigo": "0002", "quantidade": 10}]}
    prev = client.post("/api/dp/payroll/complementar/preview", headers=h, json=lanc).json()
    res = prev["results"][0]
    he = round(3000 / 220 * 1.5 * 10, 2)
    assert next(l for l in res["lines"] if l["codigo"] == "0002")["valor"] == he
    assert any(l["codigo"] == "0011" for l in res["lines"])  # DSR sobre a hora extra
    assert not any(l["codigo"] == "0001" for l in res["lines"])  # salário já pago não se repete
    t = builtin_tables("2026-08")
    base = res["base_inss"]
    assert res["inss"] == round(pe.calc_inss(3000 + base, t) - pe.calc_inss(3000, t), 2)
    assert res["fgts"] == round(base * 0.08, 2)

    out = client.post("/api/dp/payroll/complementar", headers=h, json=lanc)
    assert out.status_code == 201, out.text
    comp_run = out.json()["run"]
    assert comp_run["tipo"] == "complementar" and comp_run["parent_run_id"]

    # Recalcular sem lançamento novo não tem diferença a pagar
    vazio = client.post("/api/dp/payroll/complementar", headers=h, json={"competence": "2026-08", "employee_ids": [eid]})
    assert vazio.status_code == 400
    # A folha mensal com complementar vinculada não pode ser excluída antes dela
    assert client.delete(f"/api/dp/payroll/{comp_run['parent_run_id']}", headers=h).status_code == 400
    # A folha mensal da competência continua única
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-08"}).status_code == 400

    # Dissídio: convenção assinada em 20/10/2026, 10% retroativo a julho, pago em novembro
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-11"}).status_code == 201
    dados = {"competencia_pagamento": "2026-11", "competencia_inicio": "2026-07", "competencia_fim": "2026-10",
             "percentual": 10, "tp_acordo": "C", "dt_acordo": "2026-10-20", "descricao": "CCT 2026/2027 vigilantes"}
    ruim = client.post("/api/dp/payroll/dissidio/preview", headers=h, json={**dados, "dt_acordo": "2026-12-01"})
    assert ruim.status_code == 400
    prev = client.post("/api/dp/payroll/dissidio/preview", headers=h, json=dados).json()
    assert prev["meses_sem_folha"] == ["2026-09", "2026-10"]
    res = prev["results"][0]
    assert res["meses"] == ["2026-07", "2026-08"]
    sal = [l for l in res["lines"] if l["codigo"] == "0001"]
    assert [(l["per_ref"], l["valor"]) for l in sal] == [("2026-07", 300.0), ("2026-08", 300.0)]
    he_dif = next(l for l in res["lines"] if l["codigo"] == "0002")
    assert he_dif["per_ref"] == "2026-08" and he_dif["valor"] == round(he * 0.10, 2)
    inss_jul = next(l for l in res["lines"] if l["codigo"] == "0100" and l.get("per_ref") == "2026-07")
    t7 = builtin_tables("2026-07")
    assert inss_jul["valor"] == round(pe.calc_inss(3300, t7) - pe.calc_inss(3000, t7), 2)

    out = client.post("/api/dp/payroll/dissidio", headers=h, json={**dados, "atualizar_salarios": True})
    assert out.status_code == 201, out.text
    dis = out.json()
    assert dis["run"]["tipo"] == "dissidio" and dis["salarios_reajustados"] == 1
    assert client.get(f"/api/dp/employees/{eid}", headers=h).json()["salary"] == 3300.0
    assert client.post("/api/dp/payroll/dissidio", headers=h, json=dados).status_code == 400  # duplicado

    # Holerite impresso da folha de dissídio
    html = client.get(f"/api/dp/payroll/{dis['run']['id']}/recibos", headers=h)
    assert html.status_code == 200 and "dissídio" in html.text

    # eSocial: S-1200 de novembro com a folha (FOL) e as diferenças (DIS) em infoPerAnt
    rem = client.post("/api/esocial/gerar/remuneracoes", headers=h, json={"per_apur": "2026-11"}).json()["eventos"]
    assert len(rem) == 1 and rem[0]["status"] == "pendente", rem
    conn = get_conn()
    try:
        xml = conn.execute("""SELECT xml FROM esocial_eventos WHERE company_id = ? AND tipo = 'S-1200'
                              AND per_apur = '2026-11' ORDER BY id DESC""", (cid,)).fetchone()["xml"]
    finally:
        conn.close()
    assert xml.count("<dmDev>") == 2 and "<infoPerAnt>" in xml
    assert "<tpAcConv>C</tpAcConv>" in xml and "<dtAcConv>2026-10-20</dtAcConv>" in xml
    assert "<perRef>2026-07</perRef>" in xml and "<perRef>2026-08</perRef>" in xml

    # Agosto: folha mensal + complementar no mesmo S-1200
    ago = client.post("/api/esocial/gerar/remuneracoes", headers=h, json={"per_apur": "2026-08"}).json()["eventos"]
    assert len(ago) == 1 and ago[0]["status"] == "pendente", ago
    conn = get_conn()
    try:
        xml = conn.execute("""SELECT xml FROM esocial_eventos WHERE company_id = ? AND tipo = 'S-1200'
                              AND per_apur = '2026-08' ORDER BY id DESC""", (cid,)).fetchone()["xml"]
        conn.execute("UPDATE payroll_runs SET data_pagamento = '2026-11-30' WHERE company_id = ? AND competence = '2026-11'",
                     (cid,))
        conn.commit()
    finally:
        conn.close()
    assert xml.count("<dmDev>") == 2

    pg = client.post("/api/esocial/gerar/pagamentos", headers=h, json={"per_apur": "2026-11"}).json()["eventos"]
    assert len(pg) == 1 and pg[0]["status"] == "pendente", pg


# ── Escala 12x36 pela API: ponto, AFD noturno e adicional noturno automático ─
def test_escala_12x36_ponto_afd_e_adicional_noturno():
    cid, h = _empresa_nova()
    cpf = _cpf()
    emp = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": cpf, "admission_date": "2025-01-02"}).json()
    eid = emp["id"]

    bad = client.post("/api/dp/work-schedules", headers=h, json={"nome": "X", "tipo": "ciclica", "ciclo": "T,F"})
    assert bad.status_code == 400  # sem data de início do ciclo
    r = client.post("/api/dp/work-schedules", headers=h, json={
        "nome": "Vigilância noturna 12x36", "tipo": "ciclica", "ciclo": "12x36", "data_inicio_ciclo": "2026-09-01",
        "hora_entrada": "19:00", "hora_saida": "07:00", "intervalo_min": 60, "horas_semanais": 42,
        "adicional_noturno_auto": True})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["turno"]["horas"] == 11.0

    assert client.put(f"/api/dp/employees/{eid}/escala", headers=h,
                      json={"work_schedule_id": sid, "escala_inicio": "2026-09-01"}).status_code == 200
    assert [f["id"] for f in client.get(f"/api/dp/work-schedules/{sid}/funcionarios", headers=h).json()] == [eid]
    cal = client.get(f"/api/dp/work-schedules/{sid}/calendario?competencia=2026-09&employee_id={eid}", headers=h).json()
    assert cal["resumo"]["plantoes"] == 15

    # Ponto: plantão normal (dia escalado) não gera extra; trabalho na folga é todo extra
    r = client.post("/api/dp/ponto", headers=h, json={"employee_id": eid, "data": "2026-09-03", "entrada": "19:00",
                                                     "saida_almoco": "00:00", "retorno_almoco": "01:00", "saida": "07:00"})
    assert r.json()["horas_trabalhadas"] == 11.0 and r.json()["horas_extras"] == 0
    r = client.post("/api/dp/ponto", headers=h, json={"employee_id": eid, "data": "2026-09-04", "entrada": "08:00",
                                                     "saida": "12:00"})
    assert r.json()["horas_extras"] == 4.0

    # AFD: a saída das 7h do dia 06 pertence ao plantão que começou no dia 05
    afd = f"{cpf};2026-09-05;19:00\n{cpf};2026-09-06;07:00\n"
    r = client.post("/api/dp/ponto/importar-afd", headers=h, json={"conteudo": afd, "competencia": "2026-09"})
    assert r.status_code == 201, r.text
    dias = {p["data"]: p for p in client.get(f"/api/dp/ponto?employee_id={eid}&mes=2026-09", headers=h).json()}
    assert "2026-09-06" not in dias
    assert dias["2026-09-05"]["entrada"] == "19:00" and dias["2026-09-05"]["saida"] == "07:00"
    assert dias["2026-09-05"]["horas_trabalhadas"] == 12.0 and dias["2026-09-05"]["horas_extras"] == 1.0

    hol = client.get(f"/api/dp/employees/{eid}/holerite-preview?competencia=2026-09", headers=h).json()["holerite"]
    noturno = next(l for l in hol["lines"] if l["codigo"] == "0004")
    he100 = next(l for l in hol["lines"] if l["codigo"] == "0003")
    assert he100["referencia"] == "4h"  # trabalho na folga
    turno = escalas.horas_turno("19:00", "07:00", 60)["noturnas"]
    sem_intervalo = escalas.horas_turno("19:00", "07:00", 0)["noturnas"]
    # 15 plantões: 13 pela escala, o do dia 03 pelo ponto (mesmo horário) e o do dia 05 batido sem intervalo
    esperado = round(14 * turno + sem_intervalo, 2)
    assert noturno["referencia"] == f"{esperado:g}h"
