"""
13º salário, férias e rescisão pelo motor de rubricas.

Mesma lógica da folha mensal: cada cálculo vira linhas de rubrica, e as bases de
INSS, IRRF e FGTS são a soma das rubricas com a respectiva incidência. As linhas têm
um "grupo" porque a lei tributa separadamente o 13º (tabela própria de INSS e IRRF
exclusivo na fonte) e as férias (IRRF em separado do salário do mês).

  * calc_decimo / calc_ferias / calc_rescisao  — cálculo puro, sem banco;
  * avos_decimo, periodos_aquisitivos, planejar_rescisao — regras de datas, puras;
  * contexto_funcionario, media_variaveis, ...  — leitura do banco.
"""
import calendar
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from . import payroll_engine as pe, cct_regras
    from .payroll_tables import TaxTables, load_tables
except ImportError:  # execução com backend/ como raiz
    from services import payroll_engine as pe, cct_regras
    from services.payroll_tables import TaxTables, load_tables

r2 = pe.r2

TIPOS_RESCISAO: Dict[str, Dict[str, Any]] = {
    # aviso: fração do aviso indenizado devida; multa: % sobre o saldo do FGTS
    "sem_justa_causa":  {"nome": "Dispensa sem justa causa", "aviso": 1.0, "decimo": True, "ferias_prop": True, "multa": 0.40},
    "pedido_demissao":  {"nome": "Pedido de demissão", "aviso": 0.0, "decimo": True, "ferias_prop": True, "multa": 0.0},
    "com_justa_causa":  {"nome": "Dispensa por justa causa", "aviso": 0.0, "decimo": False, "ferias_prop": False, "multa": 0.0},
    "acordo":           {"nome": "Acordo entre as partes (CLT 484-A)", "aviso": 0.5, "decimo": True, "ferias_prop": True, "multa": 0.20},
    "termino_contrato": {"nome": "Término de contrato a prazo", "aviso": 0.0, "decimo": True, "ferias_prop": True, "multa": 0.0},
}
AVISO_MODOS = ("indenizado", "trabalhado", "dispensado", "nao_cumprido")


# ── Contexto do funcionário ──────────────────────────────────────────────────
@dataclass
class Contexto:
    employee_id: int
    nome: str
    salario: float
    admissao: Optional[date] = None
    dependentes: int = 0
    is_prolabore: bool = False
    insalubridade_grau: str = ""
    periculosidade: bool = False
    pensoes: List[Dict[str, Any]] = field(default_factory=list)
    ats: float = 0.0                 # adicional por tempo de serviço da convenção (valor mensal)
    ats_ref: str = ""
    cct: Optional[Dict[str, Any]] = None
    data_base_mes: int = 0

    def remuneracao(self, tables: TaxTables) -> float:
        """Salário + adicionais fixos (insalubridade, periculosidade e tempo de serviço): base de 13º, férias e aviso."""
        insal, peric, _, _ = pe.adicionais_fixos(self.salario, self.insalubridade_grau, self.periculosidade, tables)
        return self.salario + insal + peric + self.ats


class _Folha:
    """Acumula linhas de rubrica e calcula bases por incidência e por grupo."""

    def __init__(self, rubrics: Optional[Dict[str, Dict[str, Any]]]):
        self.rubrics = rubrics or {}
        self.lines: List[Dict[str, Any]] = []
        self.avisos: List[str] = []

    def add(self, key: str, valor: float, referencia: str = "", grupo: str = "mensal",
            nome: Optional[str] = None) -> float:
        valor = r2(valor)
        if valor <= 0:
            return 0.0
        codigo = pe.SYSTEM_RUBRICS[key][0]
        m = pe.rubric_meta(self.rubrics, codigo)
        tipo = pe.SYSTEM_RUBRICS[key][2]  # o tipo de uma rubrica de sistema não muda
        self.lines.append({
            "codigo": codigo, "nome": nome or m["nome"], "tipo": tipo, "referencia": referencia,
            "valor": valor, "origem": "automatico", "grupo": grupo,
            "incide_inss": int(m.get("incide_inss") or 0),
            "incide_irrf": int(m.get("incide_irrf") or 0),
            "incide_fgts": int(m.get("incide_fgts") or 0),
        })
        return valor

    def total(self, tipo: str, flag: Optional[str] = None, grupo: Optional[str] = None) -> float:
        return sum(l["valor"] for l in self.lines
                   if l["tipo"] == tipo and (flag is None or l[flag]) and (grupo is None or l["grupo"] == grupo))

    def base(self, flag: str, grupo: Optional[str] = None) -> float:
        return max(0.0, r2(self.total("provento", flag, grupo) - self.total("desconto", flag, grupo)))

    def resultado(self, ctx: Contexto, **extra: Any) -> Dict[str, Any]:
        proventos, descontos = r2(self.total("provento")), r2(self.total("desconto"))
        liquido = r2(proventos - descontos)
        if liquido < 0:
            self.avisos.append("Descontos maiores que os proventos: líquido negativo. Revise os valores.")
        lines = [{k: v for k, v in l.items() if not k.startswith("incide_")} for l in self.lines]
        out = {
            "employee_id": ctx.employee_id, "employee_name": ctx.nome, "lines": lines,
            "total_proventos": proventos, "total_descontos": descontos, "liquido": liquido,
            "inss": 0.0, "irrf": 0.0, "fgts": 0.0, "multa_fgts": 0.0, "avisos": self.avisos,
        }
        out.update(extra)
        return out


