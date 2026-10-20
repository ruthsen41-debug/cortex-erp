from fastapi import APIRouter, Depends
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(prefix="/api/cost-centers", tags=["Centros de Custo"])


@router.get("")
def list_cost_centers(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM cost_centers WHERE active = 1 ORDER BY code").fetchall())
    conn.close()
    return rows
