from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Dict, Any

try:
    from ..database import get_conn, begin_write, recalculate_bank_balances
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..fiscal_engine import gerar_ofx_exemplo, parse_ofx_content
except ImportError:
    from database import get_conn, begin_write, recalculate_bank_balances
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from fiscal_engine import gerar_ofx_exemplo, parse_ofx_content

router = APIRouter(prefix="/api/ofx", tags=["Conciliação OFX"])


def _score_match(ofx_amt: float, ofx_date: str, entry_amt: float, entry_date: str, entry_type: str, is_credit: bool) -> float:
    """Returns confidence 0.0–1.0 for matching an OFX transaction to a financial entry."""
    if (is_credit and entry_type != "receita") or (not is_credit and entry_type != "despesa"):
        return 0.0
    abs_ofx = abs(ofx_amt)
    abs_entry = abs(entry_amt)
    if abs_ofx == 0 or abs_entry == 0:
        return 0.0
    amt_diff_pct = abs(abs_ofx - abs_entry) / max(abs_ofx, abs_entry)
    if amt_diff_pct > 0.02:
        return 0.0
    try:
        d1 = datetime.strptime(ofx_date[:10], "%Y-%m-%d")
        d2 = datetime.strptime(entry_date[:10], "%Y-%m-%d")
        days = abs((d1 - d2).days)
    except Exception:
        days = 999
    if days > 7:
        return 0.0
    return max(0.0, 1.0 - (amt_diff_pct * 5) - (days * 0.06))


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


@router.get("/reconciliation-summary")
def reconciliation_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Per-account reconciliation status and balance comparison."""
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    accounts = rows_to_dicts(conn.execute(
        "SELECT id, name, bank_name, current_balance, color FROM bank_accounts WHERE active = 1 AND company_id = ? ORDER BY id",
        (company_id,)
    ).fetchall())
    integrations = rows_to_dicts(conn.execute(
        "SELECT item_id, connector_name, last_sync, status FROM bank_integrations WHERE company_id = ? AND active = 1",
        (company_id,)
    ).fetchall())
    summary = []
    for acc in accounts:
        stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'conciliado' THEN 1 ELSE 0 END) as reconciled,
                SUM(CASE WHEN status = 'pendente'   THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'ignorado'   THEN 1 ELSE 0 END) as ignored,
                SUM(CASE WHEN status = 'pendente'   THEN ABS(amount) ELSE 0 END) as pending_amount,
                MAX(created_at) as last_import
            FROM ofx_transactions
            WHERE bank_account_id = ? AND company_id = ?
        """, (acc["id"], company_id)).fetchone()
        summary.append({
            **acc,
            "total_transactions": stats["total"] or 0,
            "reconciled_count":   stats["reconciled"] or 0,
            "pending_count":      stats["pending"] or 0,
            "ignored_count":      stats["ignored"] or 0,
            "pending_amount":     float(stats["pending_amount"] or 0),
            "last_import":        stats["last_import"],
        })
    conn.close()
    return {"accounts": summary, "integrations": integrations}


