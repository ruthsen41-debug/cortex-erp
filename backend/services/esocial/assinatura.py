"""Assinatura digital dos eventos do eSocial (Manual do Desenvolvedor v1.16, itens 6.7 e 6.8).

XMLDSig enveloped, RSA-SHA256, digest SHA-256, canonicalização C14N 1.0, Reference URI="",
transformações enveloped-signature + C14N e apenas o certificado do titular no KeyInfo.
"""
import base64
import datetime as _dt
import hashlib
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

DSIG = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


def _c14n(el) -> bytes:
    return etree.tostring(el, method="c14n", exclusive=False, with_comments=False)


def assinar(xml: str, private_key, cert) -> str:
    """Devolve o evento com <Signature> como último filho de <eSocial>."""
    root = etree.fromstring(xml.encode("utf-8"))
    for old in root.findall(f"{{{DSIG}}}Signature"):
        root.remove(old)
    digest = base64.b64encode(hashlib.sha256(_c14n(root)).digest()).decode()

    sig = etree.SubElement(root, f"{{{DSIG}}}Signature", nsmap={None: DSIG})
    si = etree.SubElement(sig, f"{{{DSIG}}}SignedInfo")
    etree.SubElement(si, f"{{{DSIG}}}CanonicalizationMethod", Algorithm=C14N)
    etree.SubElement(si, f"{{{DSIG}}}SignatureMethod", Algorithm=RSA_SHA256)
    ref = etree.SubElement(si, f"{{{DSIG}}}Reference", URI="")
    trs = etree.SubElement(ref, f"{{{DSIG}}}Transforms")
    etree.SubElement(trs, f"{{{DSIG}}}Transform", Algorithm=ENVELOPED)
    etree.SubElement(trs, f"{{{DSIG}}}Transform", Algorithm=C14N)
    etree.SubElement(ref, f"{{{DSIG}}}DigestMethod", Algorithm=SHA256)
    etree.SubElement(ref, f"{{{DSIG}}}DigestValue").text = digest

    assinatura = private_key.sign(_c14n(si), padding.PKCS1v15(), hashes.SHA256())
    etree.SubElement(sig, f"{{{DSIG}}}SignatureValue").text = base64.b64encode(assinatura).decode()
    ki = etree.SubElement(sig, f"{{{DSIG}}}KeyInfo")
    xd = etree.SubElement(ki, f"{{{DSIG}}}X509Data")
    der = cert.public_bytes(serialization.Encoding.DER)
    etree.SubElement(xd, f"{{{DSIG}}}X509Certificate").text = base64.b64encode(der).decode()
    return etree.tostring(root, encoding="unicode")


def verificar(xml: str) -> Tuple[bool, str]:
    """Confere digest e assinatura com o certificado embutido (mesmo procedimento do item 6.8)."""
    try:
        root = etree.fromstring(xml.encode("utf-8"))
        sig = root.find(f"{{{DSIG}}}Signature")
        if sig is None:
            return False, "Evento sem assinatura"
        si = sig.find(f"{{{DSIG}}}SignedInfo")
        digest_xml = si.findtext(f".//{{{DSIG}}}DigestValue")
        cert_b64 = sig.findtext(f".//{{{DSIG}}}X509Certificate")
        valor = base64.b64decode(sig.findtext(f"{{{DSIG}}}SignatureValue"))
        si_c14n = _c14n(si)
        root.remove(sig)
        digest = base64.b64encode(hashlib.sha256(_c14n(root)).digest()).decode()
        if digest != digest_xml:
            return False, "Resumo (digest) não confere: o XML foi alterado após a assinatura"
        cert = x509.load_der_x509_certificate(base64.b64decode(cert_b64))
        cert.public_key().verify(valor, si_c14n, padding.PKCS1v15(), hashes.SHA256())
        return True, "Assinatura válida"
    except Exception as exc:  # noqa: BLE001
        return False, f"Assinatura inválida: {exc}"


def certificado_info(cert) -> dict:
    def nome(oid):
        try:
            return cert.subject.get_attributes_for_oid(oid)[0].value
        except IndexError:
            return ""
    fim = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=_dt.timezone.utc)
    return {"titular": nome(NameOID.COMMON_NAME), "validade": fim.date().isoformat(),
            "vencido": fim < _dt.datetime.now(_dt.timezone.utc)}


_TESTE: Optional[tuple] = None


def certificado_teste():
    """Par chave/certificado autoassinado, só para validar a estrutura sem o A1 da empresa.
    O governo recusa essa assinatura; ela nunca é usada para transmitir."""
    global _TESTE
    if _TESTE is None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CORTEX ERP - CERTIFICADO DE TESTE")])
        agora = _dt.datetime.now(_dt.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(agora - _dt.timedelta(days=1))
                .not_valid_after(agora + _dt.timedelta(days=3650)).sign(key, hashes.SHA256()))
        _TESTE = (key, cert)
    return _TESTE