def _encargos(f: _Folha, ctx: Contexto, tables: TaxTables, grupo: str, key_inss: str, key_irrf: str,
              nome_inss: Optional[str] = None, nome_irrf: Optional[str] = None,
              so_pensao_percentual: bool = False) -> Tuple[float, float]:
    """Lança INSS, IRRF e pensão de um grupo de rubricas tributado em separado.
    so_pensao_percentual: pensão de valor fixo já é descontada na folha mensal, então em
    férias e 13º só entram as pensões em percentual."""
    base_inss = f.base("incide_inss", grupo)
    base_irrf = f.base("incide_irrf", grupo)
    inss = pe.calc_inss(base_inss, tables, ctx.is_prolabore)
    pensoes = ctx.pensoes
    if so_pensao_percentual:
        pensoes = [p for p in ctx.pensoes if (p.get("modalidade") or "percentual") == "percentual"]
        if len(pensoes) != len(ctx.pensoes) and f.base("incide_irrf", grupo) > 0:
            f.avisos.append("Pensão de valor fixo não foi descontada neste cálculo (só na folha mensal). "
                            "Confira a decisão judicial.")
    ir, pens = pe.resolve_irrf_pensao(base_irrf, inss, ctx.dependentes, pensoes,
                                      f.total("provento", None, grupo), tables)
    f.add(key_inss, inss, "tabela", grupo, nome_inss)
    f.add(key_irrf, ir["irrf"], "simplificado" if ir["simplificado"] else f"{ctx.dependentes} dep.", grupo, nome_irrf)
    for p, v in zip(pensoes, pens):
        benef = (p.get("beneficiario") or "").strip()
        f.add("PENSAO", v, "", grupo, f"Pensão Alimentícia — {benef}" if benef else None)
    return inss, ir["irrf"]


# ── 13º salário ──────────────────────────────────────────────────────────────
def calc_decimo(ctx: Contexto, tables: TaxTables, rubrics: Optional[Dict[str, Any]], parcela: int,
                avos: int, media: float = 0.0, adiantamento_pago: float = 0.0) -> Dict[str, Any]:
    """
    parcela 1: adiantamento de 50%, sem descontos (só FGTS).
    parcela 2: 13º integral menos o adiantamento, com INSS e IRRF exclusivos do 13º.
    """
    f = _Folha(rubrics)
    avos = max(0, min(12, int(avos)))
    rem = ctx.remuneracao(tables)
    integral = rem * avos / 12.0
    media_prop = float(media or 0) * avos / 12.0
    inss = irrf = 0.0
    if parcela == 1:
        f.add("DECIMO_ADIANT", (integral + media_prop) / 2.0, f"{avos}/12", "decimo")
    else:
        f.add("DECIMO", integral, f"{avos}/12", "decimo")
        f.add("MEDIA_13", media_prop, f"{avos}/12", "decimo")
        f.add("DECIMO_ADIANT_DESC", adiantamento_pago, "", "decimo")
        inss, irrf = _encargos(f, ctx, tables, "decimo", "INSS_13", "IRRF_13", so_pensao_percentual=True)
        if not adiantamento_pago:
            f.avisos.append("Nenhuma 1ª parcela registrada: a 2ª parcela saiu sem desconto de adiantamento.")
    fgts = r2(f.base("incide_fgts") * tables.fgts_aliquota)
    return f.resultado(ctx, parcela=parcela, avos=avos, inss=inss, irrf=irrf, fgts=fgts,
                       base_inss=f.base("incide_inss"), base_fgts=f.base("incide_fgts"))


