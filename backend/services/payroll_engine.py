"""
Motor de folha por rubricas.

Cada funcionário vira uma lista de linhas (rubrica, referência, valor). As bases de
INSS, IRRF e FGTS são a soma das rubricas marcadas com a respectiva incidência, e não
mais o salário cadastrado. O motor é dividido em duas partes:

  * calculate_employee()  — cálculo puro, sem banco (fácil de testar);
  * build_inputs()        — lê ponto, afastamentos, benefícios, adiantamentos, pensão,
                            contribuição assistencial e lançamentos de rubrica do banco.
"""
import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from . import dp_parametros

try:
    from .formula_engine import FormulaError, evaluate, validate
    from .payroll_tables import TaxTables, load_tables
    from . import escalas as _escalas
    from . import cct_regras as _cct
    from . import beneficios as _benef
except ImportError:  # execução com backend/ como raiz
    from services.formula_engine import FormulaError, evaluate, validate
    from services.payroll_tables import TaxTables, load_tables
    from services import escalas as _escalas
    from services import cct_regras as _cct
    from services import beneficios as _benef


# ── Rubricas de sistema ──────────────────────────────────────────────────────
# chave: (codigo, nome, tipo, incide_inss, incide_irrf, incide_fgts, natureza eSocial)
# Em desconto, incidência = 1 significa que o valor REDUZ a base (ex.: faltas).
SYSTEM_RUBRICS: Dict[str, Tuple[str, str, str, int, int, int, str]] = {
    "SALARIO":       ("0001", "Salário Base", "provento", 1, 1, 1, "1000"),
    "HE50":          ("0002", "Hora Extra 50%", "provento", 1, 1, 1, "1003"),
    "HE100":         ("0003", "Hora Extra 100%", "provento", 1, 1, 1, "1003"),
    "NOTURNO":       ("0004", "Adicional Noturno", "provento", 1, 1, 1, "1205"),
    "INSALUBRIDADE": ("0005", "Adicional de Insalubridade", "provento", 1, 1, 1, "1202"),
    "PERICULOSIDADE": ("0006", "Adicional de Periculosidade", "provento", 1, 1, 1, "1203"),
    "DSR_HE":        ("0011", "DSR sobre Horas Extras", "provento", 1, 1, 1, "1002"),
    "SAL_FAMILIA":   ("0012", "Salário-Família", "provento", 0, 0, 0, "1409"),
    "PROLABORE":     ("0013", "Pró-labore", "provento", 1, 1, 0, "3501"),
    # Lei 8.213/91 art. 72 §1º: pago pela empresa e compensado nas contribuições; integra
    # o salário de contribuição (Lei 8.212/91 art. 28 §2º), o FGTS e o IRRF.
    "SAL_MATERNIDADE": ("0014", "Salário-Maternidade", "provento", 1, 1, 1, "4050"),
    # Convenção coletiva e categorias (bloco 3)
    "ATS":           ("0015", "Adicional por Tempo de Serviço", "provento", 1, 1, 1, "1206"),
    "COMISSAO":      ("0016", "Comissões", "provento", 1, 1, 1, "1207"),
    "DSR_COMISSAO":  ("0017", "DSR sobre Comissões", "provento", 1, 1, 1, "1002"),
    "GARANTIA_MIN":  ("0018", "Complemento de Garantia Mínima", "provento", 1, 1, 1, "1099"),
    "DSR_PROFESSOR": ("0019", "DSR do Professor (1/6)", "provento", 1, 1, 1, "1002"),
    # Súmula 340 / OJ 397 TST: sobre as comissões, a hora extra paga só o adicional
    "HE50_COMISSAO":  ("0023", "Adicional de HE 50% s/ Comissões", "provento", 1, 1, 1, "1003"),
    "HE100_COMISSAO": ("0024", "Adicional de HE 100% s/ Comissões", "provento", 1, 1, 1, "1003"),
    "NOTURNO_COMISSAO": ("0025", "Adicional Noturno s/ Comissões", "provento", 1, 1, 1, "1205"),
    "INSS":          ("0100", "INSS", "desconto", 0, 0, 0, "9201"),
    "IRRF":          ("0101", "IRRF", "desconto", 0, 0, 0, "9203"),
    "VT":            ("0102", "Vale-Transporte", "desconto", 0, 0, 0, "9216"),
    # 9219 é plano de saúde; a 9220 (alimentação) foi extinta no S-1.0 → outros descontos
    "VA":            ("0103", "Vale-Alimentação/Refeição", "desconto", 0, 0, 0, "9299"),
    "PENSAO":        ("0104", "Pensão Alimentícia", "desconto", 0, 0, 0, "9213"),
    "ADIANTAMENTO":  ("0105", "Adiantamento de Salário", "desconto", 0, 0, 0, "9200"),
    "FALTAS":        ("0106", "Faltas Injustificadas", "desconto", 1, 1, 1, "9207"),
    "DSR_FALTAS":    ("0107", "DSR Perdido por Faltas", "desconto", 1, 1, 1, "9207"),
    "ATRASOS":       ("0108", "Atrasos e Saídas Antecipadas", "desconto", 1, 1, 1, "9209"),
    "CONTRIB_ASSIST": ("0109", "Contribuição Assistencial", "desconto", 0, 0, 0, "9231"),
    "BENEFICIO":     ("0110", "Benefícios (coparticipação)", "desconto", 0, 0, 0, "9299"),
    # Bloco 4 — benefícios (Tabela 03 do eSocial)
    "PLANO_SAUDE":   ("0111", "Plano de Saúde", "desconto", 0, 0, 0, "9219"),
    "PLANO_COPART":  ("0112", "Coparticipação do Plano de Saúde", "desconto", 0, 0, 0, "9219"),
    "CONSIGNADO":    ("0113", "Empréstimo Consignado (Crédito do Trabalhador)", "desconto", 0, 0, 0, "9253"),
    "CONSIGNADO_CONV": ("0114", "Empréstimo Consignado (Convênio)", "desconto", 0, 0, 0, "9254"),
    # Férias, 13º e rescisão (usadas por payroll_special)
    "FERIAS":        ("0008", "Férias", "provento", 1, 1, 1, "1020"),
    "FERIAS_TERCO":  ("0009", "1/3 Constitucional de Férias", "provento", 1, 1, 1, "1020"),
    "DECIMO":        ("0010", "13º Salário", "provento", 1, 1, 1, "5001"),
    "DECIMO_ADIANT": ("0020", "13º Salário — 1ª Parcela", "provento", 0, 0, 1, "5001"),
    "MEDIA_13":      ("0021", "Média de Variáveis s/ 13º", "provento", 1, 1, 1, "5001"),
    "MEDIA_FERIAS":  ("0022", "Média de Variáveis s/ Férias", "provento", 1, 1, 1, "1020"),
    "ABONO_PEC":     ("0030", "Abono Pecuniário de Férias", "provento", 0, 0, 0, "1023"),
    "ABONO_TERCO":   ("0031", "1/3 s/ Abono Pecuniário", "provento", 0, 0, 0, "1023"),
    "FERIAS_DOBRO":  ("0032", "Férias em Dobro", "provento", 0, 0, 0, "1024"),
    "SALDO_SALARIO": ("0040", "Saldo de Salário", "provento", 1, 1, 1, "1000"),
    "AVISO_IND":     ("0041", "Aviso Prévio Indenizado", "provento", 0, 0, 1, "6003"),
    "DECIMO_PROP":   ("0042", "13º Salário Proporcional", "provento", 1, 1, 1, "5001"),
    "DECIMO_IND":    ("0043", "13º s/ Aviso Prévio Indenizado", "provento", 0, 1, 1, "6002"),
    "FERIAS_VENC":   ("0044", "Férias Vencidas Indenizadas", "provento", 0, 0, 0, "6006"),
    "FERIAS_PROP":   ("0045", "Férias Proporcionais Indenizadas", "provento", 0, 0, 0, "6006"),
    "FERIAS_RESC_TERCO": ("0046", "1/3 s/ Férias na Rescisão", "provento", 0, 0, 0, "6006"),
    "FERIAS_RESC_DOBRO": ("0047", "Dobra de Férias Vencidas", "provento", 0, 0, 0, "6007"),
    "MULTA_477":     ("0048", "Multa do Art. 477 § 8º da CLT", "provento", 0, 0, 0, "6106"),
    "INDENIZ_DATA_BASE": ("0049", "Indenização Adicional (Lei 7.238/84 art. 9º)", "provento", 0, 0, 0, "6102"),
    "DECIMO_ADIANT_DESC": ("0120", "Adiantamento de 13º (1ª parcela)", "desconto", 0, 0, 1, "9214"),
    "INSS_13":       ("0121", "INSS s/ 13º Salário", "desconto", 0, 0, 0, "9201"),
    "IRRF_13":       ("0122", "IRRF s/ 13º Salário", "desconto", 0, 0, 0, "9203"),
    "AVISO_DESC":    ("0130", "Aviso Prévio não Cumprido", "desconto", 0, 0, 0, "9208"),
    "MULTA_FGTS":    ("0210", "Multa Rescisória do FGTS", "informativo", 0, 0, 0, "9000"),
    "FGTS_INFO":     ("0200", "FGTS do mês", "informativo", 0, 0, 0, "9000"),
    "BASE_INSS":     ("0201", "Base de Cálculo INSS", "informativo", 0, 0, 0, "9100"),
    "BASE_IRRF":     ("0202", "Base de Cálculo IRRF", "informativo", 0, 0, 0, "9110"),
    "BASE_FGTS":     ("0203", "Base de Cálculo FGTS", "informativo", 0, 0, 0, "9120"),
}
_SYSTEM_CODES = {v[0]: k for k, v in SYSTEM_RUBRICS.items()}
# Rubricas de sistema que aceitam lançamento manual de QUANTIDADE (horas).
_HOUR_CODES = {"0002": "he50", "0003": "he100", "0004": "horas_noturnas"}
# Rubricas de sistema que aceitam lançamento manual de VALOR (comissões do mês).
_VALUE_CODES = {"0016": "comissoes"}

