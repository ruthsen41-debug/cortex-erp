"""Aviso prévio como processo, rescisão em grupo e rescisão complementar."""
from datetime import date

from backend.services import rescisao_extra as rx
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

ANTIGO = {**EMP, "admission_date": "2020-03-10", "department": "Vendas", "salary": 3000.0}


def _func(h, **extra):
    r = client.post("/api/dp/employees", headers=h, json={**ANTIGO, "cpf": _cpf(), **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


# ── Regras do aviso (unitário) ───────────────────────────────────────────────
def test_aviso_trabalhado_empregador_indeniza_proporcional():
    p = rx.planejar_aviso(date(2020, 3, 10), date(2026, 11, 3), "empregador", "trabalhado", "7dias")
    assert p["dias_total"] == 48                       # 30 + 3 × 6 anos
    assert (p["dias_trabalhados"], p["dias_indenizados"]) == (30, 18)
    assert p["data_inicio"] == "2026-11-04"            # Súmula 380: começa no dia seguinte
    assert p["data_fim"] == p["data_desligamento"] == "2026-12-03"
    assert p["data_projetada"] == "2026-12-21"
    assert p["ultimo_dia_trabalho"] == "2026-11-26"
    tudo = rx.planejar_aviso(date(2020, 3, 10), date(2026, 11, 3), "empregador", "trabalhado",
                             proporcional_trabalhado=True)
    assert (tudo["dias_trabalhados"], tudo["dias_indenizados"]) == (48, 0)


def test_aviso_pedido_demissao_e_acordo():
    p = rx.planejar_aviso(date(2020, 3, 10), date(2026, 11, 3), "empregado", "trabalhado")
    assert (p["dias_total"], p["dias_trabalhados"], p["dias_indenizados"]) == (30, 30, 0)
    n = rx.planejar_aviso(date(2020, 3, 10), date(2026, 11, 3), "empregado", "nao_cumprido")
    assert n["dias_desconto"] == 30 and n["data_desligamento"] == "2026-11-03"
    a = rx.planejar_aviso(date(2020, 3, 10), date(2026, 11, 3), "acordo", "indenizado")
    assert a["dias_indenizados"] == 24
    for args in (("empregado", "trabalhado", "2h"), ("empregador", "indenizado", "7dias")):
        try:
            rx.planejar_aviso(date(2020, 3, 10), date(2026, 11, 3), *args)
            raise AssertionError("deveria recusar a redução")
        except rx.AvisoInvalido:
            pass


# ── Fluxo pela API ───────────────────────────────────────────────────────────
def test_aviso_vira_rescisao_e_volta_ao_excluir():
    _, h = _empresa_nova()
    eid = _func(h)
    body = {"employee_id": eid, "data_aviso": "2026-11-03", "iniciativa": "empregador", "modo": "trabalhado"}
    r = client.post("/api/dp/avisos-previos", headers=h, json=body)
    assert r.status_code == 201, r.text
    aviso = r.json()
    assert client.post("/api/dp/avisos-previos", headers=h, json=body).status_code == 400   # já existe ativo
    assert "AVISO PRÉVIO DO EMPREGADOR" in client.get(f"/api/dp/avisos-previos/{aviso['id']}/documento", headers=h).text

    # a rescisão pega data, tipo e os 18 dias indenizados do aviso
    prev = client.post("/api/dp/rescisao/preview", headers=h, json={"employee_id": eid}).json()
    assert prev["data_desligamento"] == "2026-12-03" and prev["tipo"] == "sem_justa_causa"
    assert prev["plano"]["aviso_indenizado_dias"] == 18 and prev["aviso_id"] == aviso["id"]
    resc = client.post("/api/dp/rescisao", headers=h, json={"employee_id": eid})
    assert resc.status_code == 201, resc.text
    st = client.get("/api/dp/avisos-previos", headers=h).json()[0]
    assert st["status"] == "convertido" and st["rescisao_id"] == resc.json()["id"]
    assert client.post(f"/api/dp/avisos-previos/{aviso['id']}/cancelar", headers=h,
                       json={"motivo": "x"}).status_code == 400

    client.delete(f"/api/dp/especiais/{resc.json()['id']}", headers=h)
    assert client.get("/api/dp/avisos-previos", headers=h).json()[0]["status"] == "ativo"
    assert client.post(f"/api/dp/avisos-previos/{aviso['id']}/cancelar", headers=h, json={}).status_code == 422
    r = client.post(f"/api/dp/avisos-previos/{aviso['id']}/cancelar", headers=h, json={"motivo": "Reconsideração aceita"})
    assert r.status_code == 200
    # aviso cancelado não alimenta mais a rescisão
    prev = client.post("/api/dp/rescisao/preview", headers=h,
                       json={"employee_id": eid, "data_desligamento": "2026-11-30"}).json()
    assert prev.get("aviso_id") is None


def test_rescisao_em_grupo():
    _, h = _empresa_nova()
    ids = [_func(h), _func(h), _func(h, department="Outro")]
    body = {"departamento": "Vendas", "data_desligamento": "2026-11-30", "tipo": "sem_justa_causa"}
    prev = client.post("/api/dp/rescisao/grupo/preview", headers=h, json=body).json()
    assert {f["employee_id"] for f in prev["funcionarios"]} == set(ids[:2])
    assert prev["avisos"] and prev["total_multa_fgts"] > 0
    r = client.post("/api/dp/rescisao/grupo", headers=h, json=body)
    assert r.status_code == 201, r.text
    assert len(r.json()["funcionarios"]) == 2
    assert len(client.get("/api/dp/rescisao", headers=h).json()) == 2
    emps = {e["id"]: e for e in client.get("/api/dp/employees?active_only=false", headers=h).json()}
    assert not emps[ids[0]]["active"] and emps[ids[2]]["active"]


def test_rescisao_complementar_dissidio_e_multa_477():
    _, h = _empresa_nova()
    eid = _func(h)
    resc = client.post("/api/dp/rescisao", headers=h, json={
        "employee_id": eid, "data_desligamento": "2026-11-30", "tipo": "sem_justa_causa",
        "aviso_modo": "indenizado", "saldo_fgts": 10000}).json()
    url = f"/api/dp/rescisao/{resc['id']}/complementar"
    assert client.post(url + "/preview", headers=h, json={"novo_salario": 2900}).status_code == 400

    prev = client.post(url + "/preview", headers=h, json={"percentual_reajuste": 10, "multa_477": True}).json()
    assert prev["salario_novo"] == 3300.0
    linhas = {l["codigo"]: l for l in prev["lines"]}
    assert linhas["0040"]["valor"] == 300.0                       # saldo de 30 dias: 10% de 3.000
    assert linhas["0040"]["nome"].startswith("Dif.")
    assert linhas["0048"]["valor"] == 3300.0                      # multa art. 477 = 1 salário
    assert "0041" in linhas and "0100" in linhas                  # aviso indenizado e INSS sobre a diferença
    orig_inss = next(l["valor"] for l in resc["lines"] if l["codigo"] == "0100")
    assert 0 < linhas["0100"]["valor"] < orig_inss
    assert prev["multa_fgts"] == round(prev["fgts"] * 0.4, 2)

    g = client.post(url, headers=h, json={"percentual_reajuste": 10, "multa_477": True})
    assert g.status_code == 201, g.text
    assert client.post(url, headers=h, json={"percentual_reajuste": 10}).status_code == 400   # pagaria em dobro
    assert client.post(url, headers=h, json={"multa_477": True}).status_code == 400            # multa já paga
    lista = client.get("/api/dp/rescisao", headers=h).json()
    assert [c["id"] for c in lista[0]["complementares"]] == [g.json()["id"]]
    assert "RESCISÃO COMPLEMENTAR" in client.get(f"/api/dp/especiais/{g.json()['id']}/documento", headers=h).text
    assert client.delete(f"/api/dp/especiais/{resc['id']}", headers=h).status_code == 400   # tem complementar
    assert client.delete(f"/api/dp/especiais/{g.json()['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/dp/especiais/{resc['id']}", headers=h).status_code == 200
