"""Relatórios da folha: relação de líquidos, ficha financeira, lançamentos, férias e rescisões."""
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

BASE = "/api/dp/relatorios-folha"


def _func(h, **extra):
    r = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_liquidos_e_lancamentos():
    _, h = _empresa_nova()
    a = _func(h, name="Ana Banco", bank_name="Banco do Brasil", bank_agency="1234-5", bank_account="99887-1")
    _func(h, name="Beto Sem Conta")
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-10"}).status_code in (200, 201)
    run = client.get("/api/dp/payroll", headers=h).json()[0]

    html = client.get(f"{BASE}/liquidos?run_id={run['id']}", headers=h).text
    assert "Relação de líquidos" in html and "99887-1" in html and "1 funcionário(s) sem conta" in html
    csv = client.get(f"{BASE}/liquidos?run_id={run['id']}&formato=csv", headers=h)
    assert csv.headers["content-type"].startswith("text/csv")
    linhas = csv.content.decode("utf-8-sig").splitlines()
    total = [l for l in linhas if l.startswith(";Total")][0]
    liquido = f"{float(run['total_net']):.2f}".replace(".", ",")
    assert total.endswith(liquido)                                   # soma dos líquidos = total da folha

    lanc = client.get(f"{BASE}/lancamentos?competencia=2026-10&codigo=0001", headers=h).text
    assert "Salário Base" in lanc and "Ana Banco" in lanc and "Subtotal" in lanc
    assert client.get(f"{BASE}/lancamentos?competencia=10/2026", headers=h).status_code == 422

    ficha = client.get(f"{BASE}/ficha-financeira?employee_id={a}&ano=2026&formato=csv", headers=h)
    texto = ficha.content.decode("utf-8-sig")
    assert "Ficha financeira 2026" in texto and "Salário Base" in texto and "Líquido" in texto
    assert "3000,00" in texto                                        # salário de outubro na coluna Out


def test_ferias_e_rescisoes_e_isolamento():
    _, h = _empresa_nova()
    eid = _func(h, name="Clara Férias", admission_date="2024-01-10")
    r = client.post("/api/dp/ferias", headers=h, json={"employee_id": eid, "data_inicio": "2026-03-02", "dias_gozo": 30,
                                                       "periodo_inicio": "2024-01-10"})
    assert r.status_code == 201, r.text
    fer = client.get(f"{BASE}/ferias?inicio=2026-01-01&fim=2026-12-31", headers=h).text
    assert "Clara Férias" in fer and "02/03/2026 a 31/03/2026" in fer
    assert "Nenhum registro" in client.get(f"{BASE}/ferias?inicio=2025-01-01&fim=2025-12-31", headers=h).text

    resc = client.post("/api/dp/rescisao", headers=h, json={"employee_id": eid, "data_desligamento": "2026-11-30",
                                                            "tipo": "sem_justa_causa", "saldo_fgts": 5000})
    assert resc.status_code == 201, resc.text
    rel = client.get(f"{BASE}/rescisoes?inicio=2026-11-01&fim=2026-11-30", headers=h).text
    assert "Sem justa causa" in rel and "1 rescisão(ões)" in rel
    assert client.get(f"{BASE}/rescisoes?inicio=2026-12-01&fim=2026-11-01", headers=h).status_code == 422
    assert client.get(f"{BASE}/inexistente", headers=h).status_code == 404

    _, h2 = _empresa_nova()
    assert client.get(f"{BASE}/ficha-financeira?employee_id={eid}&ano=2026", headers=h2).status_code == 404
    assert "Clara" not in client.get(f"{BASE}/rescisoes?inicio=2026-11-01&fim=2026-11-30", headers=h2).text