INSALUBRIDADE_GRAUS = {"minimo": 0.10, "medio": 0.20, "maximo": 0.40}
PERICULOSIDADE_PCT = 0.30
IRRF_MINIMO_RETENCAO = 10.00

FORMULA_VARIABLES: Dict[str, str] = {
    "salario_base": "Salário contratual mensal",
    "salario_dia": "Salário base ÷ 30",
    "salario_hora": "Salário base ÷ horas mensais",
    "salario_minimo": "Salário mínimo vigente na competência",
    "horas_mes": "Horas mensais do contrato (220 para 44h semanais)",
    "dias_trabalhados": "Dias pagos no mês (mês comercial de 30 dias)",
    "dias_uteis": "Dias úteis do mês (segunda a sábado, sem feriados)",
    "dias_dsr": "Domingos e feriados do mês",
    "faltas_dias": "Faltas injustificadas no mês",
    "horas_faltantes": "Horas de atraso/saída antecipada",
    "horas_extras_50": "Horas extras a 50%",
    "horas_extras_100": "Horas extras a 100%",
    "horas_noturnas": "Horas noturnas",
    "dependentes": "Dependentes para IRRF",
    "quantidade": "Quantidade informada no lançamento",
    "valor": "Valor informado no lançamento",
    "total_proventos": "Soma dos proventos calculados até esta rubrica",
}


