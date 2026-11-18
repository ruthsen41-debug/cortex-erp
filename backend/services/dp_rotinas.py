"""Bloco 5 da paridade DP — regras puras de automação e utilitários:
vencimentos da folha e das guias e agenda das rotinas automáticas.

- Salário: até o 5º dia útil do mês seguinte (CLT art. 459 §1º). Para essa contagem o sábado é
  dia útil e domingo e feriado não são (entendimento da fiscalização do trabalho).
- FGTS Digital e DCTFWeb (INSS e IRRF da folha): dia 20 do mês seguinte; se não for dia útil,
  antecipa para o dia útil anterior (Lei 8.036/90 art. 15 e Lei 8.212/91 art. 30, I, "b").
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

TIPOS = {
    "calcular_folha": "Calcular a folha mensal",
    "enviar_holerites": "Enviar holerites por e-mail",
    "gerar_financeiro": "Lançar a folha e as guias no contas a pagar",
}
COMPETENCIAS = {"atual": "Mês da execução", "anterior": "Mês anterior à execução"}


def mes_seguinte(comp: str) -> date:
    a, m = int(comp[:4]), int(comp[5:7])
    return date(a + (m == 12), 1 if m == 12 else m + 1, 1)


def quinto_dia_util(comp: str, feriados: Iterable[date] = ()) -> date:
    """5º dia útil do mês seguinte à competência, com o sábado contando como útil."""
    feriados, d, n = set(feriados), mes_seguinte(comp), 0
    while True:
        if d.weekday() != 6 and d not in feriados:
            n += 1
            if n == 5:
                return d
        d += timedelta(days=1)


def dia20_antecipado(comp: str, feriados: Iterable[date] = ()) -> date:
    """Dia 20 do mês seguinte, antecipado para o dia útil anterior (seg–sex sem feriado)."""
    feriados = set(feriados)
    d = mes_seguinte(comp).replace(day=20)
    while d.weekday() >= 5 or d in feriados:
        d -= timedelta(days=1)
    return d


def competencia_alvo(quando: date, regra: str) -> str:
    if regra == "anterior":
        primeiro = quando.replace(day=1) - timedelta(days=1)
        return primeiro.strftime("%Y-%m")
    return quando.strftime("%Y-%m")


def proxima_execucao(dia: int, hora: str, depois_de: datetime) -> datetime:
    """Próxima data/hora (dia do mês e HH:MM) estritamente depois de `depois_de`.
    Dia maior que os dias do mês cai no último dia (ex.: 31 em fevereiro → 28/29)."""
    hh, mm = (int(x) for x in (hora or "08:00").split(":")[:2])
    ano, mes = depois_de.year, depois_de.month
    for _ in range(14):
        ultimo = calendar.monthrange(ano, mes)[1]
        alvo = datetime(ano, mes, min(max(1, dia), ultimo), hh, mm)
        if alvo > depois_de:
            return alvo
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    raise ValueError("Não foi possível calcular a próxima execução.")


def validar_rotina(d: dict) -> dict:
    tipo = str(d.get("tipo") or "")
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de rotina inválido. Use: {', '.join(TIPOS)}.")
    try:
        dia = int(d.get("dia"))
    except (TypeError, ValueError):
        raise ValueError("Dia do mês: informe um número de 1 a 31.")
    if not 1 <= dia <= 31:
        raise ValueError("Dia do mês: informe um número de 1 a 31.")
    hora = str(d.get("hora") or "08:00")
    try:
        hh, mm = (int(x) for x in hora.split(":")[:2])
        assert 0 <= hh <= 23 and 0 <= mm <= 59
    except (ValueError, AssertionError):
        raise ValueError("Hora no formato HH:MM.")
    comp = str(d.get("competencia") or ("anterior" if tipo != "calcular_folha" else "atual"))
    if comp not in COMPETENCIAS:
        raise ValueError("Competência: atual ou anterior.")
    return {"tipo": tipo, "dia": dia, "hora": f"{hh:02d}:{mm:02d}", "competencia": comp,
            "ativo": 0 if d.get("ativo") in (False, 0, "0", "false") else 1}


def mesmo_mes(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a and b and str(a)[:7] == str(b)[:7])
