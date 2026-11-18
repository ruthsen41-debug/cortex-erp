"""Férias: fracionamento (CLT art. 134 §1º), programação anual e férias em grupo / coletivas."""
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

ANTIGO = {**EMP, "admission_date": "2024-01-10", "department": "Produção"}


def _func(h, **extra):
    r = client.post("/api/dp/employees", headers=h, json={**ANTIGO, "cpf": _cpf(), **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _ferias(h, eid, inicio, dias, abono=0):
    return client.post("/api/dp/ferias", headers=h, json={"employee_id": eid, "data_inicio": inicio,
                                                          "dias_gozo": dias, "dias_abono": abono,
                                                          "periodo_inicio": "2024-01-10"})


def test_fracionamento_regras_da_clt():
    _, h = _empresa_nova()
    eid = _func(h)
    assert _ferias(h, eid, "2025-03-02", 4).status_code == 400            # menos de 5 dias
    r = _ferias(h, eid, "2025-03-02", 10)                                # sobrariam 20, ainda cabe 14
    assert r.status_code == 201, r.text
    r = _ferias(h, eid, "2025-05-04", 10)                                # sobrariam 10 e nenhum ≥ 14
    assert r.status_code == 400 and "14 dias" in r.json()["detail"]
    assert _ferias(h, eid, "2025-05-04", 17).status_code == 400          # sobrariam 3 (< 5)
    assert _ferias(h, eid, "2025-05-04", 15).status_code == 201          # 10 + 15, sobram 5
    assert _ferias(h, eid, "2025-08-03", 5).status_code == 201           # 3ª parte
    saldo = client.get(f"/api/dp/ferias/periodos/{eid}", headers=h).json()
    periodos = saldo["periodos"] if isinstance(saldo, dict) else saldo
    assert next(p for p in periodos if p["inicio"] == "2024-01-10")["saldo"] == 0


def test_programacao_de_ferias_e_calculo():
    _, h = _empresa_nova()
    eid = _func(h)
    r = client.post("/api/dp/ferias/programacao", headers=h,
                    json={"employee_id": eid, "data_inicio": "2026-02-02", "dias_gozo": 20, "dias_abono": 10})
    assert r.status_code == 201, r.text
    prog = r.json()
    assert prog["periodo_inicio"] == "2024-01-10" and prog["data_fim"] == "2026-02-21"
    assert any("limite concessivo" in a for a in prog["alertas"])       # limite 2026-01-09 → em dobro
    lista = client.get("/api/dp/ferias/programacao?ano=2026", headers=h).json()
    assert [p["id"] for p in lista] == [prog["id"]]
    assert "Programação de férias 2026" in client.get("/api/dp/ferias/programacao/relatorio?ano=2026", headers=h).text
    calc = client.post(f"/api/dp/ferias/programacao/{prog['id']}/calcular", headers=h)
    assert calc.status_code == 201, calc.text
    assert calc.json()["dias_dobro"] > 0
    assert client.get("/api/dp/ferias/programacao", headers=h).json()[0]["status"] == "calculada"
    assert client.delete(f"/api/dp/ferias/programacao/{prog['id']}", headers=h).status_code == 400
    assert client.post(f"/api/dp/ferias/programacao/{prog['id']}/calcular", headers=h).status_code == 400


def test_ferias_coletivas_em_grupo():
    _, h = _empresa_nova()
    a, b = _func(h), _func(h, name="Bruna Nova")
    novo = _func(h, name="Recém Admitido", admission_date="2025-12-01")
    _func(h, name="Outro Setor", department="Vendas")
    corpo = {"departamento": "Produção", "data_inicio": "2025-12-22", "dias_gozo": 15, "coletivas": True}
    assert client.post("/api/dp/ferias/grupo/preview", headers=h,
                       json={**corpo, "dias_gozo": 8}).status_code == 400   # coletivas ≥ 10 dias
    prev = client.post("/api/dp/ferias/grupo/preview", headers=h, json=corpo).json()
    assert {f["employee_id"] for f in prev["funcionarios"]} == {a, b}
    assert [g["employee_id"] for g in prev["ignorados"]] == [novo] and "art. 140" in prev["ignorados"][0]["motivo"]
    assert prev["avisos"] and prev["total_liquido"] > 0
    gravado = client.post("/api/dp/ferias/grupo", headers=h, json=corpo)
    assert gravado.status_code == 201, gravado.text
    assert len(client.get("/api/dp/ferias", headers=h).json()) == 2
    # Gravar de novo: sobreposição → nada gravado
    assert client.post("/api/dp/ferias/grupo", headers=h, json=corpo).status_code == 400
