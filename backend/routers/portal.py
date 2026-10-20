from datetime import date
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Dict, Any, Optional

try:
    from ..database import get_conn
    from ..utils import rows_to_dicts
    from ..services.payment_gateway import PaymentGatewayService
    from .sales import _process_sale_billing
except ImportError:
    from database import get_conn
    from utils import rows_to_dicts
    from services.payment_gateway import PaymentGatewayService
    from routers.sales import _process_sale_billing

router = APIRouter(prefix="/api/portal", tags=["Portal do Cliente"])


@router.get("/quote/{token}")
def get_quote_by_token(token: str):
    """Visualização pública e segura do orçamento para o cliente final."""
    conn = get_conn()
    cur = conn.cursor()

    sale = cur.execute("""
        SELECT s.*, c.name as client_name, c.document as client_doc, c.email as client_email, c.phone as client_phone,
               comp.razao_social as company_name, comp.cnpj as company_cnpj, comp.telefone as company_phone, comp.email as company_email
        FROM sales s
        LEFT JOIN contacts c ON c.id = s.contact_id
        LEFT JOIN companies comp ON comp.id = s.company_id
        WHERE s.token_access = ? OR CAST(s.id AS TEXT) = ?
        LIMIT 1
    """, (token, token)).fetchone()

    if not sale:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado ou token inválido.")

    items = rows_to_dicts(cur.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale["id"],)).fetchall())
    conn.close()

    sale_dict = dict(sale)
    sale_dict["items"] = items
    return sale_dict


@router.post("/quote/{token}/accept")
async def accept_quote_by_token(token: str):
    """
    Aprovação online do orçamento pelo cliente via Portal do Cliente:
    1. Transforma o orçamento em venda aprovada/faturada.
    2. Dá baixa no estoque e gera lançamentos no Contas a Receber.
    3. Gera cobrança Pix imediata para o cliente pagar na hora.
    """
    conn = get_conn()
    cur = conn.cursor()

    sale = cur.execute("""
        SELECT * FROM sales
        WHERE token_access = ? OR CAST(id AS TEXT) = ?
        LIMIT 1
    """, (token, token)).fetchone()

    if not sale:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")

    sale_id = sale["id"]
    company_id = sale["company_id"] or 1

    # Atualiza status e fatura
    if sale["status"] == "orcamento":
        _process_sale_billing(conn, sale_id, immediate_paid=False, company_id=company_id)
        cur.execute("UPDATE sales SET status = 'aprovada' WHERE id = ?", (sale_id,))
        conn.commit()

    # Busca a primeira parcela no contas a receber para gerar cobrança Pix
    entry = cur.execute("""
        SELECT id FROM financial_entries
        WHERE origin_type IN ('orcamento', 'venda') AND origin_id = ?
        ORDER BY installment_number ASC LIMIT 1
    """, (sale_id,)).fetchone()

    payment_info = None
    if entry:
        try:
            payment_info = await PaymentGatewayService.create_charge(entry["id"], billing_type="PIX", company_id=company_id)
        except Exception as e:
            payment_info = {"error": str(e)}

    conn.close()

    return {
        "status": "accepted",
        "sale_id": sale_id,
        "number": sale["number"],
        "message": "Orçamento aprovado com sucesso! Obrigado pela preferência.",
        "payment": payment_info
    }


@router.get("/invoice/{token}")
async def get_invoice_portal(token: str):
    """Consulta de fatura e pagamento online via token público."""
    conn = get_conn()
    cur = conn.cursor()

    sale = cur.execute("""
        SELECT s.*, c.name as client_name, c.document as client_doc
        FROM sales s
        LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE s.token_access = ? OR CAST(s.id AS TEXT) = ?
        LIMIT 1
    """, (token, token)).fetchone()

    if not sale:
        conn.close()
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")

    sale_id = sale["id"]
    entries = rows_to_dicts(cur.execute("""
        SELECT * FROM financial_entries
        WHERE origin_id = ? AND origin_type IN ('orcamento', 'venda')
        ORDER BY installment_number ASC
    """, (sale_id,)).fetchall())

    # Se houver títulos pendentes, obtém ou cria cobrança
    charges = []
    for e in entries:
        ch = cur.execute("SELECT * FROM payment_charges WHERE entry_id = ?", (e["id"],)).fetchone()
        if ch:
            charges.append(dict(ch))
        else:
            try:
                new_ch = await PaymentGatewayService.create_charge(e["id"], billing_type="PIX", company_id=sale["company_id"] or 1)
                charges.append(new_ch)
            except Exception:
                pass

    conn.close()

    return {
        "sale": dict(sale),
        "entries": entries,
        "charges": charges
    }
