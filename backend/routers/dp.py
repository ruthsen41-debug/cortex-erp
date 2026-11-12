"""
Módulo Departamento Pessoal — Folha de Pagamento, eSocial, Rescisão.
"""
import uuid
from datetime import date
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
