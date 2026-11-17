"""
Gerador de XMLs do eSocial.
Eventos suportados:
  S-2200  Cadastramento Inicial / Admissão
  S-1200  Remuneração Mensal do Trabalhador
  S-2299  Desligamento
  S-2298  Reintegração
Versão do leiaute: S-1.3
"""
import re
import uuid
from datetime import date as _date
from typing import Any, Dict, List, Optional


def _c(v: Any) -> str:
    return str(v or "").strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _d(v: str) -> str:
    if not v:
        return ""
    clean = re.sub(r"\D", "", str(v)[:10])
    if len(clean) == 8:
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
    return v


def _n(v: Any, dec: int = 2) -> str:
    try:
        return f"{float(v or 0):.{dec}f}"
    except Exception:
        return "0.00"


def _proc_id() -> str:
    return uuid.uuid4().hex[:8].upper()


def _header(empresa: Dict, num_inscricao: str, transmissor_cnpj: str, evento_id: str) -> str:
    today = _date.today().isoformat()
    hora = "00:00:00"
    return f"""<eSocial xmlns="http://www.esocial.gov.br/schema/lote/envio/v1_1_1">
  <envioLoteEventos grupo="1">
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>{re.sub(r"\\D", "", _c(num_inscricao))[:8]}</nrInsc>
    </ideEmpregador>
    <ideTransmissor>
      <tpInsc>1</tpInsc>
      <nrInsc>{re.sub(r"\\D", "", _c(transmissor_cnpj))}</nrInsc>
    </ideTransmissor>
    <eventos>
      <evento Id="{evento_id}">"""


def _footer() -> str:
    return """
      </evento>
    </eventos>
  </envioLoteEventos>
</eSocial>"""


def _ide_evento(ind_retif: str = "1", nr_rec: str = "") -> str:
    return f"""
        <ideEvento>
          <indRetif>{ind_retif}</indRetif>
          <nrRec>{nr_rec}</nrRec>
          <tpAmb>1</tpAmb>
          <procEmi>1</procEmi>
          <verProc>1.0.0</verProc>
        </ideEvento>"""


def _ide_empregador(cnpj: str) -> str:
    cnpj_clean = re.sub(r"\D", "", cnpj)
    return f"""
        <ideEmpregador>
          <tpInsc>1</tpInsc>
          <nrInsc>{cnpj_clean}</nrInsc>
        </ideEmpregador>"""


# ─── S-2200 — Admissão ───────────────────────────────────────────────────────

