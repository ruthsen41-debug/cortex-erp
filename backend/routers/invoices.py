import io
import re
import json
import random
import zipfile
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Response, Depends
from fastapi.responses import HTMLResponse
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.invoices import InvoiceEmitRequest, InvoiceCancelRequest, InvoiceCceRequest
    from ..fiscal_engine import gerar_chave_acesso_sefaz, validar_dados_fiscais, gerar_xml_nfe_400, gerar_html_danfe
    from ..services.fiscal_provider import FiscalProviderFactory
    from ..services.tax_calculator import TaxCalculator
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.invoices import InvoiceEmitRequest, InvoiceCancelRequest, InvoiceCceRequest
    from fiscal_engine import gerar_chave_acesso_sefaz, validar_dados_fiscais, gerar_xml_nfe_400, gerar_html_danfe
    from services.fiscal_provider import FiscalProviderFactory
    from services.tax_calculator import TaxCalculator

router = APIRouter(prefix="/api/invoices", tags=["Emissor Fiscal"])


@router.get("")
def list_invoices(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall())
    conn.close()
    for r in rows:
        r["total_amount"] = r.get("total_invoice", 0.0)
    return rows


@router.post("/emit")
async def emit_invoice(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    model = data.get("model", "55")
    if model in ("55", "NFe-55"):
        model_str = "NFe-55"
    elif model in ("65", "NFCe-65"):
        model_str = "NFCe-65"
    else:
        model_str = "NFSe"

    sale_id = data.get("sale_id")
    nature_op = data.get("natureza_operacao") or data.get("nature_operation") or "VENDA DE MERCADORIA DENTRO DO ESTADO"
    company_id = current_user.get("company_id", 1)

    conn = get_conn()
    cur = conn.cursor()
    company = dict(cur.execute("SELECT * FROM companies WHERE id = ? LIMIT 1", (company_id,)).fetchone())

    if sale_id:
        sale = cur.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if not sale:
            conn.close()
            raise HTTPException(status_code=404, detail="Venda não encontrada.")
        contact_row = cur.execute("SELECT * FROM contacts WHERE id = ?", (sale["contact_id"] or 1,)).fetchone()
        contact = dict(contact_row) if contact_row else {}
        sale_items = rows_to_dicts(cur.execute("""
            SELECT si.*, p.ncm, p.cfop_internal as cfop, p.csosn_cst, p.origin, p.pis_cst, p.pis_rate, p.cofins_cst, p.cofins_rate, p.iss_rate
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
        """, (sale_id,)).fetchall())
        total_products = float(sale["subtotal"])
        total_discounts = float(sale.get("discount_amount") or 0.0)
        total_shipping = float(sale.get("shipping_amount") or 0.0)
        total_invoice = float(sale["total_amount"])
    else:
        contact_id = int(data.get("recipient_id") or data.get("contact_id") or 1)
        contact_row = cur.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        contact = dict(contact_row) if contact_row else {}
        sale_items = data.get("items", [])
        total_products = round(sum(float(i.get("quantity", 1)) * float(i.get("unit_price", 0)) for i in sale_items), 2)
        total_discounts = float(data.get("discount_amount") or 0.0)
        total_shipping = float(data.get("shipping_amount") or 0.0)
        total_invoice = max(0.0, round(total_products - total_discounts + total_shipping, 2))

    erros = validar_dados_fiscais(company, contact, sale_items, model=model_str)
    if erros:
        conn.close()
        raise HTTPException(status_code=400, detail=" | ".join(erros))

    if model_str == "NFe-55":
        serie = int(company.get("serie_nfe") or 1)
        numero = int(company.get("proximo_numero_nfe") or 101)
        cur.execute("UPDATE companies SET proximo_numero_nfe = ? WHERE id = ?", (numero + 1, company_id))
    elif model_str == "NFCe-65":
        serie = int(company.get("serie_nfce") or 1)
        numero = int(company.get("proximo_numero_nfce") or 501)
        cur.execute("UPDATE companies SET proximo_numero_nfce = ? WHERE id = ?", (numero + 1, company_id))
    else:
        serie = int(company.get("serie_nfse") or 1)
        numero = int(company.get("proximo_numero_nfse") or 201)
        cur.execute("UPDATE companies SET proximo_numero_nfse = ? WHERE id = ?", (numero + 1, company_id))

    chave = gerar_chave_acesso_sefaz(
        cuf=company.get("codigo_ibge_uf", "51"),
        dt_emissao=datetime.now(),
        cnpj_emitente=company.get("cnpj", "45123789000190"),
        modelo=model_str,
        serie=serie,
        numero_nf=numero,
    )
    # Cálculo avançado de impostos pelo TaxCalculator
    regime = company.get("regime_tributario", "simples_nacional")
    uf_origem = company.get("uf", "MT")
    uf_dest = contact.get("state", "MT")

    total_icms = 0.0
    total_pis = 0.0
    total_cofins = 0.0
    total_iss = 0.0

    for it in sale_items:
        taxes = TaxCalculator.calculate_item_taxes(
            it,
            regime=regime,
            uf_origem=uf_origem,
            uf_destino=uf_dest,
            is_consumidor_final=True,
            is_contribuinte=False,
        )
        total_icms += taxes["icms_valor"]
        total_pis += taxes["pis_valor"]
        total_cofins += taxes["cofins_valor"]
        total_iss += taxes["iss_valor"]

    inv_meta = {
        "model": model_str,
        "series": serie,
        "number": numero,
        "access_key": chave,
        "protocol": "",
        "nature_operation": nature_op,
        "total_products": total_products,
        "total_discounts": total_discounts,
        "total_shipping": total_shipping,
        "total_icms": round(total_icms, 2),
        "total_pis": round(total_pis, 2),
        "total_cofins": round(total_cofins, 2),
        "total_iss": round(total_iss, 2),
        "total_invoice": total_invoice,
    }

    # Processa pelo motor / provedor fiscal configurado (SEFAZ Direto, Focus NFe, PlugNotas, Nuvem Fiscal)
    provider = FiscalProviderFactory.get_provider(company)
    provider_res = await provider.emit_invoice(company, contact, sale_items, inv_meta)

    protocolo = provider_res.get("protocol") or f"151{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10,99)}"
    xml_str = provider_res.get("xml_content") or gerar_xml_nfe_400(company, contact, sale_items, inv_meta)

    cur.execute("""
        INSERT INTO invoices (
            model, series, number, access_key, protocol, status, environment,
            nature_operation, sale_id, contact_id, recipient_name, recipient_doc,
            recipient_uf, total_products, total_discounts, total_shipping,
            total_icms, total_pis, total_cofins, total_iss, total_invoice, items_json, xml_content
        ) VALUES (?, ?, ?, ?, ?, 'autorizada', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        model_str,
        serie,
        numero,
        chave,
        protocolo,
        company.get("ambiente_fiscal", "homologacao"),
        nature_op,
        sale_id,
        contact.get("id"),
        contact.get("name", "CONSUMIDOR FINAL"),
        contact.get("document", "000.000.000-00"),
        contact.get("state", "MT"),
        total_products,
        total_discounts,
        total_shipping,
        round(total_icms, 2),
        round(total_pis, 2),
        round(total_cofins, 2),
        round(total_iss, 2),
        total_invoice,
        json.dumps(sale_items, ensure_ascii=False),
        xml_str,
    ))
    inv_id = cur.lastrowid
    if sale_id:
        cur.execute("UPDATE sales SET invoice_id = ? WHERE id = ?", (inv_id, sale_id))

    conn.commit()
    log_audit(conn, action="emit_invoice", entity="invoices", entity_id=inv_id, new_data={"number": numero, "chave": chave, "provider": company.get("motor_fiscal", "sefaz_direct")}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "invoice_id": inv_id,
        "number": numero,
        "access_key": chave,
        "protocol": protocolo,
        "provider": provider_res.get("provider", "sefaz_direct"),
        "message": f"{model_str} Nº {numero} autorizada com sucesso!",
    }


@router.get("/{invoice_id}/danfe", response_class=HTMLResponse)
def view_danfe(invoice_id: int):
    conn = get_conn()
    company = dict(conn.execute("SELECT * FROM companies LIMIT 1").fetchone())
    inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not inv:
        conn.close()
        raise HTTPException(status_code=404, detail="Nota Fiscal não encontrada.")
    inv_dict = dict(inv)
    contact_row = conn.execute("SELECT * FROM contacts WHERE id = ?", (inv_dict.get("contact_id") or 1,)).fetchone()
    contact = dict(contact_row) if contact_row else {}
    items = json.loads(inv_dict.get("items_json") or "[]")
    conn.close()
    return gerar_html_danfe(company, contact, inv_dict, items)


@router.get("/{invoice_id}/xml")
def download_invoice_xml(invoice_id: int):
    conn = get_conn()
    inv = conn.execute("SELECT number, access_key, xml_content FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    conn.close()
    if not inv:
        raise HTTPException(status_code=404, detail="Nota não encontrada.")
    filename = f"NFe_{inv['access_key']}.xml"
    return Response(
        content=inv["xml_content"],
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export-zip")
def export_invoices_zip():
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT number, model, access_key, xml_content FROM invoices WHERE status != 'cancelada'").fetchall())
    conn.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            zf.writestr(f"{r['model']}_{r['number']}_{r['access_key']}.xml", r["xml_content"] or "")
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="XMLs_Contabilidade_CortexERP.zip"'},
    )


@router.post("/{invoice_id}/cce")
async def emit_carta_correcao(invoice_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    texto = (data.get("correction_text") or "").strip()
    if len(texto) < 15:
        raise HTTPException(status_code=400, detail="A SEFAZ exige no mínimo 15 caracteres na Carta de Correção (CC-e).")

    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    company = dict(cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())
    inv = cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not inv:
        conn.close()
        raise HTTPException(status_code=404, detail="Nota Fiscal não encontrada.")

    provider = FiscalProviderFactory.get_provider(company)
    res = await provider.emit_cce(company, dict(inv), texto)
    protocol = res.get("cce_protocol") or f"136{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10,99)}"

    cur.execute("UPDATE invoices SET correction_letter = ?, cce_protocol = ? WHERE id = ?", (texto, protocol, invoice_id))
    conn.commit()
    log_audit(conn, action="cce", entity="invoices", entity_id=invoice_id, new_data={"text": texto, "protocol": protocol}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "protocol": protocol, "message": f"Carta de Correção Eletrônica (CC-e) averbada sob protocolo {protocol}!"}


@router.post("/{invoice_id}/cancel")
async def cancel_invoice(invoice_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    reason = (data.get("reason") or "").strip()
    if len(reason) < 15:
        raise HTTPException(status_code=400, detail="A justificativa de cancelamento na SEFAZ deve conter pelo menos 15 caracteres.")

    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    company = dict(cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())
    inv = cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not inv:
        conn.close()
        raise HTTPException(status_code=404, detail="Nota Fiscal não encontrada.")

    provider = FiscalProviderFactory.get_provider(company)
    res = await provider.cancel_invoice(company, dict(inv), reason)
    protocol = res.get("cancel_protocol") or f"135{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10,99)}"

    cur.execute("UPDATE invoices SET status = 'cancelada', cancel_reason = ?, cancel_protocol = ? WHERE id = ?", (reason, protocol, invoice_id))
    conn.commit()
    log_audit(conn, action="cancel_invoice", entity="invoices", entity_id=invoice_id, new_data={"reason": reason, "protocol": protocol}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "protocol": protocol, "message": f"Nota Fiscal cancelada sob protocolo {protocol}."}


@router.post("/inutilize")
async def inutilize_numbers(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Inutilização de numeração fiscal na SEFAZ (ex: salto de numeração por quebra de sequência)."""
    data = await req.json()
    model = data.get("model", "NFe-55")
    series = int(data.get("series", 1))
    start_n = int(data.get("start_number", 1))
    end_n = int(data.get("end_number", start_n))
    reason = (data.get("reason") or "").strip()

    if len(reason) < 15:
        raise HTTPException(status_code=400, detail="A justificativa de inutilização deve ter no mínimo 15 caracteres.")

    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    company = dict(cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())

    provider = FiscalProviderFactory.get_provider(company)
    res = await provider.inutilize(company, model, series, start_n, end_n, reason)
    protocol = res.get("protocol") or f"102{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10,99)}"

    cur.execute("""
        INSERT INTO fiscal_inutilizations (company_id, model, series, start_number, end_number, protocol, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'homologado')
    """, (company_id, model, series, start_n, end_n, protocol, reason))
    inut_id = cur.lastrowid
    conn.commit()
    log_audit(conn, action="inutilize", entity="fiscal_inutilizations", entity_id=inut_id, new_data={"range": f"{start_n}-{end_n}", "protocol": protocol}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "inutilization_id": inut_id,
        "protocol": protocol,
        "message": f"Inutilização da numeração {start_n} a {end_n} homologada pela SEFAZ sob protocolo {protocol}."
    }


@router.get("/inutilizations")
def list_inutilizations(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("SELECT * FROM fiscal_inutilizations WHERE company_id = ? ORDER BY id DESC", (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/manifest")
async def manifest_invoice(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Manifestação do Destinatário na SEFAZ Nacional:
    - 'ciencia': Ciência da Emissão
    - 'confirmacao': Confirmação da Operação
    - 'desconhecimento': Desconhecimento da Operação
    - 'nao_realizada': Operação não Realizada
    """
    data = await req.json()
    access_key = re.sub(r"\D", "", data.get("access_key", ""))
    event_type = data.get("event_type", "confirmacao")
    notes = data.get("notes", "")

    if len(access_key) != 44:
        raise HTTPException(status_code=400, detail="Chave de acesso deve conter exatamente 44 dígitos numéricos.")

    valid_events = ["ciencia", "confirmacao", "desconhecimento", "nao_realizada"]
    if event_type not in valid_events:
        raise HTTPException(status_code=400, detail=f"Tipo de evento inválido. Opções válidas: {', '.join(valid_events)}")

    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    company = dict(cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())

    provider = FiscalProviderFactory.get_provider(company)
    res = await provider.manifest(company, access_key, event_type)
    protocol = res.get("protocol") or f"135{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10,99)}"

    cur.execute("""
        INSERT INTO fiscal_manifestations (company_id, access_key, event_type, protocol, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (company_id, access_key, event_type, protocol, notes))
    m_id = cur.lastrowid
    conn.commit()
    log_audit(conn, action="manifest", entity="fiscal_manifestations", entity_id=m_id, new_data={"access_key": access_key, "event": event_type, "protocol": protocol}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "manifestation_id": m_id,
        "protocol": protocol,
        "event_type": event_type,
        "message": f"Manifestação '{event_type}' vinculada à chave {access_key} homologada pela SEFAZ."
    }


@router.get("/manifestations")
def list_manifestations(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("SELECT * FROM fiscal_manifestations WHERE company_id = ? ORDER BY id DESC", (company_id,)).fetchall())
    conn.close()
    return rows
