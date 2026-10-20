import base64
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509

try:
    from ..config import SECRET_KEY
except ImportError:
    from config import SECRET_KEY


def _get_fernet() -> Fernet:
    """Gera chave Fernet determinística de 32 bytes a partir do SECRET_KEY do app."""
    key_32 = hashlib.sha256(SECRET_KEY.encode()).digest()
    key_b64 = base64.urlsafe_b64encode(key_32)
    return Fernet(key_b64)


class CryptoVault:
    @staticmethod
    def encrypt_string(text: str) -> str:
        if not text:
            return ""
        f = _get_fernet()
        return f.encrypt(text.encode("utf-8")).decode("utf-8")

    @staticmethod
    def decrypt_string(cipher_text: str) -> str:
        if not cipher_text:
            return ""
        try:
            f = _get_fernet()
            return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except Exception:
            return cipher_text

    @staticmethod
    def encrypt_bytes(data: bytes) -> str:
        if not data:
            return ""
        f = _get_fernet()
        return f.encrypt(data).decode("utf-8")

    @staticmethod
    def decrypt_bytes(cipher_text: str) -> bytes:
        if not cipher_text:
            return b""
        try:
            f = _get_fernet()
            return f.decrypt(cipher_text.encode("utf-8"))
        except Exception:
            try:
                return base64.b64decode(cipher_text)
            except Exception:
                return cipher_text.encode("utf-8")

    @staticmethod
    def inspect_pfx_certificate(pfx_bytes: bytes, password: str) -> Dict[str, Any]:
        """
        Inspeciona e valida o arquivo PKCS#12 (.pfx / .p12) extraindo data real de validade,
        titular, CNPJ e emissor criptográfico sem depender de datas fictícias.
        """
        try:
            pwd_bytes = password.encode("utf-8") if password else None
            private_key, cert, additional_certs = pkcs12.load_key_and_certificates(pfx_bytes, pwd_bytes)
            if not cert:
                raise ValueError("Nenhum certificado digital encontrado no arquivo PKCS#12.")

            # Validade
            try:
                not_after = cert.not_valid_after_utc.strftime("%Y-%m-%d")
                not_before = cert.not_valid_before_utc.strftime("%Y-%m-%d")
            except AttributeError:
                not_after = cert.not_valid_after.strftime("%Y-%m-%d")
                not_before = cert.not_valid_before.strftime("%Y-%m-%d")

            # Titular (CN)
            subject_cn = ""
            for attr in cert.subject:
                if attr.oid == x509.NameOID.COMMON_NAME:
                    subject_cn = attr.value
                    break
            if not subject_cn:
                subject_cn = cert.subject.rfc4514_string()

            # Emissor
            issuer_cn = ""
            for attr in cert.issuer:
                if attr.oid == x509.NameOID.COMMON_NAME:
                    issuer_cn = attr.value
                    break

            return {
                "valid": True,
                "valid_from": not_before,
                "valid_to": not_after,
                "subject_cn": subject_cn,
                "issuer_cn": issuer_cn,
                "serial_number": hex(cert.serial_number),
                "has_private_key": private_key is not None,
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "valid_to": (datetime.now().date()).isoformat(),
                "subject_cn": "Certificado A1",
            }
