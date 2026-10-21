import secrets
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.crm import DealCreate, DealStageUpdate
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.crm import DealCreate, DealStageUpdate

router = APIRouter(prefix="/api/crm", tags=["CRM & Funil de Vendas"])


@router.get("")
def list_crm_deals(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM crm_deals ORDER BY id DESC").fetchall())
    conn.close()
    for r in rows:
        r["value"] = r.get("estimated_value", 0.0)
    return rows


@router.post("")
def save_crm_deal(req: DealCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    contact_name = "Cliente Potencial"
    if req.contact_id:
        c = cur.execute("SELECT name FROM contacts WHERE id = ? AND company_id = ?", (req.contact_id, company_id)).fetchone()
        if c:
            contact_name = c["name"]

    cur.execute("""
        INSERT INTO crm_deals (title, contact_id, contact_name, stage, estimated_value, probability, expected_close_date, responsible, temperature, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        req.title,
        req.contact_id,
        contact_name,
        req.stage or "prospeccao",
        float(req.value or 0.0),
        req.probability or 60,
        req.expected_close_date or (date.today() + timedelta(days=10)).isoformat(),
        current_user.get("name", "Vendedor"),
        "quente",
        req.notes or "",
    ))
    did = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="crm_deals", entity_id=did, new_data=req.model_dump(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": did}


@router.post("/{deal_id}/stage")
def move_crm_stage(deal_id: int, req: DealStageUpdate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("UPDATE crm_deals SET stage = ? WHERE id = ? AND company_id = ?", (req.stage, deal_id, current_user.get("company_id", 1)))
    conn.commit()
    log_audit(conn, action="update_stage", entity="crm_deals", entity_id=deal_id, new_data=req.model_dump(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok"}


@router.post("/{deal_id}/convert")
def convert_crm_to_quote(deal_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    deal_row = cur.execute("SELECT * FROM crm_deals WHERE id = ? AND company_id = ?", (deal_id, current_user.get("company_id", 1))).fetchone()
    if not deal_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")
    deal = dict(deal_row)

    next_num = (cur.execute("SELECT MAX(number) FROM sales").fetchone()[0] or 1000) + 1
    val = float(deal["estimated_value"] or 1000.0)
    cur.execute("""
        INSERT INTO sales (company_id, token_access, number, sale_type, status, contact_id, seller_name, sale_date, valid_until, subtotal, total_amount, payment_method, installments, bank_account_id, notes)
        VALUES (?, ?, ?, 'orcamento', 'enviado', ?, ?, ?, ?, ?, ?, 'Pix', 1, 1, ?)
    """, (
        current_user.get("company_id", 1),
        secrets.token_urlsafe(16),
        next_num,
        deal["contact_id"] or 1,
        deal.get("responsible") or current_user.get("name", "Vendedor"),
        date.today().isoformat(),
        (date.today() + timedelta(days=10)).isoformat(),
        val,
        val,
        f"Gerado a partir do Funil CRM: {deal['title']}",
    ))
    sale_id = cur.lastrowid
    cur.execute("UPDATE crm_deals SET stage = 'ganho' WHERE id = ? AND company_id = ?", (deal_id, current_user.get("company_id", 1)))
    conn.commit()
    log_audit(conn, action="convert_deal", entity="crm_deals", entity_id=deal_id, new_data={"sale_id": sale_id}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "sale_id": sale_id}
