import io
import json
import zipfile
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Response
from typing import Dict, Any, Optional

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
    from ..services.sped_generator import SpedFiscalGenerator
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts
    from services.sped_generator import SpedFiscalGenerator

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
    conn.close()

    sped_content = SpedFiscalGenerator.generate(company, invoices, s_date, e_date)
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

    sped_txt = SpedFiscalGenerator.generate(company, invoices, s_date, e_date)

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
    """Gera arquivo EFD Contribuições (layout simplificado PIS/COFINS)."""
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
    conn.close()
    cnpj = (company.get("cnpj") or "").replace(".","").replace("/","").replace("-","")
    dt_ini = s_date.replace("-","")
    dt_fin = e_date.replace("-","")
    lines = [
        f"|0000|{company.get('regime_tributario','1').upper()[:1]}|{dt_ini}|{dt_fin}|{company.get('razao_social','')}|{cnpj}|{company.get('uf','MT')}||A|1|",
        f"|0001|1|",
        f"|0140|{cnpj}|{company.get('razao_social','')}|||{company.get('uf','MT')}|||",
        f"|0990|3|",
        f"|A001|0|",
        f"|A990|2|",
        f"|C001|1|",
    ]
    for inv in invoices:
        chave = inv.get("chave_nfe","")[:44] or "0"*44
        num = str(inv.get("number",""))
        dt = (inv.get("issued_at") or s_date)[:10].replace("-","")
        total = f"{float(inv.get('total_invoice',0)):.2f}".replace(".",",")
        pis = f"{float(inv.get('total_pis',0)):.2f}".replace(".",",")
        cof = f"{float(inv.get('total_cofins',0)):.2f}".replace(".",",")
        lines.append(f"|C100|1|1|{chave}|55|{num}|{dt}|{dt}|{total}|0|0|0|0|0|")
        lines.append(f"|C170|1|{inv.get('items','')}|1,00|UN|{total}|0|0|49|0||")
        lines.append(f"|C190|5929|{total}|0,00|0,00|0,00|0,00|")
        if float(inv.get("total_pis",0)):
            lines.append(f"|C500||{pis}|1,65|")
        if float(inv.get("total_cofins",0)):
            lines.append(f"|C600||{cof}|7,60|")
    lines += [
        f"|C990|{len([l for l in lines if l.startswith('|C')])+1}|",
        f"|D001|1|",
        f"|D990|2|",
        f"|F001|1|",
        f"|F990|2|",
        f"|I001|1|",
        f"|I990|2|",
        f"|M001|1|",
        f"|M990|2|",
        f"|P001|1|",
        f"|P990|2|",
        f"|1001|1|",
        f"|1900|0|0|0,00|0,00|",
        f"|1990|2|",
        f"|9001|1|",
        f"|9999|{len(lines)+4}|",
    ]
    content = "\r\n".join(lines)
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
        WHERE pr.company_id=? AND pr.competencia=?
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
