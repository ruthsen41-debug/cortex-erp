from datetime import date
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.phase3 import ReturnCreate
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.phase3 import ReturnCreate

router = APIRouter(prefix="/api/sales/returns", tags=["Devoluções & Trocas (RMA)"])


@router.get("")
def list_sales_returns(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT sr.*, s.number as sale_number, c.name as client_name
        FROM sales_returns sr
        JOIN sales s ON s.id = sr.sale_id
        LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE sr.company_id = ?
        ORDER BY sr.id DESC
    """, (company_id,)).fetchall())

    for r in rows:
        r["items"] = rows_to_dicts(conn.execute("""
            SELECT sri.*, p.name as product_name, p.sku
            FROM sales_return_items sri
            JOIN products p ON p.id = sri.product_id
            WHERE sri.return_id = ?
        """, (r["id"],)).fetchall())
    conn.close()
    return rows


@router.post("")
def create_sales_return(data: ReturnCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    sale = cur.execute("SELECT * FROM sales WHERE id = ? AND company_id = ?", (data.sale_id, company_id)).fetchone()
    if not sale:
        conn.close()
        raise HTTPException(status_code=404, detail="Venda de origem não encontrada.")

    total_returned = sum(float(it.quantity) * float(it.unit_price) for it in data.items)

    cur.execute("""
        INSERT INTO sales_returns (company_id, sale_id, reason, total_returned, refund_method, status)
        VALUES (?, ?, ?, ?, ?, 'concluido')
    """, (company_id, data.sale_id, data.reason, total_returned, data.refund_method or "credito"))
    ret_id = cur.lastrowid

    # Processa itens e reestocagem
    for it in data.items:
        cur.execute("""
            INSERT INTO sales_return_items (return_id, product_id, quantity, unit_price, return_to_stock)
            VALUES (?, ?, ?, ?, ?)
        """, (ret_id, it.product_id, it.quantity, it.unit_price, it.return_to_stock))

        if it.return_to_stock:
            prod = cur.execute("SELECT stock_qty, average_cost, cost_price FROM products WHERE id = ?", (it.product_id,)).fetchone()
            if prod:
                old_qty = float(prod["stock_qty"] or 0.0)
                new_qty = old_qty + float(it.quantity)
                avg_cost = float(prod["average_cost"] or prod["cost_price"] or 0.0)

                cur.execute("UPDATE products SET stock_qty = ? WHERE id = ?", (new_qty, it.product_id))

                cur.execute("""
                    INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
                    VALUES (?, 'devolucao', ?, ?, ?, ?, ?, ?)
                """, (it.product_id, it.quantity, avg_cost, old_qty, new_qty, f"DEV #{ret_id} (Venda #{sale['number']})", f"Devolução/Troca de venda: {data.reason}"))

    # Processa estorno financeiro se solicitado
    fin_entry_id = None
    if data.refund_method == "estorno_financeiro":
        today_str = date.today().isoformat()
        cur.execute("""
            INSERT INTO financial_entries (
                company_id, type, description, contact_id, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount, status,
                origin_type, origin_id, notes
            ) VALUES (?, 'despesa', ?, ?, 1, 2, 1, 'Pix', ?, ?, ?, 0.0, 'pendente', 'devolucao_venda', ?, ?)
        """, (
            company_id,
            f"Estorno/Devolução da Venda #{sale['number']} (RMA #{ret_id})",
            sale["contact_id"],
            today_str,
            today_str,
            total_returned,
            ret_id,
            f"Motivo: {data.reason}"
        ))
        fin_entry_id = cur.lastrowid

    conn.commit()
    log_audit(conn, action="create_return", entity="sales_returns", entity_id=ret_id, new_data=data.dict(), user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "return_id": ret_id,
        "total_returned": total_returned,
        "financial_entry_id": fin_entry_id,
        "message": "Devolução/RMA registrada com sucesso e estoque atualizado."
    }


@router.get("/{return_id}")
def get_sales_return(return_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("""
        SELECT sr.*, s.number as sale_number, c.name as client_name
        FROM sales_returns sr
        JOIN sales s ON s.id = sr.sale_id
        LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE sr.id = ? AND sr.company_id = ?
    """, (return_id, company_id)).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Devolução não encontrada.")

    data = dict(row)
    data["items"] = rows_to_dicts(conn.execute("""
        SELECT sri.*, p.name as product_name, p.sku
        FROM sales_return_items sri
        JOIN products p ON p.id = sri.product_id
        WHERE sri.return_id = ?
    """, (return_id,)).fetchall())
    conn.close()
    return data
