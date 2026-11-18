"""Geradores dos eventos do eSocial no leiaute S-1.3.

Cada função recebe os dados já carregados do banco e devolve (evento_id, xml) sem assinatura.
A assinatura é aplicada depois (assinatura.py) e a estrutura é conferida contra o XSD oficial
(validacao.py). As regras de preenchimento seguem os leiautes S-1.3 até a NT 07/2026.
"""
import itertools
import re
import threading
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from lxml import etree

from .tabelas import (EVENTOS, RUBRICAS_NAO_ENVIADAS, TP_JORNADA_POR_ESCALA, UND_SAL_FIXO, VER_PROC,
                      VERSAO_LEIAUTE, pacote_vigente, rubrica_esocial)

_NS_BASE = "http://www.esocial.gov.br/schema/evt/{evt}/" + VERSAO_LEIAUTE

_seq_lock = threading.Lock()
_seq_state = {"stamp": "", "seq": itertools.count(1)}


class DadosIncompletos(ValueError):
    """Faltam dados obrigatórios no cadastro para gerar o evento."""

    def __init__(self, problemas: List[str]):
        super().__init__("; ".join(problemas))
        self.problemas = problemas


# ─── utilitários ──────────────────────────────────────────────────────────────

def digitos(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def txt(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def valor(v: Any) -> str:
    return str(Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def data_iso(v: Any) -> str:
    s = str(v or "")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def nr_insc_empregador(company: Dict[str, Any]) -> str:
    """Pessoa jurídica informa a raiz do CNPJ (8 posições)."""
    return digitos(company.get("cnpj"))[:8]


def gerar_id(company: Dict[str, Any]) -> str:
    """Id do evento: ID + T + inscrição (14, zeros à direita) + AAAAMMDDHHMMSS + sequencial (5)."""
    insc = nr_insc_empregador(company).ljust(14, "0")
    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    with _seq_lock:
        if _seq_state["stamp"] != agora:
            _seq_state["stamp"] = agora
            _seq_state["seq"] = itertools.count(1)
        seq = next(_seq_state["seq"])
    return f"ID1{insc}{agora}{seq:05d}"


def _el(parent, tag: str, value: Any = None, obrig: bool = False):
    """Cria um filho; valores vazios só saem quando obrigatórios (para o XSD apontar o erro)."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if not obrig:
            return None
        value = ""
    e = etree.SubElement(parent, tag)
    e.text = str(value)
    return e


def _grupo(parent, tag: str):
    return etree.SubElement(parent, tag)


def _raiz(tipo: str, company: Dict[str, Any]):
    evt, _xsd, _grupo_lote = EVENTOS[tipo]
    ns = _NS_BASE.format(evt=evt)
    root = etree.Element("eSocial", nsmap={None: ns})
    ev_id = gerar_id(company)
    evt_el = etree.SubElement(root, evt, Id=ev_id)
    return root, evt_el, ev_id




def _qualifica(root):
    """Move todos os elementos para o namespace do evento (exigência do XSD)."""
    ns = root.nsmap[None]
    for el in root.iter():
        if isinstance(el.tag, str) and not el.tag.startswith("{"):
            el.tag = f"{{{ns}}}{el.tag}"
    etree.cleanup_namespaces(root)
    return root


def _fim(root) -> str:
    return etree.tostring(_qualifica(root), encoding="unicode")


def _ide_evento(evt_el, amb: int, retif: Optional[Dict[str, str]] = None, extra: Optional[List[Tuple[str, Any]]] = None,
                proc_emi: str = "1", com_retif: bool = True):
    ide = _grupo(evt_el, "ideEvento")
    if com_retif:
        _el(ide, "indRetif", "2" if retif and retif.get("nr_recibo") else "1", True)
        if retif and retif.get("nr_recibo"):
            _el(ide, "nrRecibo", retif["nr_recibo"])
    for tag, v in (extra or []):
        _el(ide, tag, v)
    _el(ide, "tpAmb", amb, True)
    _el(ide, "procEmi", proc_emi, True)
    _el(ide, "verProc", VER_PROC, True)
    return ide


def _ide_empregador(evt_el, company):
    ide = _grupo(evt_el, "ideEmpregador")
    _el(ide, "tpInsc", "1", True)
    _el(ide, "nrInsc", nr_insc_empregador(company), True)


def _checa(problemas: List[str]):
    if problemas:
        raise DadosIncompletos(problemas)


def _ini_valid(cfg: Dict[str, Any]) -> str:
    v = str(cfg.get("ini_valid") or "")[:7]
    return v if re.fullmatch(r"\d{4}-\d{2}", v) else date.today().strftime("%Y-%m")


# ─── S-1000 Informações do empregador ─────────────────────────────────────────

def s1000(company, cfg, amb: int, operacao: str = "inclusao") -> Tuple[str, str]:
    problemas = []
    if len(digitos(company.get("cnpj"))) != 14:
        problemas.append("CNPJ da empresa inválido ou não cadastrado")
    class_trib = str(cfg.get("class_trib") or "")
    if not re.fullmatch(r"\d{2}", class_trib):
        problemas.append("Classificação tributária não configurada (Central eSocial → Configuração)")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-1000", company)
    _ide_evento(evt, amb, com_retif=False)
    _ide_empregador(evt, company)
    info = _grupo(evt, "infoEmpregador")
    op = _grupo(info, operacao)
    per = _grupo(op, "idePeriodo")
    _el(per, "iniValid", _ini_valid(cfg), True)
    if operacao != "exclusao":
        cad = _grupo(op, "infoCadastro")
        _el(cad, "classTrib", class_trib, True)
        _el(cad, "indCoop", "0" if class_trib == "99" else None)
        _el(cad, "indConstr", "0" if class_trib == "99" else None)
        _el(cad, "indDesFolha", str(cfg.get("ind_des_folha") or "0"), True)
        if class_trib in ("01", "02", "03", "04") or cfg.get("ind_porte"):
            _el(cad, "indPorte", "S")
        # Até 22/11/2026 o XSD exige o campo; depois vale a regra da NT 07/2026 (não informar a partir de 2026-02)
        if pacote_vigente() == "eventos_20261026" or _ini_valid(cfg) < "2026-02":
            _el(cad, "indOptRegEletron", str(cfg.get("ind_opt_reg_eletron") or "0"), True)
    return ev_id, _fim(root)


# ─── S-1005 Estabelecimentos ──────────────────────────────────────────────────

def s1005(company, cfg, amb: int, operacao: str = "inclusao") -> Tuple[str, str]:
    cnpj = digitos(company.get("cnpj"))
    cnae = digitos(cfg.get("cnae") or company.get("cnae_principal"))
    problemas = []
    if len(cnpj) != 14:
        problemas.append("CNPJ da empresa inválido")
    if len(cnae) != 7:
        problemas.append("CNAE principal com 7 dígitos não informado (cadastro da empresa ou configuração do eSocial)")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-1005", company)
    _ide_evento(evt, amb, com_retif=False)
    _ide_empregador(evt, company)
    info = _grupo(evt, "infoEstab")
    op = _grupo(info, operacao)
    ide = _grupo(op, "ideEstab")
    _el(ide, "tpInsc", "1", True)
    _el(ide, "nrInsc", cnpj, True)
    _el(ide, "iniValid", _ini_valid(cfg), True)
    if operacao != "exclusao":
        dados = _grupo(op, "dadosEstab")
        _el(dados, "cnaePrep", cnae, True)
        fap = cfg.get("fap")
        aliq = cfg.get("aliq_rat")
        if fap or aliq:
            g = _grupo(dados, "aliqGilrat")
            _el(g, "aliqRat", aliq)
            _el(g, "fap", f"{float(fap):.4f}" if fap else None)
    return ev_id, _fim(root)


# ─── S-1010 Rubricas ──────────────────────────────────────────────────────────

def s1010(company, cfg, amb: int, rubrica: Dict[str, Any], operacao: str = "inclusao") -> Tuple[str, str]:
    codigo = txt(rubrica.get("codigo"))
    nome = txt(rubrica.get("nome"))
    if not codigo or not nome:
        raise DadosIncompletos(["Rubrica sem código ou descrição"])
    nat, tp, inc_cp, inc_ir, inc_fgts = rubrica_esocial(
        codigo, rubrica.get("tipo") or "provento", int(rubrica.get("incide_inss") or 0),
        int(rubrica.get("incide_irrf") or 0), int(rubrica.get("incide_fgts") or 0),
        str(rubrica.get("esocial_nat_rubrica") or ""))
    root, evt, ev_id = _raiz("S-1010", company)
    _ide_evento(evt, amb, com_retif=False)
    _ide_empregador(evt, company)
    info = _grupo(evt, "infoRubrica")
    op = _grupo(info, operacao)
    ide = _grupo(op, "ideRubrica")
    _el(ide, "codRubr", codigo, True)
    _el(ide, "ideTabRubr", ide_tab_rubr(cfg), True)
    _el(ide, "iniValid", _ini_valid(cfg), True)
    if operacao != "exclusao":
        d = _grupo(op, "dadosRubrica")
        _el(d, "dscRubr", nome[:100], True)
        _el(d, "natRubr", nat, True)
        _el(d, "tpRubr", tp, True)
        _el(d, "codIncCP", inc_cp, True)
        _el(d, "codIncIRRF", inc_ir, True)
        _el(d, "codIncFGTS", inc_fgts, True)
    return ev_id, _fim(root)


def ide_tab_rubr(cfg) -> str:
    return (txt(cfg.get("ide_tab_rubr")) or "CORTEX")[:8]


def cod_lotacao(cfg) -> str:
    return (txt(cfg.get("cod_lotacao")) or "LOTACAO01")[:30]


# ─── S-1020 Lotação tributária ────────────────────────────────────────────────

def s1020(company, cfg, amb: int, operacao: str = "inclusao") -> Tuple[str, str]:
    fpas = digitos(cfg.get("fpas"))
    class_trib = str(cfg.get("class_trib") or "")
    cod_tercs = digitos(cfg.get("cod_tercs")) or ("0000" if class_trib in ("01", "02", "03", "04") else "")
    problemas = []
    if len(fpas) != 3:
        problemas.append("Código FPAS não configurado (ex.: 515 para comércio e serviços)")
    if len(cod_tercs) != 4:
        problemas.append("Código de terceiros não configurado (Simples Nacional usa 0000)")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-1020", company)
    _ide_evento(evt, amb, com_retif=False)
    _ide_empregador(evt, company)
    info = _grupo(evt, "infoLotacao")
    op = _grupo(info, operacao)
    ide = _grupo(op, "ideLotacao")
    _el(ide, "codLotacao", cod_lotacao(cfg), True)
    _el(ide, "iniValid", _ini_valid(cfg), True)
    if operacao != "exclusao":
        d = _grupo(op, "dadosLotacao")
        _el(d, "tpLotacao", "01", True)
        f = _grupo(d, "fpasLotacao")
        _el(f, "fpas", fpas, True)
        _el(f, "codTercs", cod_tercs, True)
    return ev_id, _fim(root)


# ─── S-2200 Admissão ──────────────────────────────────────────────────────────

def _problemas_trabalhador(emp: Dict[str, Any]) -> List[str]:
    p = []
    if len(digitos(emp.get("cpf"))) != 11:
        p.append("CPF")
    if not txt(emp.get("name")):
        p.append("nome")
    if (emp.get("sexo") or "") not in ("M", "F"):
        p.append("sexo")
    if not data_iso(emp.get("birth_date")):
        p.append("data de nascimento")
    if not txt(emp.get("logradouro")) or not txt(emp.get("numero")):
        p.append("endereço (logradouro e número)")
    if len(digitos(emp.get("cep"))) != 8:
        p.append("CEP")
    if len(digitos(emp.get("cod_municipio"))) != 7:
        p.append("código IBGE do município")
    if not (emp.get("uf") or ""):
        p.append("UF do endereço")
    return p


def _endereco(parent, emp, tag="endereco"):
    end = _grupo(parent, tag)
    br = _grupo(end, "brasil")
    _el(br, "dscLograd", txt(emp.get("logradouro"))[:100], True)
    _el(br, "nrLograd", txt(emp.get("numero"))[:10] or "S/N", True)
    _el(br, "complemento", txt(emp.get("complemento"))[:30])
    _el(br, "bairro", txt(emp.get("bairro"))[:90])
    _el(br, "cep", digitos(emp.get("cep")), True)
    _el(br, "codMunic", digitos(emp.get("cod_municipio")), True)
    _el(br, "uf", (emp.get("uf") or "").upper(), True)


def _deficiencia(parent, emp, dt_adm: str):
    d = (emp.get("deficiencia") or "").lower()
    g = _grupo(parent, "infoDeficiencia")
    for campo, chave in (("defFisica", "fisica"), ("defVisual", "visual"), ("defAuditiva", "auditiva"),
                         ("defMental", "mental"), ("defIntelectual", "intelectual"), ("reabReadap", "reabilitado")):
        _el(g, campo, "S" if d == chave else "N", True)
    # infoCota: só para admissões anteriores a 26/10/2026 (NT 07/2026)
    if dt_adm and dt_adm < "2026-10-26":
        _el(g, "infoCota", "S" if d else "N", True)


def _dependentes(parent, deps: List[Dict[str, Any]], tp_reg_prev: str = "1"):
    for dep in deps[:99]:
        g = _grupo(parent, "dependente")
        _el(g, "tpDep", str(dep.get("parentesco") or "03").zfill(2))
        _el(g, "nmDep", txt(dep.get("nome"))[:70], True)
        _el(g, "dtNascto", data_iso(dep.get("data_nascimento")), True)
        _el(g, "cpfDep", digitos(dep.get("cpf")) or None)
        _el(g, "sexoDep", dep.get("sexo") or None)
        _el(g, "depIRRF", "S" if dep.get("irrf") else "N", True)
        _el(g, "depSF", "S" if dep.get("salario_familia") else "N", True)
        _el(g, "incTrab", "N", True)


def _contato(parent, emp):
    fone = digitos(emp.get("celular") or emp.get("phone") or emp.get("telefone"))
    email = txt(emp.get("email"))
    if (8 <= len(fone) <= 13) or (6 <= len(email) <= 60 and "@" in email):
        g = _grupo(parent, "contato")
        _el(g, "fonePrinc", fone if 8 <= len(fone) <= 13 else None)
        _el(g, "emailPrinc", email if 6 <= len(email) <= 60 and "@" in email else None)


def _dt_term(emp: Dict[str, Any], dt_adm: str) -> str:
    if data_iso(emp.get("data_termino_contrato")):
        return data_iso(emp.get("data_termino_contrato"))
    dias = int(emp.get("experiencia_dias") or 0) + int(emp.get("experiencia_prorrogacao") or 0)
    if dias and dt_adm:
        return (date.fromisoformat(dt_adm) + timedelta(days=dias - 1)).isoformat()
    return ""


def descricao_jornada(emp: Dict[str, Any]) -> str:
    d = txt(emp.get("descricao_jornada"))
    if d:
        return d[:999]
    e, s = emp.get("horario_entrada"), emp.get("horario_saida")
    ii, fi = emp.get("intervalo_inicio"), emp.get("intervalo_fim")
    escala = emp.get("escala") or ""
    if e and s:
        base = f"{e} às {ii} e {fi} às {s}" if ii and fi else f"{e} às {s}"
        return f"{base}" + (f", escala {escala}" if escala else "")
    horas = emp.get("horas_semana") or 44
    return f"Jornada de {float(horas):g} horas semanais" + (f", escala {escala}" if escala else "")


def s2200(company, cfg, amb: int, emp: Dict[str, Any], deps: List[Dict[str, Any]],
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    problemas = [f"Funcionário sem {c}" for c in _problemas_trabalhador(emp)]
    dt_adm = data_iso(emp.get("admission_date"))
    if not dt_adm:
        problemas.append("Funcionário sem data de admissão")
    if len(digitos(emp.get("sindicato_cnpj"))) != 14:
        problemas.append("Funcionário sem CNPJ do sindicato da categoria (aba Contrato)")
    if len(digitos(company.get("cnpj"))) != 14:
        problemas.append("CNPJ da empresa inválido")
    if dt_adm >= "2024-04-22" and str(emp.get("raca_cor") or "") in ("", "6"):
        problemas.append("Raça/cor obrigatória (não pode ser 'Não informado' para admissões desde 22/04/2024)")
    matricula = txt(emp.get("matricula"))
    if not matricula:
        problemas.append("Funcionário sem matrícula")
    if not txt(emp.get("role")):
        problemas.append("Funcionário sem cargo")
    _checa(problemas)

    cod_categ = digitos(emp.get("esocial_category")) or "101"
    root, evt, ev_id = _raiz("S-2200", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)

    t = _grupo(evt, "trabalhador")
    _el(t, "cpfTrab", digitos(emp.get("cpf")), True)
    _el(t, "nmTrab", txt(emp.get("name"))[:70], True)
    _el(t, "sexo", emp.get("sexo"), True)
    _el(t, "racaCor", str(emp.get("raca_cor") or "6"), True)
    _el(t, "estCiv", str(emp.get("estado_civil") or "") or None)
    _el(t, "grauInstr", str(emp.get("grau_instrucao") or "07").zfill(2), True)
    _el(t, "nmSoc", txt(emp.get("nome_social"))[:70] or None)
    n = _grupo(t, "nascimento")
    _el(n, "dtNascto", data_iso(emp.get("birth_date")), True)
    _el(n, "paisNascto", digitos(emp.get("pais_nascimento")).zfill(3) if emp.get("pais_nascimento") else "105", True)
    _el(n, "paisNac", "105", True)
    _endereco(t, emp)
    _deficiencia(t, emp, dt_adm)
    _dependentes(t, deps)
    _contato(t, emp)

    v = _grupo(evt, "vinculo")
    _el(v, "matricula", matricula[:30], True)
    _el(v, "tpRegTrab", "1", True)
    _el(v, "tpRegPrev", str(emp.get("regime_previdenciario") or "1"), True)
    _el(v, "cadIni", "N", True)
    reg = _grupo(v, "infoRegimeTrab")
    cel = _grupo(reg, "infoCeletista")
    _el(cel, "dtAdm", dt_adm, True)
    _el(cel, "tpAdmissao", str(emp.get("tipo_admissao") or "1"), True)
    _el(cel, "indAdmissao", str(emp.get("ind_admissao") or "1"), True)
    _el(cel, "tpRegJor", "1", True)
    _el(cel, "natAtividade", "1", True)
    if str(emp.get("data_base_mes") or "").isdigit():
        _el(cel, "dtBase", str(int(emp.get("data_base_mes"))))
    _el(cel, "cnpjSindCategProf", digitos(emp.get("sindicato_cnpj")), True)

    c = _grupo(v, "infoContrato")
    _el(c, "nmCargo", txt(emp.get("role"))[:100], True)
    _el(c, "CBOCargo", digitos(emp.get("cbo")) or None)
    _el(c, "codCateg", cod_categ, True)
    r = _grupo(c, "remuneracao")
    _el(r, "vrSalFx", valor(emp.get("salary")), True)
    und = str(emp.get("tipo_salario") or "5")
    _el(r, "undSalFixo", und if und in UND_SAL_FIXO else "5", True)
    if und in ("6", "7"):
        _el(r, "dscSalVar", "Remuneração variável conforme contrato", True)
    d = _grupo(c, "duracao")
    tipo_contr = (emp.get("tipo_contrato") or "indeterminado")
    if tipo_contr in ("experiencia", "determinado"):
        _el(d, "tpContr", "2", True)
        _el(d, "dtTerm", _dt_term(emp, dt_adm), True)
        _el(d, "clauAssec", "N", True)
    else:
        _el(d, "tpContr", "1", True)
    lt = _grupo(c, "localTrabalho")
    lg = _grupo(lt, "localTrabGeral")
    _el(lg, "tpInsc", "1", True)
    _el(lg, "nrInsc", digitos(company.get("cnpj")), True)
    h = _grupo(c, "horContratual")
    horas = float(emp.get("horas_semana") or 44)
    _el(h, "qtdHrsSem", f"{min(horas, 99.99):.2f}")
    _el(h, "tpJornada", TP_JORNADA_POR_ESCALA.get(emp.get("escala") or "", "9"), True)
    _el(h, "tmpParc", "0" if (emp.get("jornada_tipo") or "integral") != "parcial" else ("1" if horas <= 25 else "2" if horas <= 26 else "3"), True)
    _el(h, "dscJorn", descricao_jornada(emp), True)
    return ev_id, _fim(root)


# ─── S-2205 Alteração cadastral ───────────────────────────────────────────────

def s2205(company, cfg, amb: int, emp: Dict[str, Any], deps: List[Dict[str, Any]], dt_alteracao: str,
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    problemas = [f"Funcionário sem {c}" for c in _problemas_trabalhador(emp)]
    if not data_iso(dt_alteracao):
        problemas.append("Data da alteração inválida")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-2205", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    ide = _grupo(evt, "ideTrabalhador")
    _el(ide, "cpfTrab", digitos(emp.get("cpf")), True)
    alt = _grupo(evt, "alteracao")
    _el(alt, "dtAlteracao", data_iso(dt_alteracao), True)
    db = _grupo(alt, "dadosTrabalhador")
    _el(db, "nmTrab", txt(emp.get("name"))[:70], True)
    _el(db, "sexo", emp.get("sexo"), True)
    _el(db, "racaCor", str(emp.get("raca_cor") or "6"), True)
    _el(db, "estCiv", str(emp.get("estado_civil") or "") or None)
    _el(db, "grauInstr", str(emp.get("grau_instrucao") or "07").zfill(2), True)
    _el(db, "nmSoc", txt(emp.get("nome_social"))[:70] or None)
    _el(db, "paisNac", "105", True)
    _endereco(db, emp)
    _deficiencia(db, emp, "9999-12-31")
    _dependentes(db, deps)
    _contato(db, emp)
    return ev_id, _fim(root)


# ─── S-2206 Alteração contratual ──────────────────────────────────────────────

def s2206(company, cfg, amb: int, emp: Dict[str, Any], dt_alteracao: str, dt_efeito: str = "",
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    problemas = []
    if len(digitos(emp.get("cpf"))) != 11:
        problemas.append("Funcionário sem CPF")
    if not txt(emp.get("matricula")):
        problemas.append("Funcionário sem matrícula")
    if not data_iso(dt_alteracao):
        problemas.append("Data da alteração inválida")
    if len(digitos(emp.get("sindicato_cnpj"))) != 14:
        problemas.append("Funcionário sem CNPJ do sindicato")
    _checa(problemas)
    dt_adm = data_iso(emp.get("admission_date"))
    root, evt, ev_id = _raiz("S-2206", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    ide = _grupo(evt, "ideVinculo")
    _el(ide, "cpfTrab", digitos(emp.get("cpf")), True)
    _el(ide, "matricula", txt(emp.get("matricula"))[:30], True)
    alt = _grupo(evt, "altContratual")
    _el(alt, "dtAlteracao", data_iso(dt_alteracao), True)
    _el(alt, "dtEf", data_iso(dt_efeito) or None)
    v = _grupo(alt, "vinculo")
    _el(v, "tpRegPrev", str(emp.get("regime_previdenciario") or "1"), True)
    reg = _grupo(v, "infoRegimeTrab")
    cel = _grupo(reg, "infoCeletista")
    _el(cel, "tpRegJor", "1", True)
    _el(cel, "natAtividade", "1", True)
    if str(emp.get("data_base_mes") or "").isdigit():
        _el(cel, "dtBase", str(int(emp.get("data_base_mes"))))
    _el(cel, "cnpjSindCategProf", digitos(emp.get("sindicato_cnpj")), True)
    c = _grupo(v, "infoContrato")
    _el(c, "nmCargo", txt(emp.get("role"))[:100], True)
    _el(c, "CBOCargo", digitos(emp.get("cbo")) or None)
    _el(c, "codCateg", digitos(emp.get("esocial_category")) or "101", True)
    r = _grupo(c, "remuneracao")
    _el(r, "vrSalFx", valor(emp.get("salary")), True)
    und = str(emp.get("tipo_salario") or "5")
    _el(r, "undSalFixo", und if und in UND_SAL_FIXO else "5", True)
    if und in ("6", "7"):
        _el(r, "dscSalVar", "Remuneração variável conforme contrato", True)
    d = _grupo(c, "duracao")
    if (emp.get("tipo_contrato") or "") in ("experiencia", "determinado"):
        _el(d, "tpContr", "2", True)
        _el(d, "dtTerm", _dt_term(emp, dt_adm), True)
    else:
        _el(d, "tpContr", "1", True)
    lt = _grupo(c, "localTrabalho")
    lg = _grupo(lt, "localTrabGeral")
    _el(lg, "tpInsc", "1", True)
    _el(lg, "nrInsc", digitos(company.get("cnpj")), True)
    h = _grupo(c, "horContratual")
    horas = float(emp.get("horas_semana") or 44)
    _el(h, "qtdHrsSem", f"{min(horas, 99.99):.2f}")
    _el(h, "tpJornada", TP_JORNADA_POR_ESCALA.get(emp.get("escala") or "", "9"), True)
    _el(h, "tmpParc", "0" if (emp.get("jornada_tipo") or "integral") != "parcial" else "3", True)
    _el(h, "dscJorn", descricao_jornada(emp), True)
    return ev_id, _fim(root)


# ─── S-2230 Afastamento temporário ────────────────────────────────────────────

def s2230(company, cfg, amb: int, emp: Dict[str, Any], cod_motivo: str, dt_inicio: str, dt_fim: str = "",
          observacao: str = "", retif: Optional[Dict[str, str]] = None, so_termino: bool = False) -> Tuple[str, str]:
    problemas = []
    if len(digitos(emp.get("cpf"))) != 11:
        problemas.append("Funcionário sem CPF")
    if not txt(emp.get("matricula")):
        problemas.append("Funcionário sem matrícula")
    if not so_termino and not data_iso(dt_inicio):
        problemas.append("Data de início do afastamento inválida")
    if so_termino and not data_iso(dt_fim):
        problemas.append("Data de término do afastamento inválida")
    if not so_termino and not re.fullmatch(r"\d{2}", cod_motivo or ""):
        problemas.append("Motivo do afastamento sem código do eSocial (Tabela 18)")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-2230", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    ide = _grupo(evt, "ideVinculo")
    _el(ide, "cpfTrab", digitos(emp.get("cpf")), True)
    _el(ide, "matricula", txt(emp.get("matricula"))[:30], True)
    info = _grupo(evt, "infoAfastamento")
    if not so_termino:
        ini = _grupo(info, "iniAfastamento")
        _el(ini, "dtIniAfast", data_iso(dt_inicio), True)
        _el(ini, "codMotAfast", cod_motivo, True)
        _el(ini, "observacao", txt(observacao)[:255] or ("Afastamento" if cod_motivo == "21" else None))
    if data_iso(dt_fim):
        fim = _grupo(info, "fimAfastamento")
        _el(fim, "dtTermAfast", data_iso(dt_fim), True)
    return ev_id, _fim(root)


# ─── S-2299 Desligamento ──────────────────────────────────────────────────────

def _itens(parent, tag: str, linhas: List[Dict[str, Any]], cfg, per_apur: str):
    n = 0
    for ln in linhas:
        cod = txt(ln.get("codigo"))
        if cod in RUBRICAS_NAO_ENVIADAS or (ln.get("tipo") not in ("provento", "desconto")):
            continue
        vr = Decimal(str(ln.get("valor") or 0))
        if vr <= 0:
            continue
        it = _grupo(parent, tag)
        _el(it, "codRubr", cod, True)
        _el(it, "ideTabRubr", ide_tab_rubr(cfg), True)
        qtd = _qtd(ln.get("referencia"))
        _el(it, "qtdRubr", qtd)
        _el(it, "vrRubr", valor(vr), True)
        _el(it, "indApurIR", "0", True)
        n += 1
    return n


def _qtd(ref: Any) -> Optional[str]:
    m = re.match(r"^\s*([\d.,]+)", str(ref or ""))
    if not m:
        return None
    try:
        q = Decimal(m.group(1).replace(".", "").replace(",", ".") if "," in m.group(1) else m.group(1))
    except Exception:
        return None
    return str(q.quantize(Decimal("0.01"))) if 0 < q < Decimal("9999999999") else None



def s2299(company, cfg, amb: int, emp: Dict[str, Any], mtv_deslig: str, dt_deslig: str,
          linhas: List[Dict[str, Any]], dt_aviso: str = "", ide_dm_dev: str = "",
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    problemas = []
    if len(digitos(emp.get("cpf"))) != 11:
        problemas.append("Funcionário sem CPF")
    if not txt(emp.get("matricula")):
        problemas.append("Funcionário sem matrícula")
    if not data_iso(dt_deslig):
        problemas.append("Data de desligamento inválida")
    if not re.fullmatch(r"\d{2}", mtv_deslig or ""):
        problemas.append("Motivo de desligamento sem código do eSocial (Tabela 19)")
    _checa(problemas)
    per_apur = data_iso(dt_deslig)[:7]
    root, evt, ev_id = _raiz("S-2299", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    ide = _grupo(evt, "ideVinculo")
    _el(ide, "cpfTrab", digitos(emp.get("cpf")), True)
    _el(ide, "matricula", txt(emp.get("matricula"))[:30], True)
    info = _grupo(evt, "infoDeslig")
    _el(info, "mtvDeslig", mtv_deslig, True)
    _el(info, "dtDeslig", data_iso(dt_deslig), True)
    if data_iso(dt_aviso):
        _el(info, "dtAvPrv", data_iso(dt_aviso))
    _el(info, "indPagtoAPI", "N", True)
    _el(info, "pensAlim", "0", True)
    sem_verbas = mtv_deslig in ("11", "12", "13", "25", "28", "29", "30", "34", "36", "43", "44")
    if not sem_verbas and linhas:
        vr = _grupo(info, "verbasResc")
        dm = _grupo(vr, "dmDev")
        _el(dm, "ideDmDev", (ide_dm_dev or f"RESC{per_apur.replace('-', '')}")[:30], True)
        pa = _grupo(dm, "infoPerApur")
        est = _grupo(pa, "ideEstabLot")
        _el(est, "tpInsc", "1", True)
        _el(est, "nrInsc", digitos(company.get("cnpj")), True)
        _el(est, "codLotacao", cod_lotacao(cfg), True)
        if not _itens(est, "detVerbas", linhas, cfg, per_apur):
            vr.getparent().remove(vr)
    return ev_id, _fim(root)


# ─── S-1200 Remuneração ───────────────────────────────────────────────────────

CATEG_COMPL_CONT = ("2", "304", "305", "4", "5", "7", "902")


def _info_per_ant(dm, company, cfg, d: Dict[str, Any], linhas: List[Dict[str, Any]], per_apur: str) -> int:
    """Grupo infoPerAnt: diferenças de acordo/convenção/dissídio de períodos anteriores, um idePeriodo
    por mês de referência (perRef)."""
    acordo = d.get("per_ant") or {}
    tp = txt(acordo.get("tp_acordo")) or "C"
    dt = data_iso(acordo.get("dt_acordo"))
    problemas = []
    if tp in ("A", "B", "C", "D", "E") and not dt:
        problemas.append("Diferenças retroativas sem a data do acordo/convenção/sentença")
    if dt and dt[:7] > per_apur:
        problemas.append("Data do acordo posterior ao período de apuração")
    _checa(problemas)
    pant = _grupo(dm, "infoPerAnt")
    adc = _grupo(pant, "ideADC")
    if dt:
        _el(adc, "dtAcConv", dt)
    _el(adc, "tpAcConv", tp, True)
    _el(adc, "dsc", (txt(acordo.get("descricao")) or "Diferencas salariais")[:255], True)
    _el(adc, "remunSuc", "N", True)
    por_mes: Dict[str, List[Dict[str, Any]]] = {}
    for l in linhas:
        por_mes.setdefault(str(l["per_ref"])[:7], []).append(l)
    total = 0
    for per in sorted(por_mes)[:180]:
        ip = _grupo(adc, "idePeriodo")
        _el(ip, "perRef", per, True)
        est = _grupo(ip, "ideEstabLot")
        _el(est, "tpInsc", "1", True)
        _el(est, "nrInsc", digitos(company.get("cnpj")), True)
        _el(est, "codLotacao", cod_lotacao(cfg), True)
        rem = _grupo(est, "remunPerAnt")
        _el(rem, "matricula", txt(d.get("matricula"))[:30] or None)
        if str(cfg.get("class_trib") or "") == "03":
            _el(rem, "indSimples", "3", True)
        k = _itens(rem, "itensRemun", por_mes[per], cfg, per)
        if not k:
            adc.remove(ip)
        total += k
    if not total:
        dm.remove(pant)
    return total


def s1200(company, cfg, amb: int, trab: Dict[str, Any], per_apur: str, dm_devs: List[Dict[str, Any]],
          ind_apuracao: str = "1", retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """Remuneração do trabalhador no período: um evento por CPF, com um demonstrativo (dmDev) por origem
    (folha mensal, férias, 13º, bolsa de estágio, RPA...).

    trab: {cpf, nome, dt_nasc, cbo, sem_cadastro (True = sem S-2200/S-2300, exige infoComplem)}
    dm_devs: [{ide_dm_dev, cod_categ, matricula (opcional), linhas}]
    """
    problemas = []
    if len(digitos(trab.get("cpf"))) != 11:
        problemas.append("Trabalhador sem CPF")
    padrao = r"\d{4}-\d{2}" if ind_apuracao == "1" else r"\d{4}"
    if not re.fullmatch(padrao, per_apur or ""):
        problemas.append("Período de apuração inválido")
    if not dm_devs:
        problemas.append("Nenhum demonstrativo de valores para informar")
    if trab.get("sem_cadastro") and (not txt(trab.get("nome")) or not data_iso(trab.get("dt_nasc"))):
        problemas.append("Trabalhador sem cadastro no eSocial: informe nome e data de nascimento")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-1200", company)
    _ide_evento(evt, amb, retif, extra=[("indApuracao", ind_apuracao), ("perApur", per_apur)])
    _ide_empregador(evt, company)
    ide = _grupo(evt, "ideTrabalhador")
    _el(ide, "cpfTrab", digitos(trab.get("cpf")), True)
    if trab.get("sem_cadastro"):
        ic = _grupo(ide, "infoComplem")
        _el(ic, "nmTrab", txt(trab.get("nome"))[:70], True)
        _el(ic, "dtNascto", data_iso(trab.get("dt_nasc")), True)
    com_itens = 0
    for d in dm_devs[:999]:
        dm = _grupo(evt, "dmDev")
        _el(dm, "ideDmDev", str(d["ide_dm_dev"])[:30], True)
        categ = digitos(d.get("cod_categ")) or "101"
        _el(dm, "codCateg", categ, True)
        linhas_d = d.get("linhas") or []
        atuais = [l for l in linhas_d if not l.get("per_ref")]
        anteriores = [l for l in linhas_d if l.get("per_ref")]
        n = 0
        if atuais:
            pa = _grupo(dm, "infoPerApur")
            est = _grupo(pa, "ideEstabLot")
            _el(est, "tpInsc", "1", True)
            _el(est, "nrInsc", digitos(company.get("cnpj")), True)
            _el(est, "codLotacao", cod_lotacao(cfg), True)
            rem = _grupo(est, "remunPerApur")
            _el(rem, "matricula", txt(d.get("matricula"))[:30] or None)
            if str(cfg.get("class_trib") or "") == "03":
                _el(rem, "indSimples", "3", True)
            k = _itens(rem, "itensRemun", atuais, cfg, per_apur)
            if not k:
                dm.remove(pa)
            n += k
        if anteriores and ind_apuracao == "1":
            n += _info_per_ant(dm, company, cfg, d, anteriores, per_apur)
        if not n:
            evt.remove(dm)
            continue
        com_itens += n
        if trab.get("sem_cadastro") and categ.startswith(CATEG_COMPL_CONT):
            cc = _grupo(dm, "infoComplCont")
            _el(cc, "codCBO", digitos(trab.get("cbo")) or "", True)
    if not com_itens:
        raise DadosIncompletos(["Nenhuma rubrica com valor para informar"])
    return ev_id, _fim(root)


# ─── S-1210 Pagamentos ────────────────────────────────────────────────────────

def s1210(company, cfg, amb: int, emp: Dict[str, Any], per_apur: str,
          pagamentos: List[Dict[str, Any]], retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """pagamentos: [{dt_pgto, tp_pgto ('1' folha | '2' rescisão), per_ref, ide_dm_dev, vr_liq}]"""
    problemas = []
    if len(digitos(emp.get("cpf"))) != 11:
        problemas.append("Funcionário sem CPF")
    for p in pagamentos:
        if not data_iso(p.get("dt_pgto")) or data_iso(p.get("dt_pgto"))[:7] != per_apur:
            problemas.append(f"Data de pagamento deve estar dentro da competência {per_apur}")
            break
    if not pagamentos:
        problemas.append("Nenhum pagamento para informar")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-1210", company)
    _ide_evento(evt, amb, retif, extra=[("perApur", per_apur)])
    _ide_empregador(evt, company)
    ben = _grupo(evt, "ideBenef")
    _el(ben, "cpfBenef", digitos(emp.get("cpf")), True)
    for p in pagamentos[:999]:
        g = _grupo(ben, "infoPgto")
        _el(g, "dtPgto", data_iso(p["dt_pgto"]), True)
        _el(g, "tpPgto", str(p.get("tp_pgto") or "1"), True)
        _el(g, "perRef", p.get("per_ref") or per_apur, True)
        _el(g, "ideDmDev", str(p["ide_dm_dev"])[:30], True)
        _el(g, "vrLiq", valor(max(Decimal(str(p.get("vr_liq") or 0)), Decimal("0"))), True)
    return ev_id, _fim(root)


# ─── S-1298 / S-1299 Reabertura e fechamento ──────────────────────────────────

def s1298(company, cfg, amb: int, per_apur: str, ind_apuracao: str = "1") -> Tuple[str, str]:
    root, evt, ev_id = _raiz("S-1298", company)
    _ide_evento(evt, amb, com_retif=False, extra=[("indApuracao", ind_apuracao), ("perApur", per_apur)])
    _ide_empregador(evt, company)
    return ev_id, _fim(root)


def s1299(company, cfg, amb: int, per_apur: str, tem_remun: bool, tem_pgtos: bool,
          ind_apuracao: str = "1") -> Tuple[str, str]:
    root, evt, ev_id = _raiz("S-1299", company)
    _ide_evento(evt, amb, com_retif=False, extra=[("indApuracao", ind_apuracao), ("perApur", per_apur)])
    _ide_empregador(evt, company)
    f = _grupo(evt, "infoFech")
    _el(f, "evtRemun", "S" if tem_remun else "N", True)
    _el(f, "evtPgtos", "S" if tem_pgtos else "N", True)
    _el(f, "evtComProd", "N", True)
    _el(f, "evtContratAvNP", "N", True)
    _el(f, "evtInfoComplPer", "N", True)
    return ev_id, _fim(root)


# ─── S-3000 Exclusão ──────────────────────────────────────────────────────────

PERIODICOS = {"S-1200", "S-1202", "S-1207", "S-1210", "S-1250", "S-1260", "S-1270", "S-1280", "S-1300"}


def s3000(company, cfg, amb: int, tp_evento: str, nr_recibo: str, cpf: str = "",
          per_apur: str = "", ind_apuracao: str = "1") -> Tuple[str, str]:
    problemas = []
    if not re.fullmatch(r"1\.\d\.\d{19}", nr_recibo or ""):
        problemas.append("Número de recibo do evento a excluir inválido")
    tp = (tp_evento or "").upper()
    if not re.fullmatch(r"S-\d{4}", tp):
        problemas.append("Tipo do evento a excluir inválido")
    nao_periodico = tp >= "S-2190" and tp <= "S-2420"
    if nao_periodico and len(digitos(cpf)) != 11:
        problemas.append("CPF do trabalhador obrigatório para excluir evento não periódico")
    if tp in PERIODICOS and not re.fullmatch(r"\d{4}(-\d{2})?", per_apur or ""):
        problemas.append("Competência obrigatória para excluir evento periódico")
    _checa(problemas)
    root, evt, ev_id = _raiz("S-3000", company)
    _ide_evento(evt, amb, com_retif=False)
    _ide_empregador(evt, company)
    info = _grupo(evt, "infoExclusao")
    _el(info, "tpEvento", tp, True)
    _el(info, "nrRecEvt", nr_recibo, True)
    if nao_periodico:
        it = _grupo(info, "ideTrabalhador")
        _el(it, "cpfTrab", digitos(cpf), True)
    if tp in PERIODICOS:
        fp = _grupo(info, "ideFolhaPagto")
        if tp in ("S-1200", "S-1202", "S-1207", "S-1280", "S-1300"):
            _el(fp, "indApuracao", ind_apuracao, True)
        _el(fp, "perApur", per_apur, True)
    return ev_id, _fim(root)


# ─── SST: S-2210 CAT, S-2220 ASO, S-2240 condições ambientais ─────────────────

def _ide_vinculo_sst(evt, emp):
    ide = _grupo(evt, "ideVinculo")
    _el(ide, "cpfTrab", digitos(emp.get("cpf")), True)
    if txt(emp.get("matricula")):
        _el(ide, "matricula", txt(emp.get("matricula"))[:30], True)
    else:
        _el(ide, "codCateg", digitos(emp.get("esocial_category")) or "101", True)


def _hora(v: Any) -> str:
    d = digitos(v)
    return d[:4].zfill(4) if d else ""


def s2210(company, cfg, amb: int, emp: Dict[str, Any], cat: Dict[str, Any],
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    p = []
    if len(digitos(emp.get("cpf"))) != 11:
        p.append("Funcionário sem CPF")
    dt = data_iso(cat.get("data_acidente"))
    if not dt:
        p.append("Data do acidente")
    tp_acid = str(cat.get("tp_acid") or "1")
    if tp_acid in ("1", "3") and not _hora(cat.get("hora_acidente")):
        p.append("Hora do acidente")
    for campo, rot, tam in (("cod_sit_geradora", "Situação geradora (Tabela 15)", 9),
                            ("cod_parte_ating", "Parte do corpo atingida (Tabela 13)", 9),
                            ("cod_agnt_causador", "Agente causador (Tabela 14 ou 15)", 9),
                            ("cod_natureza_lesao", "Natureza da lesão (Tabela 17)", 9)):
        if len(digitos(cat.get(campo))) != tam:
            p.append(rot)
    if not data_iso(cat.get("dt_atendimento")) or not _hora(cat.get("hr_atendimento")):
        p.append("Data e hora do atendimento médico")
    if not (3 <= len(txt(cat.get("cod_cid")).replace(".", "")) <= 4):
        p.append("CID")
    if not txt(cat.get("nm_emit")) or not txt(cat.get("nr_oc")):
        p.append("Médico emitente do atestado (nome e número no conselho)")
    tp_local = str(cat.get("tp_local") or "1")
    if not txt(cat.get("local_logradouro")) and tp_local != "1":
        p.append("Endereço do local do acidente")
    tp_cat = str(cat.get("tp_cat") or "1")
    if tp_cat in ("2", "3") and not re.fullmatch(r"1\.\d\.\d{19}", cat.get("nr_rec_cat_orig") or ""):
        p.append("Recibo da CAT de origem (reabertura/óbito)")
    _checa([f"CAT sem {x}" if not x.startswith(("Funcionário", "Recibo")) else x for x in p])

    obito = tp_cat == "3" or str(cat.get("houve_obito") or "0") in ("1", "S")
    afast = str(cat.get("houve_afastamento") or "0") in ("1", "S")
    root, evt, ev_id = _raiz("S-2210", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    _ide_vinculo_sst(evt, emp)
    c = _grupo(evt, "cat")
    _el(c, "dtAcid", dt, True)
    _el(c, "tpAcid", tp_acid, True)
    if tp_acid in ("1", "3"):
        _el(c, "hrAcid", _hora(cat.get("hora_acidente")), True)
        _el(c, "hrsTrabAntesAcid", _hora(cat.get("hrs_trab_antes")) or "0000", True)
    _el(c, "tpCat", tp_cat, True)
    _el(c, "indCatObito", "S" if obito else "N", True)
    if obito and data_iso(cat.get("dt_obito")):
        _el(c, "dtObito", data_iso(cat.get("dt_obito")))
    _el(c, "indComunPolicia", cat.get("ind_comun_policia") or "N", True)
    _el(c, "codSitGeradora", digitos(cat.get("cod_sit_geradora")), True)
    _el(c, "iniciatCAT", str(cat.get("iniciat_cat") or "1"), True)
    _el(c, "obsCAT", txt(cat.get("descricao"))[:999] or None)
    _el(c, "ultDiaTrab", data_iso(cat.get("ult_dia_trab")) or dt, True)
    _el(c, "houveAfast", "S" if afast else "N", True)
    loc = _grupo(c, "localAcidente")
    _el(loc, "tpLocal", tp_local, True)
    _el(loc, "dscLocal", txt(cat.get("local_acidente"))[:255] or None)
    if tp_local == "1" and not txt(cat.get("local_logradouro")):
        _el(loc, "dscLograd", txt(company.get("logradouro"))[:100] or "Estabelecimento do empregador", True)
        _el(loc, "nrLograd", txt(company.get("numero"))[:10] or "S/N", True)
        _el(loc, "bairro", txt(company.get("bairro"))[:90] or None)
        _el(loc, "cep", digitos(company.get("cep")) or None)
        _el(loc, "codMunic", digitos(company.get("codigo_ibge_municipio")) or None)
        _el(loc, "uf", (company.get("uf") or "").upper() or None)
    else:
        _el(loc, "dscLograd", txt(cat.get("local_logradouro"))[:100], True)
        _el(loc, "nrLograd", txt(cat.get("local_numero"))[:10] or "S/N", True)
        _el(loc, "bairro", txt(cat.get("local_bairro"))[:90] or None)
        if tp_local != "2":
            _el(loc, "cep", digitos(cat.get("local_cep")) or None)
            _el(loc, "codMunic", digitos(cat.get("local_cod_municipio")) or None)
            _el(loc, "uf", (cat.get("local_uf") or "").upper() or None)
    if tp_local in ("1", "3"):
        il = _grupo(loc, "ideLocalAcid")
        _el(il, "tpInsc", "1", True)
        _el(il, "nrInsc", digitos(company.get("cnpj")), True)
    pa = _grupo(c, "parteAtingida")
    _el(pa, "codParteAting", digitos(cat.get("cod_parte_ating")), True)
    _el(pa, "lateralidade", str(cat.get("lateralidade") or "0"), True)
    ag = _grupo(c, "agenteCausador")
    _el(ag, "codAgntCausador", digitos(cat.get("cod_agnt_causador")), True)
    at = _grupo(c, "atestado")
    _el(at, "dtAtendimento", data_iso(cat.get("dt_atendimento")), True)
    _el(at, "hrAtendimento", _hora(cat.get("hr_atendimento")), True)
    _el(at, "indInternacao", cat.get("ind_internacao") or "N", True)
    _el(at, "durTrat", str(int(cat.get("dur_trat") or cat.get("dias_afastamento") or 0)), True)
    _el(at, "indAfast", "N" if obito else ("S" if afast else "N"), True)
    _el(at, "dscLesao", digitos(cat.get("cod_natureza_lesao")), True)
    _el(at, "diagProvavel", txt(cat.get("diag_provavel"))[:100] or None)
    _el(at, "codCID", txt(cat.get("cod_cid")).replace(".", "").upper()[:4], True)
    em = _grupo(at, "emitente")
    _el(em, "nmEmit", txt(cat.get("nm_emit"))[:70], True)
    ide_oc = str(cat.get("ide_oc") or "1")
    _el(em, "ideOC", ide_oc, True)
    _el(em, "nrOC", txt(cat.get("nr_oc"))[:14], True)
    if ide_oc in ("1", "2"):
        _el(em, "ufOC", (cat.get("uf_oc") or company.get("uf") or "").upper(), True)
    if tp_cat in ("2", "3"):
        co_ = _grupo(c, "catOrigem")
        _el(co_, "nrRecCatOrig", cat.get("nr_rec_cat_orig"), True)
    return ev_id, _fim(root)


TP_EXAME = {"admissional": "0", "periodico": "1", "periódico": "1", "retorno": "2", "retorno_trabalho": "2",
            "mudanca_funcao": "3", "mudanca": "3", "mudança": "3", "monitoracao": "4", "demissional": "9"}


def s2220(company, cfg, amb: int, emp: Dict[str, Any], aso: Dict[str, Any], resp: Optional[Dict[str, Any]] = None,
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """aso: {tipo, data_exame, resultado, medico, crm_medico, crm_uf, procedimentos: [{cod, dt, ord, obs}]}"""
    import json as _json
    p = []
    if len(digitos(emp.get("cpf"))) != 11:
        p.append("Funcionário sem CPF")
    dt = data_iso(aso.get("data_exame"))
    if not dt:
        p.append("ASO sem data")
    tipo = TP_EXAME.get((aso.get("tipo") or "").lower())
    if tipo is None:
        p.append("Tipo do exame sem correspondência no eSocial (admissional, periódico, retorno, mudança, demissional)")
    if not txt(aso.get("medico")):
        p.append("ASO sem nome do médico emitente")
    procs = aso.get("procedimentos")
    if isinstance(procs, str):
        try:
            procs = _json.loads(procs) if procs else []
        except ValueError:
            procs = []
    procs = procs or [{"cod": "0295", "dt": dt}]
    _checa(p)
    root, evt, ev_id = _raiz("S-2220", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    _ide_vinculo_sst(evt, emp)
    ex = _grupo(evt, "exMedOcup")
    _el(ex, "tpExameOcup", tipo, True)
    a = _grupo(ex, "aso")
    _el(a, "dtAso", dt, True)
    res = (aso.get("resultado") or "").lower()
    _el(a, "resAso", "1" if res.startswith("apto") else ("2" if res.startswith("inapto") else None))
    for pr in procs[:99]:
        e = _grupo(a, "exame")
        _el(e, "dtExm", data_iso(pr.get("dt")) or dt, True)
        cod = digitos(pr.get("cod")).zfill(4)
        _el(e, "procRealizado", cod, True)
        _el(e, "obsProc", txt(pr.get("obs"))[:999] or None)
        if cod == "0281":
            _el(e, "ordExame", str(pr.get("ord") or "1"), True)
    m = _grupo(a, "medico")
    _el(m, "nmMed", txt(aso.get("medico"))[:70], True)
    _el(m, "nrCRM", txt(aso.get("crm_medico"))[:10] or None)
    _el(m, "ufCRM", (aso.get("crm_uf") or "").upper() or None)
    if resp and txt(resp.get("nome")) and txt(resp.get("crm")) and resp.get("uf"):
        r = _grupo(ex, "respMonit")
        _el(r, "cpfResp", digitos(resp.get("cpf")) or None)
        _el(r, "nmResp", txt(resp.get("nome"))[:70], True)
        _el(r, "nrCRM", txt(resp.get("crm"))[:10], True)
        _el(r, "ufCRM", resp.get("uf").upper(), True)
    return ev_id, _fim(root)


def s2240(company, cfg, amb: int, emp: Dict[str, Any], expo: Dict[str, Any],
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """expo: {dt_inicio, local_amb, dsc_setor, dsc_ativ, agentes: [{cod, dsc, tp_aval, int_conc, lim_tol, un_med,
    tec_medicao, utiliz_epc, efic_epc, utiliz_epi, efic_epi, ca_epi}], resp_cpf, resp_ide_oc, resp_dsc_oc,
    resp_nr_oc, resp_uf_oc, observacao}"""
    import json as _json
    agentes = expo.get("agentes")
    if isinstance(agentes, str):
        try:
            agentes = _json.loads(agentes) if agentes else []
        except ValueError:
            agentes = []
    agentes = agentes or [{"cod": "09.01.001"}]
    so_ausencia = all(a.get("cod") == "09.01.001" for a in agentes)
    p = []
    if len(digitos(emp.get("cpf"))) != 11:
        p.append("Funcionário sem CPF")
    if not data_iso(expo.get("dt_inicio")):
        p.append("Data de início da condição")
    if not txt(expo.get("dsc_setor")):
        p.append("Setor do ambiente de trabalho")
    if not txt(expo.get("dsc_ativ")):
        p.append("Descrição das atividades")
    if len(digitos(expo.get("resp_cpf"))) != 11:
        p.append("CPF do responsável pelos registros ambientais")
    if not so_ausencia and not (expo.get("resp_ide_oc") and txt(expo.get("resp_nr_oc"))):
        p.append("Conselho e registro do responsável técnico (obrigatório com agente nocivo)")
    for a in agentes:
        if not re.fullmatch(r"\d{2}\.\d{2}\.\d{3}", a.get("cod") or ""):
            p.append(f"Código de agente nocivo inválido: {a.get('cod')}")
    _checa(p)
    root, evt, ev_id = _raiz("S-2240", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    _ide_vinculo_sst(evt, emp)
    info = _grupo(evt, "infoExpRisco")
    _el(info, "dtIniCondicao", data_iso(expo.get("dt_inicio")), True)
    amb_ = _grupo(info, "infoAmb")
    _el(amb_, "localAmb", str(expo.get("local_amb") or "1"), True)
    _el(amb_, "dscSetor", txt(expo.get("dsc_setor"))[:100], True)
    _el(amb_, "tpInsc", "1", True)
    _el(amb_, "nrInsc", digitos(company.get("cnpj")), True)
    at = _grupo(info, "infoAtiv")
    _el(at, "dscAtivDes", txt(expo.get("dsc_ativ"))[:999], True)
    for a in agentes[:999]:
        g = _grupo(info, "agNoc")
        _el(g, "codAgNoc", a["cod"], True)
        _el(g, "dscAgNoc", txt(a.get("dsc"))[:100] or None)
        if a["cod"] != "09.01.001":
            _el(g, "tpAval", str(a.get("tp_aval") or "") or None)
            if str(a.get("tp_aval") or "") == "1":
                _el(g, "intConc", a.get("int_conc"))
                _el(g, "limTol", a.get("lim_tol"))
                _el(g, "unMed", a.get("un_med"))
                _el(g, "tecMedicao", txt(a.get("tec_medicao"))[:40] or None)
            ee = _grupo(g, "epcEpi")
            u_epc, u_epi = str(a.get("utiliz_epc") or "0"), str(a.get("utiliz_epi") or "0")
            _el(ee, "utilizEPC", u_epc, True)
            if u_epc == "2":
                _el(ee, "eficEpc", a.get("efic_epc") or "S", True)
            _el(ee, "utilizEPI", u_epi, True)
            if u_epi == "2":
                _el(ee, "eficEpi", a.get("efic_epi") or "S", True)
                epi = _grupo(ee, "epi")
                _el(epi, "docAval", txt(a.get("ca_epi"))[:255] or "Certificado de Aprovação do EPI", True)
                comp = _grupo(ee, "epiCompl")
                for campo in ("medProtecao", "condFuncto", "usoInint", "przValid", "periodicTroca", "higienizacao"):
                    _el(comp, campo, "S", True)
    r = _grupo(info, "respReg")
    _el(r, "cpfResp", digitos(expo.get("resp_cpf")), True)
    if expo.get("resp_ide_oc"):
        _el(r, "ideOC", str(expo.get("resp_ide_oc")))
        if str(expo.get("resp_ide_oc")) == "9":
            _el(r, "dscOC", txt(expo.get("resp_dsc_oc"))[:20] or "Outros", True)
        _el(r, "nrOC", txt(expo.get("resp_nr_oc"))[:14] or None)
        _el(r, "ufOC", (expo.get("resp_uf_oc") or "").upper() or None)
    if txt(expo.get("observacao")):
        o = _grupo(info, "obs")
        _el(o, "obsCompl", txt(expo.get("observacao"))[:999], True)
    return ev_id, _fim(root)


# ─── S-2298 Reintegração ──────────────────────────────────────────────────────

def s2298(company, cfg, amb: int, emp: Dict[str, Any], rein: Dict[str, Any],
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    p = []
    if len(digitos(emp.get("cpf"))) != 11:
        p.append("Funcionário sem CPF")
    if not txt(emp.get("matricula")):
        p.append("Funcionário sem matrícula")
    retorno = data_iso(rein.get("data_reintegracao"))
    if not retorno:
        p.append("Data do efetivo retorno")
    nr = digitos(rein.get("nr_processo"))
    tp = str(rein.get("tp_reint") or ("1" if nr else "9"))
    if tp == "1" and len(nr) != 20:
        p.append("Número do processo judicial com 20 dígitos (reintegração por decisão judicial)")
    _checa(p)
    root, evt, ev_id = _raiz("S-2298", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    ide = _grupo(evt, "ideVinculo")
    _el(ide, "cpfTrab", digitos(emp.get("cpf")), True)
    _el(ide, "matricula", txt(emp.get("matricula"))[:30], True)
    info = _grupo(evt, "infoReintegr")
    _el(info, "tpReint", tp, True)
    if tp == "1":
        _el(info, "nrProcJud", nr, True)
    _el(info, "dtEfetRetorno", retorno, True)
    _el(info, "dtEfeito", data_iso(rein.get("dt_efeito")) or retorno, True)
    return ev_id, _fim(root)


# ─── S-2300 / S-2399 Trabalhador sem vínculo (estagiário) ─────────────────────

def matricula_estagiario(estag: Dict[str, Any]) -> str:
    return txt(estag.get("matricula")) or f"EST{int(estag.get('id') or 0):05d}"


def s2300(company, cfg, amb: int, estag: Dict[str, Any], retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    p = []
    if len(digitos(estag.get("cpf"))) != 11:
        p.append("CPF")
    if not txt(estag.get("nome")):
        p.append("nome")
    if (estag.get("sexo") or "") not in ("M", "F"):
        p.append("sexo")
    dt_ini = data_iso(estag.get("data_inicio"))
    if dt_ini >= "2024-04-22" and str(estag.get("raca_cor") or "") in ("", "6"):
        p.append("raça/cor")
    if not data_iso(estag.get("data_nascimento")):
        p.append("data de nascimento")
    if not dt_ini:
        p.append("data de início do estágio")
    if not data_iso(estag.get("data_fim")):
        p.append("data prevista de término")
    if not txt(estag.get("logradouro")) or len(digitos(estag.get("cep"))) != 8 or len(digitos(estag.get("cod_municipio"))) != 7 or not estag.get("uf"):
        p.append("endereço completo (logradouro, CEP, código IBGE do município e UF)")
    if str(estag.get("nivel_esocial") or "") not in ("1", "2", "3", "4", "8", "9"):
        p.append("nível do estágio (fundamental, médio, superior...)")
    if len(digitos(estag.get("cnpj_inst_ensino"))) != 14:
        p.append("CNPJ da instituição de ensino")
    _checa([f"Estagiário sem {x}" for x in p])
    root, evt, ev_id = _raiz("S-2300", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    t = _grupo(evt, "trabalhador")
    _el(t, "cpfTrab", digitos(estag.get("cpf")), True)
    _el(t, "nmTrab", txt(estag.get("nome"))[:70], True)
    _el(t, "sexo", estag.get("sexo"), True)
    _el(t, "racaCor", str(estag.get("raca_cor") or "6"), True)
    _el(t, "grauInstr", str(estag.get("grau_instrucao") or "06").zfill(2), True)
    n = _grupo(t, "nascimento")
    _el(n, "dtNascto", data_iso(estag.get("data_nascimento")), True)
    _el(n, "paisNascto", "105", True)
    _el(n, "paisNac", "105", True)
    _endereco(t, estag)
    _contato(t, {"celular": estag.get("telefone"), "email": estag.get("email")})
    i = _grupo(evt, "infoTSVInicio")
    _el(i, "cadIni", "N", True)
    _el(i, "matricula", matricula_estagiario(estag)[:30], True)
    _el(i, "codCateg", "901", True)
    _el(i, "dtInicio", dt_ini, True)
    ic = _grupo(i, "infoComplementares")
    if txt(estag.get("curso")):
        cf = _grupo(ic, "cargoFuncao")
        _el(cf, "nmCargo", f"Estagiário - {txt(estag.get('curso'))}"[:100], True)
    if float(estag.get("bolsa_auxilio") or 0) > 0:
        r = _grupo(ic, "remuneracao")
        _el(r, "vrSalFx", valor(estag.get("bolsa_auxilio")), True)
        _el(r, "undSalFixo", "5", True)
    e = _grupo(ic, "infoEstagiario")
    _el(e, "natEstagio", estag.get("nat_estagio") or "N", True)
    _el(e, "nivEstagio", str(estag.get("nivel_esocial")), True)
    _el(e, "areaAtuacao", txt(estag.get("area_atuacao") or estag.get("curso"))[:100] or None)
    _el(e, "nrApol", txt(estag.get("nr_apolice"))[:30] or None)
    _el(e, "dtPrevTerm", data_iso(estag.get("data_fim")), True)
    ie = _grupo(e, "instEnsino")
    _el(ie, "cnpjInstEnsino", digitos(estag.get("cnpj_inst_ensino")), True)
    if len(digitos(estag.get("cnpj_agente_integracao"))) == 14:
        ag = _grupo(e, "ageIntegracao")
        _el(ag, "cnpjAgntInteg", digitos(estag.get("cnpj_agente_integracao")), True)
    if len(digitos(estag.get("cpf_supervisor"))) == 11:
        sv = _grupo(e, "supervisorEstagio")
        _el(sv, "cpfSupervisor", digitos(estag.get("cpf_supervisor")), True)
    lg = _grupo(ic, "localTrabGeral")
    _el(lg, "tpInsc", "1", True)
    _el(lg, "nrInsc", digitos(company.get("cnpj")), True)
    return ev_id, _fim(root)


def s2399(company, cfg, amb: int, estag: Dict[str, Any], dt_term: str,
          retif: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    p = []
    if len(digitos(estag.get("cpf"))) != 11:
        p.append("Estagiário sem CPF")
    if not data_iso(dt_term):
        p.append("Data de término do estágio")
    _checa(p)
    root, evt, ev_id = _raiz("S-2399", company)
    _ide_evento(evt, amb, retif)
    _ide_empregador(evt, company)
    ide = _grupo(evt, "ideTrabSemVinculo")
    _el(ide, "cpfTrab", digitos(estag.get("cpf")), True)
    _el(ide, "matricula", matricula_estagiario(estag)[:30], True)
    info = _grupo(evt, "infoTSVTermino")
    _el(info, "dtTerm", data_iso(dt_term), True)
    return ev_id, _fim(root)
