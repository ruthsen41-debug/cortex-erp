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


def test_payment_gateway_and_webhook():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cria lançamento para teste
    ent_res = client.post("/api/financial", json={
        "type": "receita",
        "description": "Receita Teste Gateway",
        "amount": 350.00,
        "due_date": "2026-10-30",
    }, headers=headers)
    eid = ent_res.json()["created_ids"][0]

    # 2. Gera cobrança Pix no gateway
    charge_res = client.post(f"/api/payments/charge/{eid}", json={"billing_type": "PIX"}, headers=headers)
    assert charge_res.status_code == 200
    charge = charge_res.json()["charge"]
    assert charge["status"] == "PENDING"
    assert len(charge["pix_qr_code_b64"]) > 50

    # 3. Simula Webhook de Confirmação de Pagamento
    wh_res = client.post("/api/payments/webhook", json={
        "event": "PAYMENT_RECEIVED",
        "payment": {"id": charge["gateway_id"], "value": 350.00},
    })
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "success"

    # 4. Verifica que título foi baixado
    chk_res = client.get("/api/financial?type=receita", headers=headers)
    item = next(x for x in chk_res.json() if x["id"] == eid)
    assert item["status"] == "pago"


def test_collection_rules_and_notice():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    rules_res = client.get("/api/collection/rules", headers=headers)
    assert rules_res.status_code == 200
    assert len(rules_res.json()) >= 4

    notice_res = client.post("/api/collection/send/1", json={"channel": "whatsapp"}, headers=headers)
    assert notice_res.status_code == 200
    assert "whatsapp_url" in notice_res.json()


def test_cash_flow_statement():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/reports/cash-flow", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "timeline" in data
    assert len(data["timeline"]) > 20


def test_spreadsheet_exports():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    csv_res = client.get("/api/financial/export-csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")

    excel_res = client.get("/api/financial/export-excel", headers=headers)
    assert excel_res.status_code == 200
    assert "openxmlformats" in excel_res.headers.get("content-type", "")


def test_audit_logs():
    conn = get_conn()
    cur = conn.cursor()
    logs = cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.close()
    assert logs > 0, "Deveria haver registros de auditoria gravados."


def test_phase3_sellers_and_price_tables():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tabela de preço
    pt_res = client.post("/api/price-tables", json={
        "name": "Tabela Especial Atacado 15%",
        "discount_percent": 15.0,
        "markup_percent": 0.0,
    }, headers=headers)
    assert pt_res.status_code == 200
    pt_id = pt_res.json()["id"]

    # 2. Vendedor com comissão 8%
    seller_res = client.post("/api/sellers", json={
        "name": "Carlos Vendas",
        "email": "carlos@cortex.com.br",
        "phone": "(11) 98888-7777",
        "commission_percent": 8.0,
    }, headers=headers)
    assert seller_res.status_code == 200
    seller_id = seller_res.json()["id"]

    # 3. Cria Venda associada ao vendedor e tabela de preço
    sale_res = client.post("/api/sales", json={
        "type": "venda",
        "seller_id": seller_id,
        "price_table_id": pt_id,
        "items": [
            {"product_id": 1, "product_name": "Produto Teste", "quantity": 10.0, "unit_price": 100.0}
        ]
    }, headers=headers)
    assert sale_res.status_code == 200
    sale_data = sale_res.json()
    assert "token_access" in sale_data
    # 10 x 85 = 850 total (15% de desconto da tabela de preço)
    assert sale_data["total_amount"] == 850.0
    # 8% de comissão sobre 850 = 68.0
    assert sale_data["commission_amount"] == 68.0

    # 4. Verifica relatório de comissões do vendedor
    comm_res = client.get(f"/api/sellers/{seller_id}/commissions", headers=headers)
    assert comm_res.status_code == 200
    comm_data = comm_res.json()
    assert comm_data["total_sales_count"] >= 1
    assert comm_data["total_commission_amount"] >= 68.0


def test_phase3_warehouses_batches_and_transfers():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Depósito Secundário
    wh_res = client.post("/api/warehouses", json={
        "name": "Depósito Filial Campinas",
        "code": "FILIAL-CPQ",
        "location": "Campinas/SP",
        "is_default": 0,
    }, headers=headers)
    assert wh_res.status_code == 200
    wh_id = wh_res.json()["id"]

    # 2. Lote de Produto com Validade
    batch_res = client.post("/api/products/1/batches", json={
        "product_id": 1,
        "warehouse_id": wh_id,
        "batch_number": "LOTE-2026-X1",
        "expiry_date": "2026-12-31",
        "manufacturing_date": "2026-01-01",
        "quantity": 50.0
    }, headers=headers)
    assert batch_res.status_code == 200

    # 3. Consulta lotes vencendo
    exp_res = client.get("/api/inventory/batches/expiring?days=120", headers=headers)
    assert exp_res.status_code == 200

    # 4. Variação de Produto
    var_res = client.post("/api/products/1/variants", json={
        "product_id": 1,
        "variant_name": "Tamanho GG / Azul",
        "sku": "VAR-GG-AZUL",
        "additional_price": 15.0,
        "stock_qty": 20.0
    }, headers=headers)
    assert var_res.status_code == 200

    # 5. Transferência de Estoque entre Depósitos
    trans_res = client.post("/api/inventory/transfer", json={
        "from_warehouse_id": 1,
        "to_warehouse_id": wh_id,
        "product_id": 1,
        "quantity": 5.0,
        "notes": "Transferência para abastecimento da filial"
    }, headers=headers)
    assert trans_res.status_code == 200

    # 6. Ajuste Físico de Inventário
    adj_res = client.post("/api/inventory/adjustment", json={
        "product_id": 1,
        "warehouse_id": 1,
        "new_quantity": 120.0,
        "reason": "Contagem física anual de estoque"
    }, headers=headers)
    assert adj_res.status_code == 200
    assert adj_res.json()["new_stock"] == 120.0


