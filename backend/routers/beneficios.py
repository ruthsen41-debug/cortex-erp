"""Benefícios do DP (bloco 4): plano de saúde por faixa etária com dependentes e coparticipação,
empréstimo consignado (margem, desconto em folha e na rescisão) e compra/recibo do vale-transporte.

O cálculo em folha fica no motor (payroll_engine); aqui ficam os cadastros e os relatórios."""
from __future__ import annotations

import calendar as _calendar
import html as _html
import re as _re
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..services import beneficios as bf, payroll_engine as pe, relatorios_folha, dp_parametros
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from services import beneficios as bf, payroll_engine as pe, relatorios_folha, dp_parametros

router = APIRouter(prefix="/api/dp/beneficios", tags=["Departamento Pessoal — Benefícios"])


# ── utilitários ──────────────────────────────────────────────────────────────
def _cid(u: Dict[str, Any]) -> int:
    return int(u.get("company_id", 1))


def _rows(conn, sql: str, params=()) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _num(v: Any, campo: str, minimo: float = 0.0, maximo: Optional[float] = None) -> float:
    try:
        n = float(str(v if v not in (None, "") else 0).replace(",", "."))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{campo}: informe um número.")
    if n < minimo or (maximo is not None and n > maximo):
        faixa = f"entre {minimo:g} e {maximo:g}" if maximo is not None else f"maior ou igual a {minimo:g}"
        raise HTTPException(status_code=422, detail=f"{campo}: deve ser {faixa}.")
    return round(n, 2)


def _comp(v: Any) -> str:
    v = str(v or "")
    if not _re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", v):
        raise HTTPException(status_code=422, detail="Competência no formato AAAA-MM.")
    return v


def _data(v: Any, campo: str, obrigatoria: bool = True) -> str:
    if not v:
        if obrigatoria:
            raise HTTPException(status_code=422, detail=f"{campo}: obrigatória.")
        return ""
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{campo}: data inválida.")


def _emp(conn, cid: int, emp_id: Any) -> Dict[str, Any]:
    r = conn.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (emp_id, cid)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return dict(r)


