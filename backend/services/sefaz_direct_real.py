"""
SEFAZDirectRealEngine — comunicação direta com os webservices da SEFAZ
sem provedor intermediário. 100% gratuito, sem limite de emissões.

Requisito: lxml>=5.1.0 (já incluído no requirements.txt)
A biblioteca cryptography já está no projeto.

Configuração no cadastro da empresa:
  motor_fiscal       = "sefaz_real"
  ambiente_fiscal    = "homologacao" | "producao"
  certificado_b64    = certificado A1 (.pfx) — carregado via Empresa → Fiscal
  certificado_senha  = senha do .pfx — armazenada criptografada

Fluxo:
  1. Gera XML NF-e via fiscal_engine (já existente)
  2. Assina o XML com o certificado A1 (RSA-SHA1, C14N)
  3. Envolve em envelope SOAP 1.2
  4. Envia ao webservice SEFAZ do estado (mTLS com o mesmo A1)
  5. Parseia retEnviNFe → protocolo, cStat, xMotivo
"""

from __future__ import annotations

import base64
import hashlib
import os
import ssl
import tempfile
from datetime import datetime
from typing import Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from lxml import etree

try:
    from .fiscal_provider import FiscalProviderBase, SEFAZDirectEngine, gerar_xml_nfe_400
    from ..services.crypto_vault import CryptoVault
except ImportError:
    from fiscal_provider import FiscalProviderBase, SEFAZDirectEngine, gerar_xml_nfe_400
    from crypto_vault import CryptoVault


# ── Constantes de namespace ────────────────────────────────────────────────────

_NFE_NS = "http://www.portalfiscal.inf.br/nfe"
_DSIG   = "http://www.w3.org/2000/09/xmldsig#"
_C14N   = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
_RSA_SHA1 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha1"
_SHA1   = "http://www.w3.org/2000/09/xmldsig#sha1"
_ENV_SIG = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
_SOAP12 = "http://www.w3.org/2003/05/soap-envelope"
_WSDL   = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4"


# ── Tabela de endpoints SEFAZ ─────────────────────────────────────────────────
#
# homologacao: todos os estados usam o SVRS federal
# producao:    estados com servidor próprio listados; demais caem no SVRS (RS)

_HOM_URL = "https://hom.sefazvirtual.fazenda.gov.br/NFeAutorizacao4/NFeAutorizacao4.asmx"
_SVRS_PROD = "https://nfe.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx"

# cUF (código IBGE da UF) → URL de produção
_PROD_URL: dict[int, str] = {
    13: "https://nfe.sefaz.am.gov.br/services2/NfeAutorizacao4",
    29: "https://nfe.sefaz.ba.gov.br/webservices/NFeAutorizacao4/NFeAutorizacao4.asmx",
    52: "https://nfe.sefaz.go.gov.br/nfe/services/NFeAutorizacao4",
    21: "https://www.nfe.sefaz.ma.gov.br/ws/NFeAutorizacao/NfeAutorizacao4.asmx",
    31: "https://nfe.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4",
    51: "https://nfe.sefaz.mt.gov.br/nfews/v2/services/NfeAutorizacao4",
    15: "https://app.sefa.pa.gov.br/nfe/NFeAutorizacao4",
    26: "https://nfe.sefaz.pe.gov.br/nfe-service/services/NFeAutorizacao4",
    41: "https://nfe.fazenda.pr.gov.br/nfe/NFeAutorizacao4",
    43: _SVRS_PROD,
    35: "https://nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
}

# UF sigla → cUF
_UF_COD: dict[str, int] = {
    "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23, "DF": 53,
    "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50, "MT": 51, "PA": 15,
    "PB": 25, "PE": 26, "PI": 22, "PR": 41, "RJ": 33, "RN": 24, "RO": 11,
    "RR": 14, "RS": 43, "SC": 42, "SE": 28, "SP": 35, "TO": 17,
}


def _get_endpoint(uf: str, env: str) -> tuple[str, int]:
    """Retorna (url, cUF) para o estado e ambiente."""
    cuf = _UF_COD.get(uf.upper(), 51)  # default MT
    if env != "producao":
        return _HOM_URL, cuf
    return _PROD_URL.get(cuf, _SVRS_PROD), cuf


# ── Carregamento do certificado ────────────────────────────────────────────────

