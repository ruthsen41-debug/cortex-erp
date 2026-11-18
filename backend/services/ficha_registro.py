"""Ficha de Registro de Empregado (art. 41 da CLT) em HTML pronto para imprimir/salvar PDF."""
from datetime import date, datetime
from html import escape as _esc

OPCOES = {
    "sexo": {"M": "Masculino", "F": "Feminino"},
    "estado_civil": {"1": "Solteiro(a)", "2": "Casado(a)", "3": "Divorciado(a)", "4": "Separado(a)", "5": "Viúvo(a)"},
    "raca_cor": {"1": "Branca", "2": "Preta", "3": "Parda", "4": "Amarela", "5": "Indígena", "6": "Não informado"},
    "grau_instrucao": {"01": "Analfabeto", "02": "Até o 5º ano incompleto", "03": "5º ano completo",
                       "04": "6º ao 9º ano incompleto", "05": "Fundamental completo", "06": "Médio incompleto",
                       "07": "Médio completo", "08": "Superior incompleto", "09": "Superior completo",
                       "10": "Pós-graduação", "11": "Mestrado", "12": "Doutorado"},
    "deficiencia": {"": "Não", "fisica": "Física", "visual": "Visual", "auditiva": "Auditiva", "mental": "Mental",
                    "intelectual": "Intelectual", "reabilitado": "Reabilitado / readaptado"},
    "tipo_admissao": {"1": "Admissão", "2": "Transferência (mesmo grupo)",
                      "3": "Transferência (fusão/cisão/incorporação)", "5": "Mudança de CPF"},
    "ind_admissao": {"1": "Normal", "2": "Ação fiscal", "3": "Decisão judicial"},
    "regime_previdenciario": {"1": "RGPS (INSS)", "2": "RPPS (próprio)", "3": "Regime no exterior"},
    "tipo_contrato": {"indeterminado": "Prazo indeterminado", "experiencia": "Experiência",
                      "determinado": "Prazo determinado", "intermitente": "Intermitente"},
    "tipo_salario": {"5": "Mensalista", "1": "Horista", "2": "Diarista", "3": "Semanal", "4": "Quinzenal",
                     "6": "Tarefa", "7": "Não aplicável"},
    "forma_pagamento": {"deposito": "Depósito em conta", "pix": "PIX", "cheque": "Cheque", "dinheiro": "Dinheiro"},
    "jornada_tipo": {"integral": "Integral", "parcial": "Tempo parcial"},
    "insalubridade_grau": {"": "Não", "minimo": "Mínimo (10%)", "medio": "Médio (20%)", "maximo": "Máximo (40%)"},
    "bank_account_type": {"corrente": "Conta corrente", "poupanca": "Poupança", "salario": "Conta salário"},
    "aso_resultado": {"apto": "Apto", "inapto": "Inapto"},
    "parentesco": {"01": "Cônjuge", "02": "Companheiro(a)", "03": "Filho(a) / enteado(a)",
                   "04": "Filho(a)/enteado(a) universitário", "06": "Irmão(ã), neto(a), bisneto(a)",
                   "09": "Pais, avós, bisavós", "10": "Menor sob guarda judicial",
                   "11": "Incapaz sob tutela/curatela", "12": "Ex-cônjuge com pensão", "99": "Agregado / outros"},
}
MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]

