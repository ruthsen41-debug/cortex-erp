import os
import io
import sqlite3
import tempfile
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Response
from typing import Dict, Any, Optional

try:
    from ..config import DB_PATH
    from ..database import get_conn, is_postgres
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
except ImportError:
    from config import DB_PATH
    from database import get_conn, is_postgres
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(prefix="/api/system", tags=["Sistema, Backup & Monitoramento"])


@router.get("/metrics")
def get_system_metrics(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Métricas em tempo real de saúde, recursos e volumetria do banco de dados."""
    db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

    conn = get_conn()
    cur = conn.cursor()

    counts = {
        "products": cur.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "contacts": cur.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
        "financial_entries": cur.execute("SELECT COUNT(*) FROM financial_entries").fetchone()[0],
        "sales": cur.execute("SELECT COUNT(*) FROM sales").fetchone()[0],
        "invoices": cur.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
        "users": cur.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "audit_logs": cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0],
    }
    conn.close()

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": {
            "path": str(DB_PATH),
            "size_mb": db_size_mb,
            "counts": counts
        },
        "system": {
            "version": "4.5.0-pro+",
            "engine": "FastAPI + SQLite (ACID)",
            "environment": os.getenv("ENVIRONMENT", "production")
        }
    }


@router.get("/backup")
def download_database_backup(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Gera um Snapshot íntegro e transacional do banco de dados via SQLite Online Backup API,
    garantindo cópia consistente sem risco de corrupção ou lock.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores podem realizar backup do banco.")

    if is_postgres():
        raise HTTPException(
            status_code=501,
            detail="Backup pela API só existe para SQLite. Com PostgreSQL use pg_dump (veja o README).",
        )

    source_conn = sqlite3.connect(str(DB_PATH))
    dest_bytes = io.BytesIO()

    # Cria arquivo temporário para exportar o backup online
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        dest_conn = sqlite3.connect(tmp_path)
        source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()

        with open(tmp_path, "rb") as f:
            content = f.read()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cortex_backup_{today_str}.db"

    return Response(
        content=content,
        media_type="application/x-sqlite3",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/logs")
def get_audit_logs(limit: int = 100, entity: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Consulta trilha de auditoria e logs do sistema."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = "SELECT * FROM audit_logs WHERE company_id = ?"
    params = [company_id]
    if entity:
        sql += " AND entity = ?"
        params.append(entity)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows
