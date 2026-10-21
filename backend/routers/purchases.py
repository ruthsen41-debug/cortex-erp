from fastapi import APIRouter, Request, Depends
from typing import Dict, Any

try:
    from ..database import get_conn, begin_write
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..fiscal_engine import gerar_xml_compra_exemplo, parse_nfe_compra_xml
except ImportError:
    from database import get_conn, begin_write
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from fiscal_engine import gerar_xml_compra_exemplo, parse_nfe_compra_xml

router = APIRouter(prefix="/api/xml-purchases", tags=["Compras & XML Fornecedores"])


@router.get("")
def list_xml_purchases(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("SELECT * FROM xml_purchases ORDER BY id DESC").fetchall())
    conn.close()
    return rows


@router.post("/import")
async def import_supplier_xml(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    content_type = req.headers.get("content-type", "")
    xml_text = ""

    if "multipart/form-data" in content_type:
        form = await req.form()
        file = form.get("file")
        if file and hasattr(file, "read"):
            bytes_content = await file.read()
            xml_text = bytes_content.decode("utf-8", errors="ignore")
    else:
        try:
            data = await req.json()
            xml_text = data.get("xml_content") or ""
        except Exception:
            pass

    if not xml_text.strip():
        xml_text = gerar_xml_compra_exemplo()

    parsed = parse_nfe_compra_xml(xml_text)
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    # 1. Fornecedor
    sup = parsed["supplier"]
    sup_row = cur.execute("SELECT id FROM contacts WHERE document LIKE ?", (f"%{sup['cnpj'][:8]}%",)).fetchone()
    if sup_row:
        supplier_id = sup_row["id"]
    else:
        cur.execute("""
            INSERT INTO contacts (company_id, type, person_type, name, trade_name, document, state_registration, street, number, neighborhood, city, state, cep)
            VALUES (?, 'fornecedor', 'PJ', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (company_id, sup["name"], sup["trade_name"], sup["cnpj"], sup["ie"], sup["street"], sup["number"], sup["neighborhood"], sup["city"], sup["state"], sup["cep"]))
        supplier_id = cur.lastrowid

    # 2. Produtos e Estoque com Custo Médio
    begin_write(conn)
    for it in parsed["items"]:
        prod = cur.execute("SELECT * FROM products WHERE (sku = ? OR name = ?) AND company_id = ?", (it["sku"], it["name"], company_id)).fetchone()
        qty = float(it["quantity"])
        u_cost = float(it["unit_cost"])
        if prod:
            pid = prod["id"]
            prev_stock = float(prod["stock_qty"] or 0.0)
            prev_avg = float(prod["average_cost"] or prod["cost_price"] or u_cost)
            new_stock = prev_stock + qty
            new_avg = round(((max(0.0, prev_stock) * prev_avg) + (qty * u_cost)) / max(1.0, new_stock), 2)
            cur.execute("UPDATE products SET stock_qty = ?, cost_price = ?, average_cost = ? WHERE id = ?", (new_stock, u_cost, new_avg, pid))
        else:
            sale_p = round(u_cost * 1.55, 2)
            cur.execute("""
                INSERT INTO products (company_id, type, sku, barcode, name, category_name, unit, cost_price, average_cost, margin_percent, sale_price, stock_qty, min_stock, ncm)
                VALUES (?, 'produto', ?, ?, ?, 'Importado XML', ?, ?, ?, 55.0, ?, ?, 3.0, ?)
            """, (company_id, it["sku"], it["barcode"], it["name"], it["unit"], u_cost, u_cost, sale_p, qty, it["ncm"]))
            pid = cur.lastrowid
            prev_stock = 0.0
            new_stock = qty

        cur.execute("""
            INSERT INTO stock_movements (product_id, movement_type, quantity, unit_cost, previous_stock, new_stock, reference, notes)
            VALUES (?, 'compra_xml', ?, ?, ?, ?, ?, ?)
        """, (pid, qty, u_cost, prev_stock, new_stock, f"NF-e Compra #{parsed['invoice_number']}", f"Entrada automática via XML ({sup['trade_name']})"))

    # 3. Duplicatas no Contas a Pagar
    inst_total = len(parsed["installments"])
    for idx, dup in enumerate(parsed["installments"], start=1):
        cur.execute("""
            INSERT INTO financial_entries (
                company_id, type, description, contact_id, category_id, cost_center_id, bank_account_id,
                payment_method, competence_date, due_date, amount, status, installment_number,
                installment_total, group_uid, document_number, origin_type
            ) VALUES (?, 'despesa', ?, ?, 6, 4, 1, 'Boleto', ?, ?, ?, 'pendente', ?, ?, ?, ?, 'xml_compra')
        """, (
            company_id,
            f"NF-e Compra #{parsed['invoice_number']} (Dup. {dup['number']}) - {sup['trade_name']}",
            supplier_id,
            parsed["issue_date"],
            dup["due_date"],
            float(dup["amount"]),
            idx,
            inst_total,
            f"XML-{parsed['invoice_number']}",
            f"NFE-{parsed['invoice_number']}-{dup['number']}",
        ))

    cur.execute("""
        INSERT INTO xml_purchases (access_key, invoice_number, supplier_cnpj, supplier_name, issue_date, total_amount, items_count, installments_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        parsed["access_key"],
        parsed["invoice_number"],
        sup["cnpj"],
        sup["name"],
        parsed["issue_date"],
        float(parsed["total_amount"]),
        len(parsed["items"]),
        inst_total,
    ))
    conn.commit()
    log_audit(conn, action="import_xml", entity="xml_purchases", new_data={"invoice": parsed["invoice_number"], "total": parsed["total_amount"]}, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "invoice_number": parsed["invoice_number"],
        "supplier": sup["trade_name"],
        "items_count": len(parsed["items"]),
        "total_amount": float(parsed["total_amount"]),
        "message": f"NF-e #{parsed['invoice_number']} importada com sucesso!",
    }