CSS = """*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;color:#000;background:#fff;font-size:11px;margin:0}
.page{max-width:800px;margin:16px auto 24px;padding:22px 26px;border:1px solid #ccc}
.no-print{max-width:800px;margin:16px auto 0;text-align:right}
.no-print button{padding:8px 16px;cursor:pointer;font-weight:bold;border:1px solid #555;background:#f3f3f3;border-radius:4px}
.top{display:flex;gap:14px;align-items:stretch;border:1.5px solid #000;padding:10px}
.top .emp{flex:1;line-height:1.45}.top .emp .rs{font-size:13px;font-weight:bold}
.top h1{font-size:15px;margin:8px 0 0;text-transform:uppercase;letter-spacing:.5px}
.foto{width:3cm;height:4cm;border:1px solid #000;display:flex;align-items:center;justify-content:center;
      font-size:9px;color:#777;overflow:hidden;flex-shrink:0}.foto img{width:100%;height:100%;object-fit:cover}
h2{font-size:10.5px;text-transform:uppercase;background:#e6e6e6;border:1px solid #000;border-bottom:none;
   margin:10px 0 0;padding:3px 6px;letter-spacing:.4px}
table{width:100%;border-collapse:collapse;table-layout:fixed}
td,th{border:1px solid #000;padding:2px 5px;vertical-align:top}
td span{display:block;font-size:8px;color:#444;text-transform:uppercase}
td b{font-weight:normal;font-size:11px;min-height:13px;display:block;word-wrap:break-word}
th{background:#f2f2f2;font-size:9px;text-transform:uppercase;text-align:left}
.dec{margin-top:12px;font-size:10.5px;text-align:justify;line-height:1.5}
.sig{margin-top:38px;display:flex;gap:30px}.sig div{flex:1;text-align:center;border-top:1px solid #000;padding-top:4px;font-size:10px}
.rod{margin-top:14px;font-size:8.5px;color:#555;text-align:right}
h2,th{-webkit-print-color-adjust:exact;print-color-adjust:exact}
@media print{.no-print{display:none}.page{border:none;margin:0;padding:0;max-width:none}@page{size:A4;margin:12mm}}"""


def _txt(v) -> str:
    return "" if v is None else str(v).strip()


def _data(v) -> str:
    v = _txt(v)
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return v


def _brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _num(v) -> str:
    try:
        return f"{float(v):g}".replace(".", ",")
    except (TypeError, ValueError):
        return _txt(v)


def _junta(*partes, sep=" · ") -> str:
    return sep.join(p for p in partes if p)


