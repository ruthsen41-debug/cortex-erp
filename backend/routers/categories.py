from fastapi import APIRouter, Depends
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.financial import CategoryCreate
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.financial import CategoryCreate

router = APIRouter(prefix="/api/categories", tags=["Plano de Contas / Categorias"])


@router.get("")
def list_categories(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM categories ORDER BY code").fetchall())
    conn.close()
    return rows


@router.post("")
def create_category(req: CategoryCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("""
        INSERT INTO categories (company_id, code, name, type, dre_group, keywords)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (company_id, req.code, req.name, req.type, req.dre_group or "despesas_operacionais", req.keywords or ""))
    cat_id = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="categories", entity_id=cat_id, new_data=req.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": cat_id}
