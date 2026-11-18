"""Parâmetros da folha por empresa (equivalente ao "Controle > Parâmetros" dos sistemas de folha).

Guardados como JSON em `payroll_parametros` (uma linha por empresa). Valores ausentes caem no padrão,
então empresas antigas continuam calculando exatamente como antes.
"""
from __future__ import annotations

import json
from typing import Any, Dict

PADRAO: Dict[str, Any] = {
    # Proporcionalidade do salário em admissão/afastamento/férias no mês:
    # "30" = mês comercial (sempre 30 dias) · "mes" = dias corridos do mês (28 a 31)
    "base_dias": "30",
    # Adiantamento salarial (quinzenal)
    "adiantamento_percentual": 40.0,   # sugerido ao lançar
    "adiantamento_limite": 40.0,       # máximo aceito
    "adiantamento_dia_pagamento": 20,
    # Desconta o DSR da semana em que houve falta injustificada (Lei 605/49 art. 6º)
    "descontar_dsr_faltas": True,
    # Férias: avisar quando faltarem X dias para o fim do período concessivo
    "ferias_alerta_dias": 60,
    # Texto impresso no rodapé de todos os holerites
    "mensagem_recibo": "",
    # Empréstimo consignado (Lei 10.820/2003): % máximo da remuneração disponível
    # (bruto − INSS − IRRF − pensão). Confira o percentual vigente da lei.
    "consignado_margem_pct": 35.0,
}

DESCRICOES: Dict[str, str] = {
    "base_dias": "Cálculo proporcional do salário: sempre 30 dias ou dias do mês",
    "adiantamento_percentual": "Percentual sugerido do adiantamento salarial (%)",
    "adiantamento_limite": "Percentual máximo permitido para o adiantamento (%)",
    "adiantamento_dia_pagamento": "Dia de pagamento do adiantamento",
    "descontar_dsr_faltas": "Descontar o DSR da semana com falta injustificada",
    "ferias_alerta_dias": "Avisar férias a vencer com quantos dias de antecedência",
    "mensagem_recibo": "Mensagem impressa nos holerites",
    "consignado_margem_pct": "Margem do empréstimo consignado (% da remuneração disponível)",
}


def carregar(conn, company_id: int) -> Dict[str, Any]:
    """Parâmetros da empresa já completados com os padrões."""
    row = conn.execute("SELECT dados FROM payroll_parametros WHERE company_id=?", (company_id,)).fetchone()
    salvos: Dict[str, Any] = {}
    if row and row["dados"]:
        try:
            salvos = json.loads(row["dados"]) or {}
        except (TypeError, ValueError):
            salvos = {}
    return {**PADRAO, **{k: v for k, v in salvos.items() if k in PADRAO}}


def validar(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza e valida; levanta ValueError com mensagem para o usuário."""
    v: Dict[str, Any] = {}
    if "base_dias" in dados:
        if str(dados["base_dias"]) not in ("30", "mes"):
            raise ValueError("Cálculo proporcional deve ser 'sempre 30 dias' ou 'dias do mês'.")
        v["base_dias"] = str(dados["base_dias"])
    for campo in ("adiantamento_percentual", "adiantamento_limite"):
        if campo in dados:
            try:
                n = float(dados[campo])
            except (TypeError, ValueError):
                raise ValueError(f"{DESCRICOES[campo]}: informe um número.")
            if not 0 < n <= 100:
                raise ValueError(f"{DESCRICOES[campo]}: deve ficar entre 0 e 100.")
            v[campo] = round(n, 2)
    if "adiantamento_dia_pagamento" in dados:
        try:
            dia = int(dados["adiantamento_dia_pagamento"])
        except (TypeError, ValueError):
            raise ValueError("Dia de pagamento do adiantamento: informe um número.")
        if not 1 <= dia <= 28:
            raise ValueError("Dia de pagamento do adiantamento deve ficar entre 1 e 28.")
        v["adiantamento_dia_pagamento"] = dia
    if "descontar_dsr_faltas" in dados:
        v["descontar_dsr_faltas"] = dados["descontar_dsr_faltas"] in (True, 1, "1", "true", "on", "sim")
    if "ferias_alerta_dias" in dados:
        try:
            dias = int(dados["ferias_alerta_dias"])
        except (TypeError, ValueError):
            raise ValueError("Antecedência do aviso de férias: informe um número de dias.")
        if not 0 <= dias <= 365:
            raise ValueError("Antecedência do aviso de férias deve ficar entre 0 e 365 dias.")
        v["ferias_alerta_dias"] = dias
    if "consignado_margem_pct" in dados:
        try:
            n = float(dados["consignado_margem_pct"])
        except (TypeError, ValueError):
            raise ValueError(f"{DESCRICOES['consignado_margem_pct']}: informe um número.")
        if not 0 < n <= 100:
            raise ValueError(f"{DESCRICOES['consignado_margem_pct']}: deve ficar entre 0 e 100.")
        v["consignado_margem_pct"] = round(n, 2)
    if "mensagem_recibo" in dados:
        v["mensagem_recibo"] = str(dados["mensagem_recibo"] or "").strip()[:300]
    return v


def salvar(conn, company_id: int, dados: Dict[str, Any], usuario: str = "") -> Dict[str, Any]:
    novos = {**carregar(conn, company_id), **validar(dados)}
    if novos["adiantamento_percentual"] > novos["adiantamento_limite"]:
        raise ValueError("O percentual sugerido do adiantamento não pode passar do limite máximo.")
    texto = json.dumps(novos, ensure_ascii=False)
    agora = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    if conn.execute("SELECT 1 FROM payroll_parametros WHERE company_id=?", (company_id,)).fetchone():
        conn.execute("UPDATE payroll_parametros SET dados=?, atualizado_em=?, atualizado_por=? WHERE company_id=?",
                     (texto, agora, usuario, company_id))
    else:
        conn.execute("INSERT INTO payroll_parametros (company_id, dados, atualizado_em, atualizado_por) VALUES (?,?,?,?)",
                     (company_id, texto, agora, usuario))
    return novos