def gerar_s2200(empresa: Dict, funcionario: Dict) -> str:
    """Gera o XML do evento S-2200 (Admissão / Cadastramento Inicial)."""
    ev_id = f"ID1{re.sub(r'\\D', '', _c(empresa.get('cnpj', '')))}{_date.today().strftime('%Y%m%d%H%M%S')}{'00001'}"
    cpf = re.sub(r"\D", "", _c(funcionario.get("cpf", "")))
    adm = _d(funcionario.get("admission_date", ""))
    categoria = _c(funcionario.get("esocial_category", "101"))  # 101=CLT
    regime = _c(funcionario.get("regime_previdenciario", "1"))   # 1=RGPS

    xml = _header(empresa, empresa.get("cnpj", ""), empresa.get("cnpj", ""), ev_id)
    xml += f"""
        <evtAdmissao Id="{ev_id}">
          {_ide_evento()[9:]}
          {_ide_empregador(empresa.get("cnpj", ""))[9:]}
          <trabalhador>
            <cpfTrab>{cpf}</cpfTrab>
            <nmTrab>{_c(funcionario.get("name"))}</nmTrab>
            <sexo>{_c(funcionario.get("sexo", "M"))}</sexo>
            <racaCor>1</racaCor>
            <estCiv>1</estCiv>
            <grauInstr>07</grauInstr>
            <nascimento>
              <dtNascto>{_d(funcionario.get("birth_date", "1990-01-01"))}</dtNascto>
              <codMunic>5102504</codMunic>
              <uf>{_c(funcionario.get("uf", "MT"))}</uf>
            </nascimento>
            <documentos>
              <CNH>
                <nrReg>{_c(funcionario.get("cnh", ""))}</nrReg>
              </CNH>
            </documentos>
          </trabalhador>
          <vinculo>
            <matriCad>{_c(funcionario.get("matricula", "001"))}</matriCad>
            <tpRegTrab>1</tpRegTrab>
            <tpRegPrev>{regime}</tpRegPrev>
            <dtAdm>{adm}</dtAdm>
            <tpAdmissao>1</tpAdmissao>
            <indAdmissao>1</indAdmissao>
            <nrProcTrab></nrProcTrab>
            <natAtividade>1</natAtividade>
            <dtBase></dtBase>
            <cnpjSindLaboral></cnpjSindLaboral>
            <cargo>
              <nmCargo>{_c(funcionario.get("role", "Funcionário"))}</nmCargo>
              <CBOCargo>{_c(funcionario.get("cbo", "111105"))}</CBOCargo>
            </cargo>
            <remuneracao>
              <vrSalFx>{_n(funcionario.get("salary", 0))}</vrSalFx>
              <undSalFixo>5</undSalFixo>
            </remuneracao>
            <localTrabalho>
              <localTrabGeral>
                <tpInsc>1</tpInsc>
                <nrInsc>{re.sub(r"\\D", "", _c(empresa.get("cnpj", "")))}</nrInsc>
              </localTrabGeral>
            </localTrabalho>
            <infoContrato>
              <tpJornada>2</tpJornada>
              <descJorn>Segunda a Sexta 08:00 às 17:00</descJorn>
              <qtdHrsSem>44</qtdHrsSem>
              <natAtividade>1</natAtividade>
            </infoContrato>
            <categoria>{categoria}</categoria>
          </vinculo>
        </evtAdmissao>"""
    xml += _footer()
    return xml


_INFORMATIVO_CODES = {"0200", "0201", "0202", "0203", "0210"}


def _extract_qtd(referencia: Any) -> str:
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(referencia or ""))
    if m:
        return m.group(1).replace(",", ".")
    return "1"


def _build_det_verbas(lines: List[Dict[str, Any]], tab_id: str) -> str:
    parts = []
    for ln in lines:
        cod = str(ln.get("codigo") or "")
        if ln.get("tipo") == "informativo" or cod in _INFORMATIVO_CODES:
            continue
        val = float(ln.get("valor") or 0)
        if val <= 0:
            continue
        qtd = _extract_qtd(ln.get("referencia"))
        parts.append(f"""                <detVerbas>
                  <codRubr>{_c(cod)}</codRubr>
                  <ideTabRubr>RUBR{_c(tab_id)}</ideTabRubr>
                  <qtd>{qtd}</qtd>
                  <fatorHr>0</fatorHr>
                  <vrUnit>{_n(val)}</vrUnit>
                  <vrRubr>{_n(val)}</vrRubr>
                </detVerbas>""")
    return "\n".join(parts)


# ─── S-1200 — Remuneração Mensal ────────────────────────────────────────────

