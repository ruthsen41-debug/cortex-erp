from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from datetime import date

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(tags=["Auditoria"])


def log_audit(conn, company_id: int, user_id: int, user_name: str,
              action: str, table_name: str, record_id: int = None,
              old_data: str = None, new_data: str = None, ip: str = ""):
    """Helper para registrar evento de auditoria."""
    try:
        conn.execute("""
            INSERT INTO audit_log
            (company_id, user_id, user_name, action, table_name, record_id, old_data, new_data, ip_address)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (company_id, user_id, user_name, action, table_name, record_id, old_data, new_data, ip))
    except Exception:
        pass


@router.get("/api/audit/logs")
def list_logs(
    table_name: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT * FROM audit_log WHERE company_id=?"
    params: list = [company_id]
    if table_name:
        q += " AND table_name=?"
        params.append(table_name)
    if action:
        q += " AND action=?"
        params.append(action)
    if user_id:
        q += " AND user_id=?"
        params.append(user_id)
    if start_date:
        q += " AND substr(created_at,1,10) >= ?"
        params.append(start_date)
    if end_date:
        q += " AND substr(created_at,1,10) <= ?"
        params.append(end_date)
    q += f" ORDER BY created_at DESC LIMIT {min(limit, 500)}"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return rows


@router.get("/api/audit/stats")
def audit_stats(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    total = conn.execute("SELECT COUNT(*) FROM audit_log WHERE company_id=?", (company_id,)).fetchone()[0]
    today = date.today().isoformat()
    today_count = conn.execute(
        "SELECT COUNT(*) FROM audit_log WHERE company_id=? AND substr(created_at,1,10)=?",
        (company_id, today)
    ).fetchone()[0]
    by_action = rows_to_dicts(conn.execute(
        "SELECT action, COUNT(*) as cnt FROM audit_log WHERE company_id=? GROUP BY action ORDER BY cnt DESC",
        (company_id,)
    ).fetchall())
    by_table = rows_to_dicts(conn.execute(
        "SELECT table_name, COUNT(*) as cnt FROM audit_log WHERE company_id=? GROUP BY table_name ORDER BY cnt DESC LIMIT 10",
        (company_id,)
    ).fetchall())
    by_user = rows_to_dicts(conn.execute(
        "SELECT user_name, COUNT(*) as cnt FROM audit_log WHERE company_id=? GROUP BY user_name ORDER BY cnt DESC LIMIT 10",
        (company_id,)
    ).fetchall())
    recent = rows_to_dicts(conn.execute(
        "SELECT * FROM audit_log WHERE company_id=? ORDER BY created_at DESC LIMIT 20",
        (company_id,)
    ).fetchall())
    conn.close()
    return {
        "total_events": total,
        "today_events": today_count,
        "by_action": by_action,
        "by_table": by_table,
        "by_user": by_user,
        "recent": recent,
    }
