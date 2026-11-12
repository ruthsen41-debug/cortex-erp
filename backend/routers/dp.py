"""
Módulo Departamento Pessoal — Folha de Pagamento, eSocial, Rescisão.
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
    from ..schemas.dp import EmployeeCreate, EmployeeUpdate, PayrollRunCreate, TerminationRequest
    from ..services.payroll_calculator import calculate_payroll, calc_thirteenth, calc_vacation, calc_termination
    from ..services.esocial_generator import gerar_s2200, gerar_s1200, gerar_s2299, gerar_s2230, gerar_s2210
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts
    from schemas.dp import EmployeeCreate, EmployeeUpdate, PayrollRunCreate, TerminationRequest
    from services.payroll_calculator import calculate_payroll, calc_thirteenth, calc_vacation, calc_termination
    from services.esocial_generator import gerar_s2200, gerar_s1200, gerar_s2299, gerar_s2230, gerar_s2210

router = APIRouter(prefix="/api/dp", tags=["Departamento Pessoal"])


# ─── FUNCIONÁRIOS ─────────────────────────────────────────────────────────────

@router.get("/employees")
def list_employees(
    active_only: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    where = "company_id = ?" + (" AND active = 1" if active_only else "")
    rows = rows_to_dicts(conn.execute(
        f"SELECT * FROM employees WHERE {where} ORDER BY name", (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.get("/employees/{emp_id}")
def get_employee(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return dict(row)


@router.post("/employees", status_code=201)
def create_employee(data: EmployeeCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    existing = conn.execute(
        "SELECT id FROM employees WHERE cpf = ? AND company_id = ?", (data.cpf, company_id)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="CPF já cadastrado.")

    matricula = data.matricula or f"MAT-{uuid.uuid4().hex[:6].upper()}"
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO employees (
            company_id, name, cpf, rg, pis_pasep, ctps, birth_date, sexo,
            admission_date, role, cbo, department, salary, is_prolabore,
            dependents, vt_monthly, esocial_category,
            bank_name, bank_agency, bank_account,
            email, phone, cep, address, matricula, notes, active
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
    """, (
        company_id, data.name, data.cpf, data.rg or "", data.pis_pasep or "",
        data.ctps or "", data.birth_date or "", data.sexo or "M",
        data.admission_date, data.role, data.cbo or "111105",
        data.department or "", data.salary, int(data.is_prolabore or False),
        data.dependents or 0, data.vt_monthly or 0.0, data.esocial_category or "101",
        data.bank_name or "", data.bank_agency or "", data.bank_account or "",
        data.email or "", data.phone or "", data.cep or "", data.address or "",
        matricula, data.notes or "",
    ))
    conn.commit()
    new_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM employees WHERE id = ?", (new_id,)).fetchone())
    conn.close()
    return row


