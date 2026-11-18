"""
Relatórios da folha (equivalentes ao menu Relatórios > Folha / Férias / Rescisão dos sistemas de DP).

Cada relatório monta uma estrutura de tabela única
    {titulo, subtitulo, colunas: [{k, rot, num}], linhas: [{..., "_cls": "" | "grupo" | "sub" | "tot"}]}
que vira HTML para imprimir (A4) ou CSV para planilha (separador ";" e vírgula decimal, como o
Excel em português abre).
"""
from __future__ import annotations

import csv
import io
import json
from html import escape
from typing import Any, Dict, List, Optional

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
TIPOS_ESPECIAL = {"decimo_1": "13º 1ª parcela", "decimo_2": "13º 2ª parcela", "ferias": "Férias",
                  "rescisao": "Rescisão", "rescisao_compl": "Rescisão complementar"}
NOMES_RESCISAO = {"sem_justa_causa": "Sem justa causa", "pedido_demissao": "Pedido de demissão",
                  "com_justa_causa": "Justa causa", "acordo": "Acordo (484-A)", "termino_contrato": "Término de contrato"}


def _rows(conn, sql: str, params=()) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _col(k, rot, num=False):
    return {"k": k, "rot": rot, "num": num}


# ── 1. Relação de líquidos ───────────────────────────────────────────────────
def liquidos(conn, company_id: int, run_id: int) -> Optional[Dict[str, Any]]:
    run = conn.execute("SELECT * FROM payroll_runs WHERE id=? AND company_id=?", (run_id, company_id)).fetchone()
    if not run:
        return None
    run = dict(run)
    itens = _rows(conn, """SELECT e.matricula, e.name, e.cpf, e.bank_name, e.bank_agency, e.bank_account, pi.net_salary
                           FROM payroll_items pi JOIN employees e ON e.id = pi.employee_id
                           WHERE pi.run_id=? ORDER BY e.name""", (run_id,))
    linhas = [{"matricula": i.get("matricula") or "", "nome": i["name"], "cpf": i.get("cpf") or "",
               "banco": i.get("bank_name") or "", "agencia": i.get("bank_agency") or "",
               "conta": i.get("bank_account") or "", "liquido": _f(i["net_salary"])} for i in itens]
    sem_conta = sum(1 for l in linhas if not l["conta"])
    linhas.append({"_cls": "tot", "nome": f"Total — {len(itens)} funcionário(s)",
                   "liquido": round(sum(l["liquido"] for l in linhas), 2)})
    tipo = (run.get("tipo") or "mensal").capitalize()
    return {"titulo": "Relação de líquidos", "subtitulo": f"Folha {run['competence']} · {tipo}",
            "nota": f"{sem_conta} funcionário(s) sem conta bancária no cadastro." if sem_conta else "",
            "colunas": [_col("matricula", "Matrícula"), _col("nome", "Funcionário"), _col("cpf", "CPF"),
                        _col("banco", "Banco"), _col("agencia", "Agência"), _col("conta", "Conta"),
                        _col("liquido", "Líquido", True)], "linhas": linhas}


