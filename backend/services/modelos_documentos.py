"""Pacote de modelos de documentos do Departamento Pessoal.

Cada modelo é um texto com marcações simples e variáveis, que a empresa pode personalizar
(tabela ``dp_doc_modelos``) ou restaurar ao padrão. A empresa também pode criar modelos próprios.

Marcações do texto (uma por linha ou parágrafo):
  ``# Título``              título do documento
  ``## Subtítulo``          título de seção ou cláusula
  ``**negrito**``           negrito dentro do parágrafo
  ``- item``                item de lista
  ``[[assinaturas: empregador, empregado, testemunhas]]``  bloco de assinaturas
  ``[[dependentes_salario_familia]]``, ``[[dependentes_ir]]``, ``[[vale_transporte]]``  tabelas
  ``{{variavel}}``          substituída pelo dado do cadastro ou pelo campo informado na geração

Os textos-padrão seguem a CLT e as leis citadas em cada modelo; nada foi copiado de outro sistema.
Tudo o que vem do cadastro ou do usuário é escapado antes de virar HTML.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from html import escape as _esc
from typing import Any, Dict, List, Optional

MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

ESTADO_CIVIL = {"1": "solteiro(a)", "2": "casado(a)", "3": "divorciado(a)", "4": "separado(a)", "5": "viúvo(a)"}

PARENTESCO = {"01": "Cônjuge", "02": "Companheiro(a)", "03": "Filho(a) ou enteado(a)", "04": "Filho(a) ou enteado(a) universitário(a)",
              "06": "Irmão(ã), neto(a) ou bisneto(a)", "09": "Pais, avós e bisavós", "10": "Menor pobre sob guarda",
              "11": "Incapaz (curatela)", "12": "Ex-cônjuge com pensão", "99": "Agregado/outros"}


class ModeloErro(ValueError):
    """Erro de validação do modelo ou dos campos informados."""


# ─── Utilitários ──────────────────────────────────────────────────────────────

def _txt(v) -> str:
    return "" if v is None else str(v).strip()


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(v, padrao=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return padrao


def _dt(v) -> Optional[date]:
    v = _txt(v)
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v[:10], fmt).date()
        except ValueError:
            continue
    return None


def _br(d: Optional[date]) -> str:
    return d.strftime("%d/%m/%Y") if d else "___/___/______"


def _extenso_data(d: Optional[date]) -> str:
    if not d:
        return "____ de ______________ de ______"
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def _brl(v) -> str:
    return "R$ " + f"{_f(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _somar_anos(d: date, anos: int) -> date:
    try:
        return d.replace(year=d.year + anos)
    except ValueError:                       # 29/02 em ano não bissexto
        return d.replace(year=d.year + anos, day=28)


def hoje_local() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Cuiaba")).date()
    except Exception:
        return date.today()


_UNID = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
         "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CEN = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
        "oitocentos", "novecentos"]


def _ate_mil(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cem"
    c, resto = divmod(n, 100)
    partes = [_CEN[c]] if c else []
    if resto:
        if resto < 20:
            partes.append(_UNID[resto])
        else:
            d, u = divmod(resto, 10)
            partes.append(_DEZ[d] + (f" e {_UNID[u]}" if u else ""))
    return " e ".join(partes)


def numero_extenso(n: int) -> str:
    """Número inteiro (até 999.999.999) por extenso, em português."""
    if n == 0:
        return "zero"
    milhoes, resto = divmod(n, 1_000_000)
    milhares, unidades = divmod(resto, 1000)
    grupos = []                                   # (valor do grupo, texto)
    if milhoes:
        grupos.append((milhoes, _ate_mil(milhoes) + (" milhão" if milhoes == 1 else " milhões")))
    if milhares:
        grupos.append((milhares, "mil" if milhares == 1 else _ate_mil(milhares) + " mil"))
    if unidades:
        grupos.append((unidades, _ate_mil(unidades)))
    txt = grupos[0][1]
    for valor, parte in grupos[1:]:
        # "e" antes do grupo menor que 100 ou de centena redonda: "mil e cem", "dois mil e trinta"
        txt += (" e " if valor < 100 or valor % 100 == 0 else " ") + parte
    return txt


def valor_extenso(v) -> str:
    """Valor em reais por extenso: 3.000,50 -> 'três mil reais e cinquenta centavos'."""
    centavos_total = int(round(_f(v) * 100))
    reais, centavos = divmod(centavos_total, 100)
    partes = []
    if reais:
        txt = numero_extenso(reais)
        de = " de" if reais % 1_000_000 == 0 else ""
        partes.append(f"{txt}{de} {'real' if reais == 1 else 'reais'}")
    if centavos:
        partes.append(f"{numero_extenso(centavos)} {'centavo' if centavos == 1 else 'centavos'}")
    return " e ".join(partes) if partes else "zero real"


# ─── Variáveis disponíveis ────────────────────────────────────────────────────

VARIAVEIS: Dict[str, str] = {
    "empresa.razao_social": "Razão social da empresa",
    "empresa.nome_fantasia": "Nome fantasia",
    "empresa.cnpj": "CNPJ",
    "empresa.endereco": "Endereço completo da empresa",
    "empresa.cidade": "Cidade da empresa",
    "empresa.uf": "UF da empresa",
    "empresa.email": "E-mail da empresa",
    "empresa.telefone": "Telefone da empresa",
    "empregado.nome": "Nome do empregado (nome social, se houver)",
    "empregado.nome_civil": "Nome civil do empregado",
    "empregado.matricula": "Matrícula",
    "empregado.cpf": "CPF",
    "empregado.rg": "RG com órgão emissor",
    "empregado.pis": "PIS/PASEP/NIT",
    "empregado.ctps": "CTPS (número, série e UF)",
    "empregado.nascimento": "Data de nascimento",
    "empregado.estado_civil": "Estado civil",
    "empregado.nacionalidade": "Nacionalidade",
    "empregado.endereco": "Endereço completo do empregado",
    "empregado.cidade": "Cidade do empregado",
    "empregado.email": "E-mail do empregado",
    "empregado.cargo": "Cargo",
    "empregado.funcao": "Função",
    "empregado.cbo": "CBO",
    "empregado.departamento": "Departamento",
    "empregado.local_trabalho": "Local de trabalho",
    "empregado.admissao": "Data de admissão",
    "empregado.desligamento": "Data de desligamento",
    "empregado.salario": "Salário (R$)",
    "empregado.salario_extenso": "Salário por extenso",
    "empregado.horas_semana": "Horas semanais",
    "empregado.horario": "Horário de trabalho (entrada, intervalo e saída)",
    "empregado.sindicato": "Sindicato da categoria",
    "experiencia.dias": "Dias do 1º período de experiência",
    "experiencia.fim": "Término do 1º período de experiência",
    "experiencia.prorrogacao": "Dias da prorrogação da experiência",
    "experiencia.fim_prorrogacao": "Término da prorrogação",
    "data.hoje": "Data de hoje (dd/mm/aaaa)",
    "data.hoje_extenso": "Data de hoje por extenso",
    "local_data": "Cidade/UF e data por extenso, para o fecho",
}


def montar_variaveis(emp: Dict[str, Any], co: Dict[str, Any], hoje: Optional[date] = None) -> Dict[str, str]:
    hoje = hoje or hoje_local()
    g = lambda d, k: _txt(d.get(k))
    end_emp = ", ".join(p for p in [
        " ".join(p for p in [g(emp, "logradouro"), g(emp, "numero")] if p),
        g(emp, "complemento"), g(emp, "bairro"),
        "/".join(p for p in [g(emp, "cidade"), g(emp, "uf")] if p),
        ("CEP " + g(emp, "cep")) if g(emp, "cep") else ""] if p) or g(emp, "address")
    end_co = ", ".join(p for p in [
        " ".join(p for p in [g(co, "logradouro"), g(co, "numero")] if p),
        g(co, "complemento"), g(co, "bairro"),
        "/".join(p for p in [g(co, "cidade"), g(co, "uf")] if p),
        ("CEP " + g(co, "cep")) if g(co, "cep") else ""] if p)
    rg = g(emp, "rg")
    if rg and (g(emp, "rg_orgao") or g(emp, "rg_uf")):
        rg += " " + "/".join(p for p in [g(emp, "rg_orgao"), g(emp, "rg_uf")] if p)
    ctps = g(emp, "ctps")
    if ctps and g(emp, "ctps_serie"):
        ctps += f" série {g(emp, 'ctps_serie')}"
    if ctps and g(emp, "ctps_uf"):
        ctps += f"/{g(emp, 'ctps_uf')}"
    horario = ""
    if g(emp, "horario_entrada") and g(emp, "horario_saida"):
        horario = f"das {g(emp, 'horario_entrada')} às {g(emp, 'horario_saida')}"
        if g(emp, "intervalo_inicio") and g(emp, "intervalo_fim"):
            horario += f", com intervalo das {g(emp, 'intervalo_inicio')} às {g(emp, 'intervalo_fim')}"
    elif g(emp, "descricao_jornada"):
        horario = g(emp, "descricao_jornada")

    adm = _dt(emp.get("admission_date"))
    exp_dias = _int(emp.get("experiencia_dias"), 0) or 45
    exp_pror = _int(emp.get("experiencia_prorrogacao"), 0)
    if not exp_pror:
        exp_pror = max(0, 90 - exp_dias)
    fim1 = adm + timedelta(days=exp_dias - 1) if adm else None
    fim2 = fim1 + timedelta(days=exp_pror) if fim1 else None
    cidade_co = g(co, "cidade") or "____________"
    uf_co = g(co, "uf") or "__"
    salario = _f(emp.get("salary"))

    return {
        "empresa.razao_social": g(co, "razao_social"),
        "empresa.nome_fantasia": g(co, "nome_fantasia") or g(co, "razao_social"),
        "empresa.cnpj": g(co, "cnpj"),
        "empresa.endereco": end_co,
        "empresa.cidade": cidade_co,
        "empresa.uf": uf_co,
        "empresa.email": g(co, "email"),
        "empresa.telefone": g(co, "telefone"),
        "empregado.nome": g(emp, "nome_social") or g(emp, "name"),
        "empregado.nome_civil": g(emp, "name"),
        "empregado.matricula": g(emp, "matricula"),
        "empregado.cpf": g(emp, "cpf"),
        "empregado.rg": rg,
        "empregado.pis": g(emp, "pis_pasep"),
        "empregado.ctps": ctps,
        "empregado.nascimento": _br(_dt(emp.get("birth_date"))) if emp.get("birth_date") else "",
        "empregado.estado_civil": ESTADO_CIVIL.get(g(emp, "estado_civil"), g(emp, "estado_civil")),
        "empregado.nacionalidade": "brasileiro(a)" if g(emp, "nacionalidade") in ("", "10", "105", "Brasileira", "brasileira") else g(emp, "nacionalidade"),
        "empregado.endereco": end_emp,
        "empregado.cidade": g(emp, "cidade"),
        "empregado.email": g(emp, "email"),
        "empregado.cargo": g(emp, "role"),
        "empregado.funcao": g(emp, "funcao") or g(emp, "role"),
        "empregado.cbo": g(emp, "cbo"),
        "empregado.departamento": g(emp, "department"),
        "empregado.local_trabalho": g(emp, "local_trabalho") or end_co,
        "empregado.admissao": _br(adm) if adm else "",
        "empregado.desligamento": _br(_dt(emp.get("termination_date"))) if emp.get("termination_date") else "",
        "empregado.salario": _brl(salario),
        "empregado.salario_extenso": valor_extenso(salario),
        "empregado.horas_semana": str(_int(emp.get("horas_semana"), 44) or 44),
        "empregado.horario": horario or "conforme quadro de horário da empresa",
        "empregado.sindicato": g(emp, "sindicato_nome") or "sindicato da categoria",
        "experiencia.dias": str(exp_dias),
        "experiencia.fim": _br(fim1) if fim1 else "",
        "experiencia.prorrogacao": str(exp_pror),
        "experiencia.fim_prorrogacao": _br(fim2) if fim2 and exp_pror else "",
        "data.hoje": _br(hoje),
        "data.hoje_extenso": _extenso_data(hoje),
        "local_data": f"{cidade_co}/{uf_co}, {_extenso_data(hoje)}",
    }


# ─── Catálogo de modelos-padrão ───────────────────────────────────────────────

def _campo(nome, rotulo, tipo="text", padrao="", opcoes=None, ajuda=""):
    return {"nome": nome, "rotulo": rotulo, "tipo": tipo, "padrao": padrao, "opcoes": opcoes or [], "ajuda": ajuda}


ASS_PARTES = "[[assinaturas: empregador, empregado]]"
ASS_TESTEMUNHAS = "[[assinaturas: empregador, empregado, testemunhas]]"

MODELOS: Dict[str, Dict[str, Any]] = {
    # ── Contratos ──
    "contrato_experiencia": {
        "titulo": "Contrato de experiência", "grupo": "Contratos",
        "base_legal": "CLT arts. 443 §2º “c”, 445 parágrafo único e 451",
        "descricao": "Prazo do 1º período e da prorrogação (até 90 dias somados, uma única prorrogação).",
        "campos": [_campo("dias", "Dias do 1º período", "number", "{{experiencia.dias}}"),
                   _campo("prorrogacao", "Dias da prorrogação", "number", "{{experiencia.prorrogacao}}")],
        "texto": """# Contrato de Trabalho a Título de Experiência

