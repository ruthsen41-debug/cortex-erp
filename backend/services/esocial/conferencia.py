"""Conferência folha × eSocial: compara, por trabalhador, o que a folha calculou com o que o eSocial
apurou nos totalizadores devolvidos após o processamento.

- S-5001 (contribuições sociais por trabalhador): bases de INSS (infoBaseCS) e contribuição do
  segurado calculada pelo eSocial (infoCpCalc/vrCpSeg) × descontada na folha (vrDescSeg).
- S-5002 (IRRF por trabalhador): imposto retido nos pagamentos do mês (regime de caixa, vem do S-1210).
- S-5003 (FGTS por trabalhador): base (remFGTS) e depósito (dpsFGTS) de cada mês.

A folha é lida pelas mesmas rotinas que montam o S-1200, o S-2299 e o S-1210, e as bases da folha são
refeitas pelas incidências das rubricas (as mesmas enviadas no S-1010). Assim, uma diferença aponta
para incidência de rubrica, evento não enviado/retificado ou cálculo divergente.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from lxml import etree

from .. import payroll_engine as pe
from . import servico

TOLERANCIA = 0.02          # arredondamento de centavos entre demonstrativos

# S-5001 tpValor: bases de cálculo da contribuição do segurado (as "exclusivas do empregador" ficam fora)
_TP_BASE_SEGURADO = {"11", "12", "13", "14", "19", "41", "42", "43", "44", "49"}
_TP_BASE_13_LEI = {"51", "52", "53", "54"}   # 13º — Lei 14.973/2024 (desoneração), ind13 = 1
_CR_CONSIGNADO = "160601"                    # empréstimo consignado — não é contribuição
# S-5003 tpValor: depósitos do FGTS (11–50); 41–50 é indenização compensatória do doméstico
_TP_FGTS_DOMESTICO_IND = {str(x) for x in range(41, 51)}

_INSS = {pe.SYSTEM_RUBRICS["INSS"][0], pe.SYSTEM_RUBRICS["INSS_13"][0]}


def _so_digitos(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def _r(v: float) -> float:
    return round(float(v or 0) + 0.0, 2)


# ─── leitura dos totalizadores ────────────────────────────────────────────────

def _xp(el, caminho: str) -> List[Any]:
    """XPath por nome local (o XML do retorno vem com o namespace de cada evento)."""
    partes = "/".join(f"*[local-name()='{p}']" for p in caminho.split("/"))
    return el.xpath(f".//{partes}")


def _t(el, nome: str) -> str:
    achou = _xp(el, nome)
    return (achou[0].text or "").strip() if achou else ""


def _num(el, nome: str) -> float:
    try:
        return float(_t(el, nome) or 0)
    except ValueError:
        return 0.0


def _raiz(xml: str):
    try:
        return etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except (etree.XMLSyntaxError, ValueError):
        return None


def ler_s5001(xml: str) -> Optional[Dict[str, Any]]:
    r = _raiz(xml)
    if r is None:
        return None
    out = {"cpf": _so_digitos(_t(r, "ideTrabalhador/cpfTrab")), "per_apur": _t(r, "perApur"),
           "base_inss": 0.0, "base_inss_13": 0.0, "inss_calculado": 0.0, "inss_descontado": 0.0,
           "sal_familia": 0.0, "sal_maternidade": 0.0}
    for b in _xp(r, "infoBaseCS"):
        tp, ind13, v = _t(b, "tpValor"), _t(b, "ind13"), _num(b, "valor")
        if tp in _TP_BASE_SEGURADO or tp in _TP_BASE_13_LEI:
            out["base_inss_13" if (ind13 == "1" or tp in _TP_BASE_13_LEI) else "base_inss"] += v
        elif tp == "31":
            out["sal_familia"] += v
        elif tp == "32":
            out["sal_maternidade"] += v
    for c in _xp(r, "infoCpCalc"):
        if _t(c, "tpCR") == _CR_CONSIGNADO:
            continue
        out["inss_calculado"] += _num(c, "vrCpSeg")
        out["inss_descontado"] += _num(c, "vrDescSeg")
    return {k: (_r(v) if isinstance(v, float) else v) for k, v in out.items()}


def ler_s5002(xml: str) -> Optional[Dict[str, Any]]:
    r = _raiz(xml)
    if r is None:
        return None
    out = {"cpf": _so_digitos(_t(r, "ideTrabalhador/cpfBenef")), "per_apur": _t(r, "perApur"),
           "irrf": 0.0, "rend_tributavel": 0.0}
    # totApurMen fica dentro de cada dmDev; consolidApurMen é a soma deles (não somar os dois)
    for t in _xp(r, "dmDev/totApurMen"):
        out["irrf"] += _num(t, "vlrCRMen") + _num(t, "vlrCR13Men")
        out["rend_tributavel"] += _num(t, "vlrRendTrib") + _num(t, "vlrRendTrib13")
    return {k: (_r(v) if isinstance(v, float) else v) for k, v in out.items()}


def ler_s5003(xml: str) -> Optional[Dict[str, Any]]:
    r = _raiz(xml)
    if r is None:
        return None
    out = {"cpf": _so_digitos(_t(r, "ideTrabalhador/cpfTrab")), "per_apur": _t(r, "perApur"),
           "base_fgts": 0.0, "fgts": 0.0}
    for b in _xp(r, "basePerApur"):
        if _t(b, "tpValor") in _TP_FGTS_DOMESTICO_IND or _t(b, "indIncid") == "9":
            continue
        out["base_fgts"] += _num(b, "remFGTS")
        out["fgts"] += _num(b, "dpsFGTS")
    for b in _xp(r, "basePerAntE"):
        if _t(b, "indIncidE") == "9":
            continue
        out["base_fgts"] += _num(b, "remFGTSE")
        out["fgts"] += _num(b, "dpsFGTSE")
    return {k: (_r(v) if isinstance(v, float) else v) for k, v in out.items()}


_LEITORES = {"S-5001": ler_s5001, "S-5002": ler_s5002, "S-5003": ler_s5003}


def totalizadores_validos(conn, cid: int, per: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Totalizadores por tipo e CPF, somando os de eventos diferentes (S-1200 + S-2299 no mesmo mês) e
    ignorando os de eventos retificados ou excluídos."""
    rows = conn.execute("""
        SELECT t.id, t.tipo, t.per_apur, t.xml FROM esocial_totalizadores t
        LEFT JOIN esocial_eventos ev ON ev.id = t.evento_origem_id AND ev.company_id = t.company_id
        WHERE t.company_id = ? AND t.tipo IN ('S-5001', 'S-5002', 'S-5003')
          AND (t.per_apur = ? OR COALESCE(t.per_apur, '') = '')
          AND COALESCE(ev.status, '') NOT IN ('substituido', 'excluido')
        ORDER BY t.id""", (cid, per)).fetchall()
    out: Dict[str, Dict[str, Dict[str, Any]]] = {k: {} for k in _LEITORES}
    for row in rows:
        d = _LEITORES[row["tipo"]](row["xml"] or "")
        if not d or not d["cpf"] or (d["per_apur"] and d["per_apur"] != per):
            continue
        acc = out[row["tipo"]].setdefault(d["cpf"], {k: 0.0 for k, v in d.items() if isinstance(v, float)})
        for k, v in d.items():
            if isinstance(v, float):
                acc[k] = _r(acc[k] + v)
        acc["qtd"] = acc.get("qtd", 0) + 1
    return out


