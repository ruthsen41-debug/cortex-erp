"""Tabelas e mapeamentos do eSocial S-1.3 usados pelos geradores de eventos.

Fonte: "Tabelas do eSocial" e leiautes S-1.3 (NT 07/2026), gov.br/esocial.
"""
from typing import Dict, Optional, Tuple

VERSAO_LEIAUTE = "v_S_01_03_00"
VER_PROC = "CortexERP-1.0"

# Pacotes de XSD oficiais por data de entrada em produção (pasta xsd/eventos_AAAAMMDD)
PACOTES_XSD = [("2026-10-26", "eventos_20261026"), ("2026-11-23", "eventos_20261123")]


def pacote_vigente(hoje: str = "") -> str:
    from datetime import date as _date
    hoje = hoje or _date.today().isoformat()
    vigente = PACOTES_XSD[0][1]
    for inicio, pasta in PACOTES_XSD:
        if hoje >= inicio:
            vigente = pasta
    return vigente

# Evento -> (elemento raiz dentro de <eSocial>, nome do XSD, grupo do lote)
# Grupos do lote: 1 = tabelas, 2 = não periódicos, 3 = periódicos
EVENTOS: Dict[str, Tuple[str, str, int]] = {
    "S-1000": ("evtInfoEmpregador", "evtInfoEmpregador", 1),
    "S-1005": ("evtTabEstab", "evtTabEstab", 1),
    "S-1010": ("evtTabRubrica", "evtTabRubrica", 1),
    "S-1020": ("evtTabLotacao", "evtTabLotacao", 1),
    "S-1200": ("evtRemun", "evtRemun", 3),
    "S-1210": ("evtPgtos", "evtPgtos", 3),
    "S-1298": ("evtReabreEvPer", "evtReabreEvPer", 3),
    "S-1299": ("evtFechaEvPer", "evtFechaEvPer", 3),
    "S-2200": ("evtAdmissao", "evtAdmissao", 2),
    "S-2205": ("evtAltCadastral", "evtAltCadastral", 2),
    "S-2206": ("evtAltContratual", "evtAltContratual", 2),
    "S-2230": ("evtAfastTemp", "evtAfastTemp", 2),
    "S-2299": ("evtDeslig", "evtDeslig", 2),
    "S-2210": ("evtCAT", "evtCAT", 2),
    "S-2220": ("evtMonit", "evtMonit", 2),
    "S-2240": ("evtExpRisco", "evtExpRisco", 2),
    "S-2298": ("evtReintegr", "evtReintegr", 2),
    "S-2300": ("evtTSVInicio", "evtTSVInicio", 2),
    "S-2399": ("evtTSVTermino", "evtTSVTermino", 2),
    "S-3000": ("evtExclusao", "evtExclusao", 2),
}

NOMES_EVENTOS = {
    "S-1000": "Informações do empregador",
    "S-1005": "Tabela de estabelecimentos",
    "S-1010": "Tabela de rubricas",
    "S-1020": "Tabela de lotações tributárias",
    "S-1200": "Remuneração do trabalhador",
    "S-1210": "Pagamentos de rendimentos",
    "S-1298": "Reabertura dos eventos periódicos",
    "S-1299": "Fechamento dos eventos periódicos",
    "S-2200": "Admissão do trabalhador",
    "S-2205": "Alteração de dados cadastrais",
    "S-2206": "Alteração de contrato de trabalho",
    "S-2230": "Afastamento temporário",
    "S-2299": "Desligamento",
    "S-2210": "Comunicação de acidente de trabalho (CAT)",
    "S-2220": "Monitoramento da saúde do trabalhador (ASO)",
    "S-2240": "Condições ambientais do trabalho (agentes nocivos)",
    "S-2298": "Reintegração",
    "S-2300": "Trabalhador sem vínculo — início (estagiário)",
    "S-2399": "Trabalhador sem vínculo — término",
    "S-3000": "Exclusão de eventos",
    # Totalizadores devolvidos pelo governo
    "S-5001": "Contribuições sociais por trabalhador",
    "S-5002": "IRRF por trabalhador",
    "S-5003": "FGTS por trabalhador",
    "S-5011": "Contribuições sociais consolidadas",
    "S-5012": "IRRF consolidado",
    "S-5013": "FGTS consolidado",
}