def gerar_s1200(empresa: Dict, funcionario: Dict,
                competencia: str, payroll_item: Dict,
                lines: Optional[List[Dict[str, Any]]] = None) -> str:
    """Gera o XML do evento S-1200 (Remuneração Mensal)."""
    ev_id = f"ID1{re.sub(r'\\D', '', _c(empresa.get('cnpj', '')))}{_date.today().strftime('%Y%m%d%H%M%S')}{'00002'}"
    cpf = re.sub(r"\D", "", _c(funcionario.get("cpf", "")))
    per_ref = competencia[:7].replace("-", "")  # YYYYMM
    tab_id = str(empresa.get("id", "1"))
    rub_lines = lines if lines is not None else payroll_item.get("lines")
    det_verbas = _build_det_verbas(rub_lines or [], tab_id)
    if not det_verbas:
        det_verbas = f"""                <detVerbas>
                  <codRubr>VENC001</codRubr>
                  <ideTabRubr>{_c(tab_id)}</ideTabRubr>
                  <qtd>1</qtd>
                  <fatorHr>0</fatorHr>
                  <vrUnit>{_n(payroll_item.get("gross_salary", 0))}</vrUnit>
                  <vrRubr>{_n(payroll_item.get("gross_salary", 0))}</vrRubr>
                </detVerbas>"""
    base_inss = payroll_item.get("base_inss")
    if base_inss is None:
        base_inss = payroll_item.get("gross_salary", 0)

    xml = _header(empresa, empresa.get("cnpj", ""), empresa.get("cnpj", ""), ev_id)
    xml += f"""
        <evtRemun Id="{ev_id}">
          {_ide_evento()[9:]}
          {_ide_empregador(empresa.get("cnpj", ""))[9:]}
          <ideTrabalh>
            <tpInsc>1</tpInsc>
            <nrInsc>{cpf}</nrInsc>
            <nisTrab>{_c(funcionario.get("pis_pasep", ""))}</nisTrab>
          </ideTrabalh>
          <dmDev>
            <indApuracao>1</indApuracao>
            <perRef>{per_ref[:4]}-{per_ref[4:6]}</perRef>
            <ideEstab>
              <tpInsc>1</tpInsc>
              <nrInsc>{re.sub(r"\\D", "", _c(empresa.get("cnpj", "")))}</nrInsc>
              <ideLotacao>
                <codLotacao>001</codLotacao>
{det_verbas}
                <infoAgNocivo>
                  <grauExp>0</grauExp>
                </infoAgNocivo>
              </ideLotacao>
            </ideEstab>
            <infoPerApur>
              <ideEstabLot>
                <tpInsc>1</tpInsc>
                <nrInsc>{re.sub(r"\\D", "", _c(empresa.get("cnpj", "")))}</nrInsc>
                <codLotacao>001</codLotacao>
                <infoBaseCS>
                  <tpIncCP>11</tpIncCP>
                  <vrBcCP00>{_n(base_inss)}</vrBcCP00>
                  <vrBcCP15>0.00</vrBcCP15>
                  <vrBcCP20>0.00</vrBcCP20>
                  <vrBcCP25>0.00</vrBcCP25>
                </infoBaseCS>
              </ideEstabLot>
            </infoPerApur>
          </dmDev>
        </evtRemun>"""
    xml += _footer()
    return xml


# ─── S-2230 — Afastamento Temporário ────────────────────────────────────────

_COD_MOTIVO_AFASTAMENTO = {
    "auxilio_doenca_b31": "01",
    "auxilio_doenca_b91": "03",
    "acidente_trabalho":  "03",
    "maternidade":        "11",
    "maternidade_180":    "11",
    "paternidade":        "18",
    "paternidade_20":     "18",
    "luto":               "17",
    "casamento":          "15",
    "doacao_sangue":      "20",
    "militar":            "08",
    "suspensao":          "26",
    "outros":             "99",
}


def gerar_s2230(empresa: Dict, funcionario: Dict, afastamento: Dict) -> str:
    """Gera o XML do evento S-2230 (Afastamento Temporário do Trabalhador)."""
    ev_id = f"ID1{re.sub(r'\\D', '', _c(empresa.get('cnpj', '')))}{_date.today().strftime('%Y%m%d%H%M%S')}{'00004'}"
    cpf = re.sub(r"\D", "", _c(funcionario.get("cpf", "")))
    tipo = afastamento.get("tipo", "outros")
    cod_mot = _COD_MOTIVO_AFASTAMENTO.get(tipo, "99")

    xml = _header(empresa, empresa.get("cnpj", ""), empresa.get("cnpj", ""), ev_id)
    xml += f"""
        <evtAfastTemp Id="{ev_id}">
          {_ide_evento()[9:]}
          {_ide_empregador(empresa.get("cnpj", ""))[9:]}
          <ideVinculo>
            <cpfTrab>{cpf}</cpfTrab>
            <matriCad>{_c(funcionario.get("matricula", "001"))}</matriCad>
          </ideVinculo>
          <infoAfastamento>
            <iniAfastamento>
              <dtIniAfast>{_d(afastamento.get("data_inicio", ""))}</dtIniAfast>
              <codMotAfast>{cod_mot}</codMotAfast>
              {f'<cid>{_c(afastamento.get("cid", ""))}</cid>' if afastamento.get("cid") else ''}
            </iniAfastamento>
            {f'''<fimAfastamento>
              <dtTermAfast>{_d(afastamento.get("data_fim", ""))}</dtTermAfast>
            </fimAfastamento>''' if afastamento.get("data_fim") else ''}
          </infoAfastamento>
        </evtAfastTemp>"""
    xml += _footer()
    return xml


