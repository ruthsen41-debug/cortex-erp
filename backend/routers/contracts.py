from datetime import date
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any, List, Optional

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.service_orders import ContractCreate
    from ..schemas.phase3 import ContractAdjustRequest, ContractBatchAdjustRequest
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.service_orders import ContractCreate
    from schemas.phase3 import ContractAdjustRequest, ContractBatchAdjustRequest

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


@router.post("/{contract_id}/adjust")
def adjust_contract(contract_id: int, data: ContractAdjustRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Reajuste automático anual/periódico de contrato por índice (IPCA, IGP-M ou percentual fixo)."""
    conn = get_conn()
    cur = conn.cursor()
    c = cur.execute("SELECT * FROM recurring_contracts WHERE id = ?", (contract_id,)).fetchone()
    if not c:
        conn.close()
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")

    old_val = float(c["monthly_value"])
    factor = 1.0 + (data.adjustment_percent / 100.0)
    new_val = round(old_val * factor, 2)
    today_str = date.today().isoformat()

    cur.execute("""
        UPDATE recurring_contracts
        SET monthly_value = ?, inflation_index = ?, adjustment_percent = ?, last_adjusted_at = ?
        WHERE id = ?
    """, (new_val, data.inflation_index, data.adjustment_percent, today_str, contract_id))

    conn.commit()
    log_audit(conn, action="adjust_contract", entity="recurring_contracts", entity_id=contract_id, new_data={"old": old_val, "new": new_val, "percent": data.adjustment_percent, "index": data.inflation_index}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "contract_id": contract_id,
        "previous_value": old_val,
        "new_value": new_val,
        "adjustment_percent": data.adjustment_percent,
        "inflation_index": data.inflation_index,
        "adjusted_at": today_str
    }


@router.post("/batch-adjust")
def batch_adjust_contracts(data: ContractBatchAdjustRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Reajuste automático em lote para todos os contratos ativos (ou selecionados)."""
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    sql = "SELECT id, title, monthly_value FROM recurring_contracts WHERE status = 'ativo'"
    params = []
    if data.contract_ids:
        placeholders = ",".join(["?"] * len(data.contract_ids))
        sql += f" AND id IN ({placeholders})"
        params.extend(data.contract_ids)

    contracts = cur.execute(sql, params).fetchall()
    if not contracts:
        conn.close()
        return {"status": "ok", "message": "Nenhum contrato ativo encontrado para reajuste.", "adjusted_count": 0}

    today_str = date.today().isoformat()
    factor = 1.0 + (data.adjustment_percent / 100.0)
    adjusted_list = []

    for c in contracts:
        cid = c["id"]
        old_val = float(c["monthly_value"])
        new_val = round(old_val * factor, 2)
        cur.execute("""
            UPDATE recurring_contracts
            SET monthly_value = ?, inflation_index = ?, adjustment_percent = ?, last_adjusted_at = ?
            WHERE id = ?
        """, (new_val, data.inflation_index, data.adjustment_percent, today_str, cid))
        adjusted_list.append({"id": cid, "title": c["title"], "old_value": old_val, "new_value": new_val})

    conn.commit()
    log_audit(conn, action="batch_adjust_contracts", entity="recurring_contracts", entity_id=0, new_data={"count": len(adjusted_list), "percent": data.adjustment_percent, "index": data.inflation_index}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "adjusted_count": len(adjusted_list),
        "adjustment_percent": data.adjustment_percent,
        "inflation_index": data.inflation_index,
        "contracts": adjusted_list
    }
