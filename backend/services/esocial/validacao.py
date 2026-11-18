"""Validação dos eventos contra os esquemas XSD oficiais do eSocial (S-1.3)."""
import os
import re
from functools import lru_cache
from typing import List

from lxml import etree

from .tabelas import EVENTOS, pacote_vigente

_DIR = os.path.join(os.path.dirname(__file__), "xsd")


@lru_cache(maxsize=None)
def _schema(nome_xsd: str, pasta: str) -> etree.XMLSchema:
    caminho = os.path.join(_DIR, pasta, f"{nome_xsd}.xsd")
    return etree.XMLSchema(etree.parse(caminho))


_RE_NS = re.compile(r"\{[^}]*\}")


def _traduz(msg: str) -> str:
    """Mensagens do libxml2 mais legíveis: tira namespaces e traduz os padrões comuns."""
    m = _RE_NS.sub("", msg)
    trocas = [
        (r"Element '([^']+)': This element is not expected\. Expected is one of \( ([^)]+) \)\.",
         r"Campo '\1' fora de ordem ou não permitido aqui. Esperado: \2."),
        (r"Element '([^']+)': This element is not expected\. Expected is \( ([^)]+) \)\.",
         r"Campo '\1' fora de ordem ou não permitido aqui. Esperado: \2."),
        (r"Element '([^']+)': Missing child element\(s\)\. Expected is one of \( ([^)]+) \)\.",
         r"Grupo '\1' incompleto. Falta: \2."),
        (r"Element '([^']+)': Missing child element\(s\)\. Expected is \( ([^)]+) \)\.",
         r"Grupo '\1' incompleto. Falta: \2."),
        (r"Element '([^']+)': \[facet 'pattern'\] The value '([^']*)' is not accepted by the pattern '([^']+)'\.",
         r"Campo '\1' com valor '\2' fora do formato exigido (\3)."),
        (r"Element '([^']+)': \[facet 'enumeration'\] The value '([^']*)' is not an element of the set \{([^}]+)\}\.",
         r"Campo '\1' com valor '\2' não permitido. Valores aceitos: \3."),
        (r"Element '([^']+)': \[facet '(maxLength|minLength|length)'\] The value '([^']*)' has a length of '(\d+)'.*",
         r"Campo '\1' com tamanho inválido ('\3')."),
        (r"Element '([^']+)': '([^']*)' is not a valid value of the atomic type '([^']+)'\.",
         r"Campo '\1' com valor '\2' inválido para o tipo exigido."),
    ]
    for padrao, sub in trocas:
        novo = re.sub(padrao, sub, m)
        if novo != m:
            return novo
    return m


def validar_evento(xml: str, tipo: str) -> List[str]:
    """Lista de erros de estrutura (vazia = evento válido no XSD). O XML precisa estar assinado."""
    _evt, nome_xsd, _g = EVENTOS[tipo]
    try:
        doc = etree.fromstring(xml.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return [f"XML mal formado: {exc}"]
    schema = _schema(nome_xsd, pacote_vigente())
    if schema.validate(doc):
        return []
    vistos, erros = set(), []
    for e in schema.error_log:
        msg = f"Linha {e.line}: {_traduz(e.message)}"
        if msg not in vistos:
            vistos.add(msg)
            erros.append(msg)
    return erros


def validar_lote(xml: str) -> List[str]:
    schema = _schema("EnvioLoteEventos-v1_1_1", "comunicacao")
    doc = etree.fromstring(xml.encode("utf-8"))
    if schema.validate(doc):
        return []
    return [_traduz(e.message) for e in schema.error_log]