# ─── S-2210 — Comunicação de Acidente de Trabalho (CAT) ─────────────────────

def gerar_s2210(empresa: Dict, funcionario: Dict, acidente: Dict) -> str:
    """Gera o XML do evento S-2210 (Comunicação de Acidente de Trabalho)."""
    ev_id = f"ID1{re.sub(r'\\D', '', _c(empresa.get('cnpj', '')))}{_date.today().strftime('%Y%m%d%H%M%S')}{'00005'}"
    cpf = re.sub(r"\D", "", _c(funcionario.get("cpf", "")))

    xml = _header(empresa, empresa.get("cnpj", ""), empresa.get("cnpj", ""), ev_id)
    xml += f"""
        <evtCAT Id="{ev_id}">
          {_ide_evento()[9:]}
          {_ide_empregador(empresa.get("cnpj", ""))[9:]}
          <ideVinculo>
            <cpfTrab>{cpf}</cpfTrab>
            <matriCad>{_c(funcionario.get("matricula", "001"))}</matriCad>
          </ideVinculo>
          <cat>
            <dtAcid>{_d(acidente.get("data_acidente", ""))}</dtAcid>
            <tpAcid>{_c(acidente.get("tipo_acidente", "tipico"))}</tpAcid>
            <hrAcid>{_c(acidente.get("hora_acidente", "00:00"))}</hrAcid>
            <tpCat>1</tpCat>
            <descAcid>{_c(acidente.get("descricao", ""))}</descAcid>
            <houveAfast>{1 if acidente.get("houve_afastamento") else 0}</houveAfast>
            <localAcidente>
              <tpLocal>1</tpLocal>
              <dsLocal>{_c(acidente.get("local_acidente", ""))}</dsLocal>
            </localAcidente>
            <parteAtingida>
              <codParteAting>99999</codParteAting>
              <lateralidade>9</lateralidade>
            </parteAtingida>
            <agenteCausador>
              <codAgntCausador>99999</codAgntCausador>
            </agenteCausador>
          </cat>
        </evtCAT>"""
    xml += _footer()
    return xml


# ─── S-2299 — Desligamento ───────────────────────────────────────────────────