def consolidados_recebidos(conn, cid: int, per: str) -> Dict[str, bool]:
    return {t: bool(conn.execute("SELECT 1 FROM esocial_totalizadores WHERE company_id = ? AND tipo = ? AND per_apur = ? LIMIT 1",
                                 (cid, t, per)).fetchone()) for t in ("S-5011", "S-5012", "S-5013")}


# ─── lado da folha ────────────────────────────────────────────────────────────

class _Incidencias:
    """Incidências das rubricas da empresa (mesmas do S-1010), com as de sistema como reserva."""

    def __init__(self, conn, cid: int):
        self.rub = pe.load_rubrics(conn, cid)
        self.sys = {v[0]: v for v in pe.SYSTEM_RUBRICS.values()}

    def incide(self, codigo: str, campo: str) -> bool:
        r = self.rub.get(str(codigo))
        if r is not None:
            return bool(r.get(campo))
        s = self.sys.get(str(codigo))
        return bool(s and s[{"incide_inss": 3, "incide_irrf": 4, "incide_fgts": 5}[campo]])


def _novo(nome: str, origem: str) -> Dict[str, Any]:
    return {"nome": nome, "origem": origem, "base_inss": 0.0, "base_inss_13": 0.0, "inss": 0.0,
            "base_fgts": 0.0, "fgts": 0.0, "irrf": 0.0, "aliq_fgts": 0.08, "employee_id": 0}