def test_phase3_purchase_orders_workflow():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cria Pedido de Compra
    po_res = client.post("/api/purchase-orders", json={
        "supplier_id": 1,
        "payment_terms": "Boleto 30 dias",
        "notes": "Compra de insumos mensal",
        "items": [
            {"product_id": 1, "quantity": 10.0, "unit_price": 50.0, "discount": 0.0}
        ]
    }, headers=headers)
    assert po_res.status_code == 200
    po_id = po_res.json()["id"]
    assert po_res.json()["total_amount"] == 500.0

    # 2. Atualiza Status para Aprovado
    status_res = client.post(f"/api/purchase-orders/{po_id}/status", json={"status": "aprovado"}, headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "aprovado"

    # 3. Recebimento da Mercadoria (Entrada no Estoque + Geração de Contas a Pagar)
    receive_res = client.post(f"/api/purchase-orders/{po_id}/receive", headers=headers)
    assert receive_res.status_code == 200
    data = receive_res.json()
    assert "financial_entry_id" in data
    fin_id = data["financial_entry_id"]

    # Verifica se gerou o lançamento no contas a pagar
    fin_res = client.get("/api/financial?type=despesa", headers=headers)
    assert any(x["id"] == fin_id and x["status"] == "pendente" for x in fin_res.json())


def test_phase3_sales_returns_rma():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cria venda primeiro
    sale_res = client.post("/api/sales", json={
        "type": "venda",
        "items": [{"product_id": 1, "product_name": "Item Para Devolver", "quantity": 4.0, "unit_price": 60.0}]
    }, headers=headers)
    sale_id = sale_res.json()["id"]

    # 2. Devolução com estorno financeiro e reestocagem
    ret_res = client.post("/api/sales/returns", json={
        "sale_id": sale_id,
        "reason": "Cliente desistiu da compra",
        "refund_method": "estorno_financeiro",
        "items": [
            {"product_id": 1, "quantity": 2.0, "unit_price": 60.0, "return_to_stock": 1}
        ]
    }, headers=headers)
    assert ret_res.status_code == 200
    ret_data = ret_res.json()
    assert ret_data["total_returned"] == 120.0
    assert ret_data["financial_entry_id"] is not None

    # 3. Consulta histórico de devoluções
    list_ret = client.get("/api/sales/returns", headers=headers)
    assert list_ret.status_code == 200
    assert len(list_ret.json()) >= 1


def test_phase3_contract_adjustments():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cria Contrato
    c_res = client.post("/api/contracts", json={
        "title": "Suporte Técnico Mensal Premium",
        "contact_id": 1,
        "amount": 1000.00,
        "billing_day": 15
    }, headers=headers)
    assert c_res.status_code == 200
    contract_id = c_res.json()["id"]

    # 2. Reajuste Individual (+6.5% IPCA)
    adj_res = client.post(f"/api/contracts/{contract_id}/adjust", json={
        "adjustment_percent": 6.5,
        "inflation_index": "IPCA"
    }, headers=headers)
    assert adj_res.status_code == 200
    assert adj_res.json()["previous_value"] == 1000.0
    assert adj_res.json()["new_value"] == 1065.0

    # 3. Reajuste em Lote (+5.0% IGP-M)
    batch_res = client.post("/api/contracts/batch-adjust", json={
        "adjustment_percent": 5.0,
        "inflation_index": "IGP-M",
        "contract_ids": [contract_id]
    }, headers=headers)
    assert batch_res.status_code == 200
    assert batch_res.json()["adjusted_count"] == 1
    # 1065 * 1.05 = 1118.25
    assert batch_res.json()["contracts"][0]["new_value"] == 1118.25


def test_phase3_customer_portal():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cria orçamento
    quote_res = client.post("/api/sales", json={
        "type": "orcamento",
        "contact_id": 1,
        "items": [
            {"product_id": 1, "product_name": "Licença Software Pro", "quantity": 1.0, "unit_price": 890.0}
        ]
    }, headers=headers)
    assert quote_res.status_code == 200
    quote_data = quote_res.json()
    access_token = quote_data["token_access"]

    # 2. Acesso público pelo cliente SEM token de autenticação
    portal_res = client.get(f"/api/portal/quote/{access_token}")
    assert portal_res.status_code == 200
    p_data = portal_res.json()
    assert p_data["total_amount"] == 890.0
    assert len(p_data["items"]) == 1

    # 3. Aprovação online do cliente pelo Portal
    accept_res = client.post(f"/api/portal/quote/{access_token}/accept")
    assert accept_res.status_code == 200
    acc_data = accept_res.json()
    assert acc_data["status"] == "accepted"
    assert "payment" in acc_data


if __name__ == "__main__":
    test_health()
    test_auth_me()
    test_financial_lifecycle()
    test_ai_launch()
    test_crm_and_conversion()
    test_reports_dre()
    test_payment_gateway_and_webhook()
    test_collection_rules_and_notice()
    test_cash_flow_statement()
    test_spreadsheet_exports()
    test_audit_logs()
    # Fase 3 tests
    test_phase3_sellers_and_price_tables()
    test_phase3_warehouses_batches_and_transfers()
    test_phase3_purchase_orders_workflow()
    test_phase3_sales_returns_rma()
    test_phase3_contract_adjustments()
    test_phase3_customer_portal()
    print("TODOS OS 17 TESTES AUTOMATIZADOS (FASES 0, 1, 2 E 3) PASSARAM COM SUCESSO!")
