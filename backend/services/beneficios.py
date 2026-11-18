"""Benefícios da folha (bloco 4 da paridade DP): vale-transporte por dias de uso,
plano de saúde por faixa etária com dependentes e coparticipação, e empréstimo consignado.

Regras:
- VT (Lei 7.418/85 e Decreto 10.854/2021): o empregador antecipa o transporte dos dias de
  trabalho; o desconto do empregado é de até 6% do salário básico e nunca passa do custo do
  vale. Dias de férias, afastamento e faltas não usam vale.
- Plano de saúde: faixas etárias da ANS (RN 63/2003, 10 faixas); a parte do empregado é
  descontada em folha (natureza eSocial 9219) e não integra INSS, FGTS nem IRRF mensal
  (Lei 8.212/91 art. 28 §9º "q").
- Consignado (Lei 10.820/2003): desconto limitado a uma margem (padrão 35%) da remuneração
  disponível = bruto − descontos obrigatórios (INSS, IRRF e pensão). Na rescisão, desconta-se o
  saldo até a mesma margem das verbas, se o contrato prever. Crédito do Trabalhador usa a
  natureza 9253 (desde 05/2025); convênio antigo com o banco, 9254.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# RN 63/2003 da ANS: 10 faixas etárias para planos contratados a partir de 2004
FAIXAS_ANS: List[Tuple[int, int]] = [
    (0, 18), (19, 23), (24, 28), (29, 33), (34, 38),
    (39, 43), (44, 48), (49, 53), (54, 58), (59, 200),
]

ORIGENS_CONSIGNADO = {
    "credito_trabalhador": "Crédito do Trabalhador (eSocial / FGTS Digital)",
    "convenio": "Convênio com instituição financeira",
}

MARGEM_PADRAO = 35.0


def r2(v: float) -> float:
    return round(float(v or 0) + 1e-9, 2)


def _d(v: Any) -> Optional[date]:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v or "")[:10])
    except ValueError:
        return None


# ── Vale-transporte ──────────────────────────────────────────────────────────
def dias_uso_vt(inicio: date, fim: date, feriados: Iterable[date], admissao: Optional[date] = None,
                desligamento: Optional[date] = None,
                periodos_fora: Sequence[Tuple[Optional[date], Optional[date]]] = (),
                faltas: Iterable[date] = ()) -> int:
    """Dias úteis (segunda a sexta, fora feriados) em que o funcionário usa o vale:
    exclui antes da admissão, depois do desligamento, férias/afastamentos e faltas."""
    feriados, faltas = set(feriados), set(faltas)
    fora: List[Tuple[date, date]] = []
    for a, b in periodos_fora:
        if a:
            fora.append((a, b or fim))
    n, d = 0, inicio
    while d <= fim:
        util = d.weekday() < 5 and d not in feriados
        if util and (admissao is None or d >= admissao) and (desligamento is None or d <= desligamento) \
                and d not in faltas and not any(a <= d <= b for a, b in fora):
            n += 1
        d += timedelta(days=1)
    return n


def itens_vt(vales: List[Dict[str, Any]], dias_uso: int) -> List[Dict[str, Any]]:
    """Linhas de compra: tarifa × vales por dia × dias (dias_mes fixo do cadastro tem prioridade)."""
    out = []
    for v in vales:
        if not int(v.get("ativo", 1) or 0):
            continue
        dias = int(v.get("dias_mes") or 0) or dias_uso
        qtd = int(v.get("vales_dia") or 0) * dias
        tarifa = float(v.get("tarifa") or 0)
        out.append({"descricao": v.get("descricao") or "Vale-transporte", "tarifa": tarifa,
                    "vales_dia": int(v.get("vales_dia") or 0), "dias": dias, "quantidade": qtd,
                    "valor": r2(tarifa * qtd)})
    return out


def desconto_vt(salario_basico: float, custo: float) -> float:
    """6% do salário básico, limitado ao custo do vale."""
    return r2(min(max(0.0, salario_basico) * 0.06, max(0.0, custo)))


# ── Plano de saúde ───────────────────────────────────────────────────────────
def idade_em(nascimento: Any, ref: date) -> Optional[int]:
    n = _d(nascimento)
    if not n:
        return None
    return ref.year - n.year - ((ref.month, ref.day) < (n.month, n.day))


def valor_por_idade(faixas: List[Dict[str, Any]], idade: Optional[int]) -> float:
    if idade is None:
        return 0.0
    for f in faixas:
        if int(f.get("idade_min") or 0) <= idade <= int(f.get("idade_max") if f.get("idade_max") is not None else 200):
            return float(f.get("valor") or 0)
    return 0.0


def mensalidade_plano(plano: Dict[str, Any], faixas: List[Dict[str, Any]], titular_nasc: Any,
                      dependentes: List[Dict[str, Any]], ref: date) -> Dict[str, Any]:
    """Mensalidade do titular e de cada dependente, e quanto cabe ao empregado.

    plano: modalidade_valor ('faixa' | 'fixo'), valor_fixo_titular, valor_fixo_dependente,
    pct_empresa_titular, pct_empresa_dependente (0–100)."""
    por_faixa = (plano.get("modalidade_valor") or "faixa") == "faixa"
    pt = min(100.0, max(0.0, float(plano.get("pct_empresa_titular") or 0))) / 100.0
    pd = min(100.0, max(0.0, float(plano.get("pct_empresa_dependente") or 0))) / 100.0
    vidas = []
    idade_t = idade_em(titular_nasc, ref)
    v_t = valor_por_idade(faixas, idade_t) if por_faixa else float(plano.get("valor_fixo_titular") or 0)
    vidas.append({"beneficiario": "Titular", "idade": idade_t, "valor": r2(v_t),
                  "empresa": r2(v_t * pt), "empregado": r2(v_t - r2(v_t * pt)), "dependente_id": None})
    for dep in dependentes:
        idade = idade_em(dep.get("data_nascimento"), ref)
        v = valor_por_idade(faixas, idade) if por_faixa else float(plano.get("valor_fixo_dependente") or 0)
        vidas.append({"beneficiario": dep.get("nome") or "Dependente", "idade": idade, "valor": r2(v),
                      "empresa": r2(v * pd), "empregado": r2(v - r2(v * pd)), "dependente_id": dep.get("id"),
                      "cpf": dep.get("cpf") or ""})
    avisos = []
    if por_faixa and not faixas:
        avisos.append(f"Plano {plano.get('nome')}: nenhuma faixa etária cadastrada.")
    sem_idade = [v["beneficiario"] for v in vidas if v["idade"] is None and por_faixa]
    if sem_idade:
        avisos.append(f"Plano {plano.get('nome')}: sem data de nascimento para {', '.join(sem_idade)}; mensalidade zerada.")
    return {"vidas": vidas, "total": r2(sum(v["valor"] for v in vidas)),
            "empresa": r2(sum(v["empresa"] for v in vidas)),
            "empregado": r2(sum(v["empregado"] for v in vidas)), "avisos": avisos}


def faixas_padrao_ans() -> List[Dict[str, Any]]:
    return [{"idade_min": a, "idade_max": b, "valor": 0.0} for a, b in FAIXAS_ANS]


def validar_faixas(faixas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordena e confere sobreposição; ValueError com mensagem ao usuário."""
    out = []
    for f in faixas:
        try:
            a, b = int(f.get("idade_min")), int(f.get("idade_max"))
            v = float(f.get("valor") or 0)
        except (TypeError, ValueError):
            raise ValueError("Faixa etária: informe idade inicial, idade final e valor numéricos.")
        if a < 0 or b < a:
            raise ValueError(f"Faixa {a}–{b}: a idade final deve ser maior ou igual à inicial.")
        if v < 0:
            raise ValueError(f"Faixa {a}–{b}: valor negativo.")
        out.append({"idade_min": a, "idade_max": b, "valor": r2(v)})
    out.sort(key=lambda f: f["idade_min"])
    for x, y in zip(out, out[1:]):
        if y["idade_min"] <= x["idade_max"]:
            raise ValueError(f"As faixas {x['idade_min']}–{x['idade_max']} e {y['idade_min']}–{y['idade_max']} se sobrepõem.")
    return out


