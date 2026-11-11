import secrets
from datetime import date
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(tags=["Portal do Empregado"])


# ── Manager endpoints (requires JWT) ──────────────────────────

@router.get("/api/employee-portal/employees")
def list_portal_employees(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Lista funcionários com link de acesso ao portal."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT id, name, cpf, email, cargo, status, portal_token FROM employees WHERE company_id=? ORDER BY name",
        (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/api/employee-portal/employees/{employee_id}/generate-token")
def generate_portal_token(employee_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera ou renova o token de acesso do empregado ao portal."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT id, name FROM employees WHERE id=? AND company_id=?", (employee_id, company_id)
    ).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(404, "Funcionário não encontrado.")
    token = secrets.token_urlsafe(20)
    conn.execute("UPDATE employees SET portal_token=? WHERE id=?", (token, employee_id))
    conn.commit()
    conn.close()
    return {"employee_id": employee_id, "name": emp["name"], "portal_token": token}


# ── Employee portal endpoints (token-based, no JWT) ───────────

class PortalLogin(BaseModel):
    cpf: str
    token: str


@router.post("/api/employee-portal/login")
def portal_login(body: PortalLogin):
    """Autenticação do empregado no portal pelo CPF + token."""
    conn = get_conn()
    # Normalize CPF
    cpf = "".join(c for c in body.cpf if c.isdigit())
    emp = conn.execute(
        "SELECT id, name, cargo, company_id FROM employees WHERE cpf=? AND portal_token=? AND status='ativo'",
        (cpf, body.token)
    ).fetchone()
    conn.close()
    if not emp:
        raise HTTPException(401, "CPF ou token inválidos.")
    return {"employee_id": emp["id"], "name": emp["name"], "cargo": emp["cargo"], "company_id": emp["company_id"]}


@router.get("/api/employee-portal/payslips/{employee_id}")
def employee_payslips(employee_id: int, token: str):
    """Lista holerites do empregado (autenticado pelo token)."""
    conn = get_conn()
    emp = conn.execute("SELECT id FROM employees WHERE id=? AND portal_token=?", (employee_id, token)).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(401, "Acesso negado.")
    rows = rows_to_dicts(conn.execute("""
        SELECT pr.competencia, pi.gross_salary, pi.inss, pi.irrf, pi.fgts,
               pi.vt_discount, pi.other_discounts, pi.net_salary, pi.id as item_id
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id = pi.run_id
        WHERE pi.employee_id=?
        ORDER BY pr.competencia DESC LIMIT 24
    """, (employee_id,)).fetchall())
    conn.close()
    return rows


@router.get("/api/employee-portal/vacation-balance/{employee_id}")
def employee_vacation_balance(employee_id: int, token: str):
    """Saldo de férias do empregado."""
    conn = get_conn()
    emp = conn.execute(
        "SELECT id, name, admission_date, cargo FROM employees WHERE id=? AND portal_token=?",
        (employee_id, token)
    ).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(401, "Acesso negado.")
    admission = emp["admission_date"] or date.today().isoformat()
    today = date.today()
    adm_date = date.fromisoformat(admission[:10])
    months_worked = (today.year - adm_date.year) * 12 + (today.month - adm_date.month)
    years_worked = months_worked // 12
    months_in_period = months_worked % 12
    days_accrued = round((30 / 12) * months_in_period, 1)
    conn.close()
    return {
        "employee_id": employee_id,
        "name": emp["name"],
        "admission_date": admission,
        "months_worked": months_worked,
        "years_worked": years_worked,
        "months_in_current_period": months_in_period,
        "days_accrued": days_accrued,
        "days_entitlement": 30,
        "message": f"{days_accrued} dias acumulados no período atual (de {months_in_period} meses)"
    }


@router.get("/api/employee-portal/profile/{employee_id}")
def employee_profile(employee_id: int, token: str):
    """Dados pessoais do empregado."""
    conn = get_conn()
    emp = conn.execute(
        "SELECT id, name, cpf, email, telefone, cargo, admission_date, salary, status FROM employees WHERE id=? AND portal_token=?",
        (employee_id, token)
    ).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(401, "Acesso negado.")
    result = dict(emp)
    # Mask CPF
    cpf = result.get("cpf", "")
    if cpf and len(cpf) == 11:
        result["cpf"] = f"***.***.{cpf[6:9]}-**"
    conn.close()
    return result