# ── 2. Ficha financeira anual ────────────────────────────────────────────────
def ficha_financeira(conn, company_id: int, employee_id: int, ano: int) -> Optional[Dict[str, Any]]:
    emp = conn.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (employee_id, company_id)).fetchone()
    if not emp:
        return None
    emp = dict(emp)
    lanc = _rows(conn, """SELECT l.codigo, l.nome, l.tipo, l.valor, pr.competence AS comp
                          FROM payroll_item_lines l JOIN payroll_runs pr ON pr.id = l.run_id
                          WHERE pr.company_id=? AND l.employee_id=? AND pr.competence LIKE ? AND pr.status != 'cancelado'""",
                 (company_id, employee_id, f"{ano}-%"))
    lanc += _rows(conn, """SELECT sl.codigo, sl.nome, sl.tipo, sl.valor,
                                  COALESCE(NULLIF(ps.competencia, ''), substr(ps.data_inicio, 1, 7)) AS comp
                           FROM payroll_special_lines sl JOIN payroll_special ps ON ps.id = sl.special_id
                           WHERE ps.company_id=? AND ps.employee_id=? AND ps.status != 'cancelado'
                             AND COALESCE(NULLIF(ps.competencia, ''), substr(ps.data_inicio, 1, 7)) LIKE ?""",
                  (company_id, employee_id, f"{ano}-%"))
    rub: Dict[tuple, Dict[str, Any]] = {}
    for l in lanc:
        if l["tipo"] not in ("provento", "desconto"):
            continue
        try:
            m = int(str(l["comp"])[5:7])
        except ValueError:
            continue
        k = (l["tipo"], str(l["codigo"]))
        r = rub.setdefault(k, {"codigo": l["codigo"], "rubrica": l["nome"], **{f"m{i}": 0.0 for i in range(1, 13)}})
        r[f"m{m}"] = round(r[f"m{m}"] + _f(l["valor"]), 2)
    linhas: List[Dict[str, Any]] = []
    tot = {"provento": {f"m{i}": 0.0 for i in range(1, 13)}, "desconto": {f"m{i}": 0.0 for i in range(1, 13)}}
    for tipo, rot in (("provento", "Proventos"), ("desconto", "Descontos")):
        linhas.append({"_cls": "grupo", "codigo": rot})
        for k in sorted(k for k in rub if k[0] == tipo):
            r = rub[k]
            r["total"] = round(sum(r[f"m{i}"] for i in range(1, 13)), 2)
            linhas.append(r)
            for i in range(1, 13):
                tot[tipo][f"m{i}"] += r[f"m{i}"]
        linhas.append({"_cls": "sub", "rubrica": f"Total de {rot.lower()}",
                       **{c: round(v, 2) for c, v in tot[tipo].items()},
                       "total": round(sum(tot[tipo].values()), 2)})
    liq = {f"m{i}": round(tot["provento"][f"m{i}"] - tot["desconto"][f"m{i}"], 2) for i in range(1, 13)}
    linhas.append({"_cls": "tot", "rubrica": "Líquido", **liq, "total": round(sum(liq.values()), 2)})
    return {"titulo": f"Ficha financeira {ano}",
            "subtitulo": f"{emp.get('matricula') or emp['id']} · {emp['name']} · CPF {emp.get('cpf') or ''} · "
                         f"{emp.get('role') or ''}",
            "nota": "Inclui folhas mensais, complementares, férias, 13º e rescisão, pelo mês de competência.",
            "paisagem": True,
            "colunas": [_col("codigo", "Cód."), _col("rubrica", "Rubrica")]
                       + [_col(f"m{i}", MESES[i - 1], True) for i in range(1, 13)] + [_col("total", "Total", True)],
            "linhas": linhas}


# ── 3. Lançamentos por rubrica ───────────────────────────────────────────────
def lancamentos(conn, company_id: int, competencia: str, codigo: str = "") -> Dict[str, Any]:
    sql = """SELECT l.codigo, l.nome, l.tipo, l.referencia, l.valor, e.name AS funcionario, e.matricula,
                    COALESCE(pr.tipo, 'mensal') AS folha
             FROM payroll_item_lines l JOIN payroll_runs pr ON pr.id = l.run_id JOIN employees e ON e.id = l.employee_id
             WHERE pr.company_id=? AND pr.competence=? AND pr.status != 'cancelado' AND l.tipo IN ('provento','desconto')"""
    params: List[Any] = [company_id, competencia]
    if codigo:
        sql += " AND l.codigo=?"
        params.append(codigo)
    dados = _rows(conn, sql + " ORDER BY l.tipo DESC, l.codigo, e.name", params)
    linhas: List[Dict[str, Any]] = []
    atual, soma, total = None, 0.0, {"provento": 0.0, "desconto": 0.0}
    for d in dados:
        if d["codigo"] != atual:
            if atual is not None:
                linhas.append({"_cls": "sub", "funcionario": "Subtotal", "valor": round(soma, 2)})
            linhas.append({"_cls": "grupo", "codigo": d["codigo"], "funcionario": f"{d['nome']} ({d['tipo']})"})
            atual, soma = d["codigo"], 0.0
        soma += _f(d["valor"])
        total[d["tipo"]] += _f(d["valor"])
        linhas.append({"codigo": "", "matricula": d.get("matricula") or "", "funcionario": d["funcionario"],
                       "folha": d["folha"], "referencia": d.get("referencia") or "", "valor": _f(d["valor"])})
    if atual is not None:
        linhas.append({"_cls": "sub", "funcionario": "Subtotal", "valor": round(soma, 2)})
    linhas.append({"_cls": "tot", "funcionario": "Total de proventos", "valor": round(total["provento"], 2)})
    linhas.append({"_cls": "tot", "funcionario": "Total de descontos", "valor": round(total["desconto"], 2)})
    return {"titulo": "Lançamentos por rubrica", "subtitulo": f"Competência {competencia}" + (f" · rubrica {codigo}" if codigo else ""),
            "colunas": [_col("codigo", "Cód."), _col("matricula", "Matrícula"), _col("funcionario", "Funcionário"),
                        _col("folha", "Folha"), _col("referencia", "Ref."), _col("valor", "Valor", True)],
            "linhas": linhas}


