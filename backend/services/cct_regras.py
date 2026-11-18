"""Regras da convenção coletiva (CCT) e das categorias de remuneração aplicadas na folha.

* Convenção do funcionário: a escolhida no cadastro; sem escolha, a única vigente da empresa.
* Percentuais de hora extra e adicional noturno da convenção (CLT art. 59 §1º e art. 73 são o mínimo).
* Adicional por tempo de serviço (anuênio, biênio, triênio, quinquênio) — só existe por convenção.
* Indenização adicional da data-base (Lei 7.238/1984, art. 9º; Súmulas 182, 242 e 314 do TST).
* Média de variáveis por N meses quando a convenção define (férias e rescisão).
* Salário mensal equivalente por unidade (eSocial undSalFixo): horista, diarista, semanal, quinzenal,
  tarefa/variável, e professor (CLT art. 320: aulas semanais × 4,5 semanas + DSR de 1/6, Súmula 351 TST).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

ATS_PERIODOS = {"anuenio": 1, "bienio": 2, "trienio": 3, "quinquenio": 5}
ATS_NOMES = {"anuenio": "Anuênio", "bienio": "Biênio", "trienio": "Triênio", "quinquenio": "Quinquênio"}

# eSocial undSalFixo: 1 hora, 2 dia, 3 semana, 4 quinzena, 5 mês, 6 tarefa, 7 não aplicável (só variável)
TIPOS_SALARIO = {"1": "horista", "2": "diarista", "3": "semanal", "4": "quinzenal", "5": "mensalista",
                 "6": "tarefa", "7": "variavel"}

SEMANAS_PROFESSOR = 4.5           # CLT art. 320 §1º


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _d(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


# ── Convenção do funcionário ──────────────────────────────────────────────────

def vigente_em(cct: Dict[str, Any], em: date) -> bool:
    ini, fim = _d(cct.get("data_inicio")), _d(cct.get("data_fim"))
    return (ini is None or ini <= em) and (fim is None or fim >= em)


def carregar_ccts(conn, company_id: int) -> List[Dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM cct_convencoes WHERE company_id=? ORDER BY data_inicio DESC", (company_id,)).fetchall()]
    except Exception:
        return []


def cct_do_funcionario(ccts: List[Dict[str, Any]], emp: Dict[str, Any], em: date) -> Optional[Dict[str, Any]]:
    """A convenção escolhida no cadastro (mesmo vencida, para não mudar o cálculo de surpresa);
    sem escolha, a única convenção vigente da empresa."""
    escolhida = emp.get("cct_id")
    if escolhida:
        for c in ccts:
            if str(c["id"]) == str(escolhida):
                return c
        return None
    vigentes = [c for c in ccts if vigente_em(c, em)]
    return vigentes[0] if len(vigentes) == 1 else None


def percentuais(cct: Optional[Dict[str, Any]]) -> Tuple[float, float, float]:
    """(hora extra em dia útil, hora extra em domingo/feriado, adicional noturno), em %, nunca abaixo da lei."""
    if not cct:
        return 50.0, 100.0, 20.0
    he50 = max(50.0, _f(cct.get("adicional_hora_extra_pct")) or 50.0)
    he100 = max(he50, _f(cct.get("he_100_pct")) or 100.0)
    noturno = max(20.0, _f(cct.get("adicional_noturno_pct")) or 20.0)
    return he50, he100, noturno


# ── Salário mensal equivalente ────────────────────────────────────────────────

def salario_mensal(emp: Dict[str, Any]) -> Tuple[float, str]:
    """(salário mensal equivalente, descrição) a partir do salário cadastrado e da unidade de pagamento.
    O valor mensal inclui o repouso semanal remunerado."""
    valor = _f(emp.get("salary"))
    horas_semana = _f(emp.get("horas_semana")) or 44.0
    if (emp.get("categoria_especial") or "") == "professor":
        aulas = _f(emp.get("aulas_semanais"))
        base = valor * aulas * SEMANAS_PROFESSOR
        return base * 7 / 6, f"{aulas:g} aulas/semana × 4,5 × hora-aula + DSR 1/6"
    tipo = TIPOS_SALARIO.get(str(emp.get("tipo_salario") or "5"), "mensalista")
    if tipo == "horista":
        horas_mes = round(horas_semana * 5, 2)
        return valor * horas_mes, f"{horas_mes:g}h × valor-hora (com DSR)"
    if tipo == "diarista":
        return valor * 30, "30 dias × valor-dia (com DSR)"
    if tipo == "semanal":
        return valor * 30 / 7, "valor semanal × 30/7"
    if tipo == "quinzenal":
        return valor * 2, "2 quinzenas"
    if tipo == "variavel":
        return 0.0, "remuneração só variável (comissões)"
    return valor, "mensal"


# ── Adicional por tempo de serviço ────────────────────────────────────────────

def anos_completos(admissao: Optional[date], em: date) -> int:
    if not admissao or em < admissao:
        return 0
    anos = em.year - admissao.year
    if (em.month, em.day) < (admissao.month, admissao.day):
        anos -= 1
    return max(0, anos)


def adicional_tempo_servico(cct: Optional[Dict[str, Any]], admissao: Optional[date], em: date,
                            salario: float, salario_minimo: float) -> Tuple[float, str]:
    """(valor mensal cheio, referência). Zero quando a convenção não prevê ou o período não fechou."""
    if not cct:
        return 0.0, ""
    tipo = (cct.get("ats_tipo") or "").lower()
    pct = _f(cct.get("ats_pct"))
    if tipo not in ATS_PERIODOS or pct <= 0:
        return 0.0, ""
    periodos = anos_completos(admissao, em) // ATS_PERIODOS[tipo]
    maximo = int(_f(cct.get("ats_max_periodos")))
    if maximo > 0:
        periodos = min(periodos, maximo)
    if periodos <= 0:
        return 0.0, ""
    base_tipo = (cct.get("ats_base") or "salario").lower()
    base = {"piso": _f(cct.get("piso_salarial")) or salario, "minimo": salario_minimo}.get(base_tipo, salario)
    return base * pct / 100.0 * periodos, f"{periodos} {ATS_NOMES[tipo].lower()}(s) × {pct:g}%"


# ── Indenização adicional da data-base ────────────────────────────────────────

def mes_data_base(cct: Optional[Dict[str, Any]], emp: Dict[str, Any]) -> int:
    mes = int(_f((cct or {}).get("data_base_mes"))) or int(_f(emp.get("data_base_mes")))
    return mes if 1 <= mes <= 12 else 0


def indenizacao_data_base(mes: int, data_projetada: date) -> Optional[date]:
    """Data-base que gera a indenização (Lei 7.238/84 art. 9º): a dispensa, projetada com o aviso
    indenizado (Súmula 182), cai nos 30 dias que antecedem a data-base. Se a projeção alcança a própria
    data-base, o empregado recebe o reajuste e não a indenização (Súmula 314)."""
    if not mes:
        return None
    for ano in (data_projetada.year, data_projetada.year + 1):
        db = date(ano, mes, 1)
        if db - timedelta(days=30) <= data_projetada <= db - timedelta(days=1):
            return db
    return None


# ── Médias pela convenção ─────────────────────────────────────────────────────

def janela_media(cct: Optional[Dict[str, Any]], comp_ini: str, comp_fim: str, divisor: int) -> Tuple[str, int]:
    """Quando a convenção manda tirar a média dos últimos N meses, reduz a janela e o divisor."""
    n = int(_f((cct or {}).get("media_meses")))
    if n <= 0 or not comp_fim:
        return comp_ini, divisor
    ano, mes = int(comp_fim[:4]), int(comp_fim[5:7])
    total = ano * 12 + (mes - 1) - (n - 1)
    ini_n = f"{total // 12:04d}-{total % 12 + 1:02d}"
    return max(comp_ini, ini_n) if comp_ini else ini_n, n
