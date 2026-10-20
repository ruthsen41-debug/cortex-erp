import uuid
from datetime import date
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List

try:
    from ..database import get_conn, recalculate_bank_balances
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.financial import BankAccountCreate, TransferRequest
except ImportError:
    from database import get_conn, recalculate_bank_balances
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.financial import BankAccountCreate, TransferRequest

router = APIRouter(prefix="/api/bank-accounts", tags=["Contas Bancárias"])


@router.get("")
def list_bank_accounts(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("SELECT * FROM bank_accounts WHERE active = 1 AND company_id = ? ORDER BY id", (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("")
def create_bank_account(req: BankAccountCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    init_bal = float(req.initial_balance or 0.0)

    cur.execute("""
        INSERT INTO bank_accounts (company_id, name, bank_code, bank_name, agency, account_number, account_type, initial_balance, current_balance, color)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id,
        req.name,
        req.bank_code or "000",
        req.bank_name,
        req.agency or "0001",
        req.account_number or "",
        req.account_type or "corrente",
        init_bal,
        init_bal,
        "#2563eb",
    ))
    acc_id = cur.lastrowid
    recalculate_bank_balances(conn)
    log_audit(conn, action="create", entity="bank_accounts", entity_id=acc_id, new_data=req.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": acc_id}


@router.post("/transfer")
def transfer_between_accounts(req: TransferRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    from_id = req.from_account_id
    to_id = req.to_account_id
    amount = req.amount
    transfer_date = req.date or date.today().isoformat()
    desc = req.description or "Transferência entre Contas"
    company_id = current_user.get("company_id", 1)

    if from_id == to_id or amount <= 0:
        raise HTTPException(status_code=400, detail="Selecione contas distintas e um valor maior que zero.")

    conn = get_conn()
    cur = conn.cursor()
    from_acc = cur.execute("SELECT name FROM bank_accounts WHERE id = ? AND company_id = ?", (from_id, company_id)).fetchone()
    to_acc = cur.execute("SELECT name FROM bank_accounts WHERE id = ? AND company_id = ?", (to_id, company_id)).fetchone()

    if not from_acc or not to_acc:
        conn.close()
        raise HTTPException(status_code=404, detail="Conta bancária de origem ou destino não encontrada.")

    uid = f"TRF-{uuid.uuid4().hex[:6].upper()}"

    trf_cat = cur.execute("SELECT id FROM categories WHERE dre_group = 'transferencia' OR code = '9.01' LIMIT 1").fetchone()
    trf_cat_id = trf_cat["id"] if trf_cat else 18

    # Saída na conta origem
    cur.execute("""
        INSERT INTO financial_entries (company_id, type, description, category_id, bank_account_id, payment_method, competence_date, due_date, amount, paid_amount, status, group_uid, origin_type)
        VALUES (?, 'despesa', ?, ?, ?, 'Transferência/TED', ?, ?, ?, ?, 'pago', ?, 'transferencia')
    """, (company_id, f"[Transf. Enviada -> {to_acc['name']}] {desc}", trf_cat_id, from_id, transfer_date, transfer_date, amount, amount, uid))
    out_id = cur.lastrowid
    cur.execute("""
        INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, 'Transferência/TED', 'Transferência entre contas')
    """, (out_id, from_id, transfer_date, amount, amount))

    # Entrada na conta destino
    cur.execute("""
        INSERT INTO financial_entries (company_id, type, description, category_id, bank_account_id, payment_method, competence_date, due_date, amount, paid_amount, status, group_uid, origin_type)
        VALUES (?, 'receita', ?, ?, ?, 'Transferência/TED', ?, ?, ?, ?, 'pago', ?, 'transferencia')
    """, (company_id, f"[Transf. Recebida <- {from_acc['name']}] {desc}", trf_cat_id, to_id, transfer_date, transfer_date, amount, amount, uid))
    in_id = cur.lastrowid
    cur.execute("""
        INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, 'Transferência/TED', 'Transferência entre contas')
    """, (in_id, to_id, transfer_date, amount, amount))

    recalculate_bank_balances(conn)
    log_audit(conn, action="transfer", entity="bank_accounts", entity_id=from_id, new_data=req.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Transferência realizada e saldos bancários atualizados!"}
