from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from typing import Dict, Any, Optional

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts

router = APIRouter(prefix="/api/quotes", tags=["Orçamentos & Pedidos de Venda"])

STATUS_LABELS = {
    "rascunho": "Rascunho",
    "enviado": "Enviado",
    "aprovado": "Aprovado",
    "rejeitado": "Rejeitado",
    "faturado": "Faturado",
    "cancelado": "Cancelado",
}


def _enrich(rows, conn):
    for r in rows:
        r["items"] = rows_to_dicts(conn.execute("""
            SELECT qi.*, p.ncm, p.cfop_internal as cfop, p.csosn_cst
            FROM quote_items qi
            LEFT JOIN products p ON p.id = qi.product_id
            WHERE qi.quote_id = ?
        """, (r["id"],)).fetchall())
        r["status_label"] = STATUS_LABELS.get(r["status"], r["status"])
        r["type_label"] = "Orçamento" if r["type"] == "orcamento" else "Pedido"
    return rows


@router.get("")
def list_quotes(status: Optional[str] = None, type: Optional[str] = None,
                current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = """
        SELECT q.*, c.name as contact_name, c.document as contact_doc,
               s.name as seller_name
        FROM quotes q
        LEFT JOIN contacts c ON c.id = q.contact_id
        LEFT JOIN sellers s ON s.id = q.seller_id
        WHERE q.company_id = ?
    """
    params = [company_id]
    if status and status != "todos":
        sql += " AND q.status = ?"
        params.append(status)
    if type and type != "todos":
        sql += " AND q.type = ?"
        params.append(type)
    sql += " ORDER BY q.id DESC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    _enrich(rows, conn)
    conn.close()
    return rows


@router.get("/stats")
def quote_stats(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT status, COUNT(*) as count, SUM(total_amount) as total FROM quotes WHERE company_id = ? GROUP BY status",
        (company_id,)
    ).fetchall())
    conn.close()
    stats = {r["status"]: {"count": r["count"], "total": r["total"] or 0} for r in rows}
    return stats


