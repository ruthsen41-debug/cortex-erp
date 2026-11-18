"""Impressos da folha no padrão Domínio: Recibo de Pagamento de Salário (holerite, 2 vias)
e Folha de Pagamento analítica com resumo geral e encargos da competência."""
from datetime import date, datetime
from html import escape as _esc
from typing import Any, Dict, List

MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]
TIPOS_FOLHA = {"mensal": "Folha mensal", "adiantamento": "Adiantamento", "13_1": "13º salário — 1ª parcela",
               "13_2": "13º salário — 2ª parcela", "complementar": "Folha complementar"}

# Códigos informativos gravados pelo motor de rubricas
COD_BASE_INSS, COD_BASE_IRRF, COD_BASE_FGTS, COD_FGTS = "0201", "0202", "0203", "0200"

# Encargos patronais usados no restante do sistema (GPS/SEFIP)
ALIQ_PATRONAL, ALIQ_RAT, ALIQ_TERCEIROS = 0.20, 0.03, 0.058


def _txt(v) -> str:
    return "" if v is None else str(v).strip()


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _brl(v, vazio_se_zero=False) -> str:
    v = _f(v)
    if vazio_se_zero and not v:
        return ""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data(v) -> str:
    v = _txt(v)
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return v


def competencia_extenso(comp: str) -> str:
    try:
        ano, mes = comp.split("-")[:2]
        return f"{MESES[int(mes)]}/{ano}"
    except (ValueError, IndexError):
        return comp