**EMPREGADOR:** {{empresa.razao_social}}, inscrito no CNPJ sob o nº {{empresa.cnpj}}, com sede em {{empresa.endereco}}.

**EMPREGADO(A):** {{empregado.nome}}, {{empregado.nacionalidade}}, {{empregado.estado_civil}}, CPF {{empregado.cpf}}, RG {{empregado.rg}}, CTPS {{empregado.ctps}}, PIS {{empregado.pis}}, residente em {{empregado.endereco}}.

As partes acima celebram o presente contrato de experiência, regido pela Consolidação das Leis do Trabalho, nas cláusulas a seguir.

## Cláusula 1ª — Função
O(A) EMPREGADO(A) exercerá a função de **{{empregado.cargo}}** (CBO {{empregado.cbo}}), no setor {{empregado.departamento}}, em {{empregado.local_trabalho}}, comprometendo-se a executar as tarefas compatíveis com sua condição pessoal.

## Cláusula 2ª — Prazo
Este contrato vigora por **{{dias}} dias**, de {{empregado.admissao}} a **{{fim_periodo}}**, podendo ser prorrogado uma única vez por **{{prorrogacao}} dias**, até **{{fim_prorrogacao}}**, sem ultrapassar 90 dias no total (CLT, art. 445, parágrafo único, e art. 451).

Se o(a) EMPREGADO(A) continuar trabalhando após o término do prazo, o contrato passa a vigorar por prazo indeterminado.

## Cláusula 3ª — Remuneração
Salário de **{{empregado.salario}}** ({{empregado.salario_extenso}}) por mês, pago até o 5º dia útil do mês seguinte ao trabalhado (CLT, art. 459, §1º).

## Cláusula 4ª — Jornada
Jornada de {{empregado.horas_semana}} horas semanais, {{empregado.horario}}, respeitados os intervalos legais. Havendo necessidade, as horas extras serão pagas ou compensadas na forma da lei e da convenção coletiva.

## Cláusula 5ª — Descontos
Além dos descontos previstos em lei, o(a) EMPREGADO(A) autoriza o desconto dos danos que causar por dolo, conforme o art. 462, §1º, da CLT.

## Cláusula 6ª — Rescisão antecipada
A rescisão antes do prazo, sem justa causa, segue os arts. 479 e 480 da CLT.

E, por estarem de acordo, assinam em duas vias de igual teor, na presença das testemunhas.

{{local_data}}.