@router.put("/employees/{emp_id}")
def update_employee(
    emp_id: int, data: EmployeeUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if not conn.execute(
        "SELECT 1 FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    fields, values = [], []
    for field, value in data.model_dump(exclude_none=True).items():
        if field == "active":
            value = int(value)
        fields.append(f"{field} = ?")
        values.append(value)
    if fields:
        values.append(emp_id)
        conn.execute(f"UPDATE employees SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()

    row = dict(conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone())
    conn.close()
    return row


@router.delete("/employees/{emp_id}")
def deactivate_employee(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if not conn.execute(
        "SELECT 1 FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    conn.execute("UPDATE employees SET active = 0 WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── SIMULAÇÃO RÁPIDA DE HOLERITE ────────────────────────────────────────────

@router.get("/employees/{emp_id}/holerite-preview")
def holerite_preview(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Simula o holerite do funcionário com base no salário cadastrado."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    conn.close()
    if not emp:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    emp = dict(emp)
    result = calculate_payroll(
        gross_salary=float(emp["salary"]),
        dependents=int(emp.get("dependents") or 0),
        vt_monthly=float(emp.get("vt_monthly") or 0.0),
        is_prolabore=bool(emp.get("is_prolabore")),
    )
    return {"employee": emp, "holerite": result.as_dict()}


# ─── FOLHA DE PAGAMENTO ───────────────────────────────────────────────────────

@router.post("/payroll/run", status_code=201)
def process_payroll(data: PayrollRunCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Processa a folha de pagamento da competência informada para todos os ativos."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    existing = conn.execute(
        "SELECT id FROM payroll_runs WHERE competence = ? AND company_id = ? AND status != 'cancelado'",
        (data.competence, company_id)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Folha da competência {data.competence} já foi processada (id={existing['id']})."
        )

    employees = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id = ? AND active = 1", (company_id,)
    ).fetchall())

    if not employees:
        conn.close()
        raise HTTPException(status_code=400, detail="Nenhum funcionário ativo encontrado.")

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO payroll_runs (company_id, competence, status, employee_count)
        VALUES (?, ?, 'processado', ?)
    """, (company_id, data.competence, len(employees)))
    run_id = cur.lastrowid

    total_gross = total_disc = total_net = total_fgts = 0.0

    for emp in employees:
        pr = calculate_payroll(
            gross_salary=float(emp["salary"]),
            dependents=int(emp.get("dependents") or 0),
            vt_monthly=float(emp.get("vt_monthly") or 0.0),
            is_prolabore=bool(emp.get("is_prolabore")),
        )
        d = pr.as_dict()
        total_disc_emp = d["inss"] + d["irrf"] + d["vt_discount"] + d["other_discounts"]
        cur.execute("""
            INSERT INTO payroll_items (
                run_id, employee_id, gross_salary, inss, irrf, fgts,
                vt_discount, other_discounts, net_salary
            ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            run_id, emp["id"],
            d["gross_salary"], d["inss"], d["irrf"], d["fgts"],
            d["vt_discount"], d["other_discounts"], d["net_salary"],
        ))
        total_gross += d["gross_salary"]
        total_disc  += total_disc_emp
        total_net   += d["net_salary"]
        total_fgts  += d["fgts"]

    cur.execute("""
        UPDATE payroll_runs
        SET total_gross=?, total_discounts=?, total_net=?, total_fgts=?
        WHERE id=?
    """, (round(total_gross, 2), round(total_disc, 2),
          round(total_net, 2), round(total_fgts, 2), run_id))
    conn.commit()

    # Busca resultado completo
    run = dict(conn.execute("SELECT * FROM payroll_runs WHERE id = ?", (run_id,)).fetchone())
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name as employee_name, e.role, e.matricula
        FROM payroll_items pi
        JOIN employees e ON e.id = pi.employee_id
        WHERE pi.run_id = ?
        ORDER BY e.name
    """, (run_id,)).fetchall())
    conn.close()
    return {"run": run, "items": items}


@router.get("/payroll")
def list_payroll_runs(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id = ? ORDER BY competence DESC", (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.get("/payroll/{run_id}")
def get_payroll_run(run_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE id = ? AND company_id = ?", (run_id, company_id)
    ).fetchone()
    if not run:
        conn.close()
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name as employee_name, e.role, e.cpf, e.matricula, e.pis_pasep
        FROM payroll_items pi
        JOIN employees e ON e.id = pi.employee_id
        WHERE pi.run_id = ?
        ORDER BY e.name
    """, (run_id,)).fetchall())
    conn.close()
    return {"run": dict(run), "items": items}


# ─── CÁLCULOS ESPECIAIS ───────────────────────────────────────────────────────

@router.get("/employees/{emp_id}/thirteenth")
def thirteenth_salary(
    emp_id: int,
    months_worked: int = Query(default=12, ge=1, le=12),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    conn.close()
    if not emp:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    emp = dict(emp)
    result = calc_thirteenth(float(emp["salary"]), months_worked)
    return {"employee_name": emp["name"], "salary": emp["salary"], **result}


@router.get("/employees/{emp_id}/vacation")
def vacation_calculation(
    emp_id: int,
    days: int = Query(default=30, ge=1, le=30),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    conn.close()
    if not emp:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    emp = dict(emp)
    result = calc_vacation(float(emp["salary"]), days, int(emp.get("dependents") or 0))
    return {"employee_name": emp["name"], "salary": emp["salary"], **result}


@router.post("/employees/{emp_id}/termination")
def termination_calculation(
    emp_id: int,
    data: TerminationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    emp = dict(emp)
    result = calc_termination(
        float(emp["salary"]),
        emp["admission_date"],
        data.termination_date,
        data.termination_type,
    )
    return {"employee_name": emp["name"], "salary": emp["salary"], **result}


# ─── eSocial ──────────────────────────────────────────────────────────────────

@router.get("/employees/{emp_id}/esocial/s2200")
def esocial_s2200(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera o XML do evento S-2200 (Admissão) para download."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    company = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    if not emp:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    xml = gerar_s2200(dict(company), dict(emp))
    filename = f"S2200_{dict(emp)['cpf'].replace('.','').replace('-','')}_{date.today().strftime('%Y%m%d')}.xml"
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/payroll/{run_id}/employee/{emp_id}/esocial/s1200")
def esocial_s1200(run_id: int, emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera o XML do evento S-1200 (Remuneração Mensal) para um funcionário na folha."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE id = ? AND company_id = ?", (run_id, company_id)
    ).fetchone()
    item = conn.execute(
        "SELECT * FROM payroll_items WHERE run_id = ? AND employee_id = ?", (run_id, emp_id)
    ).fetchone()
    emp = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
    company = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    if not run or not item or not emp:
        raise HTTPException(status_code=404, detail="Dados não encontrados.")
    xml = gerar_s1200(dict(company), dict(emp), dict(run)["competence"], dict(item))
    filename = f"S1200_{dict(emp)['cpf'].replace('.','').replace('-','')}_{dict(run)['competence'].replace('-','')}.xml"
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/employees/{emp_id}/esocial/s2299")
def esocial_s2299(
    emp_id: int, data: TerminationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Gera o XML do evento S-2299 (Desligamento)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    company = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    if not emp:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    xml = gerar_s2299(dict(company), dict(emp), data.termination_date, data.motivo_esocial or "03")
    filename = f"S2299_{dict(emp)['cpf'].replace('.','').replace('-','')}_{data.termination_date.replace('-','')}.xml"
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ─── AFASTAMENTOS ─────────────────────────────────────────────────────────────

@router.get("/afastamentos")
def list_afastamentos(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        """SELECT a.*, e.name as employee_name
           FROM employee_absences a
           JOIN employees e ON e.id = a.employee_id
           WHERE a.company_id = ?
           ORDER BY a.data_inicio DESC""",
        (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/afastamentos", status_code=201)
def create_afastamento(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    tipo = data.get("tipo", "outros")
    data_inicio = data.get("data_inicio", "")
    data_fim = data.get("data_fim", "")
    dias_empresa = data.get("dias_empresa", 0)
    dias_inss = data.get("dias_inss", 0)
    if data_inicio and data_fim:
        from datetime import date as _d2
        try:
            d1 = _d2.fromisoformat(data_inicio)
            d2 = _d2.fromisoformat(data_fim)
            total = max(0, (d2 - d1).days + 1)
            if tipo in ("auxilio_doenca_b31", "auxilio_doenca_b91", "acidente_trabalho"):
                dias_empresa = min(total, 15)
                dias_inss = max(0, total - 15)
            else:
                dias_empresa = total
                dias_inss = 0
        except Exception:
            pass
    cur = conn.execute(
        """INSERT INTO employee_absences
           (company_id, employee_id, tipo, cid, data_inicio, data_fim,
            dias_empresa, dias_inss, observacoes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (company_id, data["employee_id"], tipo,
         data.get("cid", ""), data_inicio, data_fim,
         dias_empresa, dias_inss, data.get("observacoes", ""))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/afastamentos/{afastamento_id}")
def update_afastamento(afastamento_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute(
        "SELECT id FROM employee_absences WHERE id = ? AND company_id = ?", (afastamento_id, company_id)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Afastamento não encontrado.")
    conn.execute(
        """UPDATE employee_absences SET tipo=?, cid=?, data_inicio=?, data_fim=?,
           dias_empresa=?, dias_inss=?, observacoes=? WHERE id=?""",
        (data.get("tipo"), data.get("cid", ""), data.get("data_inicio"), data.get("data_fim"),
         data.get("dias_empresa", 0), data.get("dias_inss", 0), data.get("observacoes", ""),
         afastamento_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/afastamentos/{afastamento_id}")
def delete_afastamento(afastamento_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        "DELETE FROM employee_absences WHERE id = ? AND company_id = ?", (afastamento_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/afastamentos/{afastamento_id}/retorno")
def registrar_retorno(afastamento_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        "UPDATE employee_absences SET retorno_efetivo=? WHERE id=? AND company_id=?",
        (data.get("retorno_efetivo", ""), afastamento_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/afastamentos/{afastamento_id}/esocial/s2230")
def esocial_s2230(afastamento_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    af = conn.execute(
        "SELECT * FROM employee_absences WHERE id=? AND company_id=?", (afastamento_id, company_id)
    ).fetchone()
    if not af:
        conn.close()
        raise HTTPException(status_code=404, detail="Afastamento não encontrado.")
    af = dict(af)
    emp = conn.execute("SELECT * FROM employees WHERE id=?", (af["employee_id"],)).fetchone()
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    xml = gerar_s2230(dict(company), dict(emp), af)
    cpf = dict(emp).get("cpf", "").replace(".", "").replace("-", "")
    filename = f"S2230_{cpf}_{af['data_inicio'].replace('-','')}.xml"
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ─── ATESTADOS ────────────────────────────────────────────────────────────────

@router.get("/atestados")
def list_atestados(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        """SELECT a.*, e.name as employee_name
           FROM medical_certificates a
           JOIN employees e ON e.id = a.employee_id
           WHERE a.company_id = ?
           ORDER BY a.data_apresentacao DESC, a.created_at DESC""",
        (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/atestados", status_code=201)
def create_atestado(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute(
        """INSERT INTO medical_certificates
           (company_id, employee_id, data_emissao, data_apresentacao, dias_afastamento,
            horas_afastamento, cid, crm_medico, nome_medico, hipotese_diagnostica,
            justifica_falta, afastamento_id, observacoes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (company_id, data["employee_id"], data.get("data_emissao", ""),
         data.get("data_apresentacao", ""), data.get("dias_afastamento", 0),
         data.get("horas_afastamento", 0), data.get("cid", ""),
         data.get("crm_medico", ""), data.get("nome_medico", ""),
         data.get("hipotese_diagnostica", ""), 1 if data.get("justifica_falta", True) else 0,
         data.get("afastamento_id"), data.get("observacoes", ""))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/atestados/{atestado_id}")
def update_atestado(atestado_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        """UPDATE medical_certificates SET data_emissao=?, data_apresentacao=?,
           dias_afastamento=?, horas_afastamento=?, cid=?, crm_medico=?, nome_medico=?,
           hipotese_diagnostica=?, justifica_falta=?, afastamento_id=?, observacoes=?
           WHERE id=? AND company_id=?""",
        (data.get("data_emissao"), data.get("data_apresentacao"),
         data.get("dias_afastamento", 0), data.get("horas_afastamento", 0),
         data.get("cid", ""), data.get("crm_medico", ""), data.get("nome_medico", ""),
         data.get("hipotese_diagnostica", ""), 1 if data.get("justifica_falta", True) else 0,
         data.get("afastamento_id"), data.get("observacoes", ""),
         atestado_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/atestados/{atestado_id}")
def delete_atestado(atestado_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        "DELETE FROM medical_certificates WHERE id=? AND company_id=?", (atestado_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── CAT ──────────────────────────────────────────────────────────────────────

@router.get("/cat")
def list_cat(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        """SELECT a.*, e.name as employee_name
           FROM work_accidents a
           JOIN employees e ON e.id = a.employee_id
           WHERE a.company_id = ?
           ORDER BY a.data_acidente DESC""",
        (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/cat", status_code=201)
def create_cat(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute(
        """INSERT INTO work_accidents
           (company_id, employee_id, data_acidente, hora_acidente, local_acidente,
            tipo_acidente, parte_corpo, agente_causador, descricao, houve_afastamento,
            dias_afastamento, houve_obito, cat_numero, observacoes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (company_id, data["employee_id"], data.get("data_acidente", ""),
         data.get("hora_acidente", ""), data.get("local_acidente", ""),
         data.get("tipo_acidente", "tipico"), data.get("parte_corpo", ""),
         data.get("agente_causador", ""), data.get("descricao", ""),
         1 if data.get("houve_afastamento") else 0,
         data.get("dias_afastamento", 0), 1 if data.get("houve_obito") else 0,
         data.get("cat_numero", ""), data.get("observacoes", ""))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/cat/{cat_id}")
def update_cat(cat_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        """UPDATE work_accidents SET data_acidente=?, hora_acidente=?, local_acidente=?,
           tipo_acidente=?, parte_corpo=?, agente_causador=?, descricao=?,
           houve_afastamento=?, dias_afastamento=?, houve_obito=?, cat_numero=?, observacoes=?
           WHERE id=? AND company_id=?""",
        (data.get("data_acidente"), data.get("hora_acidente", ""),
         data.get("local_acidente", ""), data.get("tipo_acidente", "tipico"),
         data.get("parte_corpo", ""), data.get("agente_causador", ""),
         data.get("descricao", ""), 1 if data.get("houve_afastamento") else 0,
         data.get("dias_afastamento", 0), 1 if data.get("houve_obito") else 0,
         data.get("cat_numero", ""), data.get("observacoes", ""),
         cat_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/cat/{cat_id}")
def delete_cat(cat_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        "DELETE FROM work_accidents WHERE id=? AND company_id=?", (cat_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/cat/{cat_id}/esocial/s2210")
def esocial_s2210(cat_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    ac = conn.execute(
        "SELECT * FROM work_accidents WHERE id=? AND company_id=?", (cat_id, company_id)
    ).fetchone()
    if not ac:
        conn.close()
        raise HTTPException(status_code=404, detail="CAT não encontrada.")
    ac = dict(ac)
    emp = conn.execute("SELECT * FROM employees WHERE id=?", (ac["employee_id"],)).fetchone()
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    xml = gerar_s2210(dict(company), dict(emp), ac)
    cpf = dict(emp).get("cpf", "").replace(".", "").replace("-", "")
    filename = f"S2210_{cpf}_{ac['data_acidente'].replace('-','')}.xml"
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ─── CARGOS (PLANO DE CARGOS) ─────────────────────────────────────────────────

@router.get("/job-positions")
def list_job_positions(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM job_positions WHERE company_id = ? ORDER BY nome", (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/job-positions", status_code=201)
def create_job_position(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute(
        """INSERT INTO job_positions (company_id, nome, cbo, nivel, salario_base, salario_maximo, descricao, ativo)
           VALUES (?,?,?,?,?,?,?,1)""",
        (company_id, data["nome"], data.get("cbo", ""), data.get("nivel", ""),
         data.get("salario_base", 0), data.get("salario_maximo", 0), data.get("descricao", ""))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/job-positions/{pos_id}")
def update_job_position(pos_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        """UPDATE job_positions SET nome=?, cbo=?, nivel=?, salario_base=?, salario_maximo=?, descricao=?, ativo=?
           WHERE id=? AND company_id=?""",
        (data.get("nome"), data.get("cbo", ""), data.get("nivel", ""),
         data.get("salario_base", 0), data.get("salario_maximo", 0), data.get("descricao", ""),
         1 if data.get("ativo", True) else 0, pos_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/job-positions/{pos_id}")
def delete_job_position(pos_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM job_positions WHERE id=? AND company_id=?", (pos_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── DEPARTAMENTOS ────────────────────────────────────────────────────────────

@router.get("/departments")
def list_departments(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        """SELECT d.*, e.name as responsavel_nome
           FROM departments d
           LEFT JOIN employees e ON e.id = d.responsavel_id
           WHERE d.company_id = ? ORDER BY d.nome""", (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/departments", status_code=201)
def create_department(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute(
        "INSERT INTO departments (company_id, nome, codigo, responsavel_id) VALUES (?,?,?,?)",
        (company_id, data["nome"], data.get("codigo", ""), data.get("responsavel_id"))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/departments/{dept_id}")
def update_department(dept_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        "UPDATE departments SET nome=?, codigo=?, responsavel_id=? WHERE id=? AND company_id=?",
        (data.get("nome"), data.get("codigo", ""), data.get("responsavel_id"), dept_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/departments/{dept_id}")
def delete_department(dept_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM departments WHERE id=? AND company_id=?", (dept_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── HISTÓRICO SALARIAL ───────────────────────────────────────────────────────

@router.get("/employees/{emp_id}/salary-history")
def get_salary_history(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM salary_history WHERE employee_id=? AND company_id=? ORDER BY data_vigencia DESC",
        (emp_id, company_id)
    ).fetchall())
    conn.close()
    return rows


@router.post("/employees/{emp_id}/salary-history", status_code=201)
def create_salary_history(emp_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT salary, role FROM employees WHERE id=? AND company_id=?", (emp_id, company_id)
    ).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    sal_ant = float(emp["salary"] or 0)
    sal_novo = float(data["salario_novo"])
    pct = round((sal_novo - sal_ant) / sal_ant * 100, 2) if sal_ant else 0
    cur = conn.execute(
        """INSERT INTO salary_history
           (company_id, employee_id, data_vigencia, salario_anterior, salario_novo, tipo, percentual, motivo, cargo_anterior, cargo_novo, aprovado_por)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (company_id, emp_id, data["data_vigencia"], sal_ant, sal_novo,
         data.get("tipo", "reajuste"), pct, data.get("motivo", ""),
         emp["role"] or "", data.get("cargo_novo", ""), data.get("aprovado_por", ""))
    )
    conn.execute("UPDATE employees SET salary=? WHERE id=?", (sal_novo, emp_id))
    if data.get("cargo_novo"):
        conn.execute("UPDATE employees SET role=? WHERE id=?", (data["cargo_novo"], emp_id))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "percentual": pct}


# ─── HORÁRIOS DE TRABALHO ─────────────────────────────────────────────────────

@router.get("/work-schedules")
def list_work_schedules(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM work_schedules WHERE company_id=? ORDER BY nome", (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/work-schedules", status_code=201)
def create_work_schedule(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute(
        """INSERT INTO work_schedules
           (company_id, nome, tipo, hora_entrada, hora_saida, hora_entrada_tarde, hora_saida_tarde,
            intervalo_min, horas_diarias, horas_semanais, dias_trabalho)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (company_id, data["nome"], data.get("tipo", "fixo"),
         data.get("hora_entrada", "08:00"), data.get("hora_saida", "17:00"),
         data.get("hora_entrada_tarde", ""), data.get("hora_saida_tarde", ""),
         data.get("intervalo_min", 60), data.get("horas_diarias", 8.0),
         data.get("horas_semanais", 44.0), data.get("dias_trabalho", "1,2,3,4,5"))
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/work-schedules/{sched_id}")
def update_work_schedule(sched_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute(
        """UPDATE work_schedules SET nome=?, tipo=?, hora_entrada=?, hora_saida=?,
           hora_entrada_tarde=?, hora_saida_tarde=?, intervalo_min=?,
           horas_diarias=?, horas_semanais=?, dias_trabalho=?
           WHERE id=? AND company_id=?""",
        (data.get("nome"), data.get("tipo", "fixo"),
         data.get("hora_entrada", "08:00"), data.get("hora_saida", "17:00"),
         data.get("hora_entrada_tarde", ""), data.get("hora_saida_tarde", ""),
         data.get("intervalo_min", 60), data.get("horas_diarias", 8.0),
         data.get("horas_semanais", 44.0), data.get("dias_trabalho", "1,2,3,4,5"),
         sched_id, company_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/work-schedules/{sched_id}")
def delete_work_schedule(sched_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM work_schedules WHERE id=? AND company_id=?", (sched_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── PONTO ELETRÔNICO ─────────────────────────────────────────────────────────

def _calc_horas(entrada, saida_almoco, retorno_almoco, saida):
    fmt = "%H:%M"
    try:
        t_in = datetime.strptime(entrada, fmt)
        t_out = datetime.strptime(saida, fmt)
        total = (t_out - t_in).seconds / 3600
        if saida_almoco and retorno_almoco:
            t_sa = datetime.strptime(saida_almoco, fmt)
            t_ra = datetime.strptime(retorno_almoco, fmt)
            total -= (t_ra - t_sa).seconds / 3600
        return round(max(0, total), 2)
    except Exception:
        return 0.0


@router.get("/ponto")
def list_ponto(
    employee_id: Optional[int] = Query(None),
    mes: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = """SELECT t.*, e.name as employee_name
             FROM time_records t JOIN employees e ON e.id = t.employee_id
             WHERE t.company_id = ?"""
    params: list = [company_id]
    if employee_id:
        sql += " AND t.employee_id = ?"
        params.append(employee_id)
    if mes:
        sql += " AND t.data LIKE ?"
        params.append(f"{mes}%")
    sql += " ORDER BY t.data DESC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows


@router.post("/ponto", status_code=201)
def upsert_ponto(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp_id = data["employee_id"]
    dt = data["data"]
    entrada = data.get("entrada", "")
    saida_alm = data.get("saida_almoco", "")
    ret_alm = data.get("retorno_almoco", "")
    saida = data.get("saida", "")
    ocorrencia = data.get("tipo_ocorrencia", "normal")

    horas_trab = 0.0
    horas_extras = 0.0
    horas_falt = 0.0
    if entrada and saida:
        horas_trab = _calc_horas(entrada, saida_alm, ret_alm, saida)
        sched = conn.execute(
            "SELECT horas_diarias FROM work_schedules WHERE company_id=? LIMIT 1", (company_id,)
        ).fetchone()
        horas_dia = float(sched["horas_diarias"]) if sched else 8.0
        horas_extras = round(max(0, horas_trab - horas_dia), 2)
        if ocorrencia not in ("falta_justificada", "falta_injustificada", "feriado", "folga", "afastamento"):
            horas_falt = round(max(0, horas_dia - horas_trab), 2)

    existing = conn.execute(
        "SELECT id FROM time_records WHERE employee_id=? AND data=? AND company_id=?",
        (emp_id, dt, company_id)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE time_records SET entrada=?, saida_almoco=?, retorno_almoco=?, saida=?,
               horas_trabalhadas=?, horas_extras=?, horas_faltantes=?, tipo_ocorrencia=?, justificativa=?
               WHERE id=?""",
            (entrada, saida_alm, ret_alm, saida, horas_trab, horas_extras, horas_falt,
             ocorrencia, data.get("justificativa", ""), existing["id"])
        )
        rec_id = existing["id"]
    else:
        cur = conn.execute(
            """INSERT INTO time_records
               (company_id, employee_id, data, entrada, saida_almoco, retorno_almoco, saida,
                horas_trabalhadas, horas_extras, horas_faltantes, tipo_ocorrencia, justificativa)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (company_id, emp_id, dt, entrada, saida_alm, ret_alm, saida,
             horas_trab, horas_extras, horas_falt, ocorrencia, data.get("justificativa", ""))
        )
        rec_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": rec_id, "horas_trabalhadas": horas_trab, "horas_extras": horas_extras}


@router.delete("/ponto/{rec_id}")
def delete_ponto(rec_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM time_records WHERE id=? AND company_id=?", (rec_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/ponto/espelho/{employee_id}/{mes}")
def espelho_ponto(employee_id: int, mes: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM time_records WHERE employee_id=? AND data LIKE ? AND company_id=? ORDER BY data",
        (employee_id, f"{mes}%", company_id)
    ).fetchall())
    emp = conn.execute("SELECT name FROM employees WHERE id=?", (employee_id,)).fetchone()
    saldo_hb = conn.execute(
        "SELECT COALESCE(SUM(horas),0) as saldo FROM hour_bank WHERE employee_id=? AND company_id=?",
        (employee_id, company_id)
    ).fetchone()
    conn.close()
    total_trab = round(sum(r.get("horas_trabalhadas", 0) for r in rows), 2)
    total_extras = round(sum(r.get("horas_extras", 0) for r in rows), 2)
    total_faltas = len([r for r in rows if r.get("tipo_ocorrencia") in ("falta_justificada", "falta_injustificada")])
    return {
        "employee_id": employee_id,
        "employee_name": dict(emp)["name"] if emp else "",
        "mes": mes,
        "registros": rows,
        "total_horas_trabalhadas": total_trab,
        "total_horas_extras": total_extras,
        "total_faltas": total_faltas,
        "saldo_banco": round(float(dict(saldo_hb)["saldo"]), 2) if saldo_hb else 0.0,
    }


# ─── BANCO DE HORAS ───────────────────────────────────────────────────────────

@router.get("/banco-horas")
def get_banco_horas(employee_id: int = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM hour_bank WHERE employee_id=? AND company_id=? ORDER BY data DESC",
        (employee_id, company_id)
    ).fetchall())
    saldo = round(sum(r["horas"] for r in rows), 2)
    conn.close()
    return {"saldo": saldo, "historico": rows}


@router.post("/banco-horas/compensar", status_code=201)
def compensar_banco_horas(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp_id = data["employee_id"]
    horas_comp = abs(float(data["horas"]))
    saldo_row = conn.execute(
        "SELECT COALESCE(SUM(horas),0) as s FROM hour_bank WHERE employee_id=? AND company_id=?",
        (emp_id, company_id)
    ).fetchone()
    saldo_atual = float(dict(saldo_row)["s"])
    novo_saldo = round(saldo_atual - horas_comp, 2)
    conn.execute(
        """INSERT INTO hour_bank (company_id, employee_id, data, tipo, horas, saldo_acumulado, observacao)
           VALUES (?,?,?,?,?,?,?)""",
        (company_id, emp_id, data.get("data", str(date.today())),
         "compensacao", -horas_comp, novo_saldo, data.get("observacao", ""))
    )
    conn.commit()
    conn.close()
    return {"ok": True, "saldo_novo": novo_saldo}


# ─── OBRIGAÇÕES ACESSÓRIAS ────────────────────────────────────────────────────

def _next_business_day_last(year: int, month: int) -> str:
    """Último dia útil do mês."""
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    while last.weekday() >= 5:
        last -= timedelta(days=1)
    return str(last)


@router.get("/rais/{ano}")
def gerar_rais(ano: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    emp_rows = rows_to_dicts(conn.execute(
        """SELECT * FROM employees WHERE company_id=?
           AND (active=1 OR (admission_date LIKE ? AND active=0))""",
        (company_id, f"{ano}%")
    ).fetchall())
    trabalhadores = []
    total_rem = 0.0
    for emp in emp_rows:
        total_bruto = conn.execute(
            """SELECT COALESCE(SUM(pi.gross_salary),0) as total
               FROM payroll_items pi
               JOIN payroll_runs pr ON pr.id = pi.run_id
               WHERE pi.employee_id=? AND pr.competence LIKE ? AND pr.company_id=?""",
            (emp["id"], f"{ano}%", company_id)
        ).fetchone()
        t_bruto = float(dict(total_bruto)["total"])
        meses = conn.execute(
            """SELECT COUNT(*) as cnt FROM payroll_items pi
               JOIN payroll_runs pr ON pr.id = pi.run_id
               WHERE pi.employee_id=? AND pr.competence LIKE ? AND pr.company_id=?""",
            (emp["id"], f"{ano}%", company_id)
        ).fetchone()
        trabalhadores.append({
            "cpf": emp.get("cpf", ""),
            "pis_pasep": emp.get("pis_pasep", ""),
            "nome": emp.get("name", ""),
            "data_admissao": emp.get("admission_date", ""),
            "data_demissao": emp.get("termination_date", "") if not emp.get("active") else "",
            "cargo": emp.get("role", ""),
            "cbo": emp.get("cbo", ""),
            "salario_base": float(emp.get("salary", 0)),
            "meses_trabalhados": int(dict(meses)["cnt"]),
            "total_remuneracao_ano": t_bruto,
            "tipo_vinculo": "31" if emp.get("is_prolabore") else "10",
        })
        total_rem += t_bruto
    conn.close()
    return {
        "ano": ano,
        "empresa": dict(company) if company else {},
        "trabalhadores": trabalhadores,
        "totais": {"total_trabalhadores": len(trabalhadores), "total_remuneracao": round(total_rem, 2)},
    }


@router.get("/caged/{competencia}")
def gerar_caged(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    admissoes = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id=? AND admission_date LIKE ?",
        (company_id, f"{competencia}%")
    ).fetchall())
    demissoes = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id=? AND active=0 AND notes LIKE ?",
        (company_id, f"%{competencia}%")
    ).fetchall())
    conn.close()
    return {
        "competencia": competencia,
        "admissoes": [{"cpf": e["cpf"], "nome": e["name"], "data_admissao": e["admission_date"],
                       "cargo": e["role"], "cbo": e["cbo"], "salario": e["salary"], "tipo_admissao": "1"}
                      for e in admissoes],
        "demissoes": [{"cpf": e["cpf"], "nome": e["name"], "data_demissao": e.get("termination_date", ""),
                       "cargo": e["role"], "cbo": e["cbo"], "salario": e["salary"], "motivo_desligamento": "11"}
                      for e in demissoes],
        "saldo": len(admissoes) - len(demissoes),
    }


@router.get("/dirf/{ano}")
def gerar_dirf(ano: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = conn.execute("SELECT cnpj, razao_social FROM companies WHERE id=?", (company_id,)).fetchone()
    items = rows_to_dicts(conn.execute(
        """SELECT pi.employee_id, e.cpf, e.name, e.dependents,
                  SUM(pi.gross_salary) as total_bruto,
                  SUM(pi.irrf) as total_irrf,
                  SUM(pi.inss) as total_inss
           FROM payroll_items pi
           JOIN payroll_runs pr ON pr.id = pi.run_id
           JOIN employees e ON e.id = pi.employee_id
           WHERE pr.company_id=? AND pr.competence LIKE ?
           GROUP BY pi.employee_id""",
        (company_id, f"{ano}%")
    ).fetchall())
    conn.close()
    return {
        "ano": ano,
        "empresa": dict(company) if company else {},
        "beneficiarios": [{"cpf": r["cpf"], "nome": r["name"],
                           "rendimentos_tributaveis": round(float(r["total_bruto"] or 0), 2),
                           "irrf_retido": round(float(r["total_irrf"] or 0), 2),
                           "deducoes_inss": round(float(r["total_inss"] or 0), 2),
                           "dependentes": int(r["dependents"] or 0)} for r in items],
    }


@router.get("/gps/{competencia}")
def calcular_gps(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute(
        """SELECT SUM(pi.gross_salary) as total_folha, SUM(pi.inss) as inss_func
           FROM payroll_items pi
           JOIN payroll_runs pr ON pr.id = pi.run_id
           WHERE pr.company_id=? AND pr.competence=?""",
        (company_id, competencia)
    ).fetchone()
    conn.close()
    if not row or not dict(row)["total_folha"]:
        raise HTTPException(status_code=404, detail=f"Nenhuma folha processada para {competencia}.")
    total_folha = round(float(dict(row)["total_folha"]), 2)
    inss_func = round(float(dict(row)["inss_func"] or 0), 2)
    patronal = round(total_folha * 0.20, 2)
    rat = round(total_folha * 0.03, 2)
    terceiros = round(total_folha * 0.058, 2)
    total_gps = round(inss_func + patronal + rat + terceiros, 2)
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    next_m = mes + 1 if mes < 12 else 1
    next_y = ano if mes < 12 else ano + 1
    return {
        "competencia": competencia,
        "total_folha": total_folha,
        "inss_funcionarios": inss_func,
        "inss_patronal_20pct": patronal,
        "rat_ajustado": rat,
        "terceiros": terceiros,
        "total_gps": total_gps,
        "codigo_pagamento": "2100",
        "vencimento": _next_business_day_last(next_y, next_m),
    }


@router.get("/darf/{competencia}")
def calcular_darf(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute(
        """SELECT SUM(pi.irrf) as total_irrf
           FROM payroll_items pi
           JOIN payroll_runs pr ON pr.id = pi.run_id
           WHERE pr.company_id=? AND pr.competence=?""",
        (company_id, competencia)
    ).fetchone()
    conn.close()
    total_irrf = round(float(dict(row)["total_irrf"] or 0), 2) if row else 0.0
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    next_m = mes + 1 if mes < 12 else 1
    next_y = ano if mes < 12 else ano + 1
    return {
        "competencia": competencia,
        "total_irrf": total_irrf,
        "codigo_receita": "0561",
        "periodo_apuracao": competencia,
        "vencimento": _next_business_day_last(next_y, next_m),
    }
