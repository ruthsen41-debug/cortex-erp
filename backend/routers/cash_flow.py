from datetime import date, timedelta
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

router = APIRouter(prefix="/api/reports", tags=["Fluxo de Caixa"])


@router.get("/cash-flow")
def get_cash_flow_statement(days_ahead: int = 30, days_behind: int = 15, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Relatório avançado de Fluxo de Caixa: Realizado vs. Previsto diário e acumulado.
    Calcula com precisão a projeção de saldo e identifica quebras de caixa futuras.
    """
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    accounts = rows_to_dicts(cur.execute("SELECT * FROM bank_accounts WHERE active = 1 AND company_id = ?", (company_id,)).fetchall())
    initial_balance = round(sum(float(a["current_balance"]) for a in accounts), 2)

    entries = rows_to_dicts(cur.execute("""
        SELECT e.*, cat.name as category_name
        FROM financial_entries e
        LEFT JOIN categories cat ON cat.id = e.category_id
        WHERE e.status != 'cancelado' AND e.company_id = ?
    """, (company_id,)).fetchall())

    payments = rows_to_dicts(cur.execute("""
        SELECT p.*, e.type as entry_type
        FROM financial_payments p
        JOIN financial_entries e ON e.id = p.entry_id
        WHERE e.company_id = ?
    """, (company_id,)).fetchall())
    conn.close()

    today = date.today()
    start_date = today - timedelta(days=days_behind)
    end_date = today + timedelta(days=days_ahead)

    daily_timeline = []
    projected_balance = initial_balance
    cash_shortage_dates = []

    curr = start_date
    while curr <= end_date:
        d_str = curr.isoformat()
        is_past_or_today = curr <= today

        # Realizado (pagamentos e baixas efetivadas na data)
        realized_in = sum(float(p["total_cash_flow"]) for p in payments if p["payment_date"] == d_str and p["entry_type"] == "receita")
        realized_out = sum(float(p["total_cash_flow"]) for p in payments if p["payment_date"] == d_str and p["entry_type"] == "despesa")

        # Previsto (títulos com vencimento na data)
        predicted_in = sum(float(e["amount"]) for e in entries if e["due_date"] == d_str and e["type"] == "receita")
        predicted_out = sum(float(e["amount"]) for e in entries if e["due_date"] == d_str and e["type"] == "despesa")

        # Projeção futura de saldo
        if curr > today:
            projected_balance += (predicted_in - predicted_out)
            if projected_balance < 0:
                cash_shortage_dates.append({"date": d_str, "projected_balance": round(projected_balance, 2)})

        daily_timeline.append({
            "date": d_str,
            "day_label": curr.strftime("%d/%m"),
            "is_past": is_past_or_today,
            "realized_inflows": round(realized_in, 2),
            "realized_outflows": round(realized_out, 2),
            "realized_net": round(realized_in - realized_out, 2),
            "predicted_inflows": round(predicted_in, 2),
            "predicted_outflows": round(predicted_out, 2),
            "predicted_net": round(predicted_in - predicted_out, 2),
            "balance": round(projected_balance, 2) if curr > today else initial_balance,
        })

        curr += timedelta(days=1)

    return {
        "initial_balance": initial_balance,
        "days_projected": days_ahead,
        "timeline": daily_timeline,
        "cash_shortage_alert": len(cash_shortage_dates) > 0,
        "shortage_dates": cash_shortage_dates,
        "summary": {
            "total_predicted_inflows": round(sum(d["predicted_inflows"] for d in daily_timeline if not d["is_past"]), 2),
            "total_predicted_outflows": round(sum(d["predicted_outflows"] for d in daily_timeline if not d["is_past"]), 2),
            "projected_final_balance": round(projected_balance, 2),
        },
    }