def avos_decimo(admissao: Optional[date], ano: int, ate: Optional[date] = None,
                dias_inss: Optional[Callable[[date, date], int]] = None) -> int:
    """Avos de 13º: meses do ano com pelo menos 15 dias trabalhados."""
    limite = ate or date(ano, 12, 31)
    avos = 0
    for mes in range(1, 13):
        ini, fim = date(ano, mes, 1), date(ano, mes, calendar.monthrange(ano, mes)[1])
        a = max(ini, admissao) if admissao else ini
        b = min(fim, limite)
        dias = (b - a).days + 1 if b >= a else 0
        if dias and dias_inss:
            dias -= dias_inss(a, b)
        if dias >= 15:
            avos += 1
    return avos


# ── Férias ───────────────────────────────────────────────────────────────────
def direito_ferias(faltas: int) -> int:
    """Dias de férias conforme faltas injustificadas no período aquisitivo (CLT art. 130)."""
    if faltas <= 5:
        return 30
    if faltas <= 14:
        return 24
    if faltas <= 23:
        return 18
    if faltas <= 32:
        return 12
    return 0


def calc_ferias(ctx: Contexto, tables: TaxTables, rubrics: Optional[Dict[str, Any]], dias_gozo: int,
                dias_abono: int = 0, media: float = 0.0, dias_dobro: int = 0,
                adiantamento_13: float = 0.0) -> Dict[str, Any]:
    f = _Folha(rubrics)
    dia = (ctx.remuneracao(tables)) / 30.0
    media_dia = float(media or 0) / 30.0
    v_ferias = f.add("FERIAS", dia * dias_gozo, f"{dias_gozo}d", "ferias")
    v_media = f.add("MEDIA_FERIAS", media_dia * dias_gozo, f"{dias_gozo}d", "ferias")
    f.add("FERIAS_TERCO", (v_ferias + v_media) / 3.0, "1/3", "ferias")
    if dias_abono:
        v_abono = f.add("ABONO_PEC", (dia + media_dia) * dias_abono, f"{dias_abono}d", "ferias")
        f.add("ABONO_TERCO", v_abono / 3.0, "1/3", "ferias")
    if dias_dobro:
        f.add("FERIAS_DOBRO", (dia + media_dia) * dias_dobro * 4.0 / 3.0, f"{dias_dobro}d", "ferias")
        f.avisos.append(f"{dias_dobro} dia(s) gozados após o período concessivo: pagos em dobro (CLT art. 137).")
    inss, irrf = _encargos(f, ctx, tables, "ferias", "INSS", "IRRF", "INSS s/ Férias", "IRRF s/ Férias",
                           so_pensao_percentual=True)
    # Lei 4.749/65 art. 2º §2º: 1ª parcela do 13º paga com as férias, a pedido do empregado.
    # Sem INSS/IRRF (tributados na 2ª parcela); com FGTS.
    v_ad13 = f.add("DECIMO_ADIANT", adiantamento_13, "50%", "decimo")
    fgts = r2(f.base("incide_fgts") * tables.fgts_aliquota)
    return f.resultado(ctx, dias_gozo=dias_gozo, dias_abono=dias_abono, dias_dobro=dias_dobro,
                       adiantamento_13=v_ad13,
                       inss=inss, irrf=irrf, fgts=fgts,
                       base_inss=f.base("incide_inss"), base_fgts=f.base("incide_fgts"))


def _mais_anos(d: date, anos: int) -> date:
    try:
        return d.replace(year=d.year + anos)
    except ValueError:  # 29/02
        return d.replace(year=d.year + anos, day=28)


