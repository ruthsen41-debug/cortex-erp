import io
import os
import re
import base64
import uuid
from datetime import date
from typing import Dict, Any

import httpx
import qrcode

try:
    from ..database import get_conn, begin_write, recalculate_bank_balances
    from ..auth import log_audit
except ImportError:
    from database import get_conn, begin_write, recalculate_bank_balances
    from auth import log_audit

ASAAS_API_KEY = os.getenv("ASAAS_API_KEY", "").strip()
ASAAS_ENV = os.getenv("ASAAS_ENVIRONMENT", "sandbox").strip().lower()
ASAAS_BASE_URL = "https://sandbox.asaas.com/api/v3" if ASAAS_ENV == "sandbox" else "https://api.asaas.com/v3"


def generate_qr_code_base64(data: str) -> str:
    """Gera imagem PNG do QR Code em Base64."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")




def crc16_ccitt(data: str) -> str:
    """Calcula o checksum CRC16-CCITT (polinômio 0x1021, valor inicial 0xFFFF) padrão Pix Banco Central."""
    crc = 0xFFFF
    for b in data.encode("utf-8"):
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build_tlv(tag: str, value: str) -> str:
    """Monta campo no formato TLV (Tag-Length-Value) EMV padrão BR Code / Pix."""
    return f"{tag}{len(value):02d}{value}"


def generate_pix_brcode(
    pix_key: str,
    merchant_name: str,
    merchant_city: str,
    amount: float,
    txid: str = "***",
    description: str = "",
) -> str:
    """Gera a string Pix Copia-e-Cola (BR Code EMV) em total conformidade com o Banco Central do Brasil."""
    p00 = build_tlv("00", "01")
    mai_gui = build_tlv("00", "br.gov.bcb.pix")
    mai_key = build_tlv("01", pix_key)
    mai_desc = build_tlv("02", description[:40]) if description else ""
    p26 = build_tlv("26", mai_gui + mai_key + mai_desc)
    p52 = build_tlv("52", "0000")
    p53 = build_tlv("53", "986")
    p54 = build_tlv("54", f"{amount:.2f}")
    p58 = build_tlv("58", "BR")
    clean_name = re.sub(r"[^A-Za-z0-9 ]", "", merchant_name)[:25] or "CORTEX ERP"
    p59 = build_tlv("59", clean_name.strip())
    clean_city = re.sub(r"[^A-Za-z0-9 ]", "", merchant_city)[:15] or "BRASILIA"
    p60 = build_tlv("60", clean_city.strip())
    clean_txid = re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***"
    p62 = build_tlv("62", build_tlv("05", clean_txid))
    payload = p00 + p26 + p52 + p53 + p54 + p58 + p59 + p60 + p62 + "6304"
    crc = crc16_ccitt(payload)
    return payload + crc


class PaymentGatewayService:
    @staticmethod
    async def create_charge(
        entry_id: int,
        billing_type: str = "PIX",  # PIX, BOLETO, CREDIT_CARD
        company_id: int = 1,
    ) -> Dict[str, Any]:
        """Cria cobrança no gateway (Asaas ou fallback local inteligente com QR Code)."""
        conn = get_conn()
        cur = conn.cursor()
        entry = cur.execute("""
            SELECT e.*, c.name as contact_name, c.document as contact_doc, c.email as contact_email, c.phone as contact_phone
            FROM financial_entries e
            LEFT JOIN contacts c ON c.id = e.contact_id
            WHERE e.id = ? AND e.company_id = ?
        """, (entry_id, company_id)).fetchone()

        if not entry:
            conn.close()
            raise ValueError("Lançamento financeiro não encontrado.")

        amount = float(entry["amount"])
        due_date = entry["due_date"]
        client_name = entry["contact_name"] or "Consumidor Final"
        client_doc = re.sub(r"\D", "", entry["contact_doc"] or "00000000000")

        # Verifica se já existe cobrança ativa para este título
        existing = cur.execute("SELECT * FROM payment_charges WHERE entry_id = ? AND status = 'PENDING'", (entry_id,)).fetchone()
        if existing:
            conn.close()
            return dict(existing)

        # Se houver chave Asaas configurada, tenta integrar com a API real
        if ASAAS_API_KEY:
            try:
                headers = {"access_token": ASAAS_API_KEY, "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # 1. Cria ou recupera cliente no Asaas
                    cust_res = await client.post(f"{ASAAS_BASE_URL}/customers", headers=headers, json={
                        "name": client_name,
                        "cpfCnpj": client_doc,
                        "email": entry["contact_email"] or "cliente@empresa.com.br",
                        "mobilePhone": entry["contact_phone"] or "65999999999",
                    })
                    cust_id = cust_res.json().get("id") if cust_res.status_code in (200, 201) else "cust_mock"

                    # 2. Cria cobrança
                    charge_res = await client.post(f"{ASAAS_BASE_URL}/payments", headers=headers, json={
                        "customer": cust_id,
                        "billingType": billing_type,
                        "value": amount,
                        "dueDate": due_date,
                        "description": f"Cortex ERP - {entry['description']} (#{entry_id})",
                        "postalService": False,
                    })
                    if charge_res.status_code in (200, 201):
                        ch_data = charge_res.json()
                        gw_id = ch_data.get("id")
                        inv_url = ch_data.get("invoiceUrl")
                        bank_slip = ch_data.get("bankSlipUrl")

                        # Se for PIX, obtém QR Code da API
                        pix_payload = ""
                        pix_qr_b64 = ""
                        if billing_type == "PIX":
                            pix_res = await client.get(f"{ASAAS_BASE_URL}/payments/{gw_id}/pixQrCode", headers=headers)
                            if pix_res.status_code == 200:
                                pd = pix_res.json()
                                pix_payload = pd.get("payload", "")
                                pix_qr_b64 = pd.get("encodedImage", "")

                        cur.execute("""
                            INSERT INTO payment_charges (
                                company_id, entry_id, gateway, gateway_id, billing_type,
                                status, value, due_date, pix_copy_paste, pix_qr_code_b64,
                                bank_slip_url, invoice_url, customer_id
                            ) VALUES (?, ?, 'asaas', ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            company_id, entry_id, gw_id, billing_type,
                            amount, due_date, pix_payload, pix_qr_b64,
                            bank_slip, inv_url, cust_id,
                        ))
                        cid = cur.lastrowid
                        conn.commit()
                        charge_row = cur.execute("SELECT * FROM payment_charges WHERE id = ?", (cid,)).fetchone()
                        conn.close()
                        return dict(charge_row)
            except Exception as e:
                print(f"[Asaas Warning] Falha na chamada da API Asaas, usando motor integrado local: {e}")

        # Fallback Integrado: Simulador de Alta Fidelidade com QR Code Dinâmico Real (BR Code EMV / CRC16-CCITT)
        gw_id = f"pay_{uuid.uuid4().hex[:12]}"
        comp_row = cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        comp_dict = dict(comp_row) if comp_row else {}
        pix_key = comp_dict.get("chave_pix") or comp_dict.get("cnpj") or "financeiro@empresa.com.br"
        comp_name = comp_dict.get("nome_fantasia") or comp_dict.get("razao_social") or "CORTEX ERP"
        comp_city = comp_dict.get("cidade") or "CUIABA"

        pix_code = generate_pix_brcode(
            pix_key=pix_key,
            merchant_name=comp_name,
            merchant_city=comp_city,
            amount=amount,
            txid=gw_id[:25],
            description=f"Fat #{entry_id}",
        )
        pix_qr_b64 = generate_qr_code_base64(pix_code)
        invoice_url = f"/api/payments/receipt/{gw_id}"
        bank_slip_url = f"/api/payments/bank-slip/{gw_id}"

        cur.execute("""
            INSERT INTO payment_charges (
                company_id, entry_id, gateway, gateway_id, billing_type,
                status, value, due_date, pix_copy_paste, pix_qr_code_b64,
                bank_slip_url, invoice_url, customer_id
            ) VALUES (?, ?, 'cortex_gateway', ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id, entry_id, gw_id, billing_type,
            amount, due_date, pix_code, pix_qr_b64,
            bank_slip_url, invoice_url, f"cust_{client_doc[:8]}",
        ))
        cid = cur.lastrowid
        conn.commit()
        charge_row = cur.execute("SELECT * FROM payment_charges WHERE id = ?", (cid,)).fetchone()
        conn.close()
        return dict(charge_row)

    @staticmethod
    def process_webhook_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa eventos do webhook do gateway (ex: PAYMENT_RECEIVED, PAYMENT_CONFIRMED)
        e liquida automaticamente o lançamento no ERP.
        """
        event_name = payload.get("event") or payload.get("status")
        payment_data = payload.get("payment") or payload
        gateway_id = payment_data.get("id")

        if not gateway_id:
            return {"status": "ignored", "reason": "Sem ID da cobrança"}

        conn = get_conn()
        begin_write(conn)
        cur = conn.cursor()
        charge = cur.execute("SELECT * FROM payment_charges WHERE gateway_id = ?", (gateway_id,)).fetchone()
        if not charge:
            conn.close()
            return {"status": "ignored", "reason": f"Cobrança {gateway_id} não encontrada no Cortex ERP"}

        entry_id = charge["entry_id"]
        entry = cur.execute("SELECT * FROM financial_entries WHERE id = ?", (entry_id,)).fetchone()
        if not entry:
            conn.close()
            return {"status": "ignored", "reason": "Lançamento financeiro não localizado"}

        # Eventos de liquidação
        if event_name in ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED", "RECEIVED", "CONFIRMED"):
            if charge["status"] == "CONFIRMED" or entry["status"] == "pago":
                conn.close()
                return {"status": "ignored", "reason": "Cobrança já liquidada anteriormente (evento duplicado)."}
            paid_val = float(payment_data.get("value") or charge["value"])
            net_val = float(payment_data.get("netValue") or paid_val)
            pay_date = payment_data.get("confirmedDate") or payment_data.get("paymentDate") or date.today().isoformat()
            pay_method = charge["billing_type"]

            # Atualiza charge
            cur.execute("""
                UPDATE payment_charges
                SET status = 'CONFIRMED', payment_date = ?, net_value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (pay_date, net_val, charge["id"]))

            # Baixa automática no financeiro
            cur.execute("""
                UPDATE financial_entries
                SET paid_amount = amount, status = 'pago', bank_account_id = COALESCE(bank_account_id, 1)
                WHERE id = ?
            """, (entry_id,))

            cur.execute("""
                INSERT INTO financial_payments (
                    entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes
                ) VALUES (?, ?, ?, ?, ?, ?, 'Baixa automática via Webhook Gateway')
            """, (
                entry_id,
                entry["bank_account_id"] or 1,
                pay_date,
                paid_val,
                paid_val,
                pay_method,
            ))

            recalculate_bank_balances(conn)
            log_audit(conn, action="webhook_payment", entity="payment_charges", entity_id=charge["id"], new_data={"gateway_id": gateway_id, "value": paid_val})
            conn.close()
            return {"status": "success", "message": f"Título #{entry_id} liquidado automaticamente via {pay_method}!"}

        # Evento de vencido
        elif event_name in ("PAYMENT_OVERDUE", "OVERDUE"):
            cur.execute("UPDATE payment_charges SET status = 'OVERDUE', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (charge["id"],))
            conn.commit()
            conn.close()
            return {"status": "updated", "message": "Cobrança marcada como vencida."}

        conn.close()
        return {"status": "unhandled", "event": event_name}
