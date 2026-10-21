import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.services.payment_gateway import crc16_ccitt

client = TestClient(app)


def get_auth_token():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, f"Falha no login: {res.text}"
    return res.json()["access_token"]


def test_company_fiscal_settings_csc():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "csc_id": "000002",
        "csc_token": "TEST_CSC_TOKEN_998877",
        "complemento": "Sala 304",
        "ambiente_fiscal": "homologacao",
        "serie_nfce": 2,
        "proximo_numero_nfce": 700,
        "chave_pix": "pix@cortexerp.com.br",
    }
    put_res = client.put("/api/company", json=update_payload, headers=headers)
    assert put_res.status_code == 200, put_res.text

    get_res = client.get("/api/company", headers=headers)
    assert get_res.status_code == 200
    comp = get_res.json()
    assert comp["csc_id"] == "000002"
    assert comp["csc_token"] == "TEST_CSC_TOKEN_998877"
    assert comp["complemento"] == "Sala 304"
    assert comp["ambiente_fiscal"] == "homologacao"
    assert comp["serie_nfce"] == 2
    assert comp["proximo_numero_nfce"] == 700
    assert comp["chave_pix"] == "pix@cortexerp.com.br"


def test_emit_nfe_55_and_danfe():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Cadastra contato com endereço completo (street, city, state) para nota modelo 55
    contact_res = client.post("/api/contacts", json={
        "name": "Cliente Fiscal NF-e Completo",
        "type": "cliente",
        "document": "45123789000190",
        "email": "fiscal@cliente.com.br",
        "street": "Av. Brasil, 1500",
        "city": "Cuiaba",
        "state": "MT",
    }, headers=headers)
    assert contact_res.status_code == 200
    contact_id = contact_res.json()["id"]

    # Emite NF-e Modelo 55
    emit_res = client.post("/api/invoices/emit", json={
        "model": "NFe-55",
        "contact_id": contact_id,
        "nature_operation": "VENDA DE MERCADORIAS",
        "items": [
            {
                "product_name": "Licença Software ERP Anual",
                "sku": "LIC-ERP-01",
                "quantity": 1,
                "unit_price": 1200.00,
                "ncm": "85234910",
                "cfop": "5102",
                "csosn_cst": "102",
            }
        ]
    }, headers=headers)
    assert emit_res.status_code == 200, emit_res.text
    inv_data = emit_res.json()
    inv_id = inv_data["invoice_id"]
    assert inv_data["status"] == "ok"
    assert "access_key" in inv_data
    assert len(inv_data["access_key"]) == 44

    # Baixa XML e valida Modelo 55 e protocolo
    xml_res = client.get(f"/api/invoices/{inv_id}/xml", headers=headers)
    assert xml_res.status_code == 200
    xml_content = xml_res.text
    assert '<mod>55</mod>' in xml_content
    assert '<protNFe versao="4.00">' in xml_content
    assert '<cStat>100</cStat>' in xml_content
    assert '<xMotivo>Autorizado o uso da NF-e</xMotivo>' in xml_content

    # Visualiza DANFE A4
    danfe_res = client.get(f"/api/invoices/{inv_id}/danfe", headers=headers)
    assert danfe_res.status_code == 200
    assert "DANFE" in danfe_res.text
    # Chave formatada em blocos de 4 dígitos conforme padrão DANFE
    formatted_key = " ".join([inv_data["access_key"][i:i+4] for i in range(0, 44, 4)])
    assert formatted_key in danfe_res.text


def test_emit_nfce_65_with_infnfesupl_and_coupon():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    contact_res = client.post("/api/contacts", json={
        "name": "Consumidor Final Balcão",
        "type": "cliente",
        "document": "12345678909",
        "email": "balcao@consumidor.com.br",
        "state": "MT",
    }, headers=headers)
    assert contact_res.status_code == 200
    contact_id = contact_res.json()["id"]

    # Emite NFC-e Modelo 65
    emit_res = client.post("/api/invoices/emit", json={
        "model": "NFCe-65",
        "contact_id": contact_id,
        "nature_operation": "VENDA CONSUMIDOR FINAL",
        "items": [
            {
                "product_name": "Teclado Mecânico USB",
                "sku": "KB-MEC-01",
                "quantity": 2,
                "unit_price": 150.00,
                "ncm": "84716052",
                "cfop": "5102",
                "csosn_cst": "102",
            }
        ]
    }, headers=headers)
    assert emit_res.status_code == 200, emit_res.text
    inv_data = emit_res.json()
    inv_id = inv_data["invoice_id"]
    assert inv_data["status"] == "ok"
    assert "access_key" in inv_data
    assert len(inv_data["access_key"]) == 44

    # Verifica XML da NFC-e contendo <infNFeSupl>, <qrCode> e <urlChave>
    xml_res = client.get(f"/api/invoices/{inv_id}/xml", headers=headers)
    assert xml_res.status_code == 200
    xml_content = xml_res.text
    assert '<mod>65</mod>' in xml_content
    assert '<infNFeSupl>' in xml_content
    assert '<qrCode><![CDATA[' in xml_content
    assert '<urlChave>' in xml_content

    # Verifica DANFE NFC-e: formato Cupom Térmico com imagem QR-Code
    danfe_res = client.get(f"/api/invoices/{inv_id}/danfe", headers=headers)
    assert danfe_res.status_code == 200
    html = danfe_res.text
    assert "DANFE NFC-e" in html
    assert "data:image/png;base64," in html
    assert "Consulta via leitor de QR Code" in html
    assert "VALOR A PAGAR R$:" in html