@router.get("/{quote_id}")
def get_quote(quote_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("""
        SELECT q.*, c.name as contact_name, c.document as contact_doc,
               c.email as contact_email, c.phone as contact_phone,
               s.name as seller_name
        FROM quotes q
        LEFT JOIN contacts c ON c.id = q.contact_id
        LEFT JOIN sellers s ON s.id = q.seller_id
        WHERE q.id = ? AND q.company_id = ?
    """, (quote_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    result = dict(row)
    result["items"] = rows_to_dicts(conn.execute(
        "SELECT * FROM quote_items WHERE quote_id = ? ORDER BY id", (quote_id,)
    ).fetchall())
    result["status_label"] = STATUS_LABELS.get(result["status"], result["status"])
    result["type_label"] = "Orçamento" if result["type"] == "orcamento" else "Pedido"
    conn.close()
    return result


@router.post("")
async def create_quote(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    next_num = (cur.execute(
        "SELECT MAX(quote_number) FROM quotes WHERE company_id = ?", (company_id,)
    ).fetchone()[0] or 0) + 1

    valid_until = data.get("valid_until") or (date.today() + timedelta(days=30)).isoformat()

    cur.execute("""
        INSERT INTO quotes (company_id, quote_number, type, status, contact_id, seller_id,
            valid_until, payment_terms, subtotal, discount_amount, shipping_amount, total_amount,
            notes, internal_notes)
        VALUES (?, ?, ?, 'rascunho', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id, next_num,
        data.get("type", "orcamento"),
        data.get("contact_id") or None,
        data.get("seller_id") or None,
        valid_until,
        data.get("payment_terms", "À Vista"),
        float(data.get("subtotal", 0)),
        float(data.get("discount_amount", 0)),
        float(data.get("shipping_amount", 0)),
        float(data.get("total_amount", 0)),
        data.get("notes", ""),
        data.get("internal_notes", ""),
    ))
    quote_id = cur.lastrowid

    for it in data.get("items", []):
        qty   = float(it.get("quantity", 1))
        price = float(it.get("unit_price", 0))
        disc  = float(it.get("discount", 0))
        total = round((qty * price) - disc, 2)
        cur.execute("""
            INSERT INTO quote_items (quote_id, product_id, product_name, sku, quantity, unit, unit_price, discount, total_price, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quote_id,
            it.get("product_id") or None,
            it.get("product_name") or it.get("name", "Item"),
            it.get("sku", ""),
            qty, it.get("unit", "UN"), price, disc, total,
            it.get("notes", ""),
        ))

    conn.commit()
    log_audit(conn, action="create", entity="quotes", entity_id=quote_id, new_data=data, user_id=current_user.get("id"))
    conn.close()
    prefix = "ORC" if data.get("type", "orcamento") == "orcamento" else "PED"
    return {"status": "ok", "quote_id": quote_id, "quote_number": next_num,
            "message": f"{prefix}-{next_num:04d} criado com sucesso!"}


@router.put("/{quote_id}")
async def update_quote(quote_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    row = cur.execute("SELECT id, status FROM quotes WHERE id = ? AND company_id = ?", (quote_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    if row["status"] in ("faturado", "cancelado"):
        conn.close()
        raise HTTPException(status_code=400, detail=f"Não é possível editar um orçamento com status '{row['status']}'.")

    cur.execute("""
        UPDATE quotes SET type=?, contact_id=?, seller_id=?, valid_until=?, payment_terms=?,
            subtotal=?, discount_amount=?, shipping_amount=?, total_amount=?,
            notes=?, internal_notes=?
        WHERE id = ? AND company_id = ?
    """, (
        data.get("type", "orcamento"),
        data.get("contact_id") or None,
        data.get("seller_id") or None,
        data.get("valid_until"),
        data.get("payment_terms", "À Vista"),
        float(data.get("subtotal", 0)),
        float(data.get("discount_amount", 0)),
        float(data.get("shipping_amount", 0)),
        float(data.get("total_amount", 0)),
        data.get("notes", ""),
        data.get("internal_notes", ""),
        quote_id, company_id,
    ))

    cur.execute("DELETE FROM quote_items WHERE quote_id = ?", (quote_id,))
    for it in data.get("items", []):
        qty   = float(it.get("quantity", 1))
        price = float(it.get("unit_price", 0))
        disc  = float(it.get("discount", 0))
        total = round((qty * price) - disc, 2)
        cur.execute("""
            INSERT INTO quote_items (quote_id, product_id, product_name, sku, quantity, unit, unit_price, discount, total_price, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quote_id,
            it.get("product_id") or None,
            it.get("product_name") or it.get("name", "Item"),
            it.get("sku", ""),
            qty, it.get("unit", "UN"), price, disc, total,
            it.get("notes", ""),
        ))

    conn.commit()
    log_audit(conn, action="update", entity="quotes", entity_id=quote_id, new_data=data, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Orçamento atualizado com sucesso!"}


@router.post("/{quote_id}/send")
def send_quote(quote_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("SELECT status FROM quotes WHERE id = ? AND company_id = ?", (quote_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    conn.execute("UPDATE quotes SET status = 'enviado' WHERE id = ?", (quote_id,))
    conn.commit()
    log_audit(conn, action="send", entity="quotes", entity_id=quote_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Orçamento marcado como enviado ao cliente."}


@router.post("/{quote_id}/approve")
def approve_quote(quote_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("SELECT status FROM quotes WHERE id = ? AND company_id = ?", (quote_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    conn.execute("UPDATE quotes SET status = 'aprovado' WHERE id = ?", (quote_id,))
    conn.commit()
    log_audit(conn, action="approve", entity="quotes", entity_id=quote_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Orçamento aprovado!"}


@router.post("/{quote_id}/reject")
def reject_quote(quote_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("SELECT status FROM quotes WHERE id = ? AND company_id = ?", (quote_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    conn.execute("UPDATE quotes SET status = 'rejeitado' WHERE id = ?", (quote_id,))
    conn.commit()
    log_audit(conn, action="reject", entity="quotes", entity_id=quote_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Orçamento marcado como rejeitado."}


@router.post("/{quote_id}/cancel")
def cancel_quote(quote_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("UPDATE quotes SET status = 'cancelado' WHERE id = ? AND company_id = ?", (quote_id, company_id))
    conn.commit()
    log_audit(conn, action="cancel", entity="quotes", entity_id=quote_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Orçamento cancelado."}


@router.post("/{quote_id}/convert")
async def convert_to_sale(quote_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    quote = cur.execute("SELECT * FROM quotes WHERE id = ? AND company_id = ?", (quote_id, company_id)).fetchone()
    if not quote:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    if dict(quote)["status"] in ("faturado", "cancelado"):
        conn.close()
        raise HTTPException(status_code=400, detail="Este orçamento já foi faturado ou cancelado.")
    if not dict(quote)["contact_id"]:
        conn.close()
        raise HTTPException(status_code=400, detail="O orçamento precisa ter um cliente para ser convertido em venda.")

    q = dict(quote)
    items = rows_to_dicts(cur.execute("SELECT * FROM quote_items WHERE quote_id = ?", (quote_id,)).fetchall())

    next_sale = (cur.execute("SELECT MAX(number) FROM sales WHERE company_id = ?", (company_id,)).fetchone()[0] or 1000) + 1

    cur.execute("""
        INSERT INTO sales (company_id, number, sale_type, status, contact_id, seller_id,
            seller_name, sale_date, subtotal, discount_amount, shipping_amount,
            total_amount, payment_method, notes)
        VALUES (?, ?, 'venda', 'aprovada', ?, ?, '', date('now'), ?, ?, ?, ?, ?, ?)
    """, (
        company_id, next_sale, q["contact_id"], q["seller_id"],
        q["subtotal"], q["discount_amount"], q["shipping_amount"], q["total_amount"],
        q["payment_terms"], q["notes"],
    ))
    sale_id = cur.lastrowid

    for it in items:
        cur.execute("""
            INSERT INTO sale_items (sale_id, product_id, product_name, sku, unit, quantity, unit_price, discount, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sale_id, it.get("product_id"), it["product_name"], it.get("sku", ""),
              it.get("unit", "UN"), it["quantity"], it["unit_price"], it["discount"], it["total_price"]))

    cur.execute("UPDATE quotes SET status = 'faturado', sale_id = ? WHERE id = ?", (sale_id, quote_id))
    conn.commit()
    log_audit(conn, action="convert_to_sale", entity="quotes", entity_id=quote_id,
              new_data={"sale_id": sale_id}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "sale_id": sale_id, "sale_number": next_sale,
            "message": f"Orçamento convertido para a Venda #{next_sale} com sucesso!"}


@router.get("/{quote_id}/print", response_class=HTMLResponse)
def print_quote(quote_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone())
    row = conn.execute("""
        SELECT q.*, c.name as contact_name, c.document as contact_doc,
               c.email as contact_email, c.phone as contact_phone,
               c.street as contact_street, c.city as contact_city, c.state as contact_state,
               s.name as seller_name
        FROM quotes q
        LEFT JOIN contacts c ON c.id = q.contact_id
        LEFT JOIN sellers s ON s.id = q.seller_id
        WHERE q.id = ? AND q.company_id = ?
    """, (quote_id, company_id)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    q = dict(row)
    items = rows_to_dicts(conn.execute("SELECT * FROM quote_items WHERE quote_id = ? ORDER BY id", (quote_id,)).fetchall())
    conn.close()

    prefix = "ORC" if q["type"] == "orcamento" else "PED"
    title  = "ORÇAMENTO" if q["type"] == "orcamento" else "PEDIDO DE VENDA"
    num    = f"{prefix}-{q['quote_number']:04d}"

    rows_html = "".join(f"""
        <tr>
          <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">{i+1}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">{it['product_name']}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:center">{it['quantity']:.2f} {it['unit']}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right">R$ {it['unit_price']:,.2f}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right">R$ {it['discount']:,.2f}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:600">R$ {it['total_price']:,.2f}</td>
        </tr>""" for i, it in enumerate(items))

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>{title} {num}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; font-size:12px; color:#1e293b; background:#f8fafc; }}
  .page {{ max-width:800px; margin:20px auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,.08); }}
  .header {{ background:linear-gradient(135deg,#1e3a5f,#2563eb); color:#fff; padding:24px 32px; display:flex; justify-content:space-between; align-items:flex-start; }}
  .header h1 {{ font-size:22px; font-weight:800; letter-spacing:.5px; }}
  .header .num {{ font-size:14px; opacity:.85; margin-top:2px; }}
  .badge {{ display:inline-block; padding:4px 12px; border-radius:999px; font-size:11px; font-weight:700; background:rgba(255,255,255,.2); color:#fff; margin-top:6px; }}
  .body {{ padding:24px 32px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px; }}
  .card {{ border:1px solid #e2e8f0; border-radius:8px; padding:14px; }}
  .card-title {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; color:#64748b; margin-bottom:8px; }}
  .card p {{ color:#334155; line-height:1.6; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:16px; }}
  thead tr {{ background:#f1f5f9; }}
  th {{ padding:8px; text-align:left; font-size:11px; font-weight:700; text-transform:uppercase; color:#64748b; letter-spacing:.4px; }}
  .totals {{ text-align:right; }}
  .totals table {{ width:280px; margin-left:auto; }}
  .totals td {{ padding:4px 8px; }}
  .totals .total-row td {{ font-weight:800; font-size:14px; color:#1e3a5f; border-top:2px solid #1e3a5f; padding-top:8px; }}
  .footer {{ background:#f8fafc; border-top:1px solid #e2e8f0; padding:16px 32px; text-align:center; color:#94a3b8; font-size:11px; }}
  .notes {{ background:#f8fafc; border-left:3px solid #2563eb; padding:10px 14px; border-radius:4px; margin-bottom:16px; color:#334155; }}
  @media print {{ body {{ background:#fff; }} .page {{ box-shadow:none; margin:0; border-radius:0; }} button {{ display:none; }} }}
</style>
</head><body>
<div class="page">
  <div class="header">
    <div>
      <div style="font-size:11px;opacity:.7;margin-bottom:2px">{company.get('nome_fantasia','')}</div>
      <h1>{title}</h1>
      <div class="num">{num} &nbsp;·&nbsp; {q['created_at'][:10] if q['created_at'] else ''}</div>
      <div class="badge">Válido até {q['valid_until'] or 'N/A'}</div>
    </div>
    <div style="text-align:right">
      <div style="font-weight:700;font-size:15px">{company.get('razao_social','')}</div>
      <div style="opacity:.8;margin-top:4px">CNPJ: {company.get('cnpj','')}</div>
      <div style="opacity:.8">{company.get('logradouro','')} {company.get('numero','')}, {company.get('cidade','')} - {company.get('uf','')}</div>
      <div style="opacity:.8">{company.get('email','')} | {company.get('telefone','')}</div>
    </div>
  </div>
  <div class="body">
    <div class="grid2">
      <div class="card">
        <div class="card-title">Cliente / Destinatário</div>
        <p><strong>{q.get('contact_name','Não informado')}</strong></p>
        <p>{q.get('contact_doc','')}</p>
        <p>{q.get('contact_email','')}</p>
        <p>{q.get('contact_phone','')}</p>
      </div>
      <div class="card">
        <div class="card-title">Condições Comerciais</div>
        <p><strong>Pagamento:</strong> {q.get('payment_terms','')}</p>
        <p><strong>Vendedor:</strong> {q.get('seller_name') or '—'}</p>
        <p><strong>Validade:</strong> {q.get('valid_until','')}</p>
        <p><strong>Status:</strong> {STATUS_LABELS.get(q['status'], q['status'])}</p>
      </div>
    </div>
    <table>
      <thead><tr>
        <th style="width:30px">#</th>
        <th>Produto / Serviço</th>
        <th style="text-align:center;width:100px">Qtd / Un</th>
        <th style="text-align:right;width:100px">V. Unit.</th>
        <th style="text-align:right;width:80px">Desconto</th>
        <th style="text-align:right;width:110px">Total</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div class="totals">
      <table>
        <tr><td>Subtotal:</td><td>R$ {q['subtotal']:,.2f}</td></tr>
        <tr><td>Desconto:</td><td style="color:#dc2626">- R$ {q['discount_amount']:,.2f}</td></tr>
        <tr><td>Frete:</td><td>R$ {q['shipping_amount']:,.2f}</td></tr>
        <tr class="total-row"><td>TOTAL:</td><td>R$ {q['total_amount']:,.2f}</td></tr>
      </table>
    </div>
    {f'<div class="notes"><strong>Observações:</strong> {q["notes"]}</div>' if q.get('notes') else ''}
  </div>
  <div class="footer">
    {company.get('razao_social','')} · CNPJ {company.get('cnpj','')} · {company.get('email','')} · Emitido via Cortex ERP Pro+
    <br><button onclick="window.print()" style="margin-top:8px;background:#2563eb;color:#fff;border:none;padding:6px 18px;border-radius:6px;cursor:pointer;font-size:12px">🖨️ Imprimir / Salvar PDF</button>
  </div>
</div>
</body></html>"""