def _load_cert(company: dict):
    """
    Descriptografa e carrega o certificado A1 do cadastro da empresa.
    Retorna (private_key, cert, pfx_bytes, senha_str).
    Lança ValueError se não há certificado configurado.
    """
    enc_b64 = (company.get("certificado_b64") or "").strip()
    enc_pwd = (company.get("certificado_senha") or "").strip()

    if not enc_b64 or not enc_pwd:
        raise ValueError(
            "Certificado A1 não configurado. Acesse Empresa → Fiscal → Certificado A1 "
            "e faça o upload do arquivo .pfx com a senha."
        )

    cert_b64_plain = CryptoVault.decrypt_string(enc_b64)
    senha_plain = CryptoVault.decrypt_string(enc_pwd)

    try:
        pfx_bytes = base64.b64decode(cert_b64_plain)
    except Exception:
        pfx_bytes = cert_b64_plain.encode("utf-8")

    pwd_bytes = senha_plain.encode("utf-8") if senha_plain else None
    private_key, cert, _chain = load_key_and_certificates(pfx_bytes, pwd_bytes)

    return private_key, cert, pfx_bytes, senha_plain


# ── Assinatura XML NF-e (RSA-SHA1, C14N, enveloped) ───────────────────────────

def _sign_nfe_xml(nfe_xml_str: str, private_key, cert) -> str:
    """
    Assina o XML NF-e 4.00 conforme a NT 2011.003 da SEFAZ.
    Retorna o XML com o elemento <Signature> inserido dentro de <NFe>.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(nfe_xml_str.encode("utf-8"), parser)

    inf_nfe = root.find(f"{{{_NFE_NS}}}infNFe")
    if inf_nfe is None:
        raise ValueError("Elemento infNFe não encontrado no XML da NF-e.")

    ref_id = inf_nfe.get("Id", "")  # e.g. "NFe43..."

    # 1. Digest do infNFe (C14N → SHA1 → base64)
    inf_c14n = etree.tostring(inf_nfe, method="c14n", exclusive=False, with_comments=False)
    digest_b64 = base64.b64encode(hashlib.sha1(inf_c14n).digest()).decode()

    # 2. Construir SignedInfo como elemento lxml
    si = etree.Element(f"{{{_DSIG}}}SignedInfo")

    cm = etree.SubElement(si, f"{{{_DSIG}}}CanonicalizationMethod")
    cm.set("Algorithm", _C14N)

    sm = etree.SubElement(si, f"{{{_DSIG}}}SignatureMethod")
    sm.set("Algorithm", _RSA_SHA1)

    ref = etree.SubElement(si, f"{{{_DSIG}}}Reference")
    ref.set("URI", f"#{ref_id}")

    transforms = etree.SubElement(ref, f"{{{_DSIG}}}Transforms")
    t1 = etree.SubElement(transforms, f"{{{_DSIG}}}Transform")
    t1.set("Algorithm", _ENV_SIG)
    t2 = etree.SubElement(transforms, f"{{{_DSIG}}}Transform")
    t2.set("Algorithm", _C14N)

    dm = etree.SubElement(ref, f"{{{_DSIG}}}DigestMethod")
    dm.set("Algorithm", _SHA1)

    dv = etree.SubElement(ref, f"{{{_DSIG}}}DigestValue")
    dv.text = digest_b64

    # 3. Canonicalizar SignedInfo e assinar (RSA-SHA1)
    si_c14n = etree.tostring(si, method="c14n", exclusive=False, with_comments=False)
    sig_bytes = private_key.sign(si_c14n, padding.PKCS1v15(), hashes.SHA1())
    sig_b64 = base64.b64encode(sig_bytes).decode()

    # 4. Montar elemento Signature completo
    signature = etree.Element(f"{{{_DSIG}}}Signature")
    signature.append(si)

    sv = etree.SubElement(signature, f"{{{_DSIG}}}SignatureValue")
    sv.text = sig_b64

    ki = etree.SubElement(signature, f"{{{_DSIG}}}KeyInfo")
    x9 = etree.SubElement(ki, f"{{{_DSIG}}}X509Data")
    xc = etree.SubElement(x9, f"{{{_DSIG}}}X509Certificate")
    xc.text = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()

    # 5. Inserir Signature como filho de NFe (irmão de infNFe)
    root.append(signature)

    return etree.tostring(root, encoding="unicode", xml_declaration=False)


# ── Envelope SOAP 1.2 ─────────────────────────────────────────────────────────

def _build_soap(signed_nfe_xml: str, cuf: int, lote_id: int = 1) -> str:
    """Envolve o XML assinado no envelope SOAP para NFeAutorizacao4."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        f'xmlns:soap12="{_SOAP12}">'
        f'<soap12:Header>'
        f'<nfeCabecMsg xmlns="{_WSDL}">'
        f'<cUF>{cuf}</cUF>'
        f'<versaoDados>4.00</versaoDados>'
        f'</nfeCabecMsg>'
        f'</soap12:Header>'
        f'<soap12:Body>'
        f'<nfeAutorizacaoLote xmlns="{_WSDL}">'
        f'<nfeDadosMsg>'
        f'<enviNFe versao="4.00" xmlns="{_NFE_NS}">'
        f'<idLote>{lote_id}</idLote>'
        f'<indSinc>1</indSinc>'
        f'{signed_nfe_xml}'
        f'</enviNFe>'
        f'</nfeDadosMsg>'
        f'</nfeAutorizacaoLote>'
        f'</soap12:Body>'
        f'</soap12:Envelope>'
    )


