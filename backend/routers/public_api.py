from datetime import date
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from typing import Dict, Any, List, Optional
import json

try:
    from ..database import get_conn
    from ..utils import rows_to_dicts
    from ..routers.sales import _process_sale_billing
    from ..services.webhook_dispatcher import WebhookDispatcher
except ImportError:
    from database import get_conn
    from utils import rows_to_dicts
    from routers.sales import _process_sale_billing
    from services.webhook_dispatcher import WebhookDispatcher

router = APIRouter(prefix="/api/v1", tags=["API Pública v1 (E-commerce & Marketplaces)"])


def get_api_key_company(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Valida a chave de API fornecida no Header X-API-Key ou Authorization Bearer."""
    api_key = x_api_key
    if not api_key and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            api_key = parts[1]

    if not api_key:
        raise HTTPException(status_code=401, detail="Chave de API ausente. Forneça o header 'X-API-Key'.")

    conn = get_conn()
    row = conn.execute("SELECT * FROM api_keys WHERE api_key = ? AND active = 1", (api_key,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=403, detail="Chave de API inválida ou revogada.")

    return {"company_id": row["company_id"], "key_name": row["name"]}


# ==========================================
# 1. CATÁLOGO & ESTOQUE PARA E-COMMERCE
# ==========================================
@router.get("/products")
def get_products_catalog(auth: Dict[str, Any] = Depends(get_api_key_company)):
    """Retorna produtos ativos com SKU, estoque disponível e preço de venda para e-commerce."""
    conn = get_conn()
    company_id = auth["company_id"]
    rows = rows_to_dicts(conn.execute("""
        SELECT id, sku, barcode, name, unit, sale_price, stock_qty, min_stock, active
        FROM products
        WHERE company_id = ? AND active = 1
        ORDER BY name ASC
    """, (company_id,)).fetchall())
    conn.close()
    return {"total": len(rows), "products": rows}


# ==========================================
# 2. SINCRONIZAÇÃO EM LOTE DE ESTOQUE
# ==========================================
@router.post("/inventory/sync")
async def sync_inventory_bulk(req: Request, auth: Dict[str, Any] = Depends(get_api_key_company)):
    """Atualização em lote de estoque por SKU vinda de plataformas externas."""
    items = await req.json()
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="O corpo da requisição deve ser uma lista de itens com 'sku' e 'stock'.")

    conn = get_conn()
    cur = conn.cursor()
    company_id = auth["company_id"]
    updated_count = 0
    updated_skus = []

    for it in items:
        sku = str(it.get("sku") or "").strip()
        stock = float(it.get("stock") or 0.0)
        if not sku:
            continue

        prod = cur.execute("SELECT id, stock_qty, cost_price, average_cost FROM products WHERE sku = ? AND company_id = ?", (sku, company_id)).fetchone()
        if prod:
            prev_s = float(prod["stock_qty"] or 0.0)
            avg_c = float(prod["average_cost"] or prod["cost_price"] or 0.0)
            cur.execute("UPDATE products SET stock_qty = ? WHERE id = ?", (stock, prod["id"]))
            cur.execute("""
                INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
                VALUES (?, 'ajuste_inventario', ?, ?, ?, ?, 'API-SYNC', 'Sincronização externa de estoque via API v1')
            """, (prod["id"], abs(stock - prev_s), avg_c, prev_s, stock))
            updated_count += 1
            updated_skus.append(sku)

    conn.commit()
    conn.close()

    # Dispara webhook se configurado
    await WebhookDispatcher.dispatch_event("inventory.updated", {"updated_count": updated_count, "skus": updated_skus}, company_id=company_id)

    return {"status": "ok", "updated_count": updated_count, "skus": updated_skus}


# ==========================================
# 3. CRIAÇÃO DE PEDIDO DE VENDA VIA E-COMMERCE
# ==========================================
@router.post("/orders")
async def create_external_order(req: Request, auth: Dict[str, Any] = Depends(get_api_key_company)):
    """
    Recebe pedido de venda originado no e-commerce ou marketplace:
    1. Localiza ou cadastra o cliente automaticamente.
    2. Registra o pedido de venda.
    3. Dá baixa imediata no estoque e gera contas a receber.
    4. Notifica via Webhook.
    """
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    company_id = auth["company_id"]

    cust = data.get("customer") or {}
    cust_doc = str(cust.get("document") or "").strip()
    cust_name = str(cust.get("name") or "Cliente E-commerce").strip()

    contact_id = None
    if cust_doc:
        existing = cur.execute("SELECT id FROM contacts WHERE document = ? AND company_id = ?", (cust_doc, company_id)).fetchone()
        if existing:
            contact_id = existing["id"]

    if not contact_id:
        cur.execute("""
            INSERT INTO contacts (company_id, type, name, document, email, phone, street, number, neighborhood, city, state, cep)
            VALUES (?, 'cliente', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id, cust_name, cust_doc or "000.000.000-00",
            cust.get("email", ""), cust.get("phone", ""), cust.get("street", ""),
            cust.get("number", "S/N"), cust.get("neighborhood", "Centro"),
            cust.get("city", "Cuiabá"), cust.get("state", "MT"), cust.get("cep", "78000-000")
        ))
        contact_id = cur.lastrowid

    next_num = (cur.execute("SELECT MAX(number) FROM sales WHERE company_id = ?", (company_id,)).fetchone()[0] or 1000) + 1
    items_raw = data.get("items", [])
    if not items_raw:
        conn.close()
        raise HTTPException(status_code=400, detail="O pedido deve conter pelo menos 1 item.")

    calc_subtotal = 0.0
    items_processed = []

    for it in items_raw:
        sku = it.get("sku")
        pid = it.get("product_id")
        qty = float(it.get("quantity") or 1.0)
        u_p = float(it.get("unit_price") or 0.0)

        p_row = None
        if sku:
            p_row = cur.execute("SELECT id, name, sale_price FROM products WHERE sku = ? AND company_id = ?", (sku, company_id)).fetchone()
        elif pid:
            p_row = cur.execute("SELECT id, name, sale_price FROM products WHERE id = ? AND company_id = ?", (pid, company_id)).fetchone()

        p_name = p_row["name"] if p_row else (it.get("name") or "Produto")
        prod_id = p_row["id"] if p_row else pid
        if u_p <= 0 and p_row:
            u_p = float(p_row["sale_price"])

        tot = round(qty * u_p, 2)
        calc_subtotal += tot
        items_processed.append({"product_id": prod_id, "name": p_name, "quantity": qty, "unit_price": u_p, "total": tot})

    shipping = float(data.get("shipping_amount") or 0.0)
    discount = float(data.get("discount_amount") or 0.0)
    total_order = max(0.0, round(calc_subtotal + shipping - discount, 2))
    pay_method = data.get("payment_method", "Cartão de Crédito")
    notes = f"Pedido originado via API / {auth['key_name']}. {data.get('notes', '')}".strip()

    cur.execute("""
        INSERT INTO sales (
            company_id, number, sale_type, status, contact_id, seller_name, sale_date,
            subtotal, discount_amount, shipping_amount, total_amount, payment_method, notes
        ) VALUES (?, ?, 'venda', 'aprovada', ?, 'Integração E-commerce', ?, ?, ?, ?, ?, ?, ?)
    """, (company_id, next_num, contact_id, date.today().isoformat(), calc_subtotal, discount, shipping, total_order, pay_method, notes))
    sale_id = cur.lastrowid

    for it in items_processed:
        cur.execute("""
            INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
            VALUES (?, ?, ?, 'PRD', 'UN', ?, ?, 0.0, ?)
        """, (sale_id, it["product_id"], it["name"], it["quantity"], it["unit_price"], it["total"]))

    conn.commit()

    # Efetiva baixa de estoque e faturamento no contas a receber
    _process_sale_billing(conn, sale_id, immediate_paid=True, company_id=company_id)

    # Dispara Webhook Assíncrono
    event_payload = {
        "order_id": sale_id,
        "order_number": next_num,
        "total_amount": total_order,
        "customer": {"name": cust_name, "document": cust_doc},
        "items": items_processed
    }
    await WebhookDispatcher.dispatch_event("order.created", event_payload, company_id=company_id)

    # Notificação interna
    cur.execute("""
        INSERT INTO notifications (company_id, title, message, type, link)
        VALUES (?, ?, ?, 'success', ?)
    """, (
        company_id,
        f"Novo Pedido de E-commerce #{next_num}",
        f"Venda no valor de R$ {total_order:,.2f} recebida via API ({cust_name}).",
        f"/sales"
    ))
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "order_id": sale_id,
        "order_number": next_num,
        "total_amount": total_order,
        "message": f"Pedido #{next_num} criado e faturado com sucesso!"
    }


# ==========================================
# 4. CONSULTA DE STATUS DO PEDIDO
# ==========================================
@router.get("/orders/{order_id}")
def get_order_status(order_id: int, auth: Dict[str, Any] = Depends(get_api_key_company)):
    """Consulta detalhes, faturamento e chave de NF-e do pedido."""
    conn = get_conn()
    company_id = auth["company_id"]
    row = conn.execute("""
        SELECT s.*, c.name as customer_name, c.document as customer_doc,
               inv.access_key as invoice_access_key, inv.status as invoice_status, inv.protocol as invoice_protocol
        FROM sales s
        LEFT JOIN contacts c ON c.id = s.contact_id
        LEFT JOIN invoices inv ON inv.id = s.invoice_id
        WHERE s.id = ? AND s.company_id = ?
    """, (order_id, company_id)).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    order_dict = dict(row)
    order_dict["items"] = rows_to_dicts(conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (order_id,)).fetchall())
    conn.close()
    return order_dict