@router.post("/import")
async def import_ofx(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    content_type = req.headers.get("content-type", "")
    company_id = current_user.get("company_id", 1)
    bank_account_id = 1
    ofx_content = ""

    if "multipart/form-data" in content_type:
        form = await req.form()
        bank_account_id = int(form.get("bank_account_id") or 1)
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
    open_entries = rows_to_dicts(cur.execute(
        "SELECT id, type, amount, due_date FROM financial_entries WHERE status IN ('pendente', 'parcial') AND company_id = ?",
        (company_id,)
    ).fetchall())

    imported = 0
    for item in parsed:
        exists = cur.execute(
            "SELECT id FROM ofx_transactions WHERE fitid = ? AND company_id = ?",
            (item["fitid"], company_id)
        ).fetchone()
        if exists:
            continue

        amt = float(item["amount"])
        is_credit = amt > 0
        memo_low = item["memo"].lower()

        best_match_id = None
        best_score = 0.5
        for oe in open_entries:
            score = _score_match(amt, item["posted_date"], float(oe["amount"]), oe["due_date"], oe["type"], is_credit)
            if score > best_score:
                best_score = score
                best_match_id = oe["id"]

        sug_cat_id = 1 if is_credit else 11
        for cat in categories:
            if (is_credit and cat["type"] == "receita") or (not is_credit and cat["type"] == "despesa"):
                kws = [k.strip().lower() for k in (cat.get("keywords") or "").split(",") if k.strip()]
                if any(k in memo_low for k in kws):
                    sug_cat_id = cat["id"]
                    break

        cur.execute("""
            INSERT INTO ofx_transactions (company_id, bank_account_id, fitid, posted_date, amount, memo, suggested_category_id, matched_entry_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente')
        """, (company_id, bank_account_id, item["fitid"], item["posted_date"], amt, item["memo"], sug_cat_id, best_match_id))
        imported += 1

    conn.commit()
    log_audit(conn, action="import_ofx", entity="ofx_transactions", new_data={"imported": imported}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "imported": imported, "message": f"{imported} transações importadas com sucesso!"}


@router.post("/auto-reconcile-all")
def auto_reconcile_all(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Auto-reconcile pending OFX transactions that have a matched_entry with score >= 0.75."""
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()

    pending = rows_to_dicts(cur.execute(
        "SELECT * FROM ofx_transactions WHERE status = 'pendente' AND matched_entry_id IS NOT NULL AND company_id = ?",
        (company_id,)
    ).fetchall())
    open_entries = rows_to_dicts(cur.execute(
        "SELECT id, type, amount, due_date FROM financial_entries WHERE status IN ('pendente', 'parcial') AND company_id = ?",
        (company_id,)
    ).fetchall())
    open_map = {e["id"]: e for e in open_entries}

    reconciled = 0
    used = set()
    for ofx in pending:
        eid = ofx["matched_entry_id"]
        if eid in used or eid not in open_map:
            continue
        entry = open_map[eid]
        amt = float(ofx["amount"])
        score = _score_match(amt, ofx["posted_date"], float(entry["amount"]), entry["due_date"], entry["type"], amt > 0)
        if score < 0.75:
            continue
        abs_amt = abs(amt)
        cur.execute("""
            UPDATE financial_entries SET paid_amount = amount, status = 'pago', bank_account_id = ?
            WHERE id = ? AND company_id = ?
        """, (ofx["bank_account_id"], eid, company_id))
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, 'Conciliação OFX Auto', ?)
        """, (eid, ofx["bank_account_id"], ofx["posted_date"], abs_amt, abs_amt, f"Auto-conciliado ({ofx['fitid']})"))
        cur.execute(
            "UPDATE ofx_transactions SET status = 'conciliado', reconciled_at = CURRENT_TIMESTAMP WHERE id = ? AND company_id = ?",
            (ofx["id"], company_id)
        )
        used.add(eid)
        reconciled += 1

    recalculate_bank_balances(conn)
    log_audit(conn, action="auto_reconcile_all", entity="ofx_transactions", new_data={"reconciled": reconciled}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "reconciled": reconciled, "message": f"{reconciled} transações conciliadas automaticamente!"}


@router.get("/match-suggestions/{ofx_id}")
def match_suggestions(ofx_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return ranked match suggestions for a pending OFX transaction."""
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    ofx = conn.execute(
        "SELECT o.*, b.name as bank_name FROM ofx_transactions o LEFT JOIN bank_accounts b ON b.id = o.bank_account_id WHERE o.id = ? AND o.company_id = ?",
        (ofx_id, company_id)
    ).fetchone()
    if not ofx:
        conn.close()
        raise HTTPException(status_code=404, detail="Transação OFX não encontrada.")
    ofx = dict(ofx)
    amt = float(ofx["amount"])
    is_credit = amt > 0
    entry_type = "receita" if is_credit else "despesa"

    open_entries = rows_to_dicts(conn.execute("""
        SELECT e.id, e.type, e.description, e.amount, e.due_date, e.status,
               c.name as category_name, ct.name as contact_name
        FROM financial_entries e
        LEFT JOIN categories c ON c.id = e.category_id
        LEFT JOIN contacts ct ON ct.id = e.contact_id
        WHERE e.status IN ('pendente', 'parcial') AND e.type = ? AND e.company_id = ?
        ORDER BY ABS(e.amount - ?) ASC, e.due_date DESC
        LIMIT 20
    """, (entry_type, company_id, abs(amt))).fetchall())
    conn.close()

    scored = sorted(
        [{**oe, "score": round(_score_match(amt, ofx["posted_date"], float(oe["amount"]), oe["due_date"], oe["type"], is_credit), 3)} for oe in open_entries],
        key=lambda x: x["score"], reverse=True
    )
    return {"ofx": ofx, "suggestions": scored[:10]}


@router.post("/{ofx_id}/reconcile")
async def reconcile_ofx_transaction(ofx_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        data = await req.json()
    except Exception:
        data = {}

    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()
    ofx = cur.execute("SELECT * FROM ofx_transactions WHERE id = ? AND company_id = ?", (ofx_id, company_id)).fetchone()
    if not ofx:
        conn.close()
        raise HTTPException(status_code=404, detail="Transação OFX não encontrada.")
    if ofx["status"] == "conciliado":
        conn.close()
        raise HTTPException(status_code=400, detail="Esta transação OFX já foi conciliada.")

    amt = float(ofx["amount"])
    abs_amt = abs(amt)
    e_type = "receita" if amt > 0 else "despesa"
    cat_id = int(data.get("category_id") or ofx["suggested_category_id"] or (1 if amt > 0 else 11))
    matched_id = data.get("matched_entry_id") or ofx["matched_entry_id"]

    if matched_id:
        if not cur.execute("SELECT 1 FROM financial_entries WHERE id = ? AND company_id = ?", (matched_id, company_id)).fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Lançamento a conciliar não encontrado.")
        cur.execute("""
            UPDATE financial_entries SET paid_amount = amount, status = 'pago', bank_account_id = ?
            WHERE id = ? AND company_id = ?
        """, (ofx["bank_account_id"], matched_id, company_id))
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, 'Conciliação OFX', ?)
        """, (matched_id, ofx["bank_account_id"], ofx["posted_date"], abs_amt, abs_amt, f"Conciliado via OFX ({ofx['fitid']})"))
    else:
        cur.execute("""
            INSERT INTO financial_entries (
                company_id, type, description, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount,
                status, document_number, origin_type, origin_id
            ) VALUES (?, ?, ?, ?, 1, ?, 'Conciliação OFX', ?, ?, ?, ?, 'pago', ?, 'ofx', ?)
        """, (company_id, e_type, ofx["memo"], cat_id, ofx["bank_account_id"], ofx["posted_date"], ofx["posted_date"], abs_amt, abs_amt, ofx["fitid"], ofx_id))
        new_entry_id = cur.lastrowid
        cur.execute("""
            INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, 'Conciliação OFX', 'Criado e baixado na conciliação OFX')
        """, (new_entry_id, ofx["bank_account_id"], ofx["posted_date"], abs_amt, abs_amt))
        matched_id = new_entry_id

    cur.execute(
        "UPDATE ofx_transactions SET status = 'conciliado', matched_entry_id = ?, reconciled_at = CURRENT_TIMESTAMP WHERE id = ? AND company_id = ?",
        (matched_id, ofx_id, company_id)
    )
    recalculate_bank_balances(conn)
    log_audit(conn, action="reconcile", entity="ofx_transactions", entity_id=ofx_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Transação conciliada!"}


@router.delete("/{ofx_id}/ignore")
def ignore_ofx_transaction(ofx_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()
    ofx = cur.execute("SELECT id FROM ofx_transactions WHERE id = ? AND company_id = ?", (ofx_id, company_id)).fetchone()
    if not ofx:
        conn.close()
        raise HTTPException(status_code=404, detail="Transação OFX não encontrada.")
    cur.execute("UPDATE ofx_transactions SET status = 'ignorado' WHERE id = ? AND company_id = ?", (ofx_id, company_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Transação marcada como ignorada."}
