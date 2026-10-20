import re
import random
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Optional, Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.products import ProductCreate, StockAdjustRequest
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.products import ProductCreate, StockAdjustRequest

router = APIRouter(tags=["Produtos & Estoque"])


@router.get("/api/products")
def list_products(type: Optional[str] = None, q: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = "SELECT * FROM products WHERE active = 1"
    params = []
    if type and type != "todos":
        sql += " AND type = ?"
        params.append(type)
    if q:
        sql += " AND (name LIKE ? OR sku LIKE ? OR barcode LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " ORDER BY name ASC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()

    # Aliases para compatibilidade total com o front-end
    for r in rows:
        r["stock_current"] = r.get("stock_qty", 0.0)
        r["stock_min"] = r.get("min_stock", 5.0)

    return rows


@router.post("/api/products")
async def save_product(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    pid = data.get("id")
    cost = float(data.get("cost_price") or 0.0)
    sale = float(data.get("sale_price") or 0.0)
    margin = round(((sale - cost) / cost) * 100.0, 2) if cost > 0 else 100.0
    stock_qty = float(data.get("stock_qty") or data.get("stock_current") or 0.0)
    sku = data.get("sku") or f"PRD-{random.randint(100, 999)}"

    fields = (
        data.get("type", "produto"),
        sku,
        data.get("barcode", ""),
        data.get("name", "").strip(),
        data.get("category_name", "Geral"),
        data.get("unit", "UN"),
        cost,
        cost,
        margin,
        sale,
        stock_qty,
        float(data.get("min_stock") or data.get("stock_min") or 5.0),
        re.sub(r"\D", "", str(data.get("ncm", "84713012"))).zfill(8)[:8],
        data.get("cest", ""),
        str(data.get("origin", "0")),
        re.sub(r"\D", "", str(data.get("cfop_internal", "5102"))).zfill(4)[:4],
    )

    if pid:
        cur.execute("""
            UPDATE products SET
                type=?, sku=?, barcode=?, name=?, category_name=?, unit=?,
                cost_price=?, average_cost=?, margin_percent=?, sale_price=?,
                stock_qty=?, min_stock=?, ncm=?, cest=?, origin=?, cfop_internal=?
            WHERE id=?
        """, (*fields, pid))
    else:
        cur.execute("""
            INSERT INTO products (
                type, sku, barcode, name, category_name, unit,
                cost_price, average_cost, margin_percent, sale_price,
                stock_qty, min_stock, ncm, cest, origin, cfop_internal
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, fields)
        pid = cur.lastrowid

    conn.commit()
    log_audit(conn, action="save_product", entity="products", entity_id=pid, new_data=data, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": pid}


@router.post("/api/products/{product_id}/stock-adjust")
async def adjust_stock(product_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    new_stock = float(data.get("new_stock") if "new_stock" in data else (data.get("quantity") or 0.0))
    reason = data.get("reason", "Ajuste de estoque")

    conn = get_conn()
    cur = conn.cursor()
    prod = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not prod:
        conn.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    prev = float(prod["stock_qty"] or 0.0)
    avg_cost = float(prod["average_cost"] or prod["cost_price"] or 0.0)

    cur.execute("UPDATE products SET stock_qty = ? WHERE id = ?", (new_stock, product_id))
    cur.execute("""
        INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
        VALUES (?, 'ajuste', ?, ?, ?, ?, 'INVENTARIO', ?)
    """, (product_id, abs(new_stock - prev), avg_cost, prev, new_stock, reason))

    conn.commit()
    log_audit(conn, action="stock_adjust", entity="products", entity_id=product_id, new_data=data, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "new_stock": new_stock}


@router.get("/api/stock-movements")
def list_stock_movements(product_id: Optional[int] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    sql = """
        SELECT m.*, p.name as product_name, p.sku as product_sku
        FROM stock_movements m
        JOIN products p ON p.id = m.product_id
    """
    params = []
    if product_id:
        sql += " WHERE m.product_id = ?"
        params.append(product_id)
    sql += " ORDER BY m.id DESC LIMIT 100"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows
