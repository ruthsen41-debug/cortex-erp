"""DP — automação e utilitários (bloco 5 da paridade):

- Pagamentos: lança a folha e as guias (líquidos, FGTS, INSS, IRRF, pensões e consignado) no contas a
  pagar com os vencimentos legais, e dá baixa em lote.
- Alteração em grupo: salário (percentual, valor ou novo salário, com histórico), cargo/CBO,
  departamento, centro de custo, escala e convenção.
- Exclusão em grupo de férias, 13º, rescisões e RPA.
- Acerto da data de pagamento de folhas, recibos especiais e RPA (data do S-1210 e do IRRF).
- Rotinas automáticas (calcular a folha, enviar holerites, lançar no financeiro) com execução agendada.
"""
from __future__ import annotations

import json as _json
import os
import re as _re
import threading
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..schemas.dp import PayrollRunCreate
    from ..schemas.financial import BatchPayRequest
    from ..services import dp_rotinas as rt, payroll_engine as pe
    from . import dp as _dp
    from . import financial as _fin
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from schemas.dp import PayrollRunCreate
    from schemas.financial import BatchPayRequest
    from services import dp_rotinas as rt, payroll_engine as pe
    from routers import dp as _dp
    from routers import financial as _fin

router = APIRouter(prefix="/api/dp/utilitarios", tags=["Departamento Pessoal — Utilitários"])


def _cid(u: Dict[str, Any]) -> int:
    return int(u.get("company_id", 1))


def _rows(conn, sql: str, params=()) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _comp(v: Any) -> str:
    v = str(v or "")[:7]
    if not _re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", v):
        raise HTTPException(status_code=422, detail="Competência no formato AAAA-MM.")
    return v


def _data(v: Any, campo: str) -> str:
    try:
        return date.fromisoformat(str(v or "")[:10]).isoformat()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{campo}: data inválida (AAAA-MM-DD).")


def _pode(u: Dict[str, Any]) -> None:
    if not u.get("is_superadmin") and (u.get("role") or "") not in ("admin", "dp"):
        raise HTTPException(status_code=403, detail="Apenas administrador ou Depto. Pessoal podem usar esta rotina.")


def _audit(conn, u, action: str, entity: str, entity_id: Any = None, dados: Any = None) -> None:
    log_audit(conn, action=action, entity=entity, entity_id=entity_id, new_data=dados,
              user_id=u.get("id"), company_id=_cid(u))


def _competencia_fechada(conn, cid: int, comp: str) -> bool:
    return bool(comp and conn.execute(
        "SELECT COUNT(*) FROM payroll_competencias WHERE company_id=? AND competencia=? AND status='fechada'",
        (cid, comp[:7])).fetchone()[0])


def _feriados(conn, cid: int, comp: str):
    return pe.month_calendar(conn, cid, comp)["feriados"]


# ══ 1. Pagamentos: folha e guias no contas a pagar ═══════════════════════════
def _categoria(conn, codigo: str) -> Optional[int]:
    r = conn.execute("SELECT id FROM categories WHERE code=? LIMIT 1", (codigo,)).fetchone() \
        or conn.execute("SELECT id FROM categories WHERE type='despesa' ORDER BY code LIMIT 1").fetchone()
    return r["id"] if r else None