# ── Parsing da resposta SEFAZ ─────────────────────────────────────────────────

def _parse_sefaz_response(resp_text: str, access_key: str) -> dict:
    """Extrai protocolo, cStat e xMotivo da resposta retEnviNFe."""
    try:
        root = etree.fromstring(resp_text.encode("utf-8"))
    except Exception:
        return {"status": "erro", "message": f"Resposta SEFAZ inválida: {resp_text[:200]}",
                "protocol": "", "access_key": access_key}

    ns = {"nfe": _NFE_NS}
    ret = root.find(f".//{{{_NFE_NS}}}retEnviNFe")
    if ret is None:
        # Tentar busca sem namespace (alguns estados)
        ret = root.find(".//retEnviNFe")

    def _txt(el, tag: str) -> str:
        if el is None:
            return ""
        found = el.find(f"{{{_NFE_NS}}}{tag}")
        if found is None:
            found = el.find(tag)
        return (found.text or "").strip() if found is not None else ""

    if ret is None:
        # Verificar se é erro SOAP (Fault)
        fault = root.find(f".//{{{_SOAP12}}}Fault")
        if fault is None:
            fault = root.find(".//Fault")
        if fault is not None:
            reason = fault.findtext(".//{http://www.w3.org/2003/05/soap-envelope}Text") or str(fault.text)
            return {"status": "erro", "message": f"SOAP Fault: {reason}", "protocol": "", "access_key": access_key}
        return {"status": "erro", "message": "retEnviNFe não encontrado na resposta.", "protocol": "", "access_key": access_key}

    c_stat = _txt(ret, "cStat")
    x_motivo = _txt(ret, "xMotivo")

    # Busca protNFe (retorno síncrono)
    prot = ret.find(f".//{{{_NFE_NS}}}protNFe")
    if prot is None:
        prot = ret.find(".//protNFe")

    inf_prot = prot.find(f"{{{_NFE_NS}}}infProt") if prot is not None else None
    if inf_prot is None and prot is not None:
        inf_prot = prot.find("infProt")

    prot_c_stat = _txt(inf_prot, "cStat") if inf_prot is not None else c_stat
    prot_motivo = _txt(inf_prot, "xMotivo") if inf_prot is not None else x_motivo
    n_prot = _txt(inf_prot, "nProt") if inf_prot is not None else ""
    ch_nfe = _txt(inf_prot, "chNFe") if inf_prot is not None else access_key

    # cStat 100 ou 150 = autorizado; 204 = duplicidade (aceito)
    if prot_c_stat in ("100", "150", "204"):
        return {
            "status": "autorizada",
            "protocol": n_prot,
            "access_key": ch_nfe or access_key,
            "c_stat": prot_c_stat,
            "message": prot_motivo or "Autorizado o uso da NF-e",
            "provider": "sefaz_real",
        }

    # cStat 104 = lote processado assíncrono (não deve ocorrer com indSinc=1, mas tratamos)
    if c_stat == "104":
        n_rec = _txt(ret.find(f"{{{_NFE_NS}}}infRec") or ret.find("infRec"), "nRec")
        return {
            "status": "processando",
            "protocol": n_rec,
            "access_key": access_key,
            "c_stat": c_stat,
            "message": "Lote em processamento pela SEFAZ. Consulte o status em instantes.",
            "provider": "sefaz_real",
        }

    # Rejeição
    motivo = prot_motivo or x_motivo or f"Rejeição SEFAZ (cStat {prot_c_stat or c_stat})"
    return {
        "status": "rejeitada",
        "protocol": "",
        "access_key": access_key,
        "c_stat": prot_c_stat or c_stat,
        "message": motivo,
        "error": motivo,
        "provider": "sefaz_real",
    }


