"""
Folha complementar e dissídio retroativo.

Folha complementar (mesma competência, depois da folha mensal):
    recalcula o mês do funcionário com os lançamentos novos e paga só a diferença em relação ao que já
    foi pago (folha mensal + complementares anteriores). INSS e IRRF ficam corretos porque o cálculo é
    sobre o total do mês, descontando o que já foi retido.

Dissídio / acordo / convenção retroativos (diferenças salariais de meses anteriores):
    aplica o percentual de reajuste sobre as rubricas ligadas ao salário em cada mês já pago
    (salário, horas extras, adicional noturno, periculosidade, DSR, rubricas por fórmula sobre o salário,
    férias) e paga as diferenças numa folha da competência de pagamento.
      * INSS: recalculado por mês de referência, com a tabela daquele mês (base original + diferença).
      * FGTS: 8% das diferenças, por mês de referência.
      * IRRF: regime de caixa. Diferenças do mesmo ano somam aos rendimentos do mês do pagamento; de anos
        anteriores, rendimentos recebidos acumuladamente (RRA, Lei 7.713/88 art. 12-A: tabela × nº de meses).
      * eSocial: S-1200 com o grupo infoPerAnt (ideADC: data e tipo do instrumento, perRef de cada mês).
"""
import json
from datetime import date
from typing import Any, Dict, List, Optional

try:
    from . import payroll_engine as pe
    from .payroll_tables import load_tables
except ImportError:  # execução com backend/ como raiz
    from services import payroll_engine as pe
    from services.payroll_tables import load_tables

r2 = pe.r2

TIPOS_INSTRUMENTO = {
    "A": "Acordo Coletivo de Trabalho",
    "B": "Legislação federal, estadual, municipal ou distrital",
    "C": "Convenção Coletiva de Trabalho",
    "D": "Sentença normativa - Dissídio",
}

# Rubricas de sistema proporcionais ao salário (recebem o percentual do dissídio).
# Insalubridade fica de fora: é calculada sobre o salário mínimo.
CODIGOS_SALARIAIS = {"0001", "0002", "0003", "0004", "0006", "0011", "0040",
                     "0008", "0009", "0030", "0031", "0032",          # férias, 1/3, abono
                     "0106", "0107", "0108"}                           # faltas, DSR perdido, atrasos (descontos)
_VARIAVEIS_SALARIO = ("salario_base", "salario_dia", "salario_hora")
_IMPOSTOS = {"0100", "0101", "0121", "0122"}
_INFORMATIVOS = {"0200", "0201", "0202", "0203", "0210"}


