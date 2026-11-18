"""
Escalas de trabalho: horário fixo semanal e escalas cíclicas (12x36, 24x48, 24x72, 5x1, 6x1...).

Regras usadas:
  * Escala cíclica = sequência de dias de trabalho (T) e folga (F) que se repete a partir de uma data
    de início (dia 1 do ciclo = T). Cada funcionário pode ter a sua data de início (turmas A/B).
  * Um plantão que vira a meia-noite pertence ao dia em que começou.
  * Período noturno urbano: 22h às 5h, hora noturna reduzida de 52min30s (CLT art. 73, §§ 1º e 2º).
  * Prorrogação: quando o plantão cumpre todo o período noturno, as horas seguidas após as 5h também
    são noturnas (Súmula 60, II, do TST; para 12x36, OJ 388 da SDI-1).
  * 12x36 (CLT art. 59-A, parágrafo único): a remuneração mensal já abrange o descanso semanal e os
    feriados trabalhados, que ficam compensados (configurável por escala).
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

PRESETS: Dict[str, Dict[str, Any]] = {
    "12x36": {"ciclo": "T,F", "descricao": "12 horas de trabalho por 36 de descanso", "horas_semanais": 42},
    "24x48": {"ciclo": "T,F,F", "descricao": "24 horas de trabalho por 48 de descanso", "horas_semanais": 56},
    "24x72": {"ciclo": "T,F,F,F", "descricao": "24 horas de trabalho por 72 de descanso", "horas_semanais": 42},
    "5x1": {"ciclo": "T,T,T,T,T,F", "descricao": "5 dias de trabalho e 1 de folga", "horas_semanais": 44},
    "6x1": {"ciclo": "T,T,T,T,T,T,F", "descricao": "6 dias de trabalho e 1 de folga", "horas_semanais": 44},
    "6x2": {"ciclo": "T,T,T,T,T,T,F,F", "descricao": "6 dias de trabalho e 2 de folga", "horas_semanais": 44},
}

NOITE_INICIO = 22 * 60
NOITE_FIM = 5 * 60
HORA_NOTURNA_MIN = 52.5


def _parse_date(v: Any) -> Optional[date]:
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _min(hhmm: str) -> Optional[int]:
    try:
        h, m = str(hhmm or "").strip()[:5].split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def parse_ciclo(ciclo: str) -> List[bool]:
    """'T,F' ou '12x36' -> [True, False]. Aceita também 'TF' sem vírgulas."""
    c = (ciclo or "").strip().upper()
    if c.lower() in PRESETS:
        c = PRESETS[c.lower()]["ciclo"]
    marcas = [x for x in c.replace(",", "").replace(" ", "") if x in "TF"]
    if not marcas or "T" not in marcas:
        raise ValueError("Ciclo inválido: use T (trabalho) e F (folga), por exemplo T,F para 12x36.")
    return [m == "T" for m in marcas]


def _eh_noturno(minuto_do_dia: int) -> bool:
    return minuto_do_dia >= NOITE_INICIO or minuto_do_dia < NOITE_FIM


def horas_turno(entrada: str, saida: str, intervalo_min: int = 0, intervalo_inicio: str = "",
                prorrogacao: bool = True) -> Dict[str, float]:
    """Horas de um plantão: trabalhadas, noturnas no relógio e noturnas reduzidas (para o adicional).

    Sem horário de intervalo informado, o intervalo é descontado no meio do plantão.
    """
    ini, fim = _min(entrada), _min(saida)
    if ini is None or fim is None:
        return {"horas": 0.0, "noturnas_relogio": 0.0, "noturnas": 0.0, "prorrogadas": 0.0}
    dur = (fim - ini) % 1440 or 1440
    intervalo_min = max(0, int(intervalo_min or 0))
    i_ini = _min(intervalo_inicio)
    if i_ini is not None:
        off = (i_ini - ini) % 1440
    else:
        off = max(0, (dur - intervalo_min) // 2)
    pausa = set(range(off, min(dur, off + intervalo_min))) if intervalo_min else set()

    noturno, prorrog = 0, 0
    # A jornada cobre todo o período 22h-5h? (minutos contados desde a entrada)
    fim_noite = (NOITE_INICIO - ini) % 1440 + 420
    cobre_noite = fim_noite <= dur
    trabalhado = 0
    for k in range(dur):
        if k in pausa:
            continue
        trabalhado += 1
        m = (ini + k) % 1440
        if _eh_noturno(m):
            noturno += 1
        elif prorrogacao and cobre_noite and k >= fim_noite:
            prorrog += 1
    relogio = noturno + prorrog
    return {
        "horas": round(trabalhado / 60, 2),
        "noturnas_relogio": round(relogio / 60, 2),
        "noturnas": round(relogio / HORA_NOTURNA_MIN, 2),
        "prorrogadas": round(prorrog / 60, 2),
    }


def _dias_semana(s: Dict[str, Any]) -> set:
    out = set()
    for x in str(s.get("dias_trabalho") or "1,2,3,4,5").split(","):
        x = x.strip()
        if x.isdigit():
            out.add(int(x) % 7)  # 1=segunda ... 6=sábado, 0 ou 7=domingo
    return out


def trabalha_no_dia(s: Dict[str, Any], dia: date, inicio_func: Any = None) -> bool:
    """O funcionário está escalado neste dia?"""
    if (s.get("tipo") or "fixo") != "ciclica":
        return (dia.isoweekday() % 7) in _dias_semana(s)
    ciclo = parse_ciclo(s.get("ciclo") or "")
    ref = _parse_date(inicio_func) or _parse_date(s.get("data_inicio_ciclo"))
    if not ref:
        raise ValueError("Escala cíclica sem data de início do ciclo.")
    return ciclo[(dia - ref).days % len(ciclo)]


def turno_do_dia(s: Dict[str, Any]) -> Dict[str, float]:
    entrada = s.get("hora_entrada") or "08:00"
    saida = s.get("hora_saida") or "17:00"
    return horas_turno(entrada, saida, int(s.get("intervalo_min") or 0), s.get("intervalo_inicio") or "",
                       bool(s.get("prorrogacao_noturna", 1)))


def calendario(s: Dict[str, Any], competencia: str, feriados: Optional[set] = None,
               inicio_func: Any = None) -> Dict[str, Any]:
    """Dias do mês com trabalho/folga, horas e horas noturnas, e o resumo do mês."""
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    d = date(ano, mes, 1)
    feriados = feriados or set()
    turno = turno_do_dia(s)
    dias: List[Dict[str, Any]] = []
    tot = {"plantoes": 0, "horas": 0.0, "noturnas": 0.0, "noturnas_relogio": 0.0,
           "feriados_trabalhados": 0, "domingos_trabalhados": 0, "folgas": 0}
    while d.month == mes:
        t = trabalha_no_dia(s, d, inicio_func)
        fer = d in feriados
        dias.append({"data": d.isoformat(), "dia_semana": d.isoweekday() % 7, "trabalha": t, "feriado": fer,
                     "entrada": s.get("hora_entrada") if t else "", "saida": s.get("hora_saida") if t else "",
                     "horas": turno["horas"] if t else 0.0, "noturnas": turno["noturnas"] if t else 0.0})
        if t:
            tot["plantoes"] += 1
            tot["horas"] += turno["horas"]
            tot["noturnas"] += turno["noturnas"]
            tot["noturnas_relogio"] += turno["noturnas_relogio"]
            tot["feriados_trabalhados"] += int(fer)
            tot["domingos_trabalhados"] += int(d.isoweekday() == 7)
        else:
            tot["folgas"] += 1
        d += timedelta(days=1)
    for k in ("horas", "noturnas", "noturnas_relogio"):
        tot[k] = round(tot[k], 2)
    return {"competencia": competencia, "turno": turno, "dias": dias, "resumo": tot}


def escala_do_funcionario(conn, company_id: int, emp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sid = emp.get("work_schedule_id")
    if not sid:
        return None
    r = conn.execute("SELECT * FROM work_schedules WHERE id=? AND company_id=?", (sid, company_id)).fetchone()
    return dict(r) if r else None


def jornada_prevista(conn, company_id: int, employee_id: int, dia: Any) -> Tuple[float, Optional[Dict[str, Any]], bool]:
    """(horas previstas no dia, escala, é dia de escala). Sem escala vinculada mantém o comportamento
    antigo: primeiro horário cadastrado da empresa, ou 8h."""
    d = _parse_date(dia)
    emp = conn.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (employee_id, company_id)).fetchone()
    s = escala_do_funcionario(conn, company_id, dict(emp)) if emp else None
    if s and d:
        try:
            t = trabalha_no_dia(s, d, dict(emp).get("escala_inicio"))
        except ValueError:
            t = True
        return (turno_do_dia(s)["horas"] if t else 0.0), s, t
    r = conn.execute("SELECT horas_diarias FROM work_schedules WHERE company_id=? LIMIT 1", (company_id,)).fetchone()
    return (float(r["horas_diarias"]) if r else 8.0), None, True
