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

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
def get_dashboard(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    today_str = date.today().isoformat()
    month_prefix = today_str[:7]
    company_id = current_user.get("company_id", 1)

    accounts = rows_to_dicts(cur.execute("SELECT * FROM bank_accounts WHERE active = 1 AND company_id = ? ORDER BY id", (company_id,)).fetchall())
    total_balance = round(sum(float(a["current_balance"]) for a in accounts), 2)

    entries = rows_to_dicts(cur.execute("""
        SELECT e.*, c.name as contact_name,
               cat.name as category_name, cat.dre_group as dre_group,
               b.name as bank_name
        FROM financial_entries e
        LEFT JOIN contacts c ON c.id = e.contact_id
        LEFT JOIN categories cat ON cat.id = e.category_id
        LEFT JOIN bank_accounts b ON b.id = e.bank_account_id
        WHERE e.status != 'cancelado' AND e.company_id = ?
    """, (company_id,)).fetchall())

    month_receivables = 0.0
    overdue_receivables = 0.0
    month_payables = 0.0
    overdue_payables = 0.0
    month_revenue = 0.0
    month_expenses = 0.0

    upcoming_payables = []
    upcoming_receivables = []

    for e in entries:
        net_total = float(e["amount"]) + float(e.get("interest") or 0.0) + float(e.get("fine") or 0.0) - float(e.get("discount") or 0.0)
        remaining = max(0.0, round(net_total - float(e.get("paid_amount") or 0.0), 2))
        due = e["due_date"]
        is_open = e["status"] in ("pendente", "parcial") and remaining > 0

        if e["type"] == "receita":
            if due.startswith(month_prefix):
                month_receivables += net_total
                month_revenue += float(e.get("paid_amount") or 0.0)
            if is_open and due < today_str:
                overdue_receivables += remaining
            if is_open and len(upcoming_receivables) < 5:
                upcoming_receivables.append(e)

        elif e["type"] == "despesa":
            if due.startswith(month_prefix):
                month_payables += net_total
                month_expenses += float(e.get("paid_amount") or 0.0)
            if is_open and due < today_str:
                overdue_payables += remaining
            if is_open and len(upcoming_payables) < 5:
                upcoming_payables.append(e)

    # Fluxo mensal dos últimos 6 meses
    monthly_flow = []
    for m in range(5, -1, -1):
        m_date = date.today().replace(day=1) - timedelta(days=m * 30)
        prefix = m_date.strftime("%Y-%m")
        label = m_date.strftime("%b/%y").capitalize()
        recs = sum(float(x.get("paid_amount") or x["amount"]) for x in entries if x["type"] == "receita" and x["due_date"].startswith(prefix))
        desps = sum(float(x.get("paid_amount") or x["amount"]) for x in entries if x["type"] == "despesa" and x["due_date"].startswith(prefix))
        monthly_flow.append({
            "month": label,
            "receitas": round(recs, 2),
            "despesas": round(desps, 2),
            "saldo": round(recs - desps, 2),
        })

    conn.close()

    return {
        "bank_accounts": accounts,
        "kpis": {
            "total_balance": total_balance,
            "month_receivables": round(month_receivables, 2),
            "overdue_receivables": round(overdue_receivables, 2),
            "month_payables": round(month_payables, 2),
            "overdue_payables": round(overdue_payables, 2),
            "month_revenue": round(month_revenue, 2),
            "net_income": round(month_receivables - month_payables, 2),
        },
        "monthly_cash_flow": monthly_flow,
        "upcoming_payables": upcoming_payables,
        "upcoming_receivables": upcoming_receivables,
    }
