from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(prefix="/api/notifications", tags=["Central de Notificações"])


class NotificationCreate(BaseModel):
    title: str
    message: str
    type: Optional[str] = "info"  # info, warning, success, alert
    link: Optional[str] = ""


@router.get("")
def list_notifications(unread_only: bool = False, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = "SELECT * FROM notifications WHERE company_id = ?"
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY id DESC LIMIT 50"

    rows = rows_to_dicts(conn.execute(sql, (company_id,)).fetchall())
    unread_count = conn.execute("SELECT COUNT(*) FROM notifications WHERE company_id = ? AND is_read = 0", (company_id,)).fetchone()[0]
    conn.close()

    return {
        "unread_count": unread_count,
        "notifications": rows
    }


@router.post("")
def create_notification(data: NotificationCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    cur.execute("""
        INSERT INTO notifications (company_id, user_id, title, message, type, is_read, link)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (company_id, current_user.get("id"), data.title, data.message, data.type, data.link or ""))
    nid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"status": "ok", "id": nid}


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND company_id = ?", (notification_id, company_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "id": notification_id}


@router.post("/mark-all-read")
def mark_all_notifications_read(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("UPDATE notifications SET is_read = 1 WHERE company_id = ?", (company_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Todas as notificações marcadas como lidas."}
