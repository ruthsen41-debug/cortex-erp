import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Adiciona raiz do projeto ao path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.database import get_conn

client = TestClient(app)


def get_auth_token():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, f"Falha no login: {res.text}"
    return res.json()["access_token"]


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_auth_me():
    token = get_auth_token()
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "admin@cortex.com.br"
    assert data["role"] == "admin"


def test_financial_lifecycle():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Criação
    payload = {
        "type": "despesa",
        "description": "Teste Automatizado Despesa",
        "amount": 250.00,
        "due_date": "2026-10-25",
        "payment_method": "Pix",
        "installments": 1,
    }
    create_res = client.post("/api/financial", json=payload, headers=headers)
    assert create_res.status_code == 200
    created_ids = create_res.json()["created_ids"]
    assert len(created_ids) == 1
    entry_id = created_ids[0]

    # 2. Leitura
    list_res = client.get("/api/financial?type=despesa", headers=headers)
    assert list_res.status_code == 200
    found = any(e["id"] == entry_id for e in list_res.json())
    assert found

    # 3. Baixa / Pagamento
    pay_payload = {
        "amount": 250.00,
        "bank_account_id": 1,
        "payment_method": "Pix",
    }
    pay_res = client.post(f"/api/financial/{entry_id}/pay", json=pay_payload, headers=headers)
    assert pay_res.status_code == 200
    assert pay_res.json()["entry_status"] == "pago"

    # 4. Estorno
    rev_res = client.post(f"/api/financial/{entry_id}/reverse", headers=headers)
    assert rev_res.status_code == 200

    # 5. Exclusão
    del_res = client.delete(f"/api/financial/{entry_id}", headers=headers)
    assert del_res.status_code == 200


def test_ai_launch():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/financial/ai-launch", json={"text": "Despesa de R$ 120 combustível hoje no Pix"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["amount"] == 120.0
    assert data["type"] == "despesa"


def test_crm_and_conversion():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cria Deal
    deal_res = client.post("/api/crm", json={"title": "Oportunidade Teste", "value": 5000.00, "stage": "prospeccao"}, headers=headers)
    assert deal_res.status_code == 200
    deal_id = deal_res.json()["id"]

    # 2. Atualiza Estágio
    stage_res = client.post(f"/api/crm/{deal_id}/stage", json={"stage": "negociacao"}, headers=headers)
    assert stage_res.status_code == 200

    # 3. Converte para Venda
    conv_res = client.post(f"/api/crm/{deal_id}/convert", headers=headers)
    assert conv_res.status_code == 200
    assert "sale_id" in conv_res.json()


def test_reports_dre():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/reports/dre?regime=competencia", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "lines" in data
    assert len(data["lines"]) > 5


def test_audit_logs():
    conn = get_conn()
    cur = conn.cursor()
    logs = cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.close()
    assert logs > 0, "Deveria haver registros de auditoria gravados."


if __name__ == "__main__":
    test_health()
    test_auth_me()
    test_financial_lifecycle()
    test_ai_launch()
    test_crm_and_conversion()
    test_reports_dre()
    test_audit_logs()
    print("TODOS OS 7 TESTES AUTOMATIZADOS PASSARAM COM SUCESSO!")
