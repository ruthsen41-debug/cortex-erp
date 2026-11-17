from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

try:
    from ..database import _seed_default_accumulators, get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
    from ..services.fiscal_book_engine import (
        _insert_fiscal_entry,
        apurar_impostos_mes,
        gerar_guia_html,
        sync_erp_to_fiscal_books,
    )
except ImportError:
    from database import _seed_default_accumulators, get_conn
    from auth import get_current_user
    from utils import rows_to_dicts
    from services.fiscal_book_engine import (
        _insert_fiscal_entry,
        apurar_impostos_mes,
        gerar_guia_html,
        sync_erp_to_fiscal_books,
    )

router = APIRouter(prefix="/api/fiscal-books", tags=["Escrita Fiscal"])


def _ensure_accumulators(conn, company_id: int) -> None:
    cnt = conn.execute(
        "SELECT COUNT(*) FROM fiscal_accumulators WHERE company_id = ?", (company_id,)
    ).fetchone()[0]
    if cnt == 0:
        _seed_default_accumulators(conn.cursor(), company_id)
        conn.commit()


# ─── ACUMULADORES FISCAIS ─────────────────────────────────────────────────────

@router.get("/accumulators")
def list_accumulators(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _ensure_accumulators(conn, company_id)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM fiscal_accumulators WHERE company_id = ? ORDER BY codigo",
        (company_id,),
    ).fetchall())
    conn.close()
    return rows