def gerar_s2299(empresa: Dict, funcionario: Dict,
                termination_date: str, motivo: str = "02",
                rescisao: Optional[Dict[str, Any]] = None) -> str:
    """
    Gera o XML do evento S-2299 (Desligamento).
    motivo: 01=aposentadoria, 02=pedido demissão, 03=dispensa s/jc, 04=dispensa c/jc
    """
    cnpj_clean = re.sub(r"\D", "", _c(empresa.get("cnpj", "")))
    ev_id = f"ID1{cnpj_clean}{_date.today().strftime('%Y%m%d%H%M%S')}{'00003'}"
    cpf = re.sub(r"\D", "", _c(funcionario.get("cpf", "")))
    dt_proj = ""
    verbas_resc = ""
    if rescisao:
        proj_raw = (rescisao.get("plano") or {}).get("data_projetada") or rescisao.get("data_fim") or ""
        dt_proj = _d(proj_raw) if proj_raw else ""
        det_verbas = _build_det_verbas(rescisao.get("lines") or [], str(empresa.get("id", "1")))
        if det_verbas:
            verbas_resc = f"""
            <verbasResc>
              <dmDev>
                <ideDmDev>RESC1</ideDmDev>
                <ideEstabLot>
                  <tpInsc>1</tpInsc>
                  <nrInsc>{cnpj_clean}</nrInsc>
                  <codLotacao>001</codLotacao>
{det_verbas}
                </ideEstabLot>
              </dmDev>
            </verbasResc>"""

    xml = _header(empresa, empresa.get("cnpj", ""), empresa.get("cnpj", ""), ev_id)
    xml += f"""
        <evtDeslig Id="{ev_id}">
          {_ide_evento()[9:]}
          {_ide_empregador(empresa.get("cnpj", ""))[9:]}
          <ideVinculo>
            <cpfTrab>{cpf}</cpfTrab>
            <matriCad>{_c(funcionario.get("matricula", "001"))}</matriCad>
          </ideVinculo>
          <infoDeslig>
            <dtDeslig>{_d(termination_date)}</dtDeslig>
            <mtvDeslig>{motivo}</mtvDeslig>
            <dtProjFimAPI>{dt_proj}</dtProjFimAPI>
            <indPensAlim>N</indPensAlim>
            <pensAlim>0.00</pensAlim>
            <dtPagto>{_d(termination_date)}</dtPagto>
            <tpPagtoAPI>1</tpPagtoAPI>
            <perRef>{termination_date[:7]}</perRef>
            <infoMV></infoMV>
            <quarentena>0</quarentena>{verbas_resc}
          </infoDeslig>
        </evtDeslig>"""
    xml += _footer()
    return xml


# ── S-1000 — Informações do Empregador ──────────────────────────────────────
def gerar_s1000(company: dict) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    ini = today.strftime("%Y-%m")
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00001"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtInfoEmpregador/v02_05_00">
  <evtInfoEmpregador Id="{evt_id}">
    <ideEvento><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <infoEmpregador>
      <inclAlteracao>
        <idePeriodo><iniValid>{ini}</iniValid></idePeriodo>
        <infoCadastro>
          <nmRazao>{_c(company.get("razao_social",""))}</nmRazao>
          <classTrib>03</classTrib><indCoop>0</indCoop><indConstr>0</indConstr>
          <indDesFolha>0</indDesFolha><indOptReg>0</indOptReg>
          <indEntEd>N</indEntEd><indEtt>N</indEtt><nrRegEtt>0</nrRegEtt>
          <contato>
            <nmCtt>{_c(company.get("responsavel",""))}</nmCtt>
            <cpfCtt>{re.sub(r"\D","",_c(company.get("cpf_responsavel","")))}</cpfCtt>
            <email>{_c(company.get("email",""))}</email>
          </contato>
        </infoCadastro>
      </inclAlteracao>
    </infoEmpregador>
  </evtInfoEmpregador>
</eSocial>"""


# ── S-1005 — Tabela de Estabelecimentos ─────────────────────────────────────
def gerar_s1005(company: dict) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00002"
    ini = today.strftime("%Y-%m")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtTabEstab/v04_01_00">
  <evtTabEstab Id="{evt_id}">
    <ideEvento><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <infoEstab>
      <inclAlteracao>
        <ideEstab><tpInsc>1</tpInsc><nrInsc>{cnpj}</nrInsc></ideEstab>
        <dadosEstab>
          <cnaePrep>{re.sub(r"\D","",_c(company.get("cnae",""))) or "0000000"}</cnaePrep>
          <aliqGilrat><aliqRat>2.00</aliqRat><fap>1.0000</fap><aliqRatAjust>2.00</aliqRatAjust></aliqGilrat>
          <infoEFR><ideEFR>Sem EFR</ideEFR></infoEFR>
          <situacao><dtInicio>{_c(company.get("data_fundacao","")) or today.isoformat()}</dtInicio></situacao>
          <iniValid>{ini}</iniValid>
        </dadosEstab>
      </inclAlteracao>
    </infoEstab>
  </evtTabEstab>
</eSocial>"""


