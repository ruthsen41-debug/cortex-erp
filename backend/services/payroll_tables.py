"""
Tabelas legais da folha (INSS, IRRF, FGTS, salário mínimo, salário-família).

Ordem de busca para uma competência "AAAA-MM":
  1. Tabela cadastrada pela empresa na aba "Tabelas Fiscais" (tax_tables) para o
     MESMO ano da competência;
  2. Tabela embutida abaixo, na vigência mais recente que não ultrapasse a competência.

Para atualizar sem redeploy, basta cadastrar a tabela do ano na aba "Tabelas Fiscais".
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

INF = float("inf")

# Cada entrada vale a partir da competência indicada na chave ("AAAA-MM").
#   inss: [(limite_da_faixa, aliquota)]  — a última faixa define o teto
#   irrf: [(limite_da_base, aliquota, parcela_a_deduzir)]
_BUILTIN: Dict[str, Dict[str, Any]] = {
    "2024-02": {
        "salario_minimo": 1412.00,
        "inss": [(1412.00, 0.075), (2666.68, 0.09), (4000.03, 0.12), (7786.02, 0.14)],
        "irrf": [(2259.20, 0.0, 0.0), (2826.65, 0.075, 169.44), (3751.05, 0.15, 381.44),
                 (4664.68, 0.225, 662.77), (INF, 0.275, 896.00)],
        "irrf_dependente": 189.59,
        "irrf_simplificado": 564.80,
        "salario_familia": (1819.26, 62.04),
    },
    "2025-01": {
        "salario_minimo": 1518.00,
        "inss": [(1518.00, 0.075), (2793.88, 0.09), (4190.83, 0.12), (8157.41, 0.14)],
        "salario_familia": (1906.04, 65.00),
    },
    "2025-05": {
        "irrf": [(2428.80, 0.0, 0.0), (2826.65, 0.075, 182.16), (3751.05, 0.15, 394.16),
                 (4664.68, 0.225, 675.49), (INF, 0.275, 908.73)],
        "irrf_simplificado": 607.20,
    },
    # ATENÇÃO: valores de 2026 devem ser conferidos com a portaria/lei vigente
    # antes de fechar folha real. A redução do IRRF segue a Lei 15.270/2025.
    "2026-01": {
        "salario_minimo": 1621.00,
        "inss": [(1621.00, 0.075), (2902.84, 0.09), (4354.27, 0.12), (8475.55, 0.14)],
        "salario_familia": (1980.38, 67.54),
        # (limite_isencao, limite_reducao, constante, fator, reducao_maxima)
        "irrf_reducao": (5000.00, 7350.00, 978.62, 0.133145, 312.89),
    },
}

_FGTS_DEFAULT = 0.08


@dataclass
class TaxTables:
    competencia: str
    salario_minimo: float
    inss: List[Tuple[float, float]]
    irrf: List[Tuple[float, float, float]]
    irrf_dependente: float
    irrf_simplificado: float
    fgts_aliquota: float = _FGTS_DEFAULT
    salario_familia: Tuple[float, float] = (0.0, 0.0)
    irrf_reducao: Optional[Tuple[float, float, float, float, float]] = None
    origem: Dict[str, str] = field(default_factory=dict)

    @property
    def inss_teto(self) -> float:
        return self.inss[-1][0] if self.inss else 0.0


def builtin_tables(competencia: str) -> TaxTables:
    """Monta as tabelas embutidas vigentes na competência (acumulando vigências)."""
    merged: Dict[str, Any] = {}
    origem: Dict[str, str] = {}
    keys = sorted(_BUILTIN)
    aplicaveis = [k for k in keys if k <= competencia] or keys[:1]
    for k in aplicaveis:
        for campo, valor in _BUILTIN[k].items():
            merged[campo] = valor
            origem[campo] = f"embutida {k}"
    return TaxTables(
        competencia=competencia,
        salario_minimo=merged["salario_minimo"],
        inss=list(merged["inss"]),
        irrf=list(merged["irrf"]),
        irrf_dependente=merged["irrf_dependente"],
        irrf_simplificado=merged["irrf_simplificado"],
        salario_familia=merged.get("salario_familia", (0.0, 0.0)),
        irrf_reducao=merged.get("irrf_reducao"),
        origem=origem,
    )


def load_tables(conn, company_id: int, competencia: str) -> TaxTables:
    """Tabelas da competência. Prioridade: globais do dono do sistema (company_id 0, mesmo ano)
    > as da empresa (legado) > as embutidas no código."""
    t = builtin_tables(competencia)
    ano = int(competencia[:4])
    try:
        rows = conn.execute(
            "SELECT id, tipo, company_id FROM tax_tables WHERE company_id IN (0, ?) AND ano=? "
            "ORDER BY CASE WHEN company_id = 0 THEN 0 ELSE 1 END, id DESC",
            (company_id, ano),
        ).fetchall()
    except Exception:
        return t

    vistos = set()
    for row in rows:
        row = dict(row)
        tipo = row["tipo"]
        if tipo in vistos:
            continue
        vistos.add(tipo)
        br = [dict(b) for b in conn.execute(
            "SELECT faixa_de, faixa_ate, aliquota, deducao FROM tax_brackets "
            "WHERE tax_table_id=? ORDER BY faixa_de", (row["id"],)
        ).fetchall()]
        if not br:
            continue
        marca = f"{'global' if int(row.get('company_id') or 0) == 0 else 'empresa'} {ano}"
        if tipo == "inss":
            faixas = [(float(b["faixa_ate"]), float(b["aliquota"]) / 100.0)
                      for b in br if b["faixa_ate"] is not None]
            if faixas:
                t.inss, t.origem["inss"] = faixas, marca
        elif tipo == "irrf":
            t.irrf = [(float(b["faixa_ate"]) if b["faixa_ate"] is not None else INF,
                       float(b["aliquota"]) / 100.0, float(b["deducao"] or 0)) for b in br]
            t.origem["irrf"] = marca
        elif tipo == "fgts":
            t.fgts_aliquota, t.origem["fgts"] = float(br[0]["aliquota"]) / 100.0, marca
        elif tipo == "salario_minimo":
            t.salario_minimo, t.origem["salario_minimo"] = float(br[0]["aliquota"]), marca
        elif tipo == "irrf_dependente":
            t.irrf_dependente, t.origem["irrf_dependente"] = float(br[0]["aliquota"]), marca
        elif tipo == "irrf_simplificado":
            t.irrf_simplificado, t.origem["irrf_simplificado"] = float(br[0]["aliquota"]), marca
        elif tipo == "salario_familia":
            # faixa_ate = limite de remuneração; aliquota = valor da cota
            t.salario_familia = (float(br[0]["faixa_ate"] or 0), float(br[0]["aliquota"]))
            t.origem["salario_familia"] = marca
    return t


def default_seed(ano: int) -> Dict[str, list]:
    """Linhas (faixa_de, faixa_ate, aliquota, deducao) para popular tax_tables de um ano."""
    t = builtin_tables(f"{ano}-12")
    inss, ini = [], 0.0
    for limite, aliq in t.inss:
        inss.append((ini, limite, round(aliq * 100, 4), 0))
        ini = round(limite + 0.01, 2)
    irrf, ini = [], 0.0
    for limite, aliq, ded in t.irrf:
        irrf.append((ini, None if limite == INF else limite, round(aliq * 100, 4), ded))
        ini = 0.0 if limite == INF else round(limite + 0.01, 2)
    return {
        "inss": inss,
        "irrf": irrf,
        "fgts": [(0, None, round(t.fgts_aliquota * 100, 4), 0)],
        "salario_minimo": [(0, None, t.salario_minimo, 0)],
        "irrf_dependente": [(0, None, t.irrf_dependente, 0)],
        "irrf_simplificado": [(0, None, t.irrf_simplificado, 0)],
        "salario_familia": [(0, t.salario_familia[0], t.salario_familia[1], 0)],
    }
