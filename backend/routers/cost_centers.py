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


@router.get("/budget")
def get_cost_centers_budget(month: str = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Compara o orçamento previsto (monthly_budget) com os gastos reais do mês por centro de custo."""
    from datetime import date
    conn = get_conn()
    cur = conn.cursor()
    target_month = month or date.today().strftime("%Y-%m")
    company_id = current_user.get("company_id", 1)

    centers = rows_to_dicts(cur.execute("SELECT * FROM cost_centers WHERE active = 1 ORDER BY code").fetchall())
    entries = rows_to_dicts(cur.execute("""
        SELECT cost_center_id, amount, paid_amount, status
        FROM financial_entries
        WHERE type = 'despesa' AND due_date LIKE ? AND status != 'cancelado' AND company_id = ?
    """, (f"{target_month}%", company_id)).fetchall())
    conn.close()

    result = []
    for c in centers:
        cid = c["id"]
        budget = float(c.get("monthly_budget") or 0.0)
        c_entries = [e for e in entries if e.get("cost_center_id") == cid]
        realized = sum(float(e.get("paid_amount") or 0.0) for e in c_entries)
        committed = sum(float(e.get("amount") or 0.0) for e in c_entries)
        diff = budget - committed
        usage_pct = round((committed / budget * 100.0), 1) if budget > 0 else 0.0

        result.append({
            "id": cid,
            "code": c["code"],
            "name": c["name"],
            "monthly_budget": budget,
            "realized": round(realized, 2),
            "committed": round(committed, 2),
            "available": round(diff, 2),
            "usage_percent": usage_pct,
            "is_over_budget": diff < 0,
        })
    return {"month": target_month, "cost_centers": result}


@router.put("/{cost_center_id}/budget")
def update_cost_center_budget(cost_center_id: int, req: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    budget = float(req.get("monthly_budget") or 0.0)
    conn.execute("UPDATE cost_centers SET monthly_budget = ? WHERE id = ?", (budget, cost_center_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Orçamento atualizado!"}