def _plano(conn, cid: int, plano_id: Any) -> Dict[str, Any]:
    r = conn.execute("SELECT * FROM planos_saude WHERE id=? AND company_id=?", (plano_id, cid)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    return dict(r)


def _audit(conn, u, action: str, entity: str, entity_id: Any, dados: Any = None) -> None:
    log_audit(conn, action=action, entity=entity, entity_id=entity_id, new_data=dados,
              user_id=u.get("id"), company_id=_cid(u))


def _fim_mes(comp: str) -> date:
    a, m = int(comp[:4]), int(comp[5:7])
    return date(a, m, _calendar.monthrange(a, m)[1])


def _empresa(conn, cid: int) -> Dict[str, Any]:
    return dict(conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone() or {})


def _agora() -> str:
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Cuiaba")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return datetime.now().strftime("%d/%m/%Y %H:%M")


def _saida(rel: Dict[str, Any], formato: str, nome: str, conn, cid: int):
    if formato == "csv":
        return Response(content=relatorios_folha.para_csv(rel), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{nome}.csv"'})
    return HTMLResponse(content=relatorios_folha.para_html(rel, _empresa(conn, cid), _agora()))


# ── Planos de saúde ──────────────────────────────────────────────────────────
_CAMPOS_PLANO = ("nome", "tipo", "operadora", "cnpj_operadora", "registro_ans", "modalidade_valor",
                 "valor_fixo_titular", "valor_fixo_dependente", "pct_empresa_titular",
                 "pct_empresa_dependente", "copart_pct_empregado", "ativo")


def _validar_plano(d: Dict[str, Any]) -> Dict[str, Any]:
    nome = str(d.get("nome") or "").strip()
    if not nome:
        raise HTTPException(status_code=422, detail="Informe o nome do plano.")
    tipo = str(d.get("tipo") or "saude")
    if tipo not in ("saude", "odonto"):
        raise HTTPException(status_code=422, detail="Tipo do plano: saude ou odonto.")
    mod = str(d.get("modalidade_valor") or "faixa")
    if mod not in ("faixa", "fixo"):
        raise HTTPException(status_code=422, detail="Valor do plano: por faixa etária ou fixo.")
    cnpj = _re.sub(r"\D", "", str(d.get("cnpj_operadora") or ""))
    if cnpj and len(cnpj) != 14:
        raise HTTPException(status_code=422, detail="CNPJ da operadora deve ter 14 dígitos.")
    return {
        "nome": nome[:120], "tipo": tipo, "operadora": str(d.get("operadora") or "").strip()[:120],
        "cnpj_operadora": cnpj, "registro_ans": _re.sub(r"\D", "", str(d.get("registro_ans") or ""))[:6],
        "modalidade_valor": mod,
        "valor_fixo_titular": _num(d.get("valor_fixo_titular"), "Valor do titular"),
        "valor_fixo_dependente": _num(d.get("valor_fixo_dependente"), "Valor por dependente"),
        "pct_empresa_titular": _num(d.get("pct_empresa_titular"), "% pago pela empresa (titular)", 0, 100),
        "pct_empresa_dependente": _num(d.get("pct_empresa_dependente"), "% pago pela empresa (dependentes)", 0, 100),
        "copart_pct_empregado": _num(100 if d.get("copart_pct_empregado") in (None, "") else d.get("copart_pct_empregado"),
                                     "% da coparticipação descontado do empregado", 0, 100),
        "ativo": 0 if d.get("ativo") in (False, 0, "0", "false") else 1,
    }


def _gravar_faixas(conn, plano_id: int, faixas: Optional[List[Dict[str, Any]]]) -> None:
    if faixas is None:
        return
    try:
        ok = bf.validar_faixas(faixas)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    conn.execute("DELETE FROM planos_saude_faixas WHERE plano_id=?", (plano_id,))
    for f in ok:
        conn.execute("INSERT INTO planos_saude_faixas (plano_id, idade_min, idade_max, valor) VALUES (?,?,?,?)",
                     (plano_id, f["idade_min"], f["idade_max"], f["valor"]))


def _faixas(conn, plano_id: int) -> List[Dict[str, Any]]:
    return _rows(conn, "SELECT idade_min, idade_max, valor FROM planos_saude_faixas WHERE plano_id=? ORDER BY idade_min",
                 (plano_id,))


@router.get("/faixas-ans")
def faixas_ans(u: Dict[str, Any] = Depends(get_current_user)):
    return bf.faixas_padrao_ans()


@router.get("/planos")
def listar_planos(u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        planos = _rows(conn, """SELECT p.*, (SELECT COUNT(*) FROM employee_planos_saude a
                                 WHERE a.plano_id=p.id AND a.ativo=1) AS adesoes
                                FROM planos_saude p WHERE p.company_id=? ORDER BY p.ativo DESC, p.nome""", (_cid(u),))
        for p in planos:
            p["faixas"] = _faixas(conn, p["id"])
        return planos
    finally:
        conn.close()


@router.post("/planos", status_code=201)
def criar_plano(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    v = _validar_plano(data)
    faixas = data.get("faixas")
    if faixas is None and v["modalidade_valor"] == "faixa":
        faixas = bf.faixas_padrao_ans()
    conn = get_conn()
    try:
        cur = conn.execute(f"INSERT INTO planos_saude (company_id, {', '.join(v)}) VALUES (?{', ?' * len(v)})",
                           (_cid(u), *v.values()))
        pid = cur.lastrowid
        _gravar_faixas(conn, pid, faixas)
        _audit(conn, u, "create", "planos_saude", pid, v)
        conn.commit()
        return {**v, "id": pid, "faixas": _faixas(conn, pid)}
    finally:
        conn.close()


@router.put("/planos/{plano_id}")
def editar_plano(plano_id: int, data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        atual = _plano(conn, _cid(u), plano_id)
        v = _validar_plano({**atual, **data})
        conn.execute(f"UPDATE planos_saude SET {', '.join(f'{k}=?' for k in v)} WHERE id=? AND company_id=?",
                     (*v.values(), plano_id, _cid(u)))
        _gravar_faixas(conn, plano_id, data.get("faixas"))
        _audit(conn, u, "update", "planos_saude", plano_id, v)
        conn.commit()
        return {**v, "id": plano_id, "faixas": _faixas(conn, plano_id)}
    finally:
        conn.close()


@router.delete("/planos/{plano_id}")
def excluir_plano(plano_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        _plano(conn, _cid(u), plano_id)
        if conn.execute("SELECT COUNT(*) FROM employee_planos_saude WHERE plano_id=? AND ativo=1", (plano_id,)).fetchone()[0]:
            raise HTTPException(status_code=400, detail="Há funcionários neste plano. Encerre as adesões ou desative o plano.")
        conn.execute("DELETE FROM planos_saude_faixas WHERE plano_id=?", (plano_id,))
        conn.execute("DELETE FROM planos_saude_copart WHERE plano_id=? AND company_id=?", (plano_id, _cid(u)))
        conn.execute("DELETE FROM employee_planos_saude WHERE plano_id=? AND company_id=?", (plano_id, _cid(u)))
        conn.execute("DELETE FROM planos_saude WHERE id=? AND company_id=?", (plano_id, _cid(u)))
        _audit(conn, u, "delete", "planos_saude", plano_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── Adesões ──────────────────────────────────────────────────────────────────
def _dependentes_plano(conn, cid: int, emp_id: int) -> List[Dict[str, Any]]:
    return _rows(conn, """SELECT id, nome, cpf, data_nascimento, parentesco FROM employee_dependents
                          WHERE company_id=? AND employee_id=? AND plano_saude=1 ORDER BY nome""", (cid, emp_id))


def _mensalidade(conn, cid: int, adesao: Dict[str, Any], comp: str) -> Dict[str, Any]:
    plano = _plano(conn, cid, adesao["plano_id"])
    emp = _emp(conn, cid, adesao["employee_id"])
    deps = _dependentes_plano(conn, cid, emp["id"]) if int(adesao.get("incluir_dependentes", 1) or 0) else []
    m = bf.mensalidade_plano(plano, _faixas(conn, plano["id"]), emp.get("birth_date"), deps, _fim_mes(comp))
    return {**m, "plano": plano["nome"], "employee_id": emp["id"], "employee_name": emp["name"]}


@router.get("/adesoes")
def listar_adesoes(employee_id: Optional[int] = None, competencia: str = "",
                   u: Dict[str, Any] = Depends(get_current_user)):
    comp = _comp(competencia) if competencia else date.today().strftime("%Y-%m")
    conn = get_conn()
    try:
        sql = """SELECT a.*, p.nome AS plano_nome, e.name AS employee_name FROM employee_planos_saude a
                 JOIN planos_saude p ON p.id=a.plano_id JOIN employees e ON e.id=a.employee_id
                 WHERE a.company_id=?"""
        params: List[Any] = [_cid(u)]
        if employee_id:
            sql += " AND a.employee_id=?"
            params.append(employee_id)
        out = _rows(conn, sql + " ORDER BY e.name, p.nome", params)
        for a in out:
            m = _mensalidade(conn, _cid(u), a, comp)
            a.update(vidas=m["vidas"], total=m["total"], empresa=m["empresa"], empregado=m["empregado"],
                     avisos=m["avisos"])
        return out
    finally:
        conn.close()


def _validar_adesao(conn, cid: int, d: Dict[str, Any]) -> Dict[str, Any]:
    _emp(conn, cid, d.get("employee_id"))
    _plano(conn, cid, d.get("plano_id"))
    ini = _data(d.get("data_inicio"), "Início da adesão")
    fim = _data(d.get("data_fim"), "Fim da adesão", obrigatoria=False)
    if fim and fim < ini:
        raise HTTPException(status_code=422, detail="O fim da adesão é anterior ao início.")
    return {"employee_id": int(d["employee_id"]), "plano_id": int(d["plano_id"]), "data_inicio": ini,
            "data_fim": fim, "incluir_dependentes": 0 if d.get("incluir_dependentes") in (False, 0, "0", "false") else 1,
            "carteirinha": str(d.get("carteirinha") or "").strip()[:40],
            "ativo": 0 if d.get("ativo") in (False, 0, "0", "false") else 1}


@router.post("/adesoes", status_code=201)
def criar_adesao(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        v = _validar_adesao(conn, _cid(u), data)
        if conn.execute("""SELECT COUNT(*) FROM employee_planos_saude WHERE company_id=? AND employee_id=?
                           AND plano_id=? AND ativo=1 AND (data_fim='' OR data_fim IS NULL OR data_fim>=?)""",
                        (_cid(u), v["employee_id"], v["plano_id"], v["data_inicio"])).fetchone()[0]:
            raise HTTPException(status_code=400, detail="O funcionário já tem adesão ativa neste plano.")
        cur = conn.execute(f"INSERT INTO employee_planos_saude (company_id, {', '.join(v)}) VALUES (?{', ?' * len(v)})",
                           (_cid(u), *v.values()))
        _audit(conn, u, "create", "employee_planos_saude", cur.lastrowid, v)
        conn.commit()
        return {**v, "id": cur.lastrowid}
    finally:
        conn.close()


@router.put("/adesoes/{adesao_id}")
def editar_adesao(adesao_id: int, data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        atual = conn.execute("SELECT * FROM employee_planos_saude WHERE id=? AND company_id=?", (adesao_id, _cid(u))).fetchone()
        if not atual:
            raise HTTPException(status_code=404, detail="Adesão não encontrada.")
        v = _validar_adesao(conn, _cid(u), {**dict(atual), **data})
        conn.execute(f"UPDATE employee_planos_saude SET {', '.join(f'{k}=?' for k in v)} WHERE id=?", (*v.values(), adesao_id))
        _audit(conn, u, "update", "employee_planos_saude", adesao_id, v)
        conn.commit()
        return {**v, "id": adesao_id}
    finally:
        conn.close()


@router.delete("/adesoes/{adesao_id}")
def excluir_adesao(adesao_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        n = conn.execute("DELETE FROM employee_planos_saude WHERE id=? AND company_id=?", (adesao_id, _cid(u))).rowcount
        if not n:
            raise HTTPException(status_code=404, detail="Adesão não encontrada.")
        _audit(conn, u, "delete", "employee_planos_saude", adesao_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── Coparticipação ───────────────────────────────────────────────────────────
@router.get("/copart")
def listar_copart(competencia: str, employee_id: Optional[int] = None, u: Dict[str, Any] = Depends(get_current_user)):
    comp = _comp(competencia)
    conn = get_conn()
    try:
        sql = """SELECT c.*, e.name AS employee_name, p.nome AS plano_nome FROM planos_saude_copart c
                 JOIN employees e ON e.id=c.employee_id JOIN planos_saude p ON p.id=c.plano_id
                 WHERE c.company_id=? AND c.competencia=?"""
        params: List[Any] = [_cid(u), comp]
        if employee_id:
            sql += " AND c.employee_id=?"
            params.append(employee_id)
        return _rows(conn, sql + " ORDER BY e.name, c.id", params)
    finally:
        conn.close()


def _inserir_copart(conn, cid: int, emp_id: int, plano_id: int, comp: str, benef: str, desc: str, valor: float) -> int:
    if not conn.execute("""SELECT COUNT(*) FROM employee_planos_saude WHERE company_id=? AND employee_id=? AND plano_id=?""",
                        (cid, emp_id, plano_id)).fetchone()[0]:
        raise HTTPException(status_code=400, detail="O funcionário não tem adesão a este plano.")
    return conn.execute("""INSERT INTO planos_saude_copart (company_id, employee_id, plano_id, competencia, beneficiario,
                           descricao, valor) VALUES (?,?,?,?,?,?,?)""",
                        (cid, emp_id, plano_id, comp, benef[:80] or "Titular", desc[:200], valor)).lastrowid


@router.post("/copart", status_code=201)
def criar_copart(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    comp = _comp(data.get("competencia"))
    valor = _num(data.get("valor"), "Valor da coparticipação", 0.01)
    conn = get_conn()
    try:
        _emp(conn, _cid(u), data.get("employee_id"))
        _plano(conn, _cid(u), data.get("plano_id"))
        cid = _inserir_copart(conn, _cid(u), int(data["employee_id"]), int(data["plano_id"]), comp,
                              str(data.get("beneficiario") or "Titular").strip(), str(data.get("descricao") or "").strip(), valor)
        _audit(conn, u, "create", "planos_saude_copart", cid, {"competencia": comp, "valor": valor})
        conn.commit()
        return {"id": cid}
    finally:
        conn.close()


@router.post("/copart/importar")
def importar_copart(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    """Importa o extrato da operadora: uma linha por utilização, `CPF do titular;beneficiário;descrição;valor`
    (separador ; ou tab; cabeçalho opcional). Linhas com erro voltam na resposta e não interrompem as demais."""
    comp = _comp(data.get("competencia"))
    texto = str(data.get("texto") or "")
    conn = get_conn()
    try:
        plano = _plano(conn, _cid(u), data.get("plano_id"))
        por_cpf = {_re.sub(r"\D", "", str(e["cpf"] or "")): e["id"] for e in
                   _rows(conn, "SELECT id, cpf FROM employees WHERE company_id=?", (_cid(u),))}
        ok, erros = 0, []
        for n, linha in enumerate(texto.splitlines(), 1):
            if not linha.strip():
                continue
            partes = [p.strip() for p in _re.split(r"[;\t]", linha)]
            cpf = _re.sub(r"\D", "", partes[0])
            if n == 1 and not cpf:
                continue                                     # cabeçalho
            if len(partes) < 4:
                erros.append({"linha": n, "erro": "Esperado: CPF;beneficiário;descrição;valor"})
                continue
            emp_id = por_cpf.get(cpf)
            if not emp_id:
                erros.append({"linha": n, "erro": f"CPF {partes[0]} não é funcionário desta empresa"})
                continue
            try:
                valor = float(partes[3].replace(".", "").replace(",", ".") if "," in partes[3] else partes[3])
            except ValueError:
                erros.append({"linha": n, "erro": f"Valor inválido: {partes[3]}"})
                continue
            if valor <= 0:
                erros.append({"linha": n, "erro": "Valor deve ser maior que zero"})
                continue
            try:
                _inserir_copart(conn, _cid(u), emp_id, plano["id"], comp, partes[1], partes[2], round(valor, 2))
                ok += 1
            except HTTPException as e:
                erros.append({"linha": n, "erro": e.detail})
        _audit(conn, u, "create", "planos_saude_copart", plano["id"], {"importadas": ok, "competencia": comp})
        conn.commit()
        return {"importadas": ok, "erros": erros}
    finally:
        conn.close()


@router.delete("/copart/{copart_id}")
def excluir_copart(copart_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        if not conn.execute("DELETE FROM planos_saude_copart WHERE id=? AND company_id=?", (copart_id, _cid(u))).rowcount:
            raise HTTPException(status_code=404, detail="Lançamento não encontrado.")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/planos/conferencia")
def conferencia_plano(competencia: str, plano_id: Optional[int] = None, formato: str = "html",
                      u: Dict[str, Any] = Depends(get_current_user)):
    """Conferência com a fatura da operadora: vidas, mensalidade, parte da empresa e do empregado."""
    comp = _comp(competencia)
    if formato not in ("html", "csv"):
        raise HTTPException(status_code=422, detail="Formato deve ser html ou csv.")
    conn = get_conn()
    try:
        sql = """SELECT a.* FROM employee_planos_saude a JOIN employees e ON e.id=a.employee_id
                 WHERE a.company_id=? AND a.ativo=1 AND a.data_inicio<=?
                   AND (a.data_fim='' OR a.data_fim IS NULL OR a.data_fim>=?)"""
        params: List[Any] = [_cid(u), _fim_mes(comp).isoformat(), f"{comp}-01"]
        if plano_id:
            sql += " AND a.plano_id=?"
            params.append(plano_id)
        linhas, tot = [], {"valor": 0.0, "empresa": 0.0, "empregado": 0.0, "copart": 0.0}
        n_vidas = 0
        for a in _rows(conn, sql + " ORDER BY e.name", params):
            m = _mensalidade(conn, _cid(u), a, comp)
            for i, v in enumerate(m["vidas"]):
                linhas.append({"funcionario": m["employee_name"] if i == 0 else "", "plano": m["plano"] if i == 0 else "",
                               "beneficiario": v["beneficiario"], "idade": "" if v["idade"] is None else str(v["idade"]),
                               "valor": v["valor"], "empresa": v["empresa"], "empregado": v["empregado"]})
                n_vidas += 1
            cop = conn.execute("""SELECT COALESCE(SUM(valor),0) FROM planos_saude_copart WHERE company_id=? AND employee_id=?
                                  AND plano_id=? AND competencia=?""", (_cid(u), a["employee_id"], a["plano_id"], comp)).fetchone()[0]
            if cop:
                linhas.append({"beneficiario": "Coparticipação do mês", "copart": round(float(cop), 2)})
                tot["copart"] += float(cop)
            for k in ("valor", "empresa", "empregado"):
                tot[k] += m[{"valor": "total"}.get(k, k)]
        linhas.append({"_cls": "tot", "funcionario": f"Total — {n_vidas} vida(s)",
                       **{k: round(v, 2) for k, v in tot.items()}})
        rel = {"titulo": "Conferência do plano de saúde", "subtitulo": f"Competência {comp}", "paisagem": True,
               "nota": "Mensalidade pela faixa etária na data do fim da competência (RN 63/2003 da ANS).",
               "colunas": [relatorios_folha._col("funcionario", "Funcionário"), relatorios_folha._col("plano", "Plano"),
                           relatorios_folha._col("beneficiario", "Beneficiário"), relatorios_folha._col("idade", "Idade"),
                           relatorios_folha._col("valor", "Mensalidade", True), relatorios_folha._col("empresa", "Empresa", True),
                           relatorios_folha._col("empregado", "Empregado", True), relatorios_folha._col("copart", "Coparticipação", True)],
               "linhas": linhas}
        return _saida(rel, formato, "conferencia-plano", conn, _cid(u))
    finally:
        conn.close()


# ── Consignado ───────────────────────────────────────────────────────────────
def _validar_consignado(conn, cid: int, d: Dict[str, Any]) -> Dict[str, Any]:
    _emp(conn, cid, d.get("employee_id"))
    origem = str(d.get("origem") or "credito_trabalhador")
    if origem not in bf.ORIGENS_CONSIGNADO:
        raise HTTPException(status_code=422, detail="Origem do consignado: credito_trabalhador ou convenio.")
    parcelas = int(_num(d.get("parcelas_total"), "Quantidade de parcelas", 1, 200))
    return {"employee_id": int(d["employee_id"]), "origem": origem,
            "instituicao": str(d.get("instituicao") or "").strip()[:120],
            "contrato": str(d.get("contrato") or "").strip()[:60],
            "valor_parcela": _num(d.get("valor_parcela"), "Valor da parcela", 0.01),
            "parcelas_total": parcelas, "competencia_inicio": _comp(d.get("competencia_inicio")),
            "saldo_devedor": _num(d.get("saldo_devedor"), "Saldo devedor"),
            "desconta_rescisao": 0 if d.get("desconta_rescisao") in (False, 0, "0", "false") else 1,
            "ativo": 0 if d.get("ativo") in (False, 0, "0", "false") else 1,
            "observacoes": str(d.get("observacoes") or "").strip()[:300]}


@router.get("/consignados")
def listar_consignados(employee_id: Optional[int] = None, competencia: str = "",
                       u: Dict[str, Any] = Depends(get_current_user)):
    comp = _comp(competencia) if competencia else date.today().strftime("%Y-%m")
    conn = get_conn()
    try:
        sql = """SELECT c.*, e.name AS employee_name FROM emprestimos_consignados c JOIN employees e ON e.id=c.employee_id
                 WHERE c.company_id=?"""
        params: List[Any] = [_cid(u)]
        if employee_id:
            sql += " AND c.employee_id=?"
            params.append(employee_id)
        out = _rows(conn, sql + " ORDER BY e.name, c.competencia_inicio", params)
        for c in out:
            n, v = bf.parcela_do_mes(c, comp)
            c.update(parcela_atual=n, valor_mes=v, origem_nome=bf.ORIGENS_CONSIGNADO.get(c["origem"], c["origem"]),
                     saldo_estimado=bf.saldo_rescisao({**c, "saldo_devedor": 0}, comp))
        return out
    finally:
        conn.close()


@router.post("/consignados", status_code=201)
def criar_consignado(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        v = _validar_consignado(conn, _cid(u), data)
        cur = conn.execute(f"INSERT INTO emprestimos_consignados (company_id, {', '.join(v)}) VALUES (?{', ?' * len(v)})",
                           (_cid(u), *v.values()))
        _audit(conn, u, "create", "emprestimos_consignados", cur.lastrowid, v)
        conn.commit()
        return {**v, "id": cur.lastrowid}
    finally:
        conn.close()


@router.put("/consignados/{cons_id}")
def editar_consignado(cons_id: int, data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        atual = conn.execute("SELECT * FROM emprestimos_consignados WHERE id=? AND company_id=?", (cons_id, _cid(u))).fetchone()
        if not atual:
            raise HTTPException(status_code=404, detail="Contrato não encontrado.")
        v = _validar_consignado(conn, _cid(u), {**dict(atual), **data})
        conn.execute(f"UPDATE emprestimos_consignados SET {', '.join(f'{k}=?' for k in v)} WHERE id=?", (*v.values(), cons_id))
        _audit(conn, u, "update", "emprestimos_consignados", cons_id, v)
        conn.commit()
        return {**v, "id": cons_id}
    finally:
        conn.close()


@router.delete("/consignados/{cons_id}")
def excluir_consignado(cons_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        if not conn.execute("DELETE FROM emprestimos_consignados WHERE id=? AND company_id=?", (cons_id, _cid(u))).rowcount:
            raise HTTPException(status_code=404, detail="Contrato não encontrado.")
        _audit(conn, u, "delete", "emprestimos_consignados", cons_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/consignados/margem/{employee_id}")
def margem_consignavel(employee_id: int, competencia: str = "", u: Dict[str, Any] = Depends(get_current_user)):
    """Margem pela última folha mensal processada do funcionário (até a competência informada)."""
    conn = get_conn()
    try:
        emp = _emp(conn, _cid(u), employee_id)
        pct = float(dp_parametros.carregar(conn, _cid(u)).get("consignado_margem_pct") or bf.MARGEM_PADRAO)
        comp = _comp(competencia) if competencia else "9999-12"
        run = conn.execute("""SELECT pr.id, pr.competence FROM payroll_runs pr JOIN payroll_items pi ON pi.run_id=pr.id
                              WHERE pr.company_id=? AND pi.employee_id=? AND pr.status != 'cancelado'
                                AND COALESCE(pr.tipo,'mensal')='mensal' AND pr.competence<=?
                              ORDER BY pr.competence DESC, pr.id DESC LIMIT 1""", (_cid(u), employee_id, comp)).fetchone()
        if not run:
            raise HTTPException(status_code=400, detail="Nenhuma folha processada para este funcionário: calcule a folha primeiro.")
        run = dict(run)
        lin = _rows(conn, "SELECT codigo, tipo, valor FROM payroll_item_lines WHERE run_id=? AND employee_id=?",
                    (run["id"], employee_id))
        cods = {k: pe.SYSTEM_RUBRICS[k][0] for k in ("INSS", "IRRF", "PENSAO", "CONSIGNADO", "CONSIGNADO_CONV")}
        soma = lambda *cs: round(sum(float(l["valor"] or 0) for l in lin if l["codigo"] in cs), 2)
        bruto = round(sum(float(l["valor"] or 0) for l in lin if l["tipo"] == "provento"), 2)
        obrig = soma(cods["INSS"], cods["IRRF"], cods["PENSAO"])
        total = bf.margem(bruto, obrig, pct)
        usada = soma(cods["CONSIGNADO"], cods["CONSIGNADO_CONV"])
        return {"employee_id": employee_id, "employee_name": emp["name"], "competencia": run["competence"],
                "bruto": bruto, "descontos_obrigatorios": obrig, "remuneracao_disponivel": round(bruto - obrig, 2),
                "percentual": pct, "margem_total": total, "margem_utilizada": usada,
                "margem_disponivel": round(max(0.0, total - usada), 2)}
    finally:
        conn.close()


# ── Vale-transporte: compra e recibo ─────────────────────────────────────────
def _vt_da_competencia(conn, cid: int, comp: str, employee_id: Optional[int] = None) -> List[Dict[str, Any]]:
    cal = pe.month_calendar(conn, cid, comp)
    ini, fim = cal["inicio"], cal["fim"]
    sql = """SELECT e.* FROM employees e WHERE e.company_id=? AND e.active=1
             AND EXISTS (SELECT 1 FROM employee_vt v WHERE v.employee_id=e.id AND v.company_id=e.company_id AND v.ativo=1)"""
    params: List[Any] = [cid]
    if employee_id:
        sql += " AND e.id=?"
        params.append(employee_id)
    out = []
    for e in _rows(conn, sql + " ORDER BY e.name", params):
        adm = pe._parse_date(e.get("admission_date"))
        if adm and adm > fim:
            continue
        fora = [(pe._parse_date(f["data_inicio"]), pe._parse_date(f["data_fim"])) for f in _rows(conn,
                """SELECT data_inicio, data_fim FROM payroll_special WHERE company_id=? AND employee_id=? AND tipo='ferias'
                   AND status != 'cancelado'""", (cid, e["id"]))]
        fora += [(pe._parse_date(a["data_inicio"]), pe._parse_date(a["data_fim"]) or fim) for a in _rows(conn,
                 "SELECT data_inicio, data_fim FROM employee_absences WHERE company_id=? AND employee_id=?", (cid, e["id"]))]
        faltas = {pe._parse_date(t["data"]) for t in _rows(conn,
                  """SELECT data FROM time_records WHERE company_id=? AND employee_id=? AND data LIKE ?
                     AND tipo_ocorrencia='falta_injustificada'""", (cid, e["id"], f"{comp}%"))}
        dias = bf.dias_uso_vt(ini, fim, cal["feriados"], adm, pe._parse_date(e.get("termination_date")), fora, faltas)
        itens = bf.itens_vt(_rows(conn, "SELECT * FROM employee_vt WHERE company_id=? AND employee_id=? AND ativo=1 ORDER BY id",
                                  (cid, e["id"])), dias)
        custo = round(sum(i["valor"] for i in itens), 2)
        desconto = 0.0 if e.get("is_prolabore") else bf.desconto_vt(float(e.get("salary") or 0), custo)
        out.append({"employee": e, "dias_uso": dias, "itens": itens, "custo": custo, "desconto": desconto,
                    "empresa": round(custo - desconto, 2)})
    return out


@router.get("/vt/compra")
def vt_compra(competencia: str, formato: str = "html", u: Dict[str, Any] = Depends(get_current_user)):
    """Pedido de compra do VT da competência: vales por linha, valor, desconto de 6% e custo da empresa."""
    comp = _comp(competencia)
    if formato not in ("html", "csv"):
        raise HTTPException(status_code=422, detail="Formato deve ser html ou csv.")
    conn = get_conn()
    try:
        dados = _vt_da_competencia(conn, _cid(u), comp)
        linhas = []
        tot = {"quantidade": 0, "valor": 0.0, "desconto": 0.0, "empresa": 0.0}
        for d in dados:
            for i, it in enumerate(d["itens"]):
                linhas.append({"matricula": d["employee"].get("matricula") or "" if i == 0 else "",
                               "nome": d["employee"]["name"] if i == 0 else "", "linha": it["descricao"],
                               "tarifa": it["tarifa"], "vales": f"{it['vales_dia']} × {it['dias']} d = {it['quantidade']}",
                               "valor": it["valor"]})
                tot["quantidade"] += it["quantidade"]
            linhas.append({"_cls": "sub", "nome": "", "linha": f"Subtotal — {d['dias_uso']} dia(s) de uso",
                           "valor": d["custo"], "desconto": d["desconto"], "empresa": d["empresa"]})
            for k in ("valor", "desconto", "empresa"):
                tot[k] += d["custo" if k == "valor" else k]
        linhas.append({"_cls": "tot", "nome": f"Total — {len(dados)} funcionário(s)", "vales": f"{tot['quantidade']} vales",
                       **{k: round(tot[k], 2) for k in ("valor", "desconto", "empresa")}})
        c = relatorios_folha._col
        rel = {"titulo": "Compra de vale-transporte", "subtitulo": f"Competência {comp}", "paisagem": True,
               "nota": "Dias úteis de segunda a sexta, sem feriados, férias, afastamentos e faltas já lançados. "
                       "Desconto do empregado: 6% do salário básico, limitado ao custo (Lei 7.418/85).",
               "colunas": [c("matricula", "Matrícula"), c("nome", "Funcionário"), c("linha", "Linha / trajeto"),
                           c("tarifa", "Tarifa", True), c("vales", "Vales"), c("valor", "Valor", True),
                           c("desconto", "Desconto 6%", True), c("empresa", "Custo empresa", True)],
               "linhas": linhas}
        return _saida(rel, formato, f"compra-vt-{comp}", conn, _cid(u))
    finally:
        conn.close()


def _br(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@router.get("/vt/recibo", response_class=HTMLResponse)
def vt_recibo(competencia: str, employee_id: Optional[int] = None, u: Dict[str, Any] = Depends(get_current_user)):
    """Recibo de entrega do vale-transporte (um por funcionário, para assinar)."""
    comp = _comp(competencia)
    conn = get_conn()
    try:
        if employee_id:
            _emp(conn, _cid(u), employee_id)
        dados = _vt_da_competencia(conn, _cid(u), comp, employee_id)
        emp_co = _empresa(conn, _cid(u))
    finally:
        conn.close()
    if not dados:
        raise HTTPException(status_code=404, detail="Nenhum funcionário com vale-transporte cadastrado.")
    esc = _html.escape
    mes = f"{comp[5:7]}/{comp[:4]}"
    blocos = []
    for d in dados:
        e = d["employee"]
        trs = "".join(f"<tr><td>{esc(i['descricao'])}</td><td class=n>{_br(i['tarifa'])}</td><td class=n>{i['vales_dia']}</td>"
                      f"<td class=n>{i['dias']}</td><td class=n>{i['quantidade']}</td><td class=n>{_br(i['valor'])}</td></tr>"
                      for i in d["itens"])
        blocos.append(f"""<section class="rec">
  <h2>Recibo de entrega de vale-transporte</h2>
  <p class="cab"><b>{esc(emp_co.get('name') or emp_co.get('razao_social') or '')}</b> · CNPJ {esc(emp_co.get('cnpj') or '')}</p>
  <p>Funcionário: <b>{esc(e['name'])}</b> · Matrícula {esc(e.get('matricula') or '-')} · Competência <b>{mes}</b></p>
  <table><thead><tr><th>Linha / trajeto</th><th>Tarifa</th><th>Vales/dia</th><th>Dias</th><th>Quantidade</th><th>Valor</th></tr></thead>
  <tbody>{trs}</tbody>
  <tfoot><tr><td colspan=5>Total entregue</td><td class=n>{_br(d['custo'])}</td></tr>
  <tr><td colspan=5>Desconto em folha (6% do salário básico, limitado ao custo)</td><td class=n>{_br(d['desconto'])}</td></tr></tfoot></table>
  <p class="decl">Declaro ter recebido os vales-transporte acima, para uso exclusivo no deslocamento residência–trabalho e vice-versa,
  e autorizo o desconto em folha de pagamento nos termos da Lei 7.418/85.</p>
  <div class="ass"><div>____/____/________<br>Data</div><div>______________________________________<br>{esc(e['name'])}</div></div>
</section>""")
    return HTMLResponse(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Recibo de VT {mes}</title>
<style>body{{font-family:Arial,sans-serif;font-size:12px;color:#111;margin:0;padding:16px}}
.rec{{border:1px solid #999;padding:14px 18px;margin:0 0 18px;page-break-inside:avoid}}
.rec:nth-of-type(2n){{page-break-after:always}}h2{{font-size:15px;margin:0 0 6px}}.cab{{margin:0 0 8px;color:#333}}
table{{width:100%;border-collapse:collapse;margin:8px 0}}th,td{{border:1px solid #bbb;padding:4px 6px;text-align:left}}
th{{background:#f1f1f1}}.n{{text-align:right}}tfoot td{{font-weight:bold}}.decl{{margin:10px 0 26px}}
.ass{{display:flex;justify-content:space-between;text-align:center}}@media print{{body{{padding:0}}}}</style></head>
<body>{''.join(blocos)}<script>window.onload=()=>setTimeout(()=>window.print(),300)</script></body></html>""")


# ── Vale-transporte: linhas por funcionário ──────────────────────────────────
def _validar_linha_vt(conn, cid: int, d: Dict[str, Any]) -> Dict[str, Any]:
    _emp(conn, cid, d.get("employee_id"))
    return {"employee_id": int(d["employee_id"]),
            "descricao": str(d.get("descricao") or "").strip()[:120] or "Vale-transporte",
            "tarifa": _num(d.get("tarifa"), "Tarifa", 0.01),
            "vales_dia": int(_num(d.get("vales_dia") if d.get("vales_dia") not in (None, "") else 2, "Vales por dia", 1, 10)),
            "dias_mes": int(_num(d.get("dias_mes"), "Dias fixos no mês", 0, 31)),
            "ativo": 0 if d.get("ativo") in (False, 0, "0", "false") else 1}


@router.get("/vt/linhas")
def listar_linhas_vt(employee_id: Optional[int] = None, competencia: str = "",
                     u: Dict[str, Any] = Depends(get_current_user)):
    """Linhas cadastradas e, com a competência, a prévia do mês (dias de uso, custo e desconto)."""
    conn = get_conn()
    try:
        sql = """SELECT v.*, e.name AS employee_name FROM employee_vt v JOIN employees e ON e.id=v.employee_id
                 WHERE v.company_id=?"""
        params: List[Any] = [_cid(u)]
        if employee_id:
            sql += " AND v.employee_id=?"
            params.append(employee_id)
        linhas = _rows(conn, sql + " ORDER BY e.name, v.id", params)
        previa = []
        if competencia:
            for d in _vt_da_competencia(conn, _cid(u), _comp(competencia), employee_id):
                previa.append({"employee_id": d["employee"]["id"], "employee_name": d["employee"]["name"],
                               "dias_uso": d["dias_uso"], "custo": d["custo"], "desconto": d["desconto"],
                               "empresa": d["empresa"]})
        return {"linhas": linhas, "previa": previa}
    finally:
        conn.close()


@router.post("/vt/linhas", status_code=201)
def criar_linha_vt(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        v = _validar_linha_vt(conn, _cid(u), data)
        cur = conn.execute(f"INSERT INTO employee_vt (company_id, {', '.join(v)}) VALUES (?{', ?' * len(v)})",
                           (_cid(u), *v.values()))
        _audit(conn, u, "create", "employee_vt", cur.lastrowid, v)
        conn.commit()
        return {**v, "id": cur.lastrowid}
    finally:
        conn.close()


@router.put("/vt/linhas/{linha_id}")
def editar_linha_vt(linha_id: int, data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        atual = conn.execute("SELECT * FROM employee_vt WHERE id=? AND company_id=?", (linha_id, _cid(u))).fetchone()
        if not atual:
            raise HTTPException(status_code=404, detail="Linha não encontrada.")
        v = _validar_linha_vt(conn, _cid(u), {**dict(atual), **data})
        conn.execute(f"UPDATE employee_vt SET {', '.join(f'{k}=?' for k in v)} WHERE id=?", (*v.values(), linha_id))
        _audit(conn, u, "update", "employee_vt", linha_id, v)
        conn.commit()
        return {**v, "id": linha_id}
    finally:
        conn.close()


@router.delete("/vt/linhas/{linha_id}")
def excluir_linha_vt(linha_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        if not conn.execute("DELETE FROM employee_vt WHERE id=? AND company_id=?", (linha_id, _cid(u))).rowcount:
            raise HTTPException(status_code=404, detail="Linha não encontrada.")
        _audit(conn, u, "delete", "employee_vt", linha_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
