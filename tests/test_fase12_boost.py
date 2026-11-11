"""Testes de cobertura para módulos com baixa cobertura — Fase 12 Boost.

Cobre: bank_accounts, service_orders, cost_centers, cfo, contacts,
       dashboard, purchases, quotes (parcial), dp (parcial).
"""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

client = TestClient(app)


def auth():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ── DASHBOARD ────────────────────────────────────────────────────────────────

def test_dashboard_get():
    res = client.get("/api/dashboard", headers=auth())
    assert res.status_code == 200
    data = res.json()
    assert "kpis" in data


# ── BANK ACCOUNTS ─────────────────────────────────────────────────────────────

def test_bank_accounts_crud_and_transfer():
    h = auth()

    # Criar conta A
    body_a = {"name": "Conta Corrente CI-A", "bank_name": "Bradesco", "initial_balance": 10000.0}
    res = client.post("/api/bank-accounts", json=body_a, headers=h)
    assert res.status_code == 200
    aid = res.json()["id"]

    # Criar conta B
    body_b = {"name": "Poupança CI-B", "bank_name": "Itaú", "initial_balance": 5000.0}
    res = client.post("/api/bank-accounts", json=body_b, headers=h)
    assert res.status_code == 200
    bid = res.json()["id"]

    # Listar
    res = client.get("/api/bank-accounts", headers=h)
    assert res.status_code == 200
    ids = [a["id"] for a in res.json()]
    assert aid in ids and bid in ids

    # Transferência entre contas
    res = client.post("/api/bank-accounts/transfer", json={
        "from_account_id": aid,
        "to_account_id": bid,
        "amount": 500.0,
        "description": "Transferência CI",
    }, headers=h)
    assert res.status_code == 200

    # Transferência inválida (mesma conta)
    res = client.post("/api/bank-accounts/transfer", json={
        "from_account_id": aid,
        "to_account_id": aid,
        "amount": 100.0,
    }, headers=h)
    assert res.status_code == 400


# ── CONTACTS ──────────────────────────────────────────────────────────────────

def test_contacts_crud():
    h = auth()

    # Listar
    res = client.get("/api/contacts", headers=h)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Criar
    body = {
        "name": "Fornecedor CI Teste",
        "type": "fornecedor",
        "email": "ci@fornecedor.com.br",
        "document": "12.345.678/0001-90",
    }
    res = client.post("/api/contacts", json=body, headers=h)
    assert res.status_code == 200
    cid = res.json()["id"]

    # Deletar
    res = client.delete(f"/api/contacts/{cid}", headers=h)
    assert res.status_code == 200


# ── COST CENTERS ──────────────────────────────────────────────────────────────

def test_cost_centers_list_and_budget():
    h = auth()

    # Listar centros de custo
    res = client.get("/api/cost-centers", headers=h)
    assert res.status_code == 200
    centers = res.json()
    assert isinstance(centers, list)

    # Budget do mês
    res = client.get("/api/cost-centers/budget?month=2026-11", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "cost_centers" in data
    assert data["month"] == "2026-11"

    # Atualizar orçamento do primeiro centro (se existir)
    if centers:
        cid = centers[0]["id"]
        res = client.put(f"/api/cost-centers/{cid}/budget", json={"monthly_budget": 5000.0}, headers=h)
        assert res.status_code == 200


# ── SERVICE ORDERS ────────────────────────────────────────────────────────────

def test_service_orders_crud_and_bill():
    h = auth()

    # Listar
    res = client.get("/api/service-orders", headers=h)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Criar OS
    body = {
        "title": "Notebook Dell — sem boot",
        "equipment": "Notebook Dell",
        "serial_number": "DELL-CI-001",
        "defect_reported": "Não liga",
        "description": "Troca de fonte",
        "total_amount": 350.0,
        "services_amount": 350.0,
        "parts_amount": 0.0,
    }
    res = client.post("/api/service-orders", json=body, headers=h)
    assert res.status_code == 200
    oid = res.json()["id"]

    # Faturar OS
    res = client.post(f"/api/service-orders/{oid}/bill", headers=h)
    assert res.status_code == 200
    assert "faturada" in res.json()["message"].lower() or res.json().get("status") == "ok"

    # Imprimir OS (HTML)
    res = client.get(f"/api/service-orders/{oid}/print", headers=h)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]

    # Faturar OS inexistente
    res = client.post("/api/service-orders/9999999/bill", headers=h)
    assert res.status_code == 404


# ── CFO VIRTUAL ───────────────────────────────────────────────────────────────

def test_cfo_ask():
    h = auth()
    res = client.post("/api/cfo/ask", json={"question": "Como está a saúde financeira da empresa?"}, headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data or "answer" in data


# ── PURCHASES ─────────────────────────────────────────────────────────────────

def test_purchases_list():
    res = client.get("/api/xml-purchases", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ── QUOTES (cotações) ─────────────────────────────────────────────────────────

def test_quotes_list_and_stats():
    h = auth()

    res = client.get("/api/quotes", headers=h)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/api/quotes/stats", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, dict)


# ── DP — Departamento Pessoal ─────────────────────────────────────────────────

def test_dp_employees_list():
    res = client.get("/api/dp/employees", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_dp_payroll_list():
    res = client.get("/api/dp/payroll", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ── ACCOUNTING (contabilidade) ────────────────────────────────────────────────

def test_accounting_accounts_list():
    res = client.get("/api/accounting/accounts", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_accounting_entries_list():
    res = client.get("/api/accounting/entries", headers=auth())
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_accounting_balancete():
    res = client.get("/api/accounting/balancete", headers=auth())
    assert res.status_code == 200


def test_accounting_dre():
    res = client.get("/api/accounting/dre", headers=auth())
    assert res.status_code == 200


def test_accounting_razao():
    h = auth()
    # Busca o primeiro account_id disponível
    accounts = client.get("/api/accounting/accounts", headers=h).json()
    if accounts:
        aid = accounts[0]["id"]
        res = client.get(f"/api/accounting/razao?account_id={aid}", headers=h)
        assert res.status_code == 200


# ── OPEN FINANCE ─────────────────────────────────────────────────────────────

def test_open_finance_status():
    res = client.get("/api/open-finance/status", headers=auth())
    assert res.status_code == 200
