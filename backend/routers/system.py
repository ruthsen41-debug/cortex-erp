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


# ── Tela de apresentação (antes do login) ────────────────────────────────
# Configuração global da instalação: aparece antes de qualquer login, então
# só o administrador da empresa principal (company_id 1) pode alterá-la.

def _ensure_settings_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )


def _get_setting(conn, key: str, default: str) -> str:
    _ensure_settings_table(conn)
    row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


@router.get("/intro")
def get_intro_setting():
    """Público: informa se a tela de apresentação deve aparecer antes do login."""
    conn = get_conn()
    try:
        enabled = _get_setting(conn, "intro_enabled", "1") == "1"
        conn.commit()
    finally:
        conn.close()
    return {"enabled": enabled}


@router.put("/intro")
def set_intro_setting(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Liga/desliga a tela de apresentação (apenas admin da empresa principal)."""
    if current_user.get("role") != "admin" or int(current_user.get("company_id") or 0) != 1:
        raise HTTPException(status_code=403, detail="Apenas o administrador principal pode alterar a apresentação.")
    if not isinstance(payload.get("enabled"), bool):
        raise HTTPException(status_code=422, detail="Informe 'enabled' como true ou false.")
    value = "1" if payload["enabled"] else "0"
    conn = get_conn()
    try:
        _ensure_settings_table(conn)
        conn.execute(
            "INSERT INTO system_settings (key, value) VALUES ('intro_enabled', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (value,),
        )
        conn.commit()
    finally:
        conn.close()
    return {"enabled": payload["enabled"]}
