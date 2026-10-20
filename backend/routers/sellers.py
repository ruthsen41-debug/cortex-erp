from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.phase3 import PriceTableCreate, SellerCreate
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.phase3 import PriceTableCreate, SellerCreate

router = APIRouter(tags=["Vendedores & Tabelas de Preço"])


# ==========================================
# 1. TABELAS DE PREÇO (/api/price-tables)
# ==========================================
@router.get("/api/price-tables")
def list_price_tables(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT * FROM price_tables
        WHERE company_id = ? AND active = 1
        ORDER BY id ASC
    """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/api/price-tables")
def create_price_table(data: PriceTableCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("""
        INSERT INTO price_tables (company_id, name, discount_percent, markup_percent, active)
        VALUES (?, ?, ?, ?, ?)
    """, (company_id, data.name, data.discount_percent, data.markup_percent, data.active))
    ptid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="price_tables", entity_id=ptid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": ptid, "name": data.name}


@router.put("/api/price-tables/{ptid}")
def update_price_table(ptid: int, data: PriceTableCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("""
        UPDATE price_tables
        SET name = ?, discount_percent = ?, markup_percent = ?, active = ?
        WHERE id = ? AND company_id = ?
    """, (data.name, data.discount_percent, data.markup_percent, data.active, ptid, company_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Tabela de preço não encontrada.")
    conn.commit()
    log_audit(conn, action="update", entity="price_tables", entity_id=ptid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": ptid}


@router.delete("/api/price-tables/{ptid}")
def delete_price_table(ptid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("UPDATE price_tables SET active = 0 WHERE id = ? AND company_id = ?", (ptid, company_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Tabela de preço desativada."}


# ==========================================
# 2. VENDEDORES & COMISSÕES (/api/sellers)
# ==========================================
@router.get("/api/sellers")
def list_sellers(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT * FROM sellers
        WHERE company_id = ? AND active = 1
        ORDER BY name ASC
    """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/api/sellers")
def create_seller(data: SellerCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("""
        INSERT INTO sellers (company_id, name, email, phone, commission_percent, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (company_id, data.name, data.email, data.phone, data.commission_percent, data.active))
    sid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="sellers", entity_id=sid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": sid, "name": data.name}


@router.put("/api/sellers/{sid}")
def update_seller(sid: int, data: SellerCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("""
        UPDATE sellers
        SET name = ?, email = ?, phone = ?, commission_percent = ?, active = ?
        WHERE id = ? AND company_id = ?
    """, (data.name, data.email, data.phone, data.commission_percent, data.active, sid, company_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Vendedor não encontrado.")
    conn.commit()
    log_audit(conn, action="update", entity="sellers", entity_id=sid, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": sid}


@router.delete("/api/sellers/{sid}")
def delete_seller(sid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("UPDATE sellers SET active = 0 WHERE id = ? AND company_id = ?", (sid, company_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Vendedor desativado."}


@router.get("/api/sellers/{sid}/commissions")
def get_seller_commissions(sid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Relatório detalhado de comissões acumuladas por vendedor."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    seller = conn.execute("SELECT * FROM sellers WHERE id = ? AND company_id = ?", (sid, company_id)).fetchone()
    if not seller:
        conn.close()
        raise HTTPException(status_code=404, detail="Vendedor não encontrado.")

    sales_rows = rows_to_dicts(conn.execute("""
        SELECT id, number, sale_date, total_amount, commission_amount, status
        FROM sales
        WHERE seller_id = ? AND company_id = ?
        ORDER BY id DESC
    """, (sid, company_id)).fetchall())
    conn.close()

    total_sales_value = sum(float(s["total_amount"] or 0) for s in sales_rows)
    total_commission = sum(float(s["commission_amount"] or 0) for s in sales_rows)

    return {
        "seller_id": sid,
        "seller_name": seller["name"],
        "commission_percent": float(seller["commission_percent"] or 0),
        "total_sales_count": len(sales_rows),
        "total_sales_amount": round(total_sales_value, 2),
        "total_commission_amount": round(total_commission, 2),
        "sales": sales_rows
    }
