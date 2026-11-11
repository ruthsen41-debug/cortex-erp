"""
Gerador de XMLs do eSocial.
Eventos suportados:
  S-2200  Cadastramento Inicial / Admissão
  S-1200  Remuneração Mensal do Trabalhador
  S-2299  Desligamento
Versão do leiaute: S-1.3
"""
import re
import uuid
from datetime import date as _date
from typing import Any, Dict


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


# ─── S-1200 — Remuneração Mensal ────────────────────────────────────────────

def gerar_s1200(empresa: Dict, funcionario: Dict,
                competencia: str, payroll_item: Dict) -> str:
    """Gera o XML do evento S-1200 (Remuneração Mensal)."""
    ev_id = f"ID1{re.sub(r'\\D', '', _c(empresa.get('cnpj', '')))}{_date.today().strftime('%Y%m%d%H%M%S')}{'00002'}"
    cpf = re.sub(r"\D", "", _c(funcionario.get("cpf", "")))
    per_ref = competencia[:7].replace("-", "")  # YYYYMM

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
                <detVerbas>
                  <codRubr>VENC001</codRubr>
                  <ideTabRubr>{_c(empresa.get("id", "1"))}</ideTabRubr>
                  <qtd>1</qtd>
                  <fatorHr>0</fatorHr>
                  <vrUnit>{_n(payroll_item.get("gross_salary", 0))}</vrUnit>
                  <vrRubr>{_n(payroll_item.get("gross_salary", 0))}</vrRubr>
                </detVerbas>
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
                  <vrBcCP00>{_n(payroll_item.get("gross_salary", 0))}</vrBcCP00>
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


# ─── S-2299 — Desligamento ───────────────────────────────────────────────────

def gerar_s2299(empresa: Dict, funcionario: Dict,
                termination_date: str, motivo: str = "02") -> str:
    """
    Gera o XML do evento S-2299 (Desligamento).
    motivo: 01=aposentadoria, 02=pedido demissão, 03=dispensa s/jc, 04=dispensa c/jc
    """
    ev_id = f"ID1{re.sub(r'\\D', '', _c(empresa.get('cnpj', '')))}{_date.today().strftime('%Y%m%d%H%M%S')}{'00003'}"
    cpf = re.sub(r"\D", "", _c(funcionario.get("cpf", "")))

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
            <dtProjFimAPI></dtProjFimAPI>
            <indPensAlim>N</indPensAlim>
            <pensAlim>0.00</pensAlim>
            <dtPagto>{_d(termination_date)}</dtPagto>
            <tpPagtoAPI>1</tpPagtoAPI>
            <perRef>{termination_date[:7]}</perRef>
            <infoMV></infoMV>
            <quarentena>0</quarentena>
          </infoDeslig>
        </evtDeslig>"""
    xml += _footer()
    return xml
