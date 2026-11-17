"""
Painel do Super Administrador (dono do sistema).

Acima dos administradores das empresas clientes. Aqui o dono do Cortex:
  * aprova, bloqueia e reativa empresas clientes (cadastro público entra como 'pendente');
  * gerencia os logins de qualquer empresa (ativar, desativar, redefinir senha);
  * mantém as tabelas legais globais (INSS, IRRF, FGTS, salário mínimo...) — company_id = 0,
    usadas pelo motor de folha de TODOS os clientes;
  * mantém o catálogo global de rubricas e publica nas empresas (origem 'global');
  * atende as solicitações de suporte abertas pelos clientes.

O cliente abre solicitações em /api/support.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

try:
    from ..auth import get_current_user, hash_password, log_audit, require_superadmin
    from ..database import get_conn
    from ..services.payroll_engine import SYSTEM_RUBRICS, validate_formula
    from ..services.payroll_tables import default_seed
except ImportError:  # execução com backend/ como raiz
    from auth import get_current_user, hash_password, log_audit, require_superadmin
    from database import get_conn
    from services.payroll_engine import SYSTEM_RUBRICS, validate_formula
    from services.payroll_tables import default_seed

router = APIRouter(prefix="/api/superadmin", tags=["Super Administrador"])
support_router = APIRouter(prefix="/api/support", tags=["Suporte"])

GLOBAL = 0  # company_id do catálogo global
STATUS_EMPRESA = ("ativa", "pendente", "bloqueada")
STATUS_SUPORTE = ("aberto", "em_andamento", "concluido")
CATEGORIAS_SUPORTE = ("tabelas", "rubricas", "acesso", "erro", "melhoria", "outro")
TIPOS_TABELA = ("inss", "irrf", "fgts", "salario_minimo", "irrf_dependente", "irrf_simplificado", "salario_familia")
RUBRIC_FIELDS = ("codigo", "nome", "tipo", "natureza", "incide_inss", "incide_irrf", "incide_fgts",
                 "incide_13", "incide_ferias", "esocial_cod_rubrica", "esocial_nat_rubrica", "formula",
                 "aplica_todos", "ativo")
_INT_FIELDS = {"incide_inss", "incide_irrf", "incide_fgts", "incide_13", "incide_ferias", "aplica_todos", "ativo"}


def _rows(conn, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _company_or_404(conn, company_id: int) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return dict(row)


# ─── VISÃO GERAL ──────────────────────────────────────────────────────────────

@router.get("/overview")
def overview(user: Dict[str, Any] = Depends(require_superadmin)):
    conn = get_conn()
    try:
        por_status = {s: 0 for s in STATUS_EMPRESA}
        for r in _rows(conn, "SELECT COALESCE(status, 'ativa') AS st, COUNT(*) AS n FROM companies GROUP BY COALESCE(status, 'ativa')"):
            por_status[r["st"]] = r["n"]
        usuarios = conn.execute("SELECT COUNT(*) FROM users WHERE active = 1").fetchone()[0]
        funcionarios = conn.execute("SELECT COUNT(*) FROM employees WHERE active = 1").fetchone()[0]
        suporte_aberto = conn.execute(
            "SELECT COUNT(*) FROM support_requests WHERE status != 'concluido'").fetchone()[0]
        pendentes = _rows(conn, """
            SELECT id, razao_social, cnpj, email, created_at FROM companies
            WHERE status = 'pendente' ORDER BY id DESC LIMIT 10""")
        ano = date.today().year
        tabelas_ano = [r["tipo"] for r in _rows(
            conn, "SELECT DISTINCT tipo FROM tax_tables WHERE company_id = 0 AND ano = ?", (ano,))]
        rubricas_globais = conn.execute(
            "SELECT COUNT(*) FROM payroll_rubrics WHERE company_id = 0").fetchone()[0]
    finally:
        conn.close()
    return {
        "empresas": por_status,
        "empresas_total": sum(por_status.values()),
        "usuarios_ativos": usuarios,
        "funcionarios_ativos": funcionarios,
        "suporte_aberto": suporte_aberto,
        "pendentes": pendentes,
        "ano": ano,
        "tabelas_globais_ano": tabelas_ano,
        "tabelas_faltando": [t for t in ("inss", "irrf", "fgts", "salario_minimo") if t not in tabelas_ano],
        "rubricas_globais": rubricas_globais,
    }


# ─── EMPRESAS CLIENTES ────────────────────────────────────────────────────────

@router.get("/companies")
def list_companies(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_superadmin),
):
    conn = get_conn()
    where, params = ["1=1"], []
    if status:
        where.append("COALESCE(c.status, 'ativa') = ?")
        params.append(status)
    if q:
        where.append("(LOWER(c.razao_social) LIKE ? OR LOWER(c.nome_fantasia) LIKE ? OR c.cnpj LIKE ? OR LOWER(c.email) LIKE ?)")
        like = f"%{q.strip().lower()}%"
        params += [like, like, f"%{q.strip()}%", like]
    rows = _rows(conn, f"""
        SELECT c.id, c.razao_social, c.nome_fantasia, c.cnpj, c.email, c.telefone, c.cidade, c.uf,
               COALESCE(c.status, 'ativa') AS status, c.plano, c.observacao_admin, c.bloqueio_motivo,
               c.aprovado_em, c.created_at,
               (SELECT COUNT(*) FROM users u WHERE u.home_company_id = c.id AND COALESCE(u.is_superadmin, 0) = 0) AS usuarios,
               (SELECT COUNT(*) FROM employees e WHERE e.company_id = c.id AND e.active = 1) AS funcionarios,
               (SELECT u.email FROM users u WHERE u.home_company_id = c.id AND u.role = 'admin'
                  AND COALESCE(u.is_superadmin, 0) = 0 ORDER BY u.id LIMIT 1) AS admin_email
        FROM companies c
        WHERE {' AND '.join(where)}
        ORDER BY CASE COALESCE(c.status, 'ativa') WHEN 'pendente' THEN 0 WHEN 'bloqueada' THEN 2 ELSE 1 END, c.id DESC
    """, tuple(params))
    conn.close()
    return rows


@router.get("/companies/{company_id}")
def get_company(company_id: int, user: Dict[str, Any] = Depends(require_superadmin)):
    conn = get_conn()
    comp = _company_or_404(conn, company_id)
    for k in ("cert_password", "certificado_senha", "api_secret", "asaas_api_key"):
        comp.pop(k, None)
    comp["users"] = _rows(conn, """
        SELECT id, name, email, role, active, created_at, COALESCE(is_superadmin, 0) AS is_superadmin
        FROM users WHERE home_company_id = ? ORDER BY name""", (company_id,))
    comp["support"] = _rows(conn, """
        SELECT id, categoria, assunto, status, created_at FROM support_requests
        WHERE company_id = ? ORDER BY id DESC LIMIT 20""", (company_id,))
    conn.close()
    return comp


def _set_status(company_id: int, novo: str, user: Dict[str, Any], motivo: str = "") -> Dict[str, Any]:
    conn = get_conn()
    comp = _company_or_404(conn, company_id)
    if novo == "bloqueada" and company_id == (user.get("home_company_id") or 1):
        conn.close()
        raise HTTPException(status_code=400, detail="Não é possível bloquear a empresa do próprio administrador do sistema.")
    if novo == "ativa":
        conn.execute("UPDATE companies SET status = 'ativa', bloqueio_motivo = '', "
                     "aprovado_em = CASE WHEN COALESCE(aprovado_em, '') = '' THEN ? ELSE aprovado_em END WHERE id = ?",
                     (_now(), company_id))
        if (comp.get("status") or "ativa") == "pendente":
            _publish_rubrics_to(conn, [company_id], atualizar=False)
            conn.execute("""
                INSERT INTO notifications (company_id, title, message, type, is_read, link)
                VALUES (?, 'Acesso liberado', 'Seu cadastro foi aprovado. Bem-vindo ao Cortex ERP!', 'success', 0, '')
            """, (company_id,))
    else:
        conn.execute("UPDATE companies SET status = ?, bloqueio_motivo = ? WHERE id = ?",
                     (novo, motivo.strip(), company_id))
    conn.commit()
    log_audit(conn, action=f"superadmin_{novo}", entity="companies", entity_id=company_id, user_id=user["id"])
    out = _company_or_404(conn, company_id)
    conn.close()
    return {"ok": True, "id": company_id, "status": out.get("status")}


@router.post("/companies/{company_id}/approve")
def approve_company(company_id: int, user: Dict[str, Any] = Depends(require_superadmin)):
    return _set_status(company_id, "ativa", user)


@router.post("/companies/{company_id}/block")
def block_company(company_id: int, data: Dict[str, Any] = Body(default={}),
                  user: Dict[str, Any] = Depends(require_superadmin)):
    return _set_status(company_id, "bloqueada", user, str(data.get("motivo") or ""))


@router.post("/companies/{company_id}/reactivate")
def reactivate_company(company_id: int, user: Dict[str, Any] = Depends(require_superadmin)):
    return _set_status(company_id, "ativa", user)


@router.put("/companies/{company_id}")
def update_company(company_id: int, data: Dict[str, Any] = Body(...),
                   user: Dict[str, Any] = Depends(require_superadmin)):
    conn = get_conn()
    _company_or_404(conn, company_id)
    fields, vals = [], []
    for f in ("plano", "observacao_admin"):
        if f in data:
            fields.append(f"{f} = ?")
            vals.append(str(data[f] or ""))
    if fields:
        conn.execute(f"UPDATE companies SET {', '.join(fields)} WHERE id = ?", (*vals, company_id))
        conn.commit()
    conn.close()
    return {"ok": True}


@router.put("/users/{user_id}")
def update_any_user(user_id: int, data: Dict[str, Any] = Body(...),
                    user: Dict[str, Any] = Depends(require_superadmin)):
    """Ativa/desativa, troca perfil ou redefine a senha do login de qualquer empresa."""
    conn = get_conn()
    target = conn.execute("SELECT id, COALESCE(is_superadmin, 0) AS sa FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if user_id == user["id"] and "active" in data and not int(data["active"]):
        conn.close()
        raise HTTPException(status_code=400, detail="Você não pode desativar o próprio login.")
    fields, vals = [], []
    if "active" in data:
        fields.append("active = ?"); vals.append(1 if int(data["active"]) else 0)
    if data.get("role"):
        fields.append("role = ?"); vals.append(str(data["role"]))
    if data.get("password"):
        if len(str(data["password"])) < 6:
            conn.close()
            raise HTTPException(status_code=400, detail="A senha deve ter no mínimo 6 caracteres.")
        fields.append("password_hash = ?"); vals.append(hash_password(str(data["password"])))
    if fields:
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", (*vals, user_id))
        conn.commit()
        log_audit(conn, action="superadmin_user_update", entity="users", entity_id=user_id, user_id=user["id"])
    conn.close()
    return {"ok": True}


# ─── TABELAS LEGAIS GLOBAIS ───────────────────────────────────────────────────

def _brackets(conn, table_id: int) -> List[Dict[str, Any]]:
    return _rows(conn, "SELECT faixa_de, faixa_ate, aliquota, deducao FROM tax_brackets "
                       "WHERE tax_table_id = ? ORDER BY faixa_de", (table_id,))


def _save_brackets(conn, table_id: int, brackets: List[Dict[str, Any]]) -> None:
    conn.execute("DELETE FROM tax_brackets WHERE tax_table_id = ?", (table_id,))
    for b in brackets:
        ate = b.get("faixa_ate")
        conn.execute(
            "INSERT INTO tax_brackets (tax_table_id, faixa_de, faixa_ate, aliquota, deducao) VALUES (?,?,?,?,?)",
            (table_id, float(b.get("faixa_de") or 0), None if ate in (None, "") else float(ate),
             float(b.get("aliquota") or 0), float(b.get("deducao") or 0)))


@router.get("/tax-tables")
def list_global_tables(ano: Optional[int] = None, user: Dict[str, Any] = Depends(require_superadmin)):
    conn = get_conn()
    sql, params = "SELECT * FROM tax_tables WHERE company_id = 0", []
    if ano:
        sql += " AND ano = ?"
        params.append(ano)
    tables = _rows(conn, sql + " ORDER BY ano DESC, tipo", tuple(params))
    for t in tables:
        t["brackets"] = _brackets(conn, t["id"])
    conn.close()
    return tables


@router.post("/tax-tables", status_code=201)
def save_global_table(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_superadmin)):
    """Cria ou substitui a tabela global de um tipo/ano (uma por tipo e ano)."""
    tipo = str(data.get("tipo") or "")
    if tipo not in TIPOS_TABELA:
        raise HTTPException(status_code=422, detail=f"Tipo inválido. Use: {', '.join(TIPOS_TABELA)}.")
    try:
        ano = int(data.get("ano"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Ano inválido.")
    brackets = data.get("brackets") or []
    if not brackets:
        raise HTTPException(status_code=422, detail="Informe ao menos uma faixa.")
    conn = get_conn()
    row = conn.execute("SELECT id FROM tax_tables WHERE company_id = 0 AND ano = ? AND tipo = ?", (ano, tipo)).fetchone()
    if row:
        table_id = row[0]
    else:
        cur = conn.cursor()
        cur.execute("INSERT INTO tax_tables (company_id, ano, tipo) VALUES (0, ?, ?)", (ano, tipo))
        table_id = cur.lastrowid
    _save_brackets(conn, table_id, brackets)
    conn.commit()
    log_audit(conn, action="superadmin_tax_table", entity="tax_tables", entity_id=table_id, user_id=user["id"])
    conn.close()
    return {"ok": True, "id": table_id, "atualizada": bool(row)}


@router.delete("/tax-tables/{table_id}")
def delete_global_table(table_id: int, user: Dict[str, Any] = Depends(require_superadmin)):
    conn = get_conn()
    conn.execute("DELETE FROM tax_brackets WHERE tax_table_id = ? AND tax_table_id IN "
                 "(SELECT id FROM tax_tables WHERE company_id = 0)", (table_id,))
    conn.execute("DELETE FROM tax_tables WHERE id = ? AND company_id = 0", (table_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/tax-tables/seed-default", status_code=201)
def seed_global_tables(ano: Optional[int] = None, force: bool = False,
                       user: Dict[str, Any] = Depends(require_superadmin)):
    """Importa as tabelas legais embutidas no sistema para o catálogo global do ano."""
    ano = ano or date.today().year
    conn = get_conn()
    criadas = 0
    for tipo, brackets in default_seed(ano).items():
        row = conn.execute("SELECT id FROM tax_tables WHERE company_id = 0 AND ano = ? AND tipo = ?", (ano, tipo)).fetchone()
        if row and not force:
            continue
        if row:
            table_id = row[0]
        else:
            cur = conn.cursor()
            cur.execute("INSERT INTO tax_tables (company_id, ano, tipo) VALUES (0, ?, ?)", (ano, tipo))
            table_id = cur.lastrowid
        _save_brackets(conn, table_id, [
            {"faixa_de": b[0], "faixa_ate": b[1], "aliquota": b[2], "deducao": b[3]} for b in brackets])
        criadas += 1
    conn.commit()
    conn.close()
    return {"ok": True, "ano": ano, "tabelas": criadas}


# ─── CATÁLOGO GLOBAL DE RUBRICAS ──────────────────────────────────────────────

def _clean_rubric(data: Dict[str, Any], parcial: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in RUBRIC_FIELDS:
        if f not in data:
            continue
        v = data[f]
        out[f] = (1 if v not in (0, "0", False, None, "") else 0) if f in _INT_FIELDS else str(v or "").strip()
    if not parcial:
        if not out.get("codigo") or not out.get("nome"):
            raise HTTPException(status_code=422, detail="Código e nome da rubrica são obrigatórios.")
        out.setdefault("tipo", "provento")
    if out.get("tipo") and out["tipo"] not in ("provento", "desconto", "informativo"):
        raise HTTPException(status_code=422, detail="Tipo deve ser provento, desconto ou informativo.")
    if out.get("formula"):
        erros = validate_formula(out["formula"])
        if erros:
            raise HTTPException(status_code=422, detail="Fórmula inválida: " + "; ".join(erros))
    return out


@router.get("/rubrics")
def list_global_rubrics(user: Dict[str, Any] = Depends(require_superadmin)):
    conn = get_conn()
    rows = _rows(conn, """
        SELECT r.*,
               (SELECT COUNT(DISTINCT p.company_id) FROM payroll_rubrics p
                 WHERE p.company_id != 0 AND p.codigo = r.codigo AND p.origem = 'global') AS empresas
        FROM payroll_rubrics r WHERE r.company_id = 0 ORDER BY r.codigo""")
    conn.close()
    return rows


@router.post("/rubrics", status_code=201)
def create_global_rubric(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_superadmin)):
    r = _clean_rubric(data)
    conn = get_conn()
    if conn.execute("SELECT 1 FROM payroll_rubrics WHERE company_id = 0 AND codigo = ?", (r["codigo"],)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Já existe rubrica global com o código {r['codigo']}.")
    r.setdefault("ativo", 1)
    cols = ["company_id", "origem"] + list(r.keys())
    cur = conn.cursor()
    cur.execute(f"INSERT INTO payroll_rubrics ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                (GLOBAL, "global", *r.values()))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "id": new_id}


@router.put("/rubrics/{rubric_id}")
def update_global_rubric(rubric_id: int, data: Dict[str, Any] = Body(...),
                         user: Dict[str, Any] = Depends(require_superadmin)):
    r = _clean_rubric(data, parcial=True)
    r.pop("codigo", None)  # o código liga a rubrica global às cópias das empresas
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM payroll_rubrics WHERE id = ? AND company_id = 0", (rubric_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Rubrica global não encontrada.")
    if r:
        conn.execute(f"UPDATE payroll_rubrics SET {', '.join(f'{k} = ?' for k in r)} WHERE id = ?",
                     (*r.values(), rubric_id))
        conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/rubrics/{rubric_id}")
def delete_global_rubric(rubric_id: int, user: Dict[str, Any] = Depends(require_superadmin)):
    """Remove do catálogo. As cópias já publicadas nas empresas continuam (podem ter lançamentos)."""
    conn = get_conn()
    conn.execute("DELETE FROM payroll_rubrics WHERE id = ? AND company_id = 0", (rubric_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/rubrics/import-system", status_code=201)
def import_system_rubrics(user: Dict[str, Any] = Depends(require_superadmin)):
    """Preenche o catálogo global com as rubricas de sistema do motor de folha."""
    conn = get_conn()
    existentes = {r["codigo"] for r in _rows(conn, "SELECT codigo FROM payroll_rubrics WHERE company_id = 0")}
    criadas = 0
    for codigo, nome, tipo, i1, i2, i3, nat in SYSTEM_RUBRICS.values():
        if codigo in existentes:
            continue
        conn.execute("""INSERT INTO payroll_rubrics
            (company_id, origem, codigo, nome, tipo, incide_inss, incide_irrf, incide_fgts, incide_13,
             incide_ferias, esocial_nat_rubrica, ativo)
            VALUES (0, 'global', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""", (codigo, nome, tipo, i1, i2, i3, i1, i1, nat))
        existentes.add(codigo)
        criadas += 1
    conn.commit()
    conn.close()
    return {"ok": True, "criadas": criadas}


def _publish_rubrics_to(conn, company_ids: List[int], atualizar: bool,
                        rubric_ids: Optional[List[int]] = None) -> Dict[str, int]:
    """Copia as rubricas globais para as empresas. Cria as que faltam (pelo código) e, com
    atualizar=True, sobrescreve as cópias que vieram do catálogo (origem 'global').
    Rubricas próprias da empresa com o mesmo código nunca são tocadas."""
    globais = _rows(conn, "SELECT * FROM payroll_rubrics WHERE company_id = 0 ORDER BY codigo")
    if rubric_ids:
        globais = [g for g in globais if g["id"] in set(rubric_ids)]
    campos = [f for f in RUBRIC_FIELDS if f != "codigo"]
    criadas = atualizadas = ignoradas = 0
    for cid in company_ids:
        locais = {r["codigo"]: r for r in _rows(
            conn, "SELECT id, codigo, origem FROM payroll_rubrics WHERE company_id = ?", (cid,))}
        for g in globais:
            loc = locais.get(g["codigo"])
            vals = [g.get(f) if g.get(f) is not None else ("" if f not in _INT_FIELDS else 0) for f in campos]
            if loc is None:
                cols = ["company_id", "origem", "codigo"] + campos
                conn.execute(f"INSERT INTO payroll_rubrics ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             (cid, "global", g["codigo"], *vals))
                criadas += 1
            elif atualizar and (loc.get("origem") or "") == "global":
                conn.execute(f"UPDATE payroll_rubrics SET {', '.join(f'{f} = ?' for f in campos)} WHERE id = ?",
                             (*vals, loc["id"]))
                atualizadas += 1
            else:
                ignoradas += 1
    return {"criadas": criadas, "atualizadas": atualizadas, "ignoradas": ignoradas}


@router.post("/rubrics/publish")
def publish_rubrics(data: Dict[str, Any] = Body(default={}), user: Dict[str, Any] = Depends(require_superadmin)):
    """Publica o catálogo nas empresas ativas (ou nas informadas em company_ids)."""
    conn = get_conn()
    ids = data.get("company_ids") or [r["id"] for r in _rows(
        conn, "SELECT id FROM companies WHERE COALESCE(status, 'ativa') = 'ativa'")]
    res = _publish_rubrics_to(conn, [int(i) for i in ids], bool(data.get("atualizar_existentes")),
                              [int(i) for i in (data.get("rubric_ids") or [])] or None)
    conn.commit()
    log_audit(conn, action="superadmin_publish_rubrics", entity="payroll_rubrics", entity_id=0, user_id=user["id"])
    conn.close()
    return {"ok": True, "empresas": len(ids), **res}


# ─── SOLICITAÇÕES DE SUPORTE ──────────────────────────────────────────────────

@router.get("/support")
def list_support(status: Optional[str] = Query(None), user: Dict[str, Any] = Depends(require_superadmin)):
    conn = get_conn()
    sql = """SELECT s.*, c.razao_social, c.nome_fantasia, u.name AS user_name, u.email AS user_email
             FROM support_requests s
             LEFT JOIN companies c ON c.id = s.company_id
             LEFT JOIN users u ON u.id = s.user_id"""
    params: tuple = ()
    if status:
        sql += " WHERE s.status = ?"
        params = (status,)
    rows = _rows(conn, sql + " ORDER BY CASE s.status WHEN 'aberto' THEN 0 WHEN 'em_andamento' THEN 1 ELSE 2 END, s.id DESC", params)
    conn.close()
    return rows


@router.put("/support/{req_id}")
def answer_support(req_id: int, data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(require_superadmin)):
    novo = str(data.get("status") or "")
    if novo and novo not in STATUS_SUPORTE:
        raise HTTPException(status_code=422, detail="Status inválido.")
    conn = get_conn()
    row = conn.execute("SELECT company_id, assunto FROM support_requests WHERE id = ?", (req_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    fields, vals = [], []
    if novo:
        fields.append("status = ?"); vals.append(novo)
    if "resposta" in data:
        fields.append("resposta = ?"); vals.append(str(data["resposta"] or ""))
        fields.append("respondido_em = ?"); vals.append(_now())
    if fields:
        conn.execute(f"UPDATE support_requests SET {', '.join(fields)} WHERE id = ?", (*vals, req_id))
        conn.execute("""INSERT INTO notifications (company_id, title, message, type, is_read, link)
                        VALUES (?, 'Suporte respondeu sua solicitação', ?, 'info', 0, 'support')""",
                     (row[0], f"Solicitação \"{row[1]}\": {novo or 'atualizada'}."))
        conn.commit()
    conn.close()
    return {"ok": True}


# ─── LADO DO CLIENTE: abrir e acompanhar solicitações ─────────────────────────

@support_router.get("")
def my_requests(user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = _rows(conn, """SELECT s.*, u.name AS user_name FROM support_requests s
                          LEFT JOIN users u ON u.id = s.user_id
                          WHERE s.company_id = ? ORDER BY s.id DESC""", (user.get("company_id", 1),))
    conn.close()
    return rows


@support_router.post("", status_code=201)
def open_request(data: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(get_current_user)):
    assunto = str(data.get("assunto") or "").strip()
    if not assunto:
        raise HTTPException(status_code=422, detail="Informe o assunto.")
    categoria = str(data.get("categoria") or "outro")
    if categoria not in CATEGORIAS_SUPORTE:
        categoria = "outro"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO support_requests (company_id, user_id, categoria, assunto, mensagem)
                   VALUES (?, ?, ?, ?, ?)""",
                (user.get("company_id", 1), user["id"], categoria, assunto[:200], str(data.get("mensagem") or "")[:5000]))
    new_id = cur.lastrowid
    for row in conn.execute("SELECT DISTINCT home_company_id FROM users WHERE is_superadmin = 1 AND active = 1").fetchall():
        conn.execute("""INSERT INTO notifications (company_id, title, message, type, is_read, link)
                        VALUES (?, 'Nova solicitação de suporte', ?, 'info', 0, 'superadmin')""",
                     (row[0], f"[{categoria}] {assunto[:120]}"))
    conn.commit()
    conn.close()
    return {"ok": True, "id": new_id}