# ── Consignado ───────────────────────────────────────────────────────────────
def meses_entre(ini: str, fim: str) -> int:
    """Meses de ini (AAAA-MM) até fim (AAAA-MM), contando os dois: 2026-01 → 2026-03 = 3."""
    return (int(fim[:4]) - int(ini[:4])) * 12 + int(fim[5:7]) - int(ini[5:7]) + 1


def parcela_do_mes(contrato: Dict[str, Any], competencia: str) -> Tuple[int, float]:
    """(número da parcela, valor) na competência; (0, 0) fora do prazo."""
    ini = str(contrato.get("competencia_inicio") or "")[:7]
    if not ini or not int(contrato.get("ativo", 1) or 0):
        return 0, 0.0
    n = meses_entre(ini, competencia)
    total = int(contrato.get("parcelas_total") or 0)
    if n < 1 or (total and n > total):
        return 0, 0.0
    return n, r2(float(contrato.get("valor_parcela") or 0))


def margem(bruto: float, obrigatorios: float, pct: float) -> float:
    """Margem consignável: pct% da remuneração disponível (bruto − INSS − IRRF − pensão)."""
    return r2(max(0.0, bruto - obrigatorios) * max(0.0, pct) / 100.0)


def aplicar_margem(parcelas: List[Dict[str, Any]], margem_valor: float) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Desconta as parcelas na ordem (contratos mais antigos primeiro) até a margem."""
    resto, out, avisos = margem_valor, [], []
    for p in parcelas:
        v = r2(min(p["valor"], max(0.0, resto)))
        resto = r2(resto - v)
        if v < p["valor"]:
            avisos.append(f"Consignado {p.get('nome') or ''}: parcela de R$ {p['valor']:.2f} passa da margem "
                          f"consignável; descontado R$ {v:.2f}. Avise a instituição da diferença.")
        if v > 0:
            out.append({**p, "valor": v})
    return out, avisos


def saldo_rescisao(contrato: Dict[str, Any], competencia: str) -> float:
    """Saldo a quitar na rescisão: o informado pelo banco ou as parcelas restantes (incluindo a do mês)."""
    if float(contrato.get("saldo_devedor") or 0) > 0:
        return r2(float(contrato["saldo_devedor"]))
    ini = str(contrato.get("competencia_inicio") or "")[:7]
    total = int(contrato.get("parcelas_total") or 0)
    if not ini or not total:
        return 0.0
    pagas = max(0, min(total, meses_entre(ini, competencia) - 1))
    return r2((total - pagas) * float(contrato.get("valor_parcela") or 0))