""" + ASS_TESTEMUNHAS,
    },
    "contrato_determinado": {
        "titulo": "Contrato por prazo determinado", "grupo": "Contratos",
        "base_legal": "CLT arts. 443 §§1º e 2º, 445 e 451",
        "descricao": "Para serviço ou atividade de natureza transitória; prazo máximo de 2 anos.",
        "campos": [_campo("data_termino", "Data de término", "date", "", ajuda="Até 2 anos após a admissão."),
                   _campo("justificativa", "Justificativa do prazo", "select", "servico_transitorio",
                          [["servico_transitorio", "Serviço de natureza transitória"],
                           ["atividade_transitoria", "Atividade empresarial de caráter transitório"]]),
                   _campo("objeto", "Serviço ou obra contratada", "textarea", "")],
        "texto": """# Contrato de Trabalho por Prazo Determinado

**EMPREGADOR:** {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}, com sede em {{empresa.endereco}}.

**EMPREGADO(A):** {{empregado.nome}}, CPF {{empregado.cpf}}, CTPS {{empregado.ctps}}, PIS {{empregado.pis}}, residente em {{empregado.endereco}}.

## Cláusula 1ª — Objeto e justificativa
O(A) EMPREGADO(A) é contratado(a) para a função de **{{empregado.cargo}}** (CBO {{empregado.cbo}}), em razão de {{justificativa_texto}} (CLT, art. 443, §2º), para: {{objeto}}

## Cláusula 2ª — Prazo
O contrato vigora de **{{empregado.admissao}}** a **{{data_termino_br}}** ({{duracao_dias}} dias). Pode ser prorrogado uma única vez, desde que a soma não ultrapasse 2 anos (CLT, arts. 445 e 451). Se houver trabalho após o termo final, o contrato passa a ser por prazo indeterminado.

## Cláusula 3ª — Remuneração e jornada
Salário de **{{empregado.salario}}** ({{empregado.salario_extenso}}) por mês, pago até o 5º dia útil do mês seguinte, com jornada de {{empregado.horas_semana}} horas semanais, {{empregado.horario}}.

## Cláusula 4ª — Rescisão antecipada
A rescisão antes do prazo, sem justa causa, segue os arts. 479 e 480 da CLT.

{{local_data}}.

""" + ASS_TESTEMUNHAS,
    },
    "contrato_intermitente": {
        "titulo": "Contrato de trabalho intermitente", "grupo": "Contratos",
        "base_legal": "CLT arts. 443 §3º e 452-A",
        "descricao": "Valor da hora, regras de convocação e pagamento ao fim de cada período trabalhado.",
        "campos": [_campo("valor_hora", "Valor da hora (R$)", "number", ""),
                   _campo("atividades", "Atividades", "textarea", "")],
        "texto": """# Contrato de Trabalho Intermitente

**EMPREGADOR:** {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}, com sede em {{empresa.endereco}}.

**EMPREGADO(A):** {{empregado.nome}}, CPF {{empregado.cpf}}, CTPS {{empregado.ctps}}, PIS {{empregado.pis}}, residente em {{empregado.endereco}}.

## Cláusula 1ª — Objeto
Prestação de serviços com alternância de períodos de trabalho e inatividade (CLT, art. 443, §3º), na função de **{{empregado.cargo}}** (CBO {{empregado.cbo}}), com as atividades: {{atividades}}

## Cláusula 2ª — Remuneração
Valor de **{{valor_hora_brl}} por hora** ({{valor_hora_extenso}}), não inferior ao valor horário do salário mínimo nem ao dos demais empregados na mesma função (CLT, art. 452-A).

## Cláusula 3ª — Convocação
O EMPREGADOR convocará o(a) EMPREGADO(A) por qualquer meio eficaz, informando a jornada, com pelo menos **3 dias corridos** de antecedência. O(A) EMPREGADO(A) terá **1 dia útil** para responder; o silêncio é recusa, e a recusa não descaracteriza a subordinação (CLT, art. 452-A, §§1º a 3º).

## Cláusula 4ª — Pagamento
Ao final de cada período de prestação de serviço, o(a) EMPREGADO(A) receberá de imediato: remuneração, férias proporcionais com um terço, 13º salário proporcional, repouso semanal remunerado e adicionais legais, com recibo que discrimine cada parcela (CLT, art. 452-A, §§6º e 7º). O EMPREGADOR recolherá a contribuição previdenciária e o FGTS do período (§8º).

## Cláusula 5ª — Férias
A cada 12 meses, o(a) EMPREGADO(A) tem direito a usufruir, nos 12 meses seguintes, um mês de férias, durante o qual não poderá ser convocado(a) pelo mesmo empregador (CLT, art. 452-A, §9º).

## Cláusula 6ª — Inatividade
O período de inatividade não é tempo à disposição do EMPREGADOR, e o(a) EMPREGADO(A) pode prestar serviços a outros contratantes.

{{local_data}}.

""" + ASS_TESTEMUNHAS,
    },
    "prorrogacao_experiencia": {
        "titulo": "Termo de prorrogação da experiência", "grupo": "Contratos",
        "base_legal": "CLT arts. 445 parágrafo único e 451",
        "descricao": "Prorroga o contrato de experiência uma única vez, sem passar de 90 dias.",
        "campos": [_campo("dias", "Dias do 1º período", "number", "{{experiencia.dias}}"),
                   _campo("prorrogacao", "Dias da prorrogação", "number", "{{experiencia.prorrogacao}}")],
        "texto": """# Termo de Prorrogação do Contrato de Experiência

O contrato de experiência firmado entre **{{empresa.razao_social}}**, CNPJ {{empresa.cnpj}}, e **{{empregado.nome}}**, CPF {{empregado.cpf}}, na função de {{empregado.cargo}}, iniciado em {{empregado.admissao}} com término previsto para {{fim_periodo}}, fica prorrogado por **{{prorrogacao}} dias**, passando a terminar em **{{fim_prorrogacao}}**.

Esta é a única prorrogação do contrato, que, somados os dois períodos, não ultrapassa 90 dias (CLT, art. 445, parágrafo único, e art. 451). Permanecem as demais cláusulas do contrato.

{{local_data}}.

""" + ASS_TESTEMUNHAS,
    },
    "termino_experiencia": {
        "titulo": "Comunicado de término da experiência", "grupo": "Contratos",
        "base_legal": "CLT art. 443 §2º “c”",
        "descricao": "Avisa que o contrato de experiência não será renovado nem convertido.",
        "campos": [_campo("termino", "Término do contrato", "date", "", ajuda="Em branco: usa o fim da prorrogação ou do 1º período.")],
        "texto": """# Comunicado de Término do Contrato de Experiência

Ao(À) Sr.(a) **{{empregado.nome}}**, matrícula {{empregado.matricula}}, função {{empregado.cargo}}.

Comunicamos que o seu contrato de experiência, iniciado em {{empregado.admissao}}, **termina em {{termino_br}}** e não será prorrogado nem convertido em contrato por prazo indeterminado.

Compareça ao departamento pessoal para receber as verbas rescisórias no prazo do art. 477, §6º, da CLT (até 10 dias contados do término do contrato) e para a entrega dos documentos do desligamento.

{{local_data}}.

""" + ASS_PARTES,
    },
    # ── Jornada ──
    "acordo_compensacao": {
        "titulo": "Acordo de compensação de horas", "grupo": "Jornada",
        "base_legal": "CLT art. 59 §§2º, 5º e 6º e art. 59-B",
        "descricao": "Compensação no mesmo mês ou banco de horas individual de até 6 meses.",
        "campos": [_campo("modalidade", "Modalidade", "select", "mensal",
                          [["mensal", "Compensação dentro do mesmo mês (art. 59, §6º)"],
                           ["banco_6_meses", "Banco de horas individual, até 6 meses (art. 59, §5º)"]]),
                   _campo("distribuicao", "Distribuição da jornada", "textarea",
                          "De segunda a sexta-feira, com acréscimo diário para compensar a ausência de trabalho aos sábados.")],
        "texto": """# Acordo Individual de Compensação de Horas

**EMPREGADOR:** {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}.

**EMPREGADO(A):** {{empregado.nome}}, CPF {{empregado.cpf}}, função {{empregado.cargo}}.

As partes ajustam a compensação de horas nos termos abaixo.

## 1. Modalidade
{{modalidade_texto}}

## 2. Distribuição da jornada
{{distribuicao}}