def _titulos_da_folha(conn, cid: int, run: Dict[str, Any], por_funcionario: bool) -> List[Dict[str, Any]]:
    """Títulos a pagar da folha: (chave, descrição, valor, vencimento, categoria)."""
    comp = run["competence"]
    prox = rt.mes_seguinte(comp).strftime("%Y-%m")
    fer = _feriados(conn, cid, prox)
    v_sal, v_20 = rt.quinto_dia_util(comp, fer).isoformat(), rt.dia20_antecipado(comp, fer).isoformat()
    if run.get("data_pagamento"):
        v_sal = run["data_pagamento"][:10]
    rotulo = {"mensal": "Folha", "complementar": "Folha complementar", "dissidio": "Dissídio"}.get(run.get("tipo") or "mensal", "Folha")
    itens = _rows(conn, """SELECT pi.employee_id, pi.net_salary, e.name FROM payroll_items pi
                           JOIN employees e ON e.id=pi.employee_id WHERE pi.run_id=? ORDER BY e.name""", (run["id"],))
    linhas = _rows(conn, "SELECT employee_id, codigo, nome, valor FROM payroll_item_lines WHERE run_id=?", (run["id"],))
    soma = lambda cods: round(sum(float(l["valor"] or 0) for l in linhas if l["codigo"] in cods), 2)
    cod = lambda k: pe.SYSTEM_RUBRICS[k][0]
    out: List[Dict[str, Any]] = []
    k = f"DP{run['id']}"
    if por_funcionario:
        for it in itens:
            if float(it["net_salary"] or 0) > 0:
                out.append({"chave": f"{k}-LIQ-{it['employee_id']}", "descricao": f"{rotulo} {comp} — {it['name']}",
                            "valor": round(float(it["net_salary"]), 2), "vencimento": v_sal, "categoria": "4.01"})
    else:
        tot = round(sum(float(i["net_salary"] or 0) for i in itens), 2)
        if tot > 0:
            out.append({"chave": f"{k}-LIQ", "descricao": f"{rotulo} {comp} — líquidos ({len(itens)} funcionário(s))",
                        "valor": tot, "vencimento": v_sal, "categoria": "4.01"})
    for n, l in enumerate(l for l in linhas if l["codigo"] == cod("PENSAO") and float(l["valor"] or 0) > 0):
        out.append({"chave": f"{k}-PENS-{l['employee_id']}-{n}", "descricao": f"{l['nome']} ({comp})",
                    "valor": round(float(l["valor"]), 2), "vencimento": v_sal, "categoria": "4.01"})
    fgts = round(float(run.get("total_fgts") or 0), 2)
    if fgts > 0:
        out.append({"chave": f"{k}-FGTS", "descricao": f"FGTS Digital {comp} (guia GFD)", "valor": fgts,
                    "vencimento": v_20, "categoria": "4.02"})
    inss = soma({cod("INSS")})
    if inss > 0:
        out.append({"chave": f"{k}-INSS", "descricao": f"INSS retido dos empregados {comp} (DCTFWeb)", "valor": inss,
                    "vencimento": v_20, "categoria": "4.02"})
    irrf = soma({cod("IRRF")})
    if irrf > 0:
        out.append({"chave": f"{k}-IRRF", "descricao": f"IRRF da folha {comp} (DCTFWeb)", "valor": irrf,
                    "vencimento": v_20, "categoria": "4.02"})
    ct = soma({cod("CONSIGNADO")})
    if ct > 0:
        out.append({"chave": f"{k}-CTRAB", "descricao": f"Consignado Crédito do Trabalhador {comp} (guia do FGTS Digital)",
                    "valor": ct, "vencimento": v_20, "categoria": "4.01"})
    cv = soma({cod("CONSIGNADO_CONV")})
    if cv > 0:
        out.append({"chave": f"{k}-CONV", "descricao": f"Consignado — repasse aos bancos conveniados {comp}",
                    "valor": cv, "vencimento": v_sal, "categoria": "4.01"})
    return out


def _gerar_financeiro(conn, cid: int, run_id: int, por_funcionario: bool = False) -> Dict[str, Any]:
    run = conn.execute("SELECT * FROM payroll_runs WHERE id=? AND company_id=?", (run_id, cid)).fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    run = dict(run)
    if (run.get("status") or "") == "cancelado":
        raise HTTPException(status_code=400, detail="Folha cancelada.")
    existentes = {r["document_number"] for r in _rows(conn,
                  "SELECT document_number FROM financial_entries WHERE company_id=? AND origin_type='folha_dp' AND origin_id=?",
                  (cid, run_id))}
    cc = conn.execute("SELECT id FROM cost_centers WHERE active=1 ORDER BY id LIMIT 1").fetchone()
    ba = conn.execute("SELECT id FROM bank_accounts WHERE active=1 AND company_id=? ORDER BY id LIMIT 1", (cid,)).fetchone()
    criados, ja = [], 0
    comp_data = f"{run['competence']}-01"
    for t in _titulos_da_folha(conn, cid, run, por_funcionario):
        if t["chave"] in existentes:
            ja += 1
            continue
        cur = conn.execute("""INSERT INTO financial_entries (company_id, type, description, category_id, cost_center_id,
                                  bank_account_id, payment_method, competence_date, due_date, amount, paid_amount, status,
                                  installment_number, installment_total, group_uid, recurrence, document_number,
                                  origin_type, origin_id, notes)
                              VALUES (?, 'despesa', ?, ?, ?, ?, 'Transferência/TED', ?, ?, ?, 0, 'pendente', 1, 1, ?, 'unico', ?,
                                      'folha_dp', ?, 'Gerado pelo Departamento Pessoal')""",
                           (cid, t["descricao"], _categoria(conn, t["categoria"]), cc["id"] if cc else None,
                            ba["id"] if ba else None, comp_data, t["vencimento"], t["valor"], f"DP-{run_id}", t["chave"], run_id))
        criados.append({**t, "id": cur.lastrowid})
    return {"criados": criados, "ja_existiam": ja}