def _somar_linhas(acc: Dict[str, Any], linhas: Iterable[Dict[str, Any]], inc: _Incidencias, decimo_todo: bool = False) -> None:
    for ln in linhas:
        cod, tipo, v = str(ln.get("codigo") or ""), ln.get("tipo"), float(ln.get("valor") or 0)
        if cod in _INSS:
            acc["inss"] += v
            continue
        if tipo not in ("provento", "desconto"):
            continue
        sinal = 1 if tipo == "provento" else -1
        e13 = decimo_todo or ln.get("grupo") == "decimo"
        if inc.incide(cod, "incide_inss"):
            acc["base_inss_13" if e13 else "base_inss"] += sinal * v
        if inc.incide(cod, "incide_fgts"):
            acc["base_fgts"] += sinal * v


def folha_por_cpf(conn, cid: int, per: str) -> Dict[str, Dict[str, Any]]:
    """Bases e valores da folha por CPF, no mesmo recorte dos eventos enviados ao eSocial."""
    inc = _Incidencias(conn, cid)
    anual = len(per) == 4
    out: Dict[str, Dict[str, Any]] = {}

    def acc_para(cpf: str, nome: str, origem: str, employee_id: int = 0, categ: str = "") -> Dict[str, Any]:
        a = out.setdefault(_so_digitos(cpf), _novo(nome, origem))
        if employee_id:
            a["employee_id"] = employee_id
        if categ == "103":
            a["aliq_fgts"] = 0.02          # aprendiz
        if categ in ("701", "901") or origem in ("rpa", "estagio"):
            a["aliq_fgts"] = 0.0           # autônomo e estagiário não têm FGTS
        return a

    # INSS e FGTS: competência (S-1200) e rescisões do mês (S-2299)
    for g in servico.remuneracoes_do_periodo(conn, cid, per, "2" if anual else "1").values():
        trab = g["trab"]
        origem = {"remuneracao": "folha", "remuneracao_est": "estagio", "remuneracao_rpa": "rpa"}.get(g["ref_tipo"], "folha")
        categ = (g["dm_devs"][0].get("cod_categ") if g["dm_devs"] else "") or ""
        a = acc_para(trab.get("cpf"), trab.get("nome") or "", origem, g.get("employee_id") or 0, str(categ))
        for dm in g["dm_devs"]:
            _somar_linhas(a, dm["linhas"], inc, decimo_todo=anual)
    if not anual:
        for sp in conn.execute("""SELECT ps.id, ps.employee_id, e.name, e.cpf, e.esocial_category FROM payroll_special ps
                                  JOIN employees e ON e.id = ps.employee_id
                                  WHERE ps.company_id = ? AND ps.tipo = 'rescisao' AND ps.status != 'cancelado'
                                    AND substr(ps.data_inicio, 1, 7) = ?""", (cid, per)).fetchall():
            a = acc_para(sp["cpf"], sp["name"], "folha", sp["employee_id"], str(sp["esocial_category"] or ""))
            _somar_linhas(a, servico._linhas_especial(conn, sp["id"]), inc)

        # IRRF: pagamentos feitos no mês (S-1210 → S-5002)
        for r in conn.execute("""SELECT pi.employee_id, pi.irrf, e.name, e.cpf FROM payroll_items pi
                                 JOIN payroll_runs pr ON pr.id = pi.run_id JOIN employees e ON e.id = pi.employee_id
                                 WHERE pr.company_id = ? AND pr.status != 'cancelado'
                                   AND COALESCE(pr.tipo, 'mensal') IN ('mensal', 'complementar', 'dissidio')
                                   AND substr(COALESCE(pr.data_pagamento, ''), 1, 7) = ?""", (cid, per)).fetchall():
            acc_para(r["cpf"], r["name"], "folha", r["employee_id"])["irrf"] += float(r["irrf"] or 0)
        for r in conn.execute("""SELECT ps.employee_id, ps.irrf, e.name, e.cpf FROM payroll_special ps
                                 JOIN employees e ON e.id = ps.employee_id
                                 WHERE ps.company_id = ? AND ps.status != 'cancelado'
                                   AND ps.tipo IN ('ferias', 'decimo_1', 'decimo_2', 'rescisao')
                                   AND substr(COALESCE(ps.data_pagamento, ''), 1, 7) = ?""", (cid, per)).fetchall():
            acc_para(r["cpf"], r["name"], "folha", r["employee_id"])["irrf"] += float(r["irrf"] or 0)
        for r in conn.execute("""SELECT r.irrf_retido, a.nome, a.cpf FROM rpa_payments r
                                 JOIN autonomous_workers a ON a.id = r.autonomous_id
                                 WHERE r.company_id = ? AND substr(COALESCE(r.data_pagamento, ''), 1, 7) = ?""",
                              (cid, per)).fetchall():
            acc_para(r["cpf"], r["nome"], "rpa")["irrf"] += float(r["irrf_retido"] or 0)

    for a in out.values():
        for k in ("base_inss", "base_inss_13", "base_fgts", "inss", "irrf"):
            a[k] = _r(max(0.0, a[k]))
        a["fgts"] = _r(a["base_fgts"] * a["aliq_fgts"])
        if not a["aliq_fgts"]:
            a["base_fgts"] = 0.0
    return out


