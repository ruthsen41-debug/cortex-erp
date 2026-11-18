"""
Aviso prévio como processo e rescisão complementar.

Aviso prévio (CLT arts. 487 a 491, Lei 12.506/2011, Súmula 380 do TST):
- o prazo começa no dia seguinte ao da comunicação;
- dado pelo empregador: 30 dias + 3 por ano completo, até 90. Trabalhado, a parte que passa
  de 30 dias é indenizada (prática majoritária; a Nota Técnica 184/2012 do MTE diz que a
  proporcionalidade só beneficia o empregado), salvo se a empresa optar por exigir tudo;
- redução da jornada (art. 488): 2 horas por dia ou 7 dias corridos no fim, só quando a
  iniciativa é do empregador;
- pedido de demissão: o empregado deve 30 dias (sem proporcional). Se não cumprir, a empresa
  pode descontar (art. 487 §2º); a empresa pode dispensar o cumprimento;
- acordo (art. 484-A): aviso indenizado pela metade.

Rescisão complementar: diferenças pagas depois da rescisão (reajuste por dissídio ou
convenção, comissões, multa do art. 477 §8º, indenização adicional do art. 9º da Lei
7.238/84). Recalcula a rescisão com o salário novo usando o MESMO plano (datas e avos) e
lança só a diferença de cada rubrica. INSS, IRRF e pensão são recalculados sobre o total
(rescisão original + diferenças) e descontado o que já foi retido.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

try:
    from . import payroll_engine as pe
    from . import payroll_special as ps
except ImportError:  # execução fora do pacote
    import payroll_engine as pe  # type: ignore
    import payroll_special as ps  # type: ignore

r2 = pe.r2

INICIATIVAS = {
    "empregador": {"nome": "Empregador (dispensa sem justa causa)", "tipo_rescisao": "sem_justa_causa",
                   "modos": ("trabalhado", "indenizado")},
    "empregado": {"nome": "Empregado (pedido de demissão)", "tipo_rescisao": "pedido_demissao",
                  "modos": ("trabalhado", "dispensado", "nao_cumprido")},
    "acordo": {"nome": "Acordo entre as partes (CLT 484-A)", "tipo_rescisao": "acordo",
               "modos": ("trabalhado", "indenizado")},
}
REDUCOES = {"": "Sem redução", "2h": "Redução de 2 horas diárias", "7dias": "Falta de 7 dias corridos no fim"}


class AvisoInvalido(ValueError):
    pass


def planejar_aviso(admissao: date, data_aviso: date, iniciativa: str, modo: str,
                   reducao: str = "", proporcional_trabalhado: bool = False) -> Dict[str, Any]:
    """Dias e datas do aviso prévio. Datas em ISO."""
    if iniciativa not in INICIATIVAS:
        raise AvisoInvalido(f"Iniciativa inválida. Use: {', '.join(INICIATIVAS)}.")
    if modo not in INICIATIVAS[iniciativa]["modos"]:
        raise AvisoInvalido(f"Para esta iniciativa o aviso pode ser: {', '.join(INICIATIVAS[iniciativa]['modos'])}.")
    reducao = reducao or ""
    if reducao not in REDUCOES:
        raise AvisoInvalido("Redução inválida. Use 2h ou 7dias.")
    if data_aviso < admissao:
        raise AvisoInvalido("A data do aviso é anterior à admissão.")
    if reducao and not (iniciativa == "empregador" and modo == "trabalhado"):
        raise AvisoInvalido("A redução do art. 488 da CLT só vale para aviso trabalhado dado pelo empregador.")

    avisos: List[str] = []
    total = ps.dias_aviso_previo(admissao, data_aviso) if iniciativa != "empregado" else 30
    trab = ind = desconto = 0
    if iniciativa == "empregado":
        if modo == "trabalhado":
            trab = 30
        elif modo == "nao_cumprido":
            desconto = 30
            avisos.append("Aviso não cumprido: a rescisão desconta 30 dias de salário (CLT art. 487 §2º).")
        else:
            avisos.append("Cumprimento dispensado pela empresa: não há pagamento nem desconto do aviso.")
    elif modo == "trabalhado":
        trab = total if proporcional_trabalhado else min(30, total)
        ind = total - trab
        if iniciativa == "acordo":
            trab, ind = total, 0  # no acordo trabalhado o período é cumprido integralmente
        if ind:
            avisos.append(f"{trab} dias trabalhados e {ind} dias do aviso proporcional indenizados.")
    else:
        ind = total if iniciativa == "empregador" else total // 2
        if iniciativa == "acordo":
            avisos.append(f"Acordo (art. 484-A): metade do aviso indenizado ({ind} de {total} dias).")

    fim = data_aviso + timedelta(days=trab)          # Súmula 380: exclui o dia da comunicação
    deslig = fim if trab else data_aviso
    projetada = deslig + timedelta(days=ind)
    ultimo_dia_trabalho = fim - timedelta(days=7) if reducao == "7dias" else fim
    if reducao == "2h":
        avisos.append("Jornada reduzida em 2 horas diárias, sem prejuízo do salário (CLT art. 488).")
    if reducao == "7dias":
        avisos.append(f"O empregado deixa de trabalhar nos últimos 7 dias (a partir de "
                      f"{(ultimo_dia_trabalho + timedelta(days=1)).strftime('%d/%m/%Y')}), sem prejuízo do salário.")
    return {
        "iniciativa": iniciativa, "iniciativa_nome": INICIATIVAS[iniciativa]["nome"], "modo": modo,
        "reducao": reducao, "reducao_nome": REDUCOES[reducao],
        "tipo_rescisao": INICIATIVAS[iniciativa]["tipo_rescisao"],
        "data_aviso": data_aviso.isoformat(), "data_inicio": (data_aviso + timedelta(days=1)).isoformat(),
        "dias_total": total, "dias_trabalhados": trab, "dias_indenizados": ind, "dias_desconto": desconto,
        "data_fim": fim.isoformat(), "ultimo_dia_trabalho": ultimo_dia_trabalho.isoformat(),
        "data_desligamento": deslig.isoformat(), "data_projetada": projetada.isoformat(), "avisos": avisos,
    }


# ── Rescisão complementar ────────────────────────────────────────────────────
_ENCARGOS = ("0100", "0101", "0104", "0121", "0122")      # INSS, IRRF, pensão, INSS 13º, IRRF 13º
_GRUPO_ENCARGO = {"mensal": ("INSS", "IRRF", False), "decimo": ("INSS_13", "IRRF_13", True)}


def _linha(rubrics, codigo: str, valor: float, referencia: str, grupo: str, nome: Optional[str] = None,
           tipo: Optional[str] = None) -> Dict[str, Any]:
    m = pe.rubric_meta(rubrics, codigo)
    return {"codigo": codigo, "nome": nome or m["nome"], "tipo": tipo or m.get("tipo") or "provento",
            "referencia": referencia, "valor": r2(valor), "origem": "complementar", "grupo": grupo,
            "incide_inss": int(m.get("incide_inss") or 0), "incide_irrf": int(m.get("incide_irrf") or 0),
            "incide_fgts": int(m.get("incide_fgts") or 0)}


def calc_complementar(ctx: ps.Contexto, tables, rubrics: Optional[Dict[str, Any]],
                      linhas_originais: List[Dict[str, Any]], recalculo: Optional[Dict[str, Any]],
                      multa_pct: float, multa_477: bool = False, indeniz_data_base: bool = False,
                      verbas: Optional[List[Dict[str, Any]]] = None, motivo: str = "") -> Dict[str, Any]:
    """
    linhas_originais: linhas gravadas da rescisão (com grupo).
    recalculo: resultado de payroll_special.calc_rescisao com o salário novo e o mesmo plano
    (None quando não há reajuste). verbas: [{codigo, valor, referencia?, nome?}] de rubricas
    da empresa (provento ou desconto). O salário de ctx é o vigente para as multas.
    """
    ref = motivo or "complementar"
    diffs: List[Dict[str, Any]] = []
    if recalculo:
        antes: Dict[tuple, float] = {}
        for l in linhas_originais:
            if l.get("tipo") == "provento":
                k = (str(l["codigo"]), l.get("grupo") or "mensal")
                antes[k] = antes.get(k, 0.0) + float(l["valor"] or 0)
        depois: Dict[tuple, Dict[str, Any]] = {}
        for l in recalculo["lines"]:
            if l.get("tipo") == "provento":
                k = (str(l["codigo"]), l.get("grupo") or "mensal")
                d = depois.setdefault(k, {**l, "valor": 0.0})
                d["valor"] += float(l["valor"] or 0)
        for k, l in depois.items():
            dif = r2(l["valor"] - antes.get(k, 0.0))
            if dif > 0:
                diffs.append(_linha(rubrics, k[0], dif, ref, k[1], f"Dif. {l['nome']}"))
    if multa_477:
        diffs.append(_linha(rubrics, "0048", ctx.salario, "1 salário", "indenizacao"))
    if indeniz_data_base:
        diffs.append(_linha(rubrics, "0049", ctx.salario, "1 salário", "indenizacao"))
    for v in verbas or []:
        codigo = str(v.get("codigo") or "").strip()
        try:
            valor = float(v.get("valor") or 0)
        except (TypeError, ValueError):
            raise ValueError(f"Valor inválido na rubrica {codigo}.")
        if not codigo or valor <= 0:
            continue
        if codigo in _ENCARGOS:
            raise ValueError("INSS, IRRF e pensão são calculados automaticamente; não lance essas rubricas.")
        diffs.append(_linha(rubrics, codigo, valor, str(v.get("referencia") or ref), "mensal", v.get("nome") or None))
    if not diffs:
        raise ValueError("Nada a complementar: informe o novo salário, as multas ou alguma verba.")

    # Encargos: total (original + diferenças) menos o já retido
    f_total = ps._Folha(rubrics)
    for l in linhas_originais:
        if l.get("tipo") in ("provento", "desconto") and str(l["codigo"]) not in _ENCARGOS:
            f_total.lines.append(_linha(rubrics, str(l["codigo"]), float(l["valor"] or 0), "",
                                        l.get("grupo") or "mensal", tipo=l["tipo"]))
    f_total.lines.extend(dict(d) for d in diffs)
    for grupo, (k_inss, k_irrf, so_perc) in _GRUPO_ENCARGO.items():
        ps._encargos(f_total, ctx, tables, grupo, k_inss, k_irrf, so_pensao_percentual=so_perc)
    retido: Dict[tuple, float] = {}
    for l in linhas_originais:
        if str(l["codigo"]) in _ENCARGOS:
            k = (str(l["codigo"]), l.get("grupo") or "mensal")
            retido[k] = retido.get(k, 0.0) + float(l["valor"] or 0)
    novo: Dict[tuple, Dict[str, Any]] = {}
    for l in f_total.lines:
        if str(l["codigo"]) in _ENCARGOS:
            k = (str(l["codigo"]), l.get("grupo") or "mensal")
            d = novo.setdefault(k, {**l, "valor": 0.0})
            d["valor"] += l["valor"]

    f = ps._Folha(rubrics)
    f.lines.extend(diffs)
    inss = irrf = 0.0
    for k, l in novo.items():
        dif = r2(l["valor"] - retido.get(k, 0.0))
        if dif > 0:
            f.lines.append({**l, "valor": dif, "referencia": "complementar"})
            if k[0] in ("0100", "0121"):
                inss += dif
            elif k[0] in ("0101", "0122"):
                irrf += dif
    base_fgts = f.base("incide_fgts")
    fgts = r2(base_fgts * tables.fgts_aliquota)
    multa = r2(fgts * multa_pct)
    if multa:
        f.lines.append(_linha(rubrics, "0210", multa, f"{int(multa_pct * 100)}%", "mensal",
                              "Multa Rescisória do FGTS s/ diferenças (recolhida em guia)", tipo="informativo"))
    if multa_477:
        f.avisos.append("Multa do art. 477 §8º: devida quando as verbas não são pagas em até 10 dias do término do contrato.")
    if recalculo:
        f.avisos.append("No eSocial, diferenças de dissídio ou convenção posteriores ao desligamento vão no S-2299 "
                        "retificado ou no S-1200 com informações de períodos anteriores, conforme o acordo.")
    return f.resultado(ctx, inss=r2(inss), irrf=r2(irrf), fgts=fgts, base_fgts=base_fgts, multa_fgts=multa)
