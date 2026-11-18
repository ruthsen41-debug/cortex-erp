"""
Módulo Departamento Pessoal — Folha de Pagamento, eSocial, Rescisão.
"""
import json as _json
import re as _re
import unicodedata as _unicodedata
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
import calendar as _calendar
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.dp import EmployeeCreate, EmployeeUpdate, EmployeeFicha, EmployeeDependent, PayrollRunCreate, TerminationRequest
    from ..services.payroll_calculator import calculate_payroll, calc_thirteenth, calc_vacation, calc_termination
    from ..services.esocial_generator import (gerar_s2200, gerar_s1200, gerar_s2299, gerar_s2230, gerar_s2210,
        gerar_s1000, gerar_s1005, gerar_s1020, gerar_s1050, gerar_s1070, gerar_s3000, gerar_s5001, gerar_s5011,
        gerar_s2298, _build_det_verbas)
    from ..services import payroll_engine, payroll_special, payroll_complementar, escalas, dp_parametros
    from ..services.payroll_tables import default_seed, load_tables
    from ..services.formula_engine import FormulaError, FUNCOES as FORMULA_FUNCOES
    from ..services.ficha_registro import gerar_ficha_registro_html
    from ..services.folha_impressao import gerar_folha_html, gerar_recibos_html
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.dp import EmployeeCreate, EmployeeUpdate, EmployeeFicha, EmployeeDependent, PayrollRunCreate, TerminationRequest
    from services.payroll_calculator import calculate_payroll, calc_thirteenth, calc_vacation, calc_termination
    from services.esocial_generator import (gerar_s2200, gerar_s1200, gerar_s2299, gerar_s2230, gerar_s2210,
        gerar_s1000, gerar_s1005, gerar_s1020, gerar_s1050, gerar_s1070, gerar_s3000, gerar_s5001, gerar_s5011,
        gerar_s2298, _build_det_verbas)
    from services import payroll_engine, payroll_special, payroll_complementar, escalas, dp_parametros
    from services.payroll_tables import default_seed, load_tables
    from services.formula_engine import FormulaError, FUNCOES as FORMULA_FUNCOES
    from services.ficha_registro import gerar_ficha_registro_html
    from services.folha_impressao import gerar_folha_html, gerar_recibos_html

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
    new_id = cur.lastrowid
    ficha = {k: v for k, v in data.model_dump(include=set(EmployeeFicha.model_fields)).items() if v is not None}
    if ficha:
        conn.execute(f"UPDATE employees SET {', '.join(f'{k} = ?' for k in ficha)} WHERE id = ?",
                     [*ficha.values(), new_id])
    conn.commit()
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

    payload = data.model_dump(exclude_none=True)
    if payload.get("cpf") and conn.execute(
        "SELECT 1 FROM employees WHERE cpf = ? AND company_id = ? AND id <> ?",
        (payload["cpf"], company_id, emp_id),
    ).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="CPF já cadastrado em outro funcionário.")

    fields, values = [], []
    for field, value in payload.items():
        if field in ("active", "is_prolabore"):
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


# ─── DEPENDENTES ──────────────────────────────────────────────────────────────

def _emp_da_empresa(conn, emp_id: int, company_id: int) -> None:
    if not conn.execute("SELECT 1 FROM employees WHERE id = ? AND company_id = ?",
                        (emp_id, company_id)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")


def _recontar_dependentes(conn, emp_id: int) -> None:
    """Mantém os contadores usados pelo motor de folha em sincronia com a lista de dependentes.
    Salário-família: filhos/enteados até 14 anos marcados (art. 66 da Lei 8.213/91)."""
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM employee_dependents WHERE employee_id = ?", (emp_id,)).fetchall())
    hoje = date.today()

    def menor_14(d):
        try:
            n = date.fromisoformat((d or "")[:10])
        except ValueError:
            return True
        return (hoje.year - n.year - ((hoje.month, hoje.day) < (n.month, n.day))) < 14

    irrf = sum(1 for r in rows if r.get("irrf"))
    sf = sum(1 for r in rows if r.get("salario_familia") and menor_14(r.get("data_nascimento")))
    conn.execute("UPDATE employees SET dependents = ?, filhos_sal_familia = ? WHERE id = ?", (irrf, sf, emp_id))


@router.get("/employees/{emp_id}/dependents")
def list_dependents(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _emp_da_empresa(conn, emp_id, company_id)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM employee_dependents WHERE employee_id = ? AND company_id = ? ORDER BY data_nascimento, nome",
        (emp_id, company_id)).fetchall())
    conn.close()
    return rows


@router.post("/employees/{emp_id}/dependents", status_code=201)
def add_dependent(emp_id: int, data: EmployeeDependent, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _emp_da_empresa(conn, emp_id, company_id)
    cur = conn.cursor()
    cur.execute("""INSERT INTO employee_dependents
        (company_id, employee_id, nome, cpf, data_nascimento, parentesco, sexo, irrf, salario_familia, plano_saude)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (company_id, emp_id, data.nome.strip(), data.cpf or "", data.data_nascimento or "",
         data.parentesco or "03", data.sexo or "", int(data.irrf or 0),
         int(data.salario_familia or 0), int(data.plano_saude or 0)))
    new_id = cur.lastrowid
    _recontar_dependentes(conn, emp_id)
    conn.commit()
    row = dict(conn.execute("SELECT * FROM employee_dependents WHERE id = ?", (new_id,)).fetchone())
    conn.close()
    return row


@router.put("/employees/{emp_id}/dependents/{dep_id}")
def update_dependent(emp_id: int, dep_id: int, data: EmployeeDependent,
                     current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _emp_da_empresa(conn, emp_id, company_id)
    cur = conn.execute("""UPDATE employee_dependents SET nome = ?, cpf = ?, data_nascimento = ?, parentesco = ?,
        sexo = ?, irrf = ?, salario_familia = ?, plano_saude = ? WHERE id = ? AND employee_id = ?""",
        (data.nome.strip(), data.cpf or "", data.data_nascimento or "", data.parentesco or "03",
         data.sexo or "", int(data.irrf or 0), int(data.salario_familia or 0), int(data.plano_saude or 0),
         dep_id, emp_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Dependente não encontrado.")
    _recontar_dependentes(conn, emp_id)
    conn.commit()
    row = dict(conn.execute("SELECT * FROM employee_dependents WHERE id = ?", (dep_id,)).fetchone())
    conn.close()
    return row


@router.delete("/employees/{emp_id}/dependents/{dep_id}")
def delete_dependent(emp_id: int, dep_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _emp_da_empresa(conn, emp_id, company_id)
    conn.execute("DELETE FROM employee_dependents WHERE id = ? AND employee_id = ?", (dep_id, emp_id))
    _recontar_dependentes(conn, emp_id)
    conn.commit()
    conn.close()
    return {"ok": True}


@router.put("/employees/{emp_id}/photo")
def update_employee_photo(
    emp_id: int,
    data: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Salva foto do funcionário em base64 (formato data:image/...)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if not conn.execute(
        "SELECT 1 FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    photo = data.get("photo") or None
    conn.execute("UPDATE employees SET photo = ? WHERE id = ? AND company_id = ?", (photo, emp_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/employees/{emp_id}")
def deactivate_employee(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if not conn.execute(
        "SELECT 1 FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    today = date.today().isoformat()
    conn.execute(
        "UPDATE employees SET active = 0, termination_date = ? WHERE id = ?",
        (today, emp_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── SIMULAÇÃO RÁPIDA DE HOLERITE ────────────────────────────────────────────

def _competencia_atual() -> str:
    return date.today().strftime("%Y-%m")


def _valida_competencia(comp: str) -> str:
    import re as _re
    if not _re.match(r"^\d{4}-(0[1-9]|1[0-2])$", comp or ""):
        raise HTTPException(status_code=422, detail="Competência inválida. Use o formato AAAA-MM.")
    return comp


def _holerite_compat(res: Dict[str, Any]) -> Dict[str, Any]:
    """Resultado do motor no formato antigo (gross_salary, inss...) + linhas por rubrica."""
    return {
        "gross_salary": res["total_proventos"],
        "inss": res["inss"],
        "irrf": res["irrf"],
        "fgts": res["fgts"],
        "vt_discount": res["vt_desconto"],
        "other_discounts": round(res["total_descontos"] - res["inss"] - res["irrf"] - res["vt_desconto"], 2),
        "net_salary": res["liquido"],
        "total_descontos": res["total_descontos"],
        "base_inss": res["base_inss"],
        "base_irrf": res["base_irrf"],
        "base_fgts": res["base_fgts"],
        "dias_pagos": res["dias_pagos"],
        "lines": res["lines"],
        "avisos": res["avisos"],
    }


@router.get("/employees/{emp_id}/holerite-preview")
def holerite_preview(
    emp_id: int,
    competencia: Optional[str] = Query(None, description="AAAA-MM (padrão: mês atual)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Simula o holerite pelo motor de rubricas (ponto, benefícios, pensão etc. da competência)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    emp = dict(emp)
    comp = _valida_competencia(competencia or _competencia_atual())
    calc = payroll_engine.run_payroll(conn, company_id, comp, employee_ids=[emp_id])
    conn.close()
    if not calc["results"]:
        raise HTTPException(status_code=400, detail="Funcionário inativo ou ainda não admitido nesta competência.")
    return {"employee": emp, "competencia": comp, "tabelas": calc["tabelas"],
            "holerite": _holerite_compat(calc["results"][0])}


# ─── FOLHA DE PAGAMENTO ───────────────────────────────────────────────────────

@router.post("/payroll/preview")
def preview_payroll(data: PayrollRunCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Calcula a folha da competência sem gravar (conferência antes de processar)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    calc = payroll_engine.run_payroll(conn, company_id, data.competence, data.pagar_horas_extras)
    conn.close()
    return calc


@router.post("/payroll/run", status_code=201)
def process_payroll(data: PayrollRunCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Processa a folha da competência pelo motor de rubricas e grava as linhas de cada holerite."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    existing = conn.execute(
        "SELECT id FROM payroll_runs WHERE competence = ? AND company_id = ? AND status != 'cancelado' "
        "AND COALESCE(tipo, 'mensal') = 'mensal'",
        (data.competence, company_id)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Folha da competência {data.competence} já foi processada (id={existing['id']}). "
                   f"Exclua-a para reprocessar."
        )

    try:
        payroll_engine.ensure_system_rubrics(conn, company_id)
        calc = payroll_engine.run_payroll(conn, company_id, data.competence, data.pagar_horas_extras)
        results = calc["results"]
        if not results:
            raise HTTPException(status_code=400, detail="Nenhum funcionário ativo encontrado.")

        run_id = _gravar_folha(conn, company_id, data.competence, calc)
        conn.commit()
    except HTTPException:
        conn.rollback()
        conn.close()
        raise
    except Exception:
        conn.rollback()
        conn.close()
        raise

    out = _load_payroll_run(conn, run_id, company_id)
    conn.close()
    out["tabelas"] = calc["tabelas"]
    out["avisos"] = [{"employee_name": r["employee_name"], "avisos": r["avisos"]}
                     for r in results if r["avisos"]]
    return out


def _gravar_folha(conn, company_id: int, competencia: str, calc: Dict[str, Any], tipo: str = "mensal",
                  parent_run_id: Optional[int] = None, descricao: str = "", info: str = "") -> int:
    """Grava a folha (mensal, complementar ou dissídio), os itens e as linhas de cada holerite."""
    results = calc["results"]
    tot = calc["totais"]
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO payroll_runs (company_id, competence, status, employee_count,
                                  total_gross, total_discounts, total_net, total_fgts,
                                  tipo, parent_run_id, descricao, info)
        VALUES (?, ?, 'processado', ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (company_id, competencia, len(results),
          tot["proventos"], tot["descontos"], tot["liquido"], tot["fgts"],
          tipo, parent_run_id, descricao, info))
    run_id = cur.lastrowid
    for res in results:
        h = _holerite_compat(res)
        cur.execute("""
            INSERT INTO payroll_items (
                run_id, employee_id, gross_salary, inss, irrf, fgts,
                vt_discount, other_discounts, net_salary,
                base_inss, base_irrf, base_fgts, avisos
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            run_id, res["employee_id"],
            h["gross_salary"], h["inss"], h["irrf"], h["fgts"],
            h["vt_discount"], h["other_discounts"], h["net_salary"],
            h["base_inss"], h["base_irrf"], h["base_fgts"], " | ".join(res["avisos"]),
        ))
        item_id = cur.lastrowid
        for ln in res["lines"]:
            cur.execute("""
                INSERT INTO payroll_item_lines
                    (run_id, item_id, employee_id, codigo, nome, tipo, referencia, valor, origem, per_ref)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (run_id, item_id, res["employee_id"], ln["codigo"], ln["nome"], ln["tipo"],
                  ln.get("referencia", ""), ln["valor"], ln.get("origem", "automatico"), ln.get("per_ref", "")))
    return run_id


def _load_payroll_run(conn, run_id: int, company_id: int) -> Optional[Dict[str, Any]]:
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE id = ? AND company_id = ?", (run_id, company_id)
    ).fetchone()
    if not run:
        return None
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name as employee_name, e.role, e.cpf, e.matricula, e.pis_pasep
        FROM payroll_items pi
        JOIN employees e ON e.id = pi.employee_id
        WHERE pi.run_id = ?
        ORDER BY e.name
    """, (run_id,)).fetchall())
    lines = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_item_lines WHERE run_id = ? ORDER BY item_id, tipo DESC, codigo, id",
        (run_id,)).fetchall())
    por_item: Dict[int, List[Dict[str, Any]]] = {}
    for ln in lines:
        por_item.setdefault(ln["item_id"], []).append(ln)
    for it in items:
        it["lines"] = por_item.get(it["id"], [])
    return {"run": dict(run), "items": items}


@router.get("/payroll")
def list_payroll_runs(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id = ? ORDER BY competence DESC", (company_id,)
    ).fetchall())
    conn.close()
    return rows


@router.get("/payroll/{run_id:int}")
def get_payroll_run(run_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    out = _load_payroll_run(conn, run_id, current_user.get("company_id", 1))
    conn.close()
    if not out:
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    return out


def _load_payroll_print(conn, run_id: int, company_id: int, employee_id: Optional[int] = None):
    """Folha + itens com os dados de cadastro que os impressos (holerite e folha) exibem."""
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE id = ? AND company_id = ?", (run_id, company_id)).fetchone()
    if not run:
        return None, None, []
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    sql = """
        SELECT pi.*, e.name AS employee_name, e.role, e.cpf, e.matricula, e.cbo, e.department,
               e.admission_date, e.salary, e.dependents
        FROM payroll_items pi JOIN employees e ON e.id = pi.employee_id
        WHERE pi.run_id = ?"""
    params: List[Any] = [run_id]
    if employee_id:
        sql += " AND pi.employee_id = ?"
        params.append(employee_id)
    items = rows_to_dicts(conn.execute(sql + " ORDER BY e.name", params).fetchall())
    lines = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_item_lines WHERE run_id = ? ORDER BY item_id, tipo DESC, codigo, id",
        (run_id,)).fetchall())
    por_item: Dict[int, List[Dict[str, Any]]] = {}
    for ln in lines:
        por_item.setdefault(ln["item_id"], []).append(ln)
    for it in items:
        it["lines"] = por_item.get(it["id"], [])
    return dict(run), company, items


@router.get("/payroll/{run_id:int}/recibos")
def imprimir_recibos(run_id: int, employee_id: Optional[int] = Query(default=None),
                     current_user: Dict[str, Any] = Depends(get_current_user)):
    """Recibo de pagamento de salário (holerite) em 2 vias; um funcionário ou a folha inteira."""
    conn = get_conn()
    run, company, items = _load_payroll_print(conn, run_id, current_user.get("company_id", 1), employee_id)
    conn.close()
    if not run:
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    if not items:
        raise HTTPException(status_code=404, detail="Nenhum holerite encontrado nesta folha.")
    conn = get_conn()
    mensagem = dp_parametros.carregar(conn, current_user.get("company_id", 1))["mensagem_recibo"]
    conn.close()
    return Response(content=gerar_recibos_html(company, run, items, mensagem), media_type="text/html")