@router.get("/financeiro/{run_id}")
def financeiro_da_folha(run_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    """Títulos que a folha gera e a situação de cada um no contas a pagar."""
    conn = get_conn()
    try:
        run = conn.execute("SELECT * FROM payroll_runs WHERE id=? AND company_id=?", (run_id, _cid(u))).fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Folha não encontrada.")
        lanc = {r["document_number"]: r for r in _rows(conn, """SELECT id, document_number, status, amount, paid_amount, due_date
                FROM financial_entries WHERE company_id=? AND origin_type='folha_dp' AND origin_id=?""", (_cid(u), run_id))}
        previstos = _titulos_da_folha(conn, _cid(u), dict(run), por_funcionario=any("-LIQ-" in k for k in lanc))
        for t in previstos:
            e = lanc.pop(t["chave"], None)
            t.update(lancamento_id=e["id"] if e else None, status=e["status"] if e else "nao_lancado",
                     vencimento=e["due_date"] if e else t["vencimento"])
        return {"run": dict(run), "titulos": previstos}
    finally:
        conn.close()


@router.post("/financeiro/{run_id}/gerar", status_code=201)
def financeiro_gerar(run_id: int, data: Dict[str, Any] = Body(default={}), u: Dict[str, Any] = Depends(get_current_user)):
    _pode(u)
    conn = get_conn()
    try:
        out = _gerar_financeiro(conn, _cid(u), run_id, bool((data or {}).get("por_funcionario")))
        _audit(conn, u, "create", "financial_entries", run_id, {"folha": run_id, "titulos": len(out["criados"])})
        conn.commit()
        return out
    finally:
        conn.close()


@router.post("/financeiro/{run_id}/baixar")
def financeiro_baixar(run_id: int, data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    """Baixa (pagamento) em lote dos títulos da folha, pela rotina do financeiro."""
    _pode(u)
    if not data.get("bank_account_id"):
        raise HTTPException(status_code=422, detail="Informe a conta bancária do pagamento.")
    pagto = _data(data.get("payment_date") or date.today().isoformat(), "Data do pagamento")
    conn = get_conn()
    try:
        ids = [r["id"] for r in _rows(conn, """SELECT id FROM financial_entries WHERE company_id=? AND origin_type='folha_dp'
                 AND origin_id=? AND status != 'pago'""", (_cid(u), run_id))]
        if data.get("entry_ids"):
            pedidos = {int(i) for i in data["entry_ids"]}
            ids = [i for i in ids if i in pedidos]
        if not conn.execute("SELECT 1 FROM bank_accounts WHERE id=? AND company_id=?", (data["bank_account_id"], _cid(u))).fetchone():
            raise HTTPException(status_code=404, detail="Conta bancária não encontrada.")
    finally:
        conn.close()
    if not ids:
        raise HTTPException(status_code=400, detail="Nenhum título pendente desta folha. Lance a folha no financeiro primeiro.")
    return _fin.batch_pay_entries(BatchPayRequest(entry_ids=ids, bank_account_id=int(data["bank_account_id"]),
                                                  payment_date=pagto, payment_method=data.get("payment_method") or "Transferência/TED"), u)


# ══ 2. Alteração em grupo ════════════════════════════════════════════════════
CAMPOS_GRUPO = {
    "salario": "Salário",
    "role": "Cargo",
    "cbo": "CBO",
    "department": "Departamento",
    "centro_custo": "Centro de custo",
    "work_schedule_id": "Escala / horário",
    "cct_id": "Convenção coletiva",
    "horas_semana": "Horas semanais",
}
_PEDE_S2206 = {"salario", "role", "cbo", "work_schedule_id", "horas_semana"}


def _novo_valor(emp: Dict[str, Any], d: Dict[str, Any]) -> Any:
    campo = d["campo"]
    if campo == "salario":
        atual = float(emp.get("salary") or 0)
        modo = d.get("modo") or "percentual"
        try:
            v = float(str(d.get("valor")).replace(",", "."))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Valor do reajuste: informe um número.")
        if modo == "percentual":
            novo = atual * (1 + v / 100)
        elif modo == "acrescimo":
            novo = atual + v
        elif modo == "novo":
            novo = v
        else:
            raise HTTPException(status_code=422, detail="Modo do reajuste: percentual, acrescimo ou novo.")
        novo = round(novo, 2)
        if d.get("somente_abaixo") and atual >= novo:
            return atual                         # piso: só quem ganha menos sobe
        return novo
    if campo == "horas_semana":
        try:
            h = float(d.get("valor"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Horas semanais: informe um número.")
        if not 1 <= h <= 44:
            raise HTTPException(status_code=422, detail="Horas semanais entre 1 e 44 (CF art. 7º, XIII).")
        return h
    if campo in ("work_schedule_id", "cct_id"):
        return int(d["valor"]) if str(d.get("valor") or "").strip() else None
    return str(d.get("valor") or "").strip()


def _plano_grupo(conn, cid: int, d: Dict[str, Any]) -> Dict[str, Any]:
    campo = d.get("campo")
    if campo not in CAMPOS_GRUPO:
        raise HTTPException(status_code=422, detail=f"Campo inválido. Use: {', '.join(CAMPOS_GRUPO)}.")
    ids = [int(i) for i in d.get("employee_ids") or []]
    if not ids:
        raise HTTPException(status_code=422, detail="Selecione ao menos um funcionário.")
    if campo == "work_schedule_id" and d.get("valor") and not conn.execute(
            "SELECT 1 FROM work_schedules WHERE id=? AND company_id=?", (d["valor"], cid)).fetchone():
        raise HTTPException(status_code=404, detail="Escala não encontrada.")
    if campo == "cct_id" and d.get("valor") and not conn.execute(
            "SELECT 1 FROM cct_convencoes WHERE id=? AND company_id=?", (d["valor"], cid)).fetchone():
        raise HTTPException(status_code=404, detail="Convenção não encontrada.")
    coluna = "salary" if campo == "salario" else campo
    linhas, avisos = [], []
    sm = pe.load_tables(conn, cid, date.today().strftime("%Y-%m")).salario_minimo if campo == "salario" else 0
    for e in _rows(conn, f"SELECT * FROM employees WHERE company_id=? AND id IN ({','.join('?' * len(ids))}) ORDER BY name",
                   (cid, *ids)):
        antes, depois = e.get(coluna), _novo_valor(e, d)
        if campo == "salario" and depois <= 0:
            raise HTTPException(status_code=422, detail=f"{e['name']}: o novo salário ficaria zerado ou negativo.")
        if campo == "salario" and 0 < depois < sm and float(e.get("horas_semana") or 44) >= 44 and not e.get("is_prolabore"):
            avisos.append(f"{e['name']}: novo salário abaixo do mínimo nacional (R$ {sm:.2f}).")
        linhas.append({"employee_id": e["id"], "nome": e["name"], "antes": antes, "depois": depois,
                       "muda": (antes if antes not in ("", None) else None) != (depois if depois not in ("", None) else None)})
    if len(linhas) != len(set(ids)):
        raise HTTPException(status_code=404, detail="Algum funcionário selecionado não pertence a esta empresa.")
    if campo in _PEDE_S2206:
        avisos.append("Alteração contratual: gere o S-2206 dos funcionários alterados na Central do eSocial.")
    return {"campo": campo, "rotulo": CAMPOS_GRUPO[campo], "linhas": linhas, "avisos": avisos,
            "alterados": sum(1 for l in linhas if l["muda"])}


@router.get("/alteracao-grupo/campos")
def campos_grupo(u: Dict[str, Any] = Depends(get_current_user)):
    return CAMPOS_GRUPO


@router.post("/alteracao-grupo/previa")
def alteracao_previa(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        return _plano_grupo(conn, _cid(u), data)
    finally:
        conn.close()


@router.post("/alteracao-grupo/aplicar")
def alteracao_aplicar(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    _pode(u)
    conn = get_conn()
    try:
        plano = _plano_grupo(conn, _cid(u), data)
        campo = plano["campo"]
        vigencia = _data(data.get("data_vigencia") or date.today().isoformat(), "Data de vigência") if campo == "salario" else ""
        for l in plano["linhas"]:
            if not l["muda"]:
                continue
            if campo == "salario":
                ant = float(l["antes"] or 0)
                pct = round((l["depois"] - ant) / ant * 100, 2) if ant else 0
                emp = conn.execute("SELECT role FROM employees WHERE id=?", (l["employee_id"],)).fetchone()
                conn.execute("""INSERT INTO salary_history (company_id, employee_id, data_vigencia, salario_anterior, salario_novo,
                                tipo, percentual, motivo, cargo_anterior, cargo_novo, aprovado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                             (_cid(u), l["employee_id"], vigencia, ant, l["depois"], data.get("tipo") or "reajuste", pct,
                              str(data.get("motivo") or "Alteração em grupo")[:200], emp["role"] or "", "", u.get("email") or ""))
                conn.execute("UPDATE employees SET salary=? WHERE id=? AND company_id=?", (l["depois"], l["employee_id"], _cid(u)))
            else:
                conn.execute(f"UPDATE employees SET {campo}=? WHERE id=? AND company_id=?", (l["depois"], l["employee_id"], _cid(u)))
        _audit(conn, u, "update", "employees_grupo", None,
               {"campo": campo, "alterados": [l["employee_id"] for l in plano["linhas"] if l["muda"]],
                "valor": data.get("valor"), "modo": data.get("modo")})
        conn.commit()
        return plano
    finally:
        conn.close()


# ══ 3. Exclusão em grupo ═════════════════════════════════════════════════════
TIPOS_EXCLUSAO = {"ferias": "Férias", "decimo_1": "13º — 1ª parcela", "decimo_2": "13º — 2ª parcela",
                  "rescisao": "Rescisões", "rpa": "RPA (autônomos)"}


@router.get("/exclusao-grupo")
def exclusao_listar(tipo: str, inicio: str, fim: str, u: Dict[str, Any] = Depends(get_current_user)):
    """Cálculos gravados do tipo, com data (início do gozo, desligamento, pagamento) no período."""
    if tipo not in TIPOS_EXCLUSAO:
        raise HTTPException(status_code=422, detail=f"Tipo inválido. Use: {', '.join(TIPOS_EXCLUSAO)}.")
    ini, fi = _data(inicio, "Data inicial"), _data(fim, "Data final")
    conn = get_conn()
    try:
        if tipo == "rpa":
            return _rows(conn, """SELECT r.id, a.nome AS nome, r.competencia, r.data_pagamento AS data, r.valor_liquido AS liquido
                                  FROM rpa_payments r JOIN autonomous_workers a ON a.id=r.autonomous_id
                                  WHERE r.company_id=? AND r.data_pagamento BETWEEN ? AND ? ORDER BY r.data_pagamento, a.nome""",
                         (_cid(u), ini, fi))
        campo_data = "COALESCE(NULLIF(ps.data_pagamento,''), ps.data_inicio)" if tipo.startswith("decimo") else "ps.data_inicio"
        return _rows(conn, f"""SELECT ps.id, e.name AS nome, ps.competencia, {campo_data} AS data, ps.liquido
                               FROM payroll_special ps JOIN employees e ON e.id=ps.employee_id
                               WHERE ps.company_id=? AND ps.tipo=? AND ps.status != 'cancelado'
                                 AND substr({campo_data},1,10) BETWEEN ? AND ? ORDER BY data, e.name""",
                     (_cid(u), tipo, ini, fi))
    finally:
        conn.close()


@router.post("/exclusao-grupo")
def exclusao_executar(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    """Exclui cada cálculo pela mesma rotina da exclusão individual (reativa quem a rescisão desligou).
    Não exclui de competência fechada nem rescisão com S-2299 aceito no eSocial."""
    _pode(u)
    tipo = data.get("tipo")
    if tipo not in TIPOS_EXCLUSAO:
        raise HTTPException(status_code=422, detail=f"Tipo inválido. Use: {', '.join(TIPOS_EXCLUSAO)}.")
    ids = [int(i) for i in data.get("ids") or []]
    if not ids:
        raise HTTPException(status_code=422, detail="Selecione os cálculos a excluir.")
    resultado = []
    for i in ids:
        conn = get_conn()
        try:
            if tipo == "rpa":
                r = conn.execute("SELECT competencia FROM rpa_payments WHERE id=? AND company_id=?", (i, _cid(u))).fetchone()
                comp = r["competencia"] if r else ""
            else:
                r = conn.execute("SELECT tipo, competencia, data_inicio FROM payroll_special WHERE id=? AND company_id=?",
                                 (i, _cid(u))).fetchone()
                if r and r["tipo"] != tipo:
                    r = None
                comp = (r["competencia"] or r["data_inicio"] or "")[:7] if r else ""
            erro = ""
            if not r:
                erro = "Registro não encontrado."
            elif _competencia_fechada(conn, _cid(u), comp):
                erro = f"Competência {comp} fechada."
            elif tipo == "rescisao" and conn.execute(
                    """SELECT COUNT(*) FROM esocial_eventos WHERE company_id=? AND tipo='S-2299' AND referencia_tipo='rescisao'
                       AND referencia_id=? AND status='aceito'""", (_cid(u), i)).fetchone()[0]:
                erro = "S-2299 já aceito no eSocial: envie a exclusão (S-3000) antes."
        finally:
            conn.close()
        if not erro:
            try:
                if tipo == "rpa":
                    _dp.delete_rpa(i, u)
                    resultado.append({"id": i, "ok": True})
                else:
                    out = _dp.especial_delete(i, u)
                    resultado.append({"id": i, "ok": True, "reativado": bool(out.get("funcionario_reativado"))})
                continue
            except HTTPException as e:
                erro = e.detail
        resultado.append({"id": i, "ok": False, "erro": erro})
    conn = get_conn()
    try:
        _audit(conn, u, "delete", f"exclusao_grupo_{tipo}", None, {"ids": [r["id"] for r in resultado if r["ok"]]})
        conn.commit()
    finally:
        conn.close()
    return {"excluidos": sum(1 for r in resultado if r["ok"]), "resultado": resultado}


# ══ 4. Acerto da data de pagamento ═══════════════════════════════════════════
@router.get("/data-pagamento")
def data_pagamento_listar(competencia: str, u: Dict[str, Any] = Depends(get_current_user)):
    """Folhas, recibos especiais e RPA da competência com a data de pagamento atual."""
    comp = _comp(competencia)
    conn = get_conn()
    try:
        folhas = _rows(conn, """SELECT 'folha' AS tipo, id, competence AS competencia, COALESCE(tipo,'mensal') AS descricao,
                                       employee_count AS qtd, data_pagamento FROM payroll_runs
                                WHERE company_id=? AND competence=? AND status != 'cancelado' ORDER BY id""", (_cid(u), comp))
        esp = _rows(conn, """SELECT 'especial' AS tipo, ps.id, ps.competencia, ps.tipo || ' — ' || e.name AS descricao, 1 AS qtd,
                                    ps.data_pagamento FROM payroll_special ps JOIN employees e ON e.id=ps.employee_id
                             WHERE ps.company_id=? AND ps.status != 'cancelado'
                               AND (ps.competencia=? OR substr(ps.data_inicio,1,7)=? OR substr(ps.data_pagamento,1,7)=?)
                             ORDER BY ps.tipo, e.name""", (_cid(u), comp, comp, comp))
        rpa = _rows(conn, """SELECT 'rpa' AS tipo, r.id, r.competencia, 'RPA — ' || a.nome AS descricao, 1 AS qtd, r.data_pagamento
                             FROM rpa_payments r JOIN autonomous_workers a ON a.id=r.autonomous_id
                             WHERE r.company_id=? AND r.competencia=? ORDER BY a.nome""", (_cid(u), comp))
        return folhas + esp + rpa
    finally:
        conn.close()


_TABELA_PG = {"folha": "payroll_runs", "especial": "payroll_special", "rpa": "rpa_payments"}


def _s1210_aceitos(conn, cid: int, tipo: str, reg_id: int, per_pg: str) -> int:
    """S-1210 aceitos no mês do pagamento antigo para as pessoas do registro."""
    if not per_pg:
        return 0
    if tipo == "folha":
        refs = [("pagamento", r["employee_id"]) for r in _rows(conn, "SELECT employee_id FROM payroll_items WHERE run_id=?", (reg_id,))]
    elif tipo == "especial":
        r = conn.execute("SELECT employee_id FROM payroll_special WHERE id=?", (reg_id,)).fetchone()
        refs = [("pagamento", r["employee_id"])] if r else []
    else:
        r = conn.execute("SELECT autonomous_id FROM rpa_payments WHERE id=?", (reg_id,)).fetchone()
        refs = [("pagamento_rpa", r["autonomous_id"])] if r else []
    return sum(conn.execute("""SELECT COUNT(*) FROM esocial_eventos WHERE company_id=? AND tipo='S-1210' AND referencia_tipo=?
                               AND referencia_id=? AND per_apur=? AND status='aceito'""", (cid, rt_, rid, per_pg)).fetchone()[0]
               for rt_, rid in refs)


@router.post("/data-pagamento")
def data_pagamento_acertar(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    """Troca a data de pagamento. Se o mês muda e já há S-1210 aceito no mês antigo, só segue com
    confirmar=true (o S-1210 antigo precisa ser excluído/retificado na Central do eSocial)."""
    _pode(u)
    nova = _data(data.get("nova_data"), "Nova data de pagamento")
    itens = data.get("itens") or []
    if not itens:
        raise HTTPException(status_code=422, detail="Selecione o que terá a data alterada.")
    conn = get_conn()
    try:
        plano, avisos = [], []
        for it in itens:
            tipo, rid = it.get("tipo"), int(it.get("id") or 0)
            if tipo not in _TABELA_PG:
                raise HTTPException(status_code=422, detail="Tipo deve ser folha, especial ou rpa.")
            reg = conn.execute(f"SELECT * FROM {_TABELA_PG[tipo]} WHERE id=? AND company_id=?", (rid, _cid(u))).fetchone()
            if not reg:
                raise HTTPException(status_code=404, detail=f"{tipo} {rid} não encontrado.")
            reg = dict(reg)
            antiga = (reg.get("data_pagamento") or "")[:10]
            comp = (reg.get("competence") or reg.get("competencia") or "")[:7]
            if _competencia_fechada(conn, _cid(u), comp):
                raise HTTPException(status_code=400, detail=f"Competência {comp} fechada: reabra-a para alterar a data.")
            if antiga and not rt.mesmo_mes(antiga, nova):
                n = _s1210_aceitos(conn, _cid(u), tipo, rid, antiga[:7])
                if n:
                    avisos.append(f"{tipo} {rid}: {n} S-1210 já aceito(s) em {antiga[5:7]}/{antiga[:4]} precisam ser excluídos "
                                  f"(S-3000) e o pagamento informado em {nova[5:7]}/{nova[:4]}.")
            plano.append((tipo, rid, antiga))
        if avisos and not data.get("confirmar"):
            raise HTTPException(status_code=409, detail={"mensagem": "Há pagamentos já informados ao eSocial.", "avisos": avisos})
        for tipo, rid, _ in plano:
            conn.execute(f"UPDATE {_TABELA_PG[tipo]} SET data_pagamento=? WHERE id=? AND company_id=?", (nova, rid, _cid(u)))
        conn.execute("""UPDATE financial_entries SET due_date=? WHERE company_id=? AND origin_type='folha_dp' AND status='pendente'
                        AND origin_id IN ({}) AND (document_number LIKE '%-LIQ%' OR document_number LIKE '%-PENS-%')""".format(
                        ",".join(str(r) for t, r, _ in plano if t == "folha") or "0"), (nova, _cid(u)))
        mudou_mes = any(a and not rt.mesmo_mes(a, nova) for _, _, a in plano)
        if mudou_mes:
            avisos.append("O mês do pagamento mudou: o IRRF passa a ser apurado no novo mês (regime de caixa) "
                          "e o S-1210 vai para o período do pagamento.")
        _audit(conn, u, "update", "data_pagamento", None, {"nova": nova, "itens": [(t, r) for t, r, _ in plano]})
        conn.commit()
        return {"alterados": len(plano), "nova_data": nova, "avisos": avisos}
    finally:
        conn.close()


# ══ 5. Rotinas automáticas ═══════════════════════════════════════════════════
_SISTEMA = "rotina automática"


def _usuario_rotina(cid: int) -> Dict[str, Any]:
    return {"company_id": cid, "role": "admin", "id": None, "email": _SISTEMA}


def _run_mensal(conn, cid: int, comp: str) -> Optional[Dict[str, Any]]:
    r = conn.execute("""SELECT * FROM payroll_runs WHERE company_id=? AND competence=? AND status != 'cancelado'
                        AND COALESCE(tipo,'mensal')='mensal' ORDER BY id DESC LIMIT 1""", (cid, comp)).fetchone()
    return dict(r) if r else None


def executar_rotina(rotina: Dict[str, Any], quando: datetime, origem: str = "agendada") -> Dict[str, Any]:
    """Executa uma rotina e registra o resultado. Nunca levanta exceção: o erro vira status 'erro'."""
    cid, tipo = int(rotina["company_id"]), rotina["tipo"]
    comp = rt.competencia_alvo(quando.date(), rotina.get("competencia") or "atual")
    u = _usuario_rotina(cid)
    inicio = datetime.now().isoformat(timespec="seconds")
    status, msg = "ok", ""
    try:
        conn = get_conn()
        try:
            run = _run_mensal(conn, cid, comp)
            fechada = _competencia_fechada(conn, cid, comp)
        finally:
            conn.close()
        if tipo == "calcular_folha":
            if run:
                status, msg = "ignorada", f"A folha de {comp} já está calculada (id {run['id']})."
            elif fechada:
                status, msg = "ignorada", f"Competência {comp} fechada."
            else:
                out = _dp.process_payroll(PayrollRunCreate(competence=comp), u)
                msg = f"Folha de {comp} calculada: {out['run']['employee_count']} funcionário(s), líquido R$ {out['run']['total_net']:.2f}."
        elif not run:
            status, msg = "ignorada", f"Não há folha mensal calculada em {comp}."
        elif tipo == "enviar_holerites":
            out = _dp.holerites_enviar(run["id"], {"somente_pendentes": True}, u)
            msg = f"Holerites de {comp}: {out.get('enviados', 0)} enviado(s), {out.get('falhas', 0)} falha(s)."
        elif tipo == "gerar_financeiro":
            conn = get_conn()
            try:
                out = _gerar_financeiro(conn, cid, run["id"])
                conn.commit()
            finally:
                conn.close()
            msg = f"Folha de {comp}: {len(out['criados'])} título(s) lançados no contas a pagar ({out['ja_existiam']} já existiam)."
    except HTTPException as e:
        status, msg = ("ignorada" if e.status_code == 400 and "Nenhum holerite" in str(e.detail) else "erro"), str(e.detail)
    except Exception as e:                       # rotina em segundo plano: registra e segue
        status, msg = "erro", f"{type(e).__name__}: {str(e)[:300]}"
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO dp_rotinas_execucoes (company_id, rotina_id, tipo, competencia, inicio, fim, status, mensagem, origem)
                        VALUES (?,?,?,?,?,?,?,?,?)""", (cid, rotina["id"], tipo, comp, inicio,
                                                        datetime.now().isoformat(timespec="seconds"), status, msg[:500], origem))
        conn.execute("UPDATE dp_rotinas SET ultima_execucao=?, ultimo_status=?, ultima_mensagem=? WHERE id=?",
                     (inicio, status, msg[:500], rotina["id"]))
        conn.commit()
    finally:
        conn.close()
    return {"status": status, "mensagem": msg, "competencia": comp}


def executar_pendentes(agora: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Roda as rotinas vencidas. A troca de `proxima_execucao` é condicional (só um processo ganha),
    então rodar em mais de um servidor ou worker não duplica a execução."""
    agora = agora or datetime.now()
    conn = get_conn()
    try:
        vencidas = _rows(conn, """SELECT * FROM dp_rotinas WHERE ativo=1 AND proxima_execucao != ''
                                  AND proxima_execucao <= ? ORDER BY proxima_execucao""", (agora.isoformat(timespec="minutes"),))
        minhas = []
        for r in vencidas:
            prox = rt.proxima_execucao(r["dia"], r["hora"], agora).isoformat(timespec="minutes")
            if conn.execute("UPDATE dp_rotinas SET proxima_execucao=? WHERE id=? AND proxima_execucao=?",
                            (prox, r["id"], r["proxima_execucao"])).rowcount:
                minhas.append(r)
        conn.commit()
    finally:
        conn.close()
    return [{"rotina_id": r["id"], **executar_rotina(r, agora)} for r in minhas]


def _agora_local() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(os.getenv("CORTEX_TZ", "America/Cuiaba"))).replace(tzinfo=None)
    except Exception:
        return datetime.now()


_thread: Optional[threading.Thread] = None


def iniciar_agendador(intervalo: int = 300) -> None:
    """Laço em segundo plano (servidor do escritório e Render pago). Desliga com CORTEX_ROTINAS=0."""
    global _thread
    if os.getenv("CORTEX_ROTINAS", "1") == "0" or (_thread and _thread.is_alive()):
        return

    def laco():
        while True:
            try:
                executar_pendentes(_agora_local())
            except Exception:
                pass
            time.sleep(intervalo)

    _thread = threading.Thread(target=laco, name="cortex-rotinas-dp", daemon=True)
    _thread.start()


@router.get("/rotinas")
def rotinas_listar(u: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    try:
        rot = _rows(conn, "SELECT * FROM dp_rotinas WHERE company_id=? ORDER BY dia, hora, id", (_cid(u),))
        for r in rot:
            r["tipo_nome"] = rt.TIPOS.get(r["tipo"], r["tipo"])
        hist = _rows(conn, "SELECT * FROM dp_rotinas_execucoes WHERE company_id=? ORDER BY id DESC LIMIT 30", (_cid(u),))
        return {"rotinas": rot, "execucoes": hist, "tipos": rt.TIPOS, "competencias": rt.COMPETENCIAS}
    finally:
        conn.close()


def _salvar_rotina(conn, u, d: Dict[str, Any], rot_id: Optional[int] = None) -> Dict[str, Any]:
    try:
        v = rt.validar_rotina(d)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    v["proxima_execucao"] = rt.proxima_execucao(v["dia"], v["hora"], _agora_local()).isoformat(timespec="minutes") if v["ativo"] else ""
    if rot_id:
        if not conn.execute("UPDATE dp_rotinas SET tipo=?, dia=?, hora=?, competencia=?, ativo=?, proxima_execucao=? "
                            "WHERE id=? AND company_id=?", (*v.values(), rot_id, _cid(u))).rowcount:
            raise HTTPException(status_code=404, detail="Rotina não encontrada.")
    else:
        rot_id = conn.execute("""INSERT INTO dp_rotinas (company_id, tipo, dia, hora, competencia, ativo, proxima_execucao, criado_por)
                                 VALUES (?,?,?,?,?,?,?,?)""", (_cid(u), *v.values(), u.get("email") or "")).lastrowid
    _audit(conn, u, "update", "dp_rotinas", rot_id, v)
    conn.commit()
    return {**v, "id": rot_id}


@router.post("/rotinas", status_code=201)
def rotina_criar(data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    _pode(u)
    conn = get_conn()
    try:
        return _salvar_rotina(conn, u, data)
    finally:
        conn.close()


@router.put("/rotinas/{rot_id}")
def rotina_editar(rot_id: int, data: Dict[str, Any] = Body(...), u: Dict[str, Any] = Depends(get_current_user)):
    _pode(u)
    conn = get_conn()
    try:
        return _salvar_rotina(conn, u, data, rot_id)
    finally:
        conn.close()


@router.delete("/rotinas/{rot_id}")
def rotina_excluir(rot_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    _pode(u)
    conn = get_conn()
    try:
        if not conn.execute("DELETE FROM dp_rotinas WHERE id=? AND company_id=?", (rot_id, _cid(u))).rowcount:
            raise HTTPException(status_code=404, detail="Rotina não encontrada.")
        _audit(conn, u, "delete", "dp_rotinas", rot_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/rotinas/{rot_id}/executar")
def rotina_executar_agora(rot_id: int, u: Dict[str, Any] = Depends(get_current_user)):
    _pode(u)
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM dp_rotinas WHERE id=? AND company_id=?", (rot_id, _cid(u))).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Rotina não encontrada.")
    finally:
        conn.close()
    return executar_rotina(dict(r), _agora_local(), origem=f"manual ({u.get('email') or ''})")


@router.post("/rotinas/executar-pendentes")
def rotinas_cron(x_cron_token: str = Header(default="")):
    """Para um agendador externo (cron do Render, GitHub Actions) quando o servidor dorme sem uso.
    Exige o cabeçalho X-Cron-Token igual à variável CORTEX_CRON_TOKEN."""
    esperado = os.getenv("CORTEX_CRON_TOKEN", "")
    if not esperado or x_cron_token != esperado:
        raise HTTPException(status_code=403, detail="Token inválido.")
    return {"executadas": executar_pendentes(_agora_local())}
