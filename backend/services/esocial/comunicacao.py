"""Comunicação com os webservices do eSocial (Pacote de Comunicação v1.6).

- Lote de até 50 eventos do mesmo grupo (EnvioLoteEventos-v1_1_1)
- SOAP 1.1 com autenticação mútua TLS usando o certificado A1 da empresa
- Leitura do retorno do envio (protocolo) e do processamento (recibos, ocorrências, totalizadores)
"""
import os
import ssl
from typing import Any, Dict, List, Optional

import httpx
from lxml import etree

from .tabelas import WEBSERVICES

NS_LOTE = "http://www.esocial.gov.br/schema/lote/eventos/envio/v1_1_1"
NS_CONSULTA = "http://www.esocial.gov.br/schema/lote/eventos/envio/consulta/retornoProcessamento/v1_0_0"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
WS_ENVIO = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0"
WS_CONSULTA = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/consulta/retornoProcessamento/v1_1_0"
ACTION_ENVIO = WS_ENVIO + "/ServicoEnviarLoteEventos/EnviarLoteEventos"
ACTION_CONSULTA = WS_CONSULTA + "/ServicoConsultarLoteEventos/ConsultarLoteEventos"

MAX_EVENTOS_LOTE = 50

# Códigos de resposta (Manual do Desenvolvedor, itens 7.5 e 7.6)
RESPOSTAS_LOTE = {
    "101": "Lote aguardando processamento",
    "201": "Lote processado com sucesso",
    "202": "Lote processado com advertências",
    "301": "Erro no servidor do eSocial",
    "401": "Lote incorreto - erro de preenchimento",
    "402": "Lote incorreto - schema inválido",
    "403": "Lote incorreto - versão do schema não permitida",
    "404": "Lote incorreto - erro de certificado",
    "405": "Lote incorreto - lote nulo ou vazio",
}
RESPOSTAS_EVENTO = {
    "201": "Sucesso",
    "202": "Sucesso com advertência",
    "301": "Erro no servidor do eSocial",
    "401": "Erro no conteúdo do evento",
    "402": "Schema inválido",
    "403": "Leiaute inválido",
    "404": "Erro do certificado digital da assinatura do evento",
    "405": "Erro na assinatura do evento",
    "406": "Evento não pertence ao grupo especificado no lote",
}


class ErroComunicacao(RuntimeError):
    pass


# ─── montagem ─────────────────────────────────────────────────────────────────

def montar_lote(grupo: int, nr_insc_empregador: str, transmissor: Dict[str, str],
                eventos: List[Dict[str, str]]) -> str:
    """eventos: [{"id": "ID...", "xml": "<eSocial ...assinado>"}] (máximo 50, mesmo grupo)."""
    if not eventos or len(eventos) > MAX_EVENTOS_LOTE:
        raise ValueError(f"O lote precisa ter de 1 a {MAX_EVENTOS_LOTE} eventos")
    root = etree.Element(f"{{{NS_LOTE}}}eSocial", nsmap={None: NS_LOTE})
    env = etree.SubElement(root, f"{{{NS_LOTE}}}envioLoteEventos", grupo=str(grupo))
    emp = etree.SubElement(env, f"{{{NS_LOTE}}}ideEmpregador")
    etree.SubElement(emp, f"{{{NS_LOTE}}}tpInsc").text = "1"
    etree.SubElement(emp, f"{{{NS_LOTE}}}nrInsc").text = nr_insc_empregador
    tr = etree.SubElement(env, f"{{{NS_LOTE}}}ideTransmissor")
    etree.SubElement(tr, f"{{{NS_LOTE}}}tpInsc").text = str(transmissor.get("tp_insc") or "1")
    etree.SubElement(tr, f"{{{NS_LOTE}}}nrInsc").text = transmissor["nr_insc"]
    evs = etree.SubElement(env, f"{{{NS_LOTE}}}eventos")
    for ev in eventos:
        e = etree.SubElement(evs, f"{{{NS_LOTE}}}evento", Id=ev["id"])
        e.append(etree.fromstring(ev["xml"].encode("utf-8")))
    return etree.tostring(root, encoding="unicode")