def _rows(conn, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def meses(comp_ini: str, comp_fim: str) -> List[str]:
    out = []
    a, m = int(comp_ini[:4]), int(comp_ini[5:7])
    while f"{a:04d}-{m:02d}" <= comp_fim:
        out.append(f"{a:04d}-{m:02d}")
        m += 1
        if m > 12:
            a, m = a + 1, 1
    return out


def _fmt_comp(comp: str) -> str:
    return f"{comp[5:7]}/{comp[:4]}"


def _incide(rubrics, codigo: str, flag: str) -> bool:
    return bool(pe.rubric_meta(rubrics, codigo).get(flag))


def rubricas_salariais(rubrics: Dict[str, Dict[str, Any]], extras: Optional[List[str]] = None) -> set:
    """Códigos que recebem o reajuste: os de sistema proporcionais ao salário, as rubricas da empresa com
    fórmula sobre o salário e os códigos informados pelo usuário."""
    cods = set(CODIGOS_SALARIAIS)
    for cod, r in (rubrics or {}).items():
        f = (r.get("formula") or "")
        if r.get("tipo") in ("provento", "desconto") and any(v in f for v in _VARIAVEIS_SALARIO):
            cods.add(cod)
    cods.update(str(c) for c in (extras or []))
    return cods - _IMPOSTOS - _INFORMATIVOS


# ── IRRF ─────────────────────────────────────────────────────────────────────
def rendimento_irrf(linhas: List[Dict[str, Any]], rubrics) -> float:
    """Rendimento tributável (antes das deduções) a partir das linhas de um holerite."""
    total = 0.0
    for l in linhas:
        cod = str(l.get("codigo"))
        if not _incide(rubrics, cod, "incide_irrf"):
            continue
        if l.get("tipo") == "provento":
            total += float(l.get("valor") or 0)
        elif l.get("tipo") == "desconto":
            total -= float(l.get("valor") or 0)
    return r2(max(0.0, total))


def irrf_rra(rendimento: float, inss: float, n_meses: int, t) -> float:
    """IRRF de rendimentos recebidos acumuladamente: tabela progressiva multiplicada pelo nº de meses."""
    n = max(1, int(n_meses))
    base = max(0.0, rendimento - inss)
    imposto = 0.0
    for limite, aliq, parcela in t.irrf:
        if base <= limite * n:
            imposto = max(0.0, base * aliq - parcela * n)
            break
    imposto = r2(imposto)
    return 0.0 if imposto <= pe.IRRF_MINIMO_RETENCAO else imposto


# ── Folha complementar ───────────────────────────────────────────────────────
def _ja_pago(conn, company_id: int, competencia: str, employee_id: int) -> Dict[str, Any]:
    """Soma do que já foi pago na competência (folha mensal + complementares)."""
    itens = _rows(conn, """
        SELECT pi.* FROM payroll_items pi JOIN payroll_runs pr ON pr.id = pi.run_id
        WHERE pr.company_id=? AND pr.competence=? AND pi.employee_id=? AND pr.status != 'cancelado'
          AND COALESCE(pr.tipo, 'mensal') IN ('mensal', 'complementar')""",
                  (company_id, competencia, employee_id))
    linhas: Dict[str, float] = {}
    for it in itens:
        for l in _rows(conn, "SELECT codigo, tipo, valor FROM payroll_item_lines WHERE item_id=?", (it["id"],)):
            if l["tipo"] in ("provento", "desconto"):
                linhas[(l["codigo"], l["tipo"])] = linhas.get((l["codigo"], l["tipo"]), 0.0) + float(l["valor"] or 0)
    return {
        "existe": bool(itens),
        "linhas": linhas,
        "inss": sum(float(i.get("inss") or 0) for i in itens),
        "irrf": sum(float(i.get("irrf") or 0) for i in itens),
        "fgts": sum(float(i.get("fgts") or 0) for i in itens),
        "base_inss": sum(float(i.get("base_inss") or 0) for i in itens),
        "base_fgts": sum(float(i.get("base_fgts") or 0) for i in itens),
    }


def calcular_complementar(conn, company_id: int, competencia: str,
                          lancamentos: List[Dict[str, Any]],
                          employee_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """lancamentos: [{employee_id, codigo, quantidade, valor}] somados aos do mês.
    Funcionários sem lançamento novo também entram se informados em employee_ids (recalcula o mês com o
    cadastro e o ponto atuais e paga a diferença)."""
    mensal = conn.execute("""SELECT id FROM payroll_runs WHERE company_id=? AND competence=? AND status != 'cancelado'
                             AND COALESCE(tipo, 'mensal')='mensal'""", (company_id, competencia)).fetchone()
    if not mensal:
        raise ValueError(f"Processe a folha mensal de {_fmt_comp(competencia)} antes da complementar.")
    por_emp: Dict[int, List[Dict[str, Any]]] = {}
    ignorados: List[Dict[str, Any]] = []
    for l in lancamentos or []:
        if not l.get("employee_id") or not str(l.get("codigo") or "").strip():
            continue
        cod = str(l["codigo"]).strip()
        if cod in RUBRICAS_BLOQUEADAS:
            nome_rub = pe.SYSTEM_RUBRICS[pe._SYSTEM_CODES[cod]][1]
            ignorados.append({"employee_id": int(l["employee_id"]),
                              "motivo": f"A rubrica {cod} — {nome_rub} é calculada automaticamente e não aceita "
                                        "lançamento. Para diferença de salário use o Dissídio retroativo ou corrija "
                                        "o cadastro e recalcule."})
            continue
        por_emp.setdefault(int(l["employee_id"]), []).append(
            {"codigo": str(l["codigo"]).strip(), "quantidade": float(l.get("quantidade") or 0),
             "valor": float(l.get("valor") or 0)})
    ids = sorted(set(por_emp) | set(int(i) for i in (employee_ids or [])))
    tables = load_tables(conn, company_id, competencia)
    if not ids:
        if ignorados:
            return _totais(competencia, [], _com_nomes(conn, company_id, ignorados), tables)
        raise ValueError("Informe ao menos um lançamento ou funcionário para a folha complementar.")

    rubrics = pe.load_rubrics(conn, company_id)
    inputs = {i.employee_id: i for i in pe.build_inputs(conn, company_id, competencia, True, ids, rubrics=rubrics)}
    results = []
    for eid in ids:
        inp = inputs.get(eid)
        if not inp:
            ignorados.append({"employee_id": eid, "motivo": "Funcionário inativo ou não admitido na competência."})
            continue
        pago = _ja_pago(conn, company_id, competencia, eid)
        if not pago["existe"]:
            ignorados.append({"employee_id": eid, "motivo": "Funcionário não está na folha mensal da competência."})
            continue
        inp.lancamentos = list(inp.lancamentos) + por_emp.get(eid, [])
        novo = pe.calculate_employee(inp, tables, rubrics)
        results.append(_diferenca(novo, pago, rubrics))
    return _totais(competencia, results, _com_nomes(conn, company_id, ignorados), tables)


# Rubricas de sistema que a complementar não aceita (só as de horas recebem lançamento manual).
RUBRICAS_BLOQUEADAS = frozenset(c for c in pe._SYSTEM_CODES if c not in pe._HOUR_CODES)


def _com_nomes(conn, company_id: int, ignorados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Completa employee_name nos ignorados para a tela mostrar quem foi."""
    for g in ignorados:
        if not g.get("employee_name"):
            row = conn.execute("SELECT name FROM employees WHERE id=? AND company_id=?",
                               (g["employee_id"], company_id)).fetchone()
            g["employee_name"] = row["name"] if row else f"Funcionário {g['employee_id']}"
    return ignorados


def funcionarios_da_folha(conn, company_id: int, competencia: str) -> List[Dict[str, Any]]:
    """Funcionários presentes na folha mensal (não cancelada) da competência."""
    return _rows(conn, """
        SELECT DISTINCT e.id, e.name FROM payroll_items pi
        JOIN payroll_runs pr ON pr.id = pi.run_id JOIN employees e ON e.id = pi.employee_id
        WHERE pr.company_id=? AND pr.competence=? AND pr.status != 'cancelado'
          AND COALESCE(pr.tipo, 'mensal')='mensal'
        ORDER BY e.name, e.id""", (company_id, competencia))


def _diferenca(novo: Dict[str, Any], pago: Dict[str, Any], rubrics) -> Dict[str, Any]:
    avisos: List[str] = []
    agreg: Dict[tuple, Dict[str, Any]] = {}
    for l in novo["lines"]:
        if l["tipo"] not in ("provento", "desconto") or l["codigo"] in _IMPOSTOS:
            continue
        k = (l["codigo"], l["tipo"])
        a = agreg.setdefault(k, {"codigo": l["codigo"], "nome": l["nome"], "tipo": l["tipo"],
                                 "referencia": l.get("referencia", ""), "valor": 0.0})
        a["valor"] += l["valor"]
    for k in pago["linhas"]:
        if k[0] not in _IMPOSTOS and k not in agreg:
            m = pe.rubric_meta(rubrics, k[0])
            agreg[k] = {"codigo": k[0], "nome": m["nome"], "tipo": k[1], "referencia": "", "valor": 0.0}
    linhas = []
    for k, a in sorted(agreg.items()):
        dif = r2(a["valor"] - pago["linhas"].get(k, 0.0))
        if abs(dif) < 0.005:
            continue
        if dif < 0:
            rotulo = "provento" if a["tipo"] == "provento" else "desconto"
            avisos.append(f"{a['nome']}: {rotulo} menor que o já pago (R$ {-dif:.2f}); a complementar só "
                          f"acrescenta valores — acerte na próxima folha.")
            continue
        linhas.append({**a, "valor": dif, "origem": "complementar"})
    base_inss = r2(sum(l["valor"] * (1 if l["tipo"] == "provento" else -1) for l in linhas
                       if _incide(rubrics, l["codigo"], "incide_inss")))
    base_fgts = r2(sum(l["valor"] * (1 if l["tipo"] == "provento" else -1) for l in linhas
                       if _incide(rubrics, l["codigo"], "incide_fgts")))
    inss = r2(novo["inss"] - pago["inss"])
    irrf = r2(novo["irrf"] - pago["irrf"])
    fgts = r2(novo["fgts"] - pago["fgts"])
    if inss < 0:
        avisos.append(f"INSS do mês ficou R$ {-inss:.2f} menor que o retido; a diferença não é devolvida aqui.")
        inss = 0.0
    if irrf < 0:
        avisos.append(f"IRRF do mês ficou R$ {-irrf:.2f} menor que o retido; a diferença não é devolvida aqui.")
        irrf = 0.0
    fgts = max(0.0, fgts)
    return _resultado(novo["employee_id"], novo["employee_name"], linhas, inss, irrf, fgts,
                      max(0.0, base_inss), max(0.0, base_fgts), avisos + [a for a in novo["avisos"]
                                                                          if "lançamento" in a.lower()])


def _resultado(eid, nome, linhas, inss, irrf, fgts, base_inss, base_fgts, avisos, irrf_nome=None,
               inss_por_mes=None):
    if inss_por_mes:
        for per, v in sorted(inss_por_mes.items()):
            if v > 0:
                linhas.append({"codigo": "0100", "nome": f"INSS s/ diferenças {_fmt_comp(per)}", "tipo": "desconto",
                               "referencia": "tabela", "valor": r2(v), "origem": "automatico", "per_ref": per})
    elif inss > 0:
        linhas.append({"codigo": "0100", "nome": "INSS", "tipo": "desconto", "referencia": "tabela",
                       "valor": inss, "origem": "automatico"})
    if irrf > 0:
        linhas.append({"codigo": "0101", "nome": irrf_nome or "IRRF", "tipo": "desconto", "referencia": "",
                       "valor": irrf, "origem": "automatico"})
    proventos = r2(sum(l["valor"] for l in linhas if l["tipo"] == "provento"))
    descontos = r2(sum(l["valor"] for l in linhas if l["tipo"] == "desconto"))
    for cod, nome_i, v in (("0201", "Base de Cálculo INSS", base_inss), ("0203", "Base de Cálculo FGTS", base_fgts),
                           ("0200", "FGTS do mês", fgts)):
        if v > 0:
            linhas.append({"codigo": cod, "nome": nome_i, "tipo": "informativo", "referencia": "", "valor": r2(v),
                           "origem": "automatico"})
    return {"employee_id": eid, "employee_name": nome, "lines": linhas,
            "total_proventos": proventos, "total_descontos": descontos, "liquido": r2(proventos - descontos),
            "inss": r2(inss), "irrf": r2(irrf), "fgts": r2(fgts), "base_inss": r2(base_inss), "base_irrf": 0.0,
            "base_fgts": r2(base_fgts), "vt_desconto": 0.0, "dias_pagos": 0, "avisos": avisos}


def _totais(competencia, results, ignorados, tables, extra=None):
    out = {
        "competencia": competencia,
        "tabelas": {"origem": tables.origem, "salario_minimo": tables.salario_minimo, "inss_teto": tables.inss_teto},
        "results": [r for r in results if r["lines"]],
        "ignorados": ignorados,
        "totais": {k: r2(sum(r[c] for r in results)) for k, c in (
            ("proventos", "total_proventos"), ("descontos", "total_descontos"), ("liquido", "liquido"),
            ("inss", "inss"), ("irrf", "irrf"), ("fgts", "fgts"))},
    }
    if extra:
        out.update(extra)
    return out


# ── Dissídio retroativo ──────────────────────────────────────────────────────
def calcular_dissidio(conn, company_id: int, dados: Dict[str, Any]) -> Dict[str, Any]:
    """dados: competencia_pagamento, competencia_inicio, competencia_fim (opcional), percentual,
    percentuais {employee_id: %} (opcional), employee_ids (opcional), rubricas_extras (opcional),
    tp_acordo (A/B/C/D), dt_acordo (AAAA-MM-DD), descricao."""
    comp_pg = str(dados.get("competencia_pagamento") or "")[:7]
    comp_ini = str(dados.get("competencia_inicio") or "")[:7]
    comp_fim = str(dados.get("competencia_fim") or "")[:7]
    if not comp_fim:
        a, m = int(comp_pg[:4]), int(comp_pg[5:7]) - 1
        comp_fim = f"{a - 1:04d}-12" if m == 0 else f"{a:04d}-{m:02d}"
    tp = str(dados.get("tp_acordo") or "C").upper()
    dt_acordo = str(dados.get("dt_acordo") or "")[:10]
    erros = []
    for nome, c in (("pagamento", comp_pg), ("início", comp_ini), ("fim", comp_fim)):
        if len(c) != 7 or c[4] != "-":
            erros.append(f"Competência de {nome} inválida (use AAAA-MM).")
    if not erros and not (comp_ini <= comp_fim <= comp_pg):
        erros.append("O período das diferenças deve começar antes do fim e terminar até a competência de pagamento.")
    if tp not in TIPOS_INSTRUMENTO:
        erros.append("Tipo do instrumento inválido (A acordo, B legislação, C convenção, D dissídio).")
    try:
        date.fromisoformat(dt_acordo)
    except ValueError:
        erros.append("Informe a data de assinatura do acordo/convenção/sentença (AAAA-MM-DD).")
    if not erros and dt_acordo[:7] > comp_pg:
        erros.append("A data do acordo deve ser igual ou anterior à competência de pagamento (regra do eSocial).")
    pct_geral = float(dados.get("percentual") or 0)
    pcts = {int(k): float(v) for k, v in (dados.get("percentuais") or {}).items() if v not in (None, "")}
    if pct_geral <= 0 and not pcts:
        erros.append("Informe o percentual de reajuste.")
    if erros:
        raise ValueError(" ".join(erros))

    rubrics = pe.load_rubrics(conn, company_id)
    cods = rubricas_salariais(rubrics, dados.get("rubricas_extras"))
    filtro = set(int(i) for i in (dados.get("employee_ids") or []))
    periodo = meses(comp_ini, comp_fim)
    tab_pg = load_tables(conn, company_id, comp_pg)

    # Folhas mensais/complementares já pagas no período, por funcionário e mês
    itens = _rows(conn, """
        SELECT pi.*, pr.competence, e.name AS employee_name, e.active, e.is_prolabore, e.dependents
        FROM payroll_items pi JOIN payroll_runs pr ON pr.id = pi.run_id JOIN employees e ON e.id = pi.employee_id
        WHERE pr.company_id=? AND pr.status != 'cancelado' AND pr.competence >= ? AND pr.competence <= ?
          AND COALESCE(pr.tipo, 'mensal') IN ('mensal', 'complementar')
        ORDER BY pr.competence, pi.id""", (company_id, comp_ini, comp_fim))
    ferias = _rows(conn, """
        SELECT ps.*, e.name AS employee_name, e.active, e.is_prolabore, e.dependents
        FROM payroll_special ps JOIN employees e ON e.id = ps.employee_id
        WHERE ps.company_id=? AND ps.tipo='ferias' AND ps.status != 'cancelado'""", (company_id,))

    funcs: Dict[int, Dict[str, Any]] = {}

    def func(eid, row):
        return funcs.setdefault(eid, {"employee_id": eid, "employee_name": row["employee_name"],
                                      "active": row.get("active"), "is_prolabore": row.get("is_prolabore"),
                                      "dependents": int(row.get("dependents") or 0), "meses": {}})

    for it in itens:
        eid = it["employee_id"]
        if filtro and eid not in filtro:
            continue
        mes = func(eid, it)["meses"].setdefault(it["competence"], {"linhas": [], "base_inss": 0.0, "base_fgts": 0.0})
        mes["linhas"] += _rows(conn, "SELECT codigo, nome, tipo, valor FROM payroll_item_lines WHERE item_id=?",
                               (it["id"],))
        mes["base_inss"] += float(it.get("base_inss") or 0)
    for f in ferias:
        comp_f = (f.get("competencia") or f.get("data_inicio") or "")[:7]
        eid = f["employee_id"]
        if comp_f not in periodo or (filtro and eid not in filtro):
            continue
        mes = func(eid, f)["meses"].setdefault(comp_f, {"linhas": [], "base_inss": 0.0, "base_fgts": 0.0})
        fl = _rows(conn, "SELECT codigo, nome, tipo, valor FROM payroll_special_lines WHERE special_id=?", (f["id"],))
        mes["linhas"] += [dict(l, _ferias=True) for l in fl]
        mes["base_inss"] += sum(float(l["valor"] or 0) for l in fl
                                if l["tipo"] == "provento" and _incide(rubrics, l["codigo"], "incide_inss"))

    results, ignorados = [], []
    for eid, fdados in sorted(funcs.items(), key=lambda kv: kv[1]["employee_name"]):
        if fdados["is_prolabore"]:
            continue
        pct = pcts.get(eid, pct_geral)
        if pct <= 0:
            continue
        if not fdados["active"]:
            ignorados.append({"employee_id": eid, "employee_name": fdados["employee_name"],
                              "motivo": "Funcionário desligado: pague as diferenças em rescisão complementar."})
            continue
        fator = pct / 100.0
        linhas, avisos = [], []
        inss_mes: Dict[str, float] = {}
        base_inss_tot = base_fgts_tot = fgts_tot = 0.0
        rend_ano_atual = rend_anos_ant = inss_ano_atual = inss_anos_ant = 0.0
        meses_ant = 0
        for per in periodo:
            mes = fdados["meses"].get(per)
            if not mes:
                continue
            dif_inss = dif_fgts = dif_irrf = 0.0
            agreg: Dict[tuple, Dict[str, Any]] = {}
            for l in mes["linhas"]:
                cod = str(l["codigo"])
                if cod not in cods or l["tipo"] not in ("provento", "desconto"):
                    continue
                k = (cod, l["tipo"])
                a = agreg.setdefault(k, {"codigo": cod, "nome": l["nome"], "tipo": l["tipo"], "valor": 0.0})
                a["valor"] += float(l["valor"] or 0)
            for (cod, tipo), a in sorted(agreg.items()):
                v = r2(a["valor"] * fator)
                if v <= 0:
                    continue
                sinal = 1 if tipo == "provento" else -1
                linhas.append({"codigo": cod, "nome": f"Dif. {a['nome']} {_fmt_comp(per)}", "tipo": tipo,
                               "referencia": f"{pct:g}%", "valor": v, "origem": "dissidio", "per_ref": per})
                if _incide(rubrics, cod, "incide_inss"):
                    dif_inss += sinal * v
                if _incide(rubrics, cod, "incide_fgts"):
                    dif_fgts += sinal * v
                if _incide(rubrics, cod, "incide_irrf"):
                    dif_irrf += sinal * v
            if not any(l.get("per_ref") == per for l in linhas):
                continue
            t = load_tables(conn, company_id, per)
            base_orig = r2(mes["base_inss"])
            inss_dif = max(0.0, r2(pe.calc_inss(base_orig + max(0.0, dif_inss), t) - pe.calc_inss(base_orig, t)))
            inss_mes[per] = inss_dif
            fgts_tot += max(0.0, dif_fgts) * t.fgts_aliquota
            base_inss_tot += max(0.0, dif_inss)
            base_fgts_tot += max(0.0, dif_fgts)
            if per[:4] == comp_pg[:4]:
                rend_ano_atual += dif_irrf
                inss_ano_atual += inss_dif
            else:
                rend_anos_ant += dif_irrf
                inss_anos_ant += inss_dif
                meses_ant += 1
        if not linhas:
            continue

        # IRRF (regime de caixa, no mês do pagamento)
        irrf = 0.0
        irrf_nome = "IRRF s/ diferenças"
        if rend_ano_atual > 0:
            mensal = _rows(conn, """
                SELECT pi.* FROM payroll_items pi JOIN payroll_runs pr ON pr.id = pi.run_id
                WHERE pr.company_id=? AND pr.competence=? AND pi.employee_id=? AND pr.status != 'cancelado'
                  AND COALESCE(pr.tipo, 'mensal') IN ('mensal', 'complementar')""", (company_id, comp_pg, eid))
            if mensal:
                lin_pg = []
                for it in mensal:
                    lin_pg += _rows(conn, "SELECT codigo, tipo, valor FROM payroll_item_lines WHERE item_id=?",
                                    (it["id"],))
                rend_pg = rendimento_irrf(lin_pg, rubrics)
                inss_pg = sum(float(i.get("inss") or 0) for i in mensal)
                irrf_pg = sum(float(i.get("irrf") or 0) for i in mensal)
                tot = pe.calc_irrf(rend_pg + rend_ano_atual, inss_pg + inss_ano_atual, fdados["dependents"], 0.0, tab_pg)
                irrf = max(0.0, r2(tot["irrf"] - irrf_pg))
                avisos.append(f"IRRF calculado somando as diferenças à folha de {_fmt_comp(comp_pg)}.")
            else:
                irrf = pe.calc_irrf(rend_ano_atual, inss_ano_atual, fdados["dependents"], 0.0, tab_pg)["irrf"]
                avisos.append(f"A folha mensal de {_fmt_comp(comp_pg)} ainda não foi processada: o IRRF das "
                              f"diferenças foi calculado isolado. O ideal é processar o dissídio depois da folha.")
        irrf_rra_v = 0.0
        if rend_anos_ant > 0:
            irrf_rra_v = irrf_rra(rend_anos_ant, inss_anos_ant, meses_ant, tab_pg)
            avisos.append(f"Diferenças de anos anteriores tributadas como RRA (art. 12-A da Lei 7.713/88), "
                          f"{meses_ant} mês(es): IRRF RRA R$ {irrf_rra_v:.2f}. Informe-as como RRA no "
                          f"informe de rendimentos.")
        if irrf_rra_v:
            irrf_nome += f" (inclui RRA R$ {irrf_rra_v:.2f})"
        if any(l.get("_ferias") for m in fdados["meses"].values() for l in m["linhas"]):
            avisos.append("Inclui diferenças de férias gozadas no período.")
        res = _resultado(eid, fdados["employee_name"], linhas, sum(inss_mes.values()), r2(irrf + irrf_rra_v),
                         r2(fgts_tot), base_inss_tot, base_fgts_tot, avisos, irrf_nome, inss_por_mes=inss_mes)
        res["percentual"] = pct
        res["meses"] = sorted({l["per_ref"] for l in linhas if l.get("per_ref")})
        results.append(res)

    sem_folha = [m for m in periodo if not any(m in f["meses"] for f in funcs.values())]
    extra = {
        "competencia_inicio": comp_ini, "competencia_fim": comp_fim,
        "info": {"tp_acordo": tp, "dt_acordo": dt_acordo, "descricao": (dados.get("descricao") or
                 f"{TIPOS_INSTRUMENTO[tp]} — reajuste {pct_geral:g}%").strip()[:255],
                 "percentual": pct_geral, "competencia_inicio": comp_ini, "competencia_fim": comp_fim},
        "meses_sem_folha": sem_folha,
        "rubricas_reajustadas": sorted(cods),
    }
    return _totais(comp_pg, results, ignorados, tab_pg, extra)


def atualizar_salarios(conn, company_id: int, results: List[Dict[str, Any]], competencia_pagamento: str,
                       descricao: str) -> int:
    """Reajusta o salário cadastrado (a partir da competência de pagamento) e registra no histórico."""
    n = 0
    for res in results:
        emp = conn.execute("SELECT salary, role FROM employees WHERE id=? AND company_id=?",
                           (res["employee_id"], company_id)).fetchone()
        if not emp:
            continue
        ant = float(emp["salary"] or 0)
        novo = r2(ant * (1 + float(res.get("percentual") or 0) / 100.0))
        if novo <= ant:
            continue
        conn.execute("""INSERT INTO salary_history (company_id, employee_id, data_vigencia, salario_anterior,
                        salario_novo, tipo, percentual, motivo, cargo_anterior, cargo_novo, aprovado_por)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (company_id, res["employee_id"], f"{competencia_pagamento}-01", ant, novo, "dissidio",
                      res.get("percentual"), descricao[:255], emp["role"] or "", "", "Cortex — dissídio"))
        conn.execute("UPDATE employees SET salary=? WHERE id=?", (novo, res["employee_id"]))
        n += 1
    return n


def info_json(info: Dict[str, Any]) -> str:
    return json.dumps(info, ensure_ascii=False)
