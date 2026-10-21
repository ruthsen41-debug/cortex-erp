import re
import urllib.parse
from datetime import date
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..services.payment_gateway import PaymentGatewayService
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from services.payment_gateway import PaymentGatewayService

router = APIRouter(prefix="/api/collection", tags=["Régua de Cobrança Automática"])


@router.get("/rules")
def list_collection_rules(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM collection_rules ORDER BY trigger_days ASC").fetchall())
    conn.close()
    return rows


@router.get("/pending")
def list_pending_collections(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Identifica títulos a receber que correspondem aos gatilhos da régua de cobrança
    (ex: vencimento em 3 dias, vencimento hoje, vencido há 3 dias ou há 10 dias).
    """
    conn = get_conn()
    cur = conn.cursor()
    today = date.today()
    company_id = current_user.get("company_id", 1)

    rules = rows_to_dicts(cur.execute("SELECT * FROM collection_rules WHERE active = 1").fetchall())
    entries = rows_to_dicts(cur.execute("""
        SELECT e.*, c.name as contact_name, c.phone as contact_phone, c.whatsapp as contact_whatsapp, c.email as contact_email
        FROM financial_entries e
        LEFT JOIN contacts c ON c.id = e.contact_id
        WHERE e.type = 'receita' AND e.status IN ('pendente', 'parcial') AND e.company_id = ?
    """, (company_id,)).fetchall())

    pending = []
    for e in entries:
        try:
            due = date.fromisoformat(e["due_date"][:10])
        except Exception:
            continue

        days_diff = (today - due).days  # 0 se vence hoje, positivo se vencido, negativo se a vencer

        for r in rules:
            if r["trigger_days"] == days_diff:
                rem = max(0.0, float(e["amount"]) - float(e.get("paid_amount") or 0.0))
                pending.append({
                    "entry_id": e["id"],
                    "description": e["description"],
                    "contact_name": e.get("contact_name") or "Cliente",
                    "contact_phone": e.get("contact_whatsapp") or e.get("contact_phone") or "",
                    "contact_email": e.get("contact_email") or "",
                    "due_date": e["due_date"],
                    "amount": rem,
                    "rule_name": r["name"],
                    "trigger_days": r["trigger_days"],
                    "channel": r["channel"],
                    "template": r["message_template"],
                })

    conn.close()
    return pending


@router.post("/send/{entry_id}")
async def send_collection_notice(entry_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Gera a cobrança/notificação personalizada para o cliente via WhatsApp ou E-mail.
    Garante que há um link de pagamento Pix ou Boleto no texto.
    """
    try:
        data = await req.json()
    except Exception:
        data = {}

    channel = data.get("channel", "whatsapp")
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    entry = cur.execute("""
        SELECT e.*, c.name as contact_name, c.phone as contact_phone, c.whatsapp as contact_whatsapp, c.email as contact_email
        FROM financial_entries e
        LEFT JOIN contacts c ON c.id = e.contact_id
        WHERE e.id = ? AND e.company_id = ?
    """, (entry_id, company_id)).fetchone()

    if not entry:
        conn.close()
        raise HTTPException(status_code=404, detail="Título não encontrado.")

    # Cria ou busca cobrança no gateway para obter o link de pagamento
    charge = await PaymentGatewayService.create_charge(entry_id, billing_type="PIX", company_id=company_id)
    pay_link = charge.get("invoice_url") or charge.get("bank_slip_url") or f"https://cortex.erp/pay/{charge['gateway_id']}"

    client_name = entry["contact_name"] or "Cliente"
    val_str = f"R$ {float(entry['amount']):,.2f}"
    due_str = entry["due_date"]

    custom_text = data.get("message")
    if not custom_text:
        custom_text = f"Olá {client_name}! Lembramos do seu título de {val_str} com vencimento em {due_str}. Pague facilmente pelo Pix ou Boleto acessando: {pay_link}"
    else:
        custom_text = custom_text.replace("{cliente}", client_name).replace("{valor}", val_str).replace("{vencimento}", due_str).replace("{link_pagamento}", pay_link)

    phone = re.sub(r"\D", "", entry["contact_whatsapp"] or entry["contact_phone"] or "5565999999999")
    if len(phone) in (10, 11) and not phone.startswith("55"):
        phone = f"55{phone}"

    encoded_msg = urllib.parse.quote(custom_text)
    wa_link = f"https://wa.me/{phone}?text={encoded_msg}"

    # Salva log de envio
    cur.execute("""
        INSERT INTO collection_logs (company_id, entry_id, contact_id, channel, recipient, message_sent, status)
        VALUES (?, ?, ?, ?, ?, ?, 'enviado')
    """, (company_id, entry_id, entry["contact_id"], channel, phone if channel == "whatsapp" else (entry["contact_email"] or ""), custom_text))
    conn.commit()
    log_audit(conn, action="send_collection", entity="collection_logs", entity_id=entry_id, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "channel": channel,
        "whatsapp_url": wa_link,
        "recipient": phone,
        "message": custom_text,
    }


@router.get("/logs")
def list_collection_logs(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT l.*, e.description, ct.name as contact_name
        FROM collection_logs l
        JOIN financial_entries e ON e.id = l.entry_id
        LEFT JOIN contacts ct ON ct.id = l.contact_id
        WHERE l.company_id = ?
        ORDER BY l.id DESC LIMIT 50
    """, (company_id,)).fetchall())
    conn.close()
    return rows
