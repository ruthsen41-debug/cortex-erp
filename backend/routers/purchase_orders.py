from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional

try:
    from ..database import get_conn, begin_write
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.phase3 import PurchaseOrderCreate
except ImportError:
    from database import get_conn, begin_write
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.phase3 import PurchaseOrderCreate

router = APIRouter(prefix="/api/purchase-orders", tags=["Pedidos de Compra & Suprimentos"])


@router.get("")
def list_purchase_orders(status: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = """
        SELECT po.*, c.name as supplier_name, c.document as supplier_cnpj
        FROM purchase_orders po
        LEFT JOIN contacts c ON c.id = po.supplier_id
        WHERE po.company_id = ?
    """
    params = [company_id]
    if status and status != "todos":
        sql += " AND po.status = ?"
        params.append(status)
    sql += " ORDER BY po.id DESC"

    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    for r in rows:
        r["items"] = rows_to_dicts(conn.execute("""
            SELECT poi.*, p.name as product_name, p.sku
            FROM purchase_order_items poi
            JOIN products p ON p.id = poi.product_id
            WHERE poi.order_id = ?
        """, (r["id"],)).fetchall())
    conn.close()
    return rows


@router.post("")
def create_purchase_order(data: PurchaseOrderCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    # Verifica fornecedor
    supplier = cur.execute("SELECT name FROM contacts WHERE id = ? AND company_id = ?", (data.supplier_id, company_id)).fetchone()
    if not supplier:
        conn.close()
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")

    next_num = (cur.execute("SELECT MAX(order_number) FROM purchase_orders WHERE company_id = ?", (company_id,)).fetchone()[0] or 5000) + 1

    calc_subtotal = 0.0
    for it in data.items:
        calc_subtotal += (float(it.quantity) * float(it.unit_price)) - float(it.discount or 0.0)

    cur.execute("""
        INSERT INTO purchase_orders (
            company_id, order_number, supplier_id, status, expected_delivery_date,
            subtotal, total_amount, payment_terms, notes
        ) VALUES (?, ?, ?, 'rascunho', ?, ?, ?, ?, ?)
    """, (
        company_id, next_num, data.supplier_id,
        data.expected_delivery_date or (date.today() + timedelta(days=7)).isoformat(),
        calc_subtotal, calc_subtotal, data.payment_terms or "Boleto 30 dias", data.notes or ""
    ))
    poid = cur.lastrowid

    for it in data.items:
        tot = (float(it.quantity) * float(it.unit_price)) - float(it.discount or 0.0)
        cur.execute("""
            INSERT INTO purchase_order_items (order_id, product_id, quantity, unit_price, discount, total_price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (poid, it.product_id, it.quantity, it.unit_price, it.discount or 0.0, tot))

    conn.commit()
    log_audit(conn, action="create", entity="purchase_orders", entity_id=poid, new_data=data.model_dump(), user_id=current_user.get("id"))
    conn.close()

    return {"status": "ok", "id": poid, "order_number": next_num, "total_amount": calc_subtotal}


@router.get("/{order_id}")
def get_purchase_order(order_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("""
        SELECT po.*, c.name as supplier_name, c.document as supplier_cnpj, c.phone as supplier_phone, c.email as supplier_email
        FROM purchase_orders po
        LEFT JOIN contacts c ON c.id = po.supplier_id
        WHERE po.id = ? AND po.company_id = ?
    """, (order_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Pedido de compra não encontrado.")

    data = dict(row)
    data["items"] = rows_to_dicts(conn.execute("""
        SELECT poi.*, p.name as product_name, p.sku, p.unit
        FROM purchase_order_items poi
        JOIN products p ON p.id = poi.product_id
        WHERE poi.order_id = ?
    """, (order_id,)).fetchall())
    conn.close()
    return data


@router.post("/{order_id}/status")
def update_purchase_order_status(order_id: int, status_update: Dict[str, str], current_user: Dict[str, Any] = Depends(get_current_user)):
    new_status = status_update.get("status")
    if new_status not in ["rascunho", "enviado", "aprovado", "cancelado"]:
        raise HTTPException(status_code=400, detail="Status inválido.")

    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    cur.execute("UPDATE purchase_orders SET status = ? WHERE id = ? AND company_id = ?", (new_status, order_id, company_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Pedido de compra não encontrado.")

    conn.commit()
    log_audit(conn, action="update_status", entity="purchase_orders", entity_id=order_id, new_data={"status": new_status}, user_id=current_user.get("id"))
    conn.close()
    return {"status": new_status, "order_id": order_id}


@router.post("/{order_id}/receive")
def receive_purchase_order(order_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Recebimento de Mercadorias (Check-in de Estoque & Entrada no Contas a Pagar):
    1. Atualiza status para 'recebido' e grava data de recebimento.
    2. Dá entrada no estoque dos produtos e recalcula o custo médio ponderado.
    3. Registra no Kardex (stock_movements).
    4. Gera automaticamente o título no Contas a Pagar (financial_entries).
    """
    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    po = cur.execute("""
        SELECT po.*, c.name as supplier_name
        FROM purchase_orders po
        LEFT JOIN contacts c ON c.id = po.supplier_id
        WHERE po.id = ? AND po.company_id = ?
    """, (order_id, company_id)).fetchone()

    if not po:
        conn.close()
        raise HTTPException(status_code=404, detail="Pedido de compra não encontrado.")

    if po["status"] == "recebido":
        conn.close()
        raise HTTPException(status_code=400, detail="Este pedido de compra já foi recebido anteriormente.")

    items = rows_to_dicts(cur.execute("SELECT * FROM purchase_order_items WHERE order_id = ?", (order_id,)).fetchall())

    today_str = date.today().isoformat()
    supplier_label = po["supplier_name"] or "Fornecedor"

    # 1. Entrada no estoque e recálculo de custo médio
    for it in items:
        pid = it["product_id"]
        qty_in = float(it["quantity"])
        u_price = float(it["unit_price"])

        prod = cur.execute("SELECT stock_qty, average_cost, cost_price FROM products WHERE id = ? AND company_id = ?", (pid, company_id)).fetchone()
        if prod:
            current_qty = float(prod["stock_qty"] or 0.0)
            current_avg = float(prod["average_cost"] or prod["cost_price"] or 0.0)

            # Custo Médio Ponderado
            new_qty = current_qty + qty_in
            if new_qty > 0:
                new_avg = round(((current_qty * current_avg) + (qty_in * u_price)) / new_qty, 2)
            else:
                new_avg = u_price

            cur.execute("""
                UPDATE products
                SET stock_qty = ?, average_cost = ?, cost_price = ?
                WHERE id = ?
            """, (new_qty, new_avg, u_price, pid))

            # Kardex
            cur.execute("""
                INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
                VALUES (?, 'compra', ?, ?, ?, ?, ?, ?)
            """, (pid, qty_in, u_price, current_qty, new_qty, f"PC #{po['order_number']}", f"Recebimento de compra #{po['order_number']} - {supplier_label}"))

    # 2. Gera lançamento financeiro no Contas a Pagar
    due_date = (date.today() + timedelta(days=30)).isoformat()
    total_val = float(po["total_amount"])

    # Localiza categoria de fornecedores ou default 11
    cat_row = cur.execute("SELECT id FROM categories WHERE type = 'despesa' AND name LIKE '%Fornecedor%' LIMIT 1").fetchone()
    cat_id = cat_row["id"] if cat_row else 11

    cur.execute("""
        INSERT INTO financial_entries (
            company_id, type, description, contact_id, category_id, cost_center_id, bank_account_id,
            payment_method, competence_date, due_date, amount, paid_amount, status,
            origin_type, origin_id, notes
        ) VALUES (?, 'despesa', ?, ?, ?, 2, 1, 'Boleto', ?, ?, ?, 0.0, 'pendente', 'pedido_compra', ?, ?)
    """, (
        company_id,
        f"Pedido de Compra #{po['order_number']} - {supplier_label}",
        po["supplier_id"],
        cat_id,
        today_str,
        due_date,
        total_val,
        order_id,
        f"Condições: {po['payment_terms']}"
    ))
    entry_id = cur.lastrowid

    # 3. Marca pedido como recebido
    cur.execute("""
        UPDATE purchase_orders
        SET status = 'recebido', received_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (order_id,))

    conn.commit()
    log_audit(conn, action="receive_order", entity="purchase_orders", entity_id=order_id, new_data={"financial_entry_id": entry_id, "items_received": len(items)}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "message": f"Pedido #{po['order_number']} recebido com sucesso! Estoque atualizado e conta a pagar #{entry_id} gerada.",
        "financial_entry_id": entry_id
    }