def _mais_meses(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def avos_ferias(inicio: date, ate: date) -> int:
    """Avos de férias proporcionais: meses completos desde o início do período + fração ≥ 15 dias."""
    if ate < inicio:
        return 0
    meses = 0
    while meses < 12 and _mais_meses(inicio, meses + 1) - timedelta(days=1) <= ate:
        meses += 1
    if meses < 12:
        resto = (ate - _mais_meses(inicio, meses)).days + 1
        if resto >= 15:
            meses += 1
    return min(meses, 12)


def periodos_aquisitivos(admissao: date, ate: date, gozados: Optional[Dict[str, float]] = None,
                         faltas: Optional[Dict[str, int]] = None,
                         dias_inss: Optional[Callable[[date, date], int]] = None,
                         alerta_dias: int = 60) -> List[Dict[str, Any]]:
    """
    Períodos aquisitivos desde a admissão até `ate`.
    gozados/faltas: por data de início do período (ISO) → dias já quitados / faltas injustificadas.
    dias_inss: (início, fim) → dias de benefício do INSS; mais de 180 dias no período = perda do
    direito (CLT art. 133, IV).
    """
    gozados, faltas = gozados or {}, faltas or {}
    out: List[Dict[str, Any]] = []
    i = 0
    while True:
        inicio = _mais_anos(admissao, i)
        if inicio > ate:
            break
        fim = _mais_anos(admissao, i + 1) - timedelta(days=1)
        limite = _mais_anos(fim, 1)  # fim do período concessivo
        completo = fim <= ate
        chave = inicio.isoformat()
        direito = direito_ferias(int(faltas.get(chave, 0)))
        perda_afast = bool(dias_inss and dias_inss(inicio, min(fim, ate)) > 180)
        if perda_afast:
            direito = 0
        usados = float(gozados.get(chave, 0))
        saldo = max(0.0, direito - usados) if completo else 0.0
        if perda_afast:
            status = "perda_afastamento"
        elif completo and direito == 0:
            status = "perda_faltas"
        elif not completo:
            status = "em_aquisicao"
        elif saldo <= 0:
            status = "quitado"
        elif ate > limite:
            status = "vencido_dobro"
        elif (limite - ate).days <= alerta_dias:
            status = "vence_em_breve"
        else:
            status = "a_gozar"
        out.append({
            "inicio": chave, "fim": fim.isoformat(), "limite_concessivo": limite.isoformat(),
            "completo": completo, "direito": direito, "gozados": usados, "saldo": saldo,
            "avos": 0 if perda_afast else (12 if completo else avos_ferias(inicio, ate)), "status": status,
        })
        i += 1
    return out


# ── Rescisão ─────────────────────────────────────────────────────────────────
def dias_aviso_previo(admissao: date, desligamento: date) -> int:
    """30 dias + 3 por ano completo de serviço, limitado a 90 (Lei 12.506/2011)."""
    anos = desligamento.year - admissao.year - (
        1 if (desligamento.month, desligamento.day) < (admissao.month, admissao.day) else 0)
    return min(90, 30 + 3 * max(0, anos))


def planejar_rescisao(admissao: date, desligamento: date, tipo: str, aviso_modo: str = "indenizado",
                      gozados: Optional[Dict[str, float]] = None, faltas: Optional[Dict[str, int]] = None,
                      dias_inss: Optional[Callable[[date, date], int]] = None,
                      aviso_indenizado_dias: Optional[int] = None,
                      aviso_total_dias: Optional[int] = None) -> Dict[str, Any]:
    """Transforma datas e tipo de rescisão em quantidades (dias e avos) de cada verba.
    aviso_indenizado_dias / aviso_total_dias: vêm do aviso prévio registrado (ex.: 30 dias
    trabalhados + proporcional indenizado), em vez de serem deduzidos do modo do aviso."""
    regra = TIPOS_RESCISAO[tipo]
    aviso_total = aviso_total_dias if aviso_total_dias is not None else dias_aviso_previo(admissao, desligamento)
    if aviso_indenizado_dias is not None:
        aviso_ind = max(0, int(aviso_indenizado_dias))
    else:
        aviso_ind = int(round(aviso_total * regra["aviso"])) if aviso_modo == "indenizado" else 0
    projetada = desligamento + timedelta(days=aviso_ind)  # o aviso indenizado conta como tempo de serviço

    ultimo = calendar.monthrange(desligamento.year, desligamento.month)[1]
    primeiro = date(desligamento.year, desligamento.month, 1)
    inicio_saldo = max(primeiro, admissao)
    saldo_dias = 30 if (inicio_saldo == primeiro and desligamento.day == ultimo) \
        else min(30, (desligamento - inicio_saldo).days + 1)

    avos13 = avos13_ind = 0
    if regra["decimo"]:
        avos13 = avos_decimo(admissao, desligamento.year, desligamento, dias_inss)
        if aviso_ind:
            if projetada.year == desligamento.year:
                avos13_ind = max(0, avos_decimo(admissao, desligamento.year, projetada, dias_inss) - avos13)
            else:  # projeção vira o ano: o restante do ano corrente + os meses do ano seguinte
                avos13_ind = (avos_decimo(admissao, desligamento.year, None, dias_inss) - avos13
                              + avos_decimo(admissao, projetada.year, projetada))

    vencidas = dobro = avos_prop = 0.0
    for p in periodos_aquisitivos(admissao, projetada, gozados, faltas, dias_inss):
        if p["completo"]:
            vencidas += p["saldo"]
            if p["saldo"] and desligamento > date.fromisoformat(p["limite_concessivo"]):
                dobro += p["saldo"]
        elif regra["ferias_prop"]:
            avos_prop = p["avos"]

    return {
        "aviso_dias_total": aviso_total, "aviso_indenizado_dias": aviso_ind,
        "aviso_desconto_dias": 30 if (tipo == "pedido_demissao" and aviso_modo == "nao_cumprido") else 0,
        "data_projetada": projetada.isoformat(), "saldo_dias": saldo_dias,
        "avos_13": avos13, "avos_13_indenizado": avos13_ind,
        "ferias_vencidas_dias": vencidas, "ferias_dobro_dias": dobro, "avos_ferias": int(avos_prop),
        "multa_pct": regra["multa"],
    }


def calc_rescisao(ctx: Contexto, tables: TaxTables, rubrics: Optional[Dict[str, Any]], plano: Dict[str, Any],
                  media_13: float = 0.0, media_ferias: float = 0.0, media_aviso: float = 0.0,
                  adiantamento_13: float = 0.0, saldo_fgts: float = 0.0,
                  outros_descontos: float = 0.0) -> Dict[str, Any]:
    f = _Folha(rubrics)
    insal, peric, grau, _ = pe.adicionais_fixos(ctx.salario, ctx.insalubridade_grau, ctx.periculosidade, tables)
    rem = ctx.salario + insal + peric + ctx.ats
    dia = rem / 30.0

    # Grupo mensal: saldo de salário, adicionais e aviso prévio
    sd = plano["saldo_dias"]
    f.add("SALDO_SALARIO", ctx.salario / 30.0 * sd, f"{sd}d")
    f.add("ATS", ctx.ats / 30.0 * sd, ctx.ats_ref)
    f.add("INSALUBRIDADE", insal / 30.0 * sd, f"{int(grau * 100)}% s/ mínimo")
    f.add("PERICULOSIDADE", peric / 30.0 * sd, "30%")
    ai = plano["aviso_indenizado_dias"]
    f.add("AVISO_IND", (rem + media_aviso) / 30.0 * ai, f"{ai}d")

    # Indenização adicional da data-base (Lei 7.238/84 art. 9º): 1 salário mensal com os adicionais
    # mensais (Súmula 242 TST), quando a dispensa projetada cai nos 30 dias anteriores à data-base.
    if plano.get("indenizacao_data_base"):
        f.add("INDENIZ_DATA_BASE", rem, f"data-base {plano['indenizacao_data_base']}")

    # Grupo 13º
    a13, a13i = plano["avos_13"], plano["avos_13_indenizado"]
    f.add("DECIMO_PROP", (rem + media_13) * a13 / 12.0, f"{a13}/12", "decimo")
    f.add("DECIMO_IND", (rem + media_13) * a13i / 12.0, f"{a13i}/12", "decimo")
    f.add("DECIMO_ADIANT_DESC", adiantamento_13, "", "decimo")

    # Grupo férias indenizadas (sem INSS, IRRF ou FGTS)
    dia_f = dia + media_ferias / 30.0
    v_venc = f.add("FERIAS_VENC", dia_f * plano["ferias_vencidas_dias"], f"{plano['ferias_vencidas_dias']:g}d", "ferias")
    v_prop = f.add("FERIAS_PROP", (rem + media_ferias) * plano["avos_ferias"] / 12.0, f"{plano['avos_ferias']}/12", "ferias")
    v_dobro = f.add("FERIAS_RESC_DOBRO", dia_f * plano["ferias_dobro_dias"], f"{plano['ferias_dobro_dias']:g}d", "ferias")
    f.add("FERIAS_RESC_TERCO", (v_venc + v_prop + v_dobro) / 3.0, "1/3", "ferias")

    # Descontos
    f.add("AVISO_DESC", ctx.salario / 30.0 * plano["aviso_desconto_dias"], f"{plano['aviso_desconto_dias']}d")
    f.add("ADIANTAMENTO", outros_descontos)
    inss_m, irrf_m = _encargos(f, ctx, tables, "mensal", "INSS", "IRRF")
    inss_13, irrf_13 = _encargos(f, ctx, tables, "decimo", "INSS_13", "IRRF_13", so_pensao_percentual=True)

    base_fgts = f.base("incide_fgts")
    fgts = r2(base_fgts * tables.fgts_aliquota)
    multa = r2((float(saldo_fgts or 0) + fgts) * plano["multa_pct"])
    if multa:
        f.add("MULTA_FGTS", multa, f"{int(plano['multa_pct'] * 100)}%",
              nome="Multa Rescisória do FGTS (recolhida em guia, não entra no líquido)")
    return f.resultado(ctx, plano=plano, inss=r2(inss_m + inss_13), irrf=r2(irrf_m + irrf_13),
                       fgts=fgts, base_fgts=base_fgts, multa_fgts=multa, saldo_fgts=r2(saldo_fgts or 0))


# ── Leitura do banco ─────────────────────────────────────────────────────────
_NAO_VARIAVEIS = ("0001", "0005", "0006", "0012", "0013", "0015", "0018", "0019")  # salário e adicionais fixos entram pela remuneração


def contexto_funcionario(conn, company_id: int, emp: Dict[str, Any], em: date) -> Contexto:
    pensoes = []
    for p in pe._rows(conn, "SELECT * FROM alimony_orders WHERE company_id=? AND employee_id=? AND ativo=1",
                      (company_id, emp["id"])):
        ini, fim = pe._parse_date(p.get("data_inicio")), pe._parse_date(p.get("data_fim"))
        if (ini is None or ini <= em) and (fim is None or fim >= em):
            pensoes.append(p)
    salario, _ = cct_regras.salario_mensal(emp)
    admissao = pe._parse_date(emp.get("admission_date"))
    cct = cct_regras.cct_do_funcionario(cct_regras.carregar_ccts(conn, company_id), emp, em)
    ats, ats_ref = 0.0, ""
    if cct and not emp.get("is_prolabore"):
        sm = load_tables(conn, company_id, em.strftime("%Y-%m")).salario_minimo
        ats, ats_ref = cct_regras.adicional_tempo_servico(cct, admissao, em, salario, sm)
    return Contexto(
        employee_id=emp["id"], nome=emp.get("name") or "", salario=salario,
        admissao=admissao, dependentes=int(emp.get("dependents") or 0),
        is_prolabore=bool(emp.get("is_prolabore")), insalubridade_grau=emp.get("insalubridade_grau") or "",
        periculosidade=bool(emp.get("periculosidade")), pensoes=pensoes,
        ats=pe.r2(ats), ats_ref=ats_ref, cct=cct, data_base_mes=cct_regras.mes_data_base(cct, emp),
    )


def dias_inss_fn(conn, company_id: int, employee_id: int) -> Callable[[date, date], int]:
    """Função (início, fim) → dias de afastamento pagos pelo INSS no intervalo."""
    afast = pe._rows(conn, "SELECT * FROM employee_absences WHERE company_id=? AND employee_id=?",
                     (company_id, employee_id))

    def conta(ini: date, fim: date) -> int:
        dias = set()
        for a in afast:
            a_ini = pe._parse_date(a.get("data_inicio"))
            if not a_ini or not (int(a.get("dias_inss") or 0) > 0 or a.get("tipo") in pe._TIPOS_INSS):
                continue
            ini_inss = a_ini + timedelta(days=int(a.get("dias_empresa") or 0))
            retorno = pe._parse_date(a.get("retorno_efetivo"))
            a_fim = (retorno - timedelta(days=1)) if retorno else (pe._parse_date(a.get("data_fim")) or fim)
            d = max(ini_inss, ini)
            while d <= min(a_fim, fim):
                dias.add(d)
                d += timedelta(days=1)
        return len(dias)
    return conta


def media_variaveis(conn, company_id: int, employee_id: int, comp_ini: str, comp_fim: str,
                    flag: str, divisor: int) -> float:
    """
    Média mensal das rubricas variáveis (horas extras, comissões, DSR...) pagas nas folhas
    mensais entre comp_ini e comp_fim. `flag`: incide_13 ou incide_ferias da rubrica.
    """
    if flag not in ("incide_13", "incide_ferias") or divisor <= 0 or comp_ini > comp_fim:
        return 0.0
    rows = pe._rows(conn, f"""
        SELECT l.codigo, l.valor
        FROM payroll_item_lines l
        JOIN payroll_runs pr ON pr.id = l.run_id
        JOIN payroll_rubrics r ON r.company_id = pr.company_id AND r.codigo = l.codigo
        WHERE pr.company_id=? AND l.employee_id=? AND l.tipo='provento' AND r.{flag}=1
          AND pr.competence>=? AND pr.competence<=? AND pr.status != 'cancelado'""",
        (company_id, employee_id, comp_ini, comp_fim))
    total = sum(float(r["valor"] or 0) for r in rows if str(r["codigo"]) not in _NAO_VARIAVEIS)
    return r2(total / divisor)


def meses_entre(comp_ini: str, comp_fim: str) -> int:
    a, b = comp_ini.split("-"), comp_fim.split("-")
    return max(0, (int(b[0]) - int(a[0])) * 12 + int(b[1]) - int(a[1]) + 1)


def ferias_registradas(conn, company_id: int, employee_id: int,
                       ignorar_id: Optional[int] = None) -> Tuple[Dict[str, float], Dict[str, int]]:
    """(dias já quitados, faltas informadas) por início de período aquisitivo."""
    gozados: Dict[str, float] = {}
    faltas: Dict[str, int] = {}
    for f in pe._rows(conn, """SELECT id, referencia, dias_gozo, dias_abono, params FROM payroll_special
                               WHERE company_id=? AND employee_id=? AND tipo='ferias' AND status != 'cancelado'""",
                      (company_id, employee_id)):
        if ignorar_id and f["id"] == ignorar_id:
            continue
        chave = str(f.get("referencia") or "")[:10]
        gozados[chave] = gozados.get(chave, 0.0) + float(f.get("dias_gozo") or 0) + float(f.get("dias_abono") or 0)
        try:
            faltas[chave] = max(faltas.get(chave, 0), int(json.loads(f.get("params") or "{}").get("faltas_periodo", 0)))
        except (ValueError, TypeError):
            pass
    return gozados, faltas


def saldo_fgts_estimado(conn, company_id: int, emp: Dict[str, Any], ate: date) -> Tuple[float, str]:
    """Saldo do FGTS para a multa: extrato do sistema, senão folhas processadas, senão estimativa."""
    eid = emp["id"]
    hist = pe._rows(conn, "SELECT saldo_acumulado FROM fgts_history WHERE company_id=? AND employee_id=? "
                          "ORDER BY competencia DESC, id DESC LIMIT 1", (company_id, eid))
    if hist and float(hist[0].get("saldo_acumulado") or 0) > 0:
        return r2(float(hist[0]["saldo_acumulado"])), "extrato FGTS do sistema"
    folhas = pe._rows(conn, """SELECT COALESCE(SUM(pi.fgts),0) AS t FROM payroll_items pi
                               JOIN payroll_runs pr ON pr.id=pi.run_id
                               WHERE pr.company_id=? AND pi.employee_id=? AND pr.status != 'cancelado'""",
                      (company_id, eid))
    esp = pe._rows(conn, """SELECT COALESCE(SUM(fgts),0) AS t FROM payroll_special
                            WHERE company_id=? AND employee_id=? AND tipo != 'rescisao' AND status != 'cancelado'""",
                   (company_id, eid))
    total = float((folhas[0]["t"] if folhas else 0) or 0) + float((esp[0]["t"] if esp else 0) or 0)
    if total > 0:
        return r2(total), "soma das folhas processadas no sistema"
    adm = pe._parse_date(emp.get("admission_date")) or ate
    meses = max(0, (ate.year - adm.year) * 12 + ate.month - adm.month)
    return r2(float(emp.get("salary") or 0) * 0.08 * meses), "estimativa (salário atual × 8% × meses)"