def montar_consulta(protocolo: str) -> str:
    root = etree.Element(f"{{{NS_CONSULTA}}}eSocial", nsmap={None: NS_CONSULTA})
    c = etree.SubElement(root, f"{{{NS_CONSULTA}}}consultaLoteEventos")
    etree.SubElement(c, f"{{{NS_CONSULTA}}}protocoloEnvio").text = protocolo
    return etree.tostring(root, encoding="unicode")


def envelope(operacao_ns: str, operacao: str, parametro: str, conteudo_xml: str) -> bytes:
    env = etree.Element(f"{{{NS_SOAP}}}Envelope", nsmap={"soapenv": NS_SOAP, "v1": operacao_ns})
    etree.SubElement(env, f"{{{NS_SOAP}}}Header")
    body = etree.SubElement(env, f"{{{NS_SOAP}}}Body")
    op = etree.SubElement(body, f"{{{operacao_ns}}}{operacao}")
    par = etree.SubElement(op, f"{{{operacao_ns}}}{parametro}")
    par.append(etree.fromstring(conteudo_xml.encode("utf-8")))
    return etree.tostring(env, xml_declaration=True, encoding="utf-8")


# ─── leitura dos retornos ─────────────────────────────────────────────────────

def _xp(el, path: str):
    """XPath por nome local (os retornos usam vários namespaces)."""
    partes = [p for p in path.split("/") if p]
    expr = "./" + "/".join(f"*[local-name()='{p}']" if p != ".." else ".." for p in partes)
    return el.xpath(expr)


def _t(el, path: str) -> str:
    r = _xp(el, path)
    return (r[0].text or "").strip() if r else ""


def _ocorrencias(el) -> List[Dict[str, str]]:
    out = []
    for oc in _xp(el, "ocorrencias/ocorrencia"):
        out.append({"tipo": _t(oc, "tipo"), "codigo": _t(oc, "codigo"),
                    "descricao": _t(oc, "descricao"), "localizacao": _t(oc, "localizacao")})
    return out


def _resultado_soap(resposta: bytes, resultado: str):
    doc = etree.fromstring(resposta)
    fault = doc.xpath("//*[local-name()='Fault']")
    if fault:
        raise ErroComunicacao("O eSocial devolveu erro SOAP: " + " ".join(fault[0].itertext()).strip()[:500])
    res = doc.xpath(f"//*[local-name()='{resultado}']/*")
    if not res:
        raise ErroComunicacao("Resposta do eSocial sem conteúdo")
    return res[0]


def ler_retorno_envio(resposta: bytes) -> Dict[str, Any]:
    es = _resultado_soap(resposta, "EnviarLoteEventosResult")
    ret = _xp(es, "retornoEnvioLoteEventos")[0]
    status = _xp(ret, "status")[0]
    return {
        "cd_resposta": _t(status, "cdResposta"),
        "desc_resposta": _t(status, "descResposta"),
        "ocorrencias": _ocorrencias(status),
        "protocolo": _t(ret, "dadosRecepcaoLote/protocoloEnvio"),
        "xml": etree.tostring(es, encoding="unicode"),
    }


def ler_retorno_processamento(resposta: bytes) -> Dict[str, Any]:
    es = _resultado_soap(resposta, "ConsultarLoteEventosResult")
    ret = _xp(es, "retornoProcessamentoLoteEventos")[0]
    status = _xp(ret, "status")[0]
    eventos = []
    for ev in _xp(ret, "retornoEventos/evento"):
        r = _xp(ev, "retornoEvento/eSocial/retornoEvento")
        r = r[0] if r else None
        proc = _xp(r, "processamento")[0] if r is not None and _xp(r, "processamento") else None
        eventos.append({
            "id": ev.get("Id"),
            "duplicado": ev.get("evtDupl") == "true",
            "cd_resposta": _t(proc, "cdResposta") if proc is not None else "",
            "desc_resposta": _t(proc, "descResposta") if proc is not None else "",
            "ocorrencias": _ocorrencias(proc) if proc is not None else [],
            "nr_recibo": _t(r, "recibo/nrRecibo") if r is not None else "",
            "retorno_xml": etree.tostring(r, encoding="unicode") if r is not None else "",
            "totalizadores": [{"tipo": t.get("tipo"), "xml": etree.tostring(t[0], encoding="unicode") if len(t) else ""}
                              for t in _xp(ev, "tot")],
        })
    return {
        "cd_resposta": _t(status, "cdResposta"),
        "desc_resposta": _t(status, "descResposta"),
        "tempo_estimado": _t(status, "tempoEstimadoConclusao"),
        "ocorrencias": _ocorrencias(status),
        "eventos": eventos,
        "xml": etree.tostring(es, encoding="unicode"),
    }