@router.post("/accumulators", status_code=201)
def create_accumulator(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    codigo = str(data.get("codigo") or "").strip()
    descricao = str(data.get("descricao") or "").strip()
    tipo = str(data.get("tipo") or "saida").strip()
    if not codigo or not descricao:
        conn.close()
        raise HTTPException(status_code=422, detail="Código e descrição são obrigatórios.")
    existing = conn.execute(
        "SELECT id FROM fiscal_accumulators WHERE company_id = ? AND codigo = ?",
        (company_id, codigo),
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Acumulador {codigo} já existe.")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fiscal_accumulators (
            company_id, codigo, descricao, tipo, cfop_padrao, cst_icms, aliquota_icms,
            reduz_base_icms_pct, tem_icms_st, mva_pct, aliquota_ipi, cst_pis_cofins,
            aliquota_pis, aliquota_cofins, gera_credito_icms, gera_credito_pis_cofins,
            aliquota_iss, retencao_irrf_pct, retencao_csrf_pct, retencao_inss_pct,
            retencao_iss, aliquota_ibs_teste, aliquota_cbs_teste,
            conta_contabil_debito, conta_contabil_credito, gera_financeiro, ativo
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
    """, (
        company_id, codigo, descricao, tipo,
        str(data.get("cfop_padrao") or "5102"), str(data.get("cst_icms") or "00"),
        float(data.get("aliquota_icms") or 0.0), float(data.get("reduz_base_icms_pct") or 0.0),
        int(bool(data.get("tem_icms_st"))), float(data.get("mva_pct") or 0.0),
        float(data.get("aliquota_ipi") or 0.0), str(data.get("cst_pis_cofins") or "01"),
        float(data.get("aliquota_pis") or 0.0), float(data.get("aliquota_cofins") or 0.0),
        int(bool(data.get("gera_credito_icms"))), int(bool(data.get("gera_credito_pis_cofins"))),
        float(data.get("aliquota_iss") or 0.0), float(data.get("retencao_irrf_pct") or 0.0),
        float(data.get("retencao_csrf_pct") or 0.0), float(data.get("retencao_inss_pct") or 0.0),
        int(bool(data.get("retencao_iss"))),
        float(data.get("aliquota_ibs_teste") if data.get("aliquota_ibs_teste") is not None else 0.1),
        float(data.get("aliquota_cbs_teste") if data.get("aliquota_cbs_teste") is not None else 0.9),
        str(data.get("conta_contabil_debito") or "1.1.04"),
        str(data.get("conta_contabil_credito") or "3.1.01"),
        int(bool(data.get("gera_financeiro", 1))),
    ))
    new_id = cur.lastrowid
    conn.commit()
    row = dict(conn.execute("SELECT * FROM fiscal_accumulators WHERE id = ?", (new_id,)).fetchone())
    conn.close()
    return row


@router.put("/accumulators/{acc_id}")
def update_accumulator(acc_id: int, data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    acc = conn.execute(
        "SELECT * FROM fiscal_accumulators WHERE id = ? AND company_id = ?", (acc_id, company_id)
    ).fetchone()
    if not acc:
        conn.close()
        raise HTTPException(status_code=404, detail="Acumulador não encontrado.")
    allowed = [
        "descricao", "tipo", "cfop_padrao", "cst_icms", "aliquota_icms", "reduz_base_icms_pct",
        "tem_icms_st", "mva_pct", "aliquota_ipi", "cst_pis_cofins", "aliquota_pis", "aliquota_cofins",
        "gera_credito_icms", "gera_credito_pis_cofins", "aliquota_iss", "retencao_irrf_pct",
        "retencao_csrf_pct", "retencao_inss_pct", "retencao_iss", "aliquota_ibs_teste",
        "aliquota_cbs_teste", "conta_contabil_debito", "conta_contabil_credito", "gera_financeiro", "ativo",
    ]
    sets = [f"{k} = ?" for k in allowed if k in data]
    vals = [data[k] for k in allowed if k in data]
    if sets:
        vals += [acc_id, company_id]
        conn.execute(f"UPDATE fiscal_accumulators SET {', '.join(sets)} WHERE id = ? AND company_id = ?", vals)
        conn.commit()
    row = dict(conn.execute("SELECT * FROM fiscal_accumulators WHERE id = ?", (acc_id,)).fetchone())
    conn.close()
    return row


@router.delete("/accumulators/{acc_id}")
def delete_accumulator(acc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM fiscal_accumulators WHERE id = ? AND company_id = ?", (acc_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── ESCRITURAÇÃO & LIVROS FISCAIS ────────────────────────────────────────────

@router.get("/entries")
def list_entries(
    competencia: Optional[str] = None,
    tipo: Optional[str] = None,
    cfop: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT * FROM fiscal_entries WHERE company_id = ?"
    params: List[Any] = [company_id]
    if competencia:
        q += " AND competencia = ?"
        params.append(competencia)
    if tipo:
        q += " AND tipo = ?"
        params.append(tipo)
    if cfop:
        q += " AND cfop = ?"
        params.append(cfop)
    q += " ORDER BY data_escrituracao DESC, id DESC"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return rows


@router.post("/entries", status_code=201)
def create_entry(data: Dict[str, Any] = Body(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _ensure_accumulators(conn, company_id)
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    acc = None
    if data.get("accumulator_id"):
        row = conn.execute(
            "SELECT * FROM fiscal_accumulators WHERE id = ? AND company_id = ?",
            (data["accumulator_id"], company_id),
        ).fetchone()
        acc = dict(row) if row else None
    elif data.get("accumulator_code"):
        row = conn.execute(
            "SELECT * FROM fiscal_accumulators WHERE codigo = ? AND company_id = ?",
            (str(data["accumulator_code"]), company_id),
        ).fetchone()
        acc = dict(row) if row else None

    if not data.get("numero"):
        conn.close()
        raise HTTPException(status_code=422, detail="Número do documento é obrigatório.")

    entry = _insert_fiscal_entry(conn, company_id, data, acc, company)
    conn.commit()
    conn.close()
    return entry


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute(
        "SELECT * FROM fiscal_entries WHERE id = ? AND company_id = ?", (entry_id, company_id)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Lançamento fiscal não encontrado.")
    row = dict(row)
    if row.get("accounting_entry_id"):
        conn.execute("DELETE FROM accounting_entry_lines WHERE entry_id = ?", (row["accounting_entry_id"],))
        conn.execute("DELETE FROM accounting_entries WHERE id = ? AND company_id = ?", (row["accounting_entry_id"], company_id))
    conn.execute("DELETE FROM fiscal_entries WHERE id = ? AND company_id = ?", (entry_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/sync")
def sync_fiscal_books(
    competencia: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    _ensure_accumulators(conn, company_id)
    comp = competencia or date.today().strftime("%Y-%m")
    res = sync_erp_to_fiscal_books(conn, company_id, comp)
    conn.close()
    return res


def _book_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "entries": rows,
        "count": len(rows),
        "totais": {
            "valor_contabil": round(sum(float(r.get("valor_contabil") or 0) for r in rows), 2),
            "base_icms": round(sum(float(r.get("base_icms") or 0) for r in rows), 2),
            "valor_icms": round(sum(float(r.get("valor_icms") or 0) for r in rows), 2),
            "valor_icms_st": round(sum(float(r.get("valor_icms_st") or 0) for r in rows), 2),
            "valor_ipi": round(sum(float(r.get("valor_ipi") or 0) for r in rows), 2),
            "valor_pis": round(sum(float(r.get("valor_pis") or 0) for r in rows), 2),
            "valor_cofins": round(sum(float(r.get("valor_cofins") or 0) for r in rows), 2),
            "valor_iss": round(sum(float(r.get("valor_iss") or 0) for r in rows), 2),
            "iss_retido": round(sum(float(r.get("iss_retido") or 0) for r in rows), 2),
            "irrf_retido": round(sum(float(r.get("irrf_retido") or 0) for r in rows), 2),
            "csrf_retido": round(sum(float(r.get("csrf_retido") or 0) for r in rows), 2),
            "inss_retido": round(sum(float(r.get("inss_retido") or 0) for r in rows), 2),
        },
    }


@router.get("/books")
def get_fiscal_books(
    competencia: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM fiscal_entries WHERE company_id = ? AND competencia = ? ORDER BY data_escrituracao, id",
        (company_id, comp),
    ).fetchall())
    conn.close()

    entradas = [r for r in rows if r["tipo"] == "entrada"]
    saidas = [r for r in rows if r["tipo"] == "saida"]
    serv_prest = [r for r in rows if r["tipo"] == "servico_prestado"]
    serv_tom = [r for r in rows if r["tipo"] == "servico_tomado"]

    cfop_map: Dict[tuple, Dict[str, Any]] = {}
    for r in rows:
        k = (r.get("cfop") or "", r.get("tipo") or "")
        item = cfop_map.setdefault(k, {
            "cfop": k[0], "tipo": k[1], "qtd": 0,
            "valor_contabil": 0.0, "valor_icms": 0.0, "valor_ipi": 0.0,
            "valor_pis": 0.0, "valor_cofins": 0.0, "valor_iss": 0.0,
        })
        item["qtd"] += 1
        for fld in ("valor_contabil", "valor_icms", "valor_ipi", "valor_pis", "valor_cofins", "valor_iss"):
            item[fld] = round(item[fld] + float(r.get(fld) or 0), 2)

    return {
        "competencia": comp,
        "livro_entradas": _book_summary(entradas),
        "livro_saidas": _book_summary(saidas),
        "livro_servicos_prestados": _book_summary(serv_prest),
        "livro_servicos_tomados": _book_summary(serv_tom),
        "resumo_cfop": sorted(cfop_map.values(), key=lambda x: (x["tipo"], x["cfop"])),
    }


# ─── APURAÇÃO MENSAL & GUIAS ──────────────────────────────────────────────────

@router.get("/apurations")
def list_apurations(
    competencia: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM fiscal_apurations WHERE company_id = ? AND competencia = ? ORDER BY id",
        (company_id, comp),
    ).fetchall())
    conn.close()
    return rows


@router.post("/apurations/run")
def run_apurations(
    competencia: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    rows = apurar_impostos_mes(conn, company_id, comp)
    conn.close()
    return {"competencia": comp, "apurations": rows}


@router.get("/apurations/{apuration_id}/guia", response_class=HTMLResponse)
def get_apuration_guia(apuration_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    ap = conn.execute(
        "SELECT * FROM fiscal_apurations WHERE id = ? AND company_id = ?", (apuration_id, company_id)
    ).fetchone()
    if not ap:
        conn.close()
        raise HTTPException(status_code=404, detail="Apuração não encontrada.")
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone() or {})
    conn.close()
    return HTMLResponse(content=gerar_guia_html(company, dict(ap)))


@router.post("/apurations/{apuration_id}/gerar-financeiro")
def gerar_financeiro_apuracao(apuration_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    ap = conn.execute(
        "SELECT * FROM fiscal_apurations WHERE id = ? AND company_id = ?", (apuration_id, company_id)
    ).fetchone()
    if not ap:
        conn.close()
        raise HTTPException(status_code=404, detail="Apuração não encontrada.")
    ap_d = dict(ap)
    val = float(ap_d.get("valor_a_recolher") or 0.0)
    if val <= 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Apuração sem valor a recolher.")
    if ap_d.get("financial_entry_id"):
        fe = conn.execute("SELECT * FROM financial_entries WHERE id = ?", (ap_d["financial_entry_id"],)).fetchone()
        if fe:
            conn.close()
            return {"ok": True, "financial_entry": dict(fe), "ja_existia": True}

    cur = conn.cursor()
    due = ap_d.get("vencimento") or date.today().isoformat()
    comp_dt = f"{ap_d['competencia']}-01"
    cur.execute("""
        INSERT INTO financial_entries (
            company_id, type, description, competence_date, due_date,
            amount, status, document_number, origin_type, origin_id
        ) VALUES (?, 'despesa', ?, ?, ?, ?, 'pendente', ?, 'apuracao_fiscal', ?)
    """, (
        company_id,
        f"Guia {ap_d['imposto']} ({ap_d['codigo_receita']}) — Comp. {ap_d['competencia']}",
        comp_dt, due, round(val, 2), f"{ap_d['imposto']}-{ap_d['competencia']}", apuration_id,
    ))
    fe_id = cur.lastrowid
    conn.execute(
        "UPDATE fiscal_apurations SET financial_entry_id = ?, status = 'guia_gerada' WHERE id = ?",
        (fe_id, apuration_id),
    )
    conn.commit()
    fe_row = dict(conn.execute("SELECT * FROM financial_entries WHERE id = ?", (fe_id,)).fetchone())
    conn.close()
    return {"ok": True, "financial_entry": fe_row}