## 3. Limites
A jornada não excederá 10 horas diárias (CLT, art. 59, §2º). As horas que não forem compensadas no prazo acima serão pagas como extras, com o adicional legal ou convencional. Na rescisão, o saldo não compensado será pago como hora extra, calculado sobre o salário da data da rescisão (art. 59, §3º).

## 4. Horas extras habituais
A prestação de horas extras habituais não descaracteriza este acordo (CLT, art. 59-B, parágrafo único).

## 5. Vigência
Prazo indeterminado, podendo ser cancelado por qualquer das partes mediante aviso escrito, quitadas as horas pendentes. Prevalece a convenção ou acordo coletivo que tratar do tema de forma diferente.

{{local_data}}.

""" + ASS_PARTES,
    },
    "acordo_prorrogacao": {
        "titulo": "Acordo de prorrogação de horas", "grupo": "Jornada",
        "base_legal": "CLT art. 59 caput e §1º; CF art. 7º, XVI",
        "descricao": "Autoriza até 2 horas extras por dia, com adicional mínimo de 50%.",
        "campos": [_campo("adicional", "Adicional de hora extra (%)", "number", "50")],
        "texto": """# Acordo Individual de Prorrogação de Horas

**EMPREGADOR:** {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}.

**EMPREGADO(A):** {{empregado.nome}}, CPF {{empregado.cpf}}, função {{empregado.cargo}}, jornada de {{empregado.horas_semana}} horas semanais, {{empregado.horario}}.

Fica ajustado que a jornada poderá ser acrescida de **até 2 horas extras por dia** (CLT, art. 59), quando houver necessidade do serviço.

As horas extras serão pagas com adicional de **{{adicional}}%** sobre o valor da hora normal, não inferior a 50% (CLT, art. 59, §1º, e Constituição Federal, art. 7º, XVI), ou com o percentual maior previsto na convenção coletiva.

Este acordo vale por prazo indeterminado e pode ser cancelado por qualquer das partes, por escrito.

{{local_data}}.

""" + ASS_PARTES,
    },
    # ── Férias ──
    "aviso_ferias": {
        "titulo": "Aviso de férias", "grupo": "Férias",
        "base_legal": "CLT arts. 134, 135 e 145",
        "descricao": "Comunicação por escrito com 30 dias de antecedência; usa a programação de férias, se houver.",
        "campos": [_campo("periodo_inicio", "Início do período aquisitivo", "date", ""),
                   _campo("data_inicio", "Início do gozo", "date", ""),
                   _campo("dias", "Dias de gozo", "number", "30"),
                   _campo("dias_abono", "Dias de abono pecuniário", "number", "0")],
        "texto": """# Aviso de Férias

Ao(À) Sr.(a) **{{empregado.nome}}**, matrícula {{empregado.matricula}}, função {{empregado.cargo}}, setor {{empregado.departamento}}.

Nos termos do art. 135 da CLT, comunicamos que suas férias serão concedidas conforme abaixo:

- Período aquisitivo: **{{periodo_aquisitivo}}**
- Período de gozo: **{{gozo_inicio}} a {{gozo_fim}}** ({{dias}} dias)
- Abono pecuniário: {{abono_texto}}
- Retorno ao trabalho: **{{retorno}}**
- Pagamento das férias até: **{{data_pagamento}}** (2 dias antes do início, CLT art. 145)

Pedimos que dê ciência neste aviso.

{{local_data}}.

""" + ASS_PARTES,
    },
    "abono_pecuniario": {
        "titulo": "Solicitação de abono pecuniário", "grupo": "Férias",
        "base_legal": "CLT art. 143 e §1º",
        "descricao": "Pedido do empregado para converter até 1/3 das férias em dinheiro.",
        "campos": [_campo("periodo_inicio", "Início do período aquisitivo", "date", ""),
                   _campo("dias_abono", "Dias a converter", "number", "10")],
        "texto": """# Requerimento de Abono Pecuniário de Férias

À {{empresa.razao_social}}.

Eu, **{{empregado.nome}}**, CPF {{empregado.cpf}}, matrícula {{empregado.matricula}}, função {{empregado.cargo}}, requeiro a conversão de **{{dias_abono}} dias** das férias do período aquisitivo **{{periodo_aquisitivo}}** em abono pecuniário, nos termos do art. 143 da CLT.

Este requerimento é apresentado até 15 dias antes do término do período aquisitivo, ou seja, até **{{prazo_requerimento}}** (CLT, art. 143, §1º).

{{local_data}}.

[[assinaturas: empregado, recebido]]""",
    },
    "adiantamento_13_ferias": {
        "titulo": "Pedido da 1ª parcela do 13º nas férias", "grupo": "Férias",
        "base_legal": "Lei 4.749/1965, art. 2º §2º",
        "descricao": "O empregado pede, no mês de janeiro, a 1ª parcela do 13º junto com as férias.",
        "campos": [_campo("ano", "Ano", "number", "{{ano_atual}}")],
        "texto": """# Requerimento da 1ª Parcela do 13º Salário nas Férias

À {{empresa.razao_social}}.

Eu, **{{empregado.nome}}**, CPF {{empregado.cpf}}, matrícula {{empregado.matricula}}, requeiro que o adiantamento da 1ª parcela do 13º salário de **{{ano}}** seja pago junto com as minhas férias, conforme o art. 2º, §2º, da Lei 4.749/1965.

Este requerimento é feito no mês de janeiro de {{ano}}, como exige a lei.

{{local_data}}.

[[assinaturas: empregado, recebido]]""",
    },
    # ── Benefícios e dependentes ──
    "salario_familia": {
        "titulo": "Termo de responsabilidade do salário-família", "grupo": "Benefícios e dependentes",
        "base_legal": "Lei 8.213/1991, arts. 65 a 70; Decreto 3.048/1999, arts. 81 a 92",
        "descricao": "Lista os filhos até 14 anos marcados para salário-família e as obrigações de comprovação.",
        "campos": [],
        "texto": """# Termo de Responsabilidade — Salário-Família

**Empresa:** {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}.

**Segurado(a):** {{empregado.nome}}, CPF {{empregado.cpf}}, PIS {{empregado.pis}}, matrícula {{empregado.matricula}}.

Declaro, para fins de recebimento do salário-família, que são meus filhos ou equiparados, menores de 14 anos ou inválidos, os beneficiários abaixo:

[[dependentes_salario_familia]]

Comprometo-me a:

- apresentar a certidão de nascimento de cada beneficiário;
- apresentar anualmente o atestado de vacinação obrigatória dos filhos até 6 anos de idade;
- apresentar semestralmente a comprovação de frequência escolar dos filhos a partir de 4 anos de idade;
- comunicar à empresa, de imediato, o falecimento do filho, a cessação da invalidez, a perda da guarda ou qualquer fato que faça cessar o direito ao benefício.

Estou ciente de que a falta dos documentos suspende o pagamento e de que a declaração falsa me sujeita às penalidades legais e à devolução dos valores recebidos indevidamente.

{{local_data}}.

[[assinaturas: empregado, recebido]]""",
    },
    "dependentes_ir": {
        "titulo": "Declaração de dependentes para o IR", "grupo": "Benefícios e dependentes",
        "base_legal": "Lei 9.250/1995, arts. 4º, III, e 35",
        "descricao": "Dependentes marcados para dedução do imposto de renda na fonte.",
        "campos": [],
        "texto": """# Declaração de Dependentes para Fins de Imposto de Renda

À {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}.

Eu, **{{empregado.nome}}**, CPF {{empregado.cpf}}, declaro, para fins de dedução da base de cálculo do imposto de renda retido na fonte (Lei 9.250/1995, art. 4º, III), que são meus dependentes, nos termos do art. 35 da mesma lei:

[[dependentes_ir]]

Declaro ainda que esses dependentes não são deduzidos por outra pessoa, inclusive pelo outro cônjuge ou companheiro, e que comunicarei qualquer alteração. Assumo a responsabilidade por esta declaração, ciente das penalidades da lei.

{{local_data}}.