# ── S-1020 — Tabela de Lotações Tributárias ──────────────────────────────────
def gerar_s1020(company: dict, lotacao: dict) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00003"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtTabLotacao/v04_02_00">
  <evtTabLotacao Id="{evt_id}">
    <ideEvento><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <infoLotacao>
      <inclAlteracao>
        <ideLotacao><codLotacao>{_c(lotacao.get("cod_lotacao",""))}</codLotacao></ideLotacao>
        <dadosLotacao>
          <tpLotacao>{_c(lotacao.get("tp_lotacao","01"))}</tpLotacao>
          <fpasLotacao>
            <fpas>{_c(lotacao.get("fpas","515"))}</fpas>
            <codTerco>{_c(lotacao.get("cod_terco",""))}</codTerco>
          </fpasLotacao>
          <iniValid>{_c(lotacao.get("ini_valid",""))}</iniValid>
          {f'<fimValid>{_c(lotacao.get("fim_valid",""))}</fimValid>' if lotacao.get("fim_valid") else ""}
        </dadosLotacao>
      </inclAlteracao>
    </infoLotacao>
  </evtTabLotacao>
</eSocial>"""


# ── S-1050 — Tabela de Horários/Turnos ───────────────────────────────────────
def gerar_s1050(company: dict, horario: dict) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00004"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtTabHorTur/v04_02_00">
  <evtTabHorTur Id="{evt_id}">
    <ideEvento><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <infoHorContratual>
      <inclAlteracao>
        <ideHorContratual><codHorContratual>{str(horario.get("id","1")).zfill(4)}</codHorContratual></ideHorContratual>
        <dadosHorContratual>
          <dscHorContratual>{_c(horario.get("name",""))}</dscHorContratual>
          <tpJornada>1</tpJornada>
          <nrDiasJornada>5</nrDiasJornada>
          <horarioSemanal>
            <horSemana><dia>2</dia><horaIni>08:00</horaIni><horaFim>17:00</horaFim><horaIniInt>12:00</horaIniInt><horaFimInt>13:00</horaFimInt></horSemana>
          </horarioSemanal>
          <iniValid>{today.strftime("%Y-%m")}</iniValid>
        </dadosHorContratual>
      </inclAlteracao>
    </infoHorContratual>
  </evtTabHorTur>
</eSocial>"""


# ── S-1070 — Processos Administrativos/Judiciais ─────────────────────────────
def gerar_s1070(company: dict, processo: dict) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00005"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtTabProcesso/v04_02_00">
  <evtTabProcesso Id="{evt_id}">
    <ideEvento><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <infoProcesso>
      <inclAlteracao>
        <ideProcesso><nrProc>{_c(processo.get("nr_proc",""))}</nrProc></ideProcesso>
        <dadosProcesso>
          <indProc>{_c(processo.get("ind_proc","1"))}</indProc>
          <tpProc>{_c(processo.get("tp_proc","1"))}</tpProc>
          {f'<codSusp>{_c(processo.get("cod_susp",""))}</codSusp>' if processo.get("cod_susp") else ""}
          <iniValid>{_c(processo.get("ini_valid",""))}</iniValid>
          {f'<fimValid>{_c(processo.get("fim_valid",""))}</fimValid>' if processo.get("fim_valid") else ""}
        </dadosProcesso>
      </inclAlteracao>
    </infoProcesso>
  </evtTabProcesso>
</eSocial>"""


# ── S-3000 — Exclusão de Eventos ─────────────────────────────────────────────
def gerar_s3000(company: dict, evento_tipo: str, evento_id: str, motivo: str = "") -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00006"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtExclusao/v01_01_00">
  <evtExclusao Id="{evt_id}">
    <ideEvento><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <infoExclusao>
      <tpEvento>{_c(evento_tipo)}</tpEvento>
      <nrRec>{_c(evento_id)}</nrRec>
      {f'<motivo>{_c(motivo)}</motivo>' if motivo else ""}
    </infoExclusao>
  </evtExclusao>
</eSocial>"""


