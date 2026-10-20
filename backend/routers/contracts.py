from datetime import date
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.service_orders import ContractCreate
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.service_orders import ContractCreate

router = APIRouter(prefix="/api/contracts", tags=["Contratos Recorrentes"])


@router.get("")
def list_contracts(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT r.*, c.name as contact_name, c.document as contact_doc
        FROM recurring_contracts r
        LEFT JOIN contacts c ON c.id = r.contact_id
        ORDER BY r.id DESC
    """).fetchall())
    conn.close()
    return rows


@router.post("")
def create_contract(req: ContractCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO recurring_contracts (title, contact_id, monthly_value, due_day, payment_method, bank_account_id, category_id, auto_emit_nfse, status, start_date, notes)
        VALUES (?, ?, ?, ?, 'Boleto', 1, 3, 1, 'ativo', ?, ?)
    """, (
        req.title,
        req.contact_id,
        req.amount,
        req.billing_day or 10,
        req.start_date or date.today().isoformat(),
        req.notes or "",
    ))
    cid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="recurring_contracts", entity_id=cid, new_data=req.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": cid}


@router.post("/{contract_id}/bill")
def bill_recurring_contract(contract_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    c = cur.execute("""
        SELECT r.*, ct.name as contact_name
        FROM recurring_contracts r
        LEFT JOIN contacts ct ON ct.id = r.contact_id
        WHERE r.id = ?
    """, (contract_id,)).fetchone()
    if not c:
        conn.close()
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")

    today = date.today()
    month_tag = today.strftime("%Y-%m")
    due_d = date(today.year, today.month, min(28, max(1, int(c["due_day"] or 10)))).isoformat()

    cur.execute("""
        INSERT INTO financial_entries (
            company_id, type, description, contact_id, category_id, cost_center_id, bank_account_id,
            payment_method, competence_date, due_date, amount, status, recurrence, origin_type, origin_id
        ) VALUES (1, 'receita', ?, ?, 3, 2, ?, ?, ?, ?, ?, 'pendente', 'mensal', 'contrato', ?)
    """, (
        f"[Contrato #{c['id']} - {month_tag}] {c['title']} - {c['contact_name']}",
        c["contact_id"],
        c["bank_account_id"] or 1,
        c["payment_method"] or "Boleto",
        today.isoformat(),
        due_d,
        float(c["monthly_value"]),
        contract_id,
    ))
    cur.execute("UPDATE recurring_contracts SET last_billed_month = ? WHERE id = ?", (month_tag, contract_id))
    conn.commit()
    log_audit(conn, action="bill_contract", entity="recurring_contracts", entity_id=contract_id, new_data={"month": month_tag}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": f"Mensalidade de {month_tag} gerada no Contas a Receber!"}