# ─── comparação ───────────────────────────────────────────────────────────────

_ITENS = (  # (chave, rótulo, totalizador, campo da folha, campo do eSocial)
    ("base_inss", "Base do INSS", "S-5001", "base_inss", "base_inss"),
    ("base_inss_13", "Base do INSS — 13º", "S-5001", "base_inss_13", "base_inss_13"),
    ("inss", "INSS do segurado", "S-5001", "inss", "inss_calculado"),
    ("irrf", "IRRF retido", "S-5002", "irrf", "irrf"),
    ("base_fgts", "Base do FGTS", "S-5003", "base_fgts", "base_fgts"),
    ("fgts", "FGTS", "S-5003", "fgts", "fgts"),
)

_DICAS = {
    "base_inss": "Confira a incidência de INSS (codIncCP) das rubricas no S-1010 e se todos os S-1200/S-2299 do mês foram aceitos.",
    "base_inss_13": "Confira a incidência de INSS do 13º das rubricas e o S-1200 anual (13º).",
    "inss": "O eSocial recalculou o INSS: veja o teto, as faixas da tabela do mês e outros vínculos (infoMV).",
    "irrf": "O IRRF segue a data de pagamento (S-1210): confira as datas, as deduções de dependentes e se o S-1210 foi aceito.",
    "base_fgts": "Confira a incidência de FGTS (codIncFGTS) das rubricas no S-1010 e se o S-1200/S-2299 foi aceito.",
    "fgts": "Depósito do FGTS diferente: veja a categoria (aprendiz 2%) e a base.",
}