def gerar_ficha_registro_html(emp: dict, co: dict, deps: list) -> str:
    def g(k):
        return _txt(emp.get(k))

    def opt(k, grupo=None):
        v = g(k)
        return OPCOES[grupo or k].get(v, v)

    def sn(k):
        try:
            return "Sim" if int(emp.get(k) or 0) else "Não"
        except (TypeError, ValueError):
            return "Não"

    def row(*cells):
        # cada célula: (rótulo, valor[, colunas])
        return "<tr>" + "".join(
            f'<td colspan="{c[2] if len(c) > 2 else 1}"><span>{_esc(c[0])}</span><b>{_esc(c[1])}</b></td>'
            for c in cells) + "</tr>"

    def bloco(titulo, linhas, corpo=None):
        return (f'<h2>{_esc(titulo)}</h2><table><colgroup>{"<col>" * 6}</colgroup>'
                f'{corpo if corpo is not None else "".join(linhas)}</table>')

    c = lambda k: _txt(co.get(k))  # noqa: E731

    foto = g("photo")
    foto_html = f'<img src="{_esc(foto)}" alt="Foto">' if foto.startswith("data:image") else "FOTO 3x4"

    end_emp = _junta(g("logradouro"), g("numero"), g("complemento"), sep=", ") or g("address")
    end_co = _junta(c("logradouro"), c("numero"), c("bairro"), _junta(c("cidade"), c("uf"), sep="/"), sep=", ")

    jornada = g("descricao_jornada")
    if not jornada and g("horario_entrada") and g("horario_saida"):
        if g("intervalo_inicio") and g("intervalo_fim"):
            jornada = (f'{g("horario_entrada")} às {g("intervalo_inicio")} e '
                       f'{g("intervalo_fim")} às {g("horario_saida")}')
        else:
            jornada = f'{g("horario_entrada")} às {g("horario_saida")}'

    exp = ""
    if g("tipo_contrato") == "experiencia" and emp.get("experiencia_dias"):
        exp = f'{emp["experiencia_dias"]} dias'
        if emp.get("experiencia_prorrogacao"):
            exp += f' + {emp["experiencia_prorrogacao"]} dias'

    mes = g("data_base_mes")
    mes_base = MESES[int(mes)] if mes.isdigit() and 0 < int(mes) <= 12 else mes
    try:
        adiant = f'{float(emp.get("adiantamento_pct")):g}%' if emp.get("adiantamento_pct") else ""
    except (TypeError, ValueError):
        adiant = ""

    secoes = [
        bloco("Dados pessoais", [
            row(("Nome completo", g("name"), 4), ("Nome social", g("nome_social"), 2)),
            row(("Data de nascimento", _data(g("birth_date"))), ("Sexo", opt("sexo")),
                ("Estado civil", opt("estado_civil")), ("Raça / cor", opt("raca_cor")),
                ("Grau de instrução", opt("grau_instrucao"), 2)),
            row(("Nacionalidade", g("nacionalidade")),
                ("Naturalidade", _junta(g("naturalidade"), g("uf_nascimento"), sep="/"), 2),
                ("Deficiência", opt("deficiencia")), ("Tipo sanguíneo", g("tipo_sanguineo")),
                ("País nasc. (cód.)", g("pais_nascimento"))),
            row(("Nome da mãe", g("nome_mae"), 3), ("Nome do pai", g("nome_pai"), 3)),
        ]),
        bloco("Documentos", [
            row(("CPF", g("cpf")), ("PIS / PASEP / NIT", g("pis_pasep")), ("RG", g("rg")),
                ("Órgão / UF", _junta(g("rg_orgao"), g("rg_uf"), sep="/")), ("Emissão RG", _data(g("rg_emissao"))),
                ("Reservista", g("reservista"))),
            row(("CTPS nº", g("ctps")), ("Série", g("ctps_serie")), ("UF", g("ctps_uf")),
                ("Emissão CTPS", _data(g("ctps_emissao"))), ("Título de eleitor", g("titulo_eleitor")),
                ("Zona / Seção", _junta(g("titulo_zona"), g("titulo_secao"), sep=" / "))),
            row(("CNH", g("cnh")), ("Categoria", g("cnh_categoria")), ("Validade CNH", _data(g("cnh_validade"))),
                ("UF CNH", g("cnh_uf")),
                ("Conselho de classe", _junta(g("conselho_classe"), g("conselho_numero"), g("conselho_uf"), sep=" "), 2)),
        ]),
        bloco("Endereço e contato", [
            row(("Logradouro, número e complemento", end_emp, 4), ("Bairro", g("bairro"), 2)),
            row(("Cidade / UF", _junta(g("cidade"), g("uf"), sep="/"), 2), ("CEP", g("cep")),
                ("Telefone", g("phone")), ("Celular", g("celular")), ("E-mail", g("email"))),
        ]),
        bloco("Contrato de trabalho", [
            row(("Matrícula", g("matricula")), ("Data de admissão", _data(g("admission_date"))),
                ("Tipo de admissão", opt("tipo_admissao")), ("Indicativo", opt("ind_admissao")),
                ("Categoria eSocial", g("esocial_category")), ("Primeiro emprego", sn("primeiro_emprego"))),
            row(("Tipo de contrato", opt("tipo_contrato")), ("Experiência", exp),
                ("Término do contrato", _data(g("data_termino_contrato"))),
                ("Regime previdenciário", opt("regime_previdenciario")),
                ("Opção FGTS", _data(g("fgts_opcao_data"))), ("Saque-aniversário", sn("fgts_aniversario"))),
            row(("Cargo", g("role"), 2), ("CBO", g("cbo")), ("Função", g("funcao"), 3)),
            row(("Departamento", g("department"), 2), ("Centro de custo", g("centro_custo")),
                ("Local de trabalho", g("local_trabalho"), 3)),
            row(("Sindicato", g("sindicato_nome"), 3), ("CNPJ do sindicato", g("sindicato_cnpj")),
                ("Data-base", mes_base), ("Contrib. sindical", sn("contribuicao_sindical"))),
        ]),
        bloco("Remuneração, jornada e pagamento", [
            row(("Salário base", _brl(emp.get("salary"))), ("Tipo de salário", opt("tipo_salario")),
                ("Forma de pagamento", opt("forma_pagamento")), ("Adiantamento", adiant),
                ("Insalubridade", opt("insalubridade_grau")), ("Periculosidade", sn("periculosidade"))),
            row(("Jornada", opt("jornada_tipo")), ("Horas semanais", _num(emp.get("horas_semana"))), ("Escala", g("escala")),
                ("Horário de trabalho", jornada, 3)),
            row(("Banco", _junta(g("bank_code"), g("bank_name"), sep=" - "), 2), ("Agência", g("bank_agency")),
                ("Conta", g("bank_account")), ("Tipo de conta", opt("bank_account_type")),
                ("Chave PIX", g("pix_chave"))),
        ]),
    ]

    if deps:
        linhas = "".join(
            f'<tr><td colspan="2">{_esc(_txt(d.get("nome")))}</td>'
            f'<td>{_esc(OPCOES["parentesco"].get(_txt(d.get("parentesco")), _txt(d.get("parentesco"))))}</td>'
            f'<td>{_esc(_data(d.get("data_nascimento")))}</td><td>{_esc(_txt(d.get("cpf")))}</td>'
            f'<td>{_esc(_junta("IRRF" if d.get("irrf") else "", "Sal. família" if d.get("salario_familia") else "", "Plano saúde" if d.get("plano_saude") else "", sep=", "))}</td></tr>'
            for d in deps)
    else:
        linhas = '<tr><td colspan="6" style="text-align:center;color:#666">Nenhum dependente cadastrado.</td></tr>'
    secoes.append(bloco("Dependentes", None, corpo=(
        '<tr><th colspan="2">Nome</th><th>Parentesco</th><th>Nascimento</th><th>CPF</th><th>Para fins de</th></tr>'
        + linhas)))
    secoes.append(bloco("Saúde ocupacional e observações", [
        row(("ASO admissional", _data(g("aso_admissional_data"))), ("Resultado", opt("aso_resultado")),
            ("Observações", g("notes"), 4)),
    ]))

    hoje = date.today().strftime("%d/%m/%Y")
    situacao = "Ativo" if emp.get("active", 1) else "Desligado"
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Ficha de Registro - {_esc(g("name"))}</title><style>{CSS}</style></head><body>
<div class="no-print"><button onclick="window.print()">Imprimir / Salvar PDF</button></div>
<div class="page">
  <div class="top">
    <div class="emp">
      <div class="rs">{_esc(c("razao_social"))}</div>
      CNPJ: {_esc(c("cnpj"))}<br>{_esc(end_co)}
      <h1>Ficha de Registro de Empregado</h1>
      <div style="margin-top:4px">Matrícula: <b>{_esc(g("matricula") or "—")}</b> &nbsp;·&nbsp; Situação: <b>{situacao}</b></div>
    </div>
    <div class="foto">{foto_html}</div>
  </div>
  {"".join(secoes)}
  <p class="dec">Declaro que as informações acima são verdadeiras e me comprometo a comunicar ao empregador
  qualquer alteração nos meus dados pessoais e de dependentes.</p>
  <p style="text-align:right;margin-top:14px">{_esc(c("cidade") or "____________")}, {hoje}.</p>
  <div class="sig">
    <div>{_esc(g("name"))}<br>Empregado(a)</div>
    <div>{_esc(c("razao_social"))}<br>Empregador</div>
  </div>
  <div class="rod">Registro de empregado — art. 41 da CLT · Emitido pelo Cortex ERP em {hoje}</div>
</div></body></html>"""