# Endereços oficiais (Manual de Orientação ao Desenvolvedor v1.16)
WEBSERVICES = {
    1: {  # Produção
        "envio": "https://webservices.envio.esocial.gov.br/servicos/empregador/enviarloteeventos/WsEnviarLoteEventos.svc",
        "consulta": "https://webservices.consulta.esocial.gov.br/servicos/empregador/consultarloteeventos/WsConsultarLoteEventos.svc",
    },
    2: {  # Produção restrita (testes)
        "envio": "https://webservices.producaorestrita.esocial.gov.br/servicos/empregador/enviarloteeventos/WsEnviarLoteEventos.svc",
        "consulta": "https://webservices.producaorestrita.esocial.gov.br/servicos/empregador/consultarloteeventos/WsConsultarLoteEventos.svc",
    },
}
AMBIENTES = {1: "Produção", 2: "Produção restrita (testes)"}

# Tabela 08 — Classificação tributária (sugestão a partir do regime do cadastro da empresa)
CLASS_TRIB_POR_REGIME = {
    "mei": "04",
    "simples_nacional": "01",
    "simples": "01",
    "lucro_presumido": "99",
    "lucro_real": "99",
}
CLASS_TRIB = {
    "01": "Simples Nacional com tributação previdenciária substituída",
    "02": "Simples Nacional com tributação previdenciária não substituída (Anexo IV)",
    "03": "Simples Nacional com tributação substituída e não substituída",
    "04": "Microempreendedor Individual - MEI",
    "99": "Pessoas jurídicas em geral",
}

# Tabela 19 — Motivos de desligamento (a partir do tipo de rescisão do sistema)
MOTIVO_DESLIGAMENTO = {
    "com_justa_causa": "01",
    "sem_justa_causa": "02",
    "antecipada_empregador": "03",
    "antecipada_empregado": "04",
    "culpa_reciproca": "05",
    "termino_contrato": "06",
    "pedido_demissao": "07",
    "rescisao_indireta": "17",
    "falecimento": "10",
    "acordo": "33",
}

# Tabela 18 — Motivos de afastamento (a partir do tipo de afastamento do sistema).
# None = não se informa no eSocial (faltas legais curtas, por exemplo).
MOTIVO_AFASTAMENTO: Dict[str, Optional[str]] = {
    "acidente_trabalho": "01",
    "auxilio_doenca_b91": "01",
    "auxilio_doenca_b31": "03",
    "atestado": "03",
    "maternidade": "17",
    "maternidade_180": "17",
    "paternidade": None,
    "luto": None,
    "casamento": None,
    "doacao_sangue": None,
    "militar": "29",
    "suspensao": "30",
    "licenca_remunerada": "16",
    "licenca_nao_remunerada": "21",
    "outros": None,
}
# Doença não relacionada ao trabalho (03) só é informada quando passa de 15 dias
DIAS_MINIMOS_AFASTAMENTO = {"03": 16}

# Unidade do salário fixo (undSalFixo) — o cadastro do funcionário já usa os mesmos códigos
UND_SAL_FIXO = {"1", "2", "3", "4", "5", "6", "7"}

# Tipo de jornada (tpJornada) a partir da escala do cadastro
TP_JORNADA_POR_ESCALA = {"12x36": "2", "5x2": "5", "6x1": "3", "4x2": "3", "turno": "7"}

