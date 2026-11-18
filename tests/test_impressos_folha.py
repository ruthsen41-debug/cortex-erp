"""Impressos da folha (padrão Domínio): recibo de pagamento, folha analítica e holerites do portal."""
import random
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

client = TestClient(app)


def _cpf():
    n = [random.randint(0, 9) for _ in range(9)]
    for t in (9, 10):
        s = sum(n[i] * (t + 1 - i) for i in range(t))
        n.append((s * 10 % 11) % 10)
    return "".join(map(str, n))


def _empresa_nova():
    """Empresa isolada para a folha de teste não colidir com competências já processadas."""
    admin = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    h_admin = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    email = f"folha_{uuid.uuid4().hex[:8]}@teste.com.br"
    cid = client.post("/api/auth/register-company", json={
        "company_name": "Empresa Impressos", "admin_name": "Dono", "email": email,
        "password": "senha123"}).json()["company"]["id"]
    client.post(f"/api/superadmin/companies/{cid}/approve", headers=h_admin)
    tok = client.post("/api/auth/login", json={"email": email, "password": "senha123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, h_admin


def test_recibos_folha_e_holerites_do_portal():
    h, h_admin = _empresa_nova()
    ids = []
    for nome, salario in (("Ana Recibo", 3000), ("Bruno Recibo", 2000)):
        r = client.post("/api/dp/employees", headers=h, json={
            "name": nome, "cpf": _cpf(), "admission_date": "2026-01-05", "role": "Assistente",
            "cbo": "411010", "salary": salario})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])

    run = client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-10"})
    assert run.status_code == 201, run.text
    run_id = client.get("/api/dp/payroll", headers=h).json()[0]["id"]

    # Recibo de um funcionário: 2 vias, rubricas, líquido e bases
    one = client.get(f"/api/dp/payroll/{run_id}/recibos?employee_id={ids[0]}", headers=h)
    assert one.status_code == 200 and one.headers["content-type"].startswith("text/html")
    t = one.text
    for trecho in ("Recibo de Pagamento de Salário", "Outubro/2026", "Ana Recibo", "1ª via — Empregador",
                   "2ª via — Empregado", "3.000,00", "Valor líquido", "Sal. contr. INSS", "Declaro ter recebido"):
        assert trecho in t, trecho
    assert "Bruno Recibo" not in t

    # Todos os recibos da folha
    todos = client.get(f"/api/dp/payroll/{run_id}/recibos", headers=h).text
    assert "Ana Recibo" in todos and "Bruno Recibo" in todos and todos.count('class="folha"') == 2

    # Folha analítica com resumo geral (2 funcionários, proventos 5.000,00)
    folha = client.get(f"/api/dp/payroll/{run_id}/folha-impressa", headers=h)
    assert folha.status_code == 200
    for trecho in ("FOLHA DE PAGAMENTO", "Resumo geral da folha", "Ana Recibo", "Bruno Recibo",
                   "5.000,00", "FGTS a recolher", "Total líquido a pagar"):
        assert trecho in folha.text, trecho

    # Holerites do portal do funcionário
    hol = client.get(f"/api/dp/employees/{ids[0]}/holerites", headers=h).json()
    assert hol and hol[0]["run_id"] == run_id and hol[0]["competencia"] == "2026-10"

    # Sem login e de outra empresa: bloqueado
    assert client.get(f"/api/dp/payroll/{run_id}/recibos").status_code == 401
    assert client.get(f"/api/dp/payroll/{run_id}/folha-impressa", headers=h_admin).status_code == 404
    assert client.get(f"/api/dp/payroll/{run_id}/recibos?employee_id={ids[0]}", headers=h_admin).status_code == 404
    assert client.get(f"/api/dp/employees/{ids[0]}/holerites", headers=h_admin).json() == []
