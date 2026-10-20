from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Optional, Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
    from ..services.payment_gateway import PaymentGatewayService
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts
    from services.payment_gateway import PaymentGatewayService

router = APIRouter(prefix="/api/payments", tags=["Gateway de Pagamento & Cobranças"])


@router.post("/charge/{entry_id}")
async def generate_charge(entry_id: int, req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Gera cobrança no Gateway (Asaas: PIX, BOLETO ou CREDIT_CARD)."""
    try:
        data = await req.json()
    except Exception:
        data = {}

    billing_type = data.get("billing_type", "PIX").upper()
    if billing_type not in ("PIX", "BOLETO", "CREDIT_CARD"):
        billing_type = "PIX"

    company_id = current_user.get("company_id", 1)
    try:
        charge = await PaymentGatewayService.create_charge(entry_id, billing_type=billing_type, company_id=company_id)
        return {"status": "ok", "charge": charge}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/charge/{entry_id}")
def get_charge_details(entry_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retorna detalhes da cobrança ativa para o título informado."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    charge = conn.execute(
        "SELECT * FROM payment_charges WHERE entry_id = ? AND company_id = ? ORDER BY id DESC LIMIT 1",
        (entry_id, company_id),
    ).fetchone()
    conn.close()
    if not charge:
        raise HTTPException(status_code=404, detail="Nenhuma cobrança gerada para este título.")
    return dict(charge)


@router.get("/charges")
def list_charges(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Lista todas as cobranças emitidas pelo gateway."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute("""
        SELECT c.*, e.description, e.due_date as entry_due_date, ct.name as client_name
        FROM payment_charges c
        JOIN financial_entries e ON e.id = c.entry_id
        LEFT JOIN contacts ct ON ct.id = e.contact_id
        WHERE c.company_id = ?
        ORDER BY c.id DESC
    """, (company_id,)).fetchall())
    conn.close()
    return rows


@router.post("/webhook")
async def payment_webhook(req: Request):
    """
    Webhook receptor do Gateway (ex: Asaas).
    Recebe eventos de pagamento confirmado, liquidação via Pix e baixa automaticamente no ERP.
    """
    try:
        payload = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload inválido.")

    result = PaymentGatewayService.process_webhook_event(payload)
    return result


@router.get("/bank-slip/{gateway_id}", response_class=HTMLResponse)
def view_bank_slip(gateway_id: str):
    """Renderiza visualização impressa do Boleto Bancário."""
    conn = get_conn()
    charge = conn.execute("SELECT * FROM payment_charges WHERE gateway_id = ?", (gateway_id,)).fetchone()
    if not charge:
        conn.close()
        raise HTTPException(status_code=404, detail="Boleto não encontrado.")

    entry = conn.execute("SELECT * FROM financial_entries WHERE id = ?", (charge["entry_id"],)).fetchone()
    comp = conn.execute("SELECT * FROM companies LIMIT 1").fetchone()
    conn.close()

    linha_digitavel = f"34191.79001 01043.510047 91020.150008 4 99990000{int(charge['value'] * 100):06d}"

    return f"""<!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Boleto Bancário - Cortex ERP</title>
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px; font-size: 13px; color: #222; }}
        .slip-box {{ border: 2px dashed #94a3b8; padding: 25px; border-radius: 12px; max-width: 720px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #2563eb; padding-bottom: 12px; }}
        .linha {{ font-family: monospace; font-size: 14px; font-weight: bold; background: #f1f5f9; padding: 8px; text-align: center; margin: 15px 0; border-radius: 6px; }}
        .info-grid {{ display: grid; grid-cols: 2; display: flex; justify-content: space-between; margin: 15px 0; }}
        .barcode-box {{ background: #000; height: 55px; width: 85%; margin: 20px auto; }}
        @media print {{ .no-print {{ display: none; }} }}
      </style>
    </head>
    <body>
      <div class="no-print" style="text-align:center;margin-bottom:15px;">
        <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:10px 20px;border-radius:8px;font-weight:bold;cursor:pointer;">Imprimir Boleto</button>
      </div>
      <div class="slip-box">
        <div class="header">
          <div><h2 style="margin:0;color:#2563eb;">BANCO INTER S.A. | 077-9</h2></div>
          <div style="font-weight:bold;font-size:16px;">RECIBO DO PAGADOR</div>
        </div>
        <div class="linha">{linha_digitavel}</div>
        <div class="info-grid">
          <div>
            <strong>Beneficiário:</strong> {comp['razao_social'] if comp else 'Cortex ERP'}<br>
            <strong>CNPJ:</strong> {comp['cnpj'] if comp else '00.000.000/0001-00'}<br>
            <strong>Espécie:</strong> R$ | <strong>Aceite:</strong> N
          </div>
          <div style="text-align:right;">
            <strong>Vencimento:</strong> {charge['due_date']}<br>
            <strong style="font-size:16px;color:#2563eb;">Valor Documento: R$ {charge['value']:,.2f}</strong><br>
            <strong>Nosso Número:</strong> {charge['gateway_id'][-8:].upper()}
          </div>
        </div>
        <div style="border-top:1px solid #cbd5e1;padding-top:10px;font-size:11px;color:#64748b;">
          Instruções: Pagável em qualquer agência bancária ou internet banking até o vencimento. Após vencimento, cobrar juros de 1% ao mês e multa de 2%.
        </div>
        <div class="barcode-box"></div>
      </div>
    </body>
    </html>"""


@router.get("/receipt/{gateway_id}", response_class=HTMLResponse)
def view_receipt(gateway_id: str):
    """Página de Checkout / Pagamento Online com Pix Copia e Cola e QR Code."""
    conn = get_conn()
    charge = conn.execute("SELECT * FROM payment_charges WHERE gateway_id = ?", (gateway_id,)).fetchone()
    if not charge:
        conn.close()
        raise HTTPException(status_code=404, detail="Cobrança não encontrada.")
    entry = conn.execute("SELECT * FROM financial_entries WHERE id = ?", (charge["entry_id"],)).fetchone()
    conn.close()

    qr_img = f'<img src="data:image/png;base64,{charge["pix_qr_code_b64"]}" style="width:200px;height:200px;margin:15px auto;display:block;" />' if charge["pix_qr_code_b64"] else ''

    return f"""<!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Pagar Fatura - Cortex ERP</title>
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f8fafc; margin: 0; padding: 40px 15px; color: #1e293b; }}
        .card {{ max-width: 480px; margin: 0 auto; background: #fff; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); padding: 30px; text-align: center; border: 1px solid #e2e8f0; }}
        .pix-code {{ background: #f1f5f9; padding: 12px; font-family: monospace; font-size: 11px; word-break: break-all; border-radius: 8px; border: 1px solid #cbd5e1; margin: 15px 0; }}
        .btn {{ background: #2563eb; color: #fff; border: none; padding: 10px 20px; border-radius: 10px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h3 style="margin-top:0;">Fatura Online Cortex ERP</h3>
        <p style="font-size:12px;color:#64748b;">{entry['description'] if entry else 'Cobrança Comercial'}</p>
        <div style="font-size:32px;font-weight:800;color:#10b981;margin:10px 0;">R$ {charge['value']:,.2f}</div>
        <p style="font-size:12px;">Vencimento: <strong>{charge['due_date']}</strong></p>
        <hr style="border:0;border-top:1px solid #e2e8f0;margin:20px 0;">
        <h4 style="margin:0 0 5px 0;">Pague Instantaneamente via Pix</h4>
        {qr_img}
        <div class="pix-code" id="pixCode">{charge['pix_copy_paste']}</div>
        <button class="btn" onclick="navigator.clipboard.writeText(document.getElementById('pixCode').innerText);alert('Código Pix copiado com sucesso!')">Copiar Código Pix</button>
      </div>
    </body>
    </html>"""