# ── 4. Resumo de férias ──────────────────────────────────────────────────────
def resumo_ferias(conn, company_id: int, inicio: str, fim: str) -> Dict[str, Any]:
    dados = _rows(conn, """SELECT ps.*, e.name, e.matricula FROM payroll_special ps JOIN employees e ON e.id = ps.employee_id
                           WHERE ps.company_id=? AND ps.tipo='ferias' AND ps.status != 'cancelado'
                             AND ps.data_inicio >= ? AND ps.data_inicio <= ? ORDER BY ps.data_inicio, e.name""",
                  (company_id, inicio, fim))
    linhas = []
    for d in dados:
        try:
            p = json.loads(d.get("params") or "{}")
        except ValueError:
            p = {}
        linhas.append({"funcionario": d["name"], "aquisitivo": f"{_br(d.get('referencia'))} a {_br(p.get('periodo_fim'))}",
                       "gozo": f"{_br(d.get('data_inicio'))} a {_br(d.get('data_fim'))}", "dias": int(d.get("dias_gozo") or 0),
                       "abono": int(d.get("dias_abono") or 0), "pagamento": _br(d.get("data_pagamento")),
                       "bruto": _f(d["total_proventos"]), "inss": _f(d["inss"]), "irrf": _f(d["irrf"]),
                       "liquido": _f(d["liquido"]), "fgts": _f(d["fgts"])})
    linhas.append({"_cls": "tot", "funcionario": f"Total — {len(dados)} recibo(s)",
                   **{k: round(sum(l[k] for l in linhas), 2) for k in ("bruto", "inss", "irrf", "liquido", "fgts")},
                   "dias": sum(l["dias"] for l in linhas), "abono": sum(l["abono"] for l in linhas)})
    return {"titulo": "Resumo de férias", "subtitulo": f"Início do gozo de {_br(inicio)} a {_br(fim)}", "paisagem": True,
            "colunas": [_col("funcionario", "Funcionário"), _col("aquisitivo", "Período aquisitivo"), _col("gozo", "Gozo"),
                        _col("dias", "Dias", True), _col("abono", "Abono", True), _col("pagamento", "Pagamento"),
                        _col("bruto", "Bruto", True), _col("inss", "INSS", True), _col("irrf", "IRRF", True),
                        _col("liquido", "Líquido", True), _col("fgts", "FGTS", True)], "linhas": linhas}


# ── 5. Relação de rescisões ──────────────────────────────────────────────────
def rescisoes(conn, company_id: int, inicio: str, fim: str) -> Dict[str, Any]:
    dados = _rows(conn, """SELECT ps.*, e.name, e.matricula FROM payroll_special ps JOIN employees e ON e.id = ps.employee_id
                           WHERE ps.company_id=? AND ps.tipo IN ('rescisao','rescisao_compl') AND ps.status != 'cancelado'
                             AND ps.data_inicio >= ? AND ps.data_inicio <= ? ORDER BY ps.data_inicio, e.name, ps.id""",
                  (company_id, inicio, fim))
    linhas = []
    for d in dados:
        try:
            p = json.loads(d.get("params") or "{}")
        except ValueError:
            p = {}
        compl = d["tipo"] == "rescisao_compl"
        linhas.append({"funcionario": d["name"] + (" (complementar)" if compl else ""),
                       "tipo": p.get("motivo_nome", "") if compl else NOMES_RESCISAO.get(d.get("referencia") or "", d.get("referencia") or ""),
                       "desligamento": _br(d.get("data_inicio")), "projecao": "" if compl else _br(d.get("data_fim")),
                       "aviso": "" if compl else (p.get("aviso_modo") or ""),
                       "bruto": _f(d["total_proventos"]), "descontos": _f(d["total_descontos"]), "liquido": _f(d["liquido"]),
                       "fgts": _f(d["fgts"]), "multa": _f(d["multa_fgts"])})
    n = sum(1 for d in dados if d["tipo"] == "rescisao")
    linhas.append({"_cls": "tot", "funcionario": f"Total — {n} rescisão(ões)",
                   **{k: round(sum(l[k] for l in linhas), 2) for k in ("bruto", "descontos", "liquido", "fgts", "multa")}})
    return {"titulo": "Relação de rescisões", "subtitulo": f"Desligamentos de {_br(inicio)} a {_br(fim)}", "paisagem": True,
            "colunas": [_col("funcionario", "Funcionário"), _col("tipo", "Tipo / motivo"), _col("desligamento", "Desligamento"),
                        _col("projecao", "Projeção"), _col("aviso", "Aviso"), _col("bruto", "Bruto", True),
                        _col("descontos", "Descontos", True), _col("liquido", "Líquido", True), _col("fgts", "FGTS", True),
                        _col("multa", "Multa FGTS", True)], "linhas": linhas}