# ── Contexto SSL com mTLS ─────────────────────────────────────────────────────

def _make_ssl_context(private_key, cert) -> ssl.SSLContext:
    """
    Cria um SSLContext com mTLS usando o certificado A1.
    SEFAZ exige que o cliente apresente o certificado na conexão TLS.
    Usa arquivos temporários para compatibilidade com ssl.SSLContext.
    """
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # SEFAZ usa certificados ICP-Brasil auto-assinados

    # Carregar cert + chave via arquivos temporários (ssl não aceita bytes diretamente)
    kf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    cf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    try:
        kf.write(key_pem)
        kf.flush()
        kf.close()
        cf.write(cert_pem)
        cf.flush()
        cf.close()
        ctx.load_cert_chain(certfile=cf.name, keyfile=kf.name)
    finally:
        try:
            os.unlink(kf.name)
        except Exception:
            pass
        try:
            os.unlink(cf.name)
        except Exception:
            pass

    return ctx


# ── Motor principal ────────────────────────────────────────────────────────────

class SEFAZDirectRealEngine(FiscalProviderBase):
    """
    Emissão direta na SEFAZ sem provedor intermediário.
    100% gratuito, sem limite de notas.
    Requer certificado A1 válido cadastrado na empresa.
    """

    async def emit_invoice(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        # 1. Carregar certificado
        try:
            private_key, cert, _pfx, _pwd = _load_cert(company)
        except ValueError as e:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "sefaz_real", "fiscal_ref": "",
                    "message": str(e), "error": str(e)}
        except Exception as e:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "sefaz_real", "fiscal_ref": "",
                    "message": f"Erro ao carregar certificado A1: {e}", "error": str(e)}

        # 2. Gerar XML NF-e base (fiscal_engine)
        try:
            xml_str = gerar_xml_nfe_400(company, contact, items, inv_meta)
        except Exception as e:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "sefaz_real", "fiscal_ref": "",
                    "message": f"Erro ao gerar XML NF-e: {e}", "error": str(e)}

        # 3. Assinar XML
        try:
            signed_xml = _sign_nfe_xml(xml_str, private_key, cert)
        except Exception as e:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "sefaz_real", "fiscal_ref": "",
                    "message": f"Erro na assinatura digital: {e}", "error": str(e)}

        # 4. Montar envelope SOAP
        uf = company.get("uf", "MT")
        env = (company.get("ambiente_fiscal") or "homologacao").lower()
        url, cuf = _get_endpoint(uf, env)
        access_key = inv_meta.get("access_key", "")
        lote_id = int(datetime.now().strftime("%Y%m%d%H%M%S"))
        soap_body = _build_soap(signed_xml, cuf, lote_id)

        # 5. Enviar ao webservice SEFAZ (mTLS)
        try:
            ssl_ctx = _make_ssl_context(private_key, cert)
            async with httpx.AsyncClient(verify=ssl_ctx, timeout=30.0) as client:
                resp = await client.post(
                    url,
                    content=soap_body.encode("utf-8"),
                    headers={
                        "Content-Type": (
                            'application/soap+xml;charset=UTF-8;'
                            'action="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4/nfeAutorizacaoLote"'
                        ),
                    },
                )
        except httpx.TimeoutException:
            return {"status": "erro", "protocol": "", "access_key": access_key,
                    "xml_content": signed_xml, "provider": "sefaz_real", "fiscal_ref": "",
                    "message": f"Timeout na comunicação com SEFAZ ({url}). A SEFAZ pode estar indisponível.",
                    "error": "timeout"}
        except Exception as e:
            return {"status": "erro", "protocol": "", "access_key": access_key,
                    "xml_content": signed_xml, "provider": "sefaz_real", "fiscal_ref": "",
                    "message": f"Erro de conexão com SEFAZ: {e}", "error": str(e)}

        # 6. Parsear resposta
        result = _parse_sefaz_response(resp.text, access_key)
        result["xml_content"] = signed_xml
        result["fiscal_ref"] = access_key
        return result

    async def cancel_invoice(self, company: dict, invoice: dict, reason: str) -> dict:
        return await self._send_evento(
            company=company,
            access_key=invoice.get("access_key", ""),
            evento_type="110111",
            det_evento=f"<descEvento>Cancelamento</descEvento><nProt>{invoice.get('protocol', '')}</nProt><xJust>{reason}</xJust>",
            desc="Cancelamento",
        )

    async def emit_cce(self, company: dict, invoice: dict, text: str) -> dict:
        return await self._send_evento(
            company=company,
            access_key=invoice.get("access_key", ""),
            evento_type="110110",
            det_evento=f"<descEvento>Carta de Correcao</descEvento><xCorrecao>{text}</xCorrecao><xCondUso>A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7o do Convenio S/N, de 15 de dezembro de 1970 e pode ser utilizada para regularizacao de erro ocorrido na emissao de documento fiscal, desde que o erro nao esteja relacionado com: I - as variaveis que determinam o valor do imposto tais como: base de calculo, aliquota, diferenca de preco, quantidade, valor da operacao ou da prestacao; II - a correcao de dados cadastrais que implique mudanca do remetente ou do destinatario; III - a data de emissao ou de saida.</xCondUso>",
            desc="Carta de Correcao",
        )

    async def _send_evento(self, company: dict, access_key: str, evento_type: str,
                           det_evento: str, desc: str) -> dict:
        try:
            private_key, cert, _pfx, _pwd = _load_cert(company)
        except Exception as e:
            return {"status": "erro", "message": str(e)}

        uf = company.get("uf", "MT")
        env = (company.get("ambiente_fiscal") or "homologacao").lower()
        cuf = _UF_COD.get(uf.upper(), 51)
        tp_amb = "1" if env == "producao" else "2"
        dh_evento = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
        n_seq = "1"
        id_evento = f"ID{evento_type}{access_key}0{n_seq.zfill(2)}"

        inf_evento = (
            f'<infEvento Id="{id_evento}">'
            f'<cOrgao>{cuf}</cOrgao>'
            f'<tpAmb>{tp_amb}</tpAmb>'
            f'<CNPJ>{access_key[6:20]}</CNPJ>'
            f'<chNFe>{access_key}</chNFe>'
            f'<dhEvento>{dh_evento}</dhEvento>'
            f'<tpEvento>{evento_type}</tpEvento>'
            f'<nSeqEvento>{n_seq}</nSeqEvento>'
            f'<verEvento>1.00</verEvento>'
            f'<detEvento versao="1.00">{det_evento}</detEvento>'
            f'</infEvento>'
        )
        evento_xml = f'<evento versao="1.00" xmlns="{_NFE_NS}">{inf_evento}</evento>'

        try:
            parser = etree.XMLParser(remove_blank_text=True)
            ev_root = etree.fromstring(evento_xml.encode("utf-8"), parser)
            inf_ev_el = ev_root.find(f"{{{_NFE_NS}}}infEvento")
            inf_c14n = etree.tostring(inf_ev_el, method="c14n", exclusive=False, with_comments=False)
            digest_b64 = base64.b64encode(hashlib.sha1(inf_c14n).digest()).decode()

            si = etree.Element(f"{{{_DSIG}}}SignedInfo")
            cm = etree.SubElement(si, f"{{{_DSIG}}}CanonicalizationMethod")
            cm.set("Algorithm", _C14N)
            sm = etree.SubElement(si, f"{{{_DSIG}}}SignatureMethod")
            sm.set("Algorithm", _RSA_SHA1)
            ref = etree.SubElement(si, f"{{{_DSIG}}}Reference")
            ref.set("URI", f"#{id_evento}")
            transforms = etree.SubElement(ref, f"{{{_DSIG}}}Transforms")
            t1 = etree.SubElement(transforms, f"{{{_DSIG}}}Transform")
            t1.set("Algorithm", _ENV_SIG)
            t2 = etree.SubElement(transforms, f"{{{_DSIG}}}Transform")
            t2.set("Algorithm", _C14N)
            dm = etree.SubElement(ref, f"{{{_DSIG}}}DigestMethod")
            dm.set("Algorithm", _SHA1)
            dv = etree.SubElement(ref, f"{{{_DSIG}}}DigestValue")
            dv.text = digest_b64

            si_c14n = etree.tostring(si, method="c14n", exclusive=False, with_comments=False)
            sig_bytes = private_key.sign(si_c14n, padding.PKCS1v15(), hashes.SHA1())
            sig_b64 = base64.b64encode(sig_bytes).decode()

            signature = etree.Element(f"{{{_DSIG}}}Signature")
            signature.append(si)
            sv = etree.SubElement(signature, f"{{{_DSIG}}}SignatureValue")
            sv.text = sig_b64
            ki = etree.SubElement(signature, f"{{{_DSIG}}}KeyInfo")
            x9 = etree.SubElement(ki, f"{{{_DSIG}}}X509Data")
            xc = etree.SubElement(x9, f"{{{_DSIG}}}X509Certificate")
            xc.text = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
            ev_root.append(signature)

            signed_evento = etree.tostring(ev_root, encoding="unicode", xml_declaration=False)
        except Exception as e:
            return {"status": "erro", "message": f"Erro na assinatura do evento: {e}"}

        lote_ev = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<soap12:Envelope xmlns:soap12="{_SOAP12}">'
            f'<soap12:Header><nfeCabecMsg xmlns="{_WSDL.replace("NFeAutorizacao4","NFeRecepcaoEvento4")}">'
            f'<cUF>{cuf}</cUF><versaoDados>1.00</versaoDados></nfeCabecMsg></soap12:Header>'
            f'<soap12:Body>'
            f'<nfeRecepcaoEventoNF xmlns="{_WSDL.replace("NFeAutorizacao4","NFeRecepcaoEvento4")}">'
            f'<nfeDadosMsg>'
            f'<envEvento versao="1.00" xmlns="{_NFE_NS}">'
            f'<idLote>{int(datetime.now().strftime("%Y%m%d%H%M%S"))}</idLote>'
            f'{signed_evento}'
            f'</envEvento>'
            f'</nfeDadosMsg></nfeRecepcaoEventoNF>'
            f'</soap12:Body></soap12:Envelope>'
        )

        ev_url_hom = "https://hom.sefazvirtual.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx"
        ev_url_prod = "https://nfe.svrs.rs.gov.br/ws/registroEvento/registroEvento.asmx"
        ev_url = ev_url_hom if env != "producao" else ev_url_prod

        try:
            ssl_ctx = _make_ssl_context(private_key, cert)
            async with httpx.AsyncClient(verify=ssl_ctx, timeout=30.0) as client:
                resp = await client.post(
                    ev_url,
                    content=lote_ev.encode("utf-8"),
                    headers={"Content-Type": 'application/soap+xml;charset=UTF-8'},
                )
        except Exception as e:
            return {"status": "erro", "message": f"Erro de conexão SEFAZ (evento): {e}"}

        try:
            resp_root = etree.fromstring(resp.text.encode("utf-8"))
            ret_ev = resp_root.find(f".//{{{_NFE_NS}}}retEvento")
            if ret_ev is None:
                ret_ev = resp_root.find(".//retEvento")
            inf_ret = ret_ev.find(f"{{{_NFE_NS}}}infEvento") if ret_ev is not None else None
            if inf_ret is None and ret_ev is not None:
                inf_ret = ret_ev.find("infEvento")
            c_stat = (inf_ret.findtext(f"{{{_NFE_NS}}}cStat") or inf_ret.findtext("cStat") or "").strip() if inf_ret is not None else ""
            x_motivo = (inf_ret.findtext(f"{{{_NFE_NS}}}xMotivo") or inf_ret.findtext("xMotivo") or "").strip() if inf_ret is not None else ""
            n_prot = (inf_ret.findtext(f"{{{_NFE_NS}}}nProt") or inf_ret.findtext("nProt") or "").strip() if inf_ret is not None else ""
        except Exception:
            c_stat, x_motivo, n_prot = "", resp.text[:200], ""

        if c_stat in ("135", "136", "155"):
            key = "cancel_protocol" if evento_type == "110111" else "cce_protocol"
            return {"status": "cancelada" if evento_type == "110111" else "vinculada",
                    key: n_prot, "message": x_motivo or f"{desc} registrado."}
        return {"status": "erro", "c_stat": c_stat,
                "message": x_motivo or f"Rejeição SEFAZ (cStat {c_stat})"}

    async def inutilize(self, company: dict, model: str, series: int,
                        start_n: int, end_n: int, reason: str) -> dict:
        # Inutilização usa endpoint próprio — delegamos ao SEFAZDirectEngine (simulação)
        # até implementação completa do NFeInutilizacao4
        return await SEFAZDirectEngine().inutilize(company, model, series, start_n, end_n, reason)

    async def manifest(self, company: dict, access_key: str, event_type: str) -> dict:
        return await SEFAZDirectEngine().manifest(company, access_key, event_type)

    async def consult_invoice(self, fiscal_ref: str, model: str = "NFe-55") -> dict:
        return {"status": "processando", "message": "Consulta direta SEFAZ não implementada neste motor."}