[[assinaturas: empregado, recebido]]""",
    },
    "vale_transporte": {
        "titulo": "Opção pelo vale-transporte", "grupo": "Benefícios e dependentes",
        "base_legal": "Lei 7.418/1985 e Decreto 10.854/2021",
        "descricao": "Declaração de opção ou renúncia, com endereço e linhas usadas.",
        "campos": [_campo("opcao", "Opção do empregado", "select", "optante",
                          [["optante", "Deseja receber o vale-transporte"], ["renuncia", "Não deseja receber (renúncia)"]])],
        "texto": """# Declaração de Opção pelo Vale-Transporte

À {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}.

Eu, **{{empregado.nome}}**, CPF {{empregado.cpf}}, matrícula {{empregado.matricula}}, residente em {{empregado.endereco}}, declaro que:

{{opcao_texto}}

[[vale_transporte]]

Comprometo-me a atualizar estas informações sempre que mudar de endereço ou de meio de transporte, ciente de que a declaração falsa ou o uso indevido do vale-transporte constitui falta grave.

{{local_data}}.

[[assinaturas: empregado, recebido]]""",
    },
    # ── Termos e declarações ──
    "autorizacao_desconto": {
        "titulo": "Autorização de desconto em folha", "grupo": "Termos e declarações",
        "base_legal": "CLT art. 462; Súmula 342 do TST",
        "descricao": "Autorização prévia e por escrito para descontos não previstos em lei.",
        "campos": [_campo("descricao", "Motivo do desconto", "textarea", ""),
                   _campo("valor", "Valor total (R$)", "number", ""),
                   _campo("parcelas", "Número de parcelas", "number", "1")],
        "texto": """# Autorização de Desconto em Folha de Pagamento

Eu, **{{empregado.nome}}**, CPF {{empregado.cpf}}, matrícula {{empregado.matricula}}, autorizo a {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}, a descontar do meu salário o valor total de **{{valor_brl}}** ({{valor_extenso}}), em **{{parcelas}} parcela(s)** de {{valor_parcela}}, referente a:

{{descricao}}

Esta autorização é dada de forma livre, prévia e por escrito, nos termos do art. 462 da CLT e da Súmula 342 do TST. Em caso de desligamento, o saldo poderá ser descontado das verbas rescisórias, observado o limite do art. 477, §5º, da CLT.

{{local_data}}.

[[assinaturas: empregado, empregador]]""",
    },
    "termo_lgpd": {
        "titulo": "Termo de ciência — LGPD", "grupo": "Termos e declarações",
        "base_legal": "Lei 13.709/2018 (LGPD), arts. 7º, 9º, 11, 16 e 18",
        "descricao": "Informa ao empregado como seus dados pessoais são tratados no contrato de trabalho.",
        "campos": [_campo("encarregado", "Encarregado de dados (nome e contato)", "text", "{{empresa.email}}")],
        "texto": """# Termo de Ciência sobre o Tratamento de Dados Pessoais

**Controlador:** {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}, {{empresa.endereco}}.

**Titular:** {{empregado.nome}}, CPF {{empregado.cpf}}.

Em atenção ao art. 9º da Lei 13.709/2018 (LGPD), informamos como seus dados pessoais são tratados.

## 1. Dados e finalidades
Dados de identificação, contato, documentos, dependentes, dados bancários, jornada, remuneração e saúde ocupacional, usados para:

- cumprir obrigações legais e regulatórias, como eSocial, FGTS, INSS, imposto de renda, RAIS/DIRF e normas de saúde e segurança (art. 7º, II);
- executar o contrato de trabalho: folha, benefícios, férias e rescisão (art. 7º, V);
- exercer direitos em processos judiciais ou administrativos (art. 7º, VI).

Dados de saúde, como atestados e exames ocupacionais, e biometria do ponto, quando houver, são tratados para cumprir obrigação legal (art. 11, II, “a”).

## 2. Compartilhamento
Os dados podem ser compartilhados com órgãos públicos (Receita Federal, INSS, Caixa, Ministério do Trabalho), com a contabilidade, bancos, operadoras de benefícios e de saúde ocupacional, somente para as finalidades acima.

## 3. Guarda
Os dados são guardados pelos prazos exigidos em lei, mesmo após o fim do contrato (art. 16, I).

## 4. Seus direitos
Você pode pedir confirmação do tratamento, acesso, correção, informações sobre compartilhamento e os demais direitos do art. 18, pelo contato do encarregado: **{{encarregado}}**.

## 5. Uso de imagem (opcional)
( ) Autorizo   ( ) Não autorizo o uso da minha imagem em materiais internos e institucionais da empresa. Esta autorização pode ser revogada a qualquer momento.

Declaro que recebi e li este termo.

{{local_data}}.

[[assinaturas: empregado, empregador]]""",
    },
    "carta_recomendacao": {
        "titulo": "Carta de recomendação", "grupo": "Termos e declarações",
        "base_legal": "",
        "descricao": "Carta de referência profissional para ex-empregado ou empregado.",
        "campos": [_campo("ate", "Trabalhou até", "date", "", ajuda="Em branco: usa a data de desligamento ou “até a presente data”."),
                   _campo("complemento", "Texto adicional", "textarea", "")],
        "texto": """# Carta de Recomendação

A {{empresa.razao_social}}, CNPJ {{empresa.cnpj}}, declara que **{{empregado.nome}}**, CPF {{empregado.cpf}}, trabalhou nesta empresa de {{empregado.admissao}} {{periodo_ate}}, na função de **{{empregado.cargo}}**.

Durante esse período, demonstrou responsabilidade, assiduidade e bom relacionamento com colegas e clientes, motivo pelo qual o(a) recomendamos.

{{complemento}}

{{local_data}}.

[[assinaturas: empregador]]""",
    },
    "abandono_emprego": {
        "titulo": "Convocação por abandono de emprego", "grupo": "Termos e declarações",
        "base_legal": "CLT art. 482 “i”; Súmula 32 do TST",
        "descricao": "Convoca o empregado ausente a retornar ou justificar as faltas. Envie por AR, telegrama ou e-mail com confirmação.",
        "campos": [_campo("ultimo_dia", "Último dia de trabalho", "date", ""),
                   _campo("prazo_dias", "Prazo para retorno (dias)", "number", "3")],
        "texto": """# Convocação para Retorno ao Trabalho

Ao(À) Sr.(a) **{{empregado.nome}}**, CPF {{empregado.cpf}}, matrícula {{empregado.matricula}}, residente em {{empregado.endereco}}.

Constatamos que V.Sa. não comparece ao trabalho desde **{{dia_seguinte}}**, sem apresentar justificativa, sendo {{ultimo_dia_br}} o último dia trabalhado.

Solicitamos que retorne ao trabalho ou apresente justificativa das ausências no prazo de **{{prazo_dias}} dias** do recebimento desta convocação.

A ausência injustificada por 30 dias ou mais pode caracterizar abandono de emprego, motivo de rescisão do contrato por justa causa (CLT, art. 482, “i”, e Súmula 32 do TST).

{{local_data}}.