def r2(x: float) -> float:
    """Arredonda para centavos (meio para cima, como nas folhas)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validate_formula(expr: str) -> List[str]:
    return validate(expr, list(FORMULA_VARIABLES))


# ── Entradas ─────────────────────────────────────────────────────────────────
@dataclass
class EmployeeInput:
    employee_id: int
    nome: str
    salario: float
    dependentes: int = 0
    is_prolabore: bool = False
    horas_mes: float = 220.0
    dias_direito: int = 30          # 30, ou proporcional na admissão
    base_dias: int = 30             # 30 (mês comercial) ou dias corridos do mês (parâmetro da empresa)
    dias_afastado_inss: int = 0     # dias pagos pelo INSS (não entram na folha)
    dias_ferias: int = 0            # dias de férias no mês (pagos no recibo de férias)
    faltas_dias: float = 0.0
    dsr_perdidos: float = 0.0
    horas_faltantes: float = 0.0
    he50: float = 0.0
    he100: float = 0.0
    horas_noturnas: float = 0.0
    dias_uteis: int = 25
    dias_dsr: int = 5
    insalubridade_grau: str = ""
    periculosidade: bool = False
    filhos_sal_familia: int = 0
    vt_mensal: float = 0.0
    beneficios: List[Dict[str, Any]] = field(default_factory=list)   # {nome, tipo, desconto}
    planos_saude: List[Dict[str, Any]] = field(default_factory=list)  # {nome, valor (parte do empregado), ref}
    copart: List[Dict[str, Any]] = field(default_factory=list)        # {nome, valor}
    consignados: List[Dict[str, Any]] = field(default_factory=list)   # {nome, valor, origem}
    consignado_pct: float = 35.0
    avisos_extra: List[str] = field(default_factory=list)
    adiantamentos: float = 0.0
    pensoes: List[Dict[str, Any]] = field(default_factory=list)      # {modalidade, percentual, valor_fixo, base_calculo, beneficiario}
    cct_percentual: float = 0.0
    lancamentos: List[Dict[str, Any]] = field(default_factory=list)  # {codigo, quantidade, valor}
    base_inss_ferias: float = 0.0
    inss_ferias: float = 0.0
    base_inss_outros_vinculos: float = 0.0
    inss_outros_vinculos: float = 0.0
    dias_maternidade: int = 0       # dias de salário-maternidade (compensável) no mês
    jornada_parcial: bool = False   # CLT art. 58-A
    horas_semana: float = 44.0
    # Convenção coletiva e categoria (bloco 3)
    he50_pct: float = 50.0
    he100_pct: float = 100.0
    noturno_pct: float = 20.0
    ats_valor: float = 0.0          # adicional por tempo de serviço, valor mensal cheio
    ats_ref: str = ""
    piso: float = 0.0               # piso da convenção (mensal, para 44h)
    categoria: str = "mensalista"   # mensalista, horista, diarista, semanal, quinzenal, tarefa, variavel, professor
    salario_ref: str = ""           # como o salário mensal foi obtido (horista, professor...)
    comissoes: float = 0.0


# ── Cálculos de imposto ──────────────────────────────────────────────────────
def calc_inss(base: float, t: TaxTables, prolabore: bool = False) -> float:
    if base <= 0:
        return 0.0
    base = min(base, t.inss_teto)
    if prolabore:
        return r2(base * 0.11)
    total, anterior = 0.0, 0.0
    for limite, aliq in t.inss:
        if base <= anterior:
            break
        total += (min(base, limite) - anterior) * aliq
        anterior = limite
    return r2(total)


def calc_irrf(rendimento: float, inss: float, dependentes: int, pensao: float, t: TaxTables) -> Dict[str, float]:
    """IRRF mensal. Usa o desconto simplificado quando for mais vantajoso que as deduções legais."""
    if rendimento <= 0:
        return {"irrf": 0.0, "base": 0.0, "deducao": 0.0, "simplificado": 0.0, "reducao": 0.0}
    legal = inss + dependentes * t.irrf_dependente + pensao
    usa_simplificado = t.irrf_simplificado > legal
    deducao = t.irrf_simplificado if usa_simplificado else legal
    base = max(0.0, rendimento - deducao)
    imposto = 0.0
    for limite, aliq, parcela in t.irrf:
        if base <= limite:
            imposto = max(0.0, base * aliq - parcela)
            break
    reducao = 0.0
    if t.irrf_reducao and imposto > 0:
        lim_isento, lim_reducao, const, fator, maximo = t.irrf_reducao
        if rendimento <= lim_isento:
            reducao = min(imposto, maximo)
        elif rendimento <= lim_reducao:
            reducao = min(imposto, max(0.0, const - fator * rendimento))
    imposto = r2(imposto - reducao)
    if imposto <= IRRF_MINIMO_RETENCAO:
        imposto = 0.0
    return {"irrf": imposto, "base": r2(base), "deducao": r2(deducao),
            "simplificado": 1.0 if usa_simplificado else 0.0, "reducao": r2(reducao)}


def rubric_meta(rubrics: Optional[Dict[str, Dict[str, Any]]], codigo: str) -> Dict[str, Any]:
    """Nome, tipo e incidências de uma rubrica: a da empresa, senão a de sistema."""
    r = (rubrics or {}).get(codigo)
    if r:
        return r
    key = _SYSTEM_CODES.get(codigo)
    if key:
        c, nome, tipo, i1, i2, i3, _ = SYSTEM_RUBRICS[key]
        return {"codigo": c, "nome": nome, "tipo": tipo,
                "incide_inss": i1, "incide_irrf": i2, "incide_fgts": i3}
    return {"codigo": codigo, "nome": f"Rubrica {codigo}", "tipo": "provento",
            "incide_inss": 0, "incide_irrf": 0, "incide_fgts": 0}


def adicionais_fixos(salario: float, insalubridade_grau: str, periculosidade: bool,
                     tables: TaxTables) -> Tuple[float, float, float, bool]:
    """(insalubridade, periculosidade, grau, houve_conflito) em valor mensal cheio.
    Não acumulam (CLT art. 193 §2º): fica o de maior valor."""
    grau = INSALUBRIDADE_GRAUS.get((insalubridade_grau or "").lower(), 0.0)
    insal = tables.salario_minimo * grau
    peric = salario * PERICULOSIDADE_PCT if periculosidade else 0.0
    conflito = bool(insal and peric)
    if conflito:
        if peric >= insal:
            insal = 0.0
        else:
            peric = 0.0
    return insal, peric, grau, conflito


def resolve_irrf_pensao(base_irrf: float, inss: float, dependentes: int, pensoes: List[Dict[str, Any]],
                        bruto: float, tables: TaxTables) -> Tuple[Dict[str, float], List[float]]:
    """IRRF e pensões alimentícias. Pensão sobre o líquido depende do IRRF, que depende
    da pensão (ela é dedutível): resolve por iteração."""
    def pensao_total(irrf_atual: float) -> List[float]:
        vals = []
        for p in pensoes:
            if (p.get("modalidade") or "percentual") != "percentual":
                vals.append(float(p.get("valor_fixo") or 0))
                continue
            bc = (p.get("base_calculo") or "liquido").lower()
            if bc == "liquido":
                base_p = max(0.0, base_irrf - inss - irrf_atual)
            elif bc == "salario_minimo":
                base_p = tables.salario_minimo
            else:
                base_p = bruto
            vals.append(base_p * float(p.get("percentual") or 0) / 100.0)
        return vals

    ir = calc_irrf(base_irrf, inss, dependentes, 0.0, tables)
    pens = pensao_total(ir["irrf"])
    for _ in range(40):
        novo = calc_irrf(base_irrf, inss, dependentes, sum(pens), tables)
        novas = pensao_total(novo["irrf"])
        convergiu = abs(novo["irrf"] - ir["irrf"]) < 0.005 and abs(sum(novas) - sum(pens)) < 0.005
        ir, pens = novo, novas
        if convergiu:
            break
    return ir, pens


# ── Cálculo de um funcionário ────────────────────────────────────────────────
def calculate_employee(
    inp: EmployeeInput,
    tables: TaxTables,
    rubrics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Calcula a folha de um funcionário.
    `rubrics`: rubricas da empresa por código ({codigo: {nome, tipo, incide_*, formula, aplica_todos, ativo}}).
    """
    rubrics = rubrics or {}
    lines: List[Dict[str, Any]] = []
    avisos: List[str] = list(inp.avisos_extra)

    def meta(codigo: str) -> Dict[str, Any]:
        return rubric_meta(rubrics, codigo)

    def add(codigo: str, valor: float, referencia: str = "", origem: str = "automatico",
            nome: Optional[str] = None) -> float:
        valor = r2(valor)
        if valor <= 0:
            return 0.0
        m = meta(codigo)
        lines.append({
            "codigo": codigo, "nome": nome or m["nome"], "tipo": m["tipo"],
            "referencia": referencia, "valor": valor, "origem": origem,
            "incide_inss": int(m.get("incide_inss") or 0),
            "incide_irrf": int(m.get("incide_irrf") or 0),
            "incide_fgts": int(m.get("incide_fgts") or 0),
        })
        return valor

    def sys(key: str, valor: float, referencia: str = "", nome: Optional[str] = None) -> float:
        return add(SYSTEM_RUBRICS[key][0], valor, referencia, "automatico", nome)

    def total(tipo: str, flag: Optional[str] = None) -> float:
        return sum(l["valor"] for l in lines if l["tipo"] == tipo and (flag is None or l[flag]))

    def base_de(flag: str) -> float:
        return max(0.0, r2(total("provento", flag) - total("desconto", flag)))

    salario = float(inp.salario or 0)
    horas_mes = float(inp.horas_mes or 220) or 220.0
    dias_mat = max(0, int(inp.dias_maternidade or 0))
    base_dias = int(inp.base_dias or 30) or 30
    dias = max(0, min(base_dias, int(inp.dias_direito)) - max(0, int(inp.dias_afastado_inss))
               - max(0, int(inp.dias_ferias)) - dias_mat)
    if inp.dias_ferias:
        avisos.append(f"{int(inp.dias_ferias)} dia(s) de férias no mês, pagos no recibo de férias.")
    prop = dias / float(base_dias)
    prolabore = bool(inp.is_prolabore)

    # Lançamentos manuais em rubricas de horas somam à quantidade vinda do ponto.
    horas = {"he50": float(inp.he50), "he100": float(inp.he100), "horas_noturnas": float(inp.horas_noturnas)}
    custom: List[Dict[str, Any]] = []
    comissoes = float(inp.comissoes or 0)
    for lanc in inp.lancamentos:
        cod = str(lanc.get("codigo", ""))
        if cod in _HOUR_CODES and not float(lanc.get("valor") or 0):
            horas[_HOUR_CODES[cod]] += float(lanc.get("quantidade") or 0)
        elif cod in _VALUE_CODES:
            comissoes += float(lanc.get("valor") or 0) * (float(lanc.get("quantidade") or 0) or 1.0)
        elif cod in _SYSTEM_CODES and cod not in _HOUR_CODES:
            avisos.append(f"Lançamento na rubrica de sistema {cod} ignorado (ela é calculada automaticamente).")
        else:
            custom.append(lanc)
    lancados = {str(l.get("codigo")) for l in custom}
    for cod, r in rubrics.items():
        if (r.get("aplica_todos") and r.get("ativo", 1) and (r.get("formula") or "").strip()
                and cod not in _SYSTEM_CODES and cod not in lancados and r.get("tipo") != "informativo"):
            custom.append({"codigo": cod, "quantidade": 0, "valor": 0, "_auto": True})

    # 1. Proventos automáticos
    if prolabore:
        sys("PROLABORE", salario * prop, f"{dias}d")
        adicionais = 0.0
    else:
        if inp.categoria == "professor":
            # CLT art. 320: aulas × 4,5 semanas; DSR de 1/6 (Súmula 351 TST). O salário mensal já soma os dois.
            sys("SALARIO", salario * 6 / 7 * prop, f"{dias}d", nome="Aulas (hora-aula × aulas × 4,5 semanas)")
            sys("DSR_PROFESSOR", salario / 7 * prop, "1/6")
        elif inp.categoria == "horista":
            sys("SALARIO", salario * prop, f"{horas_mes * prop:g}h", nome="Salário Horista (horas + DSR)")
        else:
            sys("SALARIO", salario * prop, f"{dias}d")
        if inp.ats_valor:
            sys("ATS", float(inp.ats_valor) * prop, inp.ats_ref)
        insal_cheio, peric_cheio, grau, conflito = adicionais_fixos(
            salario, inp.insalubridade_grau, inp.periculosidade, tables)
        if conflito:
            avisos.append("Insalubridade e periculosidade não acumulam: foi pago o adicional de maior valor.")
        sys("INSALUBRIDADE", insal_cheio * prop, f"{int(grau * 100)}% s/ mínimo")
        sys("PERICULOSIDADE", peric_cheio * prop, "30%")
        adicionais = insal_cheio + peric_cheio + float(inp.ats_valor or 0)

        # Hora extra e adicional noturno com os percentuais da convenção (mínimos legais: 50% e 20%).
        p50, p100, pnot = float(inp.he50_pct or 50), float(inp.he100_pct or 100), float(inp.noturno_pct or 20)
        valor_hora = (salario + adicionais) / horas_mes
        v_extras = sys("HE50", valor_hora * (1 + p50 / 100) * horas["he50"], f"{horas['he50']:g}h",
                       nome=None if p50 == 50 else f"Hora Extra {p50:g}%")
        v_extras += sys("HE100", valor_hora * (1 + p100 / 100) * horas["he100"], f"{horas['he100']:g}h",
                        nome=None if p100 == 100 else f"Hora Extra {p100:g}%")
        v_extras += sys("NOTURNO", valor_hora * pnot / 100 * horas["horas_noturnas"], f"{horas['horas_noturnas']:g}h",
                        nome=None if pnot == 20 else f"Adicional Noturno {pnot:g}%")
        # Súmula 340 TST (e OJ 397 para quem tem fixo + comissão): as comissões já remuneram a hora
        # trabalhada, inclusive a extra; sobre elas paga-se só o adicional. Valor-hora das comissões =
        # comissões do mês ÷ horas efetivamente trabalhadas (normais + extras).
        horas_trab = horas_mes * prop + horas["he50"] + horas["he100"]
        if comissoes > 0 and horas_trab > 0 and inp.categoria != "professor":
            vh_com = comissoes / horas_trab
            ref_com = f"R$ {vh_com:.2f}/h"
            v_extras += sys("HE50_COMISSAO", vh_com * p50 / 100 * horas["he50"], f"{horas['he50']:g}h · {ref_com}",
                            nome=None if p50 == 50 else f"Adicional de HE {p50:g}% s/ Comissões")
            v_extras += sys("HE100_COMISSAO", vh_com * p100 / 100 * horas["he100"], f"{horas['he100']:g}h · {ref_com}",
                            nome=None if p100 == 100 else f"Adicional de HE {p100:g}% s/ Comissões")
            v_extras += sys("NOTURNO_COMISSAO", vh_com * pnot / 100 * horas["horas_noturnas"],
                            f"{horas['horas_noturnas']:g}h · {ref_com}",
                            nome=None if pnot == 20 else f"Adicional Noturno {pnot:g}% s/ Comissões")
        if v_extras and inp.dias_uteis > 0 and inp.dias_dsr > 0:
            sys("DSR_HE", v_extras / inp.dias_uteis * inp.dias_dsr, f"{inp.dias_dsr}d")

        # Comissões do mês e DSR sobre elas (Lei 605/49 art. 7º; Súmula 27 TST)
        if comissoes > 0:
            v_com = sys("COMISSAO", comissoes, "")
            if inp.dias_uteis > 0 and inp.dias_dsr > 0:
                sys("DSR_COMISSAO", v_com / inp.dias_uteis * inp.dias_dsr, f"{inp.dias_dsr}d")
        # Garantia mínima de quem ganha comissão (CF art. 7º, VII; Lei 8.716/93): mínimo ou piso da convenção.
        if comissoes > 0 or inp.categoria == "variavel":
            garantia = max(tables.salario_minimo, float(inp.piso or 0)) / 220.0 * horas_mes * prop
            cods = {SYSTEM_RUBRICS[k][0] for k in ("SALARIO", "COMISSAO", "DSR_COMISSAO")}
            recebido = sum(l["valor"] for l in lines if l["codigo"] in cods)
            if recebido + 0.005 < garantia:
                sys("GARANTIA_MIN", garantia - recebido, f"mín. R$ {garantia:.2f}")
                avisos.append("Remuneração abaixo da garantia mínima: pago complemento até o mínimo/piso.")

        # Piso da convenção, proporcional à jornada
        if inp.piso and inp.categoria not in ("variavel", "tarefa") and salario:
            piso_prop = float(inp.piso) / 220.0 * horas_mes
            if salario + 0.005 < piso_prop:
                avisos.append(f"Salário abaixo do piso da convenção (R$ {piso_prop:.2f} para a jornada).")

    if dias_mat and not prolabore:
        # Remuneração integral (salário + adicionais fixos) proporcional aos dias de licença.
        sys("SAL_MATERNIDADE", (salario + adicionais) / base_dias * dias_mat, f"{dias_mat}d")
        avisos.append(f"{dias_mat} dia(s) de salário-maternidade: valor compensável na DCTFWeb.")

    if inp.jornada_parcial and not prolabore:
        hs = float(inp.horas_semana or 0)
        if hs > 30:
            avisos.append(f"Jornada parcial de {hs:g}h semanais excede o limite de 30h (CLT art. 58-A).")
        elif hs > 26 and (horas["he50"] or horas["he100"]):
            avisos.append("Jornada parcial acima de 26h semanais não admite horas extras (CLT art. 58-A).")
        piso = tables.salario_minimo / 220.0 * horas_mes
        if salario and salario + 0.005 < piso:
            avisos.append(f"Salário abaixo do mínimo proporcional à jornada (R$ {piso:.2f}).")

    # 2. Rubricas da empresa (fórmula ou valor informado)
    variaveis: Dict[str, float] = {
        "salario_base": salario, "salario_dia": salario / base_dias, "salario_hora": salario / horas_mes,
        "salario_minimo": tables.salario_minimo, "horas_mes": horas_mes, "dias_trabalhados": float(dias),
        "dias_uteis": float(inp.dias_uteis), "dias_dsr": float(inp.dias_dsr),
        "faltas_dias": float(inp.faltas_dias), "horas_faltantes": float(inp.horas_faltantes),
        "horas_extras_50": horas["he50"], "horas_extras_100": horas["he100"],
        "horas_noturnas": horas["horas_noturnas"], "dependentes": float(inp.dependentes),
    }

    def roda_custom(tipo: str) -> None:
        for lanc in sorted((c for c in custom if meta(str(c["codigo"]))["tipo"] == tipo),
                           key=lambda c: str(c["codigo"])):
            cod = str(lanc["codigo"])
            m = meta(cod)
            if cod not in rubrics:
                avisos.append(f"Rubrica {cod} não está cadastrada; lançamento ignorado.")
                continue
            if not m.get("ativo", 1):
                continue
            qtd, informado = float(lanc.get("quantidade") or 0), float(lanc.get("valor") or 0)
            formula = (m.get("formula") or "").strip()
            ctx = dict(variaveis, quantidade=qtd, valor=informado, total_proventos=total("provento"))
            for l in lines:
                ctx[f"rubrica_{l['codigo']}"] = ctx.get(f"rubrica_{l['codigo']}", 0.0) + l["valor"]
            if formula and not (informado and "valor" not in formula):
                try:
                    calculado = evaluate(formula, _com_zeros(formula, ctx))
                except FormulaError as e:
                    avisos.append(f"Rubrica {cod} ({m['nome']}): {e}")
                    continue
                ref = f"{qtd:g}" if qtd else "fórmula"
            else:
                calculado = informado * (qtd if qtd else 1.0)
                ref = f"{qtd:g}" if qtd else ""
            add(cod, calculado, ref, "automatico" if lanc.get("_auto") else "lancamento")

    roda_custom("provento")

    # 3. Descontos que reduzem a base: faltas, DSR perdido e atrasos
    if not prolabore:
        sys("FALTAS", salario / base_dias * inp.faltas_dias, f"{inp.faltas_dias:g}d")
        sys("DSR_FALTAS", salario / base_dias * inp.dsr_perdidos, f"{inp.dsr_perdidos:g}d")
        sys("ATRASOS", salario / horas_mes * inp.horas_faltantes, f"{inp.horas_faltantes:g}h")

    # 4. Salário-família (não integra nenhuma base)
    limite_sf, cota_sf = tables.salario_familia
    if not prolabore and inp.filhos_sal_familia > 0 and cota_sf > 0:
        remuneracao = base_de("incide_inss")
        if 0 < remuneracao <= limite_sf:
            sys("SAL_FAMILIA", cota_sf * inp.filhos_sal_familia * prop, f"{inp.filhos_sal_familia} cota(s)")

    roda_custom("desconto")

    # 5. Bases e encargos
    base_inss = base_de("incide_inss")
    base_irrf = base_de("incide_irrf")
    base_fgts = 0.0 if prolabore else base_de("incide_fgts")
    base_anterior = r2(float(inp.base_inss_ferias or 0) + float(inp.base_inss_outros_vinculos or 0))
    if base_anterior > 0 and base_inss > 0:
        inss_total = calc_inss(base_anterior + base_inss, tables, prolabore)
        inss_ja_retido = r2(float(inp.inss_ferias or 0) + float(inp.inss_outros_vinculos or 0))
        if inss_ja_retido <= 0:
            inss_ja_retido = calc_inss(base_anterior, tables, prolabore)
        inss = max(0.0, r2(inss_total - inss_ja_retido))
        partes = []
        if inp.base_inss_ferias > 0:
            partes.append(f"férias (base R$ {inp.base_inss_ferias:.2f})")
        if inp.base_inss_outros_vinculos > 0:
            partes.append(f"outros vínculos (base R$ {inp.base_inss_outros_vinculos:.2f})")
        avisos.append(f"INSS recalculado progressivamente somando {' e '.join(partes)}.")
    else:
        inss = calc_inss(base_inss, tables, prolabore)
    bruto = r2(total("provento"))

    ir, pens = resolve_irrf_pensao(base_irrf, inss, inp.dependentes, inp.pensoes, bruto, tables)
    irrf = ir["irrf"]

    sys("INSS", inss, "11%" if prolabore else "tabela")
    sys("IRRF", irrf, "simplificado" if ir["simplificado"] else f"{inp.dependentes} dep.")
    for p, v in zip(inp.pensoes, pens):
        benef = (p.get("beneficiario") or "").strip()
        ref = f"{float(p.get('percentual') or 0):g}%" if (p.get("modalidade") or "percentual") == "percentual" else "fixo"
        sys("PENSAO", v, ref, f"Pensão Alimentícia — {benef}" if benef else None)

    # 6. Demais descontos
    vt = 0.0
    if not prolabore and inp.vt_mensal > 0:
        vt = sys("VT", min(salario * prop * 0.06, inp.vt_mensal), "6%")
    for b in inp.beneficios:
        tipo_b = (b.get("tipo") or "").lower()
        if "transporte" in tipo_b:
            if not vt and not prolabore:
                vt = sys("VT", min(salario * prop * 0.06, float(b.get("desconto") or 0) or salario), "6%")
            continue
        key = "VA" if ("aliment" in tipo_b or "refei" in tipo_b) else "BENEFICIO"
        sys(key, float(b.get("desconto") or 0), "", b.get("nome") or None)
    for p in inp.planos_saude:
        sys("PLANO_SAUDE", float(p.get("valor") or 0), p.get("ref") or "", p.get("nome") or None)
    for c in inp.copart:
        sys("PLANO_COPART", float(c.get("valor") or 0), "", c.get("nome") or None)
    if inp.consignados:
        # Lei 10.820/2003: margem sobre a remuneração disponível (bruto − INSS − IRRF − pensão)
        marg = _benef.margem(bruto, inss + irrf + sum(pens), inp.consignado_pct)
        parcelas, avs = _benef.aplicar_margem(inp.consignados, marg)
        avisos.extend(avs)
        for p in parcelas:
            key = "CONSIGNADO_CONV" if p.get("origem") == "convenio" else "CONSIGNADO"
            sys(key, p["valor"], p.get("ref") or "", p.get("nome") or None)
    sys("ADIANTAMENTO", inp.adiantamentos)
    if not prolabore and inp.cct_percentual > 0:
        sys("CONTRIB_ASSIST", salario * inp.cct_percentual / 100.0, f"{inp.cct_percentual:g}%")

    fgts = r2(base_fgts * tables.fgts_aliquota)

    total_proventos = r2(total("provento"))
    total_descontos = r2(total("desconto"))
    liquido = r2(total_proventos - total_descontos)
    if liquido < 0:
        avisos.append("Descontos maiores que os proventos: líquido negativo. Revise os lançamentos.")

    # 7. Linhas informativas (não entram nos totais)
    for key, v in (("BASE_INSS", base_inss), ("BASE_IRRF", ir["base"]),
                   ("BASE_FGTS", base_fgts), ("FGTS_INFO", fgts)):
        sys(key, v)

    for l in lines:
        for flag in ("incide_inss", "incide_irrf", "incide_fgts"):
            l.pop(flag, None)

    return {
        "employee_id": inp.employee_id,
        "employee_name": inp.nome,
        "dias_pagos": dias,
        "lines": lines,
        "total_proventos": total_proventos,
        "total_descontos": total_descontos,
        "liquido": liquido,
        "base_inss": base_inss,
        "base_irrf": ir["base"],
        "base_fgts": base_fgts,
        "inss": inss,
        "irrf": irrf,
        "fgts": fgts,
        "vt_desconto": vt,
        "irrf_simplificado": bool(ir["simplificado"]),
        "irrf_reducao": ir["reducao"],
        "avisos": avisos,
    }