# ── Saída ────────────────────────────────────────────────────────────────────
def _br(d) -> str:
    s = str(d or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) == 10 and s[4] == "-" else s


def _num(v, csv_: bool = False) -> str:
    if v in (None, ""):
        return ""
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    n = _f(v)
    if not csv_ and n == 0:
        return ""
    s = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", "." if not csv_ else "")
    return s


CSS = """*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;color:#000;margin:0;font-size:10px}
.no-print{max-width:1100px;margin:14px auto 8px;text-align:right}
.no-print button{padding:7px 14px;font-weight:bold;cursor:pointer;border:1px solid #555;background:#f3f3f3;border-radius:4px}
.doc{max-width:1100px;margin:0 auto 24px;padding:0 10px}
.hdr{display:flex;justify-content:space-between;align-items:flex-end;border:1.2px solid #000;padding:6px 8px}
.hdr .rs{font-size:12px;font-weight:bold}.hdr h1{font-size:13px;margin:0;text-align:right}
.sub{border:1.2px solid #000;border-top:none;padding:3px 8px;font-size:9.5px;display:flex;justify-content:space-between}
table{border-collapse:collapse;width:100%;margin-top:6px}
th{font-size:8.5px;text-transform:uppercase;border-bottom:1.2px solid #000;text-align:left;padding:3px 4px}
td{padding:2px 4px;border-bottom:1px dotted #ccc;font-size:9.5px}
.num{text-align:right;font-family:"Courier New",monospace;white-space:nowrap}
tr.grupo td{font-weight:bold;background:#efefef;border-bottom:1px solid #000;-webkit-print-color-adjust:exact;print-color-adjust:exact}
tr.sub td{font-weight:bold;border-top:1px solid #000}
tr.tot td{font-weight:bold;border-top:1.5px solid #000;border-bottom:none;font-size:10px}
.nota{font-size:9px;color:#333;margin-top:6px}
@media print{.no-print{display:none}.doc{max-width:none;padding:0;margin:0}}"""


def para_html(rel: Dict[str, Any], empresa: Dict[str, Any], emitido_em: str) -> str:
    cols = rel["colunas"]
    cab = "".join(f'<th class="{"num" if c["num"] else ""}">{escape(c["rot"])}</th>' for c in cols)
    corpo = []
    for l in rel["linhas"]:
        cls = l.get("_cls", "")
        tds = "".join(
            f'<td class="num">{_num(l.get(c["k"]))}</td>' if c["num"] else f'<td>{escape(str(l.get(c["k"], "") or ""))}</td>'
            for c in cols)
        corpo.append(f'<tr class="{cls}">{tds}</tr>')
    if len(rel["linhas"]) <= 1:
        corpo.insert(0, f'<tr><td colspan="{len(cols)}" style="text-align:center;padding:14px;color:#555">Nenhum registro no período.</td></tr>')
    pagina = "@page{size:A4 landscape;margin:9mm}" if rel.get("paisagem") else "@page{size:A4;margin:10mm}"
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>{escape(rel['titulo'])}</title>
<style>{CSS}@media print{{{pagina}}}</style></head><body>
<div class="no-print"><button onclick="window.print()">Imprimir / Salvar PDF</button></div>
<div class="doc">
  <div class="hdr"><div><div class="rs">{escape(empresa.get('razao_social') or '')}</div>CNPJ {escape(empresa.get('cnpj') or '')}</div>
    <h1>{escape(rel['titulo'])}</h1></div>
  <div class="sub"><span>{escape(rel.get('subtitulo') or '')}</span><span>Emitido em {escape(emitido_em)}</span></div>
  <table><thead><tr>{cab}</tr></thead><tbody>{''.join(corpo)}</tbody></table>
  {f'<div class="nota">{escape(rel["nota"])}</div>' if rel.get('nota') else ''}
</div></body></html>"""


def para_csv(rel: Dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow([rel["titulo"], rel.get("subtitulo") or ""])
    w.writerow([c["rot"] for c in rel["colunas"]])
    for l in rel["linhas"]:
        w.writerow([_num(l.get(c["k"]), csv_=True) if c["num"] else str(l.get(c["k"], "") or "") for c in rel["colunas"]])
    return "﻿" + buf.getvalue()