def conferir(conn, cid: int, per: str) -> Dict[str, Any]:
    if not re.fullmatch(r"\d{4}(-(0[1-9]|1[0-2]))?", per or ""):
        raise ValueError("Competência inválida. Use AAAA-MM (ou AAAA para o 13º anual).")
    folha = folha_por_cpf(conn, cid, per)
    tot = totalizadores_validos(conn, cid, per)
    nomes = {_so_digitos(r["cpf"]): (r["name"], r["id"]) for r in conn.execute(
        "SELECT id, name, cpf FROM employees WHERE company_id = ?", (cid,)).fetchall()}
    itens = [i for i in _ITENS if not (len(per) == 4 and i[2] == "S-5002")]
    cpfs = set(folha) | set().union(*(set(tot[t]) for t in tot))
    linhas, totais = [], {i[0]: {"folha": 0.0, "esocial": 0.0} for i in itens}
    for cpf in cpfs:
        f = folha.get(cpf)
        nome = f["nome"] if f else nomes.get(cpf, ("CPF " + cpf, 0))[0]
        lin = {"cpf": cpf, "nome": nome, "employee_id": (f or {}).get("employee_id") or nomes.get(cpf, ("", 0))[1],
               "origem": (f or {}).get("origem", "esocial"), "valores": {}, "divergencias": [], "faltando": []}
        for chave, rot, tp, cf, ce in itens:
            vf = f.get(cf, 0.0) if f else 0.0
            t = tot[tp].get(cpf)
            ve = t.get(ce, 0.0) if t else None
            if t is None and vf == 0:
                continue
            lin["valores"][chave] = {"folha": vf, "esocial": ve, "diferenca": None if ve is None else _r(ve - vf)}
            totais[chave]["folha"] = _r(totais[chave]["folha"] + vf)
            if ve is not None:
                totais[chave]["esocial"] = _r(totais[chave]["esocial"] + ve)
            if t is None:
                if tp not in lin["faltando"]:
                    lin["faltando"].append(tp)
            elif abs(ve - vf) > TOLERANCIA:
                lin["divergencias"].append({"item": chave, "rotulo": rot, "totalizador": tp, "folha": vf,
                                            "esocial": ve, "diferenca": _r(ve - vf), "dica": _DICAS[chave]})
        if not lin["valores"]:
            continue
        if f is None:
            lin["situacao"] = "so_esocial"
        elif lin["divergencias"]:
            lin["situacao"] = "divergente"
        elif lin["faltando"]:
            lin["situacao"] = "sem_totalizador"
        else:
            lin["situacao"] = "ok"
        linhas.append(lin)
    ordem = {"divergente": 0, "so_esocial": 1, "sem_totalizador": 2, "ok": 3}
    linhas.sort(key=lambda x: (ordem[x["situacao"]], x["nome"]))
    contagem = {k: sum(1 for x in linhas if x["situacao"] == k) for k in ordem}
    consolidados = consolidados_recebidos(conn, cid, per) if len(per) == 7 else {}
    return {"competencia": per, "itens": [{"chave": i[0], "rotulo": i[1], "totalizador": i[2]} for i in itens],
            "linhas": linhas, "totais": totais, "contagem": contagem, "consolidados": consolidados,
            "pode_fechar": bool(linhas) and contagem["ok"] == len(linhas),
            "observacao": ("O IRRF é conferido pelo mês do pagamento (regime de caixa): a folha paga no mês seguinte "
                           "aparece na conferência daquele mês." if len(per) == 7 else
                           "13º anual: só INSS e FGTS; o IRRF do 13º entra no mês do pagamento.")}


def csv_conferencia(dados: Dict[str, Any]) -> str:
    cab = ["Nome", "CPF", "Situação"]
    for i in dados["itens"]:
        cab += [f"{i['rotulo']} folha", f"{i['rotulo']} eSocial", f"{i['rotulo']} diferença"]
    sit = {"ok": "Confere", "divergente": "Divergente", "sem_totalizador": "Sem totalizador", "so_esocial": "Só no eSocial"}
    br = lambda v: "" if v is None else f"{v:.2f}".replace(".", ",")
    out = [";".join(cab)]
    for l in dados["linhas"]:
        cols = [l["nome"].replace(";", ","), l["cpf"], sit[l["situacao"]]]
        for i in dados["itens"]:
            v = l["valores"].get(i["chave"]) or {}
            cols += [br(v.get("folha")), br(v.get("esocial")), br(v.get("diferenca"))]
        out.append(";".join(cols))
    return "﻿" + "\r\n".join(out) + "\r\n"