def test_payment_charge_pix_brcode_and_crc16():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Cria lançamento financeiro a receber
    entry_res = client.post("/api/financial", json={
        "type": "receita",
        "description": "Mensalidade Homologação Pix",
        "amount": 250.00,
        "due_date": "2026-11-15",
        "category": "Vendas",
    }, headers=headers)
    assert entry_res.status_code == 200, entry_res.text
    created_ids = entry_res.json()["created_ids"]
    assert len(created_ids) > 0
    entry_id = created_ids[0]

    # 2. Gera cobrança Pix via Gateway
    charge_res = client.post(f"/api/payments/charge/{entry_id}", json={
        "billing_type": "PIX"
    }, headers=headers)
    assert charge_res.status_code == 200, charge_res.text
    ch_data = charge_res.json()["charge"]

    assert ch_data["billing_type"] == "PIX"
    assert ch_data["status"] == "PENDING"
    assert float(ch_data["value"]) == 250.00
    assert "pix_copy_paste" in ch_data
    assert "pix_qr_code_b64" in ch_data
    assert len(ch_data["pix_qr_code_b64"]) > 50

    pix_str = ch_data["pix_copy_paste"]
    assert pix_str.startswith("00020126")
    assert "6304" in pix_str

    # Valida integridade do CRC16-CCITT da string Pix BR Code
    idx_crc = pix_str.rfind("6304")
    payload_to_crc = pix_str[:idx_crc + 4]
    expected_crc = pix_str[idx_crc + 4:]
    calculated_crc = crc16_ccitt(payload_to_crc)
    assert calculated_crc == expected_crc, f"CRC incorreto: esperado {expected_crc}, calculado {calculated_crc}"


def test_payment_webhook_liquidation():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Cria lançamento e cobrança
    entry_res = client.post("/api/financial", json={
        "type": "receita",
        "description": "Venda Teste Webhook",
        "amount": 99.50,
        "due_date": "2026-11-20",
        "category": "Serviços",
    }, headers=headers)
    assert entry_res.status_code == 200
    created_ids = entry_res.json()["created_ids"]
    assert len(created_ids) > 0
    entry_id = created_ids[0]

    charge_res = client.post(f"/api/payments/charge/{entry_id}", json={"billing_type": "PIX"}, headers=headers)
    assert charge_res.status_code == 200
    gw_id = charge_res.json()["charge"]["gateway_id"]

    # Configura token de webhook para teste
    os.environ["PAYMENT_WEBHOOK_TOKEN"] = "token_webhook_seguro_123"

    # Envia evento de webhook simulando confirmação de pagamento Asaas/Pix
    wh_payload = {
        "event": "PAYMENT_RECEIVED",
        "payment": {
            "id": gw_id,
            "value": 99.50,
            "netValue": 98.50,
            "billingType": "PIX",
            "confirmedDate": "2026-10-21",
        }
    }
    wh_res = client.post(
        "/api/payments/webhook",
        json=wh_payload,
        headers={"asaas-access-token": "token_webhook_seguro_123"}
    )
    assert wh_res.status_code == 200, wh_res.text
    assert wh_res.json()["status"] == "success"

    # Valida que a cobrança foi marcada como CONFIRMED
    details_res = client.get(f"/api/payments/charge/{entry_id}", headers=headers)
    assert details_res.status_code == 200
    assert details_res.json()["status"] == "CONFIRMED"

    # Valida que o lançamento financeiro foi baixado como 'pago' na listagem
    fin_res = client.get("/api/financial", headers=headers)
    assert fin_res.status_code == 200
    matched = next(e for e in fin_res.json() if e["id"] == entry_id)
    assert matched["status"] == "pago"
