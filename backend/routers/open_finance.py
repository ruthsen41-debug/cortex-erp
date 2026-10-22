import os
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any

try:
    from ..database import get_conn, begin_write, recalculate_bank_balances
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from .ofx import _score_match
except ImportError:
    from database import get_conn, begin_write, recalculate_bank_balances
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from routers.ofx import _score_match

router = APIRouter(prefix="/api/open-finance", tags=["Open Finance"])

_PLUGGY_URL = "https://api.pluggy.ai"


def _pluggy_key() -> str:
    cid = os.getenv("PLUGGY_CLIENT_ID", "")
    csec = os.getenv("PLUGGY_CLIENT_SECRET", "")
    if not cid or not csec:
        raise HTTPException(
            status_code=503,
            detail="Open Finance não configurado. Defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET nas variáveis de ambiente."
        )
    resp = httpx.post(f"{_PLUGGY_URL}/auth", json={"clientId": cid, "clientSecret": csec}, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Erro ao autenticar com Pluggy: {resp.text[:200]}")
    return resp.json()["apiKey"]


@router.get("/status")
def open_finance_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    configured = bool(os.getenv("PLUGGY_CLIENT_ID") and os.getenv("PLUGGY_CLIENT_SECRET"))
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    integrations = rows_to_dicts(conn.execute(
        "SELECT * FROM bank_integrations WHERE company_id = ? AND active = 1 ORDER BY created_at DESC",
        (company_id,)
    ).fetchall())
    conn.close()
    return {"configured": configured, "integrations": integrations}


@router.post("/connect-token")
def get_connect_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    api_key = _pluggy_key()
    resp = httpx.post(f"{_PLUGGY_URL}/connect_token", json={}, headers={"X-API-KEY": api_key}, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Erro ao gerar token de conexão Pluggy.")
    return {"connect_token": resp.json()["accessToken"]}


@router.post("/connect")
async def save_pluggy_item(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        body = await req.json()
    except Exception:
        body = {}
    item_id = body.get("itemId")
    if not item_id:
        raise HTTPException(status_code=400, detail="itemId obrigatório.")

    api_key = _pluggy_key()
    item_resp = httpx.get(f"{_PLUGGY_URL}/items/{item_id}", headers={"X-API-KEY": api_key}, timeout=10)
    connector_name = "Banco Conectado"
    if item_resp.status_code == 200:
        connector_name = item_resp.json().get("connector", {}).get("name", connector_name)

    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT id FROM bank_integrations WHERE item_id = ? AND company_id = ?",
        (item_id, company_id)
    ).fetchone()
    if existing:
        cur.execute(
            "UPDATE bank_integrations SET active = 1, connector_name = ?, status = 'connected' WHERE item_id = ? AND company_id = ?",
            (connector_name, item_id, company_id)
        )
    else:
        cur.execute(
            "INSERT INTO bank_integrations (company_id, item_id, connector_name, status) VALUES (?, ?, ?, 'connected')",
            (company_id, item_id, connector_name)
        )
    conn.commit()
    log_audit(conn, action="connect_open_finance", entity="bank_integrations", new_data={"item_id": item_id}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": f"{connector_name} conectado com sucesso!"}


@router.post("/sync/{item_id}")
def sync_open_finance(item_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Sync last 90 days of transactions from Pluggy for a connected bank."""
    from datetime import date, timedelta
    company_id = current_user.get("company_id", 1)
    api_key = _pluggy_key()

    conn = get_conn()
    integration = conn.execute(
        "SELECT * FROM bank_integrations WHERE item_id = ? AND company_id = ? AND active = 1",
        (item_id, company_id)
    ).fetchone()
    if not integration:
        conn.close()
        raise HTTPException(status_code=404, detail="Integração não encontrada.")

    acc_resp = httpx.get(f"{_PLUGGY_URL}/accounts?itemId={item_id}", headers={"X-API-KEY": api_key}, timeout=15)
    if acc_resp.status_code != 200:
        conn.close()
        raise HTTPException(status_code=502, detail="Erro ao buscar contas do Pluggy.")

    begin_write(conn)
    cur = conn.cursor()
    categories = rows_to_dicts(cur.execute("SELECT * FROM categories").fetchall())
    open_entries = rows_to_dicts(cur.execute(
        "SELECT id, type, amount, due_date FROM financial_entries WHERE status IN ('pendente', 'parcial') AND company_id = ?",
        (company_id,)
    ).fetchall())

    date_from = (date.today() - timedelta(days=90)).isoformat()
    date_to = date.today().isoformat()
    imported = 0

    for acc in acc_resp.json().get("results", []):
        pluggy_acc_id = acc["id"]
        acc_name = acc.get("name", "Conta")
        acc_balance = float(acc.get("balance", 0))

        bank_acc_row = cur.execute(
            "SELECT id FROM bank_accounts WHERE pluggy_account_id = ? AND company_id = ?",
            (pluggy_acc_id, company_id)
        ).fetchone()
        if not bank_acc_row:
            inst = acc.get("institution", {})
            cur.execute("""
                INSERT INTO bank_accounts (company_id, name, bank_code, bank_name, account_type, initial_balance, current_balance, pluggy_account_id)
                VALUES (?, ?, '999', ?, 'corrente', ?, ?, ?)
            """, (company_id, acc_name, inst.get("name", "Open Finance"), acc_balance, acc_balance, pluggy_acc_id))
            bank_acc_id = cur.lastrowid
        else:
            bank_acc_id = bank_acc_row["id"]

        txn_resp = httpx.get(
            f"{_PLUGGY_URL}/transactions?accountId={pluggy_acc_id}&from={date_from}&to={date_to}",
            headers={"X-API-KEY": api_key},
            timeout=30
        )
        if txn_resp.status_code != 200:
            continue

        for txn in txn_resp.json().get("results", []):
            fitid = str(txn.get("id", ""))
            if cur.execute("SELECT id FROM ofx_transactions WHERE fitid = ? AND company_id = ?", (fitid, company_id)).fetchone():
                continue

            amt = float(txn.get("amount", 0))
            posted_date = (txn.get("date") or txn.get("operationDate") or date_to)[:10]
            memo = txn.get("description") or (txn.get("merchant") or {}).get("name") or "Transação"
            is_credit = amt > 0
            memo_low = memo.lower()

            best_match_id = None
            best_score = 0.5
            for oe in open_entries:
                score = _score_match(amt, posted_date, float(oe["amount"]), oe["due_date"], oe["type"], is_credit)
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
            """, (company_id, bank_acc_id, fitid, posted_date, amt, memo, sug_cat_id, best_match_id))
            imported += 1

    cur.execute(
        "UPDATE bank_integrations SET last_sync = CURRENT_TIMESTAMP, status = 'synced' WHERE item_id = ? AND company_id = ?",
        (item_id, company_id)
    )
    recalculate_bank_balances(conn)
    log_audit(conn, action="sync_open_finance", entity="bank_integrations", new_data={"imported": imported}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "imported": imported, "message": f"{imported} transações sincronizadas com sucesso!"}


@router.delete("/disconnect/{item_id}")
def disconnect_open_finance(item_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()
    cur.execute(
        "UPDATE bank_integrations SET active = 0 WHERE item_id = ? AND company_id = ?",
        (item_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Conexão com Open Finance removida."}