# ── S-5001 — Totalizadores de INSS ───────────────────────────────────────────
def gerar_s5001(company: dict, competencia: str, items: list) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00007"
    total_bruto = sum(float(i.get("gross_salary", 0)) for i in items)
    total_inss_emp = sum(float(i.get("inss", 0)) for i in items)
    n = len(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/retornoProcessamento/v1_3_0">
  <evtTotalContrib Id="{evt_id}">
    <ideEvento><indRetif>1</indRetif><nrRec>SIMULADO-{today.strftime('%Y%m%d')}</nrRec><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <idePeriodo><iniValid>{competencia}</iniValid><fimValid>{competencia}</fimValid></idePeriodo>
    <infoCS>
      <qtdTrabalhadores>{n}</qtdTrabalhadores>
      <baseCS><vrBcCp01>{_n(total_bruto)}</vrBcCp01><vrBcCpMen>{_n(total_bruto)}</vrBcCpMen></baseCS>
      <inss>
        <vrCpSeg>{_n(total_inss_emp)}</vrCpSeg>
        <vrCpPatr>{_n(total_bruto * 0.20)}</vrCpPatr>
        <vrCpTerceiros>{_n(total_bruto * 0.058)}</vrCpTerceiros>
        <vrRat>{_n(total_bruto * 0.01)}</vrRat>
        <vrTotal>{_n(total_inss_emp + total_bruto * 0.279)}</vrTotal>
      </inss>
    </infoCS>
  </evtTotalContrib>
</eSocial>"""


# ── S-5011 — Totalizadores de FGTS ───────────────────────────────────────────
def gerar_s5011(company: dict, competencia: str, items: list) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00008"
    total_fgts = sum(float(i.get("fgts", 0)) for i in items)
    total_bruto = sum(float(i.get("gross_salary", 0)) for i in items)
    n = len(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/retornoProcessamento/v1_3_0">
  <evtTotalFGTS Id="{evt_id}">
    <ideEvento><indRetif>1</indRetif><nrRec>SIMULADO-FGTS-{today.strftime('%Y%m%d')}</nrRec><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <idePeriodo><iniValid>{competencia}</iniValid><fimValid>{competencia}</fimValid></idePeriodo>
    <infoFGTS>
      <qtdTrabalhadores>{n}</qtdTrabalhadores>
      <vrBcFGTSTotal>{_n(total_bruto)}</vrBcFGTSTotal>
      <vrFGTSTotal>{_n(total_fgts)}</vrFGTSTotal>
    </infoFGTS>
  </evtTotalFGTS>
</eSocial>"""


# ── S-2298 — Reintegração ─────────────────────────────────────────────────────
def gerar_s2298(company: dict, employee: dict, reintegracao: dict) -> str:
    cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
    cpf = re.sub(r"\D", "", _c(employee.get("cpf", "")))
    today = _date.today()
    evt_id = f"ID1{cnpj[:8]}{today.strftime('%Y%m%d%H%M%S')}00009"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evtReintegr/v2_6_0">
  <evtReintegr Id="{evt_id}">
    <ideEvento><indRetif>1</indRetif><tpAmb>2</tpAmb><procEmi>1</procEmi><verProc>1.0</verProc></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{cnpj[:8]}</nrInsc></ideEmpregador>
    <ideVinculo>
      <cpfTrab>{cpf}</cpfTrab>
      <nisTrab>{_c(employee.get("pis_pasep",""))}</nisTrab>
      <codCateg>101</codCateg>
    </ideVinculo>
    <infoReintegr>
      <dtDeslig>{_d(reintegracao.get("data_demissao",""))}</dtDeslig>
      <dtReintegr>{_d(reintegracao.get("data_reintegracao",""))}</dtReintegr>
      <motReintegr>01</motReintegr>
      <nrProcJud>{_c(reintegracao.get("nr_processo",""))}</nrProcJud>
    </infoReintegr>
  </evtReintegr>
</eSocial>"""