@router.get("/payroll/{run_id:int}/folha-impressa")
def imprimir_folha(run_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Folha de pagamento analítica com resumo por rubrica, bases e encargos."""
    conn = get_conn()
    run, company, items = _load_payroll_print(conn, run_id, current_user.get("company_id", 1))
    conn.close()
    if not run:
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    return Response(content=gerar_folha_html(company, run, items), media_type="text/html")


@router.get("/employees/{emp_id}/holerites")
def listar_holerites_funcionario(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Holerites já processados do funcionário (mais recentes primeiro), para o portal."""
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT pr.id AS run_id, pr.competence AS competencia, COALESCE(pr.tipo, 'mensal') AS tipo,
               pi.gross_salary, pi.net_salary
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id = pi.run_id
        WHERE pi.employee_id = ? AND pr.company_id = ?
        ORDER BY pr.competence DESC, pr.id DESC LIMIT 36
    """, (emp_id, current_user.get("company_id", 1))).fetchall())
    conn.close()
    return rows


@router.delete("/payroll/{run_id:int}")
def delete_payroll_run(run_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Exclui uma folha ainda não fechada, para permitir o reprocessamento da competência."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    run = conn.execute(
        "SELECT id, status FROM payroll_runs WHERE id = ? AND company_id = ?", (run_id, company_id)
    ).fetchone()
    if not run:
        conn.close()
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    if dict(run)["status"] == "fechado":
        conn.close()
        raise HTTPException(status_code=400, detail="Folha fechada não pode ser excluída.")
    filhas = conn.execute("SELECT COUNT(*) AS n FROM payroll_runs WHERE parent_run_id = ? AND status != 'cancelado'",
                          (run_id,)).fetchone()
    if filhas and int(dict(filhas)["n"] or 0) > 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Esta folha tem folha complementar vinculada: exclua a "
                                                    "complementar primeiro.")
    conn.execute("DELETE FROM payroll_item_lines WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM payroll_items WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM payroll_runs WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── FOLHA COMPLEMENTAR E DISSÍDIO RETROATIVO ─────────────────────────────────

def _comp_ok(c: Any) -> str:
    c = str(c or "")[:7]
    if not _re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", c):
        raise HTTPException(status_code=400, detail="Competência inválida (use AAAA-MM).")
    return c


def _calc_complementar(conn, company_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    comp = _comp_ok(data.get("competence") or data.get("competencia"))
    try:
        return payroll_complementar.calcular_complementar(
            conn, company_id, comp, data.get("lancamentos") or [], data.get("employee_ids") or [])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payroll/complementar/opcoes")
def opcoes_complementar(competence: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Funcionários da folha mensal da competência e rubricas que não aceitam lançamento na complementar."""
    comp = _comp_ok(competence)
    conn = get_conn()
    try:
        return {"competencia": comp,
                "funcionarios": payroll_complementar.funcionarios_da_folha(conn, current_user.get("company_id", 1), comp),
                "rubricas_bloqueadas": sorted(payroll_complementar.RUBRICAS_BLOQUEADAS)}
    finally:
        conn.close()


@router.post("/payroll/complementar/preview")
def preview_complementar(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Simula a folha complementar: recalcula o mês com os lançamentos novos e mostra só as diferenças."""
    conn = get_conn()
    try:
        return _calc_complementar(conn, current_user.get("company_id", 1), data)
    finally:
        conn.close()


@router.post("/payroll/complementar", status_code=201)
def processar_complementar(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Grava a folha complementar da competência (tipo 'complementar', ligada à folha mensal)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        payroll_engine.ensure_system_rubrics(conn, company_id)
        calc = _calc_complementar(conn, company_id, data)
        if not calc["results"]:
            motivos = "; ".join(f"{g['employee_name']}: {g['motivo']}" for g in calc["ignorados"])
            raise HTTPException(status_code=400, detail=("Nada a gravar. " + motivos) if motivos else
                                "Não há diferença a pagar: os valores recalculados são iguais aos já pagos.")
        mensal = conn.execute("""SELECT id FROM payroll_runs WHERE company_id=? AND competence=? AND status != 'cancelado'
                                 AND COALESCE(tipo, 'mensal')='mensal'""", (company_id, calc["competencia"])).fetchone()
        run_id = _gravar_folha(conn, company_id, calc["competencia"], calc, "complementar", mensal["id"],
                               (data.get("descricao") or "Folha complementar")[:255])
        conn.commit()
        out = _load_payroll_run(conn, run_id, company_id)
        out["avisos"] = [{"employee_name": r["employee_name"], "avisos": r["avisos"]}
                         for r in calc["results"] if r["avisos"]]
        out["ignorados"] = calc["ignorados"]
        return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/payroll/dissidio/preview")
def preview_dissidio(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Simula as diferenças retroativas de dissídio/acordo/convenção mês a mês."""
    conn = get_conn()
    try:
        return payroll_complementar.calcular_dissidio(conn, current_user.get("company_id", 1), data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.post("/payroll/dissidio", status_code=201)
def processar_dissidio(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Grava a folha de diferenças (tipo 'dissidio') na competência de pagamento e, se pedido,
    reajusta o salário cadastrado com registro no histórico salarial."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        payroll_engine.ensure_system_rubrics(conn, company_id)
        try:
            calc = payroll_complementar.calcular_dissidio(conn, company_id, data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not calc["results"]:
            raise HTTPException(status_code=400, detail="Nenhuma diferença encontrada: não há folhas processadas "
                                                        "no período informado.")
        info = calc["info"]
        for r in conn.execute("""SELECT id, info FROM payroll_runs WHERE company_id=? AND competence=? AND tipo='dissidio'
                                 AND status != 'cancelado'""", (company_id, calc["competencia"])).fetchall():
            try:
                ant = _json.loads(dict(r)["info"] or "{}")
            except ValueError:
                ant = {}
            if (ant.get("dt_acordo"), ant.get("competencia_inicio")) == (info["dt_acordo"], info["competencia_inicio"]):
                raise HTTPException(status_code=400, detail=f"Este dissídio já foi processado (folha id={dict(r)['id']}). "
                                                            f"Exclua-a para reprocessar.")
        run_id = _gravar_folha(conn, company_id, calc["competencia"], calc, "dissidio", None,
                               info["descricao"], payroll_complementar.info_json(info))
        reajustados = 0
        if data.get("atualizar_salarios"):
            reajustados = payroll_complementar.atualizar_salarios(conn, company_id, calc["results"],
                                                                  calc["competencia"], info["descricao"])
        conn.commit()
        out = _load_payroll_run(conn, run_id, company_id)
        out["avisos"] = [{"employee_name": r["employee_name"], "avisos": r["avisos"]}
                         for r in calc["results"] if r["avisos"]]
        out["ignorados"] = calc["ignorados"]
        out["salarios_reajustados"] = reajustados
        return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _cnab_txt(val: Any, length: int) -> str:
    s = _unicodedata.normalize("NFKD", str(val or "")).encode("ascii", "ignore").decode("ascii").upper()
    s = " ".join(s.split())
    return s[:length].ljust(length)


def _cnab_num(val: Any, length: int) -> str:
    digits = _re.sub(r"\D", "", str(val or ""))
    return digits[-length:].zfill(length)


def _cnab_val(val: float, length: int = 15) -> str:
    cents = int(round(max(0.0, float(val or 0)) * 100))
    return str(cents).zfill(length)[-length:]


@router.get("/payroll/{run_id:int}/cnab240")
def export_payroll_cnab240(
    run_id: int,
    banco_codigo: str = Query(default="341"),
    data_pagamento: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Gera arquivo de remessa bancária FEBRABAN CNAB 240 para pagamento de salários em lote."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    loaded = _load_payroll_run(conn, run_id, company_id)
    if not loaded:
        conn.close()
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    bank_acc = dict(conn.execute(
        "SELECT * FROM bank_accounts WHERE company_id = ? AND active = 1 ORDER BY id LIMIT 1",
        (company_id,),
    ).fetchone() or {})
    emp_rows = {
        e["id"]: dict(e)
        for e in conn.execute("SELECT * FROM employees WHERE company_id = ?", (company_id,)).fetchall()
    }
    conn.close()

    run = loaded["run"]
    pagos = [it for it in loaded["items"] if float(it.get("net_salary") or 0) > 0]
    if not pagos:
        raise HTTPException(status_code=400, detail="Nenhum funcionário com valor líquido positivo nesta folha.")

    banco = _cnab_num(banco_codigo or bank_acc.get("bank_code") or "341", 3)
    cnpj = _cnab_num(company.get("cnpj"), 14)
    razao = _cnab_txt(company.get("razao_social") or "EMPRESA", 30)
    ag = _cnab_num(bank_acc.get("agency") or "0001", 5)
    conta_full = _re.sub(r"\D", "", str(bank_acc.get("account_number") or "000010"))
    cc = _cnab_num(conta_full[:-1] or "1", 12)
    dac = _cnab_num(conta_full[-1:] or "0", 1)
    now = datetime.now()
    dt_ger = now.strftime("%d%m%Y")
    hr_ger = now.strftime("%H%M%S")
    dt_pag = _re.sub(r"\D", "", data_pagamento or "")
    dt_pag_fmt = f"{dt_pag[6:8]}{dt_pag[4:6]}{dt_pag[0:4]}" if len(dt_pag) == 8 else dt_ger
    banco_nome = _cnab_txt(bank_acc.get("bank_name") or "BANCO PAGADOR", 30)

    lines: List[str] = []

    # 0 — Header de Arquivo (240)
    h_arq = (
        banco + "0000" + "0" + (" " * 9) + "2" + cnpj + _cnab_txt("CORTEX", 20)
        + ag + " " + cc + dac + " " + razao + banco_nome + (" " * 10)
        + "1" + dt_ger + hr_ger + _cnab_num(run_id, 6) + "103" + "00000"
        + (" " * 69)
    )
    lines.append(h_arq[:240].ljust(240))

    # 1 — Header de Lote (30 = Pagamento de Salários) (240)
    h_lote = (
        banco + "0001" + "1" + "C" + "30" + "01" + "046" + " "
        + "2" + cnpj + _cnab_txt("CORTEX", 20) + ag + " " + cc + dac + " "
        + razao + (" " * 40)
        + _cnab_txt(company.get("logradouro") or "", 30)
        + _cnab_num(company.get("numero") or "0", 5)
        + _cnab_txt(company.get("complemento") or "", 15)
        + _cnab_txt(company.get("cidade") or "", 20)
        + _cnab_num(company.get("cep") or "0", 8)
        + _cnab_txt(company.get("uf") or "MT", 2)
        + (" " * 18)
    )
    lines.append(h_lote[:240].ljust(240))

    seq = 0
    total_valor = 0.0
    for it in pagos:
        emp = emp_rows.get(it["employee_id"], {})
        val_liq = round(float(it.get("net_salary") or 0), 2)
        total_valor += val_liq
        emp_bco = _cnab_num(emp.get("bank_name") or banco, 3)
        emp_ag = _cnab_num(emp.get("bank_agency") or "0001", 5)
        emp_acc_raw = _re.sub(r"\D", "", str(emp.get("bank_account") or "000010"))
        emp_cc = _cnab_num(emp_acc_raw[:-1] or "1", 12)
        emp_dac = _cnab_num(emp_acc_raw[-1:] or "0", 1)
        emp_cpf = _cnab_num(emp.get("cpf"), 14)

        seq += 1
        seg_a = (
            banco + "0001" + "3" + _cnab_num(seq, 5) + "A" + "0" + "00" + "000"
            + emp_bco + emp_ag + " " + emp_cc + emp_dac + " "
            + _cnab_txt(it.get("employee_name"), 30)
            + _cnab_txt(f"FOLHA-{run['competence']}-{it['employee_id']}", 20)
            + dt_pag_fmt + "BRL" + ("0" * 15) + _cnab_val(val_liq, 15)
            + (" " * 20) + ("0" * 8) + ("0" * 15) + (" " * 40) + "00" + "00000" + " " + (" " * 10)
        )
        lines.append(seg_a[:240].ljust(240))

        seq += 1
        seg_b = (
            banco + "0001" + "3" + _cnab_num(seq, 5) + "B" + (" " * 3)
            + "1" + emp_cpf
            + _cnab_txt(emp.get("address") or "", 30) + "00000" + (" " * 15) + (" " * 15)
            + _cnab_txt(company.get("cidade") or "", 20) + _cnab_num(emp.get("cep") or "0", 8)
            + _cnab_txt(company.get("uf") or "MT", 2)
            + dt_pag_fmt + _cnab_val(val_liq, 15)
            + ("0" * 60) + (" " * 15) + (" " * 15)
        )
        lines.append(seg_b[:240].ljust(240))

    # 5 — Trailer de Lote (240)
    qtd_reg_lote = seq + 2
    t_lote = (
        banco + "0001" + "5" + (" " * 9) + _cnab_num(qtd_reg_lote, 6)
        + _cnab_val(total_valor, 18) + ("0" * 18) + ("0" * 6) + (" " * 165) + (" " * 10)
    )
    lines.append(t_lote[:240].ljust(240))

    # 9 — Trailer de Arquivo (240)
    qtd_reg_arq = len(lines) + 1
    t_arq = (
        banco + "9999" + "9" + (" " * 9) + "000001" + _cnab_num(qtd_reg_arq, 6)
        + "000000" + (" " * 205)
    )
    lines.append(t_arq[:240].ljust(240))

    content = "\r\n".join(lines) + "\r\n"
    fname = f"CNAB240_FOLHA_{run['competence'].replace('-', '')}.rem"
    return Response(
        content=content.encode("latin1", errors="replace"),
        media_type="text/plain; charset=latin1",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ─── LANÇAMENTOS DE RUBRICA POR FUNCIONÁRIO ───────────────────────────────────

@router.get("/rubrics/formula-help")
def rubric_formula_help(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Variáveis e funções aceitas nas fórmulas de rubrica."""
    return {
        "variaveis": payroll_engine.FORMULA_VARIABLES,
        "funcoes": FORMULA_FUNCOES,
        "exemplos": [
            "salario_base * 0.30",
            "salario_hora * 1.5 * quantidade",
            "se(dias_trabalhados >= 30, 150, 150 * dias_trabalhados / 30)",
            "min(salario_base * 0.06, 220)",
            "rubrica_0001 * 0.05",
        ],
        "rubricas_sistema": sorted(v[0] for v in payroll_engine.SYSTEM_RUBRICS.values()),
    }


@router.post("/rubrics/validate-formula")
def rubric_validate_formula(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        usadas = payroll_engine.validate_formula(str(data.get("formula") or ""))
    except FormulaError as e:
        return {"ok": False, "erro": str(e)}
    return {"ok": True, "variaveis_usadas": usadas}


def _check_formula(formula: Any) -> str:
    formula = str(formula or "").strip()
    if formula:
        try:
            payroll_engine.validate_formula(formula)
        except FormulaError as e:
            raise HTTPException(status_code=422, detail=f"Fórmula inválida: {e}")
    return formula


@router.get("/employee-rubrics")
def list_employee_rubrics(
    employee_id: Optional[int] = Query(None),
    competencia: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Lançamentos de rubrica. competencia vazia no registro = fixo (todo mês)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = """SELECT er.*, e.name AS employee_name, r.codigo, r.nome AS rubric_nome, r.tipo, r.formula
             FROM employee_rubrics er
             JOIN employees e ON e.id = er.employee_id
             JOIN payroll_rubrics r ON r.id = er.rubric_id
             WHERE er.company_id = ?"""
    params: List[Any] = [company_id]
    if employee_id:
        sql += " AND er.employee_id = ?"
        params.append(employee_id)
    if competencia:
        sql += " AND (er.competencia = '' OR er.competencia = ?)"
        params.append(competencia)
    sql += " ORDER BY e.name, r.codigo"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows


def _employee_rubric_payload(conn, company_id: int, data: Dict[str, Any]) -> tuple:
    emp_id, rubric_id = data.get("employee_id"), data.get("rubric_id")
    if not conn.execute("SELECT 1 FROM employees WHERE id=? AND company_id=?", (emp_id, company_id)).fetchone():
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    rub = conn.execute("SELECT * FROM payroll_rubrics WHERE id=? AND company_id=?", (rubric_id, company_id)).fetchone()
    if not rub:
        raise HTTPException(status_code=404, detail="Rubrica não encontrada.")
    rub = dict(rub)
    comp = str(data.get("competencia") or "").strip()
    if comp:
        _valida_competencia(comp)
    try:
        qtd, valor = float(data.get("quantidade") or 0), float(data.get("valor") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Quantidade e valor devem ser numéricos.")
    if qtd < 0 or valor < 0:
        raise HTTPException(status_code=422, detail="Quantidade e valor não podem ser negativos.")
    if rub.get("tipo") == "informativo":
        raise HTTPException(status_code=422, detail="Rubrica informativa não recebe lançamento.")
    codigo = str(rub["codigo"])
    codigos_sistema = {v[0] for v in payroll_engine.SYSTEM_RUBRICS.values()}
    if codigo in ("0002", "0003", "0004"):
        if qtd <= 0:
            raise HTTPException(status_code=422, detail="Informe a quantidade de horas para esta rubrica.")
    elif codigo in codigos_sistema:
        raise HTTPException(status_code=422,
                            detail=f"A rubrica {codigo} é calculada automaticamente pelo sistema e não aceita lançamento.")
    elif not (rub.get("formula") or "").strip() and valor <= 0:
        raise HTTPException(status_code=422, detail="Informe o valor (a rubrica não tem fórmula).")
    return emp_id, rubric_id, comp, qtd, valor, str(data.get("observacao") or "")


@router.post("/employee-rubrics", status_code=201)
def create_employee_rubric(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        emp_id, rubric_id, comp, qtd, valor, obs = _employee_rubric_payload(conn, company_id, data)
    except HTTPException:
        conn.close()
        raise
    cur = conn.cursor()
    cur.execute("""INSERT INTO employee_rubrics (company_id, employee_id, rubric_id, competencia, quantidade, valor, observacao, ativo)
                   VALUES (?,?,?,?,?,?,?,1)""", (company_id, emp_id, rubric_id, comp, qtd, valor, obs))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "ok": True}


@router.put("/employee-rubrics/{er_id}")
def update_employee_rubric(er_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    atual = conn.execute("SELECT * FROM employee_rubrics WHERE id=? AND company_id=?", (er_id, company_id)).fetchone()
    if not atual:
        conn.close()
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
    merged = {**dict(atual), **data}
    try:
        emp_id, rubric_id, comp, qtd, valor, obs = _employee_rubric_payload(conn, company_id, merged)
    except HTTPException:
        conn.close()
        raise
    conn.execute("""UPDATE employee_rubrics SET employee_id=?, rubric_id=?, competencia=?, quantidade=?, valor=?,
                    observacao=?, ativo=? WHERE id=? AND company_id=?""",
                 (emp_id, rubric_id, comp, qtd, valor, obs, int(merged.get("ativo", 1)), er_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/employee-rubrics/{er_id}")
def delete_employee_rubric(er_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM employee_rubrics WHERE id=? AND company_id=?",
                 (er_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── 13º, FÉRIAS E RESCISÃO (motor de rubricas) ───────────────────────────────

def _emp_or_404(conn, company_id: int, emp_id: Any) -> Dict[str, Any]:
    emp = conn.execute(
        "SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, company_id)
    ).fetchone()
    if not emp:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return dict(emp)


def _data_iso(valor: Any, campo: str) -> date:
    try:
        return date.fromisoformat(str(valor or "")[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{campo}: data inválida (use AAAA-MM-DD).")


def _inteiro(valor: Any, campo: str, minimo: int = 0, maximo: int = 10**6) -> int:
    try:
        n = int(float(valor if valor not in (None, "") else 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{campo}: informe um número.")
    if n < minimo or n > maximo:
        raise HTTPException(status_code=422, detail=f"{campo}: deve estar entre {minimo} e {maximo}.")
    return n


def _save_special(conn, company_id: int, tipo: str, res: Dict[str, Any], **campos: Any) -> int:
    import json as _json
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO payroll_special (company_id, employee_id, tipo, referencia, competencia, data_pagamento,
            data_inicio, data_fim, dias_gozo, dias_abono, total_proventos, total_descontos, liquido,
            inss, irrf, fgts, multa_fgts, params, avisos, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'processado')
    """, (company_id, res["employee_id"], tipo, campos.get("referencia", ""), campos.get("competencia", ""),
          campos.get("data_pagamento", ""), campos.get("data_inicio", ""), campos.get("data_fim", ""),
          campos.get("dias_gozo", 0), campos.get("dias_abono", 0),
          res["total_proventos"], res["total_descontos"], res["liquido"],
          res["inss"], res["irrf"], res["fgts"], res.get("multa_fgts", 0),
          _json.dumps(campos.get("params", {}), ensure_ascii=False), " | ".join(res["avisos"])))
    special_id = cur.lastrowid
    for ln in res["lines"]:
        cur.execute("""INSERT INTO payroll_special_lines (special_id, codigo, nome, tipo, referencia, valor, grupo)
                       VALUES (?,?,?,?,?,?,?)""",
                    (special_id, ln["codigo"], ln["nome"], ln["tipo"], ln["referencia"], ln["valor"], ln.get("grupo", "mensal")))
    return special_id


def _list_special(conn, company_id: int, tipos: List[str], employee_id: Optional[int] = None,
                  referencia: Optional[str] = None, special_id: Optional[int] = None) -> List[Dict[str, Any]]:
    sql = f"""SELECT ps.*, e.name AS employee_name, e.role, e.matricula
              FROM payroll_special ps JOIN employees e ON e.id = ps.employee_id
              WHERE ps.company_id = ? AND ps.tipo IN ({','.join('?' * len(tipos))})"""
    params: List[Any] = [company_id, *tipos]
    if employee_id:
        sql += " AND ps.employee_id = ?"
        params.append(employee_id)
    if referencia:
        sql += " AND ps.referencia = ?"
        params.append(referencia)
    if special_id:
        sql += " AND ps.id = ?"
        params.append(special_id)
    sql += " ORDER BY ps.created_at DESC, ps.id DESC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    for r in rows:
        r["lines"] = rows_to_dicts(conn.execute(
            "SELECT * FROM payroll_special_lines WHERE special_id = ? ORDER BY id", (r["id"],)).fetchall())
        # mesmos nomes de campo do holerite mensal, para a tela reaproveitar a tabela
        r["gross_salary"], r["net_salary"] = r["total_proventos"], r["liquido"]
    return rows


def _especial_view(res: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    """Resultado do motor com os nomes de campo que a tabela de holerite da tela espera."""
    return {**res, "gross_salary": res["total_proventos"], "net_salary": res["liquido"], **extra}


# ── 13º salário ──────────────────────────────────────────────────────────────

def _adiant13_ferias(conn, company_id: int, employee_id: int, ano: int) -> float:
    """1ª parcela do 13º paga junto com as férias no ano (Lei 4.749/65 art. 2º §2º)."""
    row = conn.execute(
        """SELECT COALESCE(SUM(psl.valor),0) AS t FROM payroll_special_lines psl
           JOIN payroll_special ps ON ps.id = psl.special_id
           WHERE ps.company_id=? AND ps.employee_id=? AND ps.tipo='ferias' AND ps.status != 'cancelado'
             AND psl.codigo='0020' AND substr(ps.data_inicio,1,4)=?""",
        (company_id, employee_id, str(ano))).fetchone()
    return float(dict(row)["t"] or 0)


def _calc_decimo_emp(conn, company_id: int, emp: Dict[str, Any], ano: int, parcela: int,
                     rubrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if emp.get("is_prolabore"):
        return None  # sócio com pró-labore não tem 13º
    adm = payroll_engine._parse_date(emp.get("admission_date"))
    if adm and adm.year > ano:
        return None
    avos = payroll_special.avos_decimo(adm, ano, None, payroll_special.dias_inss_fn(conn, company_id, emp["id"]))
    if avos <= 0:
        return None
    comp_ref = f"{ano}-11" if parcela == 1 else f"{ano}-12"
    tables = load_tables(conn, company_id, comp_ref)
    ctx = payroll_special.contexto_funcionario(conn, company_id, emp, date(ano, 12, 1))
    comp_ini = max(f"{ano}-01", adm.strftime("%Y-%m")) if adm else f"{ano}-01"
    comp_fim = f"{ano}-10" if parcela == 1 else f"{ano}-11"
    media = payroll_special.media_variaveis(conn, company_id, emp["id"], comp_ini, comp_fim, "incide_13",
                                            payroll_special.meses_entre(comp_ini, comp_fim))
    adiant = 0.0
    adiant_ferias = _adiant13_ferias(conn, company_id, emp["id"], ano)
    if parcela == 1 and adiant_ferias > 0:
        return None  # a 1ª parcela já foi paga com as férias
    if parcela == 2:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_proventos),0) AS t FROM payroll_special
               WHERE company_id=? AND employee_id=? AND tipo='decimo_1' AND referencia=? AND status != 'cancelado'""",
            (company_id, emp["id"], str(ano))).fetchone()
        adiant = float(dict(row)["t"] or 0) + adiant_ferias
    res = payroll_special.calc_decimo(ctx, tables, rubrics, parcela, avos, media, adiant)
    if adiant_ferias and parcela == 2:
        res["avisos"].append(f"Adiantamento de R$ {adiant_ferias:.2f} pago com as férias descontado.")
    return _especial_view(res, ano=ano, media_variaveis=media, competencia=comp_ref)


def _decimo_payload(data: Dict[str, Any]) -> tuple:
    ano = _inteiro(data.get("ano") or date.today().year, "ano", 2000, 2100)
    parcela = _inteiro(data.get("parcela") or 1, "parcela", 1, 2)
    ids = data.get("employee_ids") or None
    return ano, parcela, ({int(i) for i in ids} if ids else None)


def _decimo_coletivo(conn, company_id: int, ano: int, parcela: int, ids: Optional[set]) -> List[Dict[str, Any]]:
    rubrics = payroll_engine.load_rubrics(conn, company_id)
    employees = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id = ? AND active = 1 ORDER BY name", (company_id,)).fetchall())
    out = []
    for emp in employees:
        if ids and emp["id"] not in ids:
            continue
        res = _calc_decimo_emp(conn, company_id, emp, ano, parcela, rubrics)
        if res:
            out.append(res)
    return out


@router.post("/decimo/preview")
def decimo_preview(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Prévia coletiva do 13º (1ª ou 2ª parcela), sem gravar."""
    ano, parcela, ids = _decimo_payload(data)
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    results = _decimo_coletivo(conn, company_id, ano, parcela, ids)
    conn.close()
    prazo = f"{ano}-11-30" if parcela == 1 else f"{ano}-12-20"
    return {"ano": ano, "parcela": parcela, "prazo_legal": prazo, "results": results,
            "totais": {"proventos": round(sum(r["total_proventos"] for r in results), 2),
                       "descontos": round(sum(r["total_descontos"] for r in results), 2),
                       "liquido": round(sum(r["liquido"] for r in results), 2),
                       "fgts": round(sum(r["fgts"] for r in results), 2)}}


@router.post("/decimo/run", status_code=201)
def decimo_run(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Processa e grava o 13º dos funcionários que ainda não têm a parcela no ano."""
    ano, parcela, ids = _decimo_payload(data)
    tipo = f"decimo_{parcela}"
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        payroll_engine.ensure_system_rubrics(conn, company_id)
        ja = {dict(r)["employee_id"] for r in conn.execute(
            "SELECT employee_id FROM payroll_special WHERE company_id=? AND tipo=? AND referencia=? AND status != 'cancelado'",
            (company_id, tipo, str(ano))).fetchall()}
        results = [r for r in _decimo_coletivo(conn, company_id, ano, parcela, ids) if r["employee_id"] not in ja]
        if not results:
            raise HTTPException(status_code=400,
                                detail=f"Nenhum funcionário a processar: a {parcela}ª parcela de {ano} já foi gravada ou não há funcionários com direito.")
        pagamento = str(data.get("data_pagamento") or "")[:10]
        for res in results:
            _save_special(conn, company_id, tipo, res, referencia=str(ano), competencia=res["competencia"],
                          data_pagamento=pagamento,
                          params={"avos": res["avos"], "media_variaveis": res["media_variaveis"]})
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"ok": True, "processados": len(results), "ja_existentes": len(ja)}


@router.get("/decimo")
def decimo_list(ano: Optional[int] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = _list_special(conn, current_user.get("company_id", 1), ["decimo_1", "decimo_2"],
                         referencia=str(ano or date.today().year))
    conn.close()
    return rows


# ── Férias ───────────────────────────────────────────────────────────────────

def _periodos_emp(conn, company_id: int, emp: Dict[str, Any], ate: date,
                  faltas_extra: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    adm = payroll_engine._parse_date(emp.get("admission_date"))
    if not adm:
        raise HTTPException(status_code=400, detail="Funcionário sem data de admissão válida.")
    gozados, faltas = payroll_special.ferias_registradas(conn, company_id, emp["id"])
    faltas.update(faltas_extra or {})
    alerta = int(dp_parametros.carregar(conn, company_id)["ferias_alerta_dias"])
    return payroll_special.periodos_aquisitivos(adm, ate, gozados, faltas,
                                                payroll_special.dias_inss_fn(conn, company_id, emp["id"]),
                                                alerta_dias=alerta)


@router.get("/ferias/periodos/{emp_id}")
def ferias_periodos(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Períodos aquisitivos do funcionário, com saldo, limite do concessivo e situação."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        emp = _emp_or_404(conn, company_id, emp_id)
        periodos = _periodos_emp(conn, company_id, emp, date.today())
        registros = _list_special(conn, company_id, ["ferias"], employee_id=emp_id)
    finally:
        conn.close()
    return {"employee_id": emp_id, "employee_name": emp["name"], "admission_date": emp.get("admission_date"),
            "periodos": periodos, "registros": registros,
            "saldo_total": sum(p["saldo"] for p in periodos),
            "alertas": [p for p in periodos if p["status"] in ("vencido_dobro", "vence_em_breve")]}


def _validar_fracionamento(conn, company_id: int, employee_id: int, periodo: Dict[str, Any],
                           dias_gozo: int, dias_abono: int, ignorar_id: Optional[int] = None) -> None:
    """CLT art. 134 §1º: até 3 períodos de gozo, um com pelo menos 14 dias e os demais com pelo menos 5."""
    fracoes = [int(r["dias_gozo"] or 0) for r in rows_to_dicts(conn.execute(
        """SELECT id, dias_gozo FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo='ferias'
           AND status != 'cancelado' AND referencia=?""", (company_id, employee_id, periodo["inicio"])).fetchall())
        if not ignorar_id or r["id"] != ignorar_id]
    if dias_gozo < 5:
        raise HTTPException(status_code=400, detail="Cada período de férias deve ter pelo menos 5 dias corridos "
                                                    "(CLT art. 134 §1º).")
    if len(fracoes) >= 3:
        raise HTTPException(status_code=400, detail="As férias deste período aquisitivo já foram divididas em 3 partes, "
                                                    "o máximo permitido (CLT art. 134 §1º).")
    restante = int(periodo["saldo"]) - dias_gozo - dias_abono
    if 0 < restante < 5:
        raise HTTPException(status_code=400, detail=f"Sobrariam {restante} dia(s) de férias, e nenhum período pode ter "
                                                    "menos de 5 dias. Ajuste os dias de gozo.")
    if not any(f >= 14 for f in fracoes + [dias_gozo]):
        if len(fracoes) == 2 or restante < 14:
            raise HTTPException(status_code=400, detail="Um dos períodos de férias precisa ter pelo menos 14 dias "
                                                        "corridos (CLT art. 134 §1º).")


def _calc_ferias(conn, company_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    emp = _emp_or_404(conn, company_id, data.get("employee_id"))
    if emp.get("is_prolabore"):
        raise HTTPException(status_code=400, detail="Sócio com pró-labore não tem férias pela CLT.")
    inicio = _data_iso(data.get("data_inicio"), "Início das férias")
    dias_gozo = _inteiro(data.get("dias_gozo") or 30, "Dias de gozo", 1, 30)
    dias_abono = _inteiro(data.get("dias_abono"), "Dias de abono", 0, 10)

    chave = str(data.get("periodo_inicio") or "")[:10]
    faltas_extra = {}
    if data.get("faltas_periodo") not in (None, ""):
        faltas_informadas = _inteiro(data.get("faltas_periodo"), "Faltas no período", 0, 366)
    else:
        faltas_informadas = None
    periodos = _periodos_emp(conn, company_id, emp, inicio)
    if not chave:
        com_saldo = [p for p in periodos if p["completo"] and p["saldo"] > 0]
        if not com_saldo:
            raise HTTPException(status_code=400,
                                detail="Não há período aquisitivo completo com saldo de férias na data de início informada.")
        chave = com_saldo[0]["inicio"]
    if faltas_informadas is not None:
        faltas_extra[chave] = faltas_informadas
        periodos = _periodos_emp(conn, company_id, emp, inicio, faltas_extra)
    periodo = next((p for p in periodos if p["inicio"] == chave), None)
    if not periodo:
        raise HTTPException(status_code=400, detail="Período aquisitivo não encontrado para este funcionário.")
    if not periodo["completo"]:
        raise HTTPException(status_code=400, detail="O período aquisitivo escolhido ainda não foi completado na data de início.")
    if dias_abono > periodo["direito"] // 3:
        raise HTTPException(status_code=400,
                            detail=f"O abono pecuniário é limitado a 1/3 do direito ({periodo['direito'] // 3} dias).")
    if dias_gozo + dias_abono > periodo["saldo"]:
        raise HTTPException(status_code=400,
                            detail=f"O período tem saldo de {periodo['saldo']:g} dia(s); foram pedidos {dias_gozo + dias_abono}.")
    _validar_fracionamento(conn, company_id, emp["id"], periodo, dias_gozo, dias_abono, data.get("_ignorar_id"))

    fim = inicio + timedelta(days=dias_gozo - 1)
    limite = date.fromisoformat(periodo["limite_concessivo"])
    dias_dobro = max(0, min(dias_gozo, (fim - max(inicio - timedelta(days=1), limite)).days))
    media = payroll_special.media_variaveis(conn, company_id, emp["id"], periodo["inicio"][:7], periodo["fim"][:7],
                                            "incide_ferias", 12)
    competencia = inicio.strftime("%Y-%m")
    tables = load_tables(conn, company_id, competencia)
    ctx = payroll_special.contexto_funcionario(conn, company_id, emp, inicio)
    adiant_13 = 0.0
    avisos_13 = []
    if data.get("adiantar_13") in (True, 1, "1", "true", "on"):
        ja_1a = conn.execute(
            "SELECT COUNT(*) FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo IN ('decimo_1','decimo_2') "
            "AND referencia=? AND status != 'cancelado'", (company_id, emp["id"], str(inicio.year))).fetchone()[0]
        if ja_1a or _adiant13_ferias(conn, company_id, emp["id"], inicio.year):
            avisos_13.append("A 1ª parcela do 13º deste ano já foi paga: adiantamento nas férias ignorado.")
        elif inicio.month == 12:
            avisos_13.append("Em dezembro não cabe adiantamento do 13º nas férias (pague a 2ª parcela).")
        else:
            adiant_13 = payroll_engine.r2(ctx.remuneracao(tables) / 2.0)
            if not data.get("solicitado_janeiro", True):
                avisos_13.append("O adiantamento do 13º nas férias depende de requerimento do empregado em janeiro "
                                 "(Lei 4.749/65 art. 2º §2º).")
    res = payroll_special.calc_ferias(ctx, tables, payroll_engine.load_rubrics(conn, company_id),
                                      dias_gozo, dias_abono, media, dias_dobro, adiant_13)
    res["avisos"].extend(avisos_13)
    return _especial_view(
        res, periodo=periodo, data_inicio=inicio.isoformat(), data_fim=fim.isoformat(),
        data_retorno=(fim + timedelta(days=1)).isoformat(),
        data_pagamento_limite=(inicio - timedelta(days=2)).isoformat(),
        competencia=competencia, media_variaveis=media,
        faltas_periodo=faltas_informadas if faltas_informadas is not None else 0)


@router.post("/ferias/preview")
def ferias_preview(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        return _calc_ferias(conn, current_user.get("company_id", 1), data)
    finally:
        conn.close()


@router.post("/ferias", status_code=201)
def ferias_create(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Grava as férias: baixa o saldo do período e desconta os dias na folha mensal."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        payroll_engine.ensure_system_rubrics(conn, company_id)
        new_id, res = _gravar_ferias(conn, company_id, data)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"id": new_id, "ok": True, **res}


def _gravar_ferias(conn, company_id: int, data: Dict[str, Any]):
    """Calcula e grava um recibo de férias (sem commit). Devolve (id, cálculo)."""
    res = _calc_ferias(conn, company_id, data)
    sobrepostas = conn.execute(
        """SELECT COUNT(*) FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo='ferias'
           AND status != 'cancelado' AND data_inicio <= ? AND data_fim >= ?""",
        (company_id, res["employee_id"], res["data_fim"], res["data_inicio"])).fetchone()[0]
    if sobrepostas:
        raise HTTPException(status_code=400, detail="Já existem férias gravadas que se sobrepõem a essas datas.")
    new_id = _save_special(
        conn, company_id, "ferias", res, referencia=res["periodo"]["inicio"], competencia=res["competencia"],
        data_pagamento=res["data_pagamento_limite"], data_inicio=res["data_inicio"], data_fim=res["data_fim"],
        dias_gozo=res["dias_gozo"], dias_abono=res["dias_abono"],
        params={"periodo_fim": res["periodo"]["fim"], "faltas_periodo": res["faltas_periodo"],
                "dias_dobro": res["dias_dobro"], "media_variaveis": res["media_variaveis"],
                "adiantamento_13": res.get("adiantamento_13", 0),
                "coletivas": bool(data.get("coletivas"))})
    return new_id, res


# ── Férias em grupo / coletivas ──────────────────────────────────────────────

def _funcionarios_selecionados(conn, company_id: int, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    emps = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id=? AND active=1 AND COALESCE(is_prolabore, 0)=0 ORDER BY name",
        (company_id,)).fetchall())
    ids = {int(i) for i in (data.get("employee_ids") or []) if str(i).strip()}
    depto = str(data.get("departamento") or "").strip()
    if ids:
        emps = [e for e in emps if e["id"] in ids]
    elif depto:
        emps = [e for e in emps if (e.get("department") or "").strip().lower() == depto.lower()]
    elif not data.get("todos"):
        raise HTTPException(status_code=400, detail="Escolha os funcionários, um departamento ou 'todos'.")
    if not emps:
        raise HTTPException(status_code=400, detail="Nenhum funcionário ativo encontrado para a seleção.")
    return emps


def _ferias_grupo(conn, company_id: int, data: Dict[str, Any], gravar: bool) -> Dict[str, Any]:
    coletivas = bool(data.get("coletivas"))
    inicio = _data_iso(data.get("data_inicio"), "Início das férias")
    dias_gozo = _inteiro(data.get("dias_gozo") or 30, "Dias de gozo", 1, 30)
    if coletivas and dias_gozo < 10:
        raise HTTPException(status_code=400, detail="Férias coletivas não podem ter menos de 10 dias (CLT art. 139 §1º).")
    ok, ignorados = [], []
    for emp in _funcionarios_selecionados(conn, company_id, data):
        item = {"employee_id": emp["id"], "data_inicio": inicio.isoformat(), "dias_gozo": dias_gozo,
                "dias_abono": 0, "coletivas": coletivas}
        try:
            if gravar:
                conn.execute("SAVEPOINT ferias_grupo")
                new_id, res = _gravar_ferias(conn, company_id, item)
                conn.execute("RELEASE SAVEPOINT ferias_grupo")
            else:
                new_id, res = None, _calc_ferias(conn, company_id, item)
        except HTTPException as e:
            if gravar:
                conn.execute("ROLLBACK TO SAVEPOINT ferias_grupo")
                conn.execute("RELEASE SAVEPOINT ferias_grupo")
            motivo = str(e.detail)
            if coletivas and "período aquisitivo completo" in motivo:
                motivo = ("Sem período aquisitivo completo: nas coletivas recebe férias proporcionais e inicia novo "
                          "período (CLT art. 140), ainda não automatizado. Lance os dias como licença remunerada.")
            ignorados.append({"employee_id": emp["id"], "employee_name": emp["name"], "motivo": motivo})
            continue
        ok.append({"id": new_id, "employee_id": emp["id"], "employee_name": emp["name"],
                   "periodo": res["periodo"]["inicio"] + " a " + res["periodo"]["fim"],
                   "data_inicio": res["data_inicio"], "data_fim": res["data_fim"], "dias_gozo": res["dias_gozo"],
                   "dias_dobro": res.get("dias_dobro", 0), "bruto": res.get("total_proventos", 0),
                   "liquido": res.get("liquido", 0), "avisos": res.get("avisos", [])})
    avisos = []
    if coletivas:
        avisos.append("Comunique o órgão local do Ministério do Trabalho e o sindicato com 15 dias de antecedência "
                      "e afixe aviso no local de trabalho (CLT art. 139 §§2º e 3º).")
    return {"coletivas": coletivas, "data_inicio": inicio.isoformat(), "dias_gozo": dias_gozo,
            "funcionarios": ok, "ignorados": ignorados, "avisos": avisos,
            "total_bruto": round(sum(float(o["bruto"] or 0) for o in ok), 2),
            "total_liquido": round(sum(float(o["liquido"] or 0) for o in ok), 2)}


@router.post("/ferias/grupo/preview")
def ferias_grupo_preview(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Simula férias para vários funcionários (individuais em grupo ou coletivas)."""
    conn = get_conn()
    try:
        return _ferias_grupo(conn, current_user.get("company_id", 1), data, gravar=False)
    finally:
        conn.close()


@router.post("/ferias/grupo", status_code=201)
def ferias_grupo_gravar(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Grava as férias de cada funcionário apto; os que não puderem ficam listados em 'ignorados'."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        payroll_engine.ensure_system_rubrics(conn, company_id)
        out = _ferias_grupo(conn, company_id, data, gravar=True)
        if not out["funcionarios"]:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Nenhuma férias gravada. " + "; ".join(
                f"{g['employee_name']}: {g['motivo']}" for g in out["ignorados"]))
        conn.commit()
        return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Programação de férias ────────────────────────────────────────────────────

def _programacao_valores(conn, company_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    emp = _emp_or_404(conn, company_id, data.get("employee_id"))
    inicio = _data_iso(data.get("data_inicio"), "Início previsto")
    v = {"employee_id": emp["id"], "data_inicio": inicio.isoformat(),
         "dias_gozo": _inteiro(data.get("dias_gozo") or 30, "Dias de gozo", 5, 30),
         "dias_abono": _inteiro(data.get("dias_abono"), "Dias de abono", 0, 10),
         "adiantar_13": 1 if data.get("adiantar_13") in (True, 1, "1", "true", "on") else 0,
         "periodo_inicio": str(data.get("periodo_inicio") or "")[:10],
         "observacao": str(data.get("observacao") or "")[:255]}
    if not v["periodo_inicio"]:
        periodos = _periodos_emp(conn, company_id, emp, inicio)
        abertos = [p for p in periodos if p["completo"] and p["saldo"] > 0] or [p for p in periodos if not p["completo"]]
        if not abertos:
            raise HTTPException(status_code=400, detail="Funcionário sem período aquisitivo em aberto.")
        v["periodo_inicio"] = abertos[0]["inicio"]
    return v


def _programacao_view(conn, company_id: int, row: Dict[str, Any], emp: Dict[str, Any]) -> Dict[str, Any]:
    inicio = date.fromisoformat(row["data_inicio"])
    fim = inicio + timedelta(days=int(row["dias_gozo"]) - 1)
    alertas = []
    try:
        periodo = next((p for p in _periodos_emp(conn, company_id, emp, inicio)
                        if p["inicio"] == row["periodo_inicio"]), None)
    except HTTPException:
        periodo = None
    if periodo:
        if not periodo["completo"]:
            alertas.append(f"Período aquisitivo só se completa em {periodo['fim']}.")
        if fim.isoformat() > periodo["limite_concessivo"]:
            alertas.append(f"Termina depois do limite concessivo ({periodo['limite_concessivo']}): "
                           "dias excedentes em dobro.")
    return {**row, "employee_name": emp["name"], "department": emp.get("department") or "",
            "data_fim": fim.isoformat(), "data_retorno": (fim + timedelta(days=1)).isoformat(),
            "limite_concessivo": periodo["limite_concessivo"] if periodo else "", "alertas": alertas}


def _programacao_listar(conn, company_id: int, ano: Optional[int], status: Optional[str]) -> List[Dict[str, Any]]:
    sql, params = "SELECT * FROM ferias_programacao WHERE company_id=?", [company_id]
    if ano:
        sql += " AND data_inicio LIKE ?"
        params.append(f"{int(ano)}-%")
    if status:
        sql += " AND status=?"
        params.append(status)
    rows = rows_to_dicts(conn.execute(sql + " ORDER BY data_inicio", params).fetchall())
    emps = {e["id"]: e for e in rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id=?", (company_id,)).fetchall())}
    return [_programacao_view(conn, company_id, r, emps[r["employee_id"]]) for r in rows if r["employee_id"] in emps]


@router.get("/ferias/programacao")
def ferias_programacao_list(ano: Optional[int] = None, status: Optional[str] = None,
                            current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        return _programacao_listar(conn, current_user.get("company_id", 1), ano, status)
    finally:
        conn.close()


@router.post("/ferias/programacao", status_code=201)
def ferias_programacao_create(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        v = _programacao_valores(conn, company_id, data)
        cur = conn.execute(
            """INSERT INTO ferias_programacao (company_id, employee_id, periodo_inicio, data_inicio, dias_gozo,
               dias_abono, adiantar_13, status, observacao) VALUES (?,?,?,?,?,?,?,'programada',?)""",
            (company_id, v["employee_id"], v["periodo_inicio"], v["data_inicio"], v["dias_gozo"], v["dias_abono"],
             v["adiantar_13"], v["observacao"]))
        conn.commit()
        row = dict(conn.execute("SELECT * FROM ferias_programacao WHERE id=?", (cur.lastrowid,)).fetchone())
        return _programacao_view(conn, company_id, row, _emp_or_404(conn, company_id, row["employee_id"]))
    finally:
        conn.close()


def _programacao_or_404(conn, company_id: int, prog_id: int) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM ferias_programacao WHERE id=? AND company_id=?", (prog_id, company_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Programação não encontrada.")
    return dict(row)


@router.put("/ferias/programacao/{prog_id:int}")
def ferias_programacao_update(prog_id: int, data: Dict[str, Any] = Body(...),
                              current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        atual = _programacao_or_404(conn, company_id, prog_id)
        if atual["status"] != "programada":
            raise HTTPException(status_code=400, detail="Só é possível alterar programações ainda não calculadas.")
        v = _programacao_valores(conn, company_id, {**atual, **data})
        conn.execute("""UPDATE ferias_programacao SET employee_id=?, periodo_inicio=?, data_inicio=?, dias_gozo=?,
                        dias_abono=?, adiantar_13=?, observacao=? WHERE id=?""",
                     (v["employee_id"], v["periodo_inicio"], v["data_inicio"], v["dias_gozo"], v["dias_abono"],
                      v["adiantar_13"], v["observacao"], prog_id))
        conn.commit()
        row = _programacao_or_404(conn, company_id, prog_id)
        return _programacao_view(conn, company_id, row, _emp_or_404(conn, company_id, row["employee_id"]))
    finally:
        conn.close()


@router.delete("/ferias/programacao/{prog_id:int}")
def ferias_programacao_delete(prog_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        atual = _programacao_or_404(conn, company_id, prog_id)
        if atual["status"] == "calculada":
            raise HTTPException(status_code=400, detail="Programação já calculada: exclua o recibo de férias primeiro.")
        conn.execute("DELETE FROM ferias_programacao WHERE id=?", (prog_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/ferias/programacao/{prog_id:int}/calcular", status_code=201)
def ferias_programacao_calcular(prog_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Transforma a programação em recibo de férias gravado."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        prog = _programacao_or_404(conn, company_id, prog_id)
        if prog["status"] != "programada":
            raise HTTPException(status_code=400, detail="Esta programação já foi calculada.")
        payroll_engine.ensure_system_rubrics(conn, company_id)
        new_id, res = _gravar_ferias(conn, company_id, {
            "employee_id": prog["employee_id"], "data_inicio": prog["data_inicio"], "dias_gozo": prog["dias_gozo"],
            "dias_abono": prog["dias_abono"], "periodo_inicio": prog["periodo_inicio"],
            "adiantar_13": bool(prog["adiantar_13"])})
        conn.execute("UPDATE ferias_programacao SET status='calculada', special_id=? WHERE id=?", (new_id, prog_id))
        conn.commit()
        return {"id": new_id, "programacao_id": prog_id, **res}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _esc_html(t: Any) -> str:
    return str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _data_br(d: str) -> str:
    return "/".join(reversed(d.split("-"))) if d else ""


@router.get("/ferias/programacao/relatorio", response_class=HTMLResponse)
def ferias_programacao_relatorio(ano: int = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Relatório de programação de férias do ano, agrupado por mês de início."""
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    try:
        itens = _programacao_listar(conn, company_id, ano, None)
        co = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    finally:
        conn.close()
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
             "Outubro", "Novembro", "Dezembro"]
    situ = {"programada": "Programada", "calculada": "Calculada", "cancelada": "Cancelada"}
    blocos = []
    for m in range(1, 13):
        do_mes = [i for i in itens if i["data_inicio"][5:7] == f"{m:02d}"]
        if not do_mes:
            continue
        linhas = "".join(
            f"<tr><td>{_esc_html(i['employee_name'])}</td><td>{_esc_html(i['department'])}</td>"
            f"<td>{_data_br(i['periodo_inicio'])}</td><td>{_data_br(i['data_inicio'])}</td>"
            f"<td>{_data_br(i['data_fim'])}</td><td class='n'>{i['dias_gozo']}</td>"
            f"<td class='n'>{i['dias_abono'] or ''}</td><td>{'Sim' if i['adiantar_13'] else ''}</td>"
            f"<td>{_data_br(i['limite_concessivo'])}</td><td>{situ.get(i['status'], i['status'])}"
            + (f"<br><small>{_esc_html('; '.join(i['alertas']))}</small>" if i["alertas"] else "")
            + "</td></tr>"
            for i in do_mes)
        blocos.append(f"<h2>{meses[m - 1]}</h2><table><tr><th>Funcionário</th><th>Departamento</th>"
                      "<th>Per. aquisitivo</th><th>Início</th><th>Fim</th><th>Dias</th><th>Abono</th><th>13º</th>"
                      f"<th>Limite concessivo</th><th>Situação</th></tr>{linhas}</table>")
    corpo = "".join(blocos) or "<p>Nenhuma férias programada para o ano.</p>"
    css = ("body{font-family:Arial,sans-serif;font-size:11px;margin:20px}h1{font-size:15px;margin:0}"
           "h2{font-size:12px;background:#eee;padding:4px 6px;margin:14px 0 4px}table{width:100%;border-collapse:collapse}"
           "th,td{border:1px solid #999;padding:3px 5px;text-align:left}th{background:#f5f5f5;font-size:10px}"
           ".n{text-align:right}.np{text-align:right;margin-bottom:8px}@media print{.np{display:none}}")
    html = (f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Programação de férias {ano}</title>'
            f'<style>{css}</style></head><body><div class="np"><button onclick="window.print()">Imprimir / Salvar PDF'
            f'</button></div><h1>{_esc_html(co.get("razao_social"))} — Programação de férias {ano}</h1>'
            f'<div>CNPJ {_esc_html(co.get("cnpj"))} · {len(itens)} programação(ões)</div>{corpo}</body></html>')
    return HTMLResponse(html)


@router.get("/ferias")
def ferias_list(employee_id: Optional[int] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = _list_special(conn, current_user.get("company_id", 1), ["ferias"], employee_id=employee_id)
    conn.close()
    return rows


@router.get("/ferias/alertas")
def ferias_alertas(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Funcionários com férias vencidas (em dobro) ou com o concessivo terminando dentro da antecedência
    definida em DP › Parâmetros (padrão 60 dias)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    out = []
    for emp in rows_to_dicts(conn.execute(
            "SELECT * FROM employees WHERE company_id=? AND active=1 ORDER BY name", (company_id,)).fetchall()):
        if emp.get("is_prolabore") or not payroll_engine._parse_date(emp.get("admission_date")):
            continue
        for p in _periodos_emp(conn, company_id, emp, date.today()):
            if p["status"] in ("vencido_dobro", "vence_em_breve"):
                out.append({"employee_id": emp["id"], "employee_name": emp["name"], **p})
    conn.close()
    return out


# ── Rescisão ─────────────────────────────────────────────────────────────────

def _calc_rescisao(conn, company_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    emp = _emp_or_404(conn, company_id, data.get("employee_id"))
    tipo = str(data.get("tipo") or data.get("termination_type") or "sem_justa_causa")
    if tipo not in payroll_special.TIPOS_RESCISAO:
        raise HTTPException(status_code=422, detail=f"Tipo de rescisão inválido. Use: {', '.join(payroll_special.TIPOS_RESCISAO)}.")
    aviso_modo = str(data.get("aviso_modo") or ("indenizado" if tipo in ("sem_justa_causa", "acordo") else "trabalhado"))
    if aviso_modo not in payroll_special.AVISO_MODOS:
        raise HTTPException(status_code=422, detail=f"Modo de aviso inválido. Use: {', '.join(payroll_special.AVISO_MODOS)}.")
    deslig = _data_iso(data.get("data_desligamento") or data.get("termination_date"), "Data de desligamento")
    adm = payroll_engine._parse_date(emp.get("admission_date"))
    if not adm:
        raise HTTPException(status_code=400, detail="Funcionário sem data de admissão válida.")
    if deslig < adm:
        raise HTTPException(status_code=400, detail="A data de desligamento é anterior à admissão.")

    gozados, faltas = payroll_special.ferias_registradas(conn, company_id, emp["id"])
    plano = payroll_special.planejar_rescisao(adm, deslig, tipo, aviso_modo, gozados, faltas,
                                              payroll_special.dias_inss_fn(conn, company_id, emp["id"]))
    comp = deslig.strftime("%Y-%m")
    anterior = (date(deslig.year, deslig.month, 1) - timedelta(days=1)).strftime("%Y-%m")
    ano_ini = max(f"{deslig.year}-01", adm.strftime("%Y-%m"))
    doze_ini = (date(deslig.year - 1, deslig.month, 1)).strftime("%Y-%m")
    eid = emp["id"]
    media_13 = payroll_special.media_variaveis(conn, company_id, eid, ano_ini, anterior, "incide_13",
                                               payroll_special.meses_entre(ano_ini, anterior))
    media_12 = payroll_special.media_variaveis(conn, company_id, eid, doze_ini, anterior, "incide_ferias", 12)

    tem_2a = conn.execute(
        "SELECT COUNT(*) FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo='decimo_2' AND referencia=? AND status != 'cancelado'",
        (company_id, eid, str(deslig.year))).fetchone()[0]
    adiant_13 = 0.0
    if not tem_2a:
        row = conn.execute(
            "SELECT COALESCE(SUM(total_proventos),0) AS t FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo='decimo_1' AND referencia=? AND status != 'cancelado'",
            (company_id, eid, str(deslig.year))).fetchone()
        adiant_13 = float(dict(row)["t"] or 0) + _adiant13_ferias(conn, company_id, eid, deslig.year)

    avisos_extra = []
    if tem_2a:
        plano["avos_13"] = plano["avos_13_indenizado"] = 0
        avisos_extra.append("O 13º deste ano já foi pago integralmente (2ª parcela gravada); não entra na rescisão.")
    if data.get("saldo_fgts") not in (None, ""):
        try:
            saldo_fgts, origem = max(0.0, float(data["saldo_fgts"])), "informado"
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Saldo do FGTS: informe um número.")
    else:
        saldo_fgts, origem = payroll_special.saldo_fgts_estimado(conn, company_id, emp, deslig)
        if plano["multa_pct"]:
            avisos_extra.append(f"Saldo do FGTS para a multa obtido por {origem}. Informe o saldo do extrato da Caixa para o valor exato.")

    adiantamentos = sum(float(dict(a)["valor"] or 0) for a in conn.execute(
        "SELECT valor, status FROM salary_advances WHERE company_id=? AND employee_id=? AND competencia=?",
        (company_id, eid, comp)).fetchall() if (dict(a).get("status") or "pago").lower() not in ("cancelado", "rejeitado"))
    try:
        outros = max(0.0, float(data.get("outros_descontos") or 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Outros descontos: informe um número.")

    tables = load_tables(conn, company_id, comp)
    ctx = payroll_special.contexto_funcionario(conn, company_id, emp, deslig)
    res = payroll_special.calc_rescisao(ctx, tables, payroll_engine.load_rubrics(conn, company_id), plano,
                                        media_13=media_13, media_ferias=media_12, media_aviso=media_12,
                                        adiantamento_13=adiant_13, saldo_fgts=saldo_fgts,
                                        outros_descontos=adiantamentos + outros)
    res["avisos"].extend(avisos_extra)
    return _especial_view(res, tipo=tipo, tipo_nome=payroll_special.TIPOS_RESCISAO[tipo]["nome"],
                          aviso_modo=aviso_modo, data_desligamento=deslig.isoformat(), competencia=comp,
                          saldo_fgts_origem=origem, admission_date=emp.get("admission_date"))


@router.post("/rescisao/preview")
def rescisao_preview(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        return _calc_rescisao(conn, current_user.get("company_id", 1), data)
    finally:
        conn.close()


@router.post("/rescisao", status_code=201)
def rescisao_create(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Grava a rescisão. Com desligar=true (padrão), o funcionário é marcado como desligado."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        payroll_engine.ensure_system_rubrics(conn, company_id)
        res = _calc_rescisao(conn, company_id, data)
        if conn.execute(
                "SELECT COUNT(*) FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo='rescisao' AND status != 'cancelado'",
                (company_id, res["employee_id"])).fetchone()[0]:
            raise HTTPException(status_code=400, detail="Este funcionário já tem uma rescisão gravada. Exclua-a para refazer.")
        desligar = data.get("desligar", True) not in (False, 0, "false", "0")
        new_id = _save_special(
            conn, company_id, "rescisao", res, referencia=res["tipo"], competencia=res["competencia"],
            data_inicio=res["data_desligamento"], data_fim=res["plano"]["data_projetada"],
            params={"plano": res["plano"], "aviso_modo": res["aviso_modo"], "saldo_fgts": res["saldo_fgts"],
                    "saldo_fgts_origem": res["saldo_fgts_origem"], "desligou": desligar})
        if desligar:
            conn.execute("UPDATE employees SET active = 0, termination_date = ?, termination_reason = ? WHERE id = ? AND company_id = ?",
                         (res["data_desligamento"], res["tipo"], res["employee_id"], company_id))
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"id": new_id, "ok": True, "desligado": desligar, **res}


@router.get("/rescisao")
def rescisao_list(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = _list_special(conn, current_user.get("company_id", 1), ["rescisao"])
    conn.close()
    return rows


@router.get("/rescisao/tipos")
def rescisao_tipos(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"tipos": {k: v["nome"] for k, v in payroll_special.TIPOS_RESCISAO.items()},
            "aviso_modos": list(payroll_special.AVISO_MODOS)}


@router.get("/especiais/{special_id}")
def especial_get(special_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = _list_special(conn, current_user.get("company_id", 1),
                         ["decimo_1", "decimo_2", "ferias", "rescisao"], special_id=special_id)
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    return rows[0]


@router.get("/especiais/{special_id}/esocial/s2299")
def especial_esocial_s2299(special_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera o XML S-2299 (Desligamento) detalhado por rubricas a partir da rescisão gravada."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = _list_special(conn, company_id, ["rescisao"], special_id=special_id)
    if not rows:
        conn.close()
        raise HTTPException(status_code=404, detail="Rescisão não encontrada.")
    reg = rows[0]
    emp = dict(conn.execute("SELECT * FROM employees WHERE id = ? AND company_id = ?",
                            (reg["employee_id"], company_id)).fetchone() or {})
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    conn.close()
    try:
        params = _json.loads(reg.get("params") or "{}")
    except (ValueError, TypeError):
        params = {}
    motivo_map = {
        "com_justa_causa": "04",
        "pedido_demissao": "02",
        "sem_justa_causa": "03",
        "acordo": "10",
        "termino_contrato": "11",
    }
    motivo = motivo_map.get(reg.get("referencia") or "", "03")
    res_obj = {**reg, "plano": params.get("plano") or {}}
    dt_deslig = reg.get("data_inicio") or date.today().isoformat()
    xml = gerar_s2299(company, emp, dt_deslig, motivo, rescisao=res_obj)
    cpf_clean = (emp.get("cpf") or "").replace(".", "").replace("-", "")
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="S2299_{cpf_clean}_{dt_deslig.replace("-", "")}.xml"'},
    )


def _fmt_brl(val: Any) -> str:
    v = float(val or 0.0)
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_dt(val: Any) -> str:
    s = str(val or "")[:10]
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s or "-"


@router.get("/especiais/{special_id}/documento", response_class=HTMLResponse)
def especial_documento_html(special_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera documento trabalhista imprimível (TRCT, Recibo de Férias ou Recibo de 13º)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = _list_special(conn, company_id, ["decimo_1", "decimo_2", "ferias", "rescisao"], special_id=special_id)
    if not rows:
        conn.close()
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    reg = rows[0]
    emp = dict(conn.execute("SELECT * FROM employees WHERE id = ?", (reg["employee_id"],)).fetchone() or {})
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    conn.close()

    try:
        params = _json.loads(reg.get("params") or "{}")
    except (ValueError, TypeError):
        params = {}

    tipo = reg["tipo"]
    proventos = [l for l in reg["lines"] if l.get("tipo") == "provento"]
    descontos = [l for l in reg["lines"] if l.get("tipo") == "desconto"]
    infos = [l for l in reg["lines"] if l.get("tipo") == "informativo"]

    def rows_html(items: List[Dict[str, Any]]) -> str:
        if not items:
            return "<tr><td colspan='4' style='text-align:center;color:#64748b'>Nenhum lançamento</td></tr>"
        return "".join(
            f"<tr><td>{l['codigo']}</td><td>{l['nome']}</td>"
            f"<td style='text-align:center'>{l.get('referencia') or '-'}</td>"
            f"<td style='text-align:right'>{_fmt_brl(l['valor'])}</td></tr>"
            for l in items
        )

    if tipo == "rescisao":
        titulo = "TERMO DE RESCISÃO DO CONTRATO DE TRABALHO (TRCT)"
        tipo_nome = payroll_special.TIPOS_RESCISAO.get(reg.get("referencia") or "", {}).get("nome", reg.get("referencia") or "")
        bloco_extra = f"""
        <div class="grid">
          <div><span class="lbl">Causa do Afastamento</span><div><strong>{tipo_nome}</strong> ({params.get('aviso_modo', '-')})</div></div>
          <div><span class="lbl">Data de Admissão</span><div>{_fmt_dt(emp.get('admission_date'))}</div></div>
          <div><span class="lbl">Data de Desligamento</span><div>{_fmt_dt(reg.get('data_inicio'))}</div></div>
          <div><span class="lbl">Projeção Aviso Prévio</span><div>{_fmt_dt(reg.get('data_fim'))}</div></div>
        </div>
        <div class="box">
          <strong>Demonstrativo FGTS e Indenização Rescisória</strong>
          <div style="display:flex;gap:24px;margin-top:6px;font-size:12px">
            <span>FGTS da Rescisão: <strong>{_fmt_brl(reg.get('fgts'))}</strong></span>
            <span>Multa Rescisória FGTS: <strong>{_fmt_brl(reg.get('multa_fgts'))}</strong></span>
          </div>
        </div>"""
    elif tipo == "ferias":
        titulo = "AVISO E RECIBO DE FÉRIAS (ARTS. 135 E 145 DA CLT)"
        bloco_extra = f"""
        <div class="grid">
          <div><span class="lbl">Período Aquisitivo</span><div>{_fmt_dt(reg.get('referencia'))} a {_fmt_dt(params.get('periodo_fim'))}</div></div>
          <div><span class="lbl">Período de Gozo</span><div>{_fmt_dt(reg.get('data_inicio'))} a {_fmt_dt(reg.get('data_fim'))} ({int(reg.get('dias_gozo') or 0)} dias)</div></div>
          <div><span class="lbl">Abono Pecuniário</span><div>{int(reg.get('dias_abono') or 0)} dia(s)</div></div>
          <div><span class="lbl">Limite Pagamento (CLT art. 145)</span><div>{_fmt_dt(reg.get('data_pagamento'))}</div></div>
        </div>"""
    else:
        parcela_lbl = "1ª PARCELA (ADIANTAMENTO)" if tipo == "decimo_1" else "2ª PARCELA (QUITAÇÃO FINAL)"
        titulo = f"RECIBO DE 13º SALÁRIO — {parcela_lbl}"
        bloco_extra = f"""
        <div class="grid">
          <div><span class="lbl">Ano-Base</span><div>{reg.get('referencia')}</div></div>
          <div><span class="lbl">Avos Considerados</span><div>{params.get('avos', 12)}/12</div></div>
          <div><span class="lbl">Competência</span><div>{reg.get('competencia') or '-'}</div></div>
          <div><span class="lbl">Data de Pagamento</span><div>{_fmt_dt(reg.get('data_pagamento'))}</div></div>
        </div>"""

    info_html = ""
    if infos:
        info_html = "<div class='box'><strong>Bases e Informativos</strong><div style='display:flex;flex-wrap:wrap;gap:18px;margin-top:6px;font-size:12px'>" + "".join(
            f"<span>{l['nome']}: <strong>{_fmt_brl(l['valor'])}</strong></span>" for l in infos
        ) + "</div></div>"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>{titulo} — {emp.get('name', '')}</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; color: #0f172a; margin: 24px; font-size: 13px; }}
    .page {{ max-width: 900px; margin: 0 auto; border: 1px solid #cbd5e1; padding: 24px; }}
    .hdr {{ display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0f172a; padding-bottom:10px; margin-bottom:14px; }}
    .hdr h1 {{ font-size: 16px; margin: 0; text-transform: uppercase; }}
    .grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:10px; border:1px solid #cbd5e1; padding:10px; margin-bottom:12px; background:#f8fafc; }}
    .lbl {{ display:block; font-size:10px; text-transform:uppercase; color:#64748b; }}
    table {{ width:100%; border-collapse:collapse; margin-bottom:12px; }}
    th, td {{ border:1px solid #cbd5e1; padding:6px 8px; font-size:12px; }}
    th {{ background:#f1f5f9; text-align:left; font-size:11px; text-transform:uppercase; }}
    .box {{ border:1px solid #cbd5e1; padding:10px; margin-bottom:12px; background:#f8fafc; }}
    .totais {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:12px; margin:14px 0; }}
    .tot-card {{ border:1px solid #94a3b8; padding:10px; text-align:center; }}
    .tot-card .val {{ font-size:16px; font-weight:bold; margin-top:4px; }}
    .assin {{ display:grid; grid-template-columns: 1fr 1fr; gap:40px; margin-top:38px; }}
    .assin div {{ border-top:1px solid #0f172a; padding-top:6px; text-align:center; font-size:11px; }}
    .no-print {{ margin-bottom:14px; text-align:right; }}
    @media print {{ .no-print {{ display:none; }} body {{ margin:0; }} .page {{ border:none; }} }}
  </style>
</head>
<body>
  <div class="no-print"><button onclick="window.print()" style="padding:8px 16px;cursor:pointer;font-weight:bold">Imprimir / Salvar PDF</button></div>
  <div class="page">
    <div class="hdr">
      <div><h1>{titulo}</h1><div style="font-size:11px;color:#475569">Documento gerado pelo Cortex ERP</div></div>
      <div style="text-align:right;font-size:11px">Registro #{special_id}</div>
    </div>
    <div class="grid">
      <div style="grid-column:span 2"><span class="lbl">Empregador</span><strong>{company.get('razao_social', '')}</strong></div>
      <div><span class="lbl">CNPJ</span>{company.get('cnpj', '')}</div>
      <div><span class="lbl">UF / Município</span>{company.get('cidade', '')}/{company.get('uf', '')}</div>
    </div>
    <div class="grid">
      <div style="grid-column:span 2"><span class="lbl">Empregado</span><strong>{emp.get('name', '')}</strong></div>
      <div><span class="lbl">CPF</span>{emp.get('cpf', '')}</div>
      <div><span class="lbl">PIS / Cargo</span>{emp.get('pis_pasep', '-')} · {emp.get('role', '')}</div>
    </div>
    {bloco_extra}
    <table>
      <thead><tr><th style="width:70px">Cód.</th><th>Proventos (Verbas Devidas)</th><th style="width:90px;text-align:center">Ref.</th><th style="width:130px;text-align:right">Valor</th></tr></thead>
      <tbody>{rows_html(proventos)}</tbody>
    </table>
    <table>
      <thead><tr><th style="width:70px">Cód.</th><th>Descontos (Deduções Legais)</th><th style="width:90px;text-align:center">Ref.</th><th style="width:130px;text-align:right">Valor</th></tr></thead>
      <tbody>{rows_html(descontos)}</tbody>
    </table>
    {info_html}
    <div class="totais">
      <div class="tot-card"><span class="lbl">Total Bruto (Proventos)</span><div class="val">{_fmt_brl(reg.get('total_proventos'))}</div></div>
      <div class="tot-card"><span class="lbl">Total Deduções</span><div class="val" style="color:#be123c">{_fmt_brl(reg.get('total_descontos'))}</div></div>
      <div class="tot-card" style="background:#ecfdf5"><span class="lbl">Valor Líquido a Receber</span><div class="val" style="color:#047857">{_fmt_brl(reg.get('liquido'))}</div></div>
    </div>
    <p style="font-size:11px;color:#334155">Declaro ter recebido a importância líquida discriminada acima, dando plena e geral quitação das verbas especificadas neste demonstrativo.</p>
    <div class="assin">
      <div><strong>{company.get('razao_social', '')}</strong><br>Empregador (Carimbo e Assinatura)</div>
      <div><strong>{emp.get('name', '')}</strong><br>CPF: {emp.get('cpf', '')} — Empregado</div>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.delete("/especiais/{special_id}")
def especial_delete(special_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Exclui um 13º, férias ou rescisão gravados. Excluir a rescisão reativa o funcionário
    se foi ela que o desligou."""
    import json as _json
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("SELECT * FROM payroll_special WHERE id = ? AND company_id = ?", (special_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    row = dict(row)
    if row["tipo"] == "decimo_1" and conn.execute(
            "SELECT COUNT(*) FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo='decimo_2' AND referencia=? AND status != 'cancelado'",
            (company_id, row["employee_id"], row["referencia"])).fetchone()[0]:
        conn.close()
        raise HTTPException(status_code=400, detail="Exclua antes a 2ª parcela deste funcionário, que já descontou este adiantamento.")
    reativado = False
    if row["tipo"] == "rescisao":
        try:
            desligou = bool(_json.loads(row.get("params") or "{}").get("desligou"))
        except ValueError:
            desligou = False
        if desligou:
            conn.execute("UPDATE employees SET active = 1, termination_date = NULL, termination_reason = NULL WHERE id = ? AND company_id = ?",
                         (row["employee_id"], company_id))
            reativado = True
    conn.execute("DELETE FROM payroll_special_lines WHERE special_id = ?", (special_id,))
    conn.execute("DELETE FROM payroll_special WHERE id = ?", (special_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "funcionario_reativado": reativado}


# ── Simulações rápidas (rotas antigas, agora pelo motor de rubricas) ──────────

@router.get("/employees/{emp_id}/thirteenth")
def thirteenth_salary(
    emp_id: int,
    months_worked: int = Query(default=12, ge=1, le=12),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        emp = _emp_or_404(conn, company_id, emp_id)
        hoje = date.today()
        tables = load_tables(conn, company_id, hoje.strftime("%Y-%m"))
        ctx = payroll_special.contexto_funcionario(conn, company_id, emp, hoje)
        rubrics = payroll_engine.load_rubrics(conn, company_id)
        primeira = payroll_special.calc_decimo(ctx, tables, rubrics, 1, months_worked)
        segunda = payroll_special.calc_decimo(ctx, tables, rubrics, 2, months_worked, 0.0, primeira["total_proventos"])
    finally:
        conn.close()
    bruto = round(primeira["total_proventos"] * 2, 2)
    return {"employee_name": emp["name"], "salary": emp["salary"], "months_worked": months_worked,
            "gross_value": bruto, "first_installment": primeira["liquido"],
            "inss": segunda["inss"], "irrf": segunda["irrf"], "second_installment": segunda["liquido"],
            "total_net": round(primeira["liquido"] + segunda["liquido"], 2), "fgts": round(primeira["fgts"] + segunda["fgts"], 2),
            "lines": segunda["lines"], "avisos": []}


@router.get("/employees/{emp_id}/vacation")
def vacation_calculation(
    emp_id: int,
    days: int = Query(default=30, ge=1, le=30),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        emp = _emp_or_404(conn, company_id, emp_id)
        hoje = date.today()
        tables = load_tables(conn, company_id, hoje.strftime("%Y-%m"))
        ctx = payroll_special.contexto_funcionario(conn, company_id, emp, hoje)
        res = payroll_special.calc_ferias(ctx, tables, payroll_engine.load_rubrics(conn, company_id), days)
    finally:
        conn.close()
    ferias = next((l["valor"] for l in res["lines"] if l["codigo"] == "0008"), 0.0)
    terco = next((l["valor"] for l in res["lines"] if l["codigo"] == "0009"), 0.0)
    return {"employee_name": emp["name"], "salary": emp["salary"], "days": days,
            "vacation_pay": ferias, "constitutional_third": terco, "gross_total": res["total_proventos"],
            "inss": res["inss"], "irrf": res["irrf"], "net_total": res["liquido"], "fgts": res["fgts"],
            "lines": res["lines"], "avisos": res["avisos"]}


@router.post("/employees/{emp_id}/termination")
def termination_calculation(
    emp_id: int,
    data: TerminationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    try:
        res = _calc_rescisao(conn, current_user.get("company_id", 1), {
            "employee_id": emp_id, "data_desligamento": data.termination_date, "tipo": data.termination_type})
    finally:
        conn.close()
    return {**res, "type": res["tipo"], "total_bruto": res["total_proventos"], "total_liquido": res["liquido"]}


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
    if not emp:
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    emp = dict(emp)
    emp["_dependentes"] = rows_to_dicts(conn.execute(
        "SELECT * FROM employee_dependents WHERE employee_id = ?", (emp_id,)).fetchall())
    conn.close()
    xml = gerar_s2200(dict(company), emp)
    filename = f"S2200_{dict(emp)['cpf'].replace('.','').replace('-','')}_{date.today().strftime('%Y%m%d')}.xml"
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/payroll/{run_id}/employee/{emp_id}/esocial/s1200")
def esocial_s1200(run_id: int, emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera o XML do evento S-1200 (Remuneração Mensal) detalhado por rubrica."""
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
    if not run or not item or not emp:
        conn.close()
        raise HTTPException(status_code=404, detail="Dados não encontrados.")
    item_d = dict(item)
    lines = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_item_lines WHERE item_id = ? ORDER BY tipo DESC, codigo, id",
        (item_d["id"],),
    ).fetchall())
    conn.close()
    xml = gerar_s1200(dict(company), dict(emp), dict(run)["competence"], item_d, lines=lines)
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


_SCHED_CAMPOS = ("nome", "tipo", "hora_entrada", "hora_saida", "hora_entrada_tarde", "hora_saida_tarde",
                 "intervalo_min", "horas_diarias", "horas_semanais", "dias_trabalho", "ciclo", "data_inicio_ciclo",
                 "intervalo_inicio", "prorrogacao_noturna", "feriados_compensados", "adicional_noturno_auto")


def _sched_valores(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza o horário/escala; para escala cíclica valida o ciclo e calcula as horas do plantão."""
    if not str(data.get("nome") or "").strip():
        raise HTTPException(status_code=400, detail="Informe o nome do horário/escala.")
    v = {
        "nome": str(data["nome"]).strip(), "tipo": data.get("tipo") or "fixo",
        "hora_entrada": data.get("hora_entrada") or "08:00", "hora_saida": data.get("hora_saida") or "17:00",
        "hora_entrada_tarde": data.get("hora_entrada_tarde") or "", "hora_saida_tarde": data.get("hora_saida_tarde") or "",
        "intervalo_min": int(data.get("intervalo_min") if data.get("intervalo_min") not in (None, "") else 60),
        "horas_diarias": float(data.get("horas_diarias") or 0), "horas_semanais": float(data.get("horas_semanais") or 44),
        "dias_trabalho": data.get("dias_trabalho") or "1,2,3,4,5", "ciclo": (data.get("ciclo") or "").strip(),
        "data_inicio_ciclo": (data.get("data_inicio_ciclo") or "")[:10], "intervalo_inicio": data.get("intervalo_inicio") or "",
        "prorrogacao_noturna": 1 if data.get("prorrogacao_noturna", 1) else 0,
        "feriados_compensados": 1 if data.get("feriados_compensados", 1) else 0,
        "adicional_noturno_auto": 1 if data.get("adicional_noturno_auto") else 0,
    }
    if v["tipo"] not in ("fixo", "ciclica"):
        raise HTTPException(status_code=400, detail="Tipo deve ser 'fixo' ou 'ciclica'.")
    if v["tipo"] == "ciclica":
        try:
            ciclo = escalas.parse_ciclo(v["ciclo"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        v["ciclo"] = ",".join("T" if t else "F" for t in ciclo)
        if not escalas._parse_date(v["data_inicio_ciclo"]):
            raise HTTPException(status_code=400, detail="Informe a data do primeiro dia de trabalho do ciclo.")
    turno = escalas.turno_do_dia(v)
    if not v["horas_diarias"]:
        v["horas_diarias"] = turno["horas"]
    return v


@router.post("/work-schedules", status_code=201)
def create_work_schedule(data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    v = _sched_valores(data)
    cur = conn.execute(
        f"INSERT INTO work_schedules (company_id, {', '.join(_SCHED_CAMPOS)}) VALUES (?{', ?' * len(_SCHED_CAMPOS)})",
        (company_id, *[v[c] for c in _SCHED_CAMPOS]))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "turno": escalas.turno_do_dia(v)}


@router.put("/work-schedules/{sched_id}")
def update_work_schedule(sched_id: int, data: dict, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    v = _sched_valores(data)
    conn.execute(
        f"UPDATE work_schedules SET {', '.join(c + '=?' for c in _SCHED_CAMPOS)} WHERE id=? AND company_id=?",
        (*[v[c] for c in _SCHED_CAMPOS], sched_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True, "turno": escalas.turno_do_dia(v)}


@router.get("/escalas/presets")
def escalas_presets(current_user: Dict[str, Any] = Depends(get_current_user)):
    return escalas.PRESETS


@router.get("/work-schedules/{sched_id}/calendario")
def calendario_escala(sched_id: int, competencia: str = Query(...), employee_id: Optional[int] = Query(None),
                      current_user: Dict[str, Any] = Depends(get_current_user)):
    """Calendário do mês da escala (ou do funcionário, com a data de início da turma dele)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = _comp_ok(competencia)
    s = conn.execute("SELECT * FROM work_schedules WHERE id=? AND company_id=?", (sched_id, company_id)).fetchone()
    if not s:
        conn.close()
        raise HTTPException(status_code=404, detail="Horário/escala não encontrado.")
    inicio = None
    if employee_id:
        e = conn.execute("SELECT escala_inicio FROM employees WHERE id=? AND company_id=?", (employee_id, company_id)).fetchone()
        inicio = dict(e).get("escala_inicio") if e else None
    feriados = payroll_engine.month_calendar(conn, company_id, comp)["feriados"]
    conn.close()
    try:
        return escalas.calendario(dict(s), comp, feriados, inicio)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/work-schedules/{sched_id}/funcionarios")
def funcionarios_da_escala(sched_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT id, name, matricula, role, escala_inicio FROM employees WHERE company_id=? AND work_schedule_id=? "
        "AND active=1 ORDER BY name", (current_user.get("company_id", 1), sched_id)).fetchall())
    conn.close()
    return rows


@router.put("/employees/{emp_id}/escala")
def vincular_escala(emp_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Vincula o funcionário a um horário/escala; escala_inicio = 1º dia de trabalho da turma dele."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sid = data.get("work_schedule_id") or None
    ini = (data.get("escala_inicio") or "")[:10]
    if sid:
        s = conn.execute("SELECT id, nome FROM work_schedules WHERE id=? AND company_id=?", (sid, company_id)).fetchone()
        if not s:
            conn.close()
            raise HTTPException(status_code=404, detail="Horário/escala não encontrado.")
    if ini and not escalas._parse_date(ini):
        conn.close()
        raise HTTPException(status_code=400, detail="Data de início da escala inválida.")
    cur = conn.execute("UPDATE employees SET work_schedule_id=?, escala_inicio=? WHERE id=? AND company_id=?",
                       (sid, ini, emp_id, company_id))
    if not cur.rowcount:
        conn.close()
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/work-schedules/{sched_id}")
def delete_work_schedule(sched_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("UPDATE employees SET work_schedule_id=NULL WHERE work_schedule_id=? AND company_id=?",
                 (sched_id, company_id))
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
        horas_dia, _sched, _escalado = escalas.jornada_prevista(conn, company_id, emp_id, dt)
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


def _agrupar_plantoes_noturnos(conn, company_id: int, punches: Dict[tuple, List[str]]) -> Dict[tuple, List[str]]:
    """Plantão que vira a meia-noite (ex.: 19h às 7h) pertence ao dia em que começou: as batidas da
    madrugada do dia seguinte (até 4h depois da saída prevista) voltam para o dia anterior, marcadas
    com '+' para ficarem depois das batidas da noite."""
    emps = {k[0] for k in punches}
    noturnos: Dict[int, int] = {}
    for eid in emps:
        e = conn.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (eid, company_id)).fetchone()
        s = escalas.escala_do_funcionario(conn, company_id, dict(e)) if e else None
        if not s:
            continue
        ent, sai = escalas._min(s.get("hora_entrada")), escalas._min(s.get("hora_saida"))
        if ent is not None and sai is not None and sai < ent:
            noturnos[eid] = sai + 240
    if not noturnos:
        return punches
    out: Dict[tuple, List[str]] = {}
    for (eid, dt_iso), horas in sorted(punches.items()):
        corte = noturnos.get(eid)
        for h in horas:
            alvo = dt_iso
            if corte is not None and (escalas._min(h) or 0) <= corte:
                try:
                    anterior = (date.fromisoformat(dt_iso) - timedelta(days=1)).isoformat()
                except ValueError:
                    anterior = None
                if anterior and (eid, anterior) in punches:
                    out.setdefault((eid, anterior), []).append("+" + h)
                    continue
            out.setdefault((eid, alvo), []).append(h)
    return {k: v for k, v in out.items() if v}


@router.post("/ponto/importar-afd", status_code=201)
def importar_afd_ponto(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Importa marcações de arquivo AFD (Portaria 1.510 / 671) ou CSV delimitado por ponto-e-vírgula."""
    conteudo = str(data.get("conteudo") or "").strip()
    comp_filtro = str(data.get("competencia") or "").strip()
    if not conteudo:
        raise HTTPException(status_code=422, detail="Informe o conteúdo do arquivo AFD.")

    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emps = rows_to_dicts(conn.execute(
        "SELECT id, cpf, pis_pasep FROM employees WHERE company_id = ? AND active = 1", (company_id,)
    ).fetchall())
    emp_by_doc: Dict[str, int] = {}
    for e in emps:
        for raw in (e.get("cpf"), e.get("pis_pasep")):
            d = _re.sub(r"\D", "", str(raw or ""))
            if d:
                emp_by_doc[d] = e["id"]
                emp_by_doc[d.lstrip("0") or d] = e["id"]

    sched = conn.execute("SELECT horas_diarias FROM work_schedules WHERE company_id=? LIMIT 1", (company_id,)).fetchone()
    horas_dia = float(sched["horas_diarias"]) if sched else 8.0
    feriados = {
        str(r["data"])[:10]
        for r in conn.execute("SELECT data FROM feriados WHERE company_id=?", (company_id,)).fetchall()
    }

    punches: Dict[tuple, List[str]] = {}
    nao_encontrados = set()

    def _find_emp(doc_raw: str) -> Optional[int]:
        d = _re.sub(r"\D", "", doc_raw or "")
        if not d:
            return None
        return emp_by_doc.get(d) or emp_by_doc.get(d.lstrip("0") or d)

    for raw_line in conteudo.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # 1) Formato delimitado: CPF/PIS;YYYY-MM-DD;HH:MM;...
        if ";" in line or "\t" in line:
            sep = ";" if ";" in line else "\t"
            parts = [p.strip() for p in line.split(sep) if p.strip()]
            if len(parts) >= 3:
                emp_id = _find_emp(parts[0])
                if not emp_id:
                    nao_encontrados.add(parts[0])
                    continue
                dt_raw = parts[1]
                if _re.match(r"^\d{2}/\d{2}/\d{4}$", dt_raw):
                    dt_iso = f"{dt_raw[6:10]}-{dt_raw[3:5]}-{dt_raw[0:2]}"
                else:
                    dt_iso = dt_raw[:10]
                if comp_filtro and not dt_iso.startswith(comp_filtro):
                    continue
                for tm in parts[2:]:
                    if _re.match(r"^\d{2}:\d{2}$", tm[:5]):
                        punches.setdefault((emp_id, dt_iso), []).append(tm[:5])
            continue

        # 2) AFD Registro tipo 3 (Portaria 1.510 ou Portaria 671)
        if len(line) >= 33 and line[:9].isdigit() and line[9] == "3":
            if len(line) >= 45 and line[14:15] == "-" and line[20:21] == "T":
                # Portaria 671: NSR(9) + '3' + YYYY-MM-DDTHH:MM:SS-HHMM(24) + CPF(12)
                dt_iso = line[10:20]
                hhmm = line[21:26]
                doc = line[34:46]
            elif line[10:22].isdigit():
                # Portaria 1.510: NSR(9) + '3' + DDMMAAAA(8) + HHMM(4) + PIS(12)
                d8 = line[10:18]
                dt_iso = f"{d8[4:8]}-{d8[2:4]}-{d8[0:2]}"
                hhmm = f"{line[18:20]}:{line[20:22]}"
                doc = line[22:34]
            else:
                continue
            if comp_filtro and not dt_iso.startswith(comp_filtro):
                continue
            emp_id = _find_emp(doc)
            if not emp_id:
                nao_encontrados.add(doc.strip())
                continue
            punches.setdefault((emp_id, dt_iso), []).append(hhmm)

    punches = _agrupar_plantoes_noturnos(conn, company_id, punches)

    importados = 0
    he_total = 0.0
    funcs = set()
    for (emp_id, dt_iso), horas_list in sorted(punches.items()):
        p = [h.lstrip("+") for h in sorted(horas_list, key=lambda h: (h.startswith("+"), h))]  # "+HH:MM" = dia seguinte
        if len(p) >= 4:
            entrada, saida_alm, ret_alm, saida = p[0], p[1], p[2], p[-1]
        elif len(p) >= 2:
            entrada, saida_alm, ret_alm, saida = p[0], "", "", p[-1]
        else:
            entrada, saida_alm, ret_alm, saida = p[0], "", "", ""

        horas_trab = _calc_horas(entrada, saida_alm, ret_alm, saida) if (entrada and saida) else 0.0
        prevista, escala_emp, _esc = escalas.jornada_prevista(conn, company_id, emp_id, dt_iso)
        if escala_emp:
            meta = prevista
        else:
            try:
                is_dsr = date.fromisoformat(dt_iso).weekday() == 6 or dt_iso in feriados
            except ValueError:
                is_dsr = False
            meta = 0.0 if is_dsr else horas_dia
        horas_extras = round(max(0.0, horas_trab - meta), 2) if (entrada and saida) else 0.0
        horas_falt = round(max(0.0, meta - horas_trab), 2) if (meta > 0 and entrada and saida) else 0.0

        existing = conn.execute(
            "SELECT id FROM time_records WHERE employee_id=? AND data=? AND company_id=?",
            (emp_id, dt_iso, company_id),
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE time_records SET entrada=?, saida_almoco=?, retorno_almoco=?, saida=?,
                    horas_trabalhadas=?, horas_extras=?, horas_faltantes=?, tipo_ocorrencia='normal',
                    justificativa='Importado via AFD'
                WHERE id=?""",
                (entrada, saida_alm, ret_alm, saida, horas_trab, horas_extras, horas_falt, existing["id"]),
            )
        else:
            conn.execute("""
                INSERT INTO time_records
                    (company_id, employee_id, data, entrada, saida_almoco, retorno_almoco, saida,
                     horas_trabalhadas, horas_extras, horas_faltantes, tipo_ocorrencia, justificativa)
                VALUES (?,?,?,?,?,?,?,?,?,?,'normal','Importado via AFD')""",
                (company_id, emp_id, dt_iso, entrada, saida_alm, ret_alm, saida,
                 horas_trab, horas_extras, horas_falt),
            )
        importados += 1
        he_total += horas_extras
        funcs.add(emp_id)

    conn.commit()
    conn.close()
    return {
        "ok": True,
        "registros_importados": importados,
        "funcionarios_identificados": len(funcs),
        "horas_extras_totais": round(he_total, 2),
        "nao_identificados": sorted(nao_encontrados),
    }


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


# ─── TABELAS FISCAIS ──────────────────────────────────────────────────────────

def _somente_superadmin(user: Dict[str, Any]) -> None:
    """Tabelas legais (INSS, IRRF, FGTS, salário mínimo) são mantidas pelo dono do sistema."""
    if not user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="As tabelas legais são atualizadas pelo administrador do sistema. "
                                                    "Abra uma solicitação de suporte se precisar de alteração.")


def _pode_editar_rubricas(user: Dict[str, Any]) -> None:
    if not user.get("is_superadmin") and (user.get("role") or "") not in ("admin", "dp"):
        raise HTTPException(status_code=403, detail="Apenas administrador ou Depto. Pessoal podem alterar rubricas.")


def _rubrica_global(conn, rubric_id: int, company_id: int, user: Dict[str, Any]) -> None:
    """Rubricas publicadas pelo dono do sistema (origem 'global') só ele altera ou exclui."""
    if user.get("is_superadmin"):
        return
    row = conn.execute("SELECT origem FROM payroll_rubrics WHERE id=? AND company_id=?",
                       (rubric_id, company_id)).fetchone()
    if row and (dict(row).get("origem") or "") == "global":
        conn.close()
        raise HTTPException(status_code=403, detail="Rubrica padrão do sistema: só o administrador do sistema pode alterá-la. "
                                                    "Crie uma rubrica própria com outro código, se precisar.")

@router.get("/tax-tables")
def list_tax_tables(ano: Optional[int] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    where = "company_id IN (0, ?)"
    params: List[Any] = [company_id]
    if ano:
        where += " AND ano = ?"
        params.append(ano)
    tables = rows_to_dicts(conn.execute(
        f"SELECT * FROM tax_tables WHERE {where} ORDER BY ano DESC, tipo, CASE WHEN company_id = 0 THEN 0 ELSE 1 END",
        params).fetchall())
    for t in tables:
        t["global"] = int(t.get("company_id") or 0) == 0
    for t in tables:
        t["brackets"] = rows_to_dicts(conn.execute("SELECT * FROM tax_brackets WHERE tax_table_id = ? ORDER BY faixa_de", (t["id"],)).fetchall())
    conn.close()
    return tables


@router.get("/tax-tables/vigente/{ano}")
def tax_tables_vigente(ano: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM tax_tables WHERE company_id IN (0, ?) AND ano<=? "
        "ORDER BY ano DESC, CASE WHEN company_id = 0 THEN 0 ELSE 1 END",
        (company_id, ano)
    ).fetchall())
    seen: Dict[str, bool] = {}
    result = []
    for t in rows:
        if t["tipo"] not in seen:
            seen[t["tipo"]] = True
            t["brackets"] = rows_to_dicts(conn.execute("SELECT * FROM tax_brackets WHERE tax_table_id=? ORDER BY faixa_de", (t["id"],)).fetchall())
            result.append(t)
    conn.close()
    return result


@router.post("/tax-tables/seed-default", status_code=201)
def seed_default_tax_tables(
    ano: Optional[int] = None,
    force: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Importa as tabelas legais do ano. force=true substitui as já cadastradas."""
    _somente_superadmin(current_user)
    ano = ano or date.today().year
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    existentes = rows_to_dicts(cur.execute(
        "SELECT id FROM tax_tables WHERE company_id=? AND ano=?", (company_id, ano)).fetchall())
    if existentes and not force:
        conn.close()
        return {"ok": True, "msg": f"Tabelas {ano} já existem para esta empresa."}
    for t in existentes:
        cur.execute("DELETE FROM tax_brackets WHERE tax_table_id=?", (t["id"],))
        cur.execute("DELETE FROM tax_tables WHERE id=?", (t["id"],))
    for tipo, brackets in default_seed(ano).items():
        cur.execute("INSERT INTO tax_tables (company_id, ano, tipo) VALUES (?,?,?)", (company_id, ano, tipo))
        table_id = cur.lastrowid
        for b in brackets:
            cur.execute("INSERT INTO tax_brackets (tax_table_id, faixa_de, faixa_ate, aliquota, deducao) VALUES (?,?,?,?,?)",
                        (table_id, b[0], b[1], b[2], b[3]))
    conn.commit()
    conn.close()
    return {"ok": True, "msg": f"Tabelas {ano} {'substituídas' if existentes else 'criadas'} com sucesso."}


@router.post("/tax-tables", status_code=201)
def create_tax_table(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    _somente_superadmin(current_user)
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("INSERT INTO tax_tables (company_id, ano, tipo) VALUES (?,?,?)",
                (company_id, data["ano"], data["tipo"]))
    table_id = cur.lastrowid
    for b in data.get("brackets", []):
        cur.execute("INSERT INTO tax_brackets (tax_table_id, faixa_de, faixa_ate, aliquota, deducao) VALUES (?,?,?,?,?)",
                    (table_id, b["faixa_de"], b.get("faixa_ate"), b["aliquota"], b.get("deducao", 0)))
    conn.commit()
    conn.close()
    return {"id": table_id, "ok": True}


@router.put("/tax-tables/{table_id}")
def update_tax_table(table_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    _somente_superadmin(current_user)
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if not conn.execute("SELECT 1 FROM tax_tables WHERE id=? AND company_id=?", (table_id, company_id)).fetchone():
        conn.close()
        raise HTTPException(404, "Tabela não encontrada.")
    conn.execute("DELETE FROM tax_brackets WHERE tax_table_id=?", (table_id,))
    for b in data.get("brackets", []):
        conn.execute("INSERT INTO tax_brackets (tax_table_id, faixa_de, faixa_ate, aliquota, deducao) VALUES (?,?,?,?,?)",
                     (table_id, b["faixa_de"], b.get("faixa_ate"), b["aliquota"], b.get("deducao", 0)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/tax-tables/{table_id}")
def delete_tax_table(table_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    _somente_superadmin(current_user)
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM tax_tables WHERE id=? AND company_id=?", (table_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── RUBRICAS ─────────────────────────────────────────────────────────────────

def _insert_default_rubrics_dp(conn, company_id: int):
    rubrics = [
        ("0001","Salário Base","provento",1,1,1,1,1,"1000"),
        ("0002","Hora Extra 50%","provento",1,1,1,1,1,"1010"),
        ("0003","Hora Extra 100%","provento",1,1,1,1,1,"1010"),
        ("0004","Adicional Noturno","provento",1,1,1,1,1,"1020"),
        ("0005","Adicional de Insalubridade","provento",1,1,1,1,1,"1070"),
        ("0006","Adicional de Periculosidade","provento",1,1,1,1,1,"1080"),
        ("0007","Comissão","provento",1,1,1,1,1,"1030"),
        ("0008","Férias Gozadas","provento",1,1,1,0,0,"2000"),
        ("0009","1/3 Constitucional Férias","provento",1,1,1,0,0,"2010"),
        ("0010","13º Salário","provento",1,1,1,0,0,"3000"),
        ("0100","INSS Empregado","desconto",0,0,0,0,0,"9220"),
        ("0101","IRRF","desconto",0,0,0,0,0,"9230"),
        ("0102","Vale Transporte","desconto",0,0,0,0,0,"9999"),
        ("0103","Vale Alimentação","desconto",0,0,0,0,0,"9999"),
        ("0104","Pensão Alimentícia","desconto",0,0,0,0,0,"9999"),
        ("0105","Adiantamento de Salário","desconto",0,0,0,0,0,"9999"),
        ("0200","FGTS (informativo)","informativo",0,0,0,0,0,"9000"),
        ("0201","Base de Cálculo INSS","informativo",0,0,0,0,0,"9100"),
        ("0202","Base de Cálculo IRRF","informativo",0,0,0,0,0,"9110"),
        ("0203","Base de Cálculo FGTS","informativo",0,0,0,0,0,"9120"),
    ]
    for r in rubrics:
        conn.execute("""INSERT INTO payroll_rubrics (company_id,codigo,nome,tipo,incide_inss,incide_irrf,incide_fgts,incide_13,incide_ferias,esocial_nat_rubrica,ativo)
                        VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
                     (company_id, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))


@router.get("/rubrics")
def list_rubrics(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("SELECT * FROM payroll_rubrics WHERE company_id=? ORDER BY codigo", (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/rubrics/seed-default", status_code=201)
def seed_default_rubrics(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    count = conn.execute("SELECT COUNT(*) FROM payroll_rubrics WHERE company_id=?", (company_id,)).fetchone()[0]
    if count > 0:
        conn.close()
        return {"ok": True, "message": "Rubricas já cadastradas."}
    _insert_default_rubrics_dp(conn, company_id)
    conn.commit()
    conn.close()
    return {"ok": True, "created": True}


@router.post("/rubrics", status_code=201)
def create_rubric(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    _pode_editar_rubricas(current_user)
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    try:
        formula = _check_formula(data.get("formula"))
    except HTTPException:
        conn.close()
        raise
    if conn.execute("SELECT 1 FROM payroll_rubrics WHERE company_id=? AND codigo=?", (company_id, data["codigo"])).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Já existe uma rubrica com o código {data['codigo']}.")
    cur.execute("""INSERT INTO payroll_rubrics (company_id,codigo,nome,tipo,natureza,incide_inss,incide_irrf,incide_fgts,incide_13,incide_ferias,esocial_cod_rubrica,esocial_nat_rubrica,formula,aplica_todos,ativo)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (company_id, data["codigo"], data["nome"], data.get("tipo","provento"), data.get("natureza","normal"),
                 int(data.get("incide_inss",1)), int(data.get("incide_irrf",1)), int(data.get("incide_fgts",1)),
                 int(data.get("incide_13",1)), int(data.get("incide_ferias",1)),
                 data.get("esocial_cod_rubrica",""), data.get("esocial_nat_rubrica","1000"),
                 formula, int(bool(data.get("aplica_todos", 0)))))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "ok": True}


@router.put("/rubrics/{rubric_id}")
def update_rubric(rubric_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    _pode_editar_rubricas(current_user)
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _rubrica_global(conn, rubric_id, company_id, current_user)
    fields = []
    vals: List[Any] = []
    if "formula" in data:
        try:
            data["formula"] = _check_formula(data.get("formula"))
        except HTTPException:
            conn.close()
            raise
    for f in ["codigo","nome","tipo","natureza","incide_inss","incide_irrf","incide_fgts","incide_13","incide_ferias","esocial_cod_rubrica","esocial_nat_rubrica","ativo","formula","aplica_todos"]:
        if f in data:
            fields.append(f"{f}=?")
            vals.append(int(data[f]) if f.startswith("incide") or f in ("ativo","aplica_todos") else data[f])
    if fields:
        vals += [rubric_id, company_id]
        conn.execute(f"UPDATE payroll_rubrics SET {','.join(fields)} WHERE id=? AND company_id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/rubrics/{rubric_id}")
def delete_rubric(rubric_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    _pode_editar_rubricas(current_user)
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _rubrica_global(conn, rubric_id, company_id, current_user)
    em_uso = conn.execute("SELECT COUNT(*) FROM employee_rubrics WHERE rubric_id=? AND company_id=?",
                          (rubric_id, company_id)).fetchone()[0]
    if em_uso:
        conn.close()
        raise HTTPException(status_code=400,
                            detail=f"Rubrica com {em_uso} lançamento(s) de funcionário. Exclua os lançamentos antes.")
    conn.execute("DELETE FROM payroll_rubrics WHERE id=? AND company_id=?", (rubric_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/esocial/s1010")
def gerar_s1010_rubrics(ano: int = 2025, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rubrics = rows_to_dicts(conn.execute("SELECT * FROM payroll_rubrics WHERE company_id=? AND ativo=1 ORDER BY codigo", (company_id,)).fetchall())
    company = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    if not company:
        raise HTTPException(404, "Empresa não encontrada.")
    company = dict(company)
    cnpj = (company.get("cnpj") or "").replace(".", "").replace("/", "").replace("-", "")
    cnpj8 = cnpj[:8]
    per_apur = f"{ano}-01"
    tipo_map = {"provento": "1", "desconto": "3", "informativo": "4", "reserva": "5"}
    linhas = []
    for r in rubrics:
        linhas.append(f"""    <infoRubrica>
      <inclusao>
        <ideRubrica><codRubr>{r['codigo']}</codRubr><ideTabRubr>{company_id}</ideTabRubr><iniValid>{per_apur}</iniValid></ideRubrica>
        <dadosRubrica>
          <dscRubr>{r['nome']}</dscRubr>
          <natRubr>{r['esocial_nat_rubrica']}</natRubr>
          <tpRubr>{tipo_map.get(r['tipo'],'1')}</tpRubr>
          <codIncCP>{'1' if r['incide_inss'] else '0'}</codIncCP>
          <codIncIRRF>{'1' if r['incide_irrf'] else '0'}</codIncIRRF>
          <codIncFGTS>{'1' if r['incide_fgts'] else '0'}</codIncFGTS>
        </dadosRubrica>
      </inclusao>
    </infoRubrica>""")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtTabRubrica/v02_05_00">
  <evtTabRubrica Id="ID1{cnpj8}{per_apur.replace('-','')}">
    <ideEvento>
      <nrRec/><indRetif>1</indRetif><perApur>{per_apur}</perApur>
      <tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc>
    </ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj8}</nrInsc></ideEmpregador>
{chr(10).join(linhas)}
  </evtTabRubrica>
</eSocial>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1010-{ano}.xml"'})


# ─── ESOCIAL PERIÓDICO ────────────────────────────────────────────────────────

@router.get("/payroll/items")
def list_payroll_items_by_comp(competencia: str = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name as employee_name, e.cpf, e.pis_pasep, e.cbo
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id=pi.run_id
        JOIN employees e ON e.id=pi.employee_id
        WHERE pr.company_id=? AND pr.competence=?
        ORDER BY e.name
    """, (company_id, competencia)).fetchall())
    conn.close()
    return items


@router.get("/esocial/s1200/{competencia}/todos")
def gerar_s1200_todos(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name, e.cpf, e.pis_pasep, e.cbo
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id=pi.run_id
        JOIN employees e ON e.id=pi.employee_id
        WHERE pr.company_id=? AND pr.competence=? AND COALESCE(pr.tipo, 'mensal')='mensal'
    """, (company_id, competencia)).fetchall())
    if not items:
        conn.close()
        raise HTTPException(404, "Nenhum item de folha encontrado para esta competência.")
    all_lines = rows_to_dicts(conn.execute("""
        SELECT l.* FROM payroll_item_lines l
        JOIN payroll_runs pr ON pr.id = l.run_id
        WHERE pr.company_id=? AND pr.competence=? AND COALESCE(pr.tipo, 'mensal')='mensal'
        ORDER BY l.item_id, l.tipo DESC, l.codigo, l.id
    """, (company_id, competencia)).fetchall())
    conn.close()
    lines_by_item: Dict[int, List[Dict[str, Any]]] = {}
    for ln in all_lines:
        lines_by_item.setdefault(ln["item_id"], []).append(ln)
    xmls = []
    for it in items:
        verbas = _build_det_verbas(lines_by_item.get(it["id"], []), str(company_id))
        if not verbas:
            verbas = f"""          <detVerbas><codRubr>0001</codRubr><ideTabRubr>{company_id}</ideTabRubr><qtdRubr>1</qtdRubr><vrRubr>{float(it.get('gross_salary',0)):.2f}</vrRubr></detVerbas>
          <detVerbas><codRubr>0100</codRubr><ideTabRubr>{company_id}</ideTabRubr><qtdRubr>1</qtdRubr><vrRubr>{float(it.get('inss',0)):.2f}</vrRubr></detVerbas>
          <detVerbas><codRubr>0101</codRubr><ideTabRubr>{company_id}</ideTabRubr><qtdRubr>1</qtdRubr><vrRubr>{float(it.get('irrf',0)):.2f}</vrRubr></detVerbas>"""
        xmls.append(f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v02_01_00">
  <evtRemun Id="ID1{cnpj[:8]}{competencia.replace('-','')}E{it.get('employee_id',0)}">
    <ideEvento><indRetif>1</indRetif><nrRec/><perApur>{competencia}</perApur><indGuia>1</indGuia><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEmpregador>
    <ideTrab><cpfTrab>{it.get('cpf','')}</cpfTrab><nisTrab>{it.get('pis_pasep','')}</nisTrab><codCateg>101</codCateg></ideTrab>
    <dmDev><codDmDev>1</codDmDev><indRRA>N</indRRA>
      <infoPerApur><ideEstabLot><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc><codLotacao>1</codLotacao>
{verbas}
      </ideEstabLot></infoPerApur>
      <infoComplCont><codCBO>{it.get('cbo','111105')}</codCBO><natAtividade>1</natAtividade><qtdDiasAv>30</qtdDiasAv></infoComplCont>
    </dmDev>
  </evtRemun>
</eSocial>""")
    combined = "\n<!-- === PRÓXIMO EVENTO === -->\n".join(xmls)
    return Response(content=combined, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1200-{competencia}-todos.xml"'})


@router.get("/esocial/s1200/{competencia}/{emp_id}")
def gerar_s1200_emp(competencia: str, emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    it = conn.execute("""
        SELECT pi.*, e.name, e.cpf, e.pis_pasep, e.cbo
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id=pi.run_id
        JOIN employees e ON e.id=pi.employee_id
        WHERE pr.company_id=? AND pr.competence=? AND COALESCE(pr.tipo, 'mensal')='mensal' AND pi.employee_id=?
    """, (company_id, competencia, emp_id)).fetchone()
    if not it:
        conn.close()
        raise HTTPException(404, "Item não encontrado.")
    it = dict(it)
    lines = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_item_lines WHERE item_id = ? ORDER BY tipo DESC, codigo, id",
        (it["id"],),
    ).fetchall())
    conn.close()
    verbas = _build_det_verbas(lines, str(company_id))
    if not verbas:
        verbas = f"""          <detVerbas><codRubr>0001</codRubr><ideTabRubr>{company_id}</ideTabRubr><qtdRubr>1</qtdRubr><vrRubr>{float(it.get('gross_salary',0)):.2f}</vrRubr></detVerbas>
          <detVerbas><codRubr>0100</codRubr><ideTabRubr>{company_id}</ideTabRubr><qtdRubr>1</qtdRubr><vrRubr>{float(it.get('inss',0)):.2f}</vrRubr></detVerbas>
          <detVerbas><codRubr>0101</codRubr><ideTabRubr>{company_id}</ideTabRubr><qtdRubr>1</qtdRubr><vrRubr>{float(it.get('irrf',0)):.2f}</vrRubr></detVerbas>"""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v02_01_00">
  <evtRemun Id="ID1{cnpj[:8]}{competencia.replace('-','')}E{emp_id}">
    <ideEvento><indRetif>1</indRetif><nrRec/><perApur>{competencia}</perApur><indGuia>1</indGuia><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEmpregador>
    <ideTrab><cpfTrab>{it.get('cpf','')}</cpfTrab><nisTrab>{it.get('pis_pasep','')}</nisTrab><codCateg>101</codCateg></ideTrab>
    <dmDev><codDmDev>1</codDmDev><indRRA>N</indRRA>
      <infoPerApur><ideEstabLot><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc><codLotacao>1</codLotacao>
{verbas}
      </ideEstabLot></infoPerApur>
      <infoComplCont><codCBO>{it.get('cbo','111105')}</codCBO><natAtividade>1</natAtividade><qtdDiasAv>30</qtdDiasAv></infoComplCont>
    </dmDev>
  </evtRemun>
</eSocial>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1200-{competencia}-E{emp_id}.xml"'})


@router.get("/esocial/s1299/{competencia}")
def gerar_s1299(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtFechamento/v01_01_00">
  <evtFechamento Id="ID1{cnpj[:8]}{competencia.replace('-','')}FEC">
    <ideEvento><indRetif>1</indRetif><nrRec/><perApur>{competencia}</perApur><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEmpregador>
    <infoFechamento><situFolha>1</situFolha><compSemMovto>N</compSemMovto></infoFechamento>
  </evtFechamento>
</eSocial>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1299-{competencia}.xml"'})


@router.post("/esocial/periodic/mark-sent")
def mark_esocial_sent(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    competencia = data["competencia"]
    evento = data["evento"]
    nr_rec = data.get("nr_rec", "")
    existing = conn.execute(
        "SELECT id FROM esocial_periodic_events WHERE company_id=? AND competencia=? AND evento=? AND employee_id IS NULL",
        (company_id, competencia, evento)
    ).fetchone()
    if existing:
        conn.execute("UPDATE esocial_periodic_events SET status='transmitido', nr_rec=? WHERE id=?", (nr_rec, existing["id"]))
    else:
        conn.execute("""INSERT INTO esocial_periodic_events (company_id,competencia,evento,status,nr_rec)
                        VALUES (?,?,?,'transmitido',?)""", (company_id, competencia, evento, nr_rec))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/esocial/periodic/status")
def esocial_periodic_status(competencia: str = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM esocial_periodic_events WHERE company_id=? AND competencia=?",
        (company_id, competencia)
    ).fetchall())
    conn.close()
    return rows


# ─── SEFIP/GFIP ──────────────────────────────────────────────────────────────

@router.get("/sefip/{competencia}")
def calcular_sefip(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name, e.cpf, e.pis_pasep, e.admission_date, e.birth_date
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id=pi.run_id
        JOIN employees e ON e.id=pi.employee_id
        WHERE pr.company_id=? AND pr.competence=? AND COALESCE(pr.tipo, 'mensal')='mensal'
    """, (company_id, competencia)).fetchall())
    conn.close()
    total_trab = len(items)
    total_rem = sum(float(i.get("gross_salary") or 0) for i in items)
    total_fgts = sum(float(i.get("fgts") or 0) for i in items) or round(total_rem * 0.08, 2)
    total_inss_emp = sum(float(i.get("inss") or 0) for i in items)
    patronal = round(total_rem * 0.20, 2)
    rat = round(total_rem * 0.03, 2)
    terceiros = round(total_rem * 0.058, 2)
    total_gps = round(total_inss_emp + patronal + rat + terceiros, 2)
    return {
        "competencia": competencia,
        "total_trabalhadores": total_trab,
        "total_remuneracao": round(total_rem, 2),
        "total_fgts": total_fgts,
        "total_inss_emp": total_inss_emp,
        "total_inss_patronal": patronal,
        "total_rat": rat,
        "total_terceiros": terceiros,
        "total_gps": total_gps,
        "fpas": "515",
        "cod_terceiros": "0001",
        "funcionarios": items,
    }


@router.get("/sefip/{competencia}/arquivo")
def sefip_arquivo(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name, e.cpf, e.pis_pasep, e.admission_date, e.birth_date
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id=pi.run_id
        JOIN employees e ON e.id=pi.employee_id
        WHERE pr.company_id=? AND pr.competence=? AND COALESCE(pr.tipo, 'mensal')='mensal'
    """, (company_id, competencia)).fetchall())
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    comp_fmt = competencia[5:7] + competencia[:4]
    lines = []
    total_rem = 0.0
    total_fgts_sum = 0.0
    total_inss_emp = 0.0
    lines.append(f"00{cnpj:<14}0{comp_fmt}515000115")
    for it in items:
        cpf = (it.get("cpf") or "").replace(".","").replace("-","")
        pis = (it.get("pis_pasep") or "").replace(".","").replace("-","")
        nome = (it.get("name") or "")[:40].ljust(40)
        adm = (it.get("admission_date") or "").replace("-","")
        nasc = (it.get("birth_date") or "").replace("-","")
        rem = float(it.get("gross_salary") or 0)
        fgts = float(it.get("fgts") or 0) or round(rem * 0.08, 2)
        inss = float(it.get("inss") or 0)
        total_rem += rem
        total_fgts_sum += fgts
        total_inss_emp += inss
        lines.append(f"10{cpf:<11}{pis:<11}{nome}01{adm:<8}{nasc:<8}{rem:013.2f}{fgts:013.2f}")
    patronal = round(total_rem * 0.20, 2)
    rat = round(total_rem * 0.03, 2)
    terceiros = round(total_rem * 0.058, 2)
    lines.append(f"90{len(items):05d}{total_rem:015.2f}{total_fgts_sum:015.2f}{total_inss_emp:015.2f}{patronal:015.2f}{rat:015.2f}{terceiros:015.2f}")
    content = "\r\n".join(lines) + "\r\n"
    return Response(content=content, media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="SEFIP-{competencia}.txt"'})


# FGTS Digital: não existe arquivo de envio — o FGTS Digital apura a guia a partir dos eventos do eSocial.
# A conferência da guia fica em GET /api/esocial/fgts/{competencia}.


# ─── EFD-REINF ───────────────────────────────────────────────────────────────

@router.get("/reinf/tomadores")
def list_reinf_tomadores(competencia: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    where = "company_id=?"
    params: List[Any] = [company_id]
    if competencia:
        where += " AND competencia=?"
        params.append(competencia)
    rows = rows_to_dicts(conn.execute(f"SELECT * FROM reinf_service_takers WHERE {where} ORDER BY razao_social", params).fetchall())
    conn.close()
    return rows


@router.post("/reinf/tomadores", status_code=201)
def create_reinf_tomador(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO reinf_service_takers (company_id,tipo_insc,nr_insc,razao_social,tipo_servico,valor_bruto,valor_bc_ret,valor_irrf,valor_csll,valor_pis,valor_cofins,competencia)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (company_id, data.get("tipo_insc","cnpj"), data["nr_insc"], data["razao_social"],
                 data.get("tipo_servico","0001"), float(data.get("valor_bruto",0)), float(data.get("valor_bc_ret",0)),
                 float(data.get("valor_irrf",0)), float(data.get("valor_csll",0)),
                 float(data.get("valor_pis",0)), float(data.get("valor_cofins",0)), data["competencia"]))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "ok": True}


@router.put("/reinf/tomadores/{tom_id}")
def update_reinf_tomador(tom_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    fields = []
    vals: List[Any] = []
    for f in ["tipo_insc","nr_insc","razao_social","tipo_servico","valor_bruto","valor_bc_ret","valor_irrf","valor_csll","valor_pis","valor_cofins","competencia"]:
        if f in data:
            fields.append(f"{f}=?")
            vals.append(data[f])
    if fields:
        vals += [tom_id, company_id]
        conn.execute(f"UPDATE reinf_service_takers SET {','.join(fields)} WHERE id=? AND company_id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/reinf/tomadores/{tom_id}")
def delete_reinf_tomador(tom_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM reinf_service_takers WHERE id=? AND company_id=?", (tom_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/reinf/r1000")
def gerar_r1000(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    per = date.today().strftime("%Y-%m")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schemas/evtInfoContribuinte/v2_01_01">
  <evtInfoContri Id="R{cnpj}{per.replace('-','')}">
    <ideEvento><indRetif>1</indRetif><perApur>{per}</perApur><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideContri><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideContri>
    <infoContri>
      <inclusao>
        <idePeriodo><iniValid>{per}</iniValid></idePeriodo>
        <infoCadastro>
          <classTrib>01</classTrib><indEscrituracao>1</indEscrituracao>
          <indDesoneracao>N</indDesoneracao><indAcordoIsenIsento>N</indAcordoIsenIsento>
          <contato>
            <nmCtt>{company.get('razao_social','Empresa')}</nmCtt>
            <cpfCtt>00000000000</cpfCtt>
            <fone>{company.get('telefone','')}</fone>
            <email>{company.get('email','')}</email>
          </contato>
        </infoCadastro>
      </inclusao>
    </infoContri>
  </evtInfoContri>
</Reinf>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": 'attachment; filename="R-1000.xml"'})


@router.get("/reinf/r2010/{competencia}")
def gerar_r2010(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    takers = rows_to_dicts(conn.execute(
        "SELECT * FROM reinf_service_takers WHERE company_id=? AND competencia=? ORDER BY razao_social",
        (company_id, competencia)
    ).fetchall())
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    estabs = []
    for t in takers:
        nr = t["nr_insc"].replace(".","").replace("/","").replace("-","")
        estabs.append(f"""    <ideEstabObra>
      <tpInscEstab>1</tpInscEstab><nrInscEstab>{nr}</nrInscEstab>
      <infoServ><tpSrv>{t['tipo_servico']}</tpSrv>
        <vlrServContratado>{float(t.get('valor_bruto',0)):.2f}</vlrServContratado>
        <vlrServPrestado>{float(t.get('valor_bruto',0)):.2f}</vlrServPrestado>
        <vlrBC>{float(t.get('valor_bc_ret',0)):.2f}</vlrBC>
        <vlrRetencao>{float(t.get('valor_irrf',0)):.2f}</vlrRetencao>
      </infoServ>
    </ideEstabObra>""")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schemas/evtServTom/v2_01_01">
  <evtServTom Id="R{cnpj}{competencia.replace('-','')}2010">
    <ideEvento><indRetif>1</indRetif><perApur>{competencia}</perApur><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideContri><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideContri>
    <infoServ><evtServTomado>
{chr(10).join(estabs) if estabs else '      <!-- Sem tomadores neste período -->'}
    </evtServTomado></infoServ>
  </evtServTom>
</Reinf>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="R-2010-{competencia}.xml"'})


@router.get("/reinf/r4010/{competencia}")
def gerar_r4010(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    items = rows_to_dicts(conn.execute("""
        SELECT pi.*, e.name, e.cpf
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id=pi.run_id
        JOIN employees e ON e.id=pi.employee_id
        WHERE pr.company_id=? AND pr.competence=? AND pi.irrf > 0
    """, (company_id, competencia)).fetchall())
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    last_day = _calendar.monthrange(ano, mes)[1]
    dt_fg = f"{ano}-{mes:02d}-{last_day:02d}"
    benefs = []
    for it in items:
        cpf = (it.get("cpf") or "").replace(".","").replace("-","")
        benefs.append(f"""      <ideEstab><tpInscEstab>1</tpInscEstab><nrInscEstab>{cnpj}</nrInscEstab>
        <ideBenef>
          <cpfBenef>{cpf}</cpfBenef><nmBenef>{it.get('name','')}</nmBenef>
          <infoPgto>
            <dtFG>{dt_fg}</dtFG><tpPgto>11</tpPgto>
            <vlrRendBruto>{float(it.get('gross_salary',0)):.2f}</vlrRendBruto>
            <vlrRendTrib>{float(it.get('gross_salary',0)):.2f}</vlrRendTrib>
            <vlrIR>{float(it.get('irrf',0)):.2f}</vlrIR><indRRA>N</indRRA>
          </infoPgto>
        </ideBenef>
      </ideEstab>""")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schemas/evtRetPF/v2_01_01">
  <evtRetPF Id="R{cnpj}{competencia.replace('-','')}4010">
    <ideEvento><indRetif>1</indRetif><perApur>{competencia}</perApur><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideContri><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideContri>
    <evtPgto>
{chr(10).join(benefs) if benefs else '      <!-- Sem pagamentos com retenção neste período -->'}
    </evtPgto>
  </evtRetPF>
</Reinf>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="R-4010-{competencia}.xml"'})


@router.get("/reinf/r4020/{competencia}")
def gerar_r4020(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    takers = rows_to_dicts(conn.execute(
        "SELECT * FROM reinf_service_takers WHERE company_id=? AND competencia=? AND tipo_insc='cnpj'",
        (company_id, competencia)
    ).fetchall())
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    last_day = _calendar.monthrange(ano, mes)[1]
    dt_fg = f"{ano}-{mes:02d}-{last_day:02d}"
    pgtos = []
    for t in takers:
        nr = t["nr_insc"].replace(".","").replace("/","").replace("-","")
        pgtos.append(f"""      <ideEstab><tpInscEstab>1</tpInscEstab><nrInscEstab>{cnpj}</nrInscEstab>
        <ideBenef>
          <cnpjBenef>{nr}</cnpjBenef><nmBenef>{t['razao_social']}</nmBenef>
          <infoPgto>
            <dtFG>{dt_fg}</dtFG><tpPgto>12</tpPgto>
            <vlrRendBruto>{float(t.get('valor_bruto',0)):.2f}</vlrRendBruto>
            <vlrRendTrib>{float(t.get('valor_bc_ret',0)):.2f}</vlrRendTrib>
            <vlrIR>{float(t.get('valor_irrf',0)):.2f}</vlrIR>
            <vlrCSLL>{float(t.get('valor_csll',0)):.2f}</vlrCSLL>
            <vlrPIS>{float(t.get('valor_pis',0)):.2f}</vlrPIS>
            <vlrCOFINS>{float(t.get('valor_cofins',0)):.2f}</vlrCOFINS>
          </infoPgto>
        </ideBenef>
      </ideEstab>""")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schemas/evtRetPJ/v2_01_01">
  <evtRetPJ Id="R{cnpj}{competencia.replace('-','')}4020">
    <ideEvento><indRetif>1</indRetif><perApur>{competencia}</perApur><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideContri><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideContri>
    <evtPgto>
{chr(10).join(pgtos) if pgtos else '      <!-- Sem pagamentos a PJ neste período -->'}
    </evtPgto>
  </evtRetPJ>
</Reinf>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="R-4020-{competencia}.xml"'})


@router.get("/reinf/r4099/{competencia}")
def gerar_r4099(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone() or {})
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schemas/evtFechamento/v2_01_01">
  <evtFech Id="R{cnpj}{competencia.replace('-','')}4099">
    <ideEvento><indRetif>1</indRetif><perApur>{competencia}</perApur><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideContri><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideContri>
    <infoFech>
      <evtR2010>S</evtR2010><evtR4010>S</evtR4010><evtR4020>S</evtR4020>
      <indApuracao>1</indApuracao>
    </infoFech>
  </evtFech>
</Reinf>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="R-4099-{competencia}.xml"'})


# ─── BENEFÍCIOS ───────────────────────────────────────────────────────────────

@router.get("/benefit-types")
def list_benefit_types(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("SELECT * FROM benefit_types WHERE company_id=? ORDER BY nome", (cid,)).fetchall())
    conn.close()
    return rows

@router.post("/benefit-types", status_code=201)
def create_benefit_type(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO benefit_types (company_id,nome,tipo,modalidade_desconto,percentual_desconto,valor_fixo_desconto,limite_pct_salario,ativo)
                   VALUES (?,?,?,?,?,?,?,1)""",
        (cid, data["nome"], data.get("tipo","vale_alimentacao"), data.get("modalidade_desconto","percentual"),
         float(data.get("percentual_desconto",0)), float(data.get("valor_fixo_desconto",0)), float(data.get("limite_pct_salario",0))))
    conn.commit()
    new_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM benefit_types WHERE id=?", (new_id,)).fetchone())
    conn.close()
    return row

@router.put("/benefit-types/{bt_id}")
def update_benefit_type(bt_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("""UPDATE benefit_types SET nome=?,tipo=?,modalidade_desconto=?,percentual_desconto=?,valor_fixo_desconto=?,limite_pct_salario=?,ativo=?
                    WHERE id=? AND company_id=?""",
        (data.get("nome"), data.get("tipo"), data.get("modalidade_desconto"), float(data.get("percentual_desconto",0)),
         float(data.get("valor_fixo_desconto",0)), float(data.get("limite_pct_salario",0)), int(data.get("ativo",1)), bt_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.delete("/benefit-types/{bt_id}")
def delete_benefit_type(bt_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM benefit_types WHERE id=? AND company_id=?", (bt_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.get("/employees/{emp_id}/benefits")
def get_employee_benefits(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT eb.*, bt.nome as benefit_nome, bt.tipo as benefit_tipo
        FROM employee_benefits eb JOIN benefit_types bt ON bt.id=eb.benefit_type_id
        WHERE eb.employee_id=? AND eb.company_id=? ORDER BY eb.created_at DESC
    """, (emp_id, cid)).fetchall())
    conn.close()
    return rows

@router.post("/employees/{emp_id}/benefits", status_code=201)
def add_employee_benefit(emp_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    bt = conn.execute("SELECT * FROM benefit_types WHERE id=? AND company_id=?", (data["benefit_type_id"], cid)).fetchone()
    if not bt:
        conn.close(); raise HTTPException(404, "Tipo de benefício não encontrado.")
    bt = dict(bt)
    emp = conn.execute("SELECT salary FROM employees WHERE id=? AND company_id=?", (emp_id, cid)).fetchone()
    salary = float(emp["salary"]) if emp else 0
    valor_bruto = float(data.get("valor_bruto", 0))
    if bt["modalidade_desconto"] == "percentual":
        desconto = valor_bruto * bt["percentual_desconto"] / 100
        if bt["limite_pct_salario"] > 0:
            desconto = min(desconto, salary * bt["limite_pct_salario"] / 100)
    else:
        desconto = float(bt["valor_fixo_desconto"])
    cur = conn.cursor()
    cur.execute("""INSERT INTO employee_benefits (company_id,employee_id,benefit_type_id,valor_bruto,valor_desconto,data_inicio,data_fim,ativo,observacoes)
                   VALUES (?,?,?,?,?,?,?,1,?)""",
        (cid, emp_id, data["benefit_type_id"], valor_bruto, round(desconto,2),
         data.get("data_inicio",""), data.get("data_fim"), data.get("observacoes","")))
    conn.commit()
    new_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM employee_benefits WHERE id=?", (new_id,)).fetchone())
    conn.close()
    return row

@router.put("/employee-benefits/{eb_id}")
def update_employee_benefit(eb_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("""UPDATE employee_benefits SET valor_bruto=?,valor_desconto=?,data_inicio=?,data_fim=?,ativo=?,observacoes=?
                    WHERE id=? AND company_id=?""",
        (float(data.get("valor_bruto",0)), float(data.get("valor_desconto",0)),
         data.get("data_inicio"), data.get("data_fim"), int(data.get("ativo",1)),
         data.get("observacoes",""), eb_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.delete("/employee-benefits/{eb_id}")
def delete_employee_benefit(eb_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM employee_benefits WHERE id=? AND company_id=?", (eb_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.get("/benefits/summary")
def benefits_summary(competencia: str = Query(None), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT eb.*, e.name as employee_name, bt.nome as benefit_nome, bt.tipo as benefit_tipo
        FROM employee_benefits eb
        JOIN employees e ON e.id=eb.employee_id
        JOIN benefit_types bt ON bt.id=eb.benefit_type_id
        WHERE eb.company_id=? AND eb.ativo=1 ORDER BY e.name
    """, (cid,)).fetchall())
    conn.close()
    return rows


# ─── PARÂMETROS DA FOLHA ──────────────────────────────────────────────────────

@router.get("/parametros")
def get_parametros(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Parâmetros da folha da empresa, com os padrões e a descrição de cada campo."""
    conn = get_conn()
    try:
        return {"parametros": dp_parametros.carregar(conn, current_user.get("company_id", 1)),
                "padrao": dp_parametros.PADRAO, "descricoes": dp_parametros.DESCRICOES}
    finally:
        conn.close()


@router.put("/parametros")
def put_parametros(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    if not current_user.get("is_superadmin") and (current_user.get("role") or "") not in ("admin", "dp"):
        raise HTTPException(status_code=403, detail="Apenas administrador ou Depto. Pessoal podem alterar os parâmetros da folha.")
    conn = get_conn()
    try:
        out = dp_parametros.salvar(conn, current_user.get("company_id", 1), data, current_user.get("email", ""))
        log_audit(conn, action="update", entity="payroll_parametros", entity_id=current_user.get("company_id", 1),
                  new_data=out, user_id=current_user.get("id"), company_id=current_user.get("company_id", 1))
        conn.commit()
        return {"parametros": out}
    except ValueError as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


# ─── ADIANTAMENTOS ────────────────────────────────────────────────────────────

@router.get("/advances")
def list_advances(competencia: str = Query(None), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    if competencia:
        rows = rows_to_dicts(conn.execute("""
            SELECT sa.*, e.name as employee_name, e.salary as employee_salary
            FROM salary_advances sa JOIN employees e ON e.id=sa.employee_id
            WHERE sa.company_id=? AND sa.competencia=? ORDER BY e.name
        """, (cid, competencia)).fetchall())
    else:
        rows = rows_to_dicts(conn.execute("""
            SELECT sa.*, e.name as employee_name, e.salary as employee_salary
            FROM salary_advances sa JOIN employees e ON e.id=sa.employee_id
            WHERE sa.company_id=? ORDER BY sa.competencia DESC, e.name
        """, (cid,)).fetchall())
    conn.close()
    return rows

@router.post("/advances", status_code=201)
def create_advance(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    emp = conn.execute("SELECT salary FROM employees WHERE id=? AND company_id=?", (data["employee_id"], cid)).fetchone()
    if not emp:
        conn.close(); raise HTTPException(404, "Funcionário não encontrado.")
    salary = float(emp["salary"])
    valor = float(data["valor"])
    limite = float(dp_parametros.carregar(conn, cid)["adiantamento_limite"])
    if salary > 0 and valor > salary * limite / 100:
        conn.close()
        raise HTTPException(400, f"Adiantamento não pode exceder {limite:g}% do salário ({salary * limite / 100:.2f}). "
                                 "O limite fica em DP › Parâmetros.")
    cur = conn.cursor()
    cur.execute("""INSERT INTO salary_advances (company_id,employee_id,competencia,valor,tipo,data_pagamento,status,observacoes)
                   VALUES (?,?,?,?,?,?,?,?)""",
        (cid, data["employee_id"], data["competencia"], valor,
         data.get("tipo","quinzenal"), data.get("data_pagamento",""),
         data.get("status","pago"), data.get("observacoes","")))
    conn.commit()
    new_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM salary_advances WHERE id=?", (new_id,)).fetchone())
    conn.close()
    return row

@router.delete("/advances/{adv_id}")
def delete_advance(adv_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM salary_advances WHERE id=? AND company_id=?", (adv_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.get("/advances/employee/{emp_id}")
def advances_by_employee(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM salary_advances WHERE employee_id=? AND company_id=? ORDER BY competencia DESC",
        (emp_id, cid)).fetchall())
    conn.close()
    return rows


# ─── PENSÃO ALIMENTÍCIA ───────────────────────────────────────────────────────

@router.get("/alimony")
def list_alimony(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT ao.*, e.name as employee_name
        FROM alimony_orders ao JOIN employees e ON e.id=ao.employee_id
        WHERE ao.company_id=? ORDER BY e.name
    """, (cid,)).fetchall())
    conn.close()
    return rows

@router.post("/alimony", status_code=201)
def create_alimony(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO alimony_orders
        (company_id,employee_id,processo,beneficiario,cpf_beneficiario,modalidade,percentual,valor_fixo,base_calculo,banco,agencia,conta,data_inicio,data_fim,ativo,observacoes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
        (cid, data["employee_id"], data.get("processo",""), data["beneficiario"],
         data.get("cpf_beneficiario",""), data.get("modalidade","percentual"),
         float(data.get("percentual",0)), float(data.get("valor_fixo",0)),
         data.get("base_calculo","liquido"), data.get("banco",""),
         data.get("agencia",""), data.get("conta",""),
         data.get("data_inicio",""), data.get("data_fim"),
         data.get("observacoes","")))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM alimony_orders WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    return row

@router.put("/alimony/{ao_id}")
def update_alimony(ao_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("""UPDATE alimony_orders SET processo=?,beneficiario=?,cpf_beneficiario=?,modalidade=?,percentual=?,valor_fixo=?,
                    base_calculo=?,banco=?,agencia=?,conta=?,data_inicio=?,data_fim=?,ativo=?,observacoes=?
                    WHERE id=? AND company_id=?""",
        (data.get("processo",""), data.get("beneficiario"), data.get("cpf_beneficiario",""),
         data.get("modalidade"), float(data.get("percentual",0)), float(data.get("valor_fixo",0)),
         data.get("base_calculo"), data.get("banco",""), data.get("agencia",""), data.get("conta",""),
         data.get("data_inicio"), data.get("data_fim"), int(data.get("ativo",1)),
         data.get("observacoes",""), ao_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.delete("/alimony/{ao_id}")
def delete_alimony(ao_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM alimony_orders WHERE id=? AND company_id=?", (ao_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.get("/alimony/employee/{emp_id}")
def alimony_by_employee(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM alimony_orders WHERE employee_id=? AND company_id=? ORDER BY data_inicio DESC",
        (emp_id, cid)).fetchall())
    conn.close()
    return rows

@router.get("/alimony/calculate/{emp_id}")
def calculate_alimony(emp_id: int, competencia: str = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    emp = conn.execute("SELECT name, salary FROM employees WHERE id=? AND company_id=?", (emp_id, cid)).fetchone()
    if not emp:
        conn.close(); raise HTTPException(404, "Funcionário não encontrado.")
    orders = rows_to_dicts(conn.execute(
        "SELECT * FROM alimony_orders WHERE employee_id=? AND company_id=? AND ativo=1", (emp_id, cid)).fetchall())
    # Busca holerite do mês
    pr = conn.execute("""
        SELECT pi.net_salary, pi.inss FROM payroll_runs pr
        JOIN payroll_items pi ON pi.payroll_run_id=pr.id
        WHERE pr.employee_id=? AND pr.company_id=? AND pr.competencia=?
        LIMIT 1
    """, (emp_id, cid, competencia)).fetchone()
    salary = float(emp["salary"])
    liquido = float(pr["net_salary"]) if pr else salary - float(pr["inss"] if pr else 0)
    result = []
    for o in orders:
        base = liquido if o["base_calculo"] == "liquido" else salary
        valor = base * o["percentual"] / 100 if o["modalidade"] == "percentual" else float(o["valor_fixo"])
        result.append({
            "employee_name": emp["name"], "base": round(base, 2),
            "valor_desconto": round(valor, 2), "beneficiario": o["beneficiario"],
            "banco": o["banco"], "agencia": o["agencia"], "conta": o["conta"],
        })
    conn.close()
    return result


# ─── AUTÔNOMOS / RPA ─────────────────────────────────────────────────────────

def _calc_irrf_autonomo(base: float) -> float:
    brackets = [(2824.0,0,0),(3751.05,7.5,211.80),(4664.68,15.0,492.78),(5871.22,22.5,843.34),(float('inf'),27.5,1137.74)]
    for limit, aliq, ded in brackets:
        if base <= limit:
            return round(max(0, base * aliq / 100 - ded), 2)
    return round(max(0, base * 27.5 / 100 - 1137.74), 2)

@router.get("/autonomous")
def list_autonomous(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("SELECT * FROM autonomous_workers WHERE company_id=? ORDER BY nome", (cid,)).fetchall())
    conn.close()
    return rows

@router.post("/autonomous", status_code=201)
def create_autonomous(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO autonomous_workers (company_id,nome,cpf,pis_pasep,cbo,endereco,cidade,uf,cep,banco,agencia,conta,ativo)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
        (cid, data["nome"], data["cpf"], data.get("pis_pasep",""), data.get("cbo","2521-05"),
         data.get("endereco",""), data.get("cidade",""), data.get("uf",""), data.get("cep",""),
         data.get("banco",""), data.get("agencia",""), data.get("conta","")))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM autonomous_workers WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    return row

@router.put("/autonomous/{aw_id}")
def update_autonomous(aw_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("""UPDATE autonomous_workers SET nome=?,cpf=?,pis_pasep=?,cbo=?,endereco=?,cidade=?,uf=?,cep=?,banco=?,agencia=?,conta=?,ativo=?
                    WHERE id=? AND company_id=?""",
        (data.get("nome"), data.get("cpf"), data.get("pis_pasep",""), data.get("cbo",""),
         data.get("endereco",""), data.get("cidade",""), data.get("uf",""), data.get("cep",""),
         data.get("banco",""), data.get("agencia",""), data.get("conta",""), int(data.get("ativo",1)),
         aw_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.delete("/autonomous/{aw_id}")
def delete_autonomous(aw_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM autonomous_workers WHERE id=? AND company_id=?", (aw_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.post("/rpa", status_code=201)
def create_rpa(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    bruto = float(data["valor_bruto"])
    inss = round(min(bruto * 0.11, 897.32), 2)
    base_irrf = bruto - inss
    irrf = _calc_irrf_autonomo(base_irrf)
    iss = float(data.get("iss_retido", 0))
    liquido = round(bruto - inss - irrf - iss, 2)
    cur = conn.cursor()
    cur.execute("""INSERT INTO rpa_payments (company_id,autonomous_id,competencia,data_pagamento,descricao_servico,valor_bruto,inss_retido,irrf_retido,iss_retido,valor_liquido,observacoes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, data["autonomous_id"], data["competencia"], data["data_pagamento"],
         data["descricao_servico"], bruto, inss, irrf, iss, liquido, data.get("observacoes","")))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM rpa_payments WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    return row

@router.get("/rpa")
def list_rpa(competencia: str = Query(None), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    if competencia:
        rows = rows_to_dicts(conn.execute("""
            SELECT rp.*, aw.nome, aw.cpf FROM rpa_payments rp JOIN autonomous_workers aw ON aw.id=rp.autonomous_id
            WHERE rp.company_id=? AND rp.competencia=? ORDER BY rp.data_pagamento DESC
        """, (cid, competencia)).fetchall())
    else:
        rows = rows_to_dicts(conn.execute("""
            SELECT rp.*, aw.nome, aw.cpf FROM rpa_payments rp JOIN autonomous_workers aw ON aw.id=rp.autonomous_id
            WHERE rp.company_id=? ORDER BY rp.competencia DESC, rp.data_pagamento DESC
        """, (cid,)).fetchall())
    conn.close()
    return rows

@router.get("/rpa/{rpa_id}")
def get_rpa(rpa_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    row = conn.execute("""
        SELECT rp.*, aw.nome, aw.cpf, aw.endereco, aw.cidade, aw.uf
        FROM rpa_payments rp JOIN autonomous_workers aw ON aw.id=rp.autonomous_id
        WHERE rp.id=? AND rp.company_id=?
    """, (rpa_id, cid)).fetchone()
    conn.close()
    if not row: raise HTTPException(404, "RPA não encontrado.")
    return dict(row)

@router.delete("/rpa/{rpa_id}")
def delete_rpa(rpa_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM rpa_payments WHERE id=? AND company_id=?", (rpa_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.get("/rpa/{rpa_id}/recibo")
def rpa_recibo(rpa_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    row = conn.execute("""
        SELECT rp.*, aw.nome as autonomo_nome, aw.cpf as autonomo_cpf,
               aw.endereco, aw.cidade, aw.uf
        FROM rpa_payments rp JOIN autonomous_workers aw ON aw.id=rp.autonomous_id
        WHERE rp.id=? AND rp.company_id=?
    """, (rpa_id, cid)).fetchone()
    if not row:
        conn.close(); raise HTTPException(404, "RPA não encontrado.")
    rpa = dict(row)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    bruto = float(rpa.get("valor_bruto",0))
    inss = float(rpa.get("inss_retido",0))
    irrf = float(rpa.get("irrf_retido",0))
    iss = float(rpa.get("iss_retido",0))
    liquido = float(rpa.get("valor_liquido",0))
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>RPA - {rpa.get('autonomo_nome','')}</title>
<style>body{{font-family:'Times New Roman',serif;background:#fff;color:#000;padding:40px;max-width:720px;margin:0 auto}}
h1{{text-align:center;font-size:1.3rem;margin-bottom:0}}p{{margin:4px 0}}
table{{width:100%;border-collapse:collapse;margin:20px 0}}th,td{{border:1px solid #000;padding:8px;text-align:left}}
th{{background:#f0f0f0}}.total{{font-weight:bold;font-size:1.1rem}}.assinatura{{margin-top:60px;text-align:center}}
hr{{margin:30px 0}}</style></head><body>
<h1>{company.get('razao_social','Empresa')}</h1>
<p style="text-align:center">CNPJ: {company.get('cnpj','')} | {company.get('logradouro','')} {company.get('numero','')} — {company.get('cidade','')} {company.get('uf','')}</p>
<hr>
<h2 style="text-align:center;font-size:1.1rem">RECIBO DE PAGAMENTO A AUTÔNOMO</h2>
<p><strong>Prestador:</strong> {rpa.get('autonomo_nome','')}</p>
<p><strong>CPF:</strong> {rpa.get('autonomo_cpf','')}</p>
<p><strong>Endereço:</strong> {rpa.get('endereco','')} — {rpa.get('cidade','')} {rpa.get('uf','')}</p>
<p><strong>Competência:</strong> {rpa.get('competencia','')} | <strong>Data de Pagamento:</strong> {rpa.get('data_pagamento','')}</p>
<p><strong>Serviço Prestado:</strong> {rpa.get('descricao_servico','')}</p>
<table>
<tr><th>Descrição</th><th style="text-align:right">Valor (R$)</th></tr>
<tr><td>Valor Bruto dos Serviços</td><td style="text-align:right">{bruto:,.2f}</td></tr>
<tr><td>(-) INSS Retido (11%)</td><td style="text-align:right">({inss:,.2f})</td></tr>
<tr><td>(-) IRRF Retido</td><td style="text-align:right">({irrf:,.2f})</td></tr>
<tr><td>(-) ISS Retido</td><td style="text-align:right">({iss:,.2f})</td></tr>
<tr class="total"><td>(=) Valor Líquido a Receber</td><td style="text-align:right">{liquido:,.2f}</td></tr>
</table>
<div class="assinatura">
<p>_____________________________________________</p>
<p>{rpa.get('autonomo_nome','')}</p>
<p>CPF: {rpa.get('autonomo_cpf','')}</p>
<p>Data: ____/____/________</p>
</div>
</body></html>"""
    return Response(content=html, media_type="text/html")

@router.get("/esocial/s2300/{autonomous_id}")
def gerar_s2300(autonomous_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    aw = conn.execute("SELECT * FROM autonomous_workers WHERE id=? AND company_id=?", (autonomous_id, cid)).fetchone()
    if not aw: conn.close(); raise HTTPException(404, "Autônomo não encontrado.")
    aw = dict(aw)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    cnpj = (company.get("cnpj","")).replace(".","").replace("/","").replace("-","")
    dt = date.today().isoformat()
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtTSVInicio/v03_01_00">
  <evtTSVInicio Id="ID1{cnpj}{dt.replace('-','')}001">
    <ideEvento><indRetif>1</indRetif><nrRec/><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEmpregador>
    <ideTrabSemVinculo><cpfTrab>{aw.get('cpf','').replace('.','').replace('-','')}</cpfTrab><nisTrab>{aw.get('pis_pasep','').replace('.','').replace('-','').replace('/','')}</nisTrab><codCateg>701</codCateg></ideTrabSemVinculo>
    <infoTSV><codCateg>701</codCateg><dtInicio>{dt}</dtInicio><tpRegTrab>0</tpRegTrab></infoTSV>
  </evtTSVInicio>
</eSocial>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-2300-{autonomous_id}.xml"'})

@router.get("/esocial/s2399/{rpa_id}")
def gerar_s2399(rpa_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rpa = conn.execute("SELECT rp.*, aw.cpf, aw.pis_pasep FROM rpa_payments rp JOIN autonomous_workers aw ON aw.id=rp.autonomous_id WHERE rp.id=? AND rp.company_id=?", (rpa_id, cid)).fetchone()
    if not rpa: conn.close(); raise HTTPException(404, "RPA não encontrado.")
    rpa = dict(rpa)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    cnpj = (company.get("cnpj","")).replace(".","").replace("/","").replace("-","")
    dt = rpa.get("data_pagamento", date.today().isoformat())
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtTSVTermino/v03_01_00">
  <evtTSVTermino Id="ID1{cnpj}{dt.replace('-','')}002">
    <ideEvento><indRetif>1</indRetif><nrRec/><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEmpregador>
    <ideTrabSemVinculo><cpfTrab>{rpa.get('cpf','').replace('.','').replace('-','')}</cpfTrab><nisTrab>{rpa.get('pis_pasep','').replace('.','').replace('-','').replace('/','')}</nisTrab><codCateg>701</codCateg></ideTrabSemVinculo>
    <infoTSVTermino><dtTerm>{dt}</dtTerm><mtvDeslig>99</mtvDeslig></infoTSVTermino>
  </evtTSVTermino>
</eSocial>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-2399-{rpa_id}.xml"'})


# ─── PRÓ-LABORE ───────────────────────────────────────────────────────────────

@router.get("/partners")
def list_partners(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("SELECT * FROM partners WHERE company_id=? ORDER BY nome", (cid,)).fetchall())
    conn.close()
    return rows

@router.post("/partners", status_code=201)
def create_partner(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO partners (company_id,nome,cpf,cargo,percentual_sociedade,salario_prolabore,banco,agencia,conta,ativo)
                   VALUES (?,?,?,?,?,?,?,?,?,1)""",
        (cid, data["nome"], data["cpf"], data.get("cargo","Sócio-Administrador"),
         float(data.get("percentual_sociedade",0)), float(data.get("salario_prolabore",0)),
         data.get("banco",""), data.get("agencia",""), data.get("conta","")))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM partners WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    return row

@router.put("/partners/{p_id}")
def update_partner(p_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("""UPDATE partners SET nome=?,cpf=?,cargo=?,percentual_sociedade=?,salario_prolabore=?,banco=?,agencia=?,conta=?,ativo=?
                    WHERE id=? AND company_id=?""",
        (data.get("nome"), data.get("cpf"), data.get("cargo"), float(data.get("percentual_sociedade",0)),
         float(data.get("salario_prolabore",0)), data.get("banco",""), data.get("agencia",""),
         data.get("conta",""), int(data.get("ativo",1)), p_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.delete("/partners/{p_id}")
def delete_partner(p_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM partners WHERE id=? AND company_id=?", (p_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.post("/prolabore/calcular/{competencia}")
def calcular_prolabore(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    partners = rows_to_dicts(conn.execute("SELECT * FROM partners WHERE company_id=? AND ativo=1", (cid,)).fetchall())
    result = []
    for p in partners:
        bruto = float(p.get("salario_prolabore", 0))
        inss = round(min(bruto * 0.11, 897.32), 2)
        base_irrf = bruto - inss
        irrf = _calc_irrf_autonomo(base_irrf)
        liquido = round(bruto - inss - irrf, 2)
        # upsert
        existing = conn.execute("SELECT id FROM prolabore_runs WHERE partner_id=? AND company_id=? AND competencia=?",
                                (p["id"], cid, competencia)).fetchone()
        if existing:
            conn.execute("UPDATE prolabore_runs SET valor_bruto=?,inss_retido=?,irrf_retido=?,valor_liquido=? WHERE id=?",
                         (bruto, inss, irrf, liquido, existing["id"]))
        else:
            conn.execute("INSERT INTO prolabore_runs (company_id,partner_id,competencia,valor_bruto,inss_retido,irrf_retido,valor_liquido) VALUES (?,?,?,?,?,?,?)",
                         (cid, p["id"], competencia, bruto, inss, irrf, liquido))
        result.append({**p, "competencia": competencia, "inss_retido": inss, "irrf_retido": irrf, "valor_liquido": liquido})
    conn.commit(); conn.close()
    return result

@router.get("/prolabore")
def list_prolabore(competencia: str = Query(None), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    if competencia:
        rows = rows_to_dicts(conn.execute("""
            SELECT pr.*, p.nome, p.cpf, p.cargo FROM prolabore_runs pr JOIN partners p ON p.id=pr.partner_id
            WHERE pr.company_id=? AND pr.competencia=?
        """, (cid, competencia)).fetchall())
    else:
        rows = rows_to_dicts(conn.execute("""
            SELECT pr.*, p.nome, p.cpf, p.cargo FROM prolabore_runs pr JOIN partners p ON p.id=pr.partner_id
            WHERE pr.company_id=? ORDER BY pr.competencia DESC
        """, (cid,)).fetchall())
    conn.close()
    return rows

@router.delete("/prolabore/{pr_id}")
def delete_prolabore(pr_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM prolabore_runs WHERE id=? AND company_id=?", (pr_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.get("/prolabore/{pr_id}/recibo")
def prolabore_recibo(pr_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    row = conn.execute("""
        SELECT pr.*, p.nome, p.cpf, p.cargo FROM prolabore_runs pr JOIN partners p ON p.id=pr.partner_id
        WHERE pr.id=? AND pr.company_id=?
    """, (pr_id, cid)).fetchone()
    if not row: conn.close(); raise HTTPException(404, "Pró-labore não encontrado.")
    pl = dict(row)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    bruto = float(pl.get("valor_bruto",0)); inss = float(pl.get("inss_retido",0))
    irrf = float(pl.get("irrf_retido",0)); liquido = float(pl.get("valor_liquido",0))
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Pró-labore - {pl.get('nome','')}</title>
<style>body{{font-family:'Times New Roman',serif;background:#fff;color:#000;padding:40px;max-width:720px;margin:0 auto}}
h1{{text-align:center;font-size:1.3rem}}p{{margin:4px 0}}
table{{width:100%;border-collapse:collapse;margin:20px 0}}th,td{{border:1px solid #000;padding:8px}}
th{{background:#f0f0f0}}.total{{font-weight:bold}}.assinatura{{margin-top:60px;text-align:center}}hr{{margin:30px 0}}</style></head><body>
<h1>{company.get('razao_social','Empresa')}</h1>
<p style="text-align:center">CNPJ: {company.get('cnpj','')} | {company.get('cidade','')} {company.get('uf','')}</p>
<hr><h2 style="text-align:center;font-size:1.1rem">RECIBO DE PRÓ-LABORE — {pl.get('competencia','')}</h2>
<p><strong>Sócio:</strong> {pl.get('nome','')} | <strong>CPF:</strong> {pl.get('cpf','')} | <strong>Cargo:</strong> {pl.get('cargo','')}</p>
<table>
<tr><th>Descrição</th><th style="text-align:right">Valor (R$)</th></tr>
<tr><td>Pró-labore Bruto</td><td style="text-align:right">{bruto:,.2f}</td></tr>
<tr><td>(-) INSS Contribuinte Individual (11%)</td><td style="text-align:right">({inss:,.2f})</td></tr>
<tr><td>(-) IRRF Retido na Fonte</td><td style="text-align:right">({irrf:,.2f})</td></tr>
<tr class="total"><td>(=) Valor Líquido a Receber</td><td style="text-align:right">{liquido:,.2f}</td></tr>
</table>
<div class="assinatura"><p>_____________________________________________</p><p>{pl.get('nome','')}</p><p>Data: ____/____/________</p></div>
</body></html>"""
    return Response(content=html, media_type="text/html")

@router.get("/prolabore/contabil/{competencia}")
def prolabore_contabil(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT pr.*, p.nome FROM prolabore_runs pr JOIN partners p ON p.id=pr.partner_id
        WHERE pr.company_id=? AND pr.competencia=?
    """, (cid, competencia)).fetchall())
    conn.close()
    total_bruto = sum(float(r.get("valor_bruto",0)) for r in rows)
    total_inss = sum(float(r.get("inss_retido",0)) for r in rows)
    total_irrf = sum(float(r.get("irrf_retido",0)) for r in rows)
    total_liquido = sum(float(r.get("valor_liquido",0)) for r in rows)
    return {
        "competencia": competencia,
        "total_bruto": round(total_bruto,2),
        "total_inss": round(total_inss,2),
        "total_irrf": round(total_irrf,2),
        "total_liquido": round(total_liquido,2),
        "partidas": [
            {"tipo":"debito",  "conta":"2.3.1.01", "descricao":"Pró-labore a Pagar",  "valor": round(total_bruto,2)},
            {"tipo":"credito", "conta":"1.1.1.01", "descricao":"Caixa / Banco",       "valor": round(total_liquido,2)},
            {"tipo":"credito", "conta":"2.3.1.05", "descricao":"INSS a Recolher",     "valor": round(total_inss,2)},
            {"tipo":"credito", "conta":"2.3.1.06", "descricao":"IRRF a Recolher",     "valor": round(total_irrf,2)},
        ],
        "detalhes": rows,
    }


# ─── EXAMES MÉDICOS (ASO) ─────────────────────────────────────────────────────

@router.get("/medical-exams")
def list_medical_exams(
    employee_id: Optional[int] = Query(None),
    tipo: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    sql = """SELECT me.*, e.name as employee_name, e.cpf as employee_cpf
             FROM medical_exams me JOIN employees e ON e.id=me.employee_id
             WHERE me.company_id=?"""
    params: List[Any] = [cid]
    if employee_id:
        sql += " AND me.employee_id=?"; params.append(employee_id)
    if tipo:
        sql += " AND me.tipo=?"; params.append(tipo)
    sql += " ORDER BY me.data_exame DESC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows

@router.post("/medical-exams", status_code=201)
def create_medical_exam(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    dt_exame = data.get("data_exame","")
    per = int(data.get("periodicidade_meses", 12))
    try:
        from dateutil.relativedelta import relativedelta
        dt_v = (date.fromisoformat(dt_exame) + relativedelta(months=per)).isoformat()
    except Exception:
        try:
            d = date.fromisoformat(dt_exame)
            m = d.month + per
            y = d.year + (m-1)//12
            m = (m-1)%12+1
            dt_v = date(y, m, min(d.day, 28)).isoformat()
        except Exception:
            dt_v = ""
    cur = conn.cursor()
    cur.execute("""INSERT INTO medical_exams (company_id,employee_id,tipo,data_exame,periodicidade_meses,data_vencimento,resultado,restricoes,medico,crm_medico,clinica,observacoes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, data["employee_id"], data["tipo"], dt_exame, per, dt_v,
         data.get("resultado","apto"), data.get("restricoes",""),
         data.get("medico",""), data.get("crm_medico",""),
         data.get("clinica",""), data.get("observacoes","")))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM medical_exams WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    return row

@router.put("/medical-exams/{exam_id}")
def update_medical_exam(exam_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("""UPDATE medical_exams SET tipo=?,data_exame=?,periodicidade_meses=?,data_vencimento=?,resultado=?,restricoes=?,medico=?,crm_medico=?,clinica=?,observacoes=?
                    WHERE id=? AND company_id=?""",
        (data.get("tipo"), data.get("data_exame"), int(data.get("periodicidade_meses",12)),
         data.get("data_vencimento",""), data.get("resultado","apto"), data.get("restricoes",""),
         data.get("medico",""), data.get("crm_medico",""), data.get("clinica",""),
         data.get("observacoes",""), exam_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.delete("/medical-exams/{exam_id}")
def delete_medical_exam(exam_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    conn.execute("DELETE FROM medical_exams WHERE id=? AND company_id=?", (exam_id, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@router.get("/medical-exams/vencimentos")
def medical_exams_vencimentos(dias: int = Query(30), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    hoje = date.today()
    limite = (hoje + timedelta(days=dias)).isoformat()
    rows = rows_to_dicts(conn.execute("""
        SELECT me.*, e.name as employee_name
        FROM medical_exams me JOIN employees e ON e.id=me.employee_id
        WHERE me.company_id=? AND me.data_vencimento IS NOT NULL AND me.data_vencimento <= ?
        ORDER BY me.data_vencimento ASC
    """, (cid, limite)).fetchall())
    hoje_str = hoje.isoformat()
    for r in rows:
        try:
            dv = r.get("data_vencimento","")
            diff = (date.fromisoformat(dv) - hoje).days if dv else 999
        except Exception:
            diff = 999
        r["dias_restantes"] = diff
    conn.close()
    return rows

@router.get("/esocial/s2220/{exam_id}")
def gerar_s2220(exam_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cid = current_user.get("company_id", 1)
    exam = conn.execute("SELECT me.*, e.cpf FROM medical_exams me JOIN employees e ON e.id=me.employee_id WHERE me.id=? AND me.company_id=?", (exam_id, cid)).fetchone()
    if not exam: conn.close(); raise HTTPException(404, "Exame não encontrado.")
    ex = dict(exam)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    cnpj = (company.get("cnpj","")).replace(".","").replace("/","").replace("-","")
    tipo_map = {"admissional":"1","periodico":"2","retorno_trabalho":"3","mudanca_funcao":"4","demissional":"9"}
    tp = tipo_map.get(ex.get("tipo","periodico"),"2")
    res_map = {"apto":"1","inapto":"2","apto_restricao":"3"}
    res = res_map.get(ex.get("resultado","apto"),"1")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtMonit/v03_01_00">
  <evtMonit Id="ID1{cnpj}{ex.get('data_exame','').replace('-','')}">
    <ideEvento><indRetif>1</indRetif><nrRec/><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEmpregador>
    <ideTrabalhador><cpfTrab>{ex.get('cpf','').replace('.','').replace('-','')}</cpfTrab></ideTrabalhador>
    <infoMonit>
      <aso>
        <dtAso>{ex.get('data_exame','')}</dtAso>
        <tpAso>{tp}</tpAso>
        <medico>
          <nmMed>{ex.get('medico','')}</nmMed>
          <nrCRM>{ex.get('crm_medico','')}</nrCRM>
          <ufCRM>SP</ufCRM>
        </medico>
        <resAso>{res}</resAso>
      </aso>
    </infoMonit>
  </evtMonit>
</eSocial>"""
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-2220-{exam_id}.xml"'})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BLOCO 1 â€” PPP & LTCAT / S-2240
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@router.get("/work-environments")
def list_work_environments(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); rows = rows_to_dicts(conn.execute("SELECT * FROM work_environments WHERE company_id=? ORDER BY nome", (cid,)).fetchall()); conn.close(); return rows

@router.post("/work-environments")
def create_work_environment(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    cur = conn.execute("INSERT INTO work_environments (company_id,nome,local_trabalho,setor,atividade_economica) VALUES (?,?,?,?,?)",
        (cid, body["nome"], body.get("local_trabalho",""), body.get("setor",""), body.get("atividade_economica","")))
    new_id = cur.lastrowid; conn.commit()
    row = dict(conn.execute("SELECT * FROM work_environments WHERE id=?", (new_id,)).fetchone()); conn.close(); return row

@router.put("/work-environments/{env_id}")
def update_work_environment(env_id: int, body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    conn.execute("UPDATE work_environments SET nome=?,local_trabalho=?,setor=?,atividade_economica=? WHERE id=? AND company_id=?",
        (body.get("nome",""), body.get("local_trabalho",""), body.get("setor",""), body.get("atividade_economica",""), env_id, cid))
    conn.commit(); conn.close(); return {"ok": True}

@router.delete("/work-environments/{env_id}")
def delete_work_environment(env_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); conn.execute("DELETE FROM work_environments WHERE id=? AND company_id=?", (env_id, cid)); conn.commit(); conn.close(); return {"ok": True}

@router.get("/work-environments/{env_id}/risk-agents")
def list_env_risk_agents(env_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); rows = rows_to_dicts(conn.execute("SELECT * FROM risk_agents WHERE company_id=? AND work_environment_id=?", (cid, env_id)).fetchall()); conn.close(); return rows

@router.get("/risk-agents")
def list_risk_agents(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); rows = rows_to_dicts(conn.execute("SELECT ra.*, we.nome AS ambiente_nome FROM risk_agents ra LEFT JOIN work_environments we ON we.id=ra.work_environment_id WHERE ra.company_id=? ORDER BY ra.nome", (cid,)).fetchall()); conn.close(); return rows

@router.post("/risk-agents")
def create_risk_agent(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    cur = conn.execute("INSERT INTO risk_agents (company_id,work_environment_id,tipo,nome,nr15_codigo,intensidade,limite_tolerancia,epc,epi,esocial_cod_agente) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (cid, body.get("work_environment_id"), body.get("tipo","fisico"), body["nome"], body.get("nr15_codigo",""), body.get("intensidade",""), body.get("limite_tolerancia",""), body.get("epc",""), body.get("epi",""), body.get("esocial_cod_agente","")))
    new_id = cur.lastrowid; conn.commit()
    row = dict(conn.execute("SELECT * FROM risk_agents WHERE id=?", (new_id,)).fetchone()); conn.close(); return row

@router.put("/risk-agents/{agent_id}")
def update_risk_agent(agent_id: int, body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    conn.execute("UPDATE risk_agents SET work_environment_id=?,tipo=?,nome=?,nr15_codigo=?,intensidade=?,limite_tolerancia=?,epc=?,epi=?,esocial_cod_agente=? WHERE id=? AND company_id=?",
        (body.get("work_environment_id"), body.get("tipo","fisico"), body.get("nome",""), body.get("nr15_codigo",""), body.get("intensidade",""), body.get("limite_tolerancia",""), body.get("epc",""), body.get("epi",""), body.get("esocial_cod_agente",""), agent_id, cid))
    conn.commit(); conn.close(); return {"ok": True}

@router.delete("/risk-agents/{agent_id}")
def delete_risk_agent(agent_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); conn.execute("DELETE FROM risk_agents WHERE id=? AND company_id=?", (agent_id, cid)); conn.commit(); conn.close(); return {"ok": True}

@router.get("/ltcat")
def list_ltcat(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT lt.*, we.nome AS ambiente_nome FROM ltcat_reports lt LEFT JOIN work_environments we ON we.id=lt.work_environment_id WHERE lt.company_id=? ORDER BY lt.data_emissao DESC", (cid,)).fetchall())
    conn.close()
    for r in rows:
        if r.get("data_vencimento"):
            r["dias_vencimento"] = (date.fromisoformat(r["data_vencimento"]) - date.today()).days
        else:
            r["dias_vencimento"] = None
    return rows

@router.post("/ltcat")
def create_ltcat(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    cur = conn.execute("INSERT INTO ltcat_reports (company_id,work_environment_id,data_emissao,data_vencimento,responsavel_tecnico,conselho_profissional,registro,conclusao,observacoes) VALUES (?,?,?,?,?,?,?,?,?)",
        (cid, body.get("work_environment_id"), body["data_emissao"], body.get("data_vencimento"), body["responsavel_tecnico"], body.get("conselho_profissional",""), body.get("registro",""), body.get("conclusao","sem_exposicao"), body.get("observacoes","")))
    new_id = cur.lastrowid; conn.commit()
    row = dict(conn.execute("SELECT * FROM ltcat_reports WHERE id=?", (new_id,)).fetchone()); conn.close(); return row

@router.put("/ltcat/{ltcat_id}")
def update_ltcat(ltcat_id: int, body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    conn.execute("UPDATE ltcat_reports SET work_environment_id=?,data_emissao=?,data_vencimento=?,responsavel_tecnico=?,conselho_profissional=?,registro=?,conclusao=?,observacoes=? WHERE id=? AND company_id=?",
        (body.get("work_environment_id"), body.get("data_emissao",""), body.get("data_vencimento"), body.get("responsavel_tecnico",""), body.get("conselho_profissional",""), body.get("registro",""), body.get("conclusao","sem_exposicao"), body.get("observacoes",""), ltcat_id, cid))
    conn.commit(); conn.close(); return {"ok": True}

@router.delete("/ltcat/{ltcat_id}")
def delete_ltcat(ltcat_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); conn.execute("DELETE FROM ltcat_reports WHERE id=? AND company_id=?", (ltcat_id, cid)); conn.commit(); conn.close(); return {"ok": True}

@router.get("/ltcat/vencimentos")
def ltcat_vencimentos(dias: int = 90, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    limit_date = (date.today() + timedelta(days=dias)).isoformat()
    rows = rows_to_dicts(conn.execute("SELECT lt.*, we.nome AS ambiente_nome FROM ltcat_reports lt LEFT JOIN work_environments we ON we.id=lt.work_environment_id WHERE lt.company_id=? AND lt.data_vencimento <= ? ORDER BY lt.data_vencimento", (cid, limit_date)).fetchall())
    conn.close()
    for r in rows:
        if r.get("data_vencimento"):
            r["dias_restantes"] = (date.fromisoformat(r["data_vencimento"]) - date.today()).days
    return rows

@router.get("/ppp")
def list_ppp(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""SELECT p.*, e.name AS employee_name, e.cpf, e.role AS cargo, e.pis_pasep,
        e.admission_date, e.dismissal_date, we.nome AS ambiente_nome
        FROM ppp_records p JOIN employees e ON e.id=p.employee_id
        LEFT JOIN work_environments we ON we.id=p.work_environment_id
        WHERE p.company_id=? ORDER BY p.created_at DESC""", (cid,)).fetchall())
    conn.close(); return rows

@router.post("/ppp")
def create_ppp(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    cur = conn.execute("INSERT INTO ppp_records (company_id,employee_id,work_environment_id,data_inicio_exposicao,data_fim_exposicao,responsavel_tecnico,registro_profissional,observacoes) VALUES (?,?,?,?,?,?,?,?)",
        (cid, body["employee_id"], body.get("work_environment_id"), body.get("data_inicio_exposicao",""), body.get("data_fim_exposicao",""), body.get("responsavel_tecnico",""), body.get("registro_profissional",""), body.get("observacoes","")))
    new_id = cur.lastrowid; conn.commit()
    row = dict(conn.execute("SELECT * FROM ppp_records WHERE id=?", (new_id,)).fetchone()); conn.close(); return row

@router.delete("/ppp/{ppp_id}")
def delete_ppp(ppp_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); conn.execute("DELETE FROM ppp_records WHERE id=? AND company_id=?", (ppp_id, cid)); conn.commit(); conn.close(); return {"ok": True}

@router.get("/ppp/employee/{emp_id}")
def ppp_by_employee(emp_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT p.*, we.nome AS ambiente_nome FROM ppp_records p LEFT JOIN work_environments we ON we.id=p.work_environment_id WHERE p.company_id=? AND p.employee_id=? ORDER BY p.created_at DESC", (cid, emp_id)).fetchall())
    conn.close(); return rows

@router.get("/esocial/s2240/{env_id}")
def esocial_s2240(env_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    env = conn.execute("SELECT * FROM work_environments WHERE id=? AND company_id=?", (env_id, cid)).fetchone()
    if not env:
        conn.close(); raise HTTPException(404, "Ambiente nÃ£o encontrado")
    env = dict(env)
    agents = rows_to_dicts(conn.execute("SELECT * FROM risk_agents WHERE work_environment_id=? AND company_id=?", (env_id, cid)).fetchall())
    ltcat = conn.execute("SELECT * FROM ltcat_reports WHERE work_environment_id=? AND company_id=? ORDER BY data_emissao DESC LIMIT 1", (env_id, cid)).fetchone()
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    cnpj = company.get("cnpj","").replace(".","").replace("/","").replace("-","")
    period = date.today().strftime("%Y-%m")
    ltcat_id = ltcat["id"] if ltcat else "0"
    agents_xml = "\n".join([f"""          <agNoc>
            <codAgNoc>{a.get('esocial_cod_agente','01')}</codAgNoc>
            <dscAgNoc>{a.get('nome','')}</dscAgNoc>
            <tpAval>1</tpAval>
            <nrLtcat>{ltcat_id}</nrLtcat>
          </agNoc>""" for a in agents])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtAmbiente/v03_01_00">
  <evtAmbiente Id="ID1{cnpj}{date.today().strftime('%Y%m%d')}">
    <ideEvento><indRetif>1</indRetif><nrRec/><tpAmb>1</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEmpregador>
    <infoAmbiente>
      <inclusao>
        <ideAmbiente><codAmb>{env_id}</codAmb><iniValid>{period}</iniValid></ideAmbiente>
        <dadosAmbiente>
          <localAmb>1</localAmb>
          <dscSetor>{env.get('setor','')}</dscSetor>
          <tpInsc>1</tpInsc>
          <nrInsc>{cnpj}</nrInsc>
{agents_xml}
        </dadosAmbiente>
      </inclusao>
    </infoAmbiente>
  </evtAmbiente>
</eSocial>"""
    return Response(content=xml, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="S-2240-{env_id}.xml"'})

@router.get("/ppp/{ppp_id}/documento")
def ppp_documento(ppp_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    ppp = conn.execute("""SELECT p.*, e.name, e.cpf, e.pis_pasep, e.role AS cargo,
        e.admission_date, e.dismissal_date, e.salary, we.nome AS ambiente_nome
        FROM ppp_records p JOIN employees e ON e.id=p.employee_id
        LEFT JOIN work_environments we ON we.id=p.work_environment_id
        WHERE p.id=? AND p.company_id=?""", (ppp_id, cid)).fetchone()
    if not ppp: conn.close(); raise HTTPException(404)
    ppp = dict(ppp)
    agents = rows_to_dicts(conn.execute("SELECT * FROM risk_agents WHERE work_environment_id=? AND company_id=?", (ppp.get("work_environment_id"), cid)).fetchall()) if ppp.get("work_environment_id") else []
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    agents_rows = "".join([f"<tr><td>{a.get('nome','')}</td><td>{a.get('tipo','')}</td><td>{a.get('intensidade','')}</td><td>{a.get('epi','')}</td><td>{ppp.get('data_inicio_exposicao','')}</td><td>{ppp.get('data_fim_exposicao','') or 'atual'}</td></tr>" for a in agents])
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>PPP</title>
<style>body{{font-family:serif;max-width:900px;margin:40px auto;padding:20px;color:#000;background:#fff}}
h1{{text-align:center;font-size:1.3em;text-transform:uppercase;border-bottom:2px solid #000;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin:12px 0}}th,td{{border:1px solid #333;padding:6px 10px;font-size:.85em}}
th{{background:#eee;font-weight:bold}}.sig{{margin-top:40px;display:flex;gap:40px}}
.sig div{{flex:1;text-align:center;border-top:1px solid #000;padding-top:6px}}@media print{{body{{margin:0}}}}
</style></head><body>
<h1>Perfil ProfissiogrÃ¡fico PrevidenciÃ¡rio â€” PPP</h1>
<table><tr><th colspan="2">DADOS DA EMPRESA</th></tr>
<tr><td><b>RazÃ£o Social:</b> {company.get('razao_social','')}</td><td><b>CNPJ:</b> {company.get('cnpj','')}</td></tr></table>
<table><tr><th colspan="4">DADOS DO TRABALHADOR</th></tr>
<tr><td><b>Nome:</b> {ppp.get('name','')}</td><td><b>CPF:</b> {ppp.get('cpf','')}</td><td><b>PIS/PASEP:</b> {ppp.get('pis_pasep','')}</td><td><b>Cargo:</b> {ppp.get('cargo','')}</td></tr>
<tr><td><b>AdmissÃ£o:</b> {ppp.get('admission_date','')}</td><td><b>DemissÃ£o:</b> {ppp.get('dismissal_date','') or 'Ativo'}</td><td colspan="2"><b>Ambiente:</b> {ppp.get('ambiente_nome','')}</td></tr></table>
<table><tr><th>Agente Nocivo</th><th>Tipo</th><th>Intensidade</th><th>EPI</th><th>InÃ­cio Exp.</th><th>Fim Exp.</th></tr>
{agents_rows if agents_rows else '<tr><td colspan="6" style="text-align:center">Sem agentes nocivos</td></tr>'}
</table>
<p><b>ObservaÃ§Ãµes:</b> {ppp.get('observacoes','')}</p>
<div class="sig">
<div>{ppp.get('responsavel_tecnico','')}<br><small>ResponsÃ¡vel TÃ©cnico â€” {ppp.get('registro_profissional','')}</small></div>
<div>_________________________<br><small>Trabalhador â€” {ppp.get('name','')}</small></div>
</div>
<p style="text-align:right;font-size:.75em;margin-top:20px">Emitido em {date.today().strftime('%d/%m/%Y')}</p>
</body></html>"""
    return Response(content=html, media_type="text/html")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BLOCO 2 â€” INTEGRAÃ‡ÃƒO CONTÃBIL
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@router.get("/accounting-config")
def get_accounting_config(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    row = conn.execute("SELECT * FROM accounting_config_dp WHERE company_id=?", (cid,)).fetchone()
    conn.close()
    return dict(row) if row else {}

@router.put("/accounting-config")
def update_accounting_config(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    exists = conn.execute("SELECT id FROM accounting_config_dp WHERE company_id=?", (cid,)).fetchone()
    fields = ["conta_salarios_bruto","conta_inss_empregado","conta_inss_patronal","conta_fgts_provisao",
              "conta_irrf","conta_salarios_pagar","conta_ferias_provisao","conta_decimo_provisao","conta_prolabore","conta_banco"]
    if exists:
        sets = ", ".join([f"{f}=?" for f in fields] + ["updated_at=CURRENT_TIMESTAMP"])
        vals = [body.get(f,"") for f in fields] + [cid]
        conn.execute(f"UPDATE accounting_config_dp SET {sets} WHERE company_id=?", vals)
    else:
        cols = ",".join(["company_id"] + fields)
        phs = ",".join(["?"] * (1 + len(fields)))
        vals = [cid] + [body.get(f,"") for f in fields]
        conn.execute(f"INSERT INTO accounting_config_dp ({cols}) VALUES ({phs})", vals)
    conn.commit(); conn.close(); return {"ok": True}

@router.get("/accounting/entries")
def get_accounting_entries(competencia: str = "", current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    if competencia:
        rows = rows_to_dicts(conn.execute("SELECT * FROM payroll_accounting_entries WHERE company_id=? AND competencia=? ORDER BY id", (cid, competencia)).fetchall())
    else:
        rows = rows_to_dicts(conn.execute("SELECT * FROM payroll_accounting_entries WHERE company_id=? ORDER BY competencia DESC, id LIMIT 200", (cid,)).fetchall())
    conn.close(); return rows

@router.post("/accounting/gerar/{competencia}")
def gerar_contabilidade(competencia: str, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    cfg_row = conn.execute("SELECT * FROM accounting_config_dp WHERE company_id=?", (cid,)).fetchone()
    cfg = dict(cfg_row) if cfg_row else {}
    runs = rows_to_dicts(conn.execute("SELECT * FROM payroll_runs WHERE company_id=? AND competencia=?", (cid, competencia)).fetchall())
    total_bruto = sum(r.get("gross_salary", 0) for r in runs)
    total_liquido = sum(r.get("net_salary", 0) for r in runs)
    total_inss = sum(r.get("inss", 0) for r in runs)
    total_irrf = sum(r.get("irrf", 0) for r in runs)
    if total_bruto == 0:
        conn.close(); raise HTTPException(400, "Nenhuma folha calculada para esta competÃªncia")
    conn.execute("DELETE FROM payroll_accounting_entries WHERE company_id=? AND competencia=?", (cid, competencia))
    today = date.today().isoformat()
    entries = [
        ("folha_bruta", f"Folha {competencia} â€” SalÃ¡rios Brutos",
         cfg.get("conta_salarios_bruto","6.1.1.01"), total_bruto, cfg.get("conta_salarios_pagar","2.1.1.01"), total_liquido),
        ("inss_empregado", f"Folha {competencia} â€” INSS Empregados",
         cfg.get("conta_salarios_bruto","6.1.1.01"), 0.01, cfg.get("conta_inss_empregado","2.3.1.01"), total_inss),
        ("irrf", f"Folha {competencia} â€” IRRF Retido",
         cfg.get("conta_salarios_bruto","6.1.1.01"), 0.01, cfg.get("conta_irrf","2.3.1.04"), total_irrf),
        ("inss_patronal", f"Folha {competencia} â€” INSS Patronal 20%",
         "6.1.1.10", round(total_bruto * 0.20, 2), cfg.get("conta_inss_patronal","2.3.1.02"), round(total_bruto * 0.20, 2)),
        ("fgts", f"Folha {competencia} â€” FGTS 8%",
         "6.1.1.11", round(total_bruto * 0.08, 2), cfg.get("conta_fgts_provisao","2.3.1.03"), round(total_bruto * 0.08, 2)),
        ("provisao_ferias", f"Folha {competencia} â€” ProvisÃ£o FÃ©rias 1/12",
         "6.1.1.12", round(total_bruto * 0.0833, 2), cfg.get("conta_ferias_provisao","2.1.2.01"), round(total_bruto * 0.0833, 2)),
        ("provisao_decimo", f"Folha {competencia} â€” ProvisÃ£o 13Âº Sal 1/12",
         "6.1.1.13", round(total_bruto * 0.0833, 2), cfg.get("conta_decimo_provisao","2.1.3.01"), round(total_bruto * 0.0833, 2)),
    ]
    for e in entries:
        conn.execute("INSERT INTO payroll_accounting_entries (company_id,competencia,tipo,data_lancamento,historico,debito_conta,debito_valor,credito_conta,credito_valor) VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, competencia, e[0], today, e[1], e[2], e[3], e[4], e[5]))
    conn.commit()
    rows = rows_to_dicts(conn.execute("SELECT * FROM payroll_accounting_entries WHERE company_id=? AND competencia=? ORDER BY id", (cid, competencia)).fetchall())
    conn.close(); return rows

@router.post("/accounting/exportar/{competencia}")
def exportar_contabilidade(competencia: str, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM payroll_accounting_entries WHERE company_id=? AND competencia=? ORDER BY id", (cid, competencia)).fetchall())
    conn.execute("UPDATE payroll_accounting_entries SET status='exportado' WHERE company_id=? AND competencia=?", (cid, competencia))
    conn.commit(); conn.close()
    lines = ["data;historico;debito_conta;debito_valor;credito_conta;credito_valor"]
    for r in rows:
        lines.append(f"{r['data_lancamento']};{r['historico']};{r['debito_conta']};{r['debito_valor']:.2f};{r['credito_conta']};{r['credito_valor']:.2f}")
    return Response(content="\n".join(lines), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="contabil-{competencia}.csv"'})

@router.delete("/accounting/entries/{entry_id}")
def delete_accounting_entry(entry_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); conn.execute("DELETE FROM payroll_accounting_entries WHERE id=? AND company_id=?", (entry_id, cid)); conn.commit(); conn.close(); return {"ok": True}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BLOCO 3 â€” ESTAGIÃRIOS & APRENDIZES
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@router.get("/interns")
def list_interns(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); rows = rows_to_dicts(conn.execute("SELECT * FROM interns WHERE company_id=? ORDER BY nome", (cid,)).fetchall()); conn.close()
    for r in rows:
        if r.get("data_fim"):
            r["dias_restantes"] = (date.fromisoformat(r["data_fim"]) - date.today()).days
    return rows

@router.post("/interns")
def create_intern(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    cur = conn.execute("INSERT INTO interns (company_id,nome,cpf,data_nascimento,email,telefone,instituicao,curso,nivel,supervisor_nome,agente_integracao,bolsa_auxilio,vale_transporte,carga_horaria_semanal,data_inicio,data_fim,status,observacoes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, body["nome"], body.get("cpf",""), body.get("data_nascimento",""), body.get("email",""), body.get("telefone",""), body["instituicao"], body.get("curso",""), body.get("nivel","superior"), body.get("supervisor_nome",""), body.get("agente_integracao",""), body.get("bolsa_auxilio",0), body.get("vale_transporte",0), body.get("carga_horaria_semanal",20), body["data_inicio"], body["data_fim"], "ativo", body.get("observacoes","")))
    new_id = cur.lastrowid; conn.commit()
    row = dict(conn.execute("SELECT * FROM interns WHERE id=?", (new_id,)).fetchone()); conn.close(); return row

@router.put("/interns/{intern_id}")
def update_intern(intern_id: int, body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    conn.execute("UPDATE interns SET nome=?,cpf=?,data_nascimento=?,email=?,telefone=?,instituicao=?,curso=?,nivel=?,supervisor_nome=?,agente_integracao=?,bolsa_auxilio=?,vale_transporte=?,carga_horaria_semanal=?,data_inicio=?,data_fim=?,status=?,observacoes=? WHERE id=? AND company_id=?",
        (body.get("nome",""), body.get("cpf",""), body.get("data_nascimento",""), body.get("email",""), body.get("telefone",""), body.get("instituicao",""), body.get("curso",""), body.get("nivel","superior"), body.get("supervisor_nome",""), body.get("agente_integracao",""), body.get("bolsa_auxilio",0), body.get("vale_transporte",0), body.get("carga_horaria_semanal",20), body.get("data_inicio",""), body.get("data_fim",""), body.get("status","ativo"), body.get("observacoes",""), intern_id, cid))
    conn.commit(); conn.close(); return {"ok": True}

@router.delete("/interns/{intern_id}")
def delete_intern(intern_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); conn.execute("DELETE FROM interns WHERE id=? AND company_id=?", (intern_id, cid)); conn.commit(); conn.close(); return {"ok": True}

@router.get("/interns/termo/{intern_id}")
def intern_tce(intern_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    intern = conn.execute("SELECT * FROM interns WHERE id=? AND company_id=?", (intern_id, cid)).fetchone()
    if not intern: conn.close(); raise HTTPException(404)
    intern = dict(intern)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>TCE</title>
<style>body{{font-family:serif;max-width:900px;margin:40px auto;padding:20px;color:#000;background:#fff}}
h1{{text-align:center;font-size:1.2em;text-transform:uppercase;border-bottom:2px solid #000;padding-bottom:8px}}
p{{line-height:1.7;text-align:justify}}table{{width:100%;border-collapse:collapse;margin:12px 0}}
th,td{{border:1px solid #333;padding:6px 10px;font-size:.85em}}.sig{{margin-top:50px;display:flex;gap:30px;flex-wrap:wrap}}
.sig div{{flex:1;min-width:200px;text-align:center;border-top:1px solid #000;padding-top:6px;font-size:.85em}}
@media print{{body{{margin:0}}}}</style></head><body>
<h1>Termo de Compromisso de EstÃ¡gio â€” TCE</h1>
<p>Pelo presente instrumento, de um lado <b>{company.get('razao_social','')}</b>, CNPJ nÂº {company.get('cnpj','')}, com sede em {company.get('logradouro','')}, nÂº {company.get('numero','')}, {company.get('cidade','')}/{company.get('uf','')}, doravante denominada <b>CONCEDENTE</b>; de outro lado a InstituiÃ§Ã£o de Ensino <b>{intern.get('instituicao','')}</b>, doravante denominada <b>INSTITUIÃ‡ÃƒO DE ENSINO</b>; e ainda o(a) estudante <b>{intern.get('nome','')}</b>, CPF nÂº {intern.get('cpf','')}, doravante denominado(a) <b>ESTAGIÃRIO(A)</b>, celebram o presente Termo nos termos da Lei nÂº 11.788/2008.</p>
<table>
<tr><th>Dados do EstagiÃ¡rio</th><th></th></tr>
<tr><td>Nome</td><td>{intern.get('nome','')}</td></tr>
<tr><td>CPF</td><td>{intern.get('cpf','')}</td></tr>
<tr><td>Curso / NÃ­vel</td><td>{intern.get('curso','')} â€” {intern.get('nivel','')}</td></tr>
<tr><td>InstituiÃ§Ã£o</td><td>{intern.get('instituicao','')}</td></tr>
<tr><th colspan="2">CondiÃ§Ãµes do EstÃ¡gio</th></tr>
<tr><td>PerÃ­odo</td><td>{intern.get('data_inicio','')} a {intern.get('data_fim','')}</td></tr>
<tr><td>Carga HorÃ¡ria Semanal</td><td>{intern.get('carga_horaria_semanal',20)} horas</td></tr>
<tr><td>Bolsa-AuxÃ­lio Mensal</td><td>R$ {float(intern.get('bolsa_auxilio',0)):.2f}</td></tr>
<tr><td>Vale-Transporte Mensal</td><td>R$ {float(intern.get('vale_transporte',0)):.2f}</td></tr>
<tr><td>Supervisor</td><td>{intern.get('supervisor_nome','')}</td></tr>
</table>
<p>O estÃ¡gio nÃ£o cria vÃ­nculo empregatÃ­cio de qualquer natureza, nos termos do art. 3Âº da Lei nÂº 11.788/2008.</p>
<div class="sig">
<div>{company.get('razao_social','')}<br><small>CONCEDENTE</small></div>
<div>{intern.get('nome','')}<br><small>ESTAGIÃRIO(A)</small></div>
<div>{intern.get('instituicao','')}<br><small>INSTITUIÃ‡ÃƒO DE ENSINO</small></div>
</div>
<p style="text-align:right;font-size:.75em;margin-top:20px">{company.get('cidade','')}, {date.today().strftime('%d de %B de %Y')}</p>
</body></html>"""
    return Response(content=html, media_type="text/html")

@router.get("/apprentices")
def list_apprentices(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT a.*, e.name AS employee_name, e.cpf FROM apprentices a JOIN employees e ON e.id=a.employee_id WHERE a.company_id=? ORDER BY a.data_inicio DESC", (cid,)).fetchall())
    conn.close(); return rows

@router.post("/apprentices")
def create_apprentice(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    cur = conn.execute("INSERT INTO apprentices (company_id,employee_id,entidade_qualificadora,programa,data_inicio,data_fim) VALUES (?,?,?,?,?,?)",
        (cid, body["employee_id"], body.get("entidade_qualificadora",""), body.get("programa",""), body["data_inicio"], body["data_fim"]))
    new_id = cur.lastrowid; conn.commit()
    row = dict(conn.execute("SELECT * FROM apprentices WHERE id=?", (new_id,)).fetchone()); conn.close(); return row

@router.delete("/apprentices/{app_id}")
def delete_apprentice(app_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn(); conn.execute("DELETE FROM apprentices WHERE id=? AND company_id=?", (app_id, cid)); conn.commit(); conn.close(); return {"ok": True}

@router.get("/apprentices/cota")
def apprentices_cota(current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    total_emp = conn.execute("SELECT COUNT(*) FROM employees WHERE company_id=? AND active=1", (cid,)).fetchone()[0]
    today = date.today().isoformat()
    ativos = conn.execute("SELECT COUNT(*) FROM apprentices WHERE company_id=? AND data_fim >= ?", (cid, today)).fetchone()[0]
    conn.close()
    cota_min = max(1, round(total_emp * 0.05))
    cota_max = max(1, round(total_emp * 0.15))
    if ativos < cota_min: situacao = "abaixo"
    elif ativos > cota_max: situacao = "acima"
    else: situacao = "dentro"
    return {"total_empregados": total_emp, "cota_minima": cota_min, "cota_maxima": cota_max, "aprendizes_ativos": ativos, "situacao": situacao}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BLOCO 4 â€” EXTRATO FGTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@router.get("/fgts/extrato/{employee_id}")
def fgts_extrato(employee_id: int, ano: int = 0, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    if not ano: ano = date.today().year
    conn = get_conn()
    manual = rows_to_dicts(conn.execute("SELECT * FROM fgts_history WHERE company_id=? AND employee_id=? AND competencia LIKE ? ORDER BY competencia", (cid, employee_id, f"{ano}-%")).fetchall())
    if not manual:
        runs = rows_to_dicts(conn.execute("SELECT competencia, gross_salary FROM payroll_runs WHERE company_id=? AND employee_id=? AND competencia LIKE ? ORDER BY competencia", (cid, employee_id, f"{ano}-%")).fetchall())
        manual = [{"id": None, "competencia": r["competencia"], "salario_base": r["gross_salary"], "fgts_calculado": round(r["gross_salary"]*0.08,2), "fgts_depositado": 0, "data_deposito": "", "guia_referencia": "", "saldo_acumulado": 0} for r in runs]
    saldo = 0.0
    for r in manual:
        dep = float(r.get("fgts_depositado") or 0)
        calc = float(r.get("fgts_calculado") or 0)
        saldo += dep if dep > 0 else calc
        r["saldo_acumulado"] = round(saldo, 2)
    emp = conn.execute("SELECT name FROM employees WHERE id=? AND company_id=?", (employee_id, cid)).fetchone()
    conn.close()
    return {"ano": ano, "employee_name": emp["name"] if emp else "", "registros": manual, "saldo_total": round(saldo, 2)}

@router.post("/fgts/confirmar-deposito")
def fgts_confirmar(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    emp_id = body["employee_id"]; comp = body["competencia"]
    run = conn.execute("SELECT gross_salary FROM payroll_runs WHERE company_id=? AND employee_id=? AND competencia=?", (cid, emp_id, comp)).fetchone()
    salario = run["gross_salary"] if run else 0
    fgts_calc = round(salario * 0.08, 2)
    existing = conn.execute("SELECT id FROM fgts_history WHERE company_id=? AND employee_id=? AND competencia=?", (cid, emp_id, comp)).fetchone()
    if existing:
        conn.execute("UPDATE fgts_history SET fgts_depositado=?,data_deposito=?,guia_referencia=? WHERE id=?",
            (body.get("fgts_depositado",0), body.get("data_deposito",""), body.get("guia_referencia",""), existing["id"]))
    else:
        conn.execute("INSERT INTO fgts_history (company_id,employee_id,competencia,salario_base,fgts_calculado,fgts_depositado,data_deposito,guia_referencia) VALUES (?,?,?,?,?,?,?,?)",
            (cid, emp_id, comp, salario, fgts_calc, body.get("fgts_depositado",0), body.get("data_deposito",""), body.get("guia_referencia","")))
    conn.commit(); conn.close(); return {"ok": True}

@router.get("/fgts/pendentes")
def fgts_pendentes(competencia: str = "", current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    if not competencia: competencia = date.today().strftime("%Y-%m")
    conn = get_conn()
    runs = rows_to_dicts(conn.execute("SELECT pr.employee_id, pr.competencia, pr.gross_salary, e.name FROM payroll_runs pr JOIN employees e ON e.id=pr.employee_id WHERE pr.company_id=? AND pr.competencia=?", (cid, competencia)).fetchall())
    confirmed = set(r["employee_id"] for r in rows_to_dicts(conn.execute("SELECT employee_id FROM fgts_history WHERE company_id=? AND competencia=? AND fgts_depositado > 0", (cid, competencia)).fetchall()))
    conn.close()
    return [dict(r, fgts=round(r["gross_salary"]*0.08,2)) for r in runs if r["employee_id"] not in confirmed]

@router.get("/fgts/resumo")
def fgts_resumo(competencia: str = "", current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    if not competencia: competencia = date.today().strftime("%Y-%m")
    conn = get_conn()
    runs = rows_to_dicts(conn.execute("SELECT employee_id, gross_salary FROM payroll_runs WHERE company_id=? AND competencia=?", (cid, competencia)).fetchall())
    total_calc = round(sum(r["gross_salary"]*0.08 for r in runs), 2)
    total_dep = conn.execute("SELECT COALESCE(SUM(fgts_depositado),0) FROM fgts_history WHERE company_id=? AND competencia=?", (cid, competencia)).fetchone()[0] or 0
    conn.close()
    return {"competencia": competencia, "total_calculado": total_calc, "total_depositado": round(float(total_dep),2), "total_pendente": round(total_calc - float(total_dep), 2), "n_funcionarios": len(runs)}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BLOCO 5 â€” PORTAL DO FUNCIONÃRIO
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@router.get("/employees/by-email")
def employee_by_email(email: str = Query(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    row = conn.execute("""
        SELECT e.* FROM employees e
        JOIN users u ON u.company_id = e.company_id
        WHERE u.email = ? AND u.company_id = ? LIMIT 1
    """, (email, cid)).fetchone()
    conn.close()
    if not row: raise HTTPException(404, "FuncionÃ¡rio nÃ£o encontrado para este usuÃ¡rio")
    return dict(row)

@router.get("/vacation-requests")
def list_vacation_requests(employee_id: int = 0, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    if employee_id:
        rows = rows_to_dicts(conn.execute("SELECT vr.*, e.name AS employee_name FROM vacation_requests vr JOIN employees e ON e.id=vr.employee_id WHERE vr.company_id=? AND vr.employee_id=? ORDER BY vr.created_at DESC", (cid, employee_id)).fetchall())
    else:
        rows = rows_to_dicts(conn.execute("SELECT vr.*, e.name AS employee_name FROM vacation_requests vr JOIN employees e ON e.id=vr.employee_id WHERE vr.company_id=? ORDER BY vr.created_at DESC", (cid,)).fetchall())
    conn.close(); return rows

@router.post("/vacation-requests")
def create_vacation_request(body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    d1 = date.fromisoformat(body["data_inicio_solicitada"]); d2 = date.fromisoformat(body["data_fim_solicitada"])
    dias = (d2 - d1).days + 1
    cur = conn.execute("INSERT INTO vacation_requests (company_id,employee_id,data_inicio_solicitada,data_fim_solicitada,dias_solicitados) VALUES (?,?,?,?,?)",
        (cid, body["employee_id"], body["data_inicio_solicitada"], body["data_fim_solicitada"], dias))
    new_id = cur.lastrowid; conn.commit()
    row = dict(conn.execute("SELECT * FROM vacation_requests WHERE id=?", (new_id,)).fetchone()); conn.close(); return row

@router.put("/vacation-requests/{req_id}")
def update_vacation_request(req_id: int, body: Dict[str,Any]=Body(...), current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    conn.execute("UPDATE vacation_requests SET status=?,motivo_recusa=?,aprovado_por=? WHERE id=? AND company_id=?",
        (body.get("status","pendente"), body.get("motivo_recusa",""), body.get("aprovado_por",""), req_id, cid))
    conn.commit(); conn.close(); return {"ok": True}

@router.get("/declarations/vinculo/{emp_id}")
def declaracao_vinculo(emp_id: int, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    emp = conn.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (emp_id, cid)).fetchone()
    if not emp: conn.close(); raise HTTPException(404)
    emp = dict(emp)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    conn.close()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>DeclaraÃ§Ã£o de VÃ­nculo</title>
<style>body{{font-family:serif;max-width:800px;margin:60px auto;padding:30px;color:#000;background:#fff;line-height:1.8}}
h1{{text-align:center;font-size:1.1em;text-transform:uppercase;margin-bottom:30px}}
p{{text-align:justify;margin:15px 0}}.sig{{margin-top:60px;text-align:center}}
.sig div{{border-top:1px solid #000;width:300px;margin:0 auto;padding-top:8px}}
@media print{{body{{margin:0}}}}</style></head><body>
<h1>DeclaraÃ§Ã£o de VÃ­nculo EmpregatÃ­cio</h1>
<p>{company.get('cidade','')}, {date.today().strftime('%d de %B de %Y')}.</p>
<p><b>{company.get('razao_social','')}</b>, pessoa jurÃ­dica de direito privado, inscrita no CNPJ sob o nÂº <b>{company.get('cnpj','')}</b>, com sede na {company.get('logradouro','')}, nÂº {company.get('numero','')}, {company.get('bairro','')}, {company.get('cidade','')}/{company.get('uf','')}, <b>DECLARA</b>, para os devidos fins de direito, que <b>{emp.get('name','')}</b>, portador(a) do CPF nÂº <b>{emp.get('cpf','')}</b>, Ã© funcionÃ¡rio(a) desta empresa desde <b>{emp.get('admission_date','')}</b>, exercendo o cargo de <b>{emp.get('role','')}</b>, com salÃ¡rio base de <b>R$ {float(emp.get('salary',0)):.2f}</b>, em regime CLT.</p>
<p>Esta declaraÃ§Ã£o Ã© emitida a pedido do(a) interessado(a), para os fins que se fizerem necessÃ¡rios.</p>
<div class="sig"><div>{company.get('razao_social','')}<br><small>ResponsÃ¡vel Legal / RH</small></div></div>
</body></html>"""
    return Response(content=html, media_type="text/html")

@router.get("/declarations/ir/{emp_id}")
def declaracao_ir(emp_id: int, ano: int = 0, current_user=Depends(get_current_user)):
    cid = current_user.get("company_id", 1)
    if not ano: ano = date.today().year - 1
    conn = get_conn()
    emp = conn.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (emp_id, cid)).fetchone()
    if not emp: conn.close(); raise HTTPException(404)
    emp = dict(emp)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    runs = rows_to_dicts(conn.execute("SELECT * FROM payroll_runs WHERE company_id=? AND employee_id=? AND competencia LIKE ?", (cid, emp_id, f"{ano}-%")).fetchall())
    conn.close()
    total_bruto = sum(r.get("gross_salary",0) for r in runs)
    total_inss = sum(r.get("inss",0) for r in runs)
    total_irrf = sum(r.get("irrf",0) for r in runs)
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Informe de Rendimentos</title>
<style>body{{font-family:serif;max-width:800px;margin:40px auto;padding:20px;color:#000;background:#fff}}
h1{{text-align:center;font-size:1.1em;text-transform:uppercase;border-bottom:2px solid #000;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin:12px 0}}th,td{{border:1px solid #333;padding:7px 10px;font-size:.88em}}
th{{background:#eee;font-weight:bold}}.total{{font-weight:bold;background:#f5f5f5}}
@media print{{body{{margin:0}}}}</style></head><body>
<h1>Informe de Rendimentos â€” Ano-CalendÃ¡rio {ano}</h1>
<table><tr><th colspan="2">FONTE PAGADORA</th></tr>
<tr><td>RazÃ£o Social</td><td>{company.get('razao_social','')}</td></tr>
<tr><td>CNPJ</td><td>{company.get('cnpj','')}</td></tr>
<tr><th colspan="2">BENEFICIÃRIO</th></tr>
<tr><td>Nome</td><td>{emp.get('name','')}</td></tr>
<tr><td>CPF</td><td>{emp.get('cpf','')}</td></tr>
<tr><td>PIS/PASEP</td><td>{emp.get('pis_pasep','')}</td></tr>
<tr><th colspan="2">RENDIMENTOS E DEDUÃ‡Ã•ES</th></tr>
<tr><td>Rendimentos TributÃ¡veis (SalÃ¡rios, FÃ©rias, 13Âº)</td><td style="text-align:right">R$ {total_bruto:,.2f}</td></tr>
<tr><td>(-) DeduÃ§Ãµes INSS</td><td style="text-align:right">R$ {total_inss:,.2f}</td></tr>
<tr><td>(-) IRRF Retido na Fonte</td><td style="text-align:right">R$ {total_irrf:,.2f}</td></tr>
<tr class="total"><td>Base de CÃ¡lculo LÃ­quida</td><td style="text-align:right">R$ {total_bruto-total_inss:,.2f}</td></tr>
</table>
<p style="font-size:.8em">Declaramos que as informaÃ§Ãµes acima sÃ£o fiÃ©is aos registros contÃ¡beis desta empresa.</p>
<p style="text-align:right;font-size:.75em">Emitido em {date.today().strftime('%d/%m/%Y')}</p>
</body></html>"""
    return Response(content=html, media_type="text/html")


# ─── DOCUMENTOS TRABALHISTAS ──────────────────────────────────────────────────

_DOC_CSS = """body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:20px 30px;color:#000;background:#fff;font-size:13px}
h1{text-align:center;font-size:1.1em;text-transform:uppercase;border-bottom:2px solid #000;padding-bottom:8px;margin-bottom:16px}
h2{font-size:.95em;text-transform:uppercase;margin-top:20px;margin-bottom:4px}
p{line-height:1.8;text-align:justify;margin:6px 0}
table{width:100%;border-collapse:collapse;margin:10px 0}th,td{border:1px solid #555;padding:5px 9px;font-size:.85em}
th{background:#eee;font-weight:bold}.sig{margin-top:50px;display:flex;gap:40px;flex-wrap:wrap}
.sig div{flex:1;min-width:180px;text-align:center;border-top:1px solid #000;padding-top:6px;font-size:.8em}
@media print{body{margin:0}}"""


def _get_emp_company(emp_id: int, cid: int, conn):
    emp = conn.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (emp_id, cid)).fetchone()
    if not emp:
        conn.close()
        raise HTTPException(404, "Funcionário não encontrado")
    emp = dict(emp)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    return emp, company


def _fmt(v): return str(v) if v else ""
def _brl(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"


@router.get("/employees/{emp_id}/documento/contrato")
def gerar_contrato(
    emp_id: int,
    tipo: str = Query(default="experiencia", pattern="^(experiencia|indeterminado)$"),
    current_user=Depends(get_current_user)
):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    emp, co = _get_emp_company(emp_id, cid, conn)
    conn.close()
    today = date.today()
    adm = emp.get("admission_date", str(today))
    try:
        adm_dt = datetime.strptime(adm[:10], "%Y-%m-%d").date()
    except Exception:
        adm_dt = today
    adm_ext = adm_dt.strftime("%d/%m/%Y")
    today_ext = today.strftime("%d/%m/%Y")
    cidade = co.get("cidade", "___________") or "___________"
    uf = co.get("uf", "__") or "__"

    if tipo == "experiencia":
        prazo_bloco = f"""<h2>CLÁUSULA 2ª — PRAZO</h2>
<p>O presente contrato é por prazo determinado, na modalidade CONTRATO DE EXPERIÊNCIA, nos termos do art. 443, § 2º, "c" da CLT, com duração inicial de <b>45 (quarenta e cinco) dias</b> contados de {adm_ext}, podendo ser prorrogado por mais <b>45 (quarenta e cinco) dias</b>, totalizando o prazo máximo de 90 (noventa) dias.</p>
<p>Caso o EMPREGADO continue prestando serviços após o término do prazo sem manifestação das partes, o contrato converter-se-á automaticamente em contrato por prazo indeterminado.</p>"""
    else:
        prazo_bloco = f"""<h2>CLÁUSULA 2ª — PRAZO</h2>
<p>O presente contrato é por prazo <b>INDETERMINADO</b>, nos termos da Consolidação das Leis do Trabalho, com início em {adm_ext}.</p>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Contrato de Trabalho</title>
<style>{_DOC_CSS}</style></head><body>
<h1>Contrato Individual de Trabalho — {"Experiência" if tipo=="experiencia" else "Prazo Indeterminado"}</h1>
<p>Pelo presente instrumento particular, de um lado:</p>
<p><b>EMPREGADOR:</b> {_fmt(co.get("razao_social"))} — CNPJ: {_fmt(co.get("cnpj"))} — Endereço: {_fmt(co.get("logradouro"))}, {_fmt(co.get("numero"))}, {_fmt(co.get("bairro"))}, {_fmt(co.get("cidade"))}/{_fmt(co.get("uf"))};</p>
<p>e, de outro lado:</p>
<p><b>EMPREGADO(A):</b> {_fmt(emp.get("name"))} — CPF: {_fmt(emp.get("cpf"))} — RG: {_fmt(emp.get("rg"))} — PIS/PASEP: {_fmt(emp.get("pis_pasep"))} — Endereço: {_fmt(emp.get("address"))};</p>
<p>Resolvem celebrar o presente Contrato Individual de Trabalho, regido pela Consolidação das Leis do Trabalho (CLT) e demais legislações aplicáveis, mediante as seguintes cláusulas e condições:</p>

<h2>CLÁUSULA 1ª — FUNÇÃO E LOCAL</h2>
<p>O(A) EMPREGADO(A) é contratado(a) para exercer a função de <b>{_fmt(emp.get("role"))}</b> (CBO {_fmt(emp.get("cbo"))}), no departamento <b>{_fmt(emp.get("department"))}</b>, no estabelecimento do EMPREGADOR acima qualificado, podendo ser transferido(a) para outro local conforme necessidade da empresa, observado o art. 469 da CLT.</p>

{prazo_bloco}

<h2>CLÁUSULA 3ª — REMUNERAÇÃO</h2>
<p>O(A) EMPREGADO(A) perceberá salário mensal de <b>{_brl(emp.get("salary"))}</b>, pago até o 5º dia útil do mês subsequente ao trabalhado, mediante crédito em conta-corrente ou outro meio acordado entre as partes.</p>

<h2>CLÁUSULA 4ª — JORNADA DE TRABALHO</h2>
<p>A jornada de trabalho será de <b>44 (quarenta e quatro) horas semanais</b>, distribuídas de segunda a sexta-feira, nos horários definidos pelo EMPREGADOR, respeitados os limites legais e os intervalos previstos na CLT.</p>

<h2>CLÁUSULA 5ª — DISPOSIÇÕES GERAIS</h2>
<p>O(A) EMPREGADO(A) se compromete a cumprir as normas internas, regulamentos e ordens de serviço do EMPREGADOR, guardar sigilo sobre informações confidenciais e zelar pelo patrimônio da empresa. O descumprimento das obrigações contratuais sujeitará o infrator às penalidades previstas em lei.</p>
<p>Declaram as partes que leram e concordam com todas as cláusulas deste contrato, firmando-o em 2 (duas) vias de igual teor e forma.</p>

<p style="text-align:right">{cidade}/{uf}, {today_ext}.</p>

<div class="sig">
  <div>{_fmt(co.get("razao_social"))}<br>EMPREGADOR</div>
  <div>{_fmt(emp.get("name"))}<br>EMPREGADO(A)</div>
  <div>Testemunha 1:<br><br>CPF: _______________</div>
  <div>Testemunha 2:<br><br>CPF: _______________</div>
</div>
</body></html>"""
    return Response(content=html, media_type="text/html")


@router.get("/employees/{emp_id}/documento/ficha-registro")
def gerar_ficha_registro(emp_id: int, current_user=Depends(get_current_user)):
    """Ficha de Registro de Empregado (art. 41 da CLT) para imprimir ou salvar em PDF."""
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    emp, co = _get_emp_company(emp_id, cid, conn)
    deps = [dict(r) for r in conn.execute(
        "SELECT * FROM employee_dependents WHERE employee_id=? AND company_id=? ORDER BY id",
        (emp_id, cid)).fetchall()]
    conn.close()
    return Response(content=gerar_ficha_registro_html(emp, co, deps), media_type="text/html")


@router.get("/employees/{emp_id}/documento/advertencia")
def gerar_advertencia(
    emp_id: int,
    motivo: str = Query(default=""),
    data_ocorrencia: str = Query(default=""),
    current_user=Depends(get_current_user)
):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    emp, co = _get_emp_company(emp_id, cid, conn)
    conn.close()
    today = date.today()
    cidade = co.get("cidade", "___________") or "___________"
    uf = co.get("uf", "__") or "__"
    data_oc = data_ocorrencia or today.strftime("%d/%m/%Y")
    motivo_txt = motivo or "_______________________________________________"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Carta de Advertência</title>
<style>{_DOC_CSS}</style></head><body>
<h1>Carta de Advertência</h1>
<p style="text-align:right">{cidade}/{uf}, {today.strftime("%d/%m/%Y")}.</p>
<p><b>Ao(À) Sr.(a):</b> {_fmt(emp.get("name"))}<br>
<b>Cargo:</b> {_fmt(emp.get("role"))} — <b>Depto:</b> {_fmt(emp.get("department"))}<br>
<b>Matrícula:</b> {_fmt(emp.get("matricula"))} — <b>CPF:</b> {_fmt(emp.get("cpf"))}</p>

<p>Comunicamos que, em <b>{data_oc}</b>, V.Sa. incorreu na seguinte irregularidade:</p>
<p style="border-left:3px solid #555;padding-left:12px;margin:12px 0"><i>{motivo_txt}</i></p>

<p>Tal conduta contraria as normas internas desta empresa, bem como os deveres previstos nos arts. 482 e 483 da CLT e na Convenção Coletiva de Trabalho vigente.</p>
<p>Em decorrência, aplicamos a presente <b>ADVERTÊNCIA ESCRITA</b>, alertando que a reincidência ou o cometimento de nova infração poderá ensejar penalidade mais grave, incluindo <b>suspensão disciplinar</b> ou até <b>dispensa por justa causa</b>, conforme a gravidade e a reiteração do ato.</p>
<p>Solicitamos que V.Sa. assine o presente documento em sinal de ciência, sem que isso implique concordância com o seu conteúdo.</p>

<div class="sig" style="margin-top:40px">
  <div>{_fmt(co.get("razao_social"))}<br>EMPREGADOR</div>
  <div>{_fmt(emp.get("name"))}<br>EMPREGADO(A) — Ciente em: ___/___/______</div>
  <div>Testemunha:<br><br>CPF: _______________</div>
</div>
<p style="margin-top:30px;font-size:.8em">( ) Recusa-se a assinar. Testemunhas: _____________________ e _____________________</p>
</body></html>"""
    return Response(content=html, media_type="text/html")


@router.get("/employees/{emp_id}/documento/suspensao")
def gerar_suspensao(
    emp_id: int,
    motivo: str = Query(default=""),
    data_ocorrencia: str = Query(default=""),
    dias: int = Query(default=1, ge=1, le=30),
    current_user=Depends(get_current_user)
):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    emp, co = _get_emp_company(emp_id, cid, conn)
    conn.close()
    today = date.today()
    cidade = co.get("cidade", "___________") or "___________"
    uf = co.get("uf", "__") or "__"
    data_oc = data_ocorrencia or today.strftime("%d/%m/%Y")
    motivo_txt = motivo or "_______________________________________________"
    try:
        inicio_dt = datetime.strptime(data_ocorrencia[:10], "%Y-%m-%d").date() if data_ocorrencia else today
    except Exception:
        inicio_dt = today
    fim_dt = inicio_dt + timedelta(days=dias - 1)
    desconto = float(emp.get("salary", 0)) / 30 * dias

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Carta de Suspensão</title>
<style>{_DOC_CSS}</style></head><body>
<h1>Carta de Suspensão Disciplinar</h1>
<p style="text-align:right">{cidade}/{uf}, {today.strftime("%d/%m/%Y")}.</p>
<p><b>Ao(À) Sr.(a):</b> {_fmt(emp.get("name"))}<br>
<b>Cargo:</b> {_fmt(emp.get("role"))} — <b>Depto:</b> {_fmt(emp.get("department"))}<br>
<b>Matrícula:</b> {_fmt(emp.get("matricula"))} — <b>CPF:</b> {_fmt(emp.get("cpf"))}</p>

<p>Em razão da infração praticada em <b>{data_oc}</b>:</p>
<p style="border-left:3px solid #555;padding-left:12px;margin:12px 0"><i>{motivo_txt}</i></p>

<p>E considerando o histórico disciplinar de V.Sa., aplicamos a presente <b>SUSPENSÃO DISCIPLINAR de {dias} ({_escreve_dias(dias)}) dia(s)</b>, com base no art. 474 da CLT.</p>
<p>O período de suspensão compreende de <b>{inicio_dt.strftime("%d/%m/%Y")}</b> a <b>{fim_dt.strftime("%d/%m/%Y")}</b>, durante o qual V.Sa. não deverá comparecer ao trabalho, acarretando desconto proporcional de <b>{_brl(desconto)}</b> no salário do mês.</p>
<p>Alertamos que a reincidência em infrações poderá ensejar <b>dispensa por justa causa</b>, nos termos do art. 482 da CLT.</p>
<p>Solicitamos a assinatura em sinal de ciência.</p>

<div class="sig" style="margin-top:40px">
  <div>{_fmt(co.get("razao_social"))}<br>EMPREGADOR</div>
  <div>{_fmt(emp.get("name"))}<br>EMPREGADO(A) — Ciente em: ___/___/______</div>
  <div>Testemunha:<br><br>CPF: _______________</div>
</div>
<p style="margin-top:30px;font-size:.8em">( ) Recusa-se a assinar. Testemunhas: _____________________ e _____________________</p>
</body></html>"""
    return Response(content=html, media_type="text/html")


def _escreve_dias(n: int) -> str:
    nums = {1:"um",2:"dois",3:"três",4:"quatro",5:"cinco",6:"seis",7:"sete",8:"oito",9:"nove",10:"dez",
            15:"quinze",20:"vinte",30:"trinta"}
    return nums.get(n, str(n))


@router.get("/employees/{emp_id}/documento/quitacao-anual")
def gerar_quitacao_anual(
    emp_id: int,
    ano: int = Query(default=0),
    current_user=Depends(get_current_user)
):
    cid = current_user.get("company_id", 1)
    if not ano:
        ano = date.today().year - 1
    conn = get_conn()
    emp, co = _get_emp_company(emp_id, cid, conn)
    conn.close()
    today = date.today()
    cidade = co.get("cidade", "___________") or "___________"
    uf = co.get("uf", "__") or "__"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Carta-Quitação Anual</title>
<style>{_DOC_CSS}</style></head><body>
<h1>Termo de Quitação Anual de Obrigações Trabalhistas<br>
<small style="font-size:.8em">Art. 507-B da Consolidação das Leis do Trabalho</small></h1>

<p>Pelo presente instrumento, de um lado <b>{_fmt(co.get("razao_social"))}</b>, CNPJ nº {_fmt(co.get("cnpj"))}, doravante denominado <b>EMPREGADOR</b>; e de outro lado <b>{_fmt(emp.get("name"))}</b>, CPF nº {_fmt(emp.get("cpf"))}, Matrícula {_fmt(emp.get("matricula"))}, cargo <b>{_fmt(emp.get("role"))}</b>, doravante denominado <b>EMPREGADO(A)</b>;</p>

<p>Declaram, para todos os fins de direito, que no ano de <b>{ano}</b>, todas as obrigações trabalhistas referentes às seguintes verbas foram integralmente cumpridas:</p>

<table>
  <tr><th>#</th><th>Verba / Obrigação</th><th>Situação</th></tr>
  <tr><td>1</td><td>Salários mensais (jan a dez/{ano})</td><td>Quitado</td></tr>
  <tr><td>2</td><td>13º Salário — 1ª e 2ª parcelas</td><td>Quitado</td></tr>
  <tr><td>3</td><td>Férias gozadas e/ou convertidas em pecúnia</td><td>Quitado</td></tr>
  <tr><td>4</td><td>FGTS — depósitos mensais do exercício</td><td>Quitado</td></tr>
  <tr><td>5</td><td>Vale-transporte / Vale-refeição / Benefícios convencionados</td><td>Quitado</td></tr>
  <tr><td>6</td><td>Horas extras, adicional noturno e demais adicionais legais</td><td>Quitado</td></tr>
  <tr><td>7</td><td>Contribuição Previdenciária (INSS — cota empregado)</td><td>Descontado e recolhido</td></tr>
  <tr><td>8</td><td>Imposto de Renda Retido na Fonte (IRRF)</td><td>Descontado e recolhido</td></tr>
</table>

<p>O(A) EMPREGADO(A) declara que não possui qualquer crédito ou reclamação perante o EMPREGADOR referente ao período acima mencionado, sem prejuízo de eventuais parcelas vincendas decorrentes do contrato de trabalho vigente.</p>
<p>Este termo é firmado voluntariamente por ambas as partes, nos termos do art. 507-B da CLT, com fins meramente declaratórios, não implicando novação ou quitação de parcelas não expressamente discriminadas.</p>
<p>Firmado perante o sindicato da categoria, conforme exigência legal.</p>

<p style="text-align:right;margin-top:20px">{cidade}/{uf}, {today.strftime("%d/%m/%Y")}.</p>

<div class="sig">
  <div>{_fmt(co.get("razao_social"))}<br>EMPREGADOR</div>
  <div>{_fmt(emp.get("name"))}<br>EMPREGADO(A)</div>
  <div>Representante Sindical<br><br>CPF: _______________</div>
</div>
</body></html>"""
    return Response(content=html, media_type="text/html")


@router.get("/documento/ferias-coletivas")
def gerar_recibo_ferias_coletivas(
    inicio: str = Query(...),
    fim: str = Query(...),
    departamento: str = Query(default=""),
    current_user=Depends(get_current_user)
):
    cid = current_user.get("company_id", 1)
    conn = get_conn()
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})
    q = "SELECT * FROM employees WHERE company_id=? AND active=1"
    params = [cid]
    if departamento:
        q += " AND department=?"
        params.append(departamento)
    empregados = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    today = date.today()
    cidade = company.get("cidade", "___________") or "___________"
    uf = company.get("uf", "__") or "__"
    try:
        inicio_dt = datetime.strptime(inicio[:10], "%Y-%m-%d").date()
        fim_dt = datetime.strptime(fim[:10], "%Y-%m-%d").date()
        dias = (fim_dt - inicio_dt).days + 1
        inicio_ext = inicio_dt.strftime("%d/%m/%Y")
        fim_ext = fim_dt.strftime("%d/%m/%Y")
    except Exception:
        dias = 0; inicio_ext = inicio; fim_ext = fim

    linhas = "".join(
        f"<tr><td>{i+1}</td><td>{e.get('name','')}</td><td>{e.get('cpf','')}</td>"
        f"<td>{e.get('role','')}</td><td>{_brl(e.get('salary',0))}</td>"
        f"<td style='text-align:center'>___/___/______</td></tr>"
        for i, e in enumerate(empregados)
    )
    dept_txt = f" — Departamento: {departamento}" if departamento else ""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Recibo Férias Coletivas</title>
<style>{_DOC_CSS}</style></head><body>
<h1>Recibo de Férias Coletivas{dept_txt}</h1>
<p><b>EMPRESA:</b> {_fmt(company.get("razao_social"))} — CNPJ: {_fmt(company.get("cnpj"))}</p>
<p>Comunicamos que nos termos do art. 139 da CLT, foram concedidas <b>FÉRIAS COLETIVAS</b> aos empregados abaixo relacionados, pelo período de <b>{inicio_ext} a {fim_ext} ({dias} dias corridos)</b>.</p>

<table>
  <tr><th>#</th><th>Nome</th><th>CPF</th><th>Cargo</th><th>Salário Base</th><th>Assinatura / Data Ciência</th></tr>
  {linhas if linhas else '<tr><td colspan="6" style="text-align:center">Nenhum funcionário encontrado</td></tr>'}
</table>

<p style="font-size:.8em;margin-top:8px">Período aquisitivo considera o início da concessão como data de referência. O pagamento das férias, acrescido de 1/3 constitucional, foi efetuado até 2 dias antes do início do período, conforme art. 145 da CLT.</p>

<p style="text-align:right;margin-top:20px">{cidade}/{uf}, {today.strftime("%d/%m/%Y")}.</p>
<div class="sig">
  <div>{_fmt(company.get("razao_social"))}<br>Representante da Empresa</div>
  <div>Visto do Sindicato da Categoria<br><br>Data: ___/___/______</div>
</div>
</body></html>"""
    return Response(content=html, media_type="text/html")


# ─── RELATÓRIOS GERENCIAIS ────────────────────────────────────────────────────

def _calc_inss_simples(gross: float) -> float:
    brackets = [(1412.00, 0.075), (2666.68, 0.090), (4000.03, 0.120), (7786.02, 0.140)]
    total, prev = 0.0, 0.0
    for limit, rate in brackets:
        if gross <= 0:
            break
        base = min(gross, limit) - prev
        if base <= 0:
            break
        total += base * rate
        prev = limit
        if gross <= limit:
            break
    return min(total, 908.86)


@router.get("/relatorios/custo-funcionario")
def relatorio_custo_funcionario(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Custo total por funcionário: salário + encargos patronais + benefícios + provisões."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    employees = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id = ? AND active = 1 ORDER BY name",
        (company_id,)
    ).fetchall())

    benefits_raw = rows_to_dicts(conn.execute(
        """SELECT eb.employee_id, COALESCE(SUM(eb.valor_bruto), 0) as total_empresa
           FROM employee_benefits eb
           WHERE eb.company_id = ? AND eb.ativo = 1
           GROUP BY eb.employee_id""",
        (company_id,)
    ).fetchall())
    ben_map = {b["employee_id"]: b["total_empresa"] for b in benefits_raw}
    conn.close()

    result = []
    total_bruto = total_custo = 0.0

    for emp in employees:
        salary = float(emp.get("salary") or 0)
        is_prl = bool(emp.get("is_prolabore"))

        inss_patronal = round(salary * 0.11 if is_prl else salary * 0.20, 2)
        fgts = round(salary * 0.08 if not is_prl else 0, 2)
        rat = round(salary * 0.01 if not is_prl else 0, 2)
        terceiros = round(salary * 0.058 if not is_prl else 0, 2)
        beneficios = round(float(ben_map.get(emp["id"], 0)), 2)
        prov_decimo = round(salary / 12, 2)
        prov_ferias = round((salary / 12) * (4 / 3), 2)
        custo_total = round(
            salary + inss_patronal + fgts + rat + terceiros + beneficios + prov_decimo + prov_ferias, 2
        )

        total_bruto += salary
        total_custo += custo_total

        result.append({
            "id": emp["id"],
            "name": emp["name"],
            "role": emp.get("role", ""),
            "department": emp.get("department", ""),
            "salary": salary,
            "inss_patronal": inss_patronal,
            "fgts": fgts,
            "rat": rat,
            "terceiros": terceiros,
            "beneficios": beneficios,
            "prov_decimo": prov_decimo,
            "prov_ferias": prov_ferias,
            "custo_total": custo_total,
            "multiplicador": round(custo_total / salary, 2) if salary else 0,
        })

    return {
        "employees": result,
        "totais": {
            "total_salarios": round(total_bruto, 2),
            "total_custo": round(total_custo, 2),
            "multiplicador_medio": round(total_custo / total_bruto, 2) if total_bruto else 0,
        },
    }


@router.get("/relatorios/provisoes")
def relatorio_provisoes(
    competencia: str = Query(default=""),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Provisões mensais: 13º + férias + encargos sobre férias."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    if not competencia:
        competencia = date.today().strftime("%Y-%m")

    try:
        ref_date = date.fromisoformat(competencia + "-01")
    except ValueError:
        raise HTTPException(status_code=400, detail="Competência inválida. Use YYYY-MM.")

    employees = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id = ? AND active = 1 ORDER BY name",
        (company_id,)
    ).fetchall())
    conn.close()

    result = []
    tot_decimo = tot_ferias = tot_inss_ferias = tot_fgts_ferias = tot_fgts_decimo = 0.0

    for emp in employees:
        salary = float(emp.get("salary") or 0)
        is_prl = bool(emp.get("is_prolabore"))
        try:
            adm = date.fromisoformat(emp["admission_date"][:10])
        except (ValueError, TypeError):
            adm = ref_date

        meses = ref_date.month if adm.year == ref_date.year else 12
        meses = max(1, min(12, meses))

        prov_decimo = round(salary * meses / 12, 2)
        prov_ferias_base = round(salary * meses / 12, 2)
        prov_ferias_terco = round(prov_ferias_base / 3, 2)
        prov_ferias_total = round(prov_ferias_base + prov_ferias_terco, 2)

        inss_ferias = round(_calc_inss_simples(prov_ferias_base), 2) if not is_prl else 0.0
        fgts_ferias = round(prov_ferias_total * 0.08, 2) if not is_prl else 0.0
        fgts_decimo = round(prov_decimo * 0.08, 2) if not is_prl else 0.0

        tot_decimo += prov_decimo
        tot_ferias += prov_ferias_total
        tot_inss_ferias += inss_ferias
        tot_fgts_ferias += fgts_ferias
        tot_fgts_decimo += fgts_decimo

        result.append({
            "id": emp["id"],
            "name": emp["name"],
            "department": emp.get("department", ""),
            "salary": salary,
            "meses": meses,
            "prov_decimo": prov_decimo,
            "prov_ferias_base": prov_ferias_base,
            "prov_ferias_terco": prov_ferias_terco,
            "prov_ferias_total": prov_ferias_total,
            "inss_ferias": inss_ferias,
            "fgts_ferias": fgts_ferias,
            "fgts_decimo": fgts_decimo,
            "total_provisao": round(
                prov_decimo + prov_ferias_total + inss_ferias + fgts_ferias + fgts_decimo, 2
            ),
        })

    return {
        "competencia": competencia,
        "employees": result,
        "totais": {
            "prov_decimo": round(tot_decimo, 2),
            "prov_ferias": round(tot_ferias, 2),
            "inss_ferias": round(tot_inss_ferias, 2),
            "fgts_ferias": round(tot_fgts_ferias, 2),
            "fgts_decimo": round(tot_fgts_decimo, 2),
            "total": round(tot_decimo + tot_ferias + tot_inss_ferias + tot_fgts_ferias + tot_fgts_decimo, 2),
        },
    }


@router.get("/relatorios/folha-analitica")
def relatorio_folha_analitica(
    competencia: str = Query(default=""),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Folha analítica por competência."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    if not competencia:
        competencia = date.today().strftime("%Y-%m")

    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id = ? AND competence = ? AND COALESCE(tipo, 'mensal') = 'mensal' ORDER BY id DESC LIMIT 1",
        (company_id, competencia)
    ).fetchone()

    if not run:
        conn.close()
        return {"competencia": competencia, "run": None, "items": [], "totais": {}}

    run = dict(run)
    items_raw = rows_to_dicts(conn.execute(
        """SELECT pi.*, e.name, e.role, e.department, e.cpf, e.matricula
           FROM payroll_items pi
           JOIN employees e ON e.id = pi.employee_id
           WHERE pi.run_id = ?
           ORDER BY e.name""",
        (run["id"],)
    ).fetchall())
    conn.close()

    items = []
    for it in items_raw:
        total_descontos = sum([
            float(it.get("inss") or 0),
            float(it.get("irrf") or 0),
            float(it.get("vt_discount") or 0),
            float(it.get("other_discounts") or 0),
        ])
        items.append({
            "employee_id": it["employee_id"],
            "name": it["name"],
            "cpf": it.get("cpf", ""),
            "matricula": it.get("matricula", ""),
            "role": it.get("role", ""),
            "department": it.get("department", ""),
            "proventos": {
                "salario_base": float(it.get("gross_salary") or 0),
                "total": float(it.get("gross_salary") or 0),
            },
            "descontos": {
                "inss": float(it.get("inss") or 0),
                "irrf": float(it.get("irrf") or 0),
                "vt": float(it.get("vt_discount") or 0),
                "outros": float(it.get("other_discounts") or 0),
                "total": round(total_descontos, 2),
            },
            "liquido": float(it.get("net_salary") or 0),
            "fgts": float(it.get("fgts") or 0),
        })

    totais = {
        "total_bruto": round(sum(i["proventos"]["total"] for i in items), 2),
        "total_inss": round(sum(i["descontos"]["inss"] for i in items), 2),
        "total_irrf": round(sum(i["descontos"]["irrf"] for i in items), 2),
        "total_vt": round(sum(i["descontos"]["vt"] for i in items), 2),
        "total_descontos": round(sum(i["descontos"]["total"] for i in items), 2),
        "total_liquido": round(sum(i["liquido"] for i in items), 2),
        "total_fgts": round(sum(i["fgts"] for i in items), 2),
    }

    return {"competencia": competencia, "run": run, "items": items, "totais": totais}


@router.get("/relatorios/mapa-lotacao")
def relatorio_mapa_lotacao(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Headcount por departamento e cargo."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    all_employees = rows_to_dicts(conn.execute(
        "SELECT name, role, department, salary, active FROM employees WHERE company_id = ? ORDER BY name",
        (company_id,)
    ).fetchall())
    conn.close()

    from collections import defaultdict
    dept_map: dict = defaultdict(lambda: {"ativos": 0, "inativos": 0, "total_salary": 0.0})

    for emp in all_employees:
        dept = emp.get("department") or "Sem Departamento"
        salary = float(emp.get("salary") or 0)
        if emp.get("active"):
            dept_map[dept]["ativos"] += 1
            dept_map[dept]["total_salary"] += salary
        else:
            dept_map[dept]["inativos"] += 1

    total_ativos = sum(d["ativos"] for d in dept_map.values())

    departamentos = []
    for dept, data in sorted(dept_map.items()):
        ativos = data["ativos"]
        media_sal = round(data["total_salary"] / ativos, 2) if ativos else 0
        departamentos.append({
            "departamento": dept,
            "ativos": ativos,
            "inativos": data["inativos"],
            "total": ativos + data["inativos"],
            "media_salarial": media_sal,
            "percent_headcount": round(ativos / total_ativos * 100, 1) if total_ativos else 0,
        })

    cargo_map: dict = defaultdict(lambda: {"ativos": 0, "total_salary": 0.0})
    for emp in all_employees:
        if emp.get("active"):
            cargo = emp.get("role") or "Sem Cargo"
            cargo_map[cargo]["ativos"] += 1
            cargo_map[cargo]["total_salary"] += float(emp.get("salary") or 0)

    cargos = sorted(
        [{"cargo": k, "ativos": v["ativos"],
          "media_salarial": round(v["total_salary"] / v["ativos"], 2) if v["ativos"] else 0}
         for k, v in cargo_map.items()],
        key=lambda x: -x["ativos"]
    )[:15]

    return {
        "total_ativos": total_ativos,
        "total_inativos": sum(d["inativos"] for d in dept_map.values()),
        "departamentos": departamentos,
        "cargos": cargos,
    }


@router.get("/relatorios/turnover")
def relatorio_turnover(
    ano: int = Query(default=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Taxa de turnover por mês: admissões e desligamentos no período."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    if not ano:
        ano = date.today().year

    all_employees = rows_to_dicts(conn.execute(
        "SELECT id, name, role, department, admission_date, termination_date, active FROM employees WHERE company_id = ?",
        (company_id,)
    ).fetchall())
    conn.close()

    meses_labels = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                    "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    admissoes_mes = [0] * 12
    demissoes_mes = [0] * 12
    admitidos_ano, demitidos_ano = [], []

    for emp in all_employees:
        try:
            adm = date.fromisoformat(emp["admission_date"][:10])
            if adm.year == ano:
                admissoes_mes[adm.month - 1] += 1
                admitidos_ano.append({"name": emp["name"], "role": emp.get("role", ""),
                                       "department": emp.get("department", ""),
                                       "data": emp["admission_date"][:10]})
        except (ValueError, TypeError):
            pass

        td = emp.get("termination_date")
        if td:
            try:
                dem = date.fromisoformat(td[:10])
                if dem.year == ano:
                    demissoes_mes[dem.month - 1] += 1
                    demitidos_ano.append({"name": emp["name"], "role": emp.get("role", ""),
                                          "department": emp.get("department", ""),
                                          "data": td[:10]})
            except (ValueError, TypeError):
                pass

    headcount_inicio = sum(
        1 for emp in all_employees
        if emp.get("admission_date") and emp["admission_date"][:4] < str(ano)
        and (emp.get("active") or (emp.get("termination_date") and emp["termination_date"][:4] >= str(ano)))
    )
    headcount_atual = sum(1 for emp in all_employees if emp.get("active"))

    total_adm = sum(admissoes_mes)
    total_dem = sum(demissoes_mes)
    headcount_medio = (headcount_inicio + headcount_atual) / 2 if (headcount_inicio + headcount_atual) > 0 else 1
    taxa_turnover = round((total_adm + total_dem) / 2 / headcount_medio * 100, 1)

    mensal = []
    for i in range(12):
        hc = headcount_inicio + sum(admissoes_mes[:i + 1]) - sum(demissoes_mes[:i + 1])
        mensal.append({
            "mes": meses_labels[i],
            "admissoes": admissoes_mes[i],
            "demissoes": demissoes_mes[i],
            "headcount_estimado": max(0, hc),
        })

    return {
        "ano": ano,
        "total_admissoes": total_adm,
        "total_demissoes": total_dem,
        "headcount_inicio_ano": headcount_inicio,
        "headcount_atual": headcount_atual,
        "taxa_turnover_anual": taxa_turnover,
        "mensal": mensal,
        "admitidos": admitidos_ano,
        "demitidos": demitidos_ano,
    }


# ─── ESOCIAL EVENTOS TABELA ───────────────────────────────────────────────────

def _get_company(conn, company_id: int) -> dict:
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    return dict(row) if row else {}


@router.get("/esocial/s1000")
def esocial_s1000(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company = _get_company(conn, current_user.get("company_id", 1))
    conn.close()
    xml = gerar_s1000(company)
    cnpj = (company.get("cnpj") or "").replace("/", "").replace(".", "").replace("-", "")[:8]
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1000_{cnpj}.xml"'})


@router.get("/esocial/s1005")
def esocial_s1005(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company = _get_company(conn, current_user.get("company_id", 1))
    conn.close()
    xml = gerar_s1005(company)
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": 'attachment; filename="S-1005.xml"'})


@router.get("/lotacoes")
def list_lotacoes(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM lotacoes_tributarias WHERE company_id = ? ORDER BY cod_lotacao",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


@router.post("/lotacoes", status_code=201)
def create_lotacao(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO lotacoes_tributarias
        (company_id, cod_lotacao, descricao, tp_lotacao, ini_valid, fim_valid, fpas, cod_terco)
        VALUES (?,?,?,?,?,?,?,?)""",
        (company_id, data.get("cod_lotacao",""), data.get("descricao",""),
         data.get("tp_lotacao","01"), data.get("ini_valid",""), data.get("fim_valid",""),
         data.get("fpas","515"), data.get("cod_terco","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/lotacoes/{lot_id}")
def update_lotacao(lot_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("""UPDATE lotacoes_tributarias SET cod_lotacao=?,descricao=?,tp_lotacao=?,
        ini_valid=?,fim_valid=?,fpas=?,cod_terco=? WHERE id=? AND company_id=?""",
        (data.get("cod_lotacao",""), data.get("descricao",""), data.get("tp_lotacao","01"),
         data.get("ini_valid",""), data.get("fim_valid",""), data.get("fpas","515"),
         data.get("cod_terco",""), lot_id, current_user.get("company_id",1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/lotacoes/{lot_id}")
def delete_lotacao(lot_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM lotacoes_tributarias WHERE id=? AND company_id=?",
                 (lot_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/esocial/s1020/{lot_id}")
def esocial_s1020(lot_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company = _get_company(conn, current_user.get("company_id", 1))
    lot = conn.execute("SELECT * FROM lotacoes_tributarias WHERE id=?", (lot_id,)).fetchone()
    conn.close()
    if not lot:
        raise HTTPException(status_code=404, detail="Lotação não encontrada.")
    xml = gerar_s1020(company, dict(lot))
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1020_lot{lot_id}.xml"'})


@router.get("/esocial/s1050/{horario_id}")
def esocial_s1050(horario_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company = _get_company(conn, current_user.get("company_id", 1))
    horario = conn.execute("SELECT * FROM work_schedules WHERE id=?", (horario_id,)).fetchone()
    conn.close()
    if not horario:
        raise HTTPException(status_code=404, detail="Horário não encontrado.")
    xml = gerar_s1050(company, dict(horario))
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1050_hor{horario_id}.xml"'})


@router.get("/processos-administrativos")
def list_processos(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM processos_administrativos WHERE company_id=? ORDER BY created_at DESC",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


@router.post("/processos-administrativos", status_code=201)
def create_processo(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO processos_administrativos
        (company_id, nr_proc, ind_proc, tp_proc, cod_susp, ini_valid, fim_valid, observacoes)
        VALUES (?,?,?,?,?,?,?,?)""",
        (company_id, data.get("nr_proc",""), data.get("ind_proc","1"),
         data.get("tp_proc","1"), data.get("cod_susp",""), data.get("ini_valid",""),
         data.get("fim_valid",""), data.get("observacoes","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/processos-administrativos/{proc_id}")
def update_processo(proc_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("""UPDATE processos_administrativos SET nr_proc=?,ind_proc=?,tp_proc=?,
        cod_susp=?,ini_valid=?,fim_valid=?,observacoes=? WHERE id=? AND company_id=?""",
        (data.get("nr_proc",""), data.get("ind_proc","1"), data.get("tp_proc","1"),
         data.get("cod_susp",""), data.get("ini_valid",""), data.get("fim_valid",""),
         data.get("observacoes",""), proc_id, current_user.get("company_id",1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/processos-administrativos/{proc_id}")
def delete_processo(proc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM processos_administrativos WHERE id=? AND company_id=?",
                 (proc_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/esocial/s1070/{proc_id}")
def esocial_s1070(proc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company = _get_company(conn, current_user.get("company_id", 1))
    proc = conn.execute("SELECT * FROM processos_administrativos WHERE id=?", (proc_id,)).fetchone()
    conn.close()
    if not proc:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    xml = gerar_s1070(company, dict(proc))
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-1070_proc{proc_id}.xml"'})


@router.get("/esocial/exclusoes")
def list_exclusoes(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM esocial_exclusoes WHERE company_id=? ORDER BY created_at DESC",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


@router.post("/esocial/s3000")
def esocial_s3000(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = _get_company(conn, company_id)
    evento_tipo = data.get("evento_tipo", "")
    evento_id = data.get("evento_id", "")
    motivo = data.get("motivo", "")
    xml = gerar_s3000(company, evento_tipo, evento_id, motivo)
    conn.execute("""INSERT INTO esocial_exclusoes (company_id, evento_tipo, evento_id, motivo, xml_gerado)
        VALUES (?,?,?,?,?)""", (company_id, evento_tipo, evento_id, motivo, xml))
    conn.commit()
    conn.close()
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": 'attachment; filename="S-3000.xml"'})


# ─── S-5001 / S-5011 / DCTFWeb ────────────────────────────────────────────────

@router.get("/esocial/s5001/{competencia}")
def esocial_s5001(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = _get_company(conn, company_id)
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id=? AND competence=? AND COALESCE(tipo, 'mensal')='mensal' ORDER BY id DESC LIMIT 1",
        (company_id, competencia)
    ).fetchone()
    if not run:
        conn.close()
        raise HTTPException(status_code=404, detail="Folha não processada para esta competência.")
    items = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_items WHERE run_id=?", (dict(run)["id"],)
    ).fetchall())
    conn.close()
    xml = gerar_s5001(company, competencia, items)
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-5001_{competencia}.xml"'})


@router.get("/esocial/s5011/{competencia}")
def esocial_s5011(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = _get_company(conn, company_id)
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id=? AND competence=? AND COALESCE(tipo, 'mensal')='mensal' ORDER BY id DESC LIMIT 1",
        (company_id, competencia)
    ).fetchone()
    if not run:
        conn.close()
        raise HTTPException(status_code=404, detail="Folha não processada para esta competência.")
    items = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_items WHERE run_id=?", (dict(run)["id"],)
    ).fetchall())
    conn.close()
    xml = gerar_s5011(company, competencia, items)
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-5011_{competencia}.xml"'})


@router.get("/dctfweb/{competencia}")
def dctfweb_preview(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Preview e download dos valores para preenchimento da DCTFWeb."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = _get_company(conn, company_id)
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id=? AND competence=? AND COALESCE(tipo, 'mensal')='mensal' ORDER BY id DESC LIMIT 1",
        (company_id, competencia)
    ).fetchone()

    if not run:
        conn.close()
        return {"competencia": competencia, "run": None, "valores": {}, "linhas": []}

    run_dict = dict(run)
    items = rows_to_dicts(conn.execute(
        """SELECT pi.*, e.name, e.is_prolabore, e.salary
           FROM payroll_items pi JOIN employees e ON e.id = pi.employee_id
           WHERE pi.run_id=?""", (run_dict["id"],)
    ).fetchall())
    conn.close()

    clt_items = [i for i in items if not i.get("is_prolabore")]
    prl_items = [i for i in items if i.get("is_prolabore")]

    bc_clt = sum(float(i.get("gross_salary", 0)) for i in clt_items)
    bc_prl = sum(float(i.get("gross_salary", 0)) for i in prl_items)
    inss_empregado = sum(float(i.get("inss", 0)) for i in items)
    inss_patronal = round(bc_clt * 0.20 + bc_prl * 0.11, 2)
    rat = round(bc_clt * 0.01, 2)
    terceiros = round(bc_clt * 0.058, 2)
    total_recolher = round(inss_empregado + inss_patronal + rat + terceiros, 2)

    linhas = [
        {"codigo": "2100-0", "descricao": "INSS Empregado (descontado na folha)", "valor": round(inss_empregado, 2)},
        {"codigo": "2100-1", "descricao": "INSS Patronal CLT (20%)", "valor": round(bc_clt * 0.20, 2)},
        {"codigo": "2100-2", "descricao": "INSS Pró-labore (11%)", "valor": round(bc_prl * 0.11, 2)},
        {"codigo": "2100-3", "descricao": "RAT Ajustado (1%)", "valor": rat},
        {"codigo": "2100-4", "descricao": "Terceiros / Sistema S (5,8%)", "valor": terceiros},
    ]

    return {
        "competencia": competencia,
        "company": {"razao_social": company.get("razao_social",""), "cnpj": company.get("cnpj","")},
        "run": run_dict,
        "valores": {
            "bc_clt": round(bc_clt, 2),
            "bc_prolabore": round(bc_prl, 2),
            "inss_empregado": round(inss_empregado, 2),
            "inss_patronal": inss_patronal,
            "rat": rat,
            "terceiros": terceiros,
            "total_recolher": total_recolher,
            "fgts": round(run_dict.get("total_fgts", 0), 2),
        },
        "linhas": linhas,
    }


# ─── COMPLIANCE — ESTABILIDADES ───────────────────────────────────────────────

@router.get("/estabilidades")
def list_estabilidades(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        """SELECT es.*, e.name as employee_name, e.role, e.department
           FROM employee_stability es
           JOIN employees e ON e.id = es.employee_id
           WHERE es.company_id=? ORDER BY es.data_fim_estabilidade""",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    today = date.today().isoformat()
    for r in rows:
        r["vencida"] = (r.get("data_fim_estabilidade") or "") < today
        r["dias_restantes"] = max(0, (
            date.fromisoformat(r["data_fim_estabilidade"][:10]) - date.today()
        ).days) if r.get("data_fim_estabilidade") else 0
    return rows


@router.post("/estabilidades", status_code=201)
def create_estabilidade(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""INSERT INTO employee_stability
        (company_id, employee_id, tipo, data_inicio, data_fim_estabilidade, data_referencia, observacoes)
        VALUES (?,?,?,?,?,?,?)""",
        (company_id, data.get("employee_id"), data.get("tipo",""),
         data.get("data_inicio",""), data.get("data_fim_estabilidade",""),
         data.get("data_referencia",""), data.get("observacoes","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/estabilidades/{stab_id}")
def update_estabilidade(stab_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("""UPDATE employee_stability SET tipo=?,data_inicio=?,data_fim_estabilidade=?,
        data_referencia=?,observacoes=?,ativo=? WHERE id=? AND company_id=?""",
        (data.get("tipo",""), data.get("data_inicio",""), data.get("data_fim_estabilidade",""),
         data.get("data_referencia",""), data.get("observacoes",""), data.get("ativo",1),
         stab_id, current_user.get("company_id",1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/estabilidades/{stab_id}")
def delete_estabilidade(stab_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM employee_stability WHERE id=? AND company_id=?",
                 (stab_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/alertas/contratos-experiencia")
def alertas_contratos_experiencia(
    dias: int = Query(default=30),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Funcionários com contrato de experiência vencendo nos próximos N dias."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    employees = rows_to_dicts(conn.execute(
        "SELECT * FROM employees WHERE company_id=? AND active=1 AND esocial_category='101' ORDER BY admission_date",
        (company_id,)
    ).fetchall())
    conn.close()

    today = date.today()
    result = []
    for emp in employees:
        try:
            adm = date.fromisoformat(emp["admission_date"][:10])
        except (ValueError, TypeError):
            continue
        # contrato experiência: 45 dias prorrogável por mais 45 = 90 dias total
        venc_1 = adm + timedelta(days=45)
        venc_2 = adm + timedelta(days=90)
        fase = None
        dias_venc = None
        if today <= venc_1:
            dias_venc = (venc_1 - today).days
            fase = "1ª prorrogação (45 dias)"
        elif today <= venc_2:
            dias_venc = (venc_2 - today).days
            fase = "Término definitivo (90 dias)"
        if fase is not None and dias_venc <= dias:
            result.append({
                "id": emp["id"],
                "name": emp["name"],
                "role": emp.get("role",""),
                "department": emp.get("department",""),
                "admission_date": emp["admission_date"][:10],
                "fase": fase,
                "data_vencimento": venc_1.isoformat() if "1ª" in fase else venc_2.isoformat(),
                "dias_restantes": dias_venc,
                "urgente": dias_venc <= 7,
            })
    result.sort(key=lambda x: x["dias_restantes"])
    return result


@router.get("/alertas")
def dashboard_alertas(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Dashboard de compliance: estabilidades ativas + contratos vencendo."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    today = date.today().isoformat()

    stabs = rows_to_dicts(conn.execute(
        """SELECT es.*, e.name as employee_name FROM employee_stability es
           JOIN employees e ON e.id = es.employee_id
           WHERE es.company_id=? AND es.data_fim_estabilidade >= ? AND es.ativo=1
           ORDER BY es.data_fim_estabilidade LIMIT 10""",
        (company_id, today)
    ).fetchall())

    # contratos experiência vencendo em 30 dias
    clt_employees = rows_to_dicts(conn.execute(
        "SELECT id,name,role,admission_date FROM employees WHERE company_id=? AND active=1 AND esocial_category='101'",
        (company_id,)
    ).fetchall())
    today_dt = date.today()
    contratos_alerta = []
    for emp in clt_employees:
        try:
            adm = date.fromisoformat(emp["admission_date"][:10])
            venc = adm + timedelta(days=90)
            dias_rest = (venc - today_dt).days
            if 0 <= dias_rest <= 30:
                contratos_alerta.append({"name": emp["name"], "dias_restantes": dias_rest})
        except (ValueError, TypeError):
            pass

    # CCT ativas
    cct_ativas = conn.execute(
        "SELECT COUNT(*) as n FROM cct_assistencial WHERE company_id=? AND ativo=1", (company_id,)
    ).fetchone()

    conn.close()
    return {
        "estabilidades_ativas": len(stabs),
        "estabilidades": stabs[:5],
        "contratos_vencendo": len(contratos_alerta),
        "contratos": contratos_alerta[:5],
        "cct_ativas": dict(cct_ativas)["n"] if cct_ativas else 0,
    }


# ─── CCT CONTRIBUIÇÃO ASSISTENCIAL ────────────────────────────────────────────

@router.get("/cct-assistencial")
def list_cct(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM cct_assistencial WHERE company_id=? ORDER BY created_at DESC",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


@router.post("/cct-assistencial", status_code=201)
def create_cct(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO cct_assistencial
        (company_id, descricao, percentual, data_inicio, data_fim, sindicato, prazo_oposicao_dias)
        VALUES (?,?,?,?,?,?,?)""",
        (current_user.get("company_id",1), data.get("descricao",""), data.get("percentual",1.0),
         data.get("data_inicio",""), data.get("data_fim",""), data.get("sindicato",""),
         data.get("prazo_oposicao_dias",10)))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/cct-assistencial/{cct_id}")
def update_cct(cct_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("""UPDATE cct_assistencial SET descricao=?,percentual=?,data_inicio=?,data_fim=?,
        sindicato=?,prazo_oposicao_dias=?,ativo=? WHERE id=? AND company_id=?""",
        (data.get("descricao",""), data.get("percentual",1.0), data.get("data_inicio",""),
         data.get("data_fim",""), data.get("sindicato",""), data.get("prazo_oposicao_dias",10),
         data.get("ativo",1), cct_id, current_user.get("company_id",1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/cct-assistencial/{cct_id}")
def delete_cct(cct_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM cct_assistencial WHERE id=? AND company_id=?",
                 (cct_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/cct-assistencial/{cct_id}/oposicoes")
def list_oposicoes(cct_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        """SELECT co.*, e.name as employee_name FROM cct_oposicoes co
           JOIN employees e ON e.id = co.employee_id
           WHERE co.cct_id=? AND co.company_id=?""",
        (cct_id, current_user.get("company_id",1))
    ).fetchall())
    conn.close()
    return rows


@router.post("/cct-assistencial/{cct_id}/oposicao", status_code=201)
def add_oposicao(cct_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    try:
        conn.execute("""INSERT INTO cct_oposicoes (company_id, cct_id, employee_id, data_oposicao, observacoes)
            VALUES (?,?,?,?,?)""",
            (company_id, cct_id, data.get("employee_id"), data.get("data_oposicao", date.today().isoformat()),
             data.get("observacoes","")))
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="Oposição já registrada para este funcionário.")
    conn.close()
    return {"ok": True}


@router.delete("/cct-assistencial/{cct_id}/oposicao/{emp_id}")
def remove_oposicao(cct_id: int, emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM cct_oposicoes WHERE cct_id=? AND employee_id=? AND company_id=?",
                 (cct_id, emp_id, current_user.get("company_id",1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/cct-assistencial/descontos/{competencia}")
def cct_descontos_competencia(competencia: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Descontos CCT do mês excluindo funcionários com oposição registrada."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)

    cctas = rows_to_dicts(conn.execute(
        "SELECT * FROM cct_assistencial WHERE company_id=? AND ativo=1", (company_id,)
    ).fetchall())

    employees = rows_to_dicts(conn.execute(
        "SELECT id, name, role, department, salary FROM employees WHERE company_id=? AND active=1",
        (company_id,)
    ).fetchall())

    oposicoes_raw = rows_to_dicts(conn.execute(
        "SELECT cct_id, employee_id FROM cct_oposicoes WHERE company_id=?", (company_id,)
    ).fetchall())
    oposicoes = {(o["cct_id"], o["employee_id"]) for o in oposicoes_raw}
    conn.close()

    result = []
    grand_total = 0.0
    for cct in cctas:
        linhas = []
        total_cct = 0.0
        for emp in employees:
            if (cct["id"], emp["id"]) in oposicoes:
                continue
            desconto = round(float(emp["salary"]) * float(cct["percentual"]) / 100, 2)
            total_cct += desconto
            linhas.append({"employee_id": emp["id"], "name": emp["name"],
                           "salary": emp["salary"], "desconto": desconto})
        grand_total += total_cct
        result.append({"cct": cct, "linhas": linhas, "total": round(total_cct, 2)})

    return {"competencia": competencia, "contribuicoes": result, "grand_total": round(grand_total, 2)}


# ─── PCMSO ────────────────────────────────────────────────────────────────────

@router.get("/pcmso")
def list_pcmso(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM pcmso_programas WHERE company_id=? ORDER BY ano DESC",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


@router.post("/pcmso", status_code=201)
def create_pcmso(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute("""
        INSERT INTO pcmso_programas (company_id, ano, responsavel_nome, responsavel_crm,
            data_elaboracao, vigencia_inicio, vigencia_fim, observacoes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (company_id, data.get("ano", date.today().year), data.get("responsavel_nome", ""),
          data.get("responsavel_crm", ""), data.get("data_elaboracao", ""),
          data.get("vigencia_inicio", ""), data.get("vigencia_fim", ""),
          data.get("observacoes", "")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/pcmso/{prog_id}")
def update_pcmso(prog_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    fields = ["ano", "responsavel_nome", "responsavel_crm", "data_elaboracao",
              "vigencia_inicio", "vigencia_fim", "observacoes"]
    sets = [f"{f}=?" for f in fields if f in data]
    vals = [data[f] for f in fields if f in data]
    if sets:
        vals.append(prog_id)
        conn.execute(f"UPDATE pcmso_programas SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/pcmso/{prog_id}")
def delete_pcmso(prog_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM pcmso_exames_cargo WHERE programa_id=?", (prog_id,))
    conn.execute("DELETE FROM pcmso_programas WHERE id=? AND company_id=?",
                 (prog_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/pcmso/{prog_id}/exames")
def list_pcmso_exames(prog_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM pcmso_exames_cargo WHERE programa_id=? ORDER BY cargo",
        (prog_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/pcmso/{prog_id}/exames", status_code=201)
def create_pcmso_exame(prog_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute("""
        INSERT INTO pcmso_exames_cargo (company_id, programa_id, cargo, tipo_exame, periodicidade_meses, exames)
        VALUES (?,?,?,?,?,?)
    """, (company_id, prog_id, data.get("cargo", ""), data.get("tipo_exame", "periodico"),
          data.get("periodicidade_meses", 12), data.get("exames", "")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.delete("/pcmso/{prog_id}/exames/{exam_id}")
def delete_pcmso_exame(prog_id: int, exam_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM pcmso_exames_cargo WHERE id=? AND programa_id=?", (exam_id, prog_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/pcmso/{prog_id}/pendentes")
def pcmso_pendentes(prog_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    exames = rows_to_dicts(conn.execute(
        "SELECT * FROM pcmso_exames_cargo WHERE programa_id=? AND company_id=?",
        (prog_id, company_id)
    ).fetchall())
    employees = rows_to_dicts(conn.execute(
        "SELECT id, name, role FROM employees WHERE company_id=? AND active=1",
        (company_id,)
    ).fetchall())
    today = date.today()
    result = []
    for emp in employees:
        exame_cargo = next((e for e in exames if e["cargo"].lower() == (emp["role"] or "").lower()), None)
        if not exame_cargo:
            continue
        periodicidade = int(exame_cargo.get("periodicidade_meses", 12))
        ultimo_aso = conn.execute(
            "SELECT exam_date FROM medical_exams WHERE company_id=? AND employee_id=? ORDER BY exam_date DESC LIMIT 1",
            (company_id, emp["id"])
        ).fetchone()
        if ultimo_aso:
            ultimo_dt = date.fromisoformat(str(ultimo_aso[0])[:10])
            venc = ultimo_dt + timedelta(days=periodicidade * 30)
            dias_atraso = (today - venc).days
            if dias_atraso > -30:
                result.append({
                    "employee_id": emp["id"], "name": emp["name"], "role": emp["role"],
                    "ultimo_aso": str(ultimo_aso[0])[:10], "vencimento": str(venc),
                    "dias_atraso": dias_atraso
                })
        else:
            result.append({
                "employee_id": emp["id"], "name": emp["name"], "role": emp["role"],
                "ultimo_aso": None, "vencimento": None, "dias_atraso": 9999
            })
    conn.close()
    return sorted(result, key=lambda x: -(x["dias_atraso"] or 0))


# ─── PGR ──────────────────────────────────────────────────────────────────────

@router.get("/pgr")
def list_pgr(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM pgr_inventario WHERE company_id=? ORDER BY ghe, agente_risco",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


@router.post("/pgr", status_code=201)
def create_pgr(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute("""
        INSERT INTO pgr_inventario (company_id, ghe, cargo, agente_risco, grupo_risco,
            fonte_geradora, trajetoria, medida_controle, severidade, probabilidade)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (company_id, data.get("ghe",""), data.get("cargo",""), data.get("agente_risco",""),
          data.get("grupo_risco","1"), data.get("fonte_geradora",""), data.get("trajetoria",""),
          data.get("medida_controle",""), data.get("severidade",1), data.get("probabilidade",1)))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/pgr/{inv_id}")
def update_pgr(inv_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    fields = ["ghe","cargo","agente_risco","grupo_risco","fonte_geradora","trajetoria","medida_controle","severidade","probabilidade"]
    sets = [f"{f}=?" for f in fields if f in data]
    vals = [data[f] for f in fields if f in data]
    if sets:
        vals.append(inv_id)
        conn.execute(f"UPDATE pgr_inventario SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/pgr/{inv_id}")
def delete_pgr(inv_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM pgr_inventario WHERE id=? AND company_id=?",
                 (inv_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/pgr/por-ghe")
def pgr_por_ghe(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT ghe, COUNT(*) as total_riscos, MAX(severidade*probabilidade) as risco_max FROM pgr_inventario WHERE company_id=? GROUP BY ghe ORDER BY risco_max DESC",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


# ─── EPI ──────────────────────────────────────────────────────────────────────

@router.get("/epi")
def list_epi(employee_id: Optional[int] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if employee_id:
        rows = rows_to_dicts(conn.execute(
            "SELECT e.*, emp.name as employee_name FROM epi_entregas e JOIN employees emp ON e.employee_id=emp.id WHERE e.company_id=? AND e.employee_id=? ORDER BY e.data_entrega DESC",
            (company_id, employee_id)
        ).fetchall())
    else:
        rows = rows_to_dicts(conn.execute(
            "SELECT e.*, emp.name as employee_name FROM epi_entregas e JOIN employees emp ON e.employee_id=emp.id WHERE e.company_id=? ORDER BY e.data_entrega DESC",
            (company_id,)
        ).fetchall())
    conn.close()
    return rows


@router.get("/epi/{emp_id}/historico")
def epi_historico(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM epi_entregas WHERE company_id=? AND employee_id=? ORDER BY data_entrega DESC",
        (current_user.get("company_id", 1), emp_id)
    ).fetchall())
    conn.close()
    return rows


@router.post("/epi", status_code=201)
def create_epi(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute("""
        INSERT INTO epi_entregas (company_id, employee_id, data_entrega, epi_nome, ca_numero, quantidade, motivo, observacoes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (company_id, data.get("employee_id"), data.get("data_entrega", date.today().isoformat()),
          data.get("epi_nome",""), data.get("ca_numero",""), data.get("quantidade",1),
          data.get("motivo","inicial"), data.get("observacoes","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/epi/{entrega_id}")
def update_epi(entrega_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    fields = ["data_entrega","epi_nome","ca_numero","quantidade","motivo","assinado","observacoes"]
    sets = [f"{f}=?" for f in fields if f in data]
    vals = [data[f] for f in fields if f in data]
    if sets:
        vals.append(entrega_id)
        conn.execute(f"UPDATE epi_entregas SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/epi/{entrega_id}")
def delete_epi(entrega_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM epi_entregas WHERE id=? AND company_id=?",
                 (entrega_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/epi/{entrega_id}/recibo")
def epi_recibo(entrega_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    entrega = conn.execute(
        "SELECT e.*, emp.name as emp_name, emp.role as emp_role, emp.cpf as emp_cpf, emp.matricula as emp_matricula FROM epi_entregas e JOIN employees emp ON e.employee_id=emp.id WHERE e.id=? AND e.company_id=?",
        (entrega_id, company_id)
    ).fetchone()
    if not entrega:
        conn.close()
        raise HTTPException(status_code=404, detail="Entrega não encontrada.")
    entrega = dict(entrega)
    co = _get_company(conn, company_id)
    conn.close()
    today = date.today()

    def _fmt(v):
        return str(v or "").strip() or "___"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Recibo EPI</title>
<style>{_DOC_CSS}</style></head><body>
<h1>Recibo de Entrega de EPI — NR-6</h1>
<p><b>EMPRESA:</b> {_fmt(co.get("razao_social"))} — CNPJ: {_fmt(co.get("cnpj"))}</p>
<p><b>FUNCIONÁRIO:</b> {_fmt(entrega.get("emp_name"))} — CPF: {_fmt(entrega.get("emp_cpf"))} — Matrícula: {_fmt(entrega.get("emp_matricula"))} — Cargo: {_fmt(entrega.get("emp_role"))}</p>
<p><b>Data de Entrega:</b> {_fmt(entrega.get("data_entrega"))} — <b>Motivo:</b> {_fmt(entrega.get("motivo"))}</p>
<table>
<tr><th>EPI</th><th>Nº CA (MTE)</th><th>Qtd</th><th>Observações</th></tr>
<tr><td>{_fmt(entrega.get("epi_nome"))}</td><td>{_fmt(entrega.get("ca_numero"))}</td><td>{entrega.get("quantidade",1)}</td><td>{_fmt(entrega.get("observacoes"))}</td></tr>
</table>
<p style="margin-top:16px">Declaro ter recebido o(s) Equipamento(s) de Proteção Individual (EPI) listado(s) acima, comprometendo-me a utilizá-lo(s) adequadamente, conservá-lo(s), comunicar ao empregador qualquer alteração que torne o EPI impróprio para uso e substituí-lo em caso de extravio ou dano, conforme NR-6.</p>
<div class="sig">
  <div style="flex:1;min-width:200px;border-top:1px solid #000;padding-top:6px">
    <b>{_fmt(entrega.get("emp_name"))}</b><br>Funcionário — CPF: {_fmt(entrega.get("emp_cpf"))}
  </div>
  <div style="flex:1;min-width:200px;border-top:1px solid #000;padding-top:6px">
    <b>{_fmt(co.get("razao_social"))}</b><br>Responsável pela Empresa<br>Data: {today.strftime("%d/%m/%Y")}
  </div>
</div>
</body></html>"""
    return Response(content=html, media_type="text/html")


# ─── CIPA ─────────────────────────────────────────────────────────────────────

@router.get("/cipa/eleicoes")
def list_cipa(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM cipa_eleicoes WHERE company_id=? ORDER BY ano DESC",
        (current_user.get("company_id", 1),)
    ).fetchall())
    conn.close()
    return rows


@router.post("/cipa/eleicoes", status_code=201)
def create_cipa(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute("""
        INSERT INTO cipa_eleicoes (company_id, ano, data_posse, data_fim_mandato,
            num_efetivos_emp, num_suplentes_emp, num_efetivos_patr, num_suplentes_patr, observacoes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (company_id, data.get("ano", date.today().year), data.get("data_posse",""),
          data.get("data_fim_mandato",""), data.get("num_efetivos_emp",0),
          data.get("num_suplentes_emp",0), data.get("num_efetivos_patr",0),
          data.get("num_suplentes_patr",0), data.get("observacoes","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/cipa/eleicoes/{el_id}")
def update_cipa(el_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    fields = ["ano","data_posse","data_fim_mandato","num_efetivos_emp","num_suplentes_emp",
              "num_efetivos_patr","num_suplentes_patr","status","observacoes"]
    sets = [f"{f}=?" for f in fields if f in data]
    vals = [data[f] for f in fields if f in data]
    if sets:
        vals.append(el_id)
        conn.execute(f"UPDATE cipa_eleicoes SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/cipa/eleicoes/{el_id}")
def delete_cipa(el_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM cipa_membros WHERE eleicao_id=?", (el_id,))
    conn.execute("DELETE FROM cipa_eleicoes WHERE id=? AND company_id=?",
                 (el_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/cipa/eleicoes/{el_id}/membros")
def list_cipa_membros(el_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT m.*, e.name as employee_name FROM cipa_membros m JOIN employees e ON m.employee_id=e.id WHERE m.eleicao_id=? ORDER BY m.tipo",
        (el_id,)
    ).fetchall())
    conn.close()
    return rows


@router.post("/cipa/eleicoes/{el_id}/membros", status_code=201)
def create_cipa_membro(el_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    eleicao = conn.execute("SELECT * FROM cipa_eleicoes WHERE id=? AND company_id=?", (el_id, company_id)).fetchone()
    if not eleicao:
        conn.close()
        raise HTTPException(status_code=404, detail="Eleição não encontrada.")
    eleicao = dict(eleicao)
    cur = conn.execute("""
        INSERT INTO cipa_membros (company_id, eleicao_id, employee_id, tipo, data_inicio, data_fim)
        VALUES (?,?,?,?,?,?)
    """, (company_id, el_id, data.get("employee_id"), data.get("tipo","efetivo_emp"),
          data.get("data_inicio", eleicao.get("data_posse","")), eleicao.get("data_fim_mandato","")))
    conn.commit()
    new_id = cur.lastrowid
    if eleicao.get("data_fim_mandato"):
        try:
            fim_cipa = date.fromisoformat(str(eleicao["data_fim_mandato"])[:10])
            fim_estab = fim_cipa + timedelta(days=365)
            conn.execute("""
                INSERT INTO employee_stability (company_id, employee_id, tipo, data_inicio,
                    data_fim_estabilidade, observacoes)
                VALUES (?,?,?,?,?,?)
            """, (company_id, data.get("employee_id"), "cipa",
                  data.get("data_inicio", eleicao.get("data_posse","")),
                  str(fim_estab), f"CIPA eleição {eleicao.get('ano','')}"))
            conn.commit()
        except Exception:
            pass
    conn.close()
    return {"id": new_id}


@router.delete("/cipa/eleicoes/{el_id}/membros/{mem_id}")
def delete_cipa_membro(el_id: int, mem_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM cipa_membros WHERE id=? AND eleicao_id=?", (mem_id, el_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── FERIADOS ─────────────────────────────────────────────────────────────────

def _calc_pascoa(ano: int):
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


@router.get("/feriados")
def list_feriados(ano: Optional[int] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if ano:
        rows = rows_to_dicts(conn.execute(
            "SELECT * FROM feriados WHERE company_id=? AND data LIKE ? ORDER BY data",
            (company_id, f"{ano}%")
        ).fetchall())
    else:
        rows = rows_to_dicts(conn.execute(
            "SELECT * FROM feriados WHERE company_id=? ORDER BY data",
            (company_id,)
        ).fetchall())
    conn.close()
    return rows


@router.post("/feriados", status_code=201)
def create_feriado(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute("""
        INSERT OR IGNORE INTO feriados (company_id, data, descricao, tipo, uf, municipio)
        VALUES (?,?,?,?,?,?)
    """, (company_id, data.get("data",""), data.get("descricao",""), data.get("tipo","nacional"),
          data.get("uf",""), data.get("municipio","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.delete("/feriados/{fer_id}")
def delete_feriado(fer_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM feriados WHERE id=? AND company_id=?",
                 (fer_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/feriados/seed-nacionais")
def seed_feriados_nacionais(ano: Optional[int] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    company_id = current_user.get("company_id", 1)
    ano = ano or date.today().year
    pascoa = _calc_pascoa(ano)
    carnaval = pascoa - timedelta(days=47)
    sextafeira_santa = pascoa - timedelta(days=2)
    corpus_christi = pascoa + timedelta(days=60)
    feriados = [
        (f"{ano}-01-01", "Confraternização Universal"),
        (str(carnaval), "Carnaval"),
        (str(carnaval + timedelta(days=1)), "Carnaval (terça)"),
        (str(sextafeira_santa), "Paixão de Cristo"),
        (str(pascoa), "Páscoa"),
        (f"{ano}-04-21", "Tiradentes"),
        (f"{ano}-05-01", "Dia do Trabalho"),
        (str(corpus_christi), "Corpus Christi"),
        (f"{ano}-09-07", "Independência do Brasil"),
        (f"{ano}-10-12", "Nossa Sra. Aparecida"),
        (f"{ano}-11-02", "Finados"),
        (f"{ano}-11-15", "Proclamação da República"),
        (f"{ano}-11-20", "Consciência Negra"),
        (f"{ano}-12-25", "Natal"),
    ]
    conn = get_conn()
    inserted = 0
    for data_fer, desc in feriados:
        cur = conn.execute(
            "INSERT OR IGNORE INTO feriados (company_id, data, descricao, tipo) VALUES (?,?,?,?)",
            (company_id, data_fer, desc, "nacional")
        )
        inserted += cur.rowcount
    conn.commit()
    conn.close()
    return {"inserted": inserted, "ano": ano}


# ─── FGTS ANIVERSÁRIO ─────────────────────────────────────────────────────────

@router.get("/fgts-aniversario/optantes")
def list_fgts_aniv(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT o.*, e.name as employee_name, e.birth_date
        FROM fgts_aniversario_optantes o JOIN employees e ON o.employee_id=e.id
        WHERE o.company_id=? ORDER BY e.name
    """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/fgts-aniversario/optantes", status_code=201)
def create_fgts_aniv(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp_id = data.get("employee_id")
    try:
        cur = conn.execute("""
            INSERT INTO fgts_aniversario_optantes (company_id, employee_id, data_opcao)
            VALUES (?,?,?)
        """, (company_id, emp_id, data.get("data_opcao", date.today().isoformat())))
        conn.execute("UPDATE employees SET fgts_aniversario=1 WHERE id=? AND company_id=?",
                     (emp_id, company_id))
        conn.commit()
        new_id = cur.lastrowid
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="Funcionário já é optante.")
    conn.close()
    return {"id": new_id}


@router.delete("/fgts-aniversario/optantes/{emp_id}")
def remove_fgts_aniv(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM fgts_aniversario_optantes WHERE employee_id=? AND company_id=?",
                 (emp_id, company_id))
    conn.execute("UPDATE employees SET fgts_aniversario=0 WHERE id=? AND company_id=?",
                 (emp_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/fgts-aniversario/calendario")
def fgts_aniv_calendario(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT o.employee_id, e.name, e.birth_date, o.data_opcao
        FROM fgts_aniversario_optantes o JOIN employees e ON o.employee_id=e.id
        WHERE o.company_id=?
    """, (company_id,)).fetchall())
    conn.close()
    por_mes = {}
    for r in rows:
        bd = str(r.get("birth_date") or "")
        mes = bd[5:7] if len(bd) >= 7 else "00"
        por_mes.setdefault(mes, []).append(r)
    return [{"mes": k, "funcionarios": v} for k, v in sorted(por_mes.items())]


# ─── REINTEGRAÇÃO ─────────────────────────────────────────────────────────────

@router.get("/reintegracoes")
def list_reintegracoes(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT r.*, e.name as employee_name FROM reintegracoes r
        JOIN employees e ON r.employee_id=e.id
        WHERE r.company_id=? ORDER BY r.data_reintegracao DESC
    """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/reintegracoes", status_code=201)
def create_reintegracao(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    emp_id = data.get("employee_id")
    cur = conn.execute("""
        INSERT INTO reintegracoes (company_id, employee_id, data_demissao, data_reintegracao,
            motivo, nr_processo, salario_reintegracao, observacoes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (company_id, emp_id, data.get("data_demissao",""), data.get("data_reintegracao",""),
          data.get("motivo",""), data.get("nr_processo",""),
          data.get("salario_reintegracao",0), data.get("observacoes","")))
    conn.execute("UPDATE employees SET active=1, termination_date=NULL WHERE id=? AND company_id=?",
                 (emp_id, company_id))
    if data.get("salario_reintegracao"):
        conn.execute("UPDATE employees SET salary=? WHERE id=? AND company_id=?",
                     (data["salario_reintegracao"], emp_id, company_id))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/reintegracoes/{rein_id}")
def update_reintegracao(rein_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    fields = ["data_demissao","data_reintegracao","motivo","nr_processo","salario_reintegracao","observacoes"]
    sets = [f"{f}=?" for f in fields if f in data]
    vals = [data[f] for f in fields if f in data]
    if sets:
        vals.append(rein_id)
        conn.execute(f"UPDATE reintegracoes SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/reintegracoes/{rein_id}/s2298")
def reintegracao_s2298(rein_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rein = conn.execute(
        "SELECT * FROM reintegracoes WHERE id=? AND company_id=?", (rein_id, company_id)
    ).fetchone()
    if not rein:
        conn.close()
        raise HTTPException(status_code=404, detail="Reintegração não encontrada.")
    rein = dict(rein)
    emp = conn.execute("SELECT * FROM employees WHERE id=?", (rein["employee_id"],)).fetchone()
    company = _get_company(conn, company_id)
    conn.close()
    xml = gerar_s2298(company, dict(emp) if emp else {}, rein)
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="S-2298_{rein_id}.xml"'})


# ─── CBO ──────────────────────────────────────────────────────────────────────

@router.get("/cbo")
def search_cbo(q: str = "", current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    if q:
        rows = rows_to_dicts(conn.execute(
            "SELECT codigo, descricao FROM cbo_ocupacoes WHERE descricao LIKE ? OR codigo LIKE ? ORDER BY descricao LIMIT 50",
            (f"%{q}%", f"%{q}%")
        ).fetchall())
    else:
        rows = rows_to_dicts(conn.execute(
            "SELECT codigo, descricao FROM cbo_ocupacoes ORDER BY descricao LIMIT 100"
        ).fetchall())
    conn.close()
    return rows


# ─── REPASSE AO SINDICATO ──────────────────────────────────────────────────────

@router.get("/relatorios/repasse-sindicato")
def repasse_sindicato(competencia: str = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cctas = rows_to_dicts(conn.execute(
        "SELECT * FROM cct_assistencial WHERE company_id=? AND ativo=1", (company_id,)
    ).fetchall())
    employees = rows_to_dicts(conn.execute(
        "SELECT id, name, salary FROM employees WHERE company_id=? AND active=1", (company_id,)
    ).fetchall())
    oposicoes_raw = rows_to_dicts(conn.execute(
        "SELECT cct_id, employee_id FROM cct_oposicoes WHERE company_id=?", (company_id,)
    ).fetchall())
    oposicoes = {(o["cct_id"], o["employee_id"]) for o in oposicoes_raw}
    conn.close()

    result = []
    for cct in cctas:
        total = 0.0
        qtd = 0
        for emp in employees:
            if (cct["id"], emp["id"]) in oposicoes:
                continue
            total += round(float(emp["salary"]) * float(cct["percentual"]) / 100, 2)
            qtd += 1
        result.append({
            "sindicato": cct.get("sindicato") or cct.get("descricao",""),
            "cct_id": cct["id"],
            "competencia": competencia,
            "funcionarios": qtd,
            "percentual": cct["percentual"],
            "total": round(total, 2),
        })
    return {"competencia": competencia, "sindicatos": result,
            "grand_total": round(sum(s["total"] for s in result), 2)}


# ─── MÚLTIPLOS VÍNCULOS ────────────────────────────────────────────────────────

@router.get("/employees/{emp_id}/contratos")
def list_contratos(emp_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM employee_contracts WHERE employee_id=? AND company_id=? ORDER BY contrato_num",
        (emp_id, current_user.get("company_id", 1))
    ).fetchall())
    conn.close()
    return rows


@router.post("/employees/{emp_id}/contratos", status_code=201)
def create_contrato(emp_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM employee_contracts WHERE employee_id=? AND company_id=? AND ativo=1",
        (emp_id, company_id)
    ).fetchone()
    num = str((existing["cnt"] if existing else 0) + 1)
    cur = conn.execute("""
        INSERT INTO employee_contracts (company_id, employee_id, contrato_num, cargo, salario,
            admission_date, jornada_tipo, horas_semana, observacoes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (company_id, emp_id, num, data.get("cargo",""), data.get("salario",0),
          data.get("admission_date",""), data.get("jornada_tipo","integral"),
          data.get("horas_semana",44), data.get("observacoes","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.put("/employees/{emp_id}/contratos/{cont_id}")
def update_contrato(emp_id: int, cont_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    fields = ["cargo","salario","admission_date","termination_date","jornada_tipo","horas_semana","ativo","observacoes"]
    sets = [f"{f}=?" for f in fields if f in data]
    vals = [data[f] for f in fields if f in data]
    if sets:
        vals += [cont_id, emp_id]
        conn.execute(f"UPDATE employee_contracts SET {','.join(sets)} WHERE id=? AND employee_id=?", vals)
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/employees/{emp_id}/contratos/{cont_id}")
def delete_contrato(emp_id: int, cont_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM employee_contracts WHERE id=? AND employee_id=? AND company_id=?",
                 (cont_id, emp_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── CENTRO DE CUSTO POR RUBRICA ──────────────────────────────────────────────

@router.get("/centro-custo/alocacao")
def list_cc_alocacao(competencia: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    if competencia:
        rows = rows_to_dicts(conn.execute("""
            SELECT a.*, e.name as employee_name, cc.name as cc_name
            FROM cc_alocacoes a
            JOIN employees e ON a.employee_id=e.id
            JOIN cost_centers cc ON a.cost_center_id=cc.id
            WHERE a.company_id=? AND a.competencia=?
        """, (company_id, competencia)).fetchall())
    else:
        rows = rows_to_dicts(conn.execute("""
            SELECT a.*, e.name as employee_name, cc.name as cc_name
            FROM cc_alocacoes a
            JOIN employees e ON a.employee_id=e.id
            JOIN cost_centers cc ON a.cost_center_id=cc.id
            WHERE a.company_id=? ORDER BY a.competencia DESC
        """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/centro-custo/alocacao", status_code=201)
def create_cc_alocacao(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.execute("""
        INSERT INTO cc_alocacoes (company_id, employee_id, cost_center_id, percentual, competencia)
        VALUES (?,?,?,?,?)
    """, (company_id, data.get("employee_id"), data.get("cost_center_id"),
          data.get("percentual", 100), data.get("competencia","")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id}


@router.delete("/centro-custo/alocacao/{aloc_id}")
def delete_cc_alocacao(aloc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM cc_alocacoes WHERE id=? AND company_id=?",
                 (aloc_id, current_user.get("company_id", 1)))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/relatorios/custo-por-cc")
def relatorio_custo_cc(competencia: str = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    run = conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id=? AND competence=? AND COALESCE(tipo, 'mensal')='mensal' ORDER BY id DESC LIMIT 1",
        (company_id, competencia)
    ).fetchone()
    if not run:
        conn.close()
        return {"competencia": competencia, "centros": [], "sem_alocacao": []}
    run = dict(run)
    items = rows_to_dicts(conn.execute(
        "SELECT pi.*, e.name FROM payroll_items pi JOIN employees e ON pi.employee_id=e.id WHERE pi.run_id=?",
        (run["id"],)
    ).fetchall())
    alocacoes = rows_to_dicts(conn.execute("""
        SELECT a.*, cc.name as cc_name FROM cc_alocacoes a
        JOIN cost_centers cc ON a.cost_center_id=cc.id
        WHERE a.company_id=? AND a.competencia=?
    """, (company_id, competencia)).fetchall())
    alocacoes_map = {}
    for a in alocacoes:
        alocacoes_map.setdefault(a["employee_id"], []).append(a)
    cc_totais = {}
    sem_alocacao = []
    for item in items:
        gross = float(item.get("gross_salary", 0))
        emp_aloc = alocacoes_map.get(item["employee_id"])
        if emp_aloc:
            for a in emp_aloc:
                cc_id = a["cost_center_id"]
                cc_name = a["cc_name"]
                valor = round(gross * float(a["percentual"]) / 100, 2)
                if cc_id not in cc_totais:
                    cc_totais[cc_id] = {"cc_id": cc_id, "cc_name": cc_name, "total": 0.0, "funcionarios": 0}
                cc_totais[cc_id]["total"] += valor
                cc_totais[cc_id]["funcionarios"] += 1
        else:
            sem_alocacao.append({"employee_id": item["employee_id"], "name": item["name"], "gross_salary": gross})
    conn.close()
    return {
        "competencia": competencia,
        "centros": [{"cc_id": v["cc_id"], "cc_name": v["cc_name"],
                     "total": round(v["total"], 2), "funcionarios": v["funcionarios"]}
                    for v in cc_totais.values()],
        "sem_alocacao": sem_alocacao
    }


# ─── RECÁLCULO RETROATIVO CCT ─────────────────────────────────────────────────

@router.post("/cct-assistencial/recalculo-retroativo")
def cct_recalculo_retroativo(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp_inicio = data.get("competencia_inicio","")
    comp_fim = data.get("competencia_fim","")
    cct_id = data.get("cct_id")
    dry_run = data.get("dry_run", True)

    cct = conn.execute("SELECT * FROM cct_assistencial WHERE id=? AND company_id=?", (cct_id, company_id)).fetchone()
    if not cct:
        conn.close()
        raise HTTPException(status_code=404, detail="CCT não encontrada.")
    cct = dict(cct)

    runs = rows_to_dicts(conn.execute(
        "SELECT * FROM payroll_runs WHERE company_id=? AND competence>=? AND competence<=? ORDER BY competence",
        (company_id, comp_inicio, comp_fim)
    ).fetchall())

    oposicoes_raw = rows_to_dicts(conn.execute(
        "SELECT employee_id FROM cct_oposicoes WHERE company_id=? AND cct_id=?", (company_id, cct_id)
    ).fetchall())
    opostos = {o["employee_id"] for o in oposicoes_raw}

    ajustes = []
    for run in runs:
        items = rows_to_dicts(conn.execute(
            "SELECT pi.*, e.name FROM payroll_items pi JOIN employees e ON pi.employee_id=e.id WHERE pi.run_id=?",
            (run["id"],)
        ).fetchall())
        for item in items:
            if item["employee_id"] in opostos:
                continue
            desconto = round(float(item.get("gross_salary",0)) * float(cct["percentual"]) / 100, 2)
            ajustes.append({
                "competencia": run["competence"],
                "employee_id": item["employee_id"],
                "employee_name": item["name"],
                "desconto": desconto
            })
            if not dry_run:
                current_disc = float(item.get("other_discounts", 0) or 0)
                conn.execute(
                    "UPDATE payroll_items SET other_discounts=? WHERE id=?",
                    (round(current_disc + desconto, 2), item["id"])
                )

    if not dry_run:
        conn.commit()
    conn.close()
    return {"dry_run": dry_run, "total_ajustes": len(ajustes), "ajustes": ajustes}