# ─── transporte ───────────────────────────────────────────────────────────────

def _post(url: str, action: str, corpo: bytes, ssl_context: Optional[ssl.SSLContext], timeout: float) -> bytes:
    headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{action}"'}
    try:
        with httpx.Client(verify=ssl_context if ssl_context is not None else True, timeout=timeout) as cli:
            r = cli.post(url, content=corpo, headers=headers)
    except httpx.HTTPError as exc:
        raise ErroComunicacao(f"Falha de conexão com o eSocial: {exc}") from exc
    if r.status_code in (401, 403):
        raise ErroComunicacao("O eSocial recusou o acesso (HTTP %d): é preciso o certificado digital A1 da empresa "
                              "ou do procurador com procuração eletrônica no e-CAC para este CNPJ." % r.status_code)
    if r.status_code >= 400 and b"Fault" not in r.content:
        raise ErroComunicacao(f"O eSocial respondeu HTTP {r.status_code}: {r.text[:300]}")
    return r.content


class ClienteESocial:
    """Envia lotes e consulta o processamento. O transporte pode ser trocado nos testes."""

    def __init__(self, ambiente: int, ssl_context: Optional[ssl.SSLContext], transporte=None, timeout: float = 60):
        if ambiente not in WEBSERVICES:
            raise ValueError("Ambiente do eSocial inválido")
        self.urls = WEBSERVICES[ambiente]
        self.ssl_context = ssl_context
        self.timeout = timeout
        self._post = transporte or _post

    def enviar_lote(self, lote_xml: str) -> Dict[str, Any]:
        corpo = envelope(WS_ENVIO, "EnviarLoteEventos", "loteEventos", lote_xml)
        resp = self._post(self.urls["envio"], ACTION_ENVIO, corpo, self.ssl_context, self.timeout)
        return ler_retorno_envio(resp)

    def consultar_lote(self, protocolo: str) -> Dict[str, Any]:
        corpo = envelope(WS_CONSULTA, "ConsultarLoteEventos", "consulta", montar_consulta(protocolo))
        resp = self._post(self.urls["consulta"], ACTION_CONSULTA, corpo, self.ssl_context, self.timeout)
        return ler_retorno_processamento(resp)


_CERTS_DIR = os.path.join(os.path.dirname(__file__), "certs")


def contexto_servidor() -> ssl.SSLContext:
    """Confere o certificado dos servidores do eSocial.

    Os servidores (SERPRO) não enviam a AC intermediária "AC SERPRO AR46 OV TLS CA 2025", emitida pela
    raiz pública GlobalSign Root R46. Usamos as raízes do certifi mais essa intermediária (pasta certs/).
    """
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    for nome in sorted(os.listdir(_CERTS_DIR)):
        if nome.endswith(".pem"):
            ctx.load_verify_locations(cafile=os.path.join(_CERTS_DIR, nome))
    return ctx


def contexto_tls(private_key, cert) -> ssl.SSLContext:
    """TLS 1.2+ com o certificado A1 do cliente e conferência do certificado do servidor."""
    import tempfile

    from cryptography.hazmat.primitives import serialization
    ctx = contexto_servidor()
    key_pem = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    fd, caminho = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(cert_pem + key_pem)
        ctx.load_cert_chain(certfile=caminho)
    finally:
        try:
            os.unlink(caminho)
        except OSError:
            pass
    return ctx
