import io
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
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.invoices import InvoiceEmitRequest, InvoiceCancelRequest, InvoiceCceRequest
    from fiscal_engine import gerar_chave_acesso_sefaz, validar_dados_fiscais, gerar_xml_nfe_400, gerar_html_danfe

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
    protocolo = f"151{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10,99)}"
    total_pis = round(total_products * 0.0065, 2)
    total_cofins = round(total_products * 0.03, 2)
    total_iss = round(total_products * 0.03, 2) if model_str == "NFSe" else 0.0

    inv_meta = {
        "model": model_str,
        "series": serie,
        "number": numero,
        "access_key": chave,
        "protocol": protocolo,
        "nature_operation": nature_op,
        "total_products": total_products,
        "total_discounts": total_discounts,
        "total_shipping": total_shipping,
        "total_pis": total_pis,
        "total_cofins": total_cofins,
        "total_iss": total_iss,
        "total_invoice": total_invoice,
    }
    xml_str = gerar_xml_nfe_400(company, contact, sale_items, inv_meta)

    cur.execute("""
        INSERT INTO invoices (
            model, series, number, access_key, protocol, status, environment,
            nature_operation, sale_id, contact_id, recipient_name, recipient_doc,
            recipient_uf, total_products, total_discounts, total_shipping,
            total_pis, total_cofins, total_iss, total_invoice, items_json, xml_content
        ) VALUES (?, ?, ?, ?, ?, 'autorizada', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        total_pis,
        total_cofins,
        total_iss,
        total_invoice,
        json.dumps(sale_items, ensure_ascii=False),
        xml_str,
    ))
    inv_id = cur.lastrowid
    if sale_id:
        cur.execute("UPDATE sales SET invoice_id = ? WHERE id = ?", (inv_id, sale_id))

    conn.commit()
    log_audit(conn, action="emit_invoice", entity="invoices", entity_id=inv_id, new_data={"number": numero, "chave": chave}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "invoice_id": inv_id,
        "number": numero,
        "access_key": chave,
        "protocol": protocolo,
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
    conn.execute("UPDATE invoices SET correction_letter = ? WHERE id = ?", (texto, invoice_id))
    conn.commit()
    log_audit(conn, action="cce", entity="invoices", entity_id=invoice_id, new_data={"text": texto}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Carta de Correção Eletrônica (CC-e) averbada na nota fiscal!"}


@router.post("/{invoice_id}/cancel")
async def cancel_invoice(invoice_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    reason = (data.get("reason") or "").strip()
    if len(reason) < 15:
        raise HTTPException(status_code=400, detail="A justificativa de cancelamento na SEFAZ deve conter pelo menos 15 caracteres.")
    conn = get_conn()
    conn.execute("UPDATE invoices SET status = 'cancelada', cancel_reason = ? WHERE id = ?", (reason, invoice_id))
    conn.commit()
    log_audit(conn, action="cancel_invoice", entity="invoices", entity_id=invoice_id, new_data={"reason": reason}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Nota Fiscal cancelada e evento registrado."}
