from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Dict, Any

try:
    from ..database import get_conn, recalculate_bank_balances
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..fiscal_engine import gerar_ofx_exemplo, parse_ofx_content
except ImportError:
    from database import get_conn, recalculate_bank_balances
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from fiscal_engine import gerar_ofx_exemplo, parse_ofx_content

router = APIRouter(prefix="/api/ofx", tags=["Conciliação OFX"])


@router.get("")
def list_ofx_transactions(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT o.*, b.name as bank_name, c.name as suggested_category_name,
               e.description as matched_entry_description, e.due_date as matched_entry_due
        FROM ofx_transactions o
        LEFT JOIN bank_accounts b ON b.id = o.bank_account_id
        LEFT JOIN categories c ON c.id = o.suggested_category_id
        LEFT JOIN financial_entries e ON e.id = o.matched_entry_id
        ORDER BY o.status DESC, o.posted_date DESC, o.id DESC
    """).fetchall())
    conn.close()

    for r in rows:
        r["reconciled"] = (r.get("status") == "conciliado")
        r["date"] = r.get("posted_date")

    return rows


@router.post("/import")
async def import_ofx(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    content_type = req.headers.get("content-type", "")
    bank_account_id = 1
    ofx_content = ""

    if "multipart/form-data" in content_type:
        form = await req.form()
        file = form.get("file")
        if file and hasattr(file, "read"):
            bytes_content = await file.read()
            ofx_content = bytes_content.decode("utf-8", errors="ignore")
    else:
        try:
            data = await req.json()
            bank_account_id = int(data.get("bank_account_id") or 1)
            ofx_content = data.get("ofx_content") or ""
        except Exception:
            pass

    if not ofx_content.strip():
        ofx_content = gerar_ofx_exemplo()

    parsed = parse_ofx_content(ofx_content)
    conn = get_conn()
    cur = conn.cursor()
    categories = rows_to_dicts(cur.execute("SELECT * FROM categories").fetchall())
    open_entries = rows_to_dicts(cur.execute("SELECT id, type, description, amount, due_date, status FROM financial_entries WHERE status IN ('pendente', 'parcial')").fetchall())

    imported = 0
    for item in parsed:
        exists = cur.execute("SELECT id FROM ofx_transactions WHERE fitid = ?", (item["fitid"],)).fetchone()
        if exists:
            continue

        amt = float(item["amount"])
        is_credit = amt > 0
        abs_amt = abs(amt)
        memo_low = item["memo"].lower()

        matched_id = None
        for oe in open_entries:
            if (is_credit and oe["type"] == "receita") or (not is_credit and oe["type"] == "despesa"):
                if abs(float(oe["amount"]) - abs_amt) < 0.05:
                    matched_id = oe["id"]
                    break

        sug_cat_id = 1 if is_credit else 11
        for cat in categories:
            if (is_credit and cat["type"] == "receita") or (not is_credit and cat["type"] == "despesa"):
                kws = [k.strip().lower() for k in (cat.get("keywords") or "").split(",") if k.strip()]
                if any(k in memo_low for k in kws):
                    sug_cat_id = cat["id"]
                    break

        cur.execute("""
            INSERT INTO ofx_transactions (bank_account_id, fitid, posted_date, amount, memo, suggested_category_id, matched_entry_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente')
        """, (bank_account_id, item["fitid"], item["posted_date"], amt, item["memo"], sug_cat_id, matched_id))
        imported += 1

    conn.commit()
    log_audit(conn, action="import_ofx", entity="ofx_transactions", new_data={"imported": imported}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "imported": imported, "message": f"{imported} transações importadas com sucesso!"}


@router.post("/{ofx_id}/reconcile")
async def reconcile_ofx_transaction(ofx_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        data = await req.json()
    except Exception:
        data = {}

    conn = get_conn()
    cur = conn.cursor()
    ofx = cur.execute("SELECT * FROM ofx_transactions WHERE id = ?", (ofx_id,)).fetchone()
    if not ofx:
        conn.close()
        raise HTTPException(status_code=404, detail="Transação OFX não encontrada.")

    amt = float(ofx["amount"])
    abs_amt = abs(amt)
    e_type = "receita" if amt > 0 else "despesa"
    cat_id = int(data.get("category_id") or ofx["suggested_category_id"] or (1 if amt > 0 else 11))
    matched_id = data.get("matched_entry_id") or ofx["matched_entry_id"]

    if matched_id:
        cur.execute("""
            UPDATE financial_entries
            SET paid_amount = amount, status = 'pago', bank_account_id = ?
            WHERE id = ?
        """, (ofx["bank_account_id"], matched_id))
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, 'Conciliação OFX', ?)
        """, (matched_id, ofx["bank_account_id"], ofx["posted_date"], abs_amt, abs_amt, f"Conciliado via OFX ({ofx['fitid']})"))
    else:
        cur.execute("""
            INSERT INTO financial_entries (
                type, description, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount,
                status, document_number, origin_type, origin_id
            ) VALUES (?, ?, ?, 1, ?, 'Conciliação OFX', ?, ?, ?, ?, 'pago', ?, 'ofx', ?)
        """, (e_type, ofx["memo"], cat_id, ofx["bank_account_id"], ofx["posted_date"], ofx["posted_date"], abs_amt, abs_amt, ofx["fitid"], ofx_id))
        new_entry_id = cur.lastrowid
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, 'Conciliação OFX', 'Criado e baixado na conciliação OFX')
        """, (new_entry_id, ofx["bank_account_id"], ofx["posted_date"], abs_amt, abs_amt))
        matched_id = new_entry_id

    cur.execute("UPDATE ofx_transactions SET status = 'conciliado', matched_entry_id = ? WHERE id = ?", (matched_id, ofx_id))
    recalculate_bank_balances(conn)
    log_audit(conn, action="reconcile", entity="ofx_transactions", entity_id=ofx_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Transação conciliada!"}
