import calendar
import hashlib
import io
import json
import zipfile
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
    from ..services.sped_generator import SpedFiscalGenerator
    from ..services.ecf_generator import EcfGenerator
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts
    from services.sped_generator import SpedFiscalGenerator
    from services.ecf_generator import EcfGenerator

router = APIRouter(tags=["Portal do Contador & SPED"])


# ==========================================
# 1. SPED FISCAL & PACOTE DO CONTADOR (AUTENTICADO)
# ==========================================
@router.get("/api/reports/sped-preview")
def preview_sped_fiscal(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retorna estatísticas do período sem gerar o arquivo EFD."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())

    today = date.today()
    s_date = start_date or date(today.year, today.month, 1).isoformat()
    e_date = end_date or today.isoformat()

    invoices = rows_to_dicts(conn.execute("""
        SELECT total_invoice, total_icms, total_pis, total_cofins, model
        FROM invoices
        WHERE company_id = ? AND status = 'autorizada'
        AND substr(issued_at, 1, 10) BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchall())
    conn.close()

    tot_invoice = sum(float(i.get("total_invoice") or 0) for i in invoices)
    tot_icms    = sum(float(i.get("total_icms")    or 0) for i in invoices)
    tot_pis     = sum(float(i.get("total_pis")     or 0) for i in invoices)
    tot_cofins  = sum(float(i.get("total_cofins")  or 0) for i in invoices)

    return {
        "start_date": s_date,
        "end_date": e_date,
        "company": {
            "razao_social": company.get("razao_social"),
            "cnpj": company.get("cnpj"),
            "uf": company.get("uf"),
            "regime_tributario": company.get("regime_tributario"),
        },
        "count_nfe": len(invoices),
        "total_faturamento": round(tot_invoice, 2),
        "total_icms": round(tot_icms, 2),
        "total_pis": round(tot_pis, 2),
        "total_cofins": round(tot_cofins, 2),
        "total_impostos": round(tot_icms + tot_pis + tot_cofins, 2),
    }


@router.get("/api/reports/sped-fiscal")
def download_sped_fiscal(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Gera e faz o download do arquivo oficial do SPED Fiscal (EFD ICMS/IPI)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())

    today = date.today()
    s_date = start_date or date(today.year, today.month, 1).isoformat()
    e_date = end_date or today.isoformat()

    invoices = rows_to_dicts(conn.execute("""
        SELECT * FROM invoices
        WHERE company_id = ? AND status = 'autorizada'
        AND substr(issued_at, 1, 10) BETWEEN ? AND ?
        ORDER BY number ASC
    """, (company_id, s_date, e_date)).fetchall())
    fiscal_entries = rows_to_dicts(conn.execute("""
        SELECT * FROM fiscal_entries
        WHERE company_id = ? AND data_escrituracao BETWEEN ? AND ? AND status != 'cancelado'
        ORDER BY data_escrituracao, id
    """, (company_id, s_date, e_date)).fetchall())
    ap_row = conn.execute("""
        SELECT * FROM fiscal_apurations WHERE company_id = ? AND competencia = ? AND imposto = 'ICMS' LIMIT 1
    """, (company_id, s_date[:7])).fetchone()
    assets = rows_to_dicts(conn.execute(
        "SELECT * FROM fixed_assets WHERE company_id = ? AND status IN ('ativo', 'depreciado')", (company_id,)
    ).fetchall())
    conn.close()

    sped_content = SpedFiscalGenerator.generate(
        company, invoices, s_date, e_date,
        fiscal_entries=fiscal_entries,
        apuration_icms=dict(ap_row) if ap_row else None,
        fixed_assets=assets,
    )
    cnpj = company.get("cnpj", "00000000000000")
    filename = f"SPED_Fiscal_{cnpj}_{s_date.replace('-', '')}.txt"

    return Response(
        content=sped_content,
        media_type="text/plain; charset=latin1",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/api/reports/fiscal-package")
def download_fiscal_package(
    month: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Exporta o Pacote Mensal Completo do Contador (ZIP):
    - Todos os XMLs de NF-e, NFC-e e NFS-e emitidos
    - Arquivo oficial do SPED Fiscal (EFD)
    - Relatório sintético de apuração de impostos
    """
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())

    m_tag = month or date.today().strftime("%Y-%m")
    s_date = f"{m_tag}-01"
    e_date = f"{m_tag}-31"

    invoices = rows_to_dicts(conn.execute("""
        SELECT * FROM invoices
        WHERE company_id = ? AND status = 'autorizada'
        AND substr(issued_at, 1, 7) = ?
        ORDER BY number ASC
    """, (company_id, m_tag)).fetchall())
    fiscal_entries = rows_to_dicts(conn.execute("""
        SELECT * FROM fiscal_entries
        WHERE company_id = ? AND competencia = ? AND status != 'cancelado'
        ORDER BY data_escrituracao, id
    """, (company_id, m_tag)).fetchall())
    ap_row = conn.execute("""
        SELECT * FROM fiscal_apurations WHERE company_id = ? AND competencia = ? AND imposto = 'ICMS' LIMIT 1
    """, (company_id, m_tag)).fetchone()
    assets = rows_to_dicts(conn.execute(
        "SELECT * FROM fixed_assets WHERE company_id = ? AND status IN ('ativo', 'depreciado')", (company_id,)
    ).fetchall())

    sped_txt = SpedFiscalGenerator.generate(
        company, invoices, s_date, e_date,
        fiscal_entries=fiscal_entries,
        apuration_icms=dict(ap_row) if ap_row else None,
        fixed_assets=assets,
    )

    # Resumo de impostos
    tot_faturamento = sum(float(i.get("total_invoice") or 0.0) for i in invoices)
    tot_icms = sum(float(i.get("total_icms") or 0.0) for i in invoices)
    tot_pis = sum(float(i.get("total_pis") or 0.0) for i in invoices)
    tot_cofins = sum(float(i.get("total_cofins") or 0.0) for i in invoices)
    tot_iss = sum(float(i.get("total_iss") or 0.0) for i in invoices)

    resumo_fiscal = {
        "competencia": m_tag,
        "empresa": company.get("razao_social"),
        "cnpj": company.get("cnpj"),
        "regime_tributario": company.get("regime_tributario"),
        "total_notas_emitidas": len(invoices),
        "faturamento_bruto": round(tot_faturamento, 2),
        "impostos_apurados": {
            "icms": round(tot_icms, 2),
            "pis": round(tot_pis, 2),
            "cofins": round(tot_cofins, 2),
            "iss": round(tot_iss, 2),
            "total_impostos": round(tot_icms + tot_pis + tot_cofins + tot_iss, 2)
        }
    }
    conn.close()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. XMLs
        for inv in invoices:
            zf.writestr(f"XMLs/{inv['model']}_{inv['number']}_{inv['access_key']}.xml", inv.get("xml_content") or "")

        # 2. SPED
        zf.writestr(f"SPED/SPED_Fiscal_{m_tag}.txt", sped_txt)

        # 3. Resumo Fiscal JSON
        zf.writestr("Resumo_Apuracao_Fiscal.json", json.dumps(resumo_fiscal, indent=2, ensure_ascii=False))

    buf.seek(0)
    filename = f"Pacote_Contador_{company.get('cnpj', 'empresa')}_{m_tag}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ==========================================
# 2. PORTAL DO CONTADOR (ACESSO PÚBLICO VIA TOKEN)
# ==========================================
@router.get("/api/portal/accountant/{token}")
def get_accountant_portal(token: str):
    """Painel do Contador: dados da empresa, resumo fiscal do mês e links diretos para download."""
    conn = get_conn()
    company = conn.execute("SELECT * FROM companies WHERE accountant_token = ? OR CAST(id AS TEXT) = ? LIMIT 1", (token, token)).fetchone()
    if not company:
        conn.close()
        raise HTTPException(status_code=404, detail="Token do contador inválido ou expirado.")

    comp_dict = dict(company)
    company_id = comp_dict["id"]
    month_tag = date.today().strftime("%Y-%m")

    invoices = rows_to_dicts(conn.execute("""
        SELECT id, model, series, number, access_key, total_invoice, issued_at, status
        FROM invoices
        WHERE company_id = ? AND substr(issued_at, 1, 7) = ?
        ORDER BY id DESC
    """, (company_id, month_tag)).fetchall())
    conn.close()

    tot_val = sum(float(i.get("total_invoice") or 0.0) for i in invoices if i["status"] != "cancelada")

    return {
        "company": {
            "razao_social": comp_dict.get("razao_social"),
            "cnpj": comp_dict.get("cnpj"),
            "regime_tributario": comp_dict.get("regime_tributario"),
            "uf": comp_dict.get("uf"),
            "cidade": comp_dict.get("cidade"),
        },
        "period": month_tag,
        "invoices_count": len(invoices),
        "total_billed": round(tot_val, 2),
        "invoices": invoices,
        "actions": {
            "download_package_url": f"/api/portal/accountant/{token}/package",
            "download_sped_url": f"/api/portal/accountant/{token}/sped"
        }
    }


@router.get("/api/portal/accountant/{token}/package")
def download_accountant_package_portal(token: str, month: Optional[str] = None):
    """Download direto do pacote do contador (ZIP) autenticado pelo token exclusivo do escritório contábil."""
    conn = get_conn()
    company = conn.execute("SELECT * FROM companies WHERE accountant_token = ? OR CAST(id AS TEXT) = ? LIMIT 1", (token, token)).fetchone()
    if not company:
        conn.close()
        raise HTTPException(status_code=404, detail="Token inválido.")

    comp_dict = dict(company)
    company_id = comp_dict["id"]

    m_tag = month or date.today().strftime("%Y-%m")
    s_date = f"{m_tag}-01"
    e_date = f"{m_tag}-31"

    invoices = rows_to_dicts(conn.execute("""
        SELECT * FROM invoices
        WHERE company_id = ? AND status = 'autorizada'
        AND substr(issued_at, 1, 7) = ?
        ORDER BY number ASC
    """, (company_id, m_tag)).fetchall())

    sped_txt = SpedFiscalGenerator.generate(comp_dict, invoices, s_date, e_date)
    conn.close()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for inv in invoices:
            zf.writestr(f"XMLs/{inv['model']}_{inv['number']}_{inv['access_key']}.xml", inv.get("xml_content") or "")
        zf.writestr(f"SPED/SPED_Fiscal_{m_tag}.txt", sped_txt)

    buf.seek(0)
    filename = f"Pacote_Contador_{comp_dict.get('cnpj', 'empresa')}_{m_tag}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/api/portal/accountant/{token}/sped")
def download_accountant_sped_portal(token: str):
    """Download direto do SPED Fiscal pelo contador."""
    conn = get_conn()
    company = conn.execute("SELECT * FROM companies WHERE accountant_token = ? OR CAST(id AS TEXT) = ? LIMIT 1", (token, token)).fetchone()
    if not company:
        conn.close()
        raise HTTPException(status_code=404, detail="Token inválido.")

    comp_dict = dict(company)
    today = date.today()
    s_date = date(today.year, today.month, 1).isoformat()
    e_date = today.isoformat()

    invoices = rows_to_dicts(conn.execute("""
        SELECT * FROM invoices
        WHERE company_id = ? AND status = 'autorizada'
        AND substr(issued_at, 1, 10) BETWEEN ? AND ?
        ORDER BY number ASC
    """, (comp_dict["id"], s_date, e_date)).fetchall())
    conn.close()

    sped_txt = SpedFiscalGenerator.generate(comp_dict, invoices, s_date, e_date)
    filename = f"SPED_{comp_dict.get('cnpj')}_{s_date.replace('-', '')}.txt"
    return Response(
        content=sped_txt,
        media_type="text/plain; charset=latin1",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ==========================================
# 3. EFD CONTRIBUIÇÕES (PIS/COFINS)
# ==========================================
@router.get("/api/reports/efd-contribuicoes-preview")
def efd_contribuicoes_preview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Prévia do EFD Contribuições (PIS/COFINS) sem gerar o arquivo."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone())
    today = date.today()
    s_date = start_date or date(today.year, today.month, 1).isoformat()
    e_date = end_date or today.isoformat()
    invoices = rows_to_dicts(conn.execute("""
        SELECT total_invoice, total_pis, total_cofins, model
        FROM invoices WHERE company_id=? AND status='autorizada'
        AND substr(issued_at,1,10) BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchall())
    purchases = rows_to_dicts(conn.execute("""
        SELECT COALESCE(SUM(total_value),0) as total_compras FROM purchase_orders
        WHERE company_id=? AND status='recebido'
        AND substr(created_at,1,10) BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchall())
    conn.close()
    tot_receita = sum(float(i.get("total_invoice") or 0) for i in invoices)
    tot_pis_saida = sum(float(i.get("total_pis") or 0) for i in invoices)
    tot_cofins_saida = sum(float(i.get("total_cofins") or 0) for i in invoices)
    tot_compras = float((purchases[0].get("total_compras") or 0) if purchases else 0)
    # Créditos estimados (alíquotas básicas Lucro Real não-cumulativo: PIS 1,65% / COFINS 7,6%)
    pis_credito = round(tot_compras * 0.0165, 2)
    cofins_credito = round(tot_compras * 0.076, 2)
    regime = company.get("regime_tributario", "simples_nacional")
    return {
        "start_date": s_date,
        "end_date": e_date,
        "regime": regime,
        "count_nfe": len(invoices),
        "total_receita": round(tot_receita, 2),
        "pis_saida": round(tot_pis_saida, 2),
        "cofins_saida": round(tot_cofins_saida, 2),
        "total_compras": tot_compras,
        "pis_credito_estimado": pis_credito if regime == "lucro_real" else 0,
        "cofins_credito_estimado": cofins_credito if regime == "lucro_real" else 0,
        "pis_a_recolher": round(max(0, tot_pis_saida - (pis_credito if regime == "lucro_real" else 0)), 2),
        "cofins_a_recolher": round(max(0, tot_cofins_saida - (cofins_credito if regime == "lucro_real" else 0)), 2),
        "tipo_apuracao": "não-cumulativo" if regime == "lucro_real" else "cumulativo",
    }


@router.get("/api/reports/efd-contribuicoes")
def download_efd_contribuicoes(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Gera arquivo oficial EFD Contribuições (Blocos 0, A, C, D, F, I, M, P, 1 e 9)."""
    import re as _re
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone())
    today = date.today()
    s_date = start_date or date(today.year, today.month, 1).isoformat()
    e_date = end_date or today.isoformat()

    invoices = rows_to_dicts(conn.execute("""
        SELECT * FROM invoices WHERE company_id=? AND status='autorizada'
        AND substr(issued_at,1,10) BETWEEN ? AND ?
        ORDER BY issued_at ASC
    """, (company_id, s_date, e_date)).fetchall())
    fiscal_entries = rows_to_dicts(conn.execute("""
        SELECT * FROM fiscal_entries WHERE company_id=? AND data_escrituracao BETWEEN ? AND ? AND status!='cancelado'
        ORDER BY data_escrituracao, id
    """, (company_id, s_date, e_date)).fetchall())
    assets = rows_to_dicts(conn.execute(
        "SELECT * FROM fixed_assets WHERE company_id=? AND status IN ('ativo','depreciado')", (company_id,)
    ).fetchall())
    conn.close()

    def _d8(s: str) -> str:
        c = _re.sub(r"\D", "", str(s or "")[:10])
        return f"{c[6:8]}{c[4:6]}{c[0:4]}" if len(c) == 8 else c

    def _n2(v: Any) -> str:
        return f"{float(v or 0):.2f}".replace(".", ",")

    cnpj = _re.sub(r"\D", "", company.get("cnpj") or "")
    razao = (company.get("razao_social") or "EMPRESA").replace("|", "")
    uf = company.get("uf") or "MT"
    cod_mun = _re.sub(r"\D", "", str(company.get("codigo_ibge_municipio") or "5103403"))
    regime = (company.get("regime_tributario") or "lucro_presumido").lower()
    is_real = regime == "lucro_real"
    dt_ini = _d8(s_date)
    dt_fin = _d8(e_date)

    lines: list[str] = []
    reg_counts: Dict[str, int] = {}

    def emit(reg: str, *fields: Any) -> None:
        lines.append(f"|{reg}|" + "|".join(str(f).replace("|", "") for f in fields) + "|")
        reg_counts[reg] = reg_counts.get(reg, 0) + 1

    def close_blk(prefix: str, reg: str) -> None:
        reg_counts[reg] = reg_counts.get(reg, 0) + 1
        tot = sum(v for k, v in reg_counts.items() if k.startswith(prefix))
        lines.append(f"|{reg}|{tot}|")

    # Bloco 0
    emit("0000", "006", "0", "", "", dt_ini, dt_fin, razao, cnpj, uf, cod_mun, "", "00", "0")
    emit("0001", "0")
    emit("0100",
         company.get("contador_nome") or "CONTADOR RESPONSAVEL",
         _re.sub(r"\D", "", str(company.get("contador_cpf") or "00000000000")),
         company.get("contador_crc") or "CRC-000000/O",
         _re.sub(r"\D", "", str(company.get("contador_cnpj") or cnpj)),
         _re.sub(r"\D", "", str(company.get("contador_cep") or "78000000")),
         company.get("contador_endereco") or "CENTRO",
         company.get("contador_numero") or "S/N", "", "CENTRO",
         _re.sub(r"\D", "", str(company.get("contador_telefone") or "")), "",
         company.get("contador_email") or company.get("email") or "",
         _re.sub(r"\D", "", str(company.get("contador_cod_mun") or cod_mun)))
    emit("0110", "1" if is_real else "2", "1", "1", "")
    emit("0140", cnpj, razao, cnpj, uf, company.get("inscricao_estadual") or "", cod_mun, company.get("inscricao_municipal") or "", "")
    close_blk("0", "0990")

    # Separação serviços (Bloco A) e mercadorias (Bloco C)
    serv_docs = [e for e in fiscal_entries if e.get("tipo") in ("servico_prestado", "servico_tomado")]
    merc_docs = [e for e in fiscal_entries if e.get("tipo") in ("entrada", "saida")]
    linked_inv_ids = {e.get("origem_id") for e in fiscal_entries if e.get("origem_tipo") == "invoice" and e.get("origem_id")}

    tot_pis_deb = tot_cof_deb = tot_pis_cred = tot_cof_cred = 0.0

    # Bloco A (Serviços)
    emit("A001", "0" if serv_docs else "1")
    if serv_docs:
        emit("A010", cnpj)
        for d in serv_docs:
            ind_oper = "0" if d["tipo"] == "servico_tomado" else "1"
            val = float(d.get("valor_contabil") or 0)
            vp, vc = float(d.get("valor_pis") or 0), float(d.get("valor_cofins") or 0)
            ap, ac = float(d.get("aliquota_pis") or 0), float(d.get("aliquota_cofins") or 0)
            cst = d.get("cst_pis_cofins") or ("50" if ind_oper == "0" else "01")
            dt_d = _d8(d.get("data_emissao") or s_date)
            emit("A100", ind_oper, "0" if ind_oper == "1" else "1", f"P{d.get('id')}", "00", d.get("serie") or "1", "", d.get("numero"), "", dt_d, dt_d, _n2(val), "0", "0,00", _n2(val), _n2(vp), _n2(val), _n2(vc), _n2(d.get("valor_iss") or 0))
            emit("A170", "1", "SERVICO", "", _n2(val), "0,00", "01", "", cst, _n2(val), _n2(ap), _n2(vp), cst, _n2(val), _n2(ac), _n2(vc), "", "")
            if ind_oper == "1":
                tot_pis_deb += vp
                tot_cof_deb += vc
            elif is_real:
                tot_pis_cred += vp
                tot_cof_cred += vc
    close_blk("A", "A990")

    # Bloco C (Mercadorias)
    has_c = bool(merc_docs or [i for i in invoices if i.get("id") not in linked_inv_ids])
    emit("C001", "0" if has_c else "1")
    if has_c:
        emit("C010", cnpj, "2")
        for d in merc_docs:
            ind_oper = "0" if d["tipo"] == "entrada" else "1"
            val = float(d.get("valor_contabil") or 0)
            vp, vc = float(d.get("valor_pis") or 0), float(d.get("valor_cofins") or 0)
            ap, ac = float(d.get("aliquota_pis") or 0), float(d.get("aliquota_cofins") or 0)
            cst = d.get("cst_pis_cofins") or ("50" if ind_oper == "0" else "01")
            dt_d = _d8(d.get("data_emissao") or s_date)
            emit("C100", ind_oper, "0" if ind_oper == "1" else "1", f"P{d.get('id')}", d.get("modelo") or "55", "00", d.get("serie") or "1", d.get("numero"), d.get("chave_acesso") or "", dt_d, dt_d, _n2(val), "0", "0,00", "0,00", _n2(val), "9", "0,00", "0,00", "0,00", _n2(d.get("base_icms") or 0), _n2(d.get("valor_icms") or 0), "0,00", "0,00", _n2(d.get("valor_ipi") or 0), _n2(vp), _n2(vc), "0,00", "0,00")
            emit("C170", "1", "ITEM", "", "1,00", "UN", _n2(val), "0,00", "0", d.get("cst_icms") or "000", d.get("cfop") or "5102", "", _n2(d.get("base_icms") or 0), _n2(d.get("aliquota_icms") or 0), _n2(d.get("valor_icms") or 0), "0,00", "0,00", "0,00", "0", "", "", "0,00", "0,00", "0,00", cst, _n2(val), _n2(ap), "0,00", "0,00", _n2(vp), cst, _n2(val), _n2(ac), "0,00", "0,00", _n2(vc), "")
            if ind_oper == "1":
                tot_pis_deb += vp
                tot_cof_deb += vc
            elif is_real:
                tot_pis_cred += vp
                tot_cof_cred += vc
        for inv in invoices:
            if inv.get("id") in linked_inv_ids:
                continue
            val = float(inv.get("total_invoice") or 0)
            vp, vc = float(inv.get("total_pis") or 0), float(inv.get("total_cofins") or 0)
            dt_d = _d8(inv.get("issued_at") or s_date)
            emit("C100", "1", "0", f"C{inv.get('contact_id') or 1}", "55", "00", inv.get("series") or "1", inv.get("number") or "1", inv.get("access_key") or "", dt_d, dt_d, _n2(val), "0", "0,00", "0,00", _n2(val), "9", "0,00", "0,00", "0,00", _n2(val), _n2(inv.get("total_icms") or 0), "0,00", "0,00", "0,00", _n2(vp), _n2(vc), "0,00", "0,00")
            emit("C170", "1", "MERCADORIA", "", "1,00", "UN", _n2(val), "0,00", "0", "000", "5102", "", _n2(val), "0,00", _n2(inv.get("total_icms") or 0), "0,00", "0,00", "0,00", "0", "", "", "0,00", "0,00", "0,00", "01", _n2(val), "1,65" if is_real else "0,65", "0,00", "0,00", _n2(vp), "01", _n2(val), "7,60" if is_real else "3,00", "0,00", "0,00", _n2(vc), "")
            tot_pis_deb += vp
            tot_cof_deb += vc
    close_blk("C", "C990")

    emit("D001", "1")
    close_blk("D", "D990")

    # Bloco F (F120 Ativo Imobilizado + F600 Retenções)
    cred_f120_pis = cred_f120_cof = 0.0
    ret_docs = [e for e in fiscal_entries if float(e.get("csrf_retido") or 0) > 0]
    has_f = bool((is_real and assets) or ret_docs)
    emit("F001", "0" if has_f else "1")
    if has_f:
        emit("F010", cnpj)
        if is_real:
            for a in assets:
                parc = round(float(a.get("acquisition_value") or 0) / 48.0, 2)
                if parc <= 0:
                    continue
                pp, pc = round(parc * 0.0165, 2), round(parc * 0.0760, 2)
                cred_f120_pis += pp
                cred_f120_cof += pc
                emit("F120", "09", "01", "1", "50", _n2(parc), "0,00", _n2(parc), "1,65", _n2(pp), "50", _n2(parc), "7,60", _n2(pc), "", "")
        for r in ret_docs:
            csrf = float(r.get("csrf_retido") or 0)
            emit("F600", "01", _d8(r.get("data_emissao") or s_date), _n2(r.get("valor_contabil") or 0), _n2(csrf), "5952", "0", cnpj, _n2(round(csrf * 0.14, 2)), _n2(round(csrf * 0.645, 2)), "0")
    close_blk("F", "F990")

    tot_pis_cred += cred_f120_pis
    tot_cof_cred += cred_f120_cof
    pis_rec = max(0.0, round(tot_pis_deb - tot_pis_cred, 2))
    cof_rec = max(0.0, round(tot_cof_deb - tot_cof_cred, 2))

    emit("I001", "1")
    close_blk("I", "I990")

    # Bloco M — Apuração PIS e COFINS
    emit("M001", "0")
    emit("M100", "101", "0", _n2(tot_pis_cred * 100 / 1.65 if tot_pis_cred else 0), "1,65", "0,0000", "0,00", _n2(tot_pis_cred), "0,00", "0,00", _n2(tot_pis_cred), _n2(min(tot_pis_deb, tot_pis_cred)), "0,00", "0,00", _n2(max(0.0, tot_pis_cred - tot_pis_deb)))
    emit("M200", _n2(tot_pis_deb), _n2(min(tot_pis_deb, tot_pis_cred)), "0,00", _n2(pis_rec), "0,00", "0,00", "0,00", _n2(pis_rec), "0,00", "0,00", "0,00", _n2(pis_rec))
    emit("M205", "08", "6912" if is_real else "8109", _n2(pis_rec))
    emit("M210", "01" if is_real else "51", _n2(tot_pis_deb * 100 / (1.65 if is_real else 0.65) if tot_pis_deb else 0), "0,00", _n2(tot_pis_deb), "1,65" if is_real else "0,65", "0,00", "", _n2(tot_pis_deb), "0,00", "0,00", "0,00", "0,00", _n2(tot_pis_deb))
    emit("M500", "101", "0", _n2(tot_cof_cred * 100 / 7.60 if tot_cof_cred else 0), "7,60", "0,0000", "0,00", _n2(tot_cof_cred), "0,00", "0,00", _n2(tot_cof_cred), _n2(min(tot_cof_deb, tot_cof_cred)), "0,00", "0,00", _n2(max(0.0, tot_cof_cred - tot_cof_deb)))
    emit("M600", _n2(tot_cof_deb), _n2(min(tot_cof_deb, tot_cof_cred)), "0,00", _n2(cof_rec), "0,00", "0,00", "0,00", _n2(cof_rec), "0,00", "0,00", "0,00", _n2(cof_rec))
    emit("M605", "08", "5856" if is_real else "2172", _n2(cof_rec))
    emit("M610", "01" if is_real else "51", _n2(tot_cof_deb * 100 / (7.60 if is_real else 3.00) if tot_cof_deb else 0), "0,00", _n2(tot_cof_deb), "7,60" if is_real else "3,00", "0,00", "", _n2(tot_cof_deb), "0,00", "0,00", "0,00", "0,00", _n2(tot_cof_deb))
    close_blk("M", "M990")

    emit("P001", "1")
    close_blk("P", "P990")
    emit("1001", "1")
    close_blk("1", "1990")

    # Bloco 9
    emit("9001", "0")
    existing = sorted(reg_counts.keys())
    all_9900 = dict(reg_counts)
    all_9900["9900"] = len(existing) + 3
    all_9900["9990"] = 1
    all_9900["9999"] = 1
    for reg, cnt in sorted(all_9900.items()):
        lines.append(f"|9900|{reg}|{cnt}|")
        reg_counts["9900"] = reg_counts.get("9900", 0) + 1
    reg_counts["9990"] = 1
    reg_counts["9999"] = 1
    b9_tot = sum(v for k, v in reg_counts.items() if k.startswith("9"))
    lines.append(f"|9990|{b9_tot}|")
    lines.append(f"|9999|{len(lines) + 1}|")

    content = "\r\n".join(lines) + "\r\n"
    fname = f"EFD_Contribuicoes_{cnpj}_{dt_ini}.txt"
    return Response(content=content.encode("latin1", errors="replace"),
                    media_type="text/plain; charset=latin1",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ==========================================
# 4. EFD-REINF (Retenções na Fonte)
# ==========================================
@router.get("/api/reports/efd-reinf-preview")
def efd_reinf_preview(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Prévia dos eventos EFD-Reinf do mês."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone())
    today = date.today()
    comp = competencia or today.strftime("%Y-%m")
    year, month = comp.split("-")
    import calendar
    end_day = calendar.monthrange(int(year), int(month))[1]
    s_date = f"{year}-{month}-01"
    e_date = f"{year}-{month}-{end_day:02d}"
    # R-4020: Pagamentos / créditos com retenção (serviços tomados)
    servicos = rows_to_dicts(conn.execute("""
        SELECT COALESCE(SUM(amount),0) as total_pagamentos,
               COALESCE(SUM(amount*0.015),0) as ir_retido,
               COALESCE(SUM(amount*0.03),0) as csll_cofins_pis_retidos,
               COUNT(*) as qtd
        FROM financial_entries
        WHERE company_id=? AND type='despesa' AND status='pago'
        AND due_date BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchall())
    # R-1000: Informações do Contribuinte
    conn.close()
    s = servicos[0] if servicos else {}
    total_pag = float(s.get("total_pagamentos") or 0)
    ir = float(s.get("ir_retido") or 0)
    csll_cof_pis = float(s.get("csll_cofins_pis_retidos") or 0)
    return {
        "competencia": comp,
        "razao_social": company.get("razao_social"),
        "cnpj": company.get("cnpj"),
        "eventos": {
            "R-1000": {"descricao": "Informações do Contribuinte", "status": "obrigatório"},
            "R-2010": {"descricao": "Retenção Contribuições — Serviços Tomados", "valor": round(total_pag, 2)},
            "R-4010": {"descricao": "Pagamentos/Créditos a Beneficiários PF", "ir_retido": round(ir, 2)},
            "R-4020": {"descricao": "Pagamentos/Créditos a Beneficiários PJ", "csll_cofins_pis": round(csll_cof_pis, 2)},
            "R-9000": {"descricao": "Fechamento dos Eventos Periódicos"},
        },
        "total_pagamentos": round(total_pag, 2),
        "total_retencoes_estimadas": round(ir + csll_cof_pis, 2),
        "vencimento": f"{year}-{month}-15",
    }


# ==========================================
# 5. DCTFWEB
# ==========================================
@router.get("/api/reports/dctfweb-preview")
def dctfweb_preview(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Prévia da DCTFWeb — débitos e créditos tributários federais."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone())
    today = date.today()
    comp = competencia or today.strftime("%Y-%m")
    year, month = comp.split("-")
    import calendar
    end_day = calendar.monthrange(int(year), int(month))[1]
    s_date = f"{year}-{month}-01"
    e_date = f"{year}-{month}-{end_day:02d}"
    # Folha
    payroll = conn.execute("""
        SELECT COALESCE(SUM(pi.inss),0) as total_inss,
               COALESCE(SUM(pi.irrf),0) as total_irrf,
               COALESCE(SUM(pi.fgts),0) as total_fgts
        FROM payroll_items pi JOIN payroll_runs pr ON pr.id=pi.run_id
        WHERE pr.company_id=? AND pr.competence=?
    """, (company_id, comp)).fetchone()
    # NF-e
    nf = conn.execute("""
        SELECT COALESCE(SUM(total_pis),0) as pis, COALESCE(SUM(total_cofins),0) as cofins,
               COALESCE(SUM(total_icms),0) as icms
        FROM invoices WHERE company_id=? AND status='autorizada'
        AND substr(issued_at,1,10) BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchone()
    conn.close()
    inss = float(payroll["total_inss"] or 0) if payroll else 0
    irrf = float(payroll["total_irrf"] or 0) if payroll else 0
    fgts = float(payroll["total_fgts"] or 0) if payroll else 0
    pis  = float(nf["pis"] or 0) if nf else 0
    cof  = float(nf["cofins"] or 0) if nf else 0
    total_debitos = inss + irrf + pis + cof
    return {
        "competencia": comp,
        "razao_social": company.get("razao_social"),
        "cnpj": company.get("cnpj"),
        "regime": company.get("regime_tributario"),
        "debitos": {
            "INSS_patronal": round(inss, 2),
            "IRRF_folha": round(irrf, 2),
            "PIS_faturamento": round(pis, 2),
            "COFINS_faturamento": round(cof, 2),
        },
        "total_debitos": round(total_debitos, 2),
        "total_fgts": round(fgts, 2),
        "creditos": 0,
        "saldo_a_recolher": round(total_debitos, 2),
        "vencimento_darf": f"{year}-{month}-20",
        "vencimento_fgts": f"{year}-{month}-07",
        "observacao": "Valores estimados com base nos dados do ERP. Revisar antes de transmitir.",
    }


# ==========================================
# 6. ECF (Escrituração Contábil Fiscal — IRPJ/CSLL)
# ==========================================
@router.get("/api/reports/ecf-preview")
def ecf_preview(
    year: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Prévia da ECF (IRPJ e CSLL Lucro Real/Presumido)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone())
    yr = year or date.today().year
    s_date = f"{yr}-01-01"
    e_date = f"{yr}-12-31"
    receitas = conn.execute("""
        SELECT COALESCE(SUM(amount),0) as total FROM financial_entries
        WHERE company_id=? AND type='receita' AND status='pago'
        AND due_date BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchone()
    despesas = conn.execute("""
        SELECT COALESCE(SUM(amount),0) as total FROM financial_entries
        WHERE company_id=? AND type='despesa' AND status='pago'
        AND due_date BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchone()
    conn.close()
    receita = float(receitas["total"] or 0)
    despesa = float(despesas["total"] or 0)
    lucro_bruto = receita - despesa
    regime = company.get("regime_tributario", "lucro_presumido")
    if regime == "lucro_presumido":
        base_irpj = receita * 0.32
        base_csll = receita * 0.32
    else:
        base_irpj = max(0, lucro_bruto)
        base_csll = max(0, lucro_bruto)
    irpj_normal = base_irpj * 0.15
    irpj_adicional = max(0, base_irpj - 240000) * 0.10
    csll = base_csll * 0.09
    return {
        "ano_calendario": yr,
        "razao_social": company.get("razao_social"),
        "cnpj": company.get("cnpj"),
        "regime": regime,
        "receita_bruta_total": round(receita, 2),
        "total_despesas": round(despesa, 2),
        "lucro_bruto_contabil": round(lucro_bruto, 2),
        "base_calculo_irpj": round(base_irpj, 2),
        "base_calculo_csll": round(base_csll, 2),
        "irpj_normal_15pct": round(irpj_normal, 2),
        "irpj_adicional_10pct": round(irpj_adicional, 2),
        "irpj_total": round(irpj_normal + irpj_adicional, 2),
        "csll_total": round(csll, 2),
        "total_impostos_federais": round(irpj_normal + irpj_adicional + csll, 2),
        "prazo_entrega": f"{yr+1}-07-31",
        "observacao": "Valores estimados. Base real depende de adições, exclusões e compensações do LALUR.",
    }


@router.get("/api/reports/ecf")
def download_ecf(
    year: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Gera e baixa o arquivo oficial SPED ECF (.txt) pronto para validação no PVA RFB."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())
    yr = year or date.today().year
    s_date, e_date = f"{yr}-01-01", f"{yr}-12-31"

    accounts = rows_to_dicts(conn.execute(
        "SELECT * FROM accounting_accounts WHERE company_id = ? AND active = 1 ORDER BY code",
        (company_id,),
    ).fetchall())
    for acc in accounts:
        tot = conn.execute("""
            SELECT COALESCE(SUM(l.debit),0) as td, COALESCE(SUM(l.credit),0) as tc
            FROM accounting_entry_lines l
            JOIN accounting_entries e ON e.id = l.entry_id
            WHERE l.account_id = ? AND e.company_id = ? AND e.entry_date BETWEEN ? AND ?
        """, (acc["id"], company_id, s_date, e_date)).fetchone()
        acc["_total_debit"] = float(tot["td"])
        acc["_total_credit"] = float(tot["tc"])

    lalur_lancs = rows_to_dicts(conn.execute(
        "SELECT * FROM lalur_lancamentos WHERE company_id = ? AND ano = ? ORDER BY id", (company_id, yr)
    ).fetchall())
    parte_b = rows_to_dicts(conn.execute(
        "SELECT * FROM lalur_parte_b WHERE company_id = ? AND ano = ? ORDER BY id", (company_id, yr)
    ).fetchall())

    rec = float(conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM financial_entries WHERE company_id=? AND type='receita' AND status='pago' AND due_date BETWEEN ? AND ?",
        (company_id, s_date, e_date),
    ).fetchone()[0] or 0.0)
    desp = float(conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM financial_entries WHERE company_id=? AND type='despesa' AND status='pago' AND due_date BETWEEN ? AND ?",
        (company_id, s_date, e_date),
    ).fetchone()[0] or 0.0)
    conn.close()

    adicoes = sum(float(l.get("valor") or 0) for l in lalur_lancs if l.get("tipo") == "adicao")
    exclusoes = sum(float(l.get("valor") or 0) for l in lalur_lancs if l.get("tipo") == "exclusao")
    lucro_real = max(0.0, (rec - desp) + adicoes - exclusoes)
    irpj_15 = round(lucro_real * 0.15, 2)
    irpj_add = round(max(0.0, lucro_real - 240000.0) * 0.10, 2)
    csll_9 = round(lucro_real * 0.09, 2)
    apuracao = {
        "adicoes": round(adicoes, 2),
        "exclusoes": round(exclusoes, 2),
        "lucro_real": round(lucro_real, 2),
        "base_calculo_positiva": round(lucro_real, 2),
        "irpj_15pct": irpj_15,
        "irpj_adicional_10pct": irpj_add,
        "csll_9pct": csll_9,
    }

    txt = EcfGenerator.generate(company, yr, accounts, lalur_lancs, parte_b, apuracao, receita_bruta=rec)
    cnpj = "".join(c for c in company.get("cnpj", "00000000000000") if c.isdigit())
    return Response(
        content=txt.encode("latin1", errors="replace"),
        media_type="text/plain; charset=latin1",
        headers={"Content-Disposition": f'attachment; filename="SPED_ECF_{cnpj}_{yr}.txt"'},
    )


# ==========================================
# 7. AUDITORIA FISCAL CRUZADA, PROCESSOS E CNDs (ESCRITÓRIO CONTÁBIL)
# ==========================================

class ProcessUpdatePayload(BaseModel):
    status: Optional[str] = None
    responsavel: Optional[str] = None
    observacoes: Optional[str] = None


class CndCreatePayload(BaseModel):
    tipo: str  # RFB_PGFN, FGTS_CRF, ESTADUAL, MUNICIPAL, TRABALHISTA_CNDT
    orgao_emissor: str = ""
    numero_certidao: str = ""
    codigo_controle: str = ""
    data_emissao: str
    data_validade: str
    situacao: str = "negativa"
    observacoes: str = ""


@router.get("/api/audit/cruzamento-fiscal")
def cruzamento_fiscal(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Domínio Auditoria Fiscal Cruzada: NF-e x Escrita Fiscal x Contábil x Folha x Diário."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    yr, mo = map(int, comp.split("-"))
    last_day = calendar.monthrange(yr, mo)[1]
    s_date, e_date = f"{yr}-{mo:02d}-01", f"{yr}-{mo:02d}-{last_day:02d}"

    # Eixo 1: Faturamento NF-e/NFS-e x Escrita Fiscal x Receita Contábil
    inv_row = conn.execute("""
        SELECT COALESCE(SUM(total_invoice),0) as fat,
               COALESCE(SUM(total_icms),0) as icms,
               COALESCE(SUM(total_pis),0) as pis,
               COALESCE(SUM(total_cofins),0) as cofins
        FROM invoices WHERE company_id = ? AND status = 'autorizada'
          AND substr(issued_at, 1, 10) BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchone()
    fat_nfe = round(float(inv_row["fat"] or 0.0), 2)

    fe_out_row = conn.execute("""
        SELECT COALESCE(SUM(valor_contabil),0) as fat,
               COALESCE(SUM(valor_icms),0) as icms,
               COALESCE(SUM(valor_pis),0) as pis,
               COALESCE(SUM(valor_cofins),0) as cofins
        FROM fiscal_entries
        WHERE company_id = ? AND competencia = ? AND tipo IN ('saida', 'servico_prestado') AND status != 'cancelado'
    """, (company_id, comp)).fetchone()
    fat_fiscal = round(float(fe_out_row["fat"] or 0.0), 2)

    rec_contab = round(float(conn.execute("""
        SELECT COALESCE(SUM(l.credit - l.debit), 0)
        FROM accounting_entry_lines l
        JOIN accounting_entries e ON e.id = l.entry_id
        JOIN accounting_accounts a ON a.id = l.account_id
        WHERE e.company_id = ? AND a.account_type = 'receita'
          AND e.entry_date BETWEEN ? AND ? AND COALESCE(e.entry_type, '') != 'encerramento'
    """, (company_id, s_date, e_date)).fetchone()[0] or 0.0), 2)

    # Eixo 2: Tributos Destacados x Apuração Fiscal
    trib_notas = round(
        float(fe_out_row["icms"] or 0) + float(fe_out_row["pis"] or 0) + float(fe_out_row["cofins"] or 0)
        if fat_fiscal > 0 else float(inv_row["icms"] or 0) + float(inv_row["pis"] or 0) + float(inv_row["cofins"] or 0),
        2,
    )
    ap_rows = rows_to_dicts(conn.execute(
        "SELECT imposto, debitos, valor_a_recolher FROM fiscal_apurations WHERE company_id = ? AND competencia = ?",
        (company_id, comp),
    ).fetchall())
    trib_apurado = round(sum(
        float(a["debitos"] or 0) for a in ap_rows if a["imposto"] in ("ICMS", "PIS", "COFINS")
    ), 2)

    # Eixo 3: Folha de Pagamento x Contabilização DP
    folha_row = conn.execute("""
        SELECT COALESCE(SUM(pi.gross_salary),0) as bruto,
               COALESCE(SUM(pi.inss),0) as inss,
               COALESCE(SUM(pi.irrf),0) as irrf,
               COALESCE(SUM(pi.fgts),0) as fgts
        FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id = pi.run_id
        WHERE pr.company_id = ? AND pr.competence = ? AND pr.status != 'cancelado'
    """, (company_id, comp)).fetchone()
    folha_bruto = round(float(folha_row["bruto"] or 0.0), 2)
    folha_contab = round(float(conn.execute("""
        SELECT COALESCE(SUM(l.debit - l.credit), 0)
        FROM accounting_entry_lines l
        JOIN accounting_entries e ON e.id = l.entry_id
        JOIN accounting_accounts a ON a.id = l.account_id
        WHERE e.company_id = ? AND a.code LIKE '5.1%'
          AND e.entry_date BETWEEN ? AND ? AND COALESCE(e.entry_type, '') != 'encerramento'
    """, (company_id, s_date, e_date)).fetchone()[0] or 0.0), 2)

    # Eixo 4: Partidas Dobradas no Livro Diário
    diario_row = conn.execute("""
        SELECT COALESCE(SUM(l.debit),0) as td, COALESCE(SUM(l.credit),0) as tc
        FROM accounting_entry_lines l
        JOIN accounting_entries e ON e.id = l.entry_id
        WHERE e.company_id = ? AND e.entry_date BETWEEN ? AND ?
    """, (company_id, s_date, e_date)).fetchone()
    tot_d = round(float(diario_row["td"] or 0.0), 2)
    tot_c = round(float(diario_row["tc"] or 0.0), 2)
    conn.close()

    cruzamentos = [
        {
            "eixo": "Faturamento NF-e × Escrita Fiscal",
            "modulo_a": "Emissor NF-e/NFS-e", "valor_a": fat_nfe,
            "modulo_b": "Livros Fiscais (Saídas)", "valor_b": fat_fiscal,
            "diferenca": round(fat_nfe - fat_fiscal, 2),
            "ok": abs(fat_nfe - fat_fiscal) < 0.05 or (fat_nfe == 0 and fat_fiscal > 0),
        },
        {
            "eixo": "Escrita Fiscal × Receita Contábil",
            "modulo_a": "Livros Fiscais (Saídas)", "valor_a": fat_fiscal or fat_nfe,
            "modulo_b": "Contabilidade (Grupo 3.x)", "valor_b": rec_contab,
            "diferenca": round((fat_fiscal or fat_nfe) - rec_contab, 2),
            "ok": abs((fat_fiscal or fat_nfe) - rec_contab) < 0.05 or (fat_fiscal == 0 and fat_nfe == 0 and rec_contab == 0),
        },
        {
            "eixo": "Tributos Destacados × Apuração Fiscal",
            "modulo_a": "Documentos Fiscais (ICMS/PIS/COFINS)", "valor_a": trib_notas,
            "modulo_b": "Apuração Mensal (Débitos)", "valor_b": trib_apurado,
            "diferenca": round(trib_notas - trib_apurado, 2),
            "ok": abs(trib_notas - trib_apurado) < 0.05 or (trib_notas == 0 and trib_apurado == 0),
        },
        {
            "eixo": "Folha de Pagamento × Contabilização DP",
            "modulo_a": "Folha Bruta (DP)", "valor_a": folha_bruto,
            "modulo_b": "Despesa Pessoal Contábil (5.1.x)", "valor_b": folha_contab,
            "diferenca": round(folha_bruto - folha_contab, 2),
            "ok": abs(folha_bruto - folha_contab) < 0.05 or (folha_bruto == 0 and folha_contab == 0),
        },
        {
            "eixo": "Integridade Livro Diário (Partidas Dobradas)",
            "modulo_a": "Total Débitos", "valor_a": tot_d,
            "modulo_b": "Total Créditos", "valor_b": tot_c,
            "diferenca": round(tot_d - tot_c, 2),
            "ok": abs(tot_d - tot_c) < 0.02,
        },
    ]

    divergencias: List[Dict[str, Any]] = []
    for cz in cruzamentos:
        if not cz["ok"]:
            divergencias.append({
                "severidade": "alta" if abs(cz["diferenca"]) > 100 else "media",
                "eixo": cz["eixo"],
                "modulo_a": cz["modulo_a"], "valor_a": cz["valor_a"],
                "modulo_b": cz["modulo_b"], "valor_b": cz["valor_b"],
                "diferenca": cz["diferenca"],
                "recomendacao": f"Conciliar {cz['modulo_a']} com {cz['modulo_b']} antes da transmissão do SPED/DCTFWeb.",
            })

    ok_count = sum(1 for c in cruzamentos if c["ok"])
    score = int(round((ok_count / len(cruzamentos)) * 100))
    status_geral = "conforme" if score == 100 else ("alerta" if score >= 60 else "critico")

    return {
        "competencia": comp,
        "score_conformidade": score,
        "status_geral": status_geral,
        "cruzamentos": cruzamentos,
        "divergencias": divergencias,
        "resumo": {
            "faturamento_nfe": fat_nfe,
            "faturamento_escrita": fat_fiscal,
            "receita_contabil": rec_contab,
            "folha_bruta": folha_bruto,
            "folha_inss": round(float(folha_row["inss"] or 0.0), 2),
            "folha_irrf": round(float(folha_row["irrf"] or 0.0), 2),
            "folha_fgts": round(float(folha_row["fgts"] or 0.0), 2),
        },
    }


@router.post("/api/office/processes/generate")
def generate_office_processes(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Gera a agenda mensal automática de obrigações acessórias (Domínio Processos) conforme regime da empresa."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    yr, mo = map(int, comp.split("-"))
    next_mo = 1 if mo == 12 else mo + 1
    next_yr = yr + 1 if mo == 12 else yr
    last_next = calendar.monthrange(next_yr, next_mo)[1]

    comp_row = conn.execute("SELECT regime_tributario, contador_nome FROM companies WHERE id = ?", (company_id,)).fetchone()
    regime = (comp_row["regime_tributario"] if comp_row else "simples_nacional") or "simples_nacional"
    resp = (comp_row["contador_nome"] if comp_row and comp_row["contador_nome"] else None) or "Contador Responsável"

    def _due(day: int) -> str:
        return f"{next_yr}-{next_mo:02d}-{min(day, last_next):02d}"

    obrigacoes = [
        ("FGTS Digital", _due(7)),
        ("eSocial — Eventos Periódicos (S-1200/S-1299)", _due(15)),
        ("DCTFWeb", _due(20)),
    ]
    if regime in ("simples_nacional", "mei"):
        obrigacoes.append(("PGDAS-D / Guia DAS", _due(20)))
    else:
        obrigacoes.extend([
            ("EFD-Reinf (R-2010/R-4000)", _due(15)),
            ("SPED Fiscal (EFD ICMS/IPI)", _due(25)),
            ("EFD-Contribuições (PIS/COFINS)", _due(10)),
            ("Balancete Contábil Mensal", _due(28)),
        ])

    for ob, venc in obrigacoes:
        conn.execute("""
            INSERT OR IGNORE INTO office_processes (company_id, competencia, obrigacao, regime, vencimento, responsavel, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pendente')
        """, (company_id, comp, ob, regime, venc, resp))
    conn.commit()
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM office_processes WHERE company_id = ? AND competencia = ? ORDER BY vencimento, id",
        (company_id, comp),
    ).fetchall())
    conn.close()
    return {"competencia": comp, "regime": regime, "processes": rows}


@router.get("/api/office/processes")
def list_office_processes(
    competencia: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Lista os processos/obrigações do escritório na competência."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = competencia or date.today().strftime("%Y-%m")
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM office_processes WHERE company_id = ? AND competencia = ? ORDER BY vencimento, id",
        (company_id, comp),
    ).fetchall())
    conn.close()
    return rows


@router.put("/api/office/processes/{proc_id}")
def update_office_process(
    proc_id: int,
    data: ProcessUpdatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Atualiza status, responsável ou observações de um processo contábil."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    proc = conn.execute(
        "SELECT * FROM office_processes WHERE id = ? AND company_id = ?", (proc_id, company_id)
    ).fetchone()
    if not proc:
        conn.close()
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    fields, values = [], []
    if data.status is not None:
        fields.append("status = ?"); values.append(data.status)
    if data.responsavel is not None:
        fields.append("responsavel = ?"); values.append(data.responsavel)
    if data.observacoes is not None:
        fields.append("observacoes = ?"); values.append(data.observacoes)
    if fields:
        values.append(proc_id)
        conn.execute(f"UPDATE office_processes SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    row = dict(conn.execute("SELECT * FROM office_processes WHERE id = ?", (proc_id,)).fetchone())
    conn.close()
    return row


@router.post("/api/office/processes/{proc_id}/protocolar")
def protocolar_processo(proc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Registra a entrega e gera protocolo digital com hash único para o cliente."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    proc = conn.execute(
        "SELECT * FROM office_processes WHERE id = ? AND company_id = ?", (proc_id, company_id)
    ).fetchone()
    if not proc:
        conn.close()
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    now_iso = datetime.now().isoformat(timespec="seconds")
    raw = f"{company_id}:{proc_id}:{proc['competencia']}:{proc['obrigacao']}:{now_iso}"
    proto_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    conn.execute(
        "UPDATE office_processes SET status = 'protocolado', entregue_em = ?, protocolo_hash = ? WHERE id = ?",
        (now_iso, proto_hash, proc_id),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM office_processes WHERE id = ?", (proc_id,)).fetchone())
    conn.close()
    return row


@router.post("/api/office/processes/{proc_id}/confirmar-leitura")
def confirmar_leitura_processo(proc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Registra a confirmação de leitura/recebimento pelo cliente no Protocolo Digital."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    proc = conn.execute(
        "SELECT * FROM office_processes WHERE id = ? AND company_id = ?", (proc_id, company_id)
    ).fetchone()
    if not proc:
        conn.close()
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    now_iso = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE office_processes SET status = 'confirmado_cliente', confirmado_cliente_em = ? WHERE id = ?",
        (now_iso, proc_id),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM office_processes WHERE id = ?", (proc_id,)).fetchone())
    conn.close()
    return row


@router.get("/api/office/cnds")
def list_company_cnds(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Monitoramento de CNDs da empresa com cálculo automático de dias para vencer e alertas."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT * FROM company_cnds WHERE company_id = ? ORDER BY data_validade ASC, id DESC",
        (company_id,),
    ).fetchall())
    conn.close()
    today = date.today()
    for r in rows:
        try:
            val_dt = date.fromisoformat(str(r.get("data_validade") or "")[:10])
            dias = (val_dt - today).days
        except Exception:
            dias = 0
        r["dias_para_vencer"] = dias
        r["status_alerta"] = "vencida" if dias < 0 else ("vencendo" if dias <= 15 else "regular")
    return rows


@router.post("/api/office/cnds", status_code=201)
def create_company_cnd(
    data: CndCreatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Cadastra uma Certidão Negativa de Débitos (CND) no monitoramento."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO company_cnds
            (company_id, tipo, orgao_emissor, numero_certidao, codigo_controle, data_emissao, data_validade, situacao, observacoes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id, data.tipo, data.orgao_emissor, data.numero_certidao,
        data.codigo_controle, data.data_emissao, data.data_validade,
        data.situacao, data.observacoes,
    ))
    cid = cur.lastrowid
    conn.commit()
    row = dict(conn.execute("SELECT * FROM company_cnds WHERE id = ?", (cid,)).fetchone())
    conn.close()
    today = date.today()
    try:
        dias = (date.fromisoformat(row["data_validade"][:10]) - today).days
    except Exception:
        dias = 0
    row["dias_para_vencer"] = dias
    row["status_alerta"] = "vencida" if dias < 0 else ("vencendo" if dias <= 15 else "regular")
    return row


@router.delete("/api/office/cnds/{cnd_id}")
def delete_company_cnd(cnd_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Remove uma CND cadastrada."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("DELETE FROM company_cnds WHERE id = ? AND company_id = ?", (cnd_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}
