from datetime import date
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.service_orders import ServiceOrderCreate
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.service_orders import ServiceOrderCreate

router = APIRouter(prefix="/api/service-orders", tags=["Ordens de Serviço"])


@router.get("")
def list_service_orders(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    rows = rows_to_dicts(conn.execute("""
        SELECT o.*, c.name as client_name, c.phone as contact_phone
        FROM service_orders o
        LEFT JOIN contacts c ON c.id = o.contact_id
        ORDER BY o.id DESC
    """).fetchall())
    conn.close()
    for r in rows:
        r["title"] = r.get("equipment") or f"OS #{r.get('os_number', r.get('id'))}"
    return rows


@router.post("")
def save_service_order(req: ServiceOrderCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    next_os = (cur.execute("SELECT MAX(os_number) FROM service_orders").fetchone()[0] or 900) + 1
    total = float(req.total_amount or 0.0)

    cur.execute("""
        INSERT INTO service_orders (
            os_number, contact_id, equipment, brand_model, serial_number, reported_defect,
            technical_report, technician, status, priority, parts_total, labor_total,
            discount, total_amount, warranty_days
        ) VALUES (?, ?, ?, '', ?, ?, ?, ?, 'aberta', 'normal', ?, ?, ?, ?, 90)
    """, (
        next_os,
        req.contact_id or 1,
        req.title or req.equipment or "Equipamento",
        req.serial_number or "",
        req.defect_reported or "",
        req.description or "",
        current_user.get("name", "Técnico"),
        float(req.parts_amount or 0.0),
        float(req.services_amount or total),
        float(req.discount or 0.0),
        total,
    ))
    oid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="service_orders", entity_id=oid, new_data=req.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": oid, "os_number": next_os}


@router.post("/{os_id}/bill")
def bill_service_order(os_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    so = cur.execute("""
        SELECT o.*, c.name as contact_name
        FROM service_orders o LEFT JOIN contacts c ON c.id = o.contact_id
        WHERE o.id = ?
    """, (os_id,)).fetchone()
    if not so:
        conn.close()
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    today_iso = date.today().isoformat()
    cur.execute("""
        INSERT INTO financial_entries (
            company_id, type, description, contact_id, category_id, cost_center_id, bank_account_id,
            payment_method, competence_date, due_date, amount, status, document_number, origin_type, origin_id
        ) VALUES (1, 'receita', ?, ?, 2, 3, 1, 'Pix', ?, ?, ?, 'pendente', ?, 'os', ?)
    """, (
        f"Ordem de Serviço #{so['os_number']} ({so['equipment']}) - {so['contact_name'] or 'Cliente'}",
        so["contact_id"],
        today_iso,
        today_iso,
        float(so["total_amount"]),
        f"OS-{so['os_number']}",
        os_id,
    ))
    cur.execute("UPDATE service_orders SET status = 'faturada', billed = 1, closed_at = CURRENT_TIMESTAMP WHERE id = ?", (os_id,))
    conn.commit()
    log_audit(conn, action="bill_os", entity="service_orders", entity_id=os_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": f"OS #{so['os_number']} finalizada e faturada no Contas a Receber!"}


@router.get("/{os_id}/print", response_class=HTMLResponse)
def print_service_order(os_id: int):
    conn = get_conn()
    company = dict(conn.execute("SELECT * FROM companies LIMIT 1").fetchone())
    so = dict(conn.execute("""
        SELECT o.*, c.name as contact_name, c.document as contact_doc, c.phone as contact_phone
        FROM service_orders o LEFT JOIN contacts c ON c.id = o.contact_id
        WHERE o.id = ?
    """, (os_id,)).fetchone())
    conn.close()
    return f"""<!DOCTYPE html>
    <html lang="pt-BR"><head><meta charset="UTF-8"><title>OS #{so['os_number']}</title>
    <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; font-size: 12px; color:#111; }}
    .box {{ border:1px solid #334155; padding:10px; margin-bottom:10px; border-radius:4px; }}
    @media print {{ .no-print {{ display:none; }} }}
    </style></head><body>
    <div class="no-print" style="margin-bottom:12px;text-align:right;">
      <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold;">Imprimir OS</button>
    </div>
    <div class="box" style="display:flex;justify-content:space-between;align-items:center;">
      <div><h2 style="margin:0;">{company['nome_fantasia']}</h2><div>CNPJ: {company['cnpj']} | Tel: {company['telefone']}</div></div>
      <div style="text-align:right;"><div style="font-size:18px;font-weight:bold;">ORDEM DE SERVIÇO Nº {so['os_number']}</div><div>Status: {so['status'].upper()} | Garantia: {so['warranty_days']} dias</div></div>
    </div>
    <div class="box"><b>CLIENTE:</b> {so.get('contact_name')} | <b>CPF/CNPJ:</b> {so.get('contact_doc')} | <b>TEL:</b> {so.get('contact_phone')}</div>
    <div class="box"><b>EQUIPAMENTO:</b> {so['equipment']} ({so.get('brand_model', '')}) — <b>Nº SÉRIE:</b> {so.get('serial_number', '-')}</div>
    <div class="box"><b>DEFEITO RELATADO:</b><br>{so.get('reported_defect') or 'Não informado'}</div>
    <div class="box"><b>LAUDO TÉCNICO E SERVIÇOS EXECUTADOS:</b><br>{so.get('technical_report') or 'Serviço executado conforme padrão de fábrica.'}</div>
    <div class="box" style="text-align:right;font-size:16px;font-weight:bold;color:#2563eb;">
      VALOR TOTAL: R$ {so['total_amount']:,.2f}
    </div>
    </body></html>"""
