import base64
from datetime import date, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Dict, Any

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..schemas.company import CompanyUpdate
    from ..services.crypto_vault import CryptoVault
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from schemas.company import CompanyUpdate
    from services.crypto_vault import CryptoVault

router = APIRouter(prefix="/api/company", tags=["Empresa & Certificado A1"])


@router.get("")
def get_company(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("SELECT * FROM companies WHERE id = ? ORDER BY id LIMIT 1", (company_id,)).fetchone()
    conn.close()
    if not row:
        return {}
    comp = dict(row)
    # Protege a senha do certificado: mascara para nunca expor a senha em claro
    if comp.get("certificado_senha"):
        comp["certificado_senha"] = "******"
        comp["has_certificate"] = True
    else:
        comp["has_certificate"] = False
    return comp


@router.put("")
async def update_company(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    data = await req.json()
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    cur.execute("""
        UPDATE companies SET
            razao_social = COALESCE(?, razao_social),
            nome_fantasia = COALESCE(?, nome_fantasia),
            cnpj = COALESCE(?, cnpj),
            inscricao_estadual = COALESCE(?, inscricao_estadual),
            inscricao_municipal = COALESCE(?, inscricao_municipal),
            regime_tributario = COALESCE(?, regime_tributario),
            cnae_principal = COALESCE(?, cnae_principal),
            aliquota_simples = COALESCE(?, aliquota_simples),
            cep = COALESCE(?, cep),
            logradouro = COALESCE(?, logradouro),
            numero = COALESCE(?, numero),
            bairro = COALESCE(?, bairro),
            cidade = COALESCE(?, cidade),
            uf = COALESCE(?, uf),
            codigo_ibge_municipio = COALESCE(?, codigo_ibge_municipio),
            telefone = COALESCE(?, telefone),
            email = COALESCE(?, email),
            chave_pix = COALESCE(?, chave_pix),
            ambiente_fiscal = COALESCE(?, ambiente_fiscal),
            motor_fiscal = COALESCE(?, motor_fiscal),
            api_fiscal_token = COALESCE(?, api_fiscal_token),
            serie_nfe = COALESCE(?, serie_nfe),
            proximo_numero_nfe = COALESCE(?, proximo_numero_nfe),
            serie_nfce = COALESCE(?, serie_nfce),
            proximo_numero_nfce = COALESCE(?, proximo_numero_nfce),
            serie_nfse = COALESCE(?, serie_nfse),
            proximo_numero_nfse = COALESCE(?, proximo_numero_nfse)
        WHERE id = ?
    """, (
        data.get("razao_social"),
        data.get("nome_fantasia"),
        data.get("cnpj"),
        data.get("inscricao_estadual"),
        data.get("inscricao_municipal"),
        data.get("regime_tributario"),
        data.get("cnae_principal"),
        float(data["aliquota_simples"]) if data.get("aliquota_simples") is not None else None,
        data.get("cep"),
        data.get("logradouro"),
        data.get("numero"),
        data.get("bairro"),
        data.get("cidade"),
        data.get("uf"),
        data.get("codigo_ibge_municipio"),
        data.get("telefone"),
        data.get("email"),
        data.get("chave_pix"),
        data.get("ambiente_fiscal"),
        data.get("motor_fiscal"),
        data.get("api_fiscal_token"),
        int(data["serie_nfe"]) if data.get("serie_nfe") is not None else None,
        int(data["proximo_numero_nfe"]) if data.get("proximo_numero_nfe") is not None else None,
        int(data["serie_nfce"]) if data.get("serie_nfce") is not None else None,
        int(data["proximo_numero_nfce"]) if data.get("proximo_numero_nfce") is not None else None,
        int(data["serie_nfse"]) if data.get("serie_nfse") is not None else None,
        int(data["proximo_numero_nfse"]) if data.get("proximo_numero_nfse") is not None else None,
        company_id,
    ))
    conn.commit()
    log_audit(conn, action="update", entity="companies", entity_id=company_id, new_data=data, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "message": "Configurações fiscais e da empresa salvas com sucesso!"}


@router.post("/certificate")
async def upload_certificate(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    content_type = req.headers.get("content-type", "")
    cert_name = "certificado_a1.pfx"
    cert_b64 = ""
    password = ""
    company_id = current_user.get("company_id", 1)

    if "multipart/form-data" in content_type:
        form = await req.form()
        file = form.get("file")
        password = form.get("password", "")
        if file and hasattr(file, "read"):
            content = await file.read()
            cert_b64 = base64.b64encode(content).decode("utf-8")
            cert_name = getattr(file, "filename", "certificado_a1.pfx")
    else:
        data = await req.json()
        cert_name = data.get("filename", "certificado_a1.pfx")
        cert_b64 = data.get("content_b64", "")
        password = data.get("password", "")

    # Inspeciona certificado de verdade se houver bytes válidos
    raw_bytes = b""
    try:
        raw_bytes = base64.b64decode(cert_b64)
    except Exception:
        raw_bytes = cert_b64.encode("utf-8")

    inspect_info = CryptoVault.inspect_pfx_certificate(raw_bytes, password)
    validade = inspect_info["valid_to"]
    titular = inspect_info["subject_cn"]

    # Criptografia no Cofre Seguro
    encrypted_cert = CryptoVault.encrypt_string(cert_b64)
    encrypted_pwd = CryptoVault.encrypt_string(password)

    conn = get_conn()
    conn.execute("""
        UPDATE companies
        SET certificado_nome = ?, certificado_validade = ?, certificado_titular = ?, certificado_b64 = ?, certificado_senha = ?
        WHERE id = ?
    """, (cert_name, validade, titular, encrypted_cert, encrypted_pwd, company_id))
    conn.commit()
    log_audit(conn, action="update_cert", entity="companies", entity_id=company_id, user_id=current_user.get("id"))
    conn.close()

    return {
        "status": "ok",
        "message": f"Certificado A1 ({cert_name}) validado e gravado no cofre criptográfico com sucesso!",
        "titular": titular,
        "validade": validade,
        "is_valid_pkcs12": inspect_info["valid"],
    }


@router.get("/certificate/status")
def get_certificate_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    row = conn.execute("SELECT certificado_nome, certificado_validade, certificado_titular, certificado_senha FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()

    if not row or not row["certificado_senha"]:
        return {"installed": False, "message": "Nenhum certificado A1 instalado."}

    val_str = row["certificado_validade"] or ""
    days_left = None
    if val_str:
        try:
            val_date = date.fromisoformat(val_str[:10])
            days_left = (val_date - date.today()).days
        except Exception:
            pass

    return {
        "installed": True,
        "name": row["certificado_nome"],
        "titular": row["certificado_titular"] or "Empresa Emitente",
        "valid_until": val_str,
        "days_remaining": days_left,
        "is_expired": days_left is not None and days_left < 0,
    }
