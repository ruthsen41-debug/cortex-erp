from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from typing import Optional, Dict, Any, List

try:
    from ..database import get_conn, recalculate_bank_balances
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts, add_months
    from ..schemas.sales import SaleCreate
except ImportError:
    from database import get_conn, recalculate_bank_balances
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts, add_months
    from schemas.sales import SaleCreate

router = APIRouter(prefix="/api/sales", tags=["Vendas & Orçamentos"])


def _process_sale_billing(conn, sale_id: int, immediate_paid: bool = False, company_id: int = 1):
    """Dá baixa automática no estoque dos produtos vendidos e gera as parcelas no Contas a Receber."""
    cur = conn.cursor()
    sale = cur.execute("""
        SELECT s.*, c.name as contact_name
        FROM sales s LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE s.id = ?
    """, (sale_id,)).fetchone()
    items = rows_to_dicts(cur.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall())

    # 1. Baixa estoque de produtos físicos
    for it in items:
        if it.get("product_id"):
            prod = cur.execute("SELECT * FROM products WHERE id = ?", (it["product_id"],)).fetchone()
            if prod and prod["type"] == "produto":
                prev_s = float(prod["stock_qty"] or 0.0)
                new_s = prev_s - float(it["quantity"])
                cur.execute("UPDATE products SET stock_qty = ? WHERE id = ?", (new_s, prod["id"]))
                cur.execute("""
                    INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
                    VALUES (?, 'venda', ?, ?, ?, ?, ?, ?)
                """, (prod["id"], float(it["quantity"]), float(prod["average_cost"] or prod["cost_price"] or 0), prev_s, new_s, f"VENDA #{sale['number']}", f"Baixa automática Venda #{sale['number']}"))

    # 2. Gera parcelas no Contas a Receber
    installments = max(1, int(sale.get("installments") or 1))
    total = float(sale["total_amount"])
    per_inst = round(total / installments, 2)
    base_date = date.fromisoformat(sale["sale_date"][:10])
    client_label = sale["contact_name"] or "Consumidor Final"

    for i in range(1, installments + 1):
        due_d = base_date.isoformat() if (i == 1 and immediate_paid) else add_months(base_date, i - 1 if immediate_paid else i).isoformat()
        amt = per_inst if i < installments else round(total - per_inst * (installments - 1), 2)
        is_paid = immediate_paid and i == 1
        cur.execute("""
            INSERT INTO financial_entries (
                company_id, type, description, contact_id, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, paid_amount, status,
                installment_number, installment_total, group_uid, document_number, origin_type, origin_id
            ) VALUES (?, 'receita', ?, ?, 1, 2, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            f"Venda #{sale['number']} ({i}/{installments}) - {client_label}",
            sale["contact_id"],
            sale["bank_account_id"] or 1,
            sale["payment_method"],
            sale["sale_date"][:10],
            due_d,
            amt,
            amt if is_paid else 0.0,
            "pago" if is_paid else "pendente",
            i,
            installments,
            f"VND-{sale['number']}",
            f"PED-{sale['number']}",
            sale["sale_type"],
            sale_id,
        ))
        eid = cur.lastrowid
        if is_paid:
            cur.execute("""
                INSERT INTO financial_payments (entry_id, bank_account_id, payment_date, principal_paid, total_cash_flow, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (eid, sale["bank_account_id"] or 1, due_d, amt, amt, sale["payment_method"], f"Recebimento Venda #{sale['number']}"))

    cur.execute("UPDATE sales SET status = 'faturada', sale_type = CASE WHEN sale_type = 'orcamento' THEN 'venda' ELSE sale_type END WHERE id = ?", (sale_id,))
    recalculate_bank_balances(conn)
    conn.commit()


@router.get("")
def list_sales(sale_type: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = """
        SELECT s.*, c.name as client_name, c.document as client_doc
        FROM sales s
        LEFT JOIN contacts c ON c.id = s.contact_id
        WHERE 1=1
    """
    params = []
    if sale_type and sale_type != "todos":
        sql += " AND s.sale_type = ?"
        params.append(sale_type)
    sql += " ORDER BY s.id DESC"
    sales = rows_to_dicts(conn.execute(sql, params).fetchall())
    for s in sales:
        s["items"] = rows_to_dicts(conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (s["id"],)).fetchall())
    conn.close()
    return sales


@router.post("")
async def create_sale(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    s_type = data.get("type") or data.get("sale_type") or "venda"
    status = "faturada" if s_type == "pdv" else ("aprovada" if s_type == "venda" else "orcamento")
    contact_id = data.get("contact_id")
    seller = current_user.get("name", "Vendedor")
    pay_method = data.get("payment_method", "Pix")
    installments = int(data.get("installments") or 1)
    notes = data.get("notes", "")

    next_num = (cur.execute("SELECT MAX(number) FROM sales").fetchone()[0] or 1000) + 1
    items = data.get("items", [])

    calc_subtotal = 0.0
    for it in items:
        qty = float(it.get("quantity") or 1.0)
        u_p = float(it.get("unit_price") or 0.0)
        calc_subtotal += (qty * u_p)

    total = float(data.get("total_amount") if data.get("total_amount") is not None else calc_subtotal)

    cur.execute("""
        INSERT INTO sales (number, sale_type, status, contact_id, seller_name, sale_date, subtotal, total_amount, payment_method, installments, bank_account_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (next_num, s_type, status, contact_id, seller, date.today().isoformat(), calc_subtotal, total, pay_method, installments, notes))
    sale_id = cur.lastrowid

    for it in items:
        pid = it.get("product_id")
        pname = it.get("name") or "Produto"
        qty = float(it.get("quantity") or 1.0)
        up = float(it.get("unit_price") or 0.0)
        sub = qty * up
        cur.execute("""
            INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
            VALUES (?, ?, ?, 'PRD', 'UN', ?, ?, 0.0, ?)
        """, (sale_id, pid, pname, qty, up, sub))

    conn.commit()

    if s_type == "pdv":
        _process_sale_billing(conn, sale_id, immediate_paid=True, company_id=company_id)
    elif s_type == "venda":
        _process_sale_billing(conn, sale_id, immediate_paid=False, company_id=company_id)

    log_audit(conn, action="create_sale", entity="sales", entity_id=sale_id, new_data={"number": next_num, "total": total}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": sale_id, "number": next_num}


@router.post("/{sale_id}/approve")
def approve_sale(sale_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    sale = cur.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if not sale:
        conn.close()
        raise HTTPException(status_code=404, detail="Venda/Orçamento não encontrado.")

    _process_sale_billing(conn, sale_id, immediate_paid=False, company_id=current_user.get("company_id", 1))
    log_audit(conn, action="approve_sale", entity="sales", entity_id=sale_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Venda aprovada e faturada!"}


@router.get("/{sale_id}/print", response_class=HTMLResponse)
def print_sale_proposal(sale_id: int):
    conn = get_conn()
    cur = conn.cursor()
    sale = cur.execute("""
        SELECT s.*, c.name as client_name, c.document as client_doc, c.phone as client_phone, c.email as client_email,
               comp.razao_social as comp_name, comp.cnpj as comp_cnpj, comp.telefone as comp_phone
        FROM sales s
        LEFT JOIN contacts c ON c.id = s.contact_id
        CROSS JOIN companies comp
        WHERE s.id = ?
        LIMIT 1
    """, (sale_id,)).fetchone()
    if not sale:
        conn.close()
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    items = rows_to_dicts(cur.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall())
    conn.close()

    items_html = "".join([
        f"<tr><td style='padding:8px;border-bottom:1px solid #ddd'>{it['product_name']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #ddd;text-align:center'>{it['quantity']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #ddd;text-align:right'>R$ {it['unit_price']:,.2f}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #ddd;text-align:right'>R$ {it['total_price']:,.2f}</td></tr>"
        for it in items
    ])

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Proposta Comercial #{sale['number']}</title>
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
        .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #2563eb; padding-bottom: 15px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #f3f4f6; text-align: left; padding: 8px; font-size: 12px; }}
        .total {{ text-align: right; font-size: 18px; font-weight: bold; color: #2563eb; }}
      </style>
    </head>
    <body>
      <div class="header">
        <div>
          <h2>{sale['comp_name'] or 'Cortex ERP Solutions'}</h2>
          <div>CNPJ: {sale['comp_cnpj'] or '00.000.000/0001-00'} · Tel: {sale['comp_phone'] or '(65) 3223-0000'}</div>
        </div>
        <div style="text-align:right">
          <h3>PROPOSTA COMERCIAL #{sale['number']}</h3>
          <div>Data: {sale['sale_date']}</div>
        </div>
      </div>
      <div>
        <strong>Cliente:</strong> {sale['client_name'] or 'Consumidor Final'} ({sale['client_doc'] or 'Não informado'})<br>
        <strong>Condição:</strong> {sale['payment_method']} ({sale['installments']}x)
      </div>
      <table>
        <thead>
          <tr><th>Item / Serviço</th><th style="text-align:center">Qtd</th><th style="text-align:right">Unitário</th><th style="text-align:right">Total</th></tr>
        </thead>
        <tbody>
          {items_html}
        </tbody>
      </table>
      <div class="total">Valor Total: R$ {sale['total_amount']:,.2f}</div>
      <div style="margin-top:40px;text-align:center;font-size:12px;color:#777">
        Documento gerado automaticamente pelo Cortex ERP Pro+
      </div>
    </body>
    </html>
    """
