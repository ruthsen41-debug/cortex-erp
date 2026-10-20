from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.phase3 import (
        WarehouseCreate,
        BatchCreate,
        VariantCreate,
        StockTransferCreate,
        InventoryAdjustmentCreate
    )
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.phase3 import (
        WarehouseCreate,
        BatchCreate,
        VariantCreate,
        StockTransferCreate,
        InventoryAdjustmentCreate
    )

router = APIRouter(tags=["Depósitos & Inventário"])


# ==========================================
# 1. DEPÓSITOS / ARMAZÉNS (/api/warehouses)
# ==========================================
@router.get("/api/warehouses")
def list_warehouses(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT * FROM warehouses
        WHERE company_id = ? AND active = 1
        ORDER BY is_default DESC, name ASC
    """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/api/warehouses")
def create_warehouse(data: WarehouseCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    if data.is_default:
        cur.execute("UPDATE warehouses SET is_default = 0 WHERE company_id = ?", (company_id,))

    cur.execute("""
        INSERT INTO warehouses (company_id, name, code, location, is_default, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (company_id, data.name, data.code.upper(), data.location, data.is_default, data.active))
    wid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="warehouses", entity_id=wid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": wid, "name": data.name}


@router.put("/api/warehouses/{wid}")
def update_warehouse(wid: int, data: WarehouseCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    if data.is_default:
        cur.execute("UPDATE warehouses SET is_default = 0 WHERE company_id = ? AND id != ?", (company_id, wid))

    cur.execute("""
        UPDATE warehouses
        SET name = ?, code = ?, location = ?, is_default = ?, active = ?
        WHERE id = ? AND company_id = ?
    """, (data.name, data.code.upper(), data.location, data.is_default, data.active, wid, company_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Depósito não encontrado.")
    conn.commit()
    log_audit(conn, action="update", entity="warehouses", entity_id=wid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": wid}


@router.delete("/api/warehouses/{wid}")
def delete_warehouse(wid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    wh = cur.execute("SELECT is_default FROM warehouses WHERE id = ? AND company_id = ?", (wid, company_id)).fetchone()
    if wh and wh["is_default"] == 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Não é permitido excluir o depósito padrão.")

    cur.execute("UPDATE warehouses SET active = 0 WHERE id = ? AND company_id = ?", (wid, company_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Depósito desativado com sucesso."}


# ==========================================
# 2. TRANSFERÊNCIA ENTRE DEPÓSITOS
# ==========================================
@router.post("/api/inventory/transfer")
def transfer_stock(data: StockTransferCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    if data.from_warehouse_id == data.to_warehouse_id:
        raise HTTPException(status_code=400, detail="O depósito de origem e destino devem ser diferentes.")

    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    prod = cur.execute("SELECT * FROM products WHERE id = ? AND company_id = ?", (data.product_id, company_id)).fetchone()
    if not prod:
        conn.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    wh_from = cur.execute("SELECT * FROM warehouses WHERE id = ?", (data.from_warehouse_id,)).fetchone()
    wh_to = cur.execute("SELECT * FROM warehouses WHERE id = ?", (data.to_warehouse_id,)).fetchone()
    if not wh_from or not wh_to:
        conn.close()
        raise HTTPException(status_code=404, detail="Depósito de origem ou destino não localizado.")

    cur_stock = float(prod["stock_qty"] or 0)
    avg_cost = float(prod["average_cost"] or prod["cost_price"] or 0)

    # Registra no Kardex a saída e a entrada entre depósitos
    ref_desc = f"Transferência de {wh_from['name']} para {wh_to['name']}"
    cur.execute("""
        INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
        VALUES (?, 'transferencia_saida', ?, ?, ?, ?, ?, ?)
    """, (data.product_id, data.quantity, avg_cost, cur_stock, cur_stock - data.quantity, f"SAIDA-DEP-{wh_from['code']}", data.notes or ref_desc))

    cur.execute("""
        INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
        VALUES (?, 'transferencia_entrada', ?, ?, ?, ?, ?, ?)
    """, (data.product_id, data.quantity, avg_cost, cur_stock - data.quantity, cur_stock, f"ENTRADA-DEP-{wh_to['code']}", data.notes or ref_desc))

    conn.commit()
    log_audit(conn, action="transfer", entity="inventory", entity_id=data.product_id, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "message": f"Transferência de {data.quantity} un de '{wh_from['name']}' para '{wh_to['name']}' registrada com sucesso."
    }


# ==========================================
# 3. AJUSTE DE INVENTÁRIO FÍSICO
# ==========================================
@router.post("/api/inventory/adjustment")
def adjust_inventory(data: InventoryAdjustmentCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    prod = cur.execute("SELECT * FROM products WHERE id = ? AND company_id = ?", (data.product_id, company_id)).fetchone()
    if not prod:
        conn.close()
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    old_qty = float(prod["stock_qty"] or 0)
    new_qty = float(data.new_quantity)
    delta = new_qty - old_qty
    avg_cost = float(prod["average_cost"] or prod["cost_price"] or 0)

    cur.execute("UPDATE products SET stock_qty = ? WHERE id = ?", (new_qty, data.product_id))

    cur.execute("""
        INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
        VALUES (?, 'ajuste_inventario', ?, ?, ?, ?, 'INVENTARIO-AUDIT', ?)
    """, (data.product_id, abs(delta), avg_cost, old_qty, new_qty, f"{data.reason} (Delta: {delta:+.2f})"))

    conn.commit()
    log_audit(conn, action="adjust_inventory", entity="products", entity_id=data.product_id, new_data={"old": old_qty, "new": new_qty, "reason": data.reason}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "product_id": data.product_id,
        "previous_stock": old_qty,
        "new_stock": new_qty,
        "delta": delta
    }


# ==========================================
# 4. LOTES E VALIDADES (/api/products/{id}/batches)
# ==========================================
@router.get("/api/products/{product_id}/batches")
def get_product_batches(product_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT b.*, w.name as warehouse_name
        FROM product_batches b
        LEFT JOIN warehouses w ON w.id = b.warehouse_id
        WHERE b.product_id = ? AND b.company_id = ?
        ORDER BY b.expiry_date ASC
    """, (product_id, company_id)).fetchall())
    conn.close()
    return rows


@router.post("/api/products/{product_id}/batches")
def create_product_batch(product_id: int, data: BatchCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    cur.execute("""
        INSERT INTO product_batches (company_id, product_id, warehouse_id, batch_number, expiry_date, manufacturing_date, quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, product_id, data.warehouse_id or 1, data.batch_number, data.expiry_date, data.manufacturing_date, data.quantity))
    bid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create_batch", entity="product_batches", entity_id=bid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": bid, "batch_number": data.batch_number}


@router.get("/api/inventory/batches/expiring")
def get_expiring_batches(days: int = 90, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retorna lotes com validade próxima nos próximos N dias."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    target_date = (date.today() + timedelta(days=days)).isoformat()
    rows = rows_to_dicts(conn.execute("""
        SELECT b.*, p.name as product_name, p.sku, w.name as warehouse_name
        FROM product_batches b
        JOIN products p ON p.id = b.product_id
        LEFT JOIN warehouses w ON w.id = b.warehouse_id
        WHERE b.company_id = ? AND b.expiry_date <= ? AND b.quantity > 0
        ORDER BY b.expiry_date ASC
    """, (company_id, target_date)).fetchall())
    conn.close()
    return rows


# ==========================================
# 5. VARIAÇÕES DE PRODUTO (/api/products/{id}/variants)
# ==========================================
@router.get("/api/products/{product_id}/variants")
def get_product_variants(product_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT * FROM product_variants
        WHERE product_id = ? AND company_id = ? AND active = 1
        ORDER BY id ASC
    """, (product_id, company_id)).fetchall())
    conn.close()
    return rows


@router.post("/api/products/{product_id}/variants")
def create_product_variant(product_id: int, data: VariantCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    cur.execute("""
        INSERT INTO product_variants (company_id, product_id, variant_name, sku, additional_price, stock_qty, active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, product_id, data.variant_name, data.sku, data.additional_price, data.stock_qty, data.active))
    vid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create_variant", entity="product_variants", entity_id=vid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": vid, "variant_name": data.variant_name}