# Natureza (Tabela 03) e incidências das rubricas padrão do sistema.
# codigo -> (natRubr, tpRubr, codIncCP, codIncIRRF, codIncFGTS)
# tpRubr: 1 vencimento, 2 desconto, 3 informativa, 4 informativa dedutora
RUBRICAS_PADRAO: Dict[str, Tuple[str, str, str, str, str]] = {
    "0001": ("1000", "1", "11", "11", "11"),   # Salário
    "0002": ("1003", "1", "11", "11", "11"),   # Hora extra 50%
    "0003": ("1003", "1", "11", "11", "11"),   # Hora extra 100%
    "0004": ("1205", "1", "11", "11", "11"),   # Adicional noturno
    "0005": ("1202", "1", "11", "11", "11"),   # Insalubridade
    "0006": ("1203", "1", "11", "11", "11"),   # Periculosidade
    "0007": ("1207", "1", "11", "11", "11"),   # Comissões
    "0008": ("1016", "1", "11", "13", "11"),   # Férias
    "0009": ("1017", "1", "11", "13", "11"),   # 1/3 de férias
    "0010": ("5001", "1", "12", "12", "12"),   # 13º salário
    "0011": ("1002", "1", "11", "11", "11"),   # DSR
    "0012": ("1409", "1", "51", "9", "00"),    # Salário-família
    "0013": ("3501", "1", "11", "11", "00"),   # Pró-labore
    "0020": ("5504", "1", "00", "9", "12"),    # 13º — adiantamento (1ª parcela)
    "0021": ("5001", "1", "12", "12", "12"),   # Média de variáveis no 13º
    "0022": ("1016", "1", "11", "13", "11"),   # Média de variáveis nas férias
    "0030": ("1023", "1", "00", "75", "00"),   # Abono pecuniário
    "0031": ("1023", "1", "00", "75", "00"),   # 1/3 sobre abono
    "0032": ("1024", "1", "00", "13", "00"),   # Férias em dobro
    "0040": ("6000", "1", "11", "11", "11"),   # Saldo de salário
    "0041": ("6003", "1", "00", "74", "21"),   # Aviso prévio indenizado
    "0042": ("6002", "1", "12", "12", "12"),   # 13º proporcional na rescisão
    "0043": ("6001", "1", "00", "12", "12"),   # 13º sobre aviso indenizado
    "0044": ("6007", "1", "00", "74", "00"),   # Férias vencidas indenizadas
    "0045": ("6006", "1", "00", "74", "00"),   # Férias proporcionais indenizadas
    "0046": ("6006", "1", "00", "74", "00"),   # 1/3 de férias na rescisão
    "0047": ("6004", "1", "00", "74", "00"),   # Dobra de férias
    "0100": ("9201", "2", "31", "41", "00"),   # INSS
    "0101": ("9203", "2", "00", "31", "00"),   # IRRF
    "0102": ("9216", "2", "00", "9", "00"),    # Vale-transporte
    "0103": ("9220", "2", "00", "9", "00"),    # Alimentação
    "0104": ("9213", "2", "00", "51", "00"),   # Pensão alimentícia
    "0105": ("9200", "2", "00", "9", "00"),    # Adiantamento
    "0106": ("9207", "2", "11", "11", "11"),   # Faltas
    "0107": ("9210", "2", "11", "11", "11"),   # DSR sobre faltas
    "0108": ("9208", "2", "11", "11", "11"),   # Atrasos
    "0109": ("9231", "2", "00", "9", "00"),    # Contribuição assistencial
    "0110": ("9299", "2", "00", "9", "00"),    # Benefícios (coparticipação)
    "0120": ("9214", "2", "00", "9", "12"),    # Desconto do adiantamento do 13º
    "0121": ("9201", "2", "32", "42", "00"),   # INSS sobre 13º
    "0122": ("9203", "2", "00", "32", "00"),   # IRRF sobre 13º
    "0130": ("6901", "2", "00", "9", "00"),    # Desconto do aviso prévio
    "0050": ("1350", "1", "00", "11", "00"),   # Bolsa-auxílio de estágio
    "0060": ("3501", "1", "11", "11", "00"),   # Remuneração de autônomo (RPA)
}
# Rubricas próprias do eSocial (estágio e autônomo) que não estão no cadastro da folha
RUBRICAS_EXTRAS = [("0050", "Bolsa-auxílio de estágio", "provento"), ("0060", "Remuneração de autônomo (RPA)", "provento")]
# Rubricas internas que não vão ao eSocial (bases e FGTS são apurados pelo próprio governo)
RUBRICAS_NAO_ENVIADAS = {"0200", "0201", "0202", "0203", "0210"}


def rubrica_esocial(codigo: str, tipo: str, incide_inss: int, incide_irrf: int, incide_fgts: int,
                    nat_cadastro: str = "") -> Tuple[str, str, str, str, str]:
    """Natureza e incidências de uma rubrica: padrão do sistema ou derivadas do cadastro."""
    if codigo in RUBRICAS_PADRAO:
        return RUBRICAS_PADRAO[codigo]
    nat = nat_cadastro if (nat_cadastro or "").isdigit() and len(nat_cadastro) == 4 else ""
    if tipo == "desconto":
        return (nat or "9299", "2", "00", "9", "00")
    if tipo == "informativo":
        return (nat or "9989", "3", "00", "9", "00")
    return (nat or "1299", "1",
            "11" if incide_inss else "00",
            "11" if incide_irrf else "79",
            "11" if incide_fgts else "00")
