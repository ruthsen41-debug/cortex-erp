"""Parâmetros da folha por empresa: dias do mês, DSR por falta, adiantamento, aviso de férias e mensagem no holerite."""
from datetime import date

from backend.database import get_conn
from backend.services import payroll_special
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client


def _salario_linha(item):
    return next(l["valor"] for l in item["lines"] if l["codigo"] == "0001")


def _rodar(h, comp):
    r = client.post("/api/dp/payroll/run", headers=h, json={"competence": comp})
    assert r.status_code == 201, r.text
    return r.json()


def test_parametros_padrao_validacao_e_permissao():
    _, h = _empresa_nova()
    d = client.get("/api/dp/parametros", headers=h).json()
    assert d["parametros"]["base_dias"] == "30" and d["parametros"]["adiantamento_limite"] == 40
    assert client.put("/api/dp/parametros", headers=h, json={"base_dias": "31"}).status_code == 400
    assert client.put("/api/dp/parametros", headers=h, json={"adiantamento_percentual": 50,
                                                              "adiantamento_limite": 40}).status_code == 400
    ok = client.put("/api/dp/parametros", headers=h, json={"ferias_alerta_dias": 90, "mensagem_recibo": "  Olá  "})
    assert ok.status_code == 200
    salvo = client.get("/api/dp/parametros", headers=h).json()["parametros"]
    assert salvo["ferias_alerta_dias"] == 90 and salvo["mensagem_recibo"] == "Olá" and salvo["base_dias"] == "30"


def test_admissao_no_meio_do_mes_30_dias_ou_dias_do_mes():
    _, h = _empresa_nova()
    client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), "salary": 3100.0,
                                                       "admission_date": "2026-07-15"})
    # Padrão: mês comercial → 17 dias de 30
    run = _rodar(h, "2026-07")
    assert _salario_linha(run["items"][0]) == round(3100 / 30 * 17, 2)
    client.delete(f"/api/dp/payroll/{run['run']['id']}", headers=h)
    # Dias do mês → 17 dias de 31
    client.put("/api/dp/parametros", headers=h, json={"base_dias": "mes"})
    run = _rodar(h, "2026-07")
    assert _salario_linha(run["items"][0]) == round(3100 / 31 * 17, 2)


def test_dsr_por_falta_pode_ser_desligado():
    cid, h = _empresa_nova()
    eid = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf()}).json()["id"]
    conn = get_conn()
    conn.execute("INSERT INTO time_records (company_id, employee_id, data, tipo_ocorrencia) VALUES (?,?,?,?)",
                 (cid, eid, "2026-08-12", "falta_injustificada"))
    conn.commit()
    conn.close()
    run = _rodar(h, "2026-08")
    codigos = {l["codigo"] for l in run["items"][0]["lines"]}
    assert {"0106", "0107"} <= codigos  # falta + DSR perdido
    client.delete(f"/api/dp/payroll/{run['run']['id']}", headers=h)
    client.put("/api/dp/parametros", headers=h, json={"descontar_dsr_faltas": False})
    codigos = {l["codigo"] for l in _rodar(h, "2026-08")["items"][0]["lines"]}
    assert "0106" in codigos and "0107" not in codigos


def test_limite_do_adiantamento_vem_dos_parametros():
    _, h = _empresa_nova()
    eid = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf()}).json()["id"]  # salário 3000
    adv = {"employee_id": eid, "competencia": "2026-08", "valor": 1050}  # 35%
    assert client.post("/api/dp/advances", headers=h, json=adv).status_code == 201
    client.put("/api/dp/parametros", headers=h, json={"adiantamento_percentual": 30, "adiantamento_limite": 30})
    r = client.post("/api/dp/advances", headers=h, json=adv)
    assert r.status_code == 400 and "30%" in r.json()["detail"]


def test_mensagem_no_holerite():
    _, h = _empresa_nova()
    client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf()})
    client.put("/api/dp/parametros", headers=h, json={"mensagem_recibo": "Reunião geral dia 10"})
    run = _rodar(h, "2026-08")
    html = client.get(f"/api/dp/payroll/{run['run']['id']}/recibos", headers=h).text
    assert html.count("Reunião geral dia 10") == 2  # nas duas vias


def test_antecedencia_do_aviso_de_ferias():
    periodos = lambda alerta: payroll_special.periodos_aquisitivos(  # noqa: E731
        date(2024, 1, 10), date(2026, 10, 1), alerta_dias=alerta)
    # 2º período (2025-01-10 a 2026-01-09) vence em 2027-01-09 → faltam 100 dias
    assert periodos(60)[1]["status"] == "a_gozar"
    assert periodos(120)[1]["status"] == "vence_em_breve"
