import base64
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(tags=["Certificados Digitais"])


def _parse_cert_info(cert_b64: str, senha: str = "") -> dict:
    """Tenta extrair info do certificado A1 (PFX/P12)."""
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.hazmat.primitives import serialization
        cert_bytes = base64.b64decode(cert_b64)
        priv_key, cert, chain = pkcs12.load_key_and_certificates(
            cert_bytes, senha.encode() if senha else b""
        )
        subject = cert.subject
        cn = ""
        for attr in subject:
            if attr.oid.dotted_string == "2.5.4.3":
                cn = attr.value
                break
        not_after = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after
        return {
            "titular": cn,
            "validade": not_after.strftime("%Y-%m-%d"),
            "dias_restantes": (not_after.date() - date.today()).days,
        }
    except Exception as e:
        return {"titular": "", "validade": "", "dias_restantes": -1, "erro": str(e)}


@router.get("/api/certificates")
def list_certificates(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Lista certificados da empresa com status de validade."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = conn.execute(
        "SELECT certificado_nome, certificado_validade, certificado_titular, certificado_b64 FROM companies WHERE id=?",
        (company_id,)
    ).fetchone()
    conn.close()
    if not comp:
        return {"certificates": []}
    certs = []
    if comp["certificado_nome"]:
        validade = comp["certificado_validade"] or ""
        dias = -1
        if validade:
            try:
                val_date = date.fromisoformat(validade[:10])
                dias = (val_date - date.today()).days
            except Exception:
                pass
        status = "valido" if dias > 30 else ("vencendo" if dias > 0 else "vencido")
        certs.append({
            "tipo": "A1",
            "nome": comp["certificado_nome"],
            "titular": comp["certificado_titular"] or "",
            "validade": validade,
            "dias_restantes": dias,
            "status": status,
            "tem_arquivo": bool(comp["certificado_b64"]),
        })
    # Check additional certificates table
    extra = rows_to_dicts(conn.execute(
        "SELECT * FROM digital_certificates WHERE company_id=? ORDER BY expiry_date", (company_id,)
    ).fetchall()) if False else []  # table created in migrate_db
    return {"certificates": certs + extra}


@router.post("/api/certificates/upload")
async def upload_certificate(
    file: UploadFile = File(...),
    senha: str = Form(""),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Faz upload e extrai informações de um certificado A1 (.pfx/.p12)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    content = await file.read()
    cert_b64 = base64.b64encode(content).decode()
    info = _parse_cert_info(cert_b64, senha)
    conn.execute("""
        UPDATE companies SET
        certificado_nome=?, certificado_validade=?, certificado_titular=?,
        certificado_b64=?, certificado_senha=?
        WHERE id=?
    """, (file.filename, info.get("validade", ""), info.get("titular", ""),
          cert_b64, senha, company_id))
    conn.commit()
    conn.close()
    return {
        "message": "Certificado salvo com sucesso.",
        "nome": file.filename,
        "titular": info.get("titular", ""),
        "validade": info.get("validade", ""),
        "dias_restantes": info.get("dias_restantes", -1),
        "erro": info.get("erro"),
    }


@router.post("/api/certificates/check-expiry")
def check_expiry(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Verifica se há certificados vencendo nos próximos 30 dias."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = conn.execute(
        "SELECT certificado_validade, certificado_nome FROM companies WHERE id=?",
        (company_id,)
    ).fetchone()
    conn.close()
    alerts = []
    if comp and comp["certificado_validade"]:
        try:
            val_date = date.fromisoformat(comp["certificado_validade"][:10])
            dias = (val_date - date.today()).days
            if dias <= 60:
                alerts.append({
                    "nome": comp["certificado_nome"],
                    "validade": comp["certificado_validade"],
                    "dias_restantes": dias,
                    "urgencia": "critico" if dias <= 15 else ("alerta" if dias <= 30 else "aviso"),
                })
        except Exception:
            pass
    return {"alerts": alerts, "total_alerts": len(alerts)}


@router.delete("/api/certificates")
def delete_certificate(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Remove o certificado digital da empresa."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    conn.execute("""
        UPDATE companies SET
        certificado_nome='', certificado_validade='', certificado_titular='',
        certificado_b64='', certificado_senha=''
        WHERE id=?
    """, (company_id,))
    conn.commit()
    conn.close()
    return {"message": "Certificado removido."}


@router.get("/api/certificates/generate-csr")
def generate_csr(
    razao_social: Optional[str] = None,
    cnpj: Optional[str] = None,
    uf: Optional[str] = "SP",
    municipio: Optional[str] = "São Paulo",
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Gera CSR (Certificate Signing Request) para renovação A1."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    comp = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    name = razao_social or (comp["razao_social"] if comp else "Empresa")
    cnpj_v = cnpj or (comp["cnpj"] if comp else "")
    uf_v = uf or (comp["uf"] if comp else "SP")
    mun = municipio or (comp["cidade"] if comp else "São Paulo")
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, uf_v),
            x509.NameAttribute(NameOID.LOCALITY_NAME, mun),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, name),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{name}:{cnpj_v}"),
        ])).sign(key, hashes.SHA256())
        csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()
        key_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ).decode()
        return {"csr_pem": csr_pem, "private_key_pem": key_pem,
                "message": "CSR gerado. Envie o CSR para a AC para obter o certificado."}
    except ImportError:
        return {"message": "Instale 'cryptography' para gerar CSR.",
                "csr_pem": "", "private_key_pem": ""}
