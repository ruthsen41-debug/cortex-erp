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
