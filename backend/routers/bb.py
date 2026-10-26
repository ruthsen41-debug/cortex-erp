"""
Endpoints da integração Banco do Brasil (modelo ISV — multi-empresa):

  OAuth / Conexão:
    GET  /api/bb/oauth/authorize          — URL de autorização para o cliente conectar sua conta BB
    GET  /api/bb/oauth/callback           — callback público; troca code por tokens e salva no banco
    GET  /api/bb/oauth/status             — lista empresas conectadas e status dos tokens
    DELETE /api/bb/oauth/disconnect       — remove tokens de uma empresa

  Operacional:
    GET  /api/bb/status                   — configuração geral + cobranças recentes
    GET  /api/bb/gerar-csr                — gera chave privada + CSR para mTLS
    POST /api/bb/boleto/{entry_id}        — emite boleto registrado
    GET  /api/bb/boleto/{numero}/consulta — consulta situação do boleto
    DELETE /api/bb/boleto/{numero}        — cancela (baixa) boleto
    POST /api/bb/pix/{entry_id}           — cria cobrança Pix dinâmica
    POST /api/bb/extrato/sync             — importa extrato v2 → conciliação
    POST /api/bb/webhook                  — recebe confirmação Pix do BB
"""
import os
import re
from datetime import date, timedelta
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse

try:
    from ..database import get_conn, begin_write, recalculate_bank_balances
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..services.bb_client import (
        get_authorization_url,
        exchange_code_for_token,
        get_company_token_row,
        remove_company_token,
        is_company_connected,
        emitir_boleto,
        cancelar_boleto,
        consultar_boleto,
        criar_cobranca_pix,
        consultar_extrato,
        normalize_extrato_date,
        gerar_csr,
        is_configured,
        mtls_active,
        BB_SANDBOX,
    )
    from ..services.payment_gateway import generate_qr_code_base64
    from .ofx import _score_match
except ImportError:
    from database import get_conn, begin_write, recalculate_bank_balances
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from services.bb_client import (
        get_authorization_url,
        exchange_code_for_token,
        get_company_token_row,
        remove_company_token,
        is_company_connected,
        emitir_boleto,
        cancelar_boleto,
        consultar_boleto,
        criar_cobranca_pix,
        consultar_extrato,
        normalize_extrato_date,
        gerar_csr,
        is_configured,
        mtls_active,
        BB_SANDBOX,
    )
    from services.payment_gateway import generate_qr_code_base64
    from routers.ofx import _score_match

router = APIRouter(prefix="/api/bb", tags=["Banco do Brasil"])

# URL base do ERP (usada como redirect_uri no OAuth)
_ERP_BASE_URL = os.getenv("ERP_BASE_URL", "https://cortex-erp.onrender.com")
_REDIRECT_URI = f"{_ERP_BASE_URL}/api/bb/oauth/callback"


def _require_config():
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Banco do Brasil não configurado. "
                "Defina BB_CLIENT_ID, BB_CLIENT_SECRET e BB_APP_KEY nas variáveis de ambiente."
            ),
        )


def _require_connected(company_id: int):
    if not is_company_connected(company_id):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Empresa {company_id} não autorizou o acesso ao Banco do Brasil. "
                "Acesse GET /api/bb/oauth/authorize para iniciar a conexão."
            ),
        )