[[assinaturas: empregador]]""",
    },
}

GRUPOS = ["Contratos", "Jornada", "Férias", "Benefícios e dependentes", "Termos e declarações", "Personalizados"]


# ─── Campos calculados por modelo ─────────────────────────────────────────────

def _valor_campo(campos: Dict[str, Any], nome: str, var: Dict[str, str], padrao: str = "") -> str:
    v = _txt(campos.get(nome))
    if v:
        return v
    return _substituir_simples(padrao, var)


def _substituir_simples(txt: str, var: Dict[str, str]) -> str:
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", lambda m: var.get(m.group(1), ""), txt or "")


def calcular_campos(codigo: str, emp: Dict[str, Any], var: Dict[str, str], campos: Dict[str, Any],
                    extras: Dict[str, Any]) -> Dict[str, str]:
    """Valida os campos informados e devolve as variáveis próprias do modelo."""
    modelo = MODELOS.get(codigo)
    hoje = _dt(extras.get("hoje")) or hoje_local()
    var = {**var, "ano_atual": str(hoje.year)}
    out: Dict[str, str] = {}
    if modelo:
        for c in modelo.get("campos", []):
            out[c["nome"]] = _valor_campo(campos, c["nome"], var, c.get("padrao", ""))
    adm = _dt(emp.get("admission_date"))

    if codigo in ("contrato_experiencia", "prorrogacao_experiencia"):
        dias, pror = _int(out.get("dias")), _int(out.get("prorrogacao"))
        if dias < 1:
            raise ModeloErro("Informe os dias do 1º período de experiência.")
        if pror < 0 or dias + pror > 90:
            raise ModeloErro("O contrato de experiência não pode passar de 90 dias somados (CLT, art. 445, parágrafo único).")
        if codigo == "prorrogacao_experiencia" and pror < 1:
            raise ModeloErro("Informe os dias da prorrogação.")
        fim1 = adm + timedelta(days=dias - 1) if adm else None
        out.update(dias=str(dias), prorrogacao=str(pror), fim_periodo=_br(fim1),
                   fim_prorrogacao=_br(fim1 + timedelta(days=pror)) if fim1 and pror else "—")

    elif codigo == "contrato_determinado":
        fim = _dt(out.get("data_termino")) or _dt(emp.get("data_termino_contrato"))
        if not fim:
            raise ModeloErro("Informe a data de término do contrato.")
        if adm:
            if fim < adm:
                raise ModeloErro("A data de término é anterior à admissão.")
            if fim >= _somar_anos(adm, 2):
                raise ModeloErro("O contrato por prazo determinado não pode passar de 2 anos (CLT, art. 445).")
        out.update(data_termino_br=_br(fim), duracao_dias=str((fim - adm).days + 1) if adm else "___",
                   justificativa_texto={"servico_transitorio": "serviço cuja natureza ou transitoriedade justifica a predeterminação do prazo",
                                        "atividade_transitoria": "atividade empresarial de caráter transitório"}
                   .get(out.get("justificativa"), "serviço de natureza transitória"),
                   objeto=out.get("objeto") or "_______________________________________________")

    elif codigo == "contrato_intermitente":
        vh = _f(out.get("valor_hora"))
        if vh <= 0:
            sal = _f(emp.get("salary"))
            vh = round(sal / 220, 2) if sal else 0
        if vh <= 0:
            raise ModeloErro("Informe o valor da hora.")
        out.update(valor_hora_brl=_brl(vh), valor_hora_extenso=valor_extenso(vh),
                   atividades=out.get("atividades") or "as inerentes à função")

    elif codigo == "termino_experiencia":
        fim = _dt(out.get("termino"))
        if not fim:
            fim = _dt(var.get("experiencia.fim_prorrogacao")) or _dt(var.get("experiencia.fim"))
        out["termino_br"] = _br(fim)

    elif codigo == "acordo_compensacao":
        out["modalidade_texto"] = {
            "mensal": "As horas trabalhadas além da jornada normal em um dia serão compensadas com redução da jornada "
                      "em outro dia, **dentro do mesmo mês** (CLT, art. 59, §6º).",
            "banco_6_meses": "Banco de horas individual: as horas excedentes serão compensadas em **até 6 meses** "
                             "contados da sua realização (CLT, art. 59, §5º).",
        }.get(out.get("modalidade"), "")
        if not out["modalidade_texto"]:
            raise ModeloErro("Modalidade de compensação inválida.")

    elif codigo == "acordo_prorrogacao":
        if _f(out.get("adicional")) < 50:
            raise ModeloErro("O adicional de hora extra não pode ser menor que 50% (CF, art. 7º, XVI).")
        out["adicional"] = f"{_f(out['adicional']):g}"

    elif codigo in ("aviso_ferias", "abono_pecuniario"):
        prog = extras.get("programacao") or {}
        ini_aq = _dt(out.get("periodo_inicio")) or _dt(prog.get("periodo_inicio")) or adm
        if not ini_aq:
            raise ModeloErro("Informe o início do período aquisitivo.")
        fim_aq = _somar_anos(ini_aq, 1) - timedelta(days=1)
        out["periodo_aquisitivo"] = f"{_br(ini_aq)} a {_br(fim_aq)}"
        if codigo == "aviso_ferias":
            inicio = _dt(out.get("data_inicio")) or _dt(prog.get("data_inicio"))
            if not inicio:
                raise ModeloErro("Informe o início do gozo das férias.")
            dias = _int(campos.get("dias")) or _int(prog.get("dias_gozo")) or 30
            abono = _int(campos.get("dias_abono")) if _txt(campos.get("dias_abono")) else _int(prog.get("dias_abono"))
            if dias < 5:
                raise ModeloErro("O período de férias não pode ter menos de 5 dias (CLT, art. 134, §1º).")
            if abono < 0 or abono > 10 or dias + abono > 30:
                raise ModeloErro("Gozo mais abono não podem passar de 30 dias, e o abono é de até 1/3 (CLT, art. 143).")
            fim = inicio + timedelta(days=dias - 1)
            out.update(dias=str(dias), gozo_inicio=_br(inicio), gozo_fim=_br(fim), retorno=_br(fim + timedelta(days=1)),
                       data_pagamento=_br(inicio - timedelta(days=2)),
                       abono_texto=f"{abono} dias" if abono else "não")
        else:
            abono = _int(out.get("dias_abono"))
            if abono < 1 or abono > 10:
                raise ModeloErro("O abono pecuniário é de até 1/3 das férias (até 10 dias) — CLT, art. 143.")
            out.update(dias_abono=str(abono), prazo_requerimento=_br(fim_aq - timedelta(days=15)))

    elif codigo == "adiantamento_13_ferias":
        ano = _int(out.get("ano"))
        if ano < 2000 or ano > 2100:
            raise ModeloErro("Ano inválido.")
        out["ano"] = str(ano)

    elif codigo == "vale_transporte":
        out["opcao_texto"] = {
            "optante": "**( X ) DESEJO RECEBER o vale-transporte** para o deslocamento residência–trabalho–residência, "
                       "autorizando o desconto de até 6% do meu salário básico (Lei 7.418/1985, art. 4º, parágrafo único), "
                       "utilizando os meios de transporte abaixo:",
            "renuncia": "**( X ) NÃO DESEJO RECEBER o vale-transporte**, pois não necessito dele para o deslocamento "
                        "residência–trabalho–residência.",
        }.get(out.get("opcao"), "")
        if not out["opcao_texto"]:
            raise ModeloErro("Opção de vale-transporte inválida.")

    elif codigo == "autorizacao_desconto":
        valor, parcelas = _f(out.get("valor")), _int(out.get("parcelas"), 1) or 1
        if valor <= 0:
            raise ModeloErro("Informe o valor do desconto.")
        if parcelas < 1:
            raise ModeloErro("Número de parcelas inválido.")
        out.update(valor_brl=_brl(valor), valor_extenso=valor_extenso(valor), parcelas=str(parcelas),
                   valor_parcela=_brl(round(valor / parcelas, 2)),
                   descricao=out.get("descricao") or "_______________________________________________")

    elif codigo == "carta_recomendacao":
        ate = _dt(out.get("ate")) or _dt(emp.get("termination_date"))
        out["periodo_ate"] = f"a {_br(ate)}" if ate else "até a presente data"

    elif codigo == "abandono_emprego":
        ult = _dt(out.get("ultimo_dia"))
        if not ult:
            raise ModeloErro("Informe o último dia trabalhado.")
        prazo = _int(out.get("prazo_dias"), 3)
        if prazo < 1:
            raise ModeloErro("Prazo para retorno inválido.")
        out.update(ultimo_dia_br=_br(ult), dia_seguinte=_br(ult + timedelta(days=1)), prazo_dias=str(prazo))
    return out


# ─── Renderização ─────────────────────────────────────────────────────────────

CSS = """*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;max-width:820px;margin:32px auto;padding:20px 36px;
color:#000;background:#fff;font-size:13px}
h1{text-align:center;font-size:15px;text-transform:uppercase;border-bottom:2px solid #000;padding-bottom:8px;margin:0 0 18px}
h2{font-size:13px;text-transform:uppercase;margin:18px 0 4px}
p{line-height:1.7;text-align:justify;margin:6px 0}ul{margin:6px 0 6px 22px;padding:0}li{line-height:1.6;margin:2px 0}
table{width:100%;border-collapse:collapse;margin:10px 0}th,td{border:1px solid #555;padding:5px 8px;font-size:12px;text-align:left}
th{background:#eee}.sig{margin-top:56px;display:grid;grid-template-columns:1fr 1fr;gap:56px 40px;page-break-inside:avoid}
.sig.um{grid-template-columns:1fr;width:50%;margin-left:auto;margin-right:auto}
.sig div{text-align:center;border-top:1px solid #000;padding-top:6px;font-size:11px;line-height:1.4}
.vazio{color:#666;font-style:italic}.rodape{margin-top:28px;font-size:10px;color:#555;text-align:center}
@media print{body{margin:0;padding:0 8mm}.noprint{display:none}}"""

_RE_VAR = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
_RE_BLOCO = re.compile(r"^\[\[\s*([\w]+)\s*(?::\s*(.*?))?\s*\]\]$")
BLOCOS = {"assinaturas", "dependentes_salario_familia", "dependentes_ir", "vale_transporte"}
ASSINANTES = {"empregador", "empregado", "testemunhas", "recebido"}


def variaveis_do_texto(texto: str) -> List[str]:
    return sorted(set(_RE_VAR.findall(texto or "")))


def validar_texto(texto: str, codigo: Optional[str] = None) -> None:
    """Recusa variáveis ou blocos desconhecidos, para o erro aparecer ao salvar e não no papel."""
    if not _txt(texto):
        raise ModeloErro("O texto do modelo está vazio.")
    if len(texto) > 60000:
        raise ModeloErro("Texto muito longo (máximo de 60.000 caracteres).")
    proprias = set(campos_calculados(codigo))
    desconhecidas = [v for v in variaveis_do_texto(texto) if v not in VARIAVEIS and v not in proprias]
    if desconhecidas:
        raise ModeloErro("Variáveis desconhecidas: " + ", ".join("{{" + v + "}}" for v in desconhecidas))
    for linha in texto.splitlines():
        m = _RE_BLOCO.match(linha.strip())
        if linha.strip().startswith("[[") and not m:
            raise ModeloErro(f"Bloco mal escrito: {linha.strip()}")
        if m:
            if m.group(1) not in BLOCOS:
                raise ModeloErro(f"Bloco desconhecido: [[{m.group(1)}]]")
            if m.group(1) == "assinaturas":
                nomes = [n.strip() for n in (m.group(2) or "").split(",") if n.strip()]
                ruins = [n for n in nomes if n not in ASSINANTES]
                if not nomes or ruins:
                    raise ModeloErro("Assinaturas aceitas: empregador, empregado, testemunhas, recebido.")


# variáveis que cada modelo-padrão calcula (além dos seus campos)
_CALCULADAS = {
    "contrato_experiencia": ["fim_periodo", "fim_prorrogacao"],
    "prorrogacao_experiencia": ["fim_periodo", "fim_prorrogacao"],
    "contrato_determinado": ["data_termino_br", "duracao_dias", "justificativa_texto"],
    "contrato_intermitente": ["valor_hora_brl", "valor_hora_extenso"],
    "termino_experiencia": ["termino_br"],
    "acordo_compensacao": ["modalidade_texto"],
    "aviso_ferias": ["periodo_aquisitivo", "gozo_inicio", "gozo_fim", "retorno", "data_pagamento", "abono_texto"],
    "abono_pecuniario": ["periodo_aquisitivo", "prazo_requerimento"],
    "vale_transporte": ["opcao_texto"],
    "autorizacao_desconto": ["valor_brl", "valor_extenso", "valor_parcela"],
    "carta_recomendacao": ["periodo_ate"],
    "abandono_emprego": ["ultimo_dia_br", "dia_seguinte"],
}


def campos_calculados(codigo: Optional[str]) -> List[str]:
    m = MODELOS.get(codigo or "")
    if not m:
        return []
    return [c["nome"] for c in m.get("campos", [])] + _CALCULADAS.get(codigo, [])


def _inline(txt: str, var: Dict[str, str]) -> str:
    """Escapa o texto, troca as variáveis (também escapadas) e aplica **negrito**."""
    partes, pos = [], 0
    for m in _RE_VAR.finditer(txt):
        partes.append(_esc(txt[pos:m.start()]))
        valor = var.get(m.group(1), "")
        partes.append(_inline_valor(valor) if valor else '<span class="vazio">__________</span>')
        pos = m.end()
    partes.append(_esc(txt[pos:]))
    html = "".join(partes)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)


def _inline_valor(valor: str) -> str:
    # valores calculados podem conter **negrito**; o resto é escapado
    return _esc(valor).replace("\n", "<br>")


def _tabela_dependentes(deps: List[Dict[str, Any]], tipo: str, hoje: date) -> str:
    linhas = []
    for d in deps:
        nasc = _dt(d.get("data_nascimento"))
        if tipo == "salario_familia":
            marcado = _int(d.get("salario_familia"))
            idade_ok = nasc and _somar_anos(nasc, 14) > hoje
            if not marcado or not idade_ok:
                continue
            linhas.append(f"<tr><td>{_esc(_txt(d.get('nome')))}</td><td>{_br(nasc)}</td>"
                          f"<td>{_esc(_txt(d.get('cpf')))}</td><td>{_br(_somar_anos(nasc, 14) - timedelta(days=1))}</td></tr>")
        else:
            if not _int(d.get("irrf")):
                continue
            par = PARENTESCO.get(_txt(d.get("parentesco")), _txt(d.get("parentesco")))
            linhas.append(f"<tr><td>{_esc(_txt(d.get('nome')))}</td><td>{_esc(par)}</td>"
                          f"<td>{_br(nasc) if nasc else ''}</td><td>{_esc(_txt(d.get('cpf')))}</td></tr>")
    if tipo == "salario_familia":
        cab = "<tr><th>Nome do filho(a) ou equiparado(a)</th><th>Nascimento</th><th>CPF</th><th>Direito até</th></tr>"
    else:
        cab = "<tr><th>Nome do dependente</th><th>Parentesco</th><th>Nascimento</th><th>CPF</th></tr>"
    if not linhas:
        linhas = ['<tr><td colspan="4" class="vazio">Nenhum dependente marcado no cadastro. Preencha à mão:</td></tr>'] + \
                 ["<tr><td>&nbsp;</td><td></td><td></td><td></td></tr>"] * 3
    return f"<table>{cab}{''.join(linhas)}</table>"


def _tabela_vt(vt: List[Dict[str, Any]], opcao: str) -> str:
    if opcao == "renuncia":
        return ""
    linhas = [f"<tr><td>{_esc(_txt(v.get('descricao')))}</td><td>{_brl(v.get('tarifa'))}</td>"
              f"<td>{_int(v.get('vales_dia'))}</td></tr>" for v in vt if _int(v.get("ativo"), 1)]
    if not linhas:
        linhas = ["<tr><td>&nbsp;</td><td></td><td></td></tr>"] * 4
    return ("<table><tr><th>Linha / meio de transporte (ida e volta)</th><th>Tarifa</th><th>Vales por dia</th></tr>"
            + "".join(linhas) + "</table>")


def _assinaturas(nomes: List[str], var: Dict[str, str]) -> str:
    caixas = []
    for n in nomes:
        if n == "empregador":
            caixas.append(f"<div>{_esc(var.get('empresa.razao_social', ''))}<br>EMPREGADOR</div>")
        elif n == "empregado":
            caixas.append(f"<div>{_esc(var.get('empregado.nome', ''))}<br>EMPREGADO(A) — CPF {_esc(var.get('empregado.cpf', ''))}</div>")
        elif n == "testemunhas":
            caixas.append("<div>Testemunha 1<br>CPF: ____________________</div>")
            caixas.append("<div>Testemunha 2<br>CPF: ____________________</div>")
        elif n == "recebido":
            caixas.append(f"<div>Recebido por {_esc(var.get('empresa.razao_social', ''))}<br>em ___/___/______</div>")
    classe = "sig um" if len(caixas) == 1 else "sig"
    return f'<div class="{classe}">{"".join(caixas)}</div>'


def renderizar(texto: str, var: Dict[str, str], titulo: str = "Documento",
               deps: Optional[List[Dict[str, Any]]] = None, vt: Optional[List[Dict[str, Any]]] = None,
               hoje: Optional[date] = None) -> str:
    hoje = hoje or hoje_local()
    deps, vt = deps or [], vt or []
    corpo: List[str] = []
    paragrafo: List[str] = []
    lista: List[str] = []

    def fecha_par():
        if paragrafo:
            corpo.append("<p>" + "<br>".join(_inline(l, var) for l in paragrafo) + "</p>")
            paragrafo.clear()

    def fecha_lista():
        if lista:
            corpo.append("<ul>" + "".join(f"<li>{_inline(l, var)}</li>" for l in lista) + "</ul>")
            lista.clear()

    for bruta in (texto or "").replace("\r\n", "\n").split("\n"):
        linha = bruta.strip()
        if not linha:
            fecha_par(); fecha_lista()
            continue
        bloco = _RE_BLOCO.match(linha)
        if bloco:
            fecha_par(); fecha_lista()
            nome, args = bloco.group(1), bloco.group(2) or ""
            if nome == "assinaturas":
                corpo.append(_assinaturas([n.strip() for n in args.split(",") if n.strip()], var))
            elif nome == "dependentes_salario_familia":
                corpo.append(_tabela_dependentes(deps, "salario_familia", hoje))
            elif nome == "dependentes_ir":
                corpo.append(_tabela_dependentes(deps, "ir", hoje))
            elif nome == "vale_transporte":
                corpo.append(_tabela_vt(vt, var.get("opcao", "optante")))
            continue
        if linha.startswith("## "):
            fecha_par(); fecha_lista()
            corpo.append(f"<h2>{_inline(linha[3:], var)}</h2>")
        elif linha.startswith("# "):
            fecha_par(); fecha_lista()
            corpo.append(f"<h1>{_inline(linha[2:], var)}</h1>")
        elif linha.startswith("- "):
            fecha_par()
            lista.append(linha[2:])
        else:
            fecha_lista()
            paragrafo.append(linha)
    fecha_par(); fecha_lista()

    # **negrito** vindo de valores calculados (ex.: modalidade_texto) — já escapados
    html_corpo = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", "\n".join(corpo))
    return (f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>{_esc(titulo)}</title>'
            f"<style>{CSS}</style></head><body>{html_corpo}"
            f'<div class="rodape noprint">Emitido em {_br(hoje)} pelo Cortex ERP</div></body></html>')


# ─── Persistência (personalização por empresa) ───────────────────────────────

def _linhas_personalizadas(conn, company_id: int) -> Dict[str, Dict[str, Any]]:
    rows = conn.execute("SELECT codigo, titulo, texto, atualizado_em, atualizado_por FROM dp_doc_modelos "
                        "WHERE company_id=?", (company_id,)).fetchall()
    return {r["codigo"]: dict(r) for r in rows}


def listar(conn, company_id: int) -> List[Dict[str, Any]]:
    pers = _linhas_personalizadas(conn, company_id)
    out = []
    for cod, m in MODELOS.items():
        p = pers.get(cod)
        out.append({"codigo": cod, "titulo": (p or {}).get("titulo") or m["titulo"], "grupo": m["grupo"],
                    "base_legal": m["base_legal"], "descricao": m["descricao"], "campos": m["campos"],
                    "personalizado": bool(p), "proprio": False})
    for cod, p in pers.items():
        if cod not in MODELOS:
            out.append({"codigo": cod, "titulo": p["titulo"] or "Modelo próprio", "grupo": "Personalizados",
                        "base_legal": "", "descricao": "Modelo criado pela empresa.", "campos": [],
                        "personalizado": True, "proprio": True})
    return out


def obter(conn, company_id: int, codigo: str) -> Dict[str, Any]:
    p = _linhas_personalizadas(conn, company_id).get(codigo)
    m = MODELOS.get(codigo)
    if not m and not p:
        raise KeyError(codigo)
    base = {"codigo": codigo, "grupo": m["grupo"] if m else "Personalizados",
            "base_legal": m["base_legal"] if m else "", "descricao": m["descricao"] if m else "Modelo criado pela empresa.",
            "campos": m["campos"] if m else [], "proprio": not m,
            "titulo_padrao": m["titulo"] if m else "", "texto_padrao": m["texto"] if m else "",
            "variaveis": VARIAVEIS, "calculadas": campos_calculados(codigo)}
    if p:
        base.update(titulo=p["titulo"] or (m or {}).get("titulo", ""), texto=p["texto"], personalizado=True,
                    atualizado_em=p["atualizado_em"], atualizado_por=p["atualizado_por"])
    else:
        base.update(titulo=m["titulo"], texto=m["texto"], personalizado=False)
    return base


def salvar(conn, company_id: int, codigo: str, titulo: str, texto: str, usuario: str) -> None:
    titulo = _txt(titulo)[:120]
    if codigo not in MODELOS and not codigo.startswith("pers_"):
        raise KeyError(codigo)
    if not titulo:
        raise ModeloErro("Informe o título do modelo.")
    validar_texto(texto, codigo)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existe = conn.execute("SELECT 1 FROM dp_doc_modelos WHERE company_id=? AND codigo=?", (company_id, codigo)).fetchone()
    if existe:
        conn.execute("UPDATE dp_doc_modelos SET titulo=?, texto=?, atualizado_em=?, atualizado_por=? "
                     "WHERE company_id=? AND codigo=?", (titulo, texto, agora, usuario, company_id, codigo))
    else:
        conn.execute("INSERT INTO dp_doc_modelos (company_id, codigo, titulo, texto, atualizado_em, atualizado_por) "
                     "VALUES (?,?,?,?,?,?)", (company_id, codigo, titulo, texto, agora, usuario))


def novo_codigo(conn, company_id: int) -> str:
    rows = conn.execute("SELECT codigo FROM dp_doc_modelos WHERE company_id=? AND codigo LIKE 'pers_%'",
                        (company_id,)).fetchall()
    nums = [_int(r["codigo"][5:]) for r in rows]
    return f"pers_{max(nums, default=0) + 1}"


def excluir(conn, company_id: int, codigo: str) -> bool:
    cur = conn.execute("DELETE FROM dp_doc_modelos WHERE company_id=? AND codigo=?", (company_id, codigo))
    return (cur.rowcount or 0) > 0


def gerar(conn, company_id: int, codigo: str, emp: Dict[str, Any], co: Dict[str, Any],
          campos: Dict[str, Any], texto: Optional[str] = None, titulo: Optional[str] = None,
          hoje: Optional[date] = None) -> str:
    """Gera o HTML do documento para o empregado. ``texto`` permite pré-visualizar sem salvar."""
    if codigo == "_novo" and texto is not None:          # prévia de modelo próprio ainda não salvo
        modelo = {"titulo": titulo or "Novo modelo", "texto": texto}
    else:
        modelo = obter(conn, company_id, codigo)
    texto = modelo["texto"] if texto is None else texto
    validar_texto(texto, codigo)
    hoje = hoje or hoje_local()
    var = montar_variaveis(emp, co, hoje)
    extras: Dict[str, Any] = {"hoje": hoje.isoformat()}
    if codigo in ("aviso_ferias", "abono_pecuniario"):
        prog = conn.execute(
            "SELECT * FROM ferias_programacao WHERE company_id=? AND employee_id=? AND status IN ('programada','calculada') "
            "ORDER BY CASE WHEN data_inicio >= ? THEN 0 ELSE 1 END, "
            "CASE WHEN status='programada' THEN 0 ELSE 1 END, data_inicio LIMIT 1",
            (company_id, emp["id"], hoje.isoformat())).fetchone()
        extras["programacao"] = dict(prog) if prog else {}
    var.update(calcular_campos(codigo, emp, var, campos, extras))
    deps = [dict(r) for r in conn.execute(
        "SELECT * FROM employee_dependents WHERE employee_id=? AND company_id=? ORDER BY id",
        (emp["id"], company_id)).fetchall()]
    vt = [dict(r) for r in conn.execute(
        "SELECT * FROM employee_vt WHERE employee_id=? AND company_id=? ORDER BY id",
        (emp["id"], company_id)).fetchall()]
    nome = f"{titulo or modelo['titulo']} — {var.get('empregado.nome', '')}"
    return renderizar(texto, var, nome, deps, vt, hoje)
