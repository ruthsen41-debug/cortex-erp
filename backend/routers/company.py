import base64
import secrets
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

try:
    from ..database import get_conn, _seed_accounting_accounts, _seed_default_rubrics, _seed_default_accumulators
    from ..auth import get_current_user, log_audit, create_access_token
    from ..utils import rows_to_dicts
    from ..schemas.company import CompanyUpdate
    from ..services.crypto_vault import CryptoVault
except ImportError:
    from database import get_conn, _seed_accounting_accounts, _seed_default_rubrics, _seed_default_accumulators
    from auth import get_current_user, log_audit, create_access_token
    from utils import rows_to_dicts
    from services.crypto_vault import CryptoVault

router = APIRouter(prefix="/api/company", tags=["Empresa & Certificado A1"])


class CompanyCreatePayload(BaseModel):
    razao_social: str
    nome_fantasia: str = ""
    cnpj: str = ""
    regime_tributario: str = "simples_nacional"
    uf: str = "MT"
    cidade: str = "Cuiabá"
    inscricao_estadual: str = ""
    inscricao_municipal: str = ""
    email: str = ""
    telefone: str = ""
    contador_nome: str = ""
    contador_cpf: str = ""
    contador_crc: str = ""


class CompanySwitchPayload(BaseModel):
    company_id: int


def _sanitize_company(row: Any) -> Dict[str, Any]:
    comp = dict(row)
    if comp.get("certificado_senha"):
        comp["certificado_senha"] = "******"
        comp["has_certificate"] = True
    else:
        comp["has_certificate"] = False
    return comp


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
            proximo_numero_nfse = COALESCE(?, proximo_numero_nfse),
            complemento = COALESCE(?, complemento),
            csc_id = COALESCE(?, csc_id),
            csc_token = COALESCE(?, csc_token)
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
        data.get("complemento"),
        data.get("csc_id"),
        data.get("csc_token"),
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


# =====================================================
# MULTIEMPRESA DE ESCRITÓRIO CONTÁBIL
# =====================================================

@router.get("/list")
def list_companies(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Lista todas as empresas acessíveis pelo usuário logado (escritório contábil)."""
    conn = get_conn()
    active_id = current_user.get("company_id", 1)
    role = (current_user.get("role") or "").lower()
    if role in ("admin", "contador", "contabil"):
        rows = conn.execute("SELECT * FROM companies ORDER BY id").fetchall()
    else:
        rows = conn.execute("""
            SELECT DISTINCT c.*
            FROM companies c
            LEFT JOIN user_companies uc ON uc.company_id = c.id AND uc.user_id = ?
            WHERE c.id = ? OR uc.user_id IS NOT NULL
            ORDER BY c.id
        """, (current_user["id"], active_id)).fetchall()
    conn.close()
    return {
        "active_company_id": active_id,
        "companies": [_sanitize_company(r) for r in rows],
    }


@router.post("/create", status_code=201)
def create_client_company(
    data: CompanyCreatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Cria uma nova empresa-cliente no escritório contábil com plano de contas, rubricas e acumuladores."""
    if not data.razao_social.strip():
        raise HTTPException(status_code=400, detail="Razão social é obrigatória.")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO companies (
            razao_social, nome_fantasia, cnpj, inscricao_estadual, inscricao_municipal,
            regime_tributario, uf, cidade, email, telefone,
            contador_nome, contador_cpf, contador_crc,
            accountant_token, ambiente_fiscal, motor_fiscal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'homologacao', 'sefaz_direto')
    """, (
        data.razao_social.strip(),
        (data.nome_fantasia or data.razao_social).strip(),
        data.cnpj.strip(),
        data.inscricao_estadual.strip(),
        data.inscricao_municipal.strip(),
        data.regime_tributario or "simples_nacional",
        (data.uf or "MT").upper()[:2],
        data.cidade or "Cuiabá",
        data.email.strip(),
        data.telefone.strip(),
        data.contador_nome.strip(),
        data.contador_cpf.strip(),
        data.contador_crc.strip(),
        secrets.token_urlsafe(16),
    ))
    new_company_id = cur.lastrowid

    # Conta bancária inicial, Plano de Contas, Rubricas DP e Acumuladores Fiscais
    cur.execute("""
        INSERT INTO bank_accounts (company_id, name, bank_code, bank_name, account_type, initial_balance, current_balance)
        VALUES (?, 'Caixa Geral', '000', 'Caixa Interno', 'caixa', 0.0, 0.0)
    """, (new_company_id,))
    _seed_accounting_accounts(cur, new_company_id)
    _seed_default_rubrics(cur, new_company_id)
    _seed_default_accumulators(cur, new_company_id)
    cur.execute(
        "INSERT OR IGNORE INTO user_companies (user_id, company_id, role) VALUES (?, ?, ?)",
        (current_user["id"], new_company_id, current_user.get("role", "contador")),
    )
    conn.commit()
    comp_row = conn.execute("SELECT * FROM companies WHERE id = ?", (new_company_id,)).fetchone()
    log_audit(conn, action="create", entity="companies", entity_id=new_company_id, user_id=current_user.get("id"), company_id=new_company_id)
    conn.close()
    return {"id": new_company_id, "company": _sanitize_company(comp_row)}


@router.post("/switch")
def switch_company(
    data: CompanySwitchPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Troca a empresa ativa do usuário logado sem precisar refazer login."""
    conn = get_conn()
    target = conn.execute("SELECT * FROM companies WHERE id = ?", (data.company_id,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    role = (current_user.get("role") or "").lower()
    if role not in ("admin", "contador", "contabil") and data.company_id != current_user.get("company_id"):
        link = conn.execute(
            "SELECT id FROM user_companies WHERE user_id = ? AND company_id = ?",
            (current_user["id"], data.company_id),
        ).fetchone()
        if not link:
            conn.close()
            raise HTTPException(status_code=403, detail="Usuário sem acesso a esta empresa.")

    conn.execute("UPDATE users SET company_id = ? WHERE id = ?", (data.company_id, current_user["id"]))
    conn.commit()
    new_token = create_access_token({
        "sub": current_user["email"],
        "uid": current_user["id"],
        "role": current_user["role"],
        "company_id": data.company_id,
    })
    log_audit(conn, action="switch_company", entity="companies", entity_id=data.company_id,
              user_id=current_user["id"], company_id=data.company_id)
    conn.close()
    return {
        "status": "ok",
        "company_id": data.company_id,
        "company": _sanitize_company(target),
        "access_token": new_token,
    }