def _get_entry(cur, entry_id: int, company_id: int) -> Dict[str, Any]:
    row = cur.execute("""
        SELECT e.*,
               c.name         AS contact_name,
               c.document     AS contact_doc,
               c.email        AS contact_email,
               c.phone        AS contact_phone,
               c.cep          AS contact_cep,
               c.street       AS contact_street,
               c.neighborhood AS contact_neighborhood,
               c.city         AS contact_city,
               c.state        AS contact_state
        FROM financial_entries e
        LEFT JOIN contacts c ON c.id = e.contact_id
        WHERE e.id = ? AND e.company_id = ?
    """, (entry_id, company_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Lançamento financeiro não encontrado.")
    return dict(row)


# ===========================================================================
# OAUTH — CONEXÃO DA EMPRESA
# ===========================================================================

@router.get("/oauth/authorize")
def bb_oauth_authorize(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Gera a URL de autorização do Banco do Brasil e redireciona o navegador do
    usuário para que ele faça login no BB e autorize o acesso do Cortex ERP.
    Após autorizar, o BB redireciona para /api/bb/oauth/callback automaticamente.
    """
    _require_config()
    company_id = current_user.get("company_id", 1)
    auth_url = get_authorization_url(company_id, _REDIRECT_URI)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/oauth/callback")
def bb_oauth_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
):
    """
    Callback público chamado pelo Banco do Brasil após o cliente autorizar.
    Troca o authorization_code por access_token + refresh_token e salva no banco.
    Redireciona para o frontend com mensagem de sucesso ou erro.
    """
    if error:
        return RedirectResponse(
            url=f"{_ERP_BASE_URL}/#/bb-connect?error={error}&desc={error_description}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="Parâmetros 'code' e 'state' são obrigatórios.")

    try:
        result = exchange_code_for_token(code, _REDIRECT_URI, state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao obter tokens do BB: {e}")

    company_id = result.get("company_id")
    return RedirectResponse(
        url=f"{_ERP_BASE_URL}/#/bb-connect?success=1&company_id={company_id}",
        status_code=302,
    )


@router.get("/oauth/status")
def bb_oauth_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Lista o status de conexão BB da empresa logada."""
    _require_config()
    company_id = current_user.get("company_id", 1)
    token_row = get_company_token_row(company_id)
    connected = token_row is not None
    return {
        "configured": is_configured(),
        "sandbox": BB_SANDBOX,
        "mtls_active": mtls_active(),
        "connected": connected,
        "expires_at": token_row.get("expires_at") if token_row else None,
        "scope": token_row.get("scope") if token_row else None,
        "updated_at": token_row.get("updated_at") if token_row else None,
        "authorize_url": f"{_ERP_BASE_URL}/api/bb/oauth/authorize" if not connected else None,
    }


@router.delete("/oauth/disconnect")
def bb_oauth_disconnect(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Remove os tokens BB da empresa, desconectando-a da integração."""
    company_id = current_user.get("company_id", 1)
    remove_company_token(company_id)
    log_audit(
        get_conn(), action="bb_oauth_disconnect", entity="bb_oauth_tokens",
        new_data={"company_id": company_id}, user_id=current_user.get("id")
    )
    return {"status": "ok", "message": "Conexão com o Banco do Brasil removida com sucesso."}


# ===========================================================================
# STATUS GERAL
# ===========================================================================

@router.get("/status")
def bb_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    recent = rows_to_dicts(conn.execute(
        "SELECT id, entry_id, billing_type, status, value, due_date, created_at "
        "FROM payment_charges WHERE gateway = 'banco_do_brasil' AND company_id = ? "
        "ORDER BY created_at DESC LIMIT 20",
        (company_id,)
    ).fetchall())
    conn.close()
    token_row = get_company_token_row(company_id)
    return {
        "configured": is_configured(),
        "sandbox": BB_SANDBOX,
        "mtls_active": mtls_active(),
        "connected": token_row is not None,
        "token_expires_at": token_row.get("expires_at") if token_row else None,
        "recent_charges": recent,
    }


# ===========================================================================
# CSR mTLS
# ===========================================================================

@router.get("/gerar-csr")
def gerar_csr_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Gera par RSA 2048-bit + CSR para submissão no portal BB Developers (Certificado mTLS).
    A chave privada é salva em data/bb_mtls.key. O CSR retornado vai para o portal BB.
    """
    company_id = current_user.get("company_id", 1)
    conn = get_conn()
    comp = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    if not comp:
        raise HTTPException(status_code=404, detail="Cadastre os dados da empresa primeiro.")

    comp = dict(comp)
    try:
        result = gerar_csr(
            company_name=comp.get("razao_social") or comp.get("nome_fantasia") or "Empresa",
            cnpj=comp.get("cnpj") or "00000000000000",
            state=comp.get("uf") or comp.get("estado") or "MT",
            city=comp.get("cidade") or "Cuiabá",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar CSR: {e}")

    return {
        "status": "ok",
        "csr_pem": result["csr_pem"],
        "key_path": result["key_path"],
        "instrucoes": result["instrucoes"],
        "proximos_passos": [
            "1. Copie 'csr_pem' inteiro e cole em developers.bb.com.br → Aplicação → Certificado mTLS",
            "2. BB assina e devolve um arquivo .crt",
            "3. Salve o .crt no servidor e configure no .env:",
            f"   BB_KEY_PATH={result['key_path']}",
            "   BB_CERT_PATH=/caminho/para/certificado.crt",
            "4. Reinicie — mTLS é ativado automaticamente",
        ],
    }


# ===========================================================================
# BOLETO
# ===========================================================================

@router.post("/boleto/{entry_id}")
def emitir_boleto_entry(
    entry_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Emite boleto registrado no BB para um lançamento financeiro."""
    _require_config()
    company_id = current_user.get("company_id", 1)
    _require_connected(company_id)

    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT * FROM payment_charges WHERE entry_id = ? AND billing_type = 'BOLETO' "
        "AND gateway = 'banco_do_brasil' AND status = 'PENDING'",
        (entry_id,)
    ).fetchone()
    if existing:
        conn.close()
        return dict(existing)

    entry = _get_entry(cur, entry_id, company_id)

    try:
        result = emitir_boleto(
            company_id=company_id,
            nosso_numero=entry_id,
            valor=float(entry["amount"]),
            vencimento=entry["due_date"],
            pagador_nome=entry.get("contact_name") or "Consumidor Final",
            pagador_doc=entry.get("contact_doc") or "00000000000",
            pagador_cep=entry.get("contact_cep") or "78000000",
            pagador_endereco=entry.get("contact_street") or "Endereço não informado",
            pagador_bairro=entry.get("contact_neighborhood") or "Centro",
            pagador_cidade=entry.get("contact_city") or "Cuiabá",
            pagador_uf=entry.get("contact_state") or "MT",
            descricao=(entry.get("description") or "")[:30],
        )
    except RuntimeError as e:
        conn.close()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=502, detail=f"Erro na API do Banco do Brasil: {e}")

    linha_digitavel = result.get("codigoLinhaDigitavel", "")
    codigo_barras = result.get("codigoBarraNumerico", "")
    numero_boleto = str(result.get("numero", entry_id))
    qr_data = result.get("qrCode") or {}
    pix_payload = qr_data.get("emv", "")
    pix_url = qr_data.get("url", "")
    pix_qr_b64 = generate_qr_code_base64(pix_payload) if pix_payload else ""
    gw_id = f"bb-bol-{numero_boleto}"

    cur.execute("""
        INSERT INTO payment_charges (
            company_id, entry_id, gateway, gateway_id, billing_type,
            status, value, due_date, pix_copy_paste, pix_qr_code_b64,
            bank_slip_url, invoice_url, customer_id
        ) VALUES (?, ?, 'banco_do_brasil', ?, 'BOLETO', 'PENDING', ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id, entry_id, gw_id, float(entry["amount"]), entry["due_date"],
        pix_payload, pix_qr_b64, linha_digitavel, pix_url,
        entry.get("contact_doc") or "",
    ))
    charge_id = cur.lastrowid
    try:
        cur.execute(
            "UPDATE payment_charges SET linha_digitavel=?, codigo_barras=?, numero_boleto_bb=? WHERE id=?",
            (linha_digitavel, codigo_barras, numero_boleto, charge_id),
        )
    except Exception:
        pass

    log_audit(conn, action="emit_boleto_bb", entity="payment_charges", entity_id=charge_id,
              new_data={"entry_id": entry_id, "valor": entry["amount"]}, user_id=current_user.get("id"))
    conn.close()
    return {
        "status": "ok",
        "charge_id": charge_id,
        "linha_digitavel": linha_digitavel,
        "codigo_barras": codigo_barras,
        "pix_copia_cola": pix_payload,
        "pix_qr_code_b64": pix_qr_b64,
        "numero_boleto": numero_boleto,
        "vencimento": entry["due_date"],
        "valor": float(entry["amount"]),
        "message": "Boleto emitido com sucesso no Banco do Brasil!",
    }


@router.get("/boleto/{numero_boleto}/consulta")
def consultar_boleto_endpoint(numero_boleto: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    _require_config()
    company_id = current_user.get("company_id", 1)
    _require_connected(company_id)
    try:
        return consultar_boleto(company_id, numero_boleto)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar boleto: {e}")


@router.delete("/boleto/{numero_boleto}")
def cancelar_boleto_endpoint(numero_boleto: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    _require_config()
    company_id = current_user.get("company_id", 1)
    _require_connected(company_id)
    try:
        result = cancelar_boleto(company_id, numero_boleto)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao cancelar boleto: {e}")

    conn = get_conn()
    conn.execute(
        "UPDATE payment_charges SET status='CANCELLED', updated_at=CURRENT_TIMESTAMP "
        "WHERE gateway_id=? AND company_id=?",
        (f"bb-bol-{numero_boleto}", company_id),
    )
    conn.commit()
    log_audit(conn, action="cancel_boleto_bb", entity="payment_charges",
              new_data={"numero": numero_boleto}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": f"Boleto {numero_boleto} cancelado.", "result": result}


# ===========================================================================
# PIX
# ===========================================================================

@router.post("/pix/{entry_id}")
def criar_pix_entry(entry_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cria cobrança Pix dinâmica no BB para um lançamento financeiro."""
    _require_config()
    company_id = current_user.get("company_id", 1)
    _require_connected(company_id)

    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT * FROM payment_charges WHERE entry_id=? AND billing_type='PIX' "
        "AND gateway='banco_do_brasil' AND status='PENDING'",
        (entry_id,)
    ).fetchone()
    if existing:
        conn.close()
        return dict(existing)

    entry = _get_entry(cur, entry_id, company_id)
    txid = f"cortex{entry_id:020d}"

    try:
        result = criar_cobranca_pix(
            company_id=company_id,
            txid=txid,
            valor=float(entry["amount"]),
            devedor_nome=entry.get("contact_name") or "Consumidor Final",
            devedor_doc=entry.get("contact_doc") or "00000000000",
            descricao=(entry.get("description") or "Pagamento Cortex ERP")[:140],
        )
    except RuntimeError as e:
        conn.close()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=502, detail=f"Erro na API Pix do BB: {e}")

    pix_payload = result.get("pixCopiaECola", "")
    pix_location = result.get("location", "")
    pix_qr_b64 = generate_qr_code_base64(pix_payload) if pix_payload else ""
    gw_id = f"bb-pix-{txid}"

    cur.execute("""
        INSERT INTO payment_charges (
            company_id, entry_id, gateway, gateway_id, billing_type,
            status, value, due_date, pix_copy_paste, pix_qr_code_b64,
            bank_slip_url, invoice_url, customer_id
        ) VALUES (?, ?, 'banco_do_brasil', ?, 'PIX', 'PENDING', ?, ?, ?, ?, '', ?, ?)
    """, (
        company_id, entry_id, gw_id, float(entry["amount"]), entry["due_date"],
        pix_payload, pix_qr_b64, pix_location, entry.get("contact_doc") or "",
    ))
    charge_id = cur.lastrowid
    log_audit(conn, action="create_pix_bb", entity="payment_charges", entity_id=charge_id,
              new_data={"entry_id": entry_id, "txid": txid}, user_id=current_user.get("id"))
    conn.close()
    return {
        "status": "ok",
        "charge_id": charge_id,
        "pix_copia_cola": pix_payload,
        "pix_qr_code_b64": pix_qr_b64,
        "location": pix_location,
        "txid": txid,
        "valor": float(entry["amount"]),
        "message": "Cobrança Pix criada com sucesso no Banco do Brasil!",
    }


# ===========================================================================
# EXTRATO
# ===========================================================================

@router.post("/extrato/sync")
def sync_extrato_bb(dias: int = 30, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Importa extrato BB v2 para conciliação bancária (últimos N dias, máx 90)."""
    _require_config()
    company_id = current_user.get("company_id", 1)
    _require_connected(company_id)

    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()

    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=min(dias, 90))

    try:
        lancamentos = consultar_extrato(company_id, data_inicio.isoformat(), data_fim.isoformat(), agencia, conta)
    except RuntimeError as e:
        conn.close()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=502, detail=f"Erro ao buscar extrato do BB: {e}")

    bank_acc = cur.execute(
        "SELECT id, agency, account_number FROM bank_accounts WHERE bank_code='001' AND company_id=? AND active=1 LIMIT 1",
        (company_id,)
    ).fetchone()
    bank_acc_id = bank_acc["id"] if bank_acc else 1

    if bank_acc:
        agencia_raw = bank_acc["agency"] or os.getenv("BB_AGENCIA", "")
        conta_raw = bank_acc["account_number"] or os.getenv("BB_CONTA", "")
    else:
        agencia_raw = os.getenv("BB_AGENCIA", "")
        conta_raw = os.getenv("BB_CONTA", "")
    agencia = int(re.sub(r"\D", "", agencia_raw) or "0")
    conta = int(re.sub(r"\D", "", conta_raw) or "0")
    if not agencia or not conta:
        conn.close()
        raise HTTPException(
            status_code=422,
            detail=(
                "Conta BB sem agência/número cadastrados. "
                "Cadastre a conta corrente BB com agência e número, ou defina BB_AGENCIA e BB_CONTA."
            ),
        )

    categories = rows_to_dicts(cur.execute("SELECT * FROM categories").fetchall())
    open_entries = rows_to_dicts(cur.execute(
        "SELECT id, type, amount, due_date FROM financial_entries "
        "WHERE status IN ('pendente','parcial') AND company_id=?", (company_id,)
    ).fetchall())

    imported = 0
    for txn in lancamentos:
        fitid = str(txn.get("codigoLancamento") or "")
        if not fitid:
            continue
        if cur.execute(
            "SELECT id FROM ofx_transactions WHERE fitid=? AND company_id=?", (fitid, company_id)
        ).fetchone():
            continue

        raw_val = float(txn.get("valorLancamento") or 0)
        posted_date = normalize_extrato_date(str(txn.get("dataLancamento") or data_fim.isoformat())[:10])
        memo = txn.get("textoLancamento") or "Lançamento BB"
        is_credit = raw_val > 0
        memo_low = memo.lower()

        best_match_id = None
        best_score = 0.5
        for oe in open_entries:
            score = _score_match(abs(raw_val), posted_date, float(oe["amount"]), oe["due_date"], oe["type"], is_credit)
            if score > best_score:
                best_score = score
                best_match_id = oe["id"]

        sug_cat_id = 1 if is_credit else 11
        for cat in categories:
            if (is_credit and cat["type"] == "receita") or (not is_credit and cat["type"] == "despesa"):
                kws = [k.strip().lower() for k in (cat.get("keywords") or "").split(",") if k.strip()]
                if any(k in memo_low for k in kws):
                    sug_cat_id = cat["id"]
                    break

        cur.execute("""
            INSERT INTO ofx_transactions (
                company_id, bank_account_id, fitid, posted_date, amount,
                memo, suggested_category_id, matched_entry_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente')
        """, (company_id, bank_acc_id, fitid, posted_date, raw_val, memo, sug_cat_id, best_match_id))
        imported += 1

    recalculate_bank_balances(conn)
    log_audit(conn, action="sync_extrato_bb", entity="bank_accounts", entity_id=bank_acc_id,
              new_data={"imported": imported, "dias": dias}, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "imported": imported,
            "message": f"{imported} lançamento(s) importado(s) do extrato BB!"}


# ===========================================================================
# WEBHOOK PIX
# ===========================================================================

@router.post("/webhook")
async def bb_webhook(req: Request):
    """
    Recebe confirmações de pagamento Pix do BB e baixa automaticamente o lançamento no ERP.
    Formato: { "pix": [{ "txid", "valor", "horario", "pagador": {...} }] }
    """
    try:
        payload = await req.json()
    except Exception:
        return {"status": "ignored"}

    pix_events = payload.get("pix", [])
    if not pix_events:
        return {"status": "ignored"}

    conn = get_conn()
    begin_write(conn)
    cur = conn.cursor()
    settled = 0

    for event in pix_events:
        txid = str(event.get("txid", ""))
        if not txid:
            continue
        valor_pago = float(event.get("valor") or 0)
        horario = str(event.get("horario") or date.today().isoformat())[:10]

        charge = cur.execute(
            "SELECT * FROM payment_charges WHERE gateway_id=? AND gateway='banco_do_brasil'",
            (f"bb-pix-cortex{txid}",)
        ).fetchone()
        if not charge:
            charge = cur.execute(
                "SELECT * FROM payment_charges WHERE gateway_id LIKE ? AND gateway='banco_do_brasil'",
                (f"bb-pix-%{txid[:20]}%",)
            ).fetchone()
        if not charge:
            continue

        charge = dict(charge)
        if charge["status"] in ("CONFIRMED", "RECEIVED"):
            continue

        cur.execute(
            "UPDATE payment_charges SET status='CONFIRMED', payment_date=?, net_value=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (horario, valor_pago, charge["id"]),
        )
        cur.execute(
            "UPDATE financial_entries SET paid_amount=amount, status='pago' WHERE id=? AND status!='pago'",
            (charge["entry_id"],),
        )
        entry = cur.execute(
            "SELECT bank_account_id FROM financial_entries WHERE id=?", (charge["entry_id"],)
        ).fetchone()
        ba_id = (entry["bank_account_id"] if entry else None) or 1
        cur.execute("""
            INSERT INTO financial_payments (
                entry_id, bank_account_id, payment_date, principal_paid,
                total_cash_flow, payment_method, notes
            ) VALUES (?, ?, ?, ?, ?, 'PIX', 'Baixa automática via webhook Banco do Brasil')
        """, (charge["entry_id"], ba_id, horario, valor_pago, valor_pago))
        settled += 1

    recalculate_bank_balances(conn)
    conn.close()
    return {"status": "ok", "settled": settled}