def _com_zeros(formula: str, ctx: Dict[str, float]) -> Dict[str, float]:
    """Rubricas referenciadas que não tiveram valor no mês valem zero."""
    for nome in re.findall(r"\brubrica_\w+", formula):
        ctx.setdefault(nome, 0.0)
    return ctx


# ── Leitura do banco ─────────────────────────────────────────────────────────
def _parse_date(value: Any) -> Optional[date]:
    s = str(value or "").strip()[:10]
    if not s:
        return None
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return date(int(s[:4]), int(s[5:7]), int(s[8:10]))
        if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
            return date(int(s[6:10]), int(s[3:5]), int(s[0:2]))
        d = re.sub(r"\D", "", s)
        if len(d) == 8:
            return date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    except ValueError:
        return None
    return None


def _rows(conn, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception:
        return []  # tabela opcional ainda não criada


def load_rubrics(conn, company_id: int) -> Dict[str, Dict[str, Any]]:
    return {str(r["codigo"]): r for r in _rows(
        conn, "SELECT * FROM payroll_rubrics WHERE company_id=? ORDER BY codigo", (company_id,))}


def ensure_system_rubrics(conn, company_id: int) -> int:
    """Cadastra as rubricas de sistema que a empresa ainda não tem (para S-1010 e holerite)."""
    existentes = {str(r["codigo"]) for r in _rows(
        conn, "SELECT codigo FROM payroll_rubrics WHERE company_id=?", (company_id,))}
    criadas = 0
    for codigo, nome, tipo, i1, i2, i3, nat in SYSTEM_RUBRICS.values():
        if codigo in existentes:
            continue
        conn.execute(
            """INSERT INTO payroll_rubrics
               (company_id,codigo,nome,tipo,incide_inss,incide_irrf,incide_fgts,incide_13,incide_ferias,esocial_nat_rubrica,ativo)
               VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
            (company_id, codigo, nome, tipo, i1, i2, i3, i1, i1, nat))
        criadas += 1
    return criadas


def month_calendar(conn, company_id: int, competencia: str) -> Dict[str, Any]:
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    ultimo = calendar.monthrange(ano, mes)[1]
    inicio, fim = date(ano, mes, 1), date(ano, mes, ultimo)
    feriados = set()
    for f in _rows(conn, "SELECT data FROM feriados WHERE company_id=? AND data LIKE ?",
                   (company_id, f"{competencia}%")):
        d = _parse_date(f["data"])
        if d:
            feriados.add(d)
    uteis = dsr = 0
    d = inicio
    while d <= fim:
        if d.weekday() == 6 or d in feriados:
            dsr += 1
        else:
            uteis += 1
        d += timedelta(days=1)
    return {"inicio": inicio, "fim": fim, "feriados": feriados, "dias_uteis": uteis, "dias_dsr": dsr}


_TIPOS_INSS = ("auxilio_doenca_b31", "auxilio_doenca_b91", "acidente_trabalho")


def _dias_inss_no_mes(afastamentos: List[Dict[str, Any]], inicio: date, fim: date, cheio: int = 30) -> int:
    dias = set()
    for a in afastamentos:
        ini = _parse_date(a.get("data_inicio"))
        if not ini:
            continue
        if not (int(a.get("dias_inss") or 0) > 0 or a.get("tipo") in _TIPOS_INSS):
            continue
        ini_inss = ini + timedelta(days=int(a.get("dias_empresa") or 0))
        retorno = _parse_date(a.get("retorno_efetivo"))
        fim_af = (retorno - timedelta(days=1)) if retorno else (_parse_date(a.get("data_fim")) or fim)
        d = max(ini_inss, inicio)
        while d <= min(fim_af, fim):
            dias.add(d)
            d += timedelta(days=1)
    total_mes = (fim - inicio).days + 1
    return cheio if len(dias) >= total_mes else min(len(dias), cheio)


def _dias_maternidade_no_mes(afastamentos: List[Dict[str, Any]], inicio: date, fim: date, cheio: int = 30) -> int:
    """Dias de salário-maternidade no mês: só os 120 primeiros dias da licença; a prorrogação
    da Empresa Cidadã (Lei 11.770/2008) é paga como salário normal (dedução no IRPJ)."""
    dias = set()
    for a in afastamentos:
        if not str(a.get("tipo") or "").startswith("maternidade"):
            continue
        ini = _parse_date(a.get("data_inicio"))
        if not ini:
            continue
        retorno = _parse_date(a.get("retorno_efetivo"))
        fim_af = (retorno - timedelta(days=1)) if retorno else (_parse_date(a.get("data_fim")) or fim)
        fim_af = min(fim_af, ini + timedelta(days=119))
        d = max(ini, inicio)
        while d <= min(fim_af, fim):
            dias.add(d)
            d += timedelta(days=1)
    total_mes = (fim - inicio).days + 1
    return cheio if len(dias) >= total_mes else min(len(dias), cheio)


def custo_vt(vales: List[Dict[str, Any]], dias_padrao: int) -> float:
    """Custo mensal do vale-transporte: tarifa × vales por dia × dias de uso."""
    total = 0.0
    for v in vales:
        if not int(v.get("ativo", 1) or 0):
            continue
        dias = int(v.get("dias_mes") or 0) or dias_padrao
        total += float(v.get("tarifa") or 0) * int(v.get("vales_dia") or 0) * dias
    return r2(total)


def dias_uteis_seg_sex(inicio: date, fim: date, feriados: set) -> int:
    n, d = 0, inicio
    while d <= fim:
        if d.weekday() < 5 and d not in feriados:
            n += 1
        d += timedelta(days=1)
    return n


def _dias_ferias_no_mes(ferias: List[Dict[str, Any]], inicio: date, fim: date, cheio: int = 30) -> int:
    dias = set()
    for f in ferias:
        ini, f_fim = _parse_date(f.get("data_inicio")), _parse_date(f.get("data_fim"))
        if not ini or not f_fim:
            continue
        d = max(ini, inicio)
        while d <= min(f_fim, fim):
            dias.add(d)
            d += timedelta(days=1)
    total_mes = (fim - inicio).days + 1
    return cheio if len(dias) >= total_mes else min(len(dias), cheio)


def _noturnas_do_mes(escala: Dict[str, Any], inicio_func: Any, inicio: date, fim: date,
                     ponto: List[Dict[str, Any]], afastamentos: List[Dict[str, Any]],
                     ferias: List[Dict[str, Any]], admissao: Optional[date]) -> float:
    """Horas noturnas (reduzidas) do mês pela escala: dia com marcação usa o horário batido; dia escalado
    sem marcação usa o horário da escala; falta, afastamento e férias não contam."""
    por_dia = {_parse_date(t.get("data")): t for t in ponto if _parse_date(t.get("data"))}
    fora = set()
    for r in list(afastamentos) + list(ferias):
        ini, f = _parse_date(r.get("data_inicio")), _parse_date(r.get("data_fim"))
        if ini:  # afastamento de qualquer tipo ou férias: não trabalhou
            d = max(ini, inicio)
            while d <= min(f or fim, fim):
                fora.add(d)
                d += timedelta(days=1)
    turno = _escalas.turno_do_dia(escala)
    prorrog = bool(escala.get("prorrogacao_noturna", 1))
    total = 0.0
    d = inicio
    while d <= fim:
        t = por_dia.get(d)
        if admissao and d < admissao:
            pass
        elif t is not None:
            oc = (t.get("tipo_ocorrencia") or "normal").lower()
            if oc == "normal" and t.get("entrada") and t.get("saida"):
                iv_ini, iv_min = "", 0
                if t.get("saida_almoco") and t.get("retorno_almoco"):
                    a, b = _escalas._min(t["saida_almoco"]), _escalas._min(t["retorno_almoco"])
                    if a is not None and b is not None:
                        iv_ini, iv_min = t["saida_almoco"], (b - a) % 1440
                total += _escalas.horas_turno(t["entrada"], t["saida"], iv_min, iv_ini, prorrog)["noturnas"]
        elif d not in fora:
            try:
                if _escalas.trabalha_no_dia(escala, d, inicio_func):
                    total += turno["noturnas"]
            except ValueError:
                pass
        d += timedelta(days=1)
    return total


def build_inputs(
    conn,
    company_id: int,
    competencia: str,
    pagar_horas_extras: bool = True,
    employee_ids: Optional[List[int]] = None,
    rubrics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[EmployeeInput]:
    """Monta as entradas do motor para todos os funcionários ativos na competência."""
    cal = month_calendar(conn, company_id, competencia)
    inicio, fim = cal["inicio"], cal["fim"]
    like = f"{competencia}%"
    if rubrics is None:
        rubrics = load_rubrics(conn, company_id)

    params = dp_parametros.carregar(conn, company_id)
    base_dias = 30 if params["base_dias"] == "30" else fim.day
    employees = _rows(conn, "SELECT * FROM employees WHERE company_id=? AND active=1 ORDER BY name", (company_id,))
    if employee_ids:
        employees = [e for e in employees if e["id"] in set(employee_ids)]

    def por_emp(rows: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        out: Dict[int, List[Dict[str, Any]]] = {}
        for r in rows:
            out.setdefault(r["employee_id"], []).append(r)
        return out

    ponto = por_emp(_rows(conn, "SELECT * FROM time_records WHERE company_id=? AND data LIKE ?", (company_id, like)))
    afast = por_emp(_rows(conn, "SELECT * FROM employee_absences WHERE company_id=?", (company_id,)))
    benef = por_emp(_rows(conn, """
        SELECT eb.*, bt.nome AS bt_nome, bt.tipo AS bt_tipo
        FROM employee_benefits eb JOIN benefit_types bt ON bt.id = eb.benefit_type_id
        WHERE eb.company_id=? AND eb.ativo=1""", (company_id,)))
    adiant = por_emp(_rows(conn, "SELECT * FROM salary_advances WHERE company_id=? AND competencia=?",
                           (company_id, competencia)))
    pensao = por_emp(_rows(conn, "SELECT * FROM alimony_orders WHERE company_id=? AND ativo=1", (company_id,)))
    ferias = por_emp(_rows(conn, """
        SELECT id, employee_id, competencia, data_inicio, data_fim, dias_gozo, total_proventos, inss
        FROM payroll_special
        WHERE company_id=? AND tipo='ferias' AND status != 'cancelado'""", (company_id,)))
    ferias_lines_all = _rows(conn, """
        SELECT psl.special_id, psl.codigo, psl.tipo, psl.valor
        FROM payroll_special_lines psl
        JOIN payroll_special ps ON ps.id = psl.special_id
        WHERE ps.company_id=? AND ps.tipo='ferias' AND ps.status != 'cancelado'""", (company_id,))
    ferias_lines_by_id: Dict[int, List[Dict[str, Any]]] = {}
    for fl in ferias_lines_all:
        ferias_lines_by_id.setdefault(fl["special_id"], []).append(fl)

    contratos_extra = por_emp(_rows(conn, """
        SELECT * FROM employee_contracts WHERE company_id=? AND ativo=1""", (company_id,)))
    outros_emps_all = _rows(conn, "SELECT id, company_id, cpf, salary, admission_date, active FROM employees WHERE active=1")
    outros_by_cpf: Dict[str, List[Dict[str, Any]]] = {}
    for oe in outros_emps_all:
        cpf_k = re.sub(r"\D", "", str(oe.get("cpf") or ""))
        if cpf_k:
            outros_by_cpf.setdefault(cpf_k, []).append(oe)

    escalas_emp = {r["id"]: r for r in _rows(conn, "SELECT * FROM work_schedules WHERE company_id=?", (company_id,))}
    vt_vales = por_emp(_rows(conn, "SELECT * FROM employee_vt WHERE company_id=? AND ativo=1", (company_id,)))
    dias_vt = dias_uteis_seg_sex(inicio, fim, cal["feriados"])

    # Bloco 4 — plano de saúde (faixa etária, dependentes, coparticipação) e consignado
    planos = {p["id"]: p for p in _rows(conn, "SELECT * FROM planos_saude WHERE company_id=? AND ativo=1", (company_id,))}
    faixas_plano: Dict[int, List[Dict[str, Any]]] = {}
    if planos:
        for f in _rows(conn, f"SELECT * FROM planos_saude_faixas WHERE plano_id IN ({','.join('?' * len(planos))})",
                       tuple(planos)):
            faixas_plano.setdefault(f["plano_id"], []).append(f)
    adesoes = por_emp(_rows(conn, "SELECT * FROM employee_planos_saude WHERE company_id=? AND ativo=1", (company_id,)))
    deps_plano = por_emp(_rows(conn, "SELECT * FROM employee_dependents WHERE company_id=? AND plano_saude=1",
                               (company_id,)))
    copart = por_emp(_rows(conn, "SELECT * FROM planos_saude_copart WHERE company_id=? AND competencia=?",
                           (company_id, competencia)))
    consig = por_emp(_rows(conn, """SELECT * FROM emprestimos_consignados WHERE company_id=? AND ativo=1
                                    ORDER BY competencia_inicio, id""", (company_id,)))

    lanc = por_emp(_rows(conn, """
        SELECT er.employee_id, er.quantidade, er.valor, er.competencia, r.codigo
        FROM employee_rubrics er JOIN payroll_rubrics r ON r.id = er.rubric_id
        WHERE er.company_id=? AND er.ativo=1 AND (er.competencia='' OR er.competencia IS NULL OR er.competencia=?)""",
        (company_id, competencia)))

    ccts = [c for c in _rows(conn, "SELECT * FROM cct_assistencial WHERE company_id=? AND ativo=1", (company_id,))
            if (_parse_date(c.get("data_inicio")) or inicio) <= fim
            and (_parse_date(c.get("data_fim")) or fim) >= inicio]
    oposicoes = {(o["cct_id"], o["employee_id"]) for o in _rows(
        conn, "SELECT cct_id, employee_id FROM cct_oposicoes WHERE company_id=?", (company_id,))}

    def vigente(r: Dict[str, Any]) -> bool:
        ini, f = _parse_date(r.get("data_inicio")), _parse_date(r.get("data_fim"))
        return (ini is None or ini <= fim) and (f is None or f >= inicio)

    ccts_conv = _cct.carregar_ccts(conn, company_id)
    tables_sm = load_tables(conn, company_id, competencia).salario_minimo if ccts_conv else 0.0

    inputs: List[EmployeeInput] = []
    for e in employees:
        eid = e["id"]
        adm = _parse_date(e.get("admission_date"))
        if adm and adm > fim:
            continue  # ainda não admitido na competência
        dias_direito = base_dias
        if adm and adm >= inicio and adm.day > 1:
            dias_direito = max(1, min(base_dias, fim.day - adm.day + 1))

        he50 = he100 = faltantes = faltas = 0.0
        semanas_com_falta = set()
        escala = escalas_emp.get(e.get("work_schedule_id")) if e.get("work_schedule_id") else None
        ciclica = bool(escala and (escala.get("tipo") or "fixo") == "ciclica")
        for t in ponto.get(eid, []):
            d = _parse_date(t.get("data"))
            if not d:
                continue
            oc = (t.get("tipo_ocorrencia") or "normal").lower()
            if oc == "falta_injustificada":
                faltas += 1
                semanas_com_falta.add(d.isocalendar()[:2])
                continue
            if oc != "normal":
                continue
            if ciclica:
                # Escala cíclica (12x36 etc.): o domingo não é o descanso; folga trabalhada = 100%.
                try:
                    escalado = _escalas.trabalha_no_dia(escala, d, e.get("escala_inicio"))
                except ValueError:
                    escalado = True
                feriado_pago = d in cal["feriados"] and not escala.get("feriados_compensados", 1)
                if not escalado or feriado_pago:
                    he100 += float(t.get("horas_trabalhadas") or 0)
                else:
                    he50 += float(t.get("horas_extras") or 0)
                    faltantes += float(t.get("horas_faltantes") or 0)
            elif d.weekday() == 6 or d in cal["feriados"]:
                he100 += float(t.get("horas_trabalhadas") or 0)
            else:
                he50 += float(t.get("horas_extras") or 0)
                faltantes += float(t.get("horas_faltantes") or 0)
        if not pagar_horas_extras:
            he50 = he100 = 0.0
        noturnas = 0.0
        if escala and escala.get("adicional_noturno_auto"):
            noturnas = _noturnas_do_mes(escala, e.get("escala_inicio"), inicio, fim, ponto.get(eid, []),
                                        afast.get(eid, []), ferias.get(eid, []), adm)

        # Férias na competência: soma base de INSS e INSS retido nas férias proporcionais aos dias no mês
        base_inss_ferias = 0.0
        inss_ferias = 0.0
        for f_rec in ferias.get(eid, []):
            f_ini, f_fim = _parse_date(f_rec.get("data_inicio")), _parse_date(f_rec.get("data_fim"))
            if not f_ini or not f_fim:
                continue
            ov_ini, ov_fim = max(f_ini, inicio), min(f_fim, fim)
            if ov_fim < ov_ini:
                continue
            dias_ov = (ov_fim - ov_ini).days + 1
            total_dias = max(1, (f_fim - f_ini).days + 1)
            frac = min(1.0, dias_ov / total_dias)
            flines = ferias_lines_by_id.get(f_rec["id"], [])
            if flines:
                base_f = sum(
                    float(fl.get("valor") or 0)
                    for fl in flines
                    if fl.get("tipo") == "provento" and rubric_meta(rubrics, str(fl.get("codigo")))["incide_inss"]
                )
            else:
                base_f = float(f_rec.get("total_proventos") or 0)
            base_inss_ferias += base_f * frac
            inss_ferias += float(f_rec.get("inss") or 0) * frac

        # Multi-vínculo: contratos adicionais em employee_contracts e outros vínculos do mesmo CPF
        base_outros = 0.0
        inss_outros = 0.0
        for ce in contratos_extra.get(eid, []):
            c_adm = _parse_date(ce.get("admission_date"))
            c_term = _parse_date(ce.get("termination_date"))
            if (c_adm is None or c_adm <= fim) and (c_term is None or c_term >= inicio):
                sal_c = float(ce.get("salario") or 0)
                if sal_c > 0:
                    base_outros += sal_c
        cpf_k = re.sub(r"\D", "", str(e.get("cpf") or ""))
        if cpf_k:
            for oe in outros_by_cpf.get(cpf_k, []):
                if oe["id"] == eid:
                    continue
                oe_adm = _parse_date(oe.get("admission_date"))
                if oe_adm and oe_adm > fim:
                    continue
                proc_rows = _rows(conn, """
                    SELECT pi.base_inss, pi.inss
                    FROM payroll_items pi JOIN payroll_runs pr ON pr.id = pi.run_id
                    WHERE pr.company_id=? AND pr.competence=? AND pi.employee_id=? AND pr.status != 'cancelado'
                      AND COALESCE(pr.tipo, 'mensal') = 'mensal'
                    LIMIT 1""", (oe["company_id"], competencia, oe["id"]))
                if proc_rows:
                    base_outros += float(proc_rows[0].get("base_inss") or 0)
                    inss_outros += float(proc_rows[0].get("inss") or 0)
                elif oe["id"] < eid:
                    base_outros += float(oe.get("salary") or 0)

        # VT: só os dias úteis em que trabalha (fora férias, afastamentos e faltas)
        vt_custo = float(e.get("vt_monthly") or 0)
        if vt_vales.get(eid):
            fora = [(_parse_date(f.get("data_inicio")), _parse_date(f.get("data_fim"))) for f in ferias.get(eid, [])]
            fora += [(_parse_date(a.get("data_inicio")), _parse_date(a.get("data_fim")) or fim)
                     for a in afast.get(eid, [])]
            datas_falta = {_parse_date(t.get("data")) for t in ponto.get(eid, [])
                           if (t.get("tipo_ocorrencia") or "").lower() == "falta_injustificada"}
            dias_uso = _benef.dias_uso_vt(inicio, fim, cal["feriados"], adm, _parse_date(e.get("termination_date")),
                                          fora, datas_falta)
            vt_custo = custo_vt(vt_vales[eid], dias_uso)

        planos_emp, copart_emp, avisos_emp = [], [], []
        for ad in adesoes.get(eid, []):
            plano = planos.get(ad["plano_id"])
            if not plano or not vigente(ad):
                continue
            deps = deps_plano.get(eid, []) if int(ad.get("incluir_dependentes", 1) or 0) else []
            m = _benef.mensalidade_plano(plano, faixas_plano.get(plano["id"], []), e.get("birth_date"), deps, fim)
            avisos_emp.extend(m["avisos"])
            if m["empregado"] > 0:
                vidas = len(m["vidas"])
                planos_emp.append({"nome": f"Plano {plano['nome']}", "valor": m["empregado"],
                                   "ref": f"{vidas} vida(s)" if vidas > 1 else "titular"})
            pct_c = min(100.0, max(0.0, float(plano.get("copart_pct_empregado") if plano.get("copart_pct_empregado") is not None else 100))) / 100.0
            tot_c = sum(float(c.get("valor") or 0) for c in copart.get(eid, []) if c["plano_id"] == plano["id"])
            if tot_c * pct_c > 0:
                copart_emp.append({"nome": f"Coparticipação — {plano['nome']}", "valor": r2(tot_c * pct_c)})
        consig_emp = []
        for c in consig.get(eid, []):
            n_parc, v_parc = _benef.parcela_do_mes(c, competencia)
            if v_parc > 0:
                consig_emp.append({"nome": f"Consignado {c.get('instituicao') or ''}".strip(), "valor": v_parc,
                                   "origem": c.get("origem") or "credito_trabalhador",
                                   "ref": f"{n_parc}/{c.get('parcelas_total') or '?'}"})

        horas_semana = float(e.get("horas_semana") or 44) or 44.0
        cct = _cct.cct_do_funcionario(ccts_conv, e, fim)
        p50, p100, pnot = _cct.percentuais(cct)
        sal_mensal, sal_ref = _cct.salario_mensal(e)
        ats_valor, ats_ref = _cct.adicional_tempo_servico(cct, adm, fim, sal_mensal, tables_sm)
        categoria = ("professor" if (e.get("categoria_especial") or "") == "professor"
                     else _cct.TIPOS_SALARIO.get(str(e.get("tipo_salario") or "5"), "mensalista"))
        inputs.append(EmployeeInput(
            employee_id=eid,
            nome=e.get("name") or "",
            salario=sal_mensal,
            he50_pct=p50, he100_pct=p100, noturno_pct=pnot,
            ats_valor=ats_valor, ats_ref=ats_ref,
            piso=float((cct or {}).get("piso_salarial") or 0),
            categoria=categoria, salario_ref=sal_ref,
            dependentes=int(e.get("dependents") or 0),
            is_prolabore=bool(e.get("is_prolabore")),
            horas_mes=round(horas_semana * 5, 2),
            dias_direito=dias_direito,
            base_dias=base_dias,
            dias_afastado_inss=_dias_inss_no_mes(afast.get(eid, []), inicio, fim, base_dias),
            dias_ferias=_dias_ferias_no_mes(ferias.get(eid, []), inicio, fim, base_dias),
            faltas_dias=faltas,
            dsr_perdidos=float(len(semanas_com_falta)) if params["descontar_dsr_faltas"] else 0.0,
            horas_faltantes=round(faltantes, 2),
            he50=round(he50, 2),
            he100=round(he100, 2),
            horas_noturnas=round(noturnas, 2),
            dias_uteis=cal["dias_uteis"],
            dias_dsr=cal["dias_dsr"],
            insalubridade_grau=e.get("insalubridade_grau") or "",
            periculosidade=bool(e.get("periculosidade")),
            filhos_sal_familia=int(e.get("filhos_sal_familia") or 0),
            vt_mensal=vt_custo,
            planos_saude=planos_emp, copart=copart_emp, consignados=consig_emp, avisos_extra=avisos_emp,
            consignado_pct=float(params.get("consignado_margem_pct") or _benef.MARGEM_PADRAO),
            beneficios=[{"nome": b.get("bt_nome"), "tipo": b.get("bt_tipo"),
                         "desconto": float(b.get("valor_desconto") or 0)}
                        for b in benef.get(eid, []) if vigente(b)],
            adiantamentos=sum(float(a.get("valor") or 0) for a in adiant.get(eid, [])
                              if (a.get("status") or "pago").lower() not in ("cancelado", "rejeitado")),
            pensoes=[p for p in pensao.get(eid, []) if vigente(p)],
            cct_percentual=sum(float(c.get("percentual") or 0) for c in ccts
                               if (c["id"], eid) not in oposicoes),
            lancamentos=[{"codigo": l["codigo"], "quantidade": l.get("quantidade") or 0,
                          "valor": l.get("valor") or 0} for l in lanc.get(eid, [])],
            base_inss_ferias=r2(base_inss_ferias),
            inss_ferias=r2(inss_ferias),
            base_inss_outros_vinculos=r2(base_outros),
            inss_outros_vinculos=r2(inss_outros),
            dias_maternidade=_dias_maternidade_no_mes(afast.get(eid, []), inicio, fim, base_dias),
            jornada_parcial=(str(e.get("jornada_tipo") or "").lower() == "parcial"),
            horas_semana=horas_semana,
        ))
    return inputs


def run_payroll(
    conn,
    company_id: int,
    competencia: str,
    pagar_horas_extras: bool = True,
    employee_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Calcula a folha da competência (sem gravar). Devolve resultados por funcionário e totais."""
    tables = load_tables(conn, company_id, competencia)
    rubrics = load_rubrics(conn, company_id)
    inputs = build_inputs(conn, company_id, competencia, pagar_horas_extras, employee_ids, rubrics=rubrics)
    results = [calculate_employee(i, tables, rubrics) for i in inputs]
    return {
        "competencia": competencia,
        "tabelas": {"origem": tables.origem, "salario_minimo": tables.salario_minimo,
                    "inss_teto": tables.inss_teto},
        "results": results,
        "totais": {
            "proventos": r2(sum(r["total_proventos"] for r in results)),
            "descontos": r2(sum(r["total_descontos"] for r in results)),
            "liquido": r2(sum(r["liquido"] for r in results)),
            "inss": r2(sum(r["inss"] for r in results)),
            "irrf": r2(sum(r["irrf"] for r in results)),
            "fgts": r2(sum(r["fgts"] for r in results)),
        },
    }
