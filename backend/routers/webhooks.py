import secrets
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..services.webhook_dispatcher import WebhookDispatcher, validate_target_url
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from services.webhook_dispatcher import WebhookDispatcher, validate_target_url

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks & Notificações Externas"])


class WebhookCreate(BaseModel):
    target_url: str = Field(..., description="URL que receberá as requisições POST do webhook")
    events: Optional[str] = "all"  # 'all' ou 'order.created,invoice.authorized,payment.received'
    secret: Optional[str] = None


@router.get("")
def list_webhooks(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT id, target_url, events, secret, active, created_at
        FROM webhook_subscriptions
        WHERE company_id = ?
        ORDER BY id DESC
    """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("")
def create_webhook(data: WebhookCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        validate_target_url(data.target_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    secret = data.secret or f"whsec_{secrets.token_hex(16)}"

    cur.execute("""
        INSERT INTO webhook_subscriptions (company_id, target_url, secret, events, active)
        VALUES (?, ?, ?, ?, 1)
    """, (company_id, data.target_url, secret, data.events or "all"))
    wid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create_webhook", entity="webhook_subscriptions", entity_id=wid, new_data={"url": data.target_url}, user_id=current_user.get("id"))
    conn.close()

    return {"status": "ok", "id": wid, "secret": secret, "target_url": data.target_url}


@router.delete("/{sub_id}")
def delete_webhook(sub_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("DELETE FROM webhook_subscriptions WHERE id = ? AND company_id = ?", (sub_id, company_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Inscrição de webhook removida."}


@router.get("/deliveries")
def list_webhook_deliveries(limit: int = 50, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT wd.*, ws.target_url
        FROM webhook_deliveries wd
        LEFT JOIN webhook_subscriptions ws ON ws.id = wd.subscription_id
        WHERE wd.company_id = ?
        ORDER BY wd.id DESC LIMIT ?
    """, (company_id, limit)).fetchall())
    conn.close()
    return rows


@router.post("/test")
async def trigger_test_webhook(current_user: Dict[str, Any] = Depends(get_current_user)):
    company_id = current_user.get("company_id", 1)
    payload = {
        "message": "Ping de teste do Cortex ERP Pro+",
        "timestamp": "2026-10-20T00:00:00",
        "sender": current_user.get("name", "Administrador")
    }
    deliveries = await WebhookDispatcher.dispatch_event("test.ping", payload, company_id=company_id)
    return {"status": "ok", "deliveries": deliveries}