def linhas_do_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rubricas do holerite; folhas antigas (antes do motor de rubricas) são remontadas pelos totais."""
    lines = item.get("lines") or []
    if lines:
        return lines
    out = [{"codigo": "0001", "nome": "Salário", "tipo": "provento", "referencia": "30d", "valor": item.get("gross_salary")}]
    for cod, nome, campo in (("0100", "INSS", "inss"), ("0101", "IRRF", "irrf"),
                             ("0102", "Vale-transporte", "vt_discount"), ("0199", "Outros descontos", "other_discounts")):
        if _f(item.get(campo)):
            out.append({"codigo": cod, "nome": nome, "tipo": "desconto", "referencia": "", "valor": item.get(campo)})
    for cod, nome, campo in ((COD_BASE_INSS, "Base INSS", "base_inss"), (COD_BASE_IRRF, "Base IRRF", "base_irrf"),
                             (COD_BASE_FGTS, "Base FGTS", "base_fgts"), (COD_FGTS, "FGTS", "fgts")):
        if _f(item.get(campo)):
            out.append({"codigo": cod, "nome": nome, "tipo": "informativo", "referencia": "", "valor": item.get(campo)})
    return out


def _info(item, lines, cod, campo) -> float:
    for ln in lines:
        if ln.get("tipo") == "informativo" and _txt(ln.get("codigo")) == cod:
            return _f(ln.get("valor"))
    return _f(item.get(campo))


def _totais(item, lines):
    prov = sum(_f(ln.get("valor")) for ln in lines if ln.get("tipo") == "provento")
    desc = sum(_f(ln.get("valor")) for ln in lines if ln.get("tipo") == "desconto")
    return prov or _f(item.get("gross_salary")), desc


def _cabecalho_empresa(co: Dict[str, Any]) -> str:
    end = ", ".join(p for p in (_txt(co.get("logradouro")), _txt(co.get("numero")), _txt(co.get("bairro"))) if p)
    cid = "/".join(p for p in (_txt(co.get("cidade")), _txt(co.get("uf"))) if p)
    return _esc(" — ".join(p for p in (end, cid) if p))


# ─── Recibo de pagamento (holerite) ───────────────────────────────────────────

RECIBO_CSS = """*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;color:#000;background:#e5e7eb;margin:0;font-size:10px}
.no-print{max-width:780px;margin:16px auto 8px;display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#333}
.no-print button{padding:8px 16px;cursor:pointer;font-weight:bold;border:1px solid #555;background:#fff;border-radius:4px}
.folha{width:780px;margin:0 auto 18px;background:#fff;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,.15)}
.via{display:flex;border:1.2px solid #000}
.corpo{flex:1;min-width:0}
.lateral{width:54px;border-left:1.2px solid #000;position:relative}
.lateral div{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) rotate(-90deg);white-space:nowrap;
  font-size:8.5px;text-align:center;line-height:1.9}
table{width:100%;border-collapse:collapse;table-layout:fixed}
td,th{border:1px solid #000;padding:2px 5px}
.cab td{border-top:none;border-left:none}
.cab td:last-child{border-right:none}
.tit{font-size:12px;font-weight:bold;text-align:right}
.rot{display:block;font-size:7.5px;text-transform:uppercase;color:#333}
.val{font-size:10.5px;font-weight:bold}
.mov th{font-size:8px;text-transform:uppercase;background:#efefef;font-weight:bold;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
.mov td{border-top:none;border-bottom:none;font-size:10px;height:15px}
.mov tr.fill td{height:auto}
.num{text-align:right;font-family:"Courier New",monospace;font-size:10.5px}
.tot td{border-top:1px solid #000;border-bottom:1px solid #000}
.liq{font-weight:bold;font-size:11px}
.bases td{text-align:center;border-bottom:none}
.bases td:first-child{border-left:none}.bases td:last-child{border-right:none}
.via-nome{font-size:7.5px;text-align:right;color:#444;margin-top:2px}
.corte{border-top:1px dashed #777;margin:12px 0;position:relative;height:0}
.corte span{position:absolute;left:50%;top:-7px;transform:translateX(-50%);background:#fff;padding:0 8px;font-size:8px;color:#777}
@media print{body{background:#fff}.no-print{display:none}.folha{box-shadow:none;margin:0;padding:0;width:auto;page-break-after:always}
  .folha:last-child{page-break-after:auto}@page{size:A4;margin:10mm}}"""

LINHAS_MIN_RECIBO = 12


def _recibo_via(co, run, it, via: str) -> str:
    lines = linhas_do_item(it)
    mov = [ln for ln in lines if ln.get("tipo") in ("provento", "desconto")]
    prov, desc = _totais(it, lines)
    liquido = _f(it.get("net_salary")) if it.get("net_salary") is not None else prov - desc
    corpo = "".join(
        f'<tr><td>{_esc(_txt(ln.get("codigo")))}</td><td>{_esc(_txt(ln.get("nome")))}</td>'
        f'<td class="num">{_esc(_txt(ln.get("referencia")))}</td>'
        f'<td class="num">{_brl(ln.get("valor")) if ln.get("tipo") == "provento" else ""}</td>'
        f'<td class="num">{_brl(ln.get("valor")) if ln.get("tipo") == "desconto" else ""}</td></tr>'
        for ln in mov)
    corpo += '<tr><td></td><td></td><td></td><td></td><td></td></tr>' * max(0, LINHAS_MIN_RECIBO - len(mov))

    base_inss = _info(it, lines, COD_BASE_INSS, "base_inss")
    base_fgts = _info(it, lines, COD_BASE_FGTS, "base_fgts")
    base_irrf = _info(it, lines, COD_BASE_IRRF, "base_irrf")
    fgts = _info(it, lines, COD_FGTS, "fgts")
    comp = competencia_extenso(_txt(run.get("competence")))
    tipo = TIPOS_FOLHA.get(_txt(run.get("tipo")) or "mensal", _txt(run.get("tipo")))
    func = " / ".join(p for p in (_txt(it.get("role")), _txt(it.get("department"))) if p)
    return f"""
<div class="via"><div class="corpo">
  <table class="cab"><colgroup><col style="width:62%"><col></colgroup>
    <tr><td><span class="rot">Empregador</span><span class="val">{_esc(_txt(co.get("razao_social")))}</span><br>
      CNPJ: {_esc(_txt(co.get("cnpj")))} &nbsp; {_cabecalho_empresa(co)}</td>
      <td class="tit">Recibo de Pagamento de Salário<br><span style="font-weight:normal;font-size:10px">
      Referente a: <b>{_esc(comp)}</b> · {_esc(tipo)}</span></td></tr>
  </table>
  <table class="cab"><colgroup><col style="width:14%"><col style="width:38%"><col style="width:10%"><col style="width:24%"><col></colgroup>
    <tr><td><span class="rot">Código</span><span class="val">{_esc(_txt(it.get("matricula")) or str(it.get("employee_id", "")))}</span></td>
      <td><span class="rot">Nome do funcionário</span><span class="val">{_esc(_txt(it.get("employee_name")))}</span></td>
      <td><span class="rot">CBO</span>{_esc(_txt(it.get("cbo")))}</td>
      <td><span class="rot">Cargo / Departamento</span>{_esc(func)}</td>
      <td><span class="rot">Admissão</span>{_esc(_data(it.get("admission_date")))}</td></tr>
  </table>
  <table class="mov"><colgroup><col style="width:9%"><col style="width:45%"><col style="width:12%"><col style="width:17%"><col></colgroup>
    <tr><th>Cód.</th><th style="text-align:left">Descrição</th><th>Referência</th><th>Vencimentos</th><th>Descontos</th></tr>
    {corpo}
    <tr class="tot"><td colspan="3" style="text-align:right;font-size:8px;text-transform:uppercase">Total de vencimentos / descontos</td>
      <td class="num">{_brl(prov)}</td><td class="num">{_brl(desc)}</td></tr>
    <tr class="tot"><td colspan="3" style="text-align:right" class="liq">Valor líquido &rArr;</td>
      <td colspan="2" class="num liq" style="font-size:12px">R$ {_brl(liquido)}</td></tr>
  </table>
  <table class="bases"><tr>
    <td><span class="rot">Salário base</span>{_brl(it.get("salary"))}</td>
    <td><span class="rot">Sal. contr. INSS</span>{_brl(base_inss)}</td>
    <td><span class="rot">Base cálc. FGTS</span>{_brl(base_fgts)}</td>
    <td><span class="rot">FGTS do mês</span>{_brl(fgts)}</td>
    <td><span class="rot">Base cálc. IRRF</span>{_brl(base_irrf)}</td>
    <td><span class="rot">Dep. IRRF</span>{_esc(str(it.get("dependents") or 0))}</td>
  </tr></table>
</div>
<div class="lateral"><div>Declaro ter recebido a importância líquida discriminada neste recibo.<br>
  ____/____/______ &nbsp;&nbsp; ______________________________________<br>
  Data &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Assinatura do funcionário</div></div>
</div>
<div class="via-nome">{_esc(via)}</div>"""


def gerar_recibos_html(co: Dict[str, Any], run: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    comp = competencia_extenso(_txt(run.get("competence")))
    folhas = "".join(
        f'<div class="folha">{_recibo_via(co, run, it, "1ª via — Empregador")}'
        f'<div class="corte"><span>✂ recortar</span></div>'
        f'{_recibo_via(co, run, it, "2ª via — Empregado")}</div>'
        for it in items)
    titulo = (f"Holerite {items[0].get('employee_name', '')} - {comp}" if len(items) == 1
              else f"Holerites - {comp}")
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>{_esc(titulo)}</title>
<style>{RECIBO_CSS}</style></head><body>
<div class="no-print"><span>{len(items)} recibo(s) · {_esc(comp)} · 2 vias por página</span>
  <button onclick="window.print()">Imprimir / Salvar PDF</button></div>
{folhas}
</body></html>"""


# ─── Folha de pagamento (analítica + resumo) ──────────────────────────────────

FOLHA_CSS = """*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;color:#000;background:#fff;margin:0;font-size:9.5px}
.no-print{max-width:1050px;margin:16px auto 8px;text-align:right}
.no-print button{padding:8px 16px;cursor:pointer;font-weight:bold;border:1px solid #555;background:#f3f3f3;border-radius:4px}
.doc{max-width:1050px;margin:0 auto 24px;padding:0 10px}
.hdr{display:flex;justify-content:space-between;align-items:flex-end;border:1.2px solid #000;padding:6px 8px}
.hdr .rs{font-size:12px;font-weight:bold}.hdr h1{font-size:13px;margin:0;text-align:right}
.sub{display:flex;justify-content:space-between;border:1.2px solid #000;border-top:none;padding:3px 8px;font-size:9px}
.emp{border:1px solid #000;margin-top:6px;page-break-inside:avoid}
.emp-cab{display:flex;gap:14px;background:#efefef;border-bottom:1px solid #000;padding:3px 6px;font-size:9.5px;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
.emp-cab b{font-size:10px}
.cols{display:flex}.cols>table{width:50%}.cols>table+table{border-left:1px solid #000}
table{border-collapse:collapse;width:100%}
td,th{padding:1.5px 5px;font-size:9.5px}
th{text-align:left;font-size:8px;text-transform:uppercase;border-bottom:1px solid #000}
.num{text-align:right;font-family:"Courier New",monospace;white-space:nowrap}
.emp-tot{display:flex;flex-wrap:wrap;gap:4px 16px;border-top:1px solid #000;padding:3px 6px;font-size:9px}
.emp-tot b{font-family:"Courier New",monospace}
.resumo{margin-top:14px;page-break-before:always}
.resumo h2{font-size:12px;border:1.2px solid #000;padding:4px 8px;margin:0;background:#efefef;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px}
.box{border:1px solid #000}.box h3{font-size:9.5px;margin:0;padding:3px 6px;border-bottom:1px solid #000;text-transform:uppercase}
.box td{border-bottom:1px dotted #bbb}
.box tr.t td{border-top:1px solid #000;border-bottom:none;font-weight:bold}
.nota{font-size:8.5px;color:#333;margin-top:6px}
.sig{margin-top:40px;display:flex;gap:40px}.sig div{flex:1;text-align:center;border-top:1px solid #000;padding-top:3px;font-size:9px}
@media print{.no-print{display:none}.doc{max-width:none;padding:0;margin:0}@page{size:A4 landscape;margin:9mm}}"""


def gerar_folha_html(co: Dict[str, Any], run: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    comp = competencia_extenso(_txt(run.get("competence")))
    tipo = TIPOS_FOLHA.get(_txt(run.get("tipo")) or "mensal", _txt(run.get("tipo")))
    resumo: Dict[tuple, Dict[str, Any]] = {}
    tot = {"prov": 0.0, "desc": 0.0, "liq": 0.0, "base_inss": 0.0, "base_fgts": 0.0, "base_irrf": 0.0, "fgts": 0.0,
           "inss": 0.0, "irrf": 0.0}
    blocos = []
    for it in items:
        lines = linhas_do_item(it)
        prov, desc = _totais(it, lines)
        liq = _f(it.get("net_salary")) if it.get("net_salary") is not None else prov - desc
        b_inss = _info(it, lines, COD_BASE_INSS, "base_inss")
        b_fgts = _info(it, lines, COD_BASE_FGTS, "base_fgts")
        b_irrf = _info(it, lines, COD_BASE_IRRF, "base_irrf")
        fgts = _info(it, lines, COD_FGTS, "fgts")
        for k, v in (("prov", prov), ("desc", desc), ("liq", liq), ("base_inss", b_inss), ("base_fgts", b_fgts),
                     ("base_irrf", b_irrf), ("fgts", fgts), ("inss", _f(it.get("inss"))), ("irrf", _f(it.get("irrf")))):
            tot[k] += v
        for ln in lines:
            if ln.get("tipo") not in ("provento", "desconto"):
                continue
            chave = (ln.get("tipo"), _txt(ln.get("codigo")), _txt(ln.get("nome")))
            r = resumo.setdefault(chave, {"valor": 0.0, "qtd": 0})
            r["valor"] += _f(ln.get("valor"))
            r["qtd"] += 1

        def col(tp):
            rows = "".join(
                f'<tr><td style="width:12%">{_esc(_txt(ln.get("codigo")))}</td><td>{_esc(_txt(ln.get("nome")))}</td>'
                f'<td class="num" style="width:14%">{_esc(_txt(ln.get("referencia")))}</td>'
                f'<td class="num" style="width:22%">{_brl(ln.get("valor"))}</td></tr>'
                for ln in lines if ln.get("tipo") == tp)
            return (f'<table><tr><th style="width:12%">Cód.</th><th>{"Proventos" if tp == "provento" else "Descontos"}</th>'
                    f'<th class="num">Ref.</th><th class="num">Valor</th></tr>{rows or "<tr><td colspan=4>&nbsp;</td></tr>"}</table>')

        blocos.append(f"""
<div class="emp">
  <div class="emp-cab"><span>Cód. <b>{_esc(_txt(it.get("matricula")) or str(it.get("employee_id", "")))}</b></span>
    <span><b>{_esc(_txt(it.get("employee_name")))}</b></span>
    <span>CPF {_esc(_txt(it.get("cpf")))}</span><span>Cargo: {_esc(_txt(it.get("role")))}</span>
    <span>CBO {_esc(_txt(it.get("cbo")))}</span><span>Admissão {_esc(_data(it.get("admission_date")))}</span>
    <span>Salário {_brl(it.get("salary"))}</span></div>
  <div class="cols">{col("provento")}{col("desconto")}</div>
  <div class="emp-tot"><span>Proventos <b>{_brl(prov)}</b></span><span>Descontos <b>{_brl(desc)}</b></span>
    <span>Líquido <b>{_brl(liq)}</b></span><span>Base INSS <b>{_brl(b_inss)}</b></span>
    <span>Base FGTS <b>{_brl(b_fgts)}</b></span><span>FGTS <b>{_brl(fgts)}</b></span>
    <span>Base IRRF <b>{_brl(b_irrf)}</b></span><span>Dep. IRRF <b>{_esc(str(it.get("dependents") or 0))}</b></span></div>
</div>""")

    def tabela_resumo(tp):
        linhas = sorted(((k, v) for k, v in resumo.items() if k[0] == tp), key=lambda kv: kv[0][1])
        rows = "".join(f'<tr><td>{_esc(k[1])}</td><td>{_esc(k[2])}</td><td class="num">{v["qtd"]}</td>'
                       f'<td class="num">{_brl(v["valor"])}</td></tr>' for k, v in linhas)
        total = tot["prov"] if tp == "provento" else tot["desc"]
        return (f'<div class="box"><h3>{"Proventos" if tp == "provento" else "Descontos"}</h3><table>'
                f'<tr><th style="width:14%">Cód.</th><th>Rubrica</th><th class="num">Func.</th><th class="num">Valor</th></tr>'
                f'{rows}<tr class="t"><td colspan="3">Total</td><td class="num">{_brl(total)}</td></tr></table></div>')

    simples = "simples" in _txt(co.get("regime_tributario")).lower()
    base = tot["base_inss"]
    patronal, rat, terceiros = (0.0, 0.0, 0.0) if simples else (
        round(base * ALIQ_PATRONAL, 2), round(base * ALIQ_RAT, 2), round(base * ALIQ_TERCEIROS, 2))
    total_inss = round(tot["inss"] + patronal + rat + terceiros, 2)
    nota_simples = ('<p class="nota">Empresa do Simples Nacional: a contribuição patronal (CPP) é recolhida no DAS, '
                    'exceto atividades do Anexo IV, que recolhem CPP pela GPS/DCTFWeb.</p>') if simples else ""
    encargos = f"""<div class="box"><h3>Bases e encargos</h3><table>
  <tr><td>Funcionários na folha</td><td class="num">{len(items)}</td></tr>
  <tr><td>Base de cálculo INSS</td><td class="num">{_brl(tot["base_inss"])}</td></tr>
  <tr><td>Base de cálculo FGTS</td><td class="num">{_brl(tot["base_fgts"])}</td></tr>
  <tr><td>Base de cálculo IRRF</td><td class="num">{_brl(tot["base_irrf"])}</td></tr>
  <tr><td>FGTS a recolher (8%)</td><td class="num">{_brl(tot["fgts"])}</td></tr>
  <tr><td>IRRF retido (DARF 0561)</td><td class="num">{_brl(tot["irrf"])}</td></tr>
  <tr><td>INSS segurados (descontado)</td><td class="num">{_brl(tot["inss"])}</td></tr>
  <tr><td>INSS empresa ({ALIQ_PATRONAL * 100:g}%)</td><td class="num">{"Simples (DAS)" if simples else _brl(patronal)}</td></tr>
  <tr><td>RAT/SAT ({ALIQ_RAT * 100:g}%)</td><td class="num">{"Simples (DAS)" if simples else _brl(rat)}</td></tr>
  <tr><td>Outras entidades / terceiros ({ALIQ_TERCEIROS * 100:g}%)</td><td class="num">{"Simples (DAS)" if simples else _brl(terceiros)}</td></tr>
  <tr class="t"><td>Total INSS da competência</td><td class="num">{_brl(total_inss)}</td></tr>
</table></div>
<div class="box"><h3>Totais da folha</h3><table>
  <tr><td>Total de proventos</td><td class="num">{_brl(tot["prov"])}</td></tr>
  <tr><td>Total de descontos</td><td class="num">{_brl(tot["desc"])}</td></tr>
  <tr class="t"><td>Total líquido a pagar</td><td class="num">{_brl(tot["liq"])}</td></tr>
  <tr><td>Custo total (proventos + FGTS + INSS empresa/RAT/terceiros)</td>
    <td class="num">{_brl(tot["prov"] + tot["fgts"] + patronal + rat + terceiros)}</td></tr>
</table></div>"""

    hoje = date.today().strftime("%d/%m/%Y")
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Folha de Pagamento - {_esc(comp)}</title>
<style>{FOLHA_CSS}</style></head><body>
<div class="no-print"><button onclick="window.print()">Imprimir / Salvar PDF</button></div>
<div class="doc">
  <div class="hdr"><div><div class="rs">{_esc(_txt(co.get("razao_social")))}</div>
    CNPJ: {_esc(_txt(co.get("cnpj")))} &nbsp; {_cabecalho_empresa(co)}</div>
    <h1>FOLHA DE PAGAMENTO</h1></div>
  <div class="sub"><span>Competência: <b>{_esc(comp)}</b> · {_esc(tipo)}</span>
    <span>Situação: {_esc(_txt(run.get("status")).capitalize())}</span><span>Emitido em {hoje}</span></div>
  {"".join(blocos) or '<p style="padding:12px">Nenhum funcionário nesta folha.</p>'}
  <div class="resumo">
    <h2>Resumo geral da folha — {_esc(comp)}</h2>
    <div class="grid">{tabela_resumo("provento")}{tabela_resumo("desconto")}{encargos}</div>
    {nota_simples}
    <div class="sig"><div>Responsável pelo Departamento Pessoal</div><div>{_esc(_txt(co.get("razao_social")))}</div></div>
  </div>
</div></body></html>"""
