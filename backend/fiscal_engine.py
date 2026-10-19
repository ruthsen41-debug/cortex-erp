import re
import random
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta


def _only_digits(val: str) -> str:
    return re.sub(r"\D", "", str(val or ""))


def calcular_dv_modulo11(chave_43: str) -> str:
    """Calcula o dígito verificador oficial da SEFAZ (Módulo 11, pesos 2 a 9 da direita para a esquerda)."""
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for idx, digito in enumerate(reversed(chave_43)):
        peso = pesos[idx % 8]
        soma += int(digito) * peso
    resto = soma % 11
    dv = 11 - resto
    if dv >= 10:
        dv = 0
    return str(dv)


def gerar_chave_acesso_sefaz(
    cuf: str,
    dt_emissao: datetime,
    cnpj_emitente: str,
    modelo: str,
    serie: int,
    numero_nf: int,
    tp_emis: str = "1",
) -> str:
    """
    Gera a chave de acesso oficial de 44 dígitos da NF-e / NFC-e:
    cUF(2) + AAMM(4) + CNPJ(14) + mod(2) + serie(3) + nNF(9) + tpEmis(1) + cNF(8) + cDV(1)
    """
    cuf_clean = _only_digits(cuf).zfill(2)[:2] or "51"
    aamm = dt_emissao.strftime("%y%m")
    cnpj_clean = _only_digits(cnpj_emitente).zfill(14)[:14]
    mod_clean = "65" if "65" in str(modelo) else "55"
    serie_clean = str(int(serie)).zfill(3)[:3]
    nnf_clean = str(int(numero_nf)).zfill(9)[:9]
    cnf = str(random.randint(10000000, 99999999))
    chave_43 = f"{cuf_clean}{aamm}{cnpj_clean}{mod_clean}{serie_clean}{nnf_clean}{tp_emis}{cnf}"
    dv = calcular_dv_modulo11(chave_43)
    return f"{chave_43}{dv}"


def validar_dados_fiscais(company: dict, contact: dict, items: list[dict], model: str = "NFe-55") -> list[str]:
    """Valida todos os requisitos fiscais antes de autorizar a NF-e/NFC-e/NFS-e."""
    erros = []
    cnpj_emit = _only_digits(company.get("cnpj", ""))
    if len(cnpj_emit) != 14:
        erros.append("CNPJ da empresa emitente deve conter 14 dígitos.")

    if model in ("NFe-55", "NFSe"):
        doc_dest = _only_digits(contact.get("document", ""))
        if len(doc_dest) not in (11, 14):
            erros.append("O cliente destinatário precisa ter um CPF (11 dígitos) ou CNPJ (14 dígitos) válido para emissão de Nota Fiscal.")
        if not contact.get("street") or not contact.get("city") or not contact.get("state"):
            erros.append("O endereço completo do cliente (Logradouro, Cidade e UF) é obrigatório para NF-e / NFS-e.")

    if not items:
        erros.append("A nota fiscal deve conter pelo menos 1 item/serviço.")

    for idx, it in enumerate(items, start=1):
        nome = it.get("name") or it.get("product_name") or f"Item #{idx}"
        if model in ("NFe-55", "NFCe-65"):
            ncm = _only_digits(it.get("ncm", "84713012"))
            if len(ncm) != 8:
                erros.append(f"O item '{nome}' possui NCM inválido ('{ncm}'). O NCM deve ter exatamente 8 dígitos.")
            cfop = _only_digits(it.get("cfop", "5102"))
            if len(cfop) != 4:
                erros.append(f"O item '{nome}' possui CFOP inválido ('{cfop}'). O CFOP deve ter 4 dígitos.")
    return erros


def gerar_xml_nfe_400(
    company: dict,
    contact: dict,
    items: list[dict],
    invoice_data: dict,
) -> str:
    """Gera o XML completo no Layout 4.00 da SEFAZ (<nfeProc versao="4.00">)."""
    chave = invoice_data["access_key"]
    protocolo = invoice_data["protocol"]
    numero = invoice_data["number"]
    serie = invoice_data["series"]
    mod_code = "65" if "65" in invoice_data["model"] else "55"
    tp_amb = "1" if company.get("ambiente_fiscal") == "producao" else "2"
    dh_emi = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-04:00")
    cnpj_emit = _only_digits(company.get("cnpj", "45123789000190")).zfill(14)
    doc_dest = _only_digits(contact.get("document", "12456789000110"))
    tag_doc_dest = "CNPJ" if len(doc_dest) == 14 else "CPF"
    crt = "1" if company.get("regime_tributario", "simples_nacional") in ("simples_nacional", "mei") else "3"

    det_xml_list = []
    for idx, it in enumerate(items, start=1):
        ncm = _only_digits(it.get("ncm", "84713012")).zfill(8)
        cfop = _only_digits(it.get("cfop", "5102")).zfill(4)
        csosn = it.get("csosn_cst", "102")
        qty = float(it.get("quantity", 1))
        v_un = float(it.get("unit_price", 0))
        v_prod = round(qty * v_un, 2)
        det_xml_list.append(f"""
        <det nItem="{idx}">
          <prod>
            <cProd>{it.get("sku") or f"PRD-{idx:03d}"}</cProd>
            <cEAN>SEM GTIN</cEAN>
            <xProd>{it.get("product_name") or it.get("name")}</xProd>
            <NCM>{ncm}</NCM>
            <CFOP>{cfop}</CFOP>
            <uCom>{it.get("unit") or "UN"}</uCom>
            <qCom>{qty:.4f}</qCom>
            <vUnCom>{v_un:.4f}</vUnCom>
            <vProd>{v_prod:.2f}</vProd>
            <cEANTrib>SEM GTIN</cEANTrib>
            <uTrib>{it.get("unit") or "UN"}</uTrib>
            <qTrib>{qty:.4f}</qTrib>
            <vUnTrib>{v_un:.4f}</vUnTrib>
            <indTot>1</indTot>
          </prod>
          <imposto>
            <ICMS>
              <ICMSSN102>
                <orig>{it.get("origin", "0")}</orig>
                <CSOSN>{csosn}</CSOSN>
              </ICMSSN102>
            </ICMS>
            <PIS>
              <PISOutr>
                <CST>{it.get("pis_cst", "07")}</CST>
                <vBC>{v_prod:.2f}</vBC>
                <pPIS>{float(it.get("pis_rate", 0.65)):.2f}</pPIS>
                <vPIS>{round(v_prod * float(it.get("pis_rate", 0.65)) / 100.0, 2):.2f}</vPIS>
              </PISOutr>
            </PIS>
            <COFINS>
              <COFINSOutr>
                <CST>{it.get("cofins_cst", "07")}</CST>
                <vBC>{v_prod:.2f}</vBC>
                <pCOFINS>{float(it.get("cofins_rate", 3.0)):.2f}</pCOFINS>
                <vCOFINS>{round(v_prod * float(it.get("cofins_rate", 3.0)) / 100.0, 2):.2f}</vCOFINS>
              </COFINSOutr>
            </COFINS>
          </imposto>
        </det>""")

    dets_joined = "\n".join(det_xml_list)
    v_prod_total = float(invoice_data.get("total_products", 0))
    v_desc = float(invoice_data.get("total_discounts", 0))
    v_frete = float(invoice_data.get("total_shipping", 0))
    v_nf = float(invoice_data.get("total_invoice", 0))
    v_pis = float(invoice_data.get("total_pis", 0))
    v_cofins = float(invoice_data.get("total_cofins", 0))

    xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
    <infNFe Id="NFe{chave}" versao="4.00">
      <ide>
        <cUF>{company.get("codigo_ibge_uf", "51")}</cUF>
        <cNF>{chave[35:43]}</cNF>
        <natOp>{invoice_data.get("nature_operation", "VENDA DE MERCADORIA")}</natOp>
        <mod>{mod_code}</mod>
        <serie>{serie}</serie>
        <nNF>{numero}</nNF>
        <dhEmi>{dh_emi}</dhEmi>
        <tpNF>1</tpNF>
        <idDest>1</idDest>
        <cMunFG>{company.get("codigo_ibge_municipio", "5102504")}</cMunFG>
        <tpImp>1</tpImp>
        <tpEmis>1</tpEmis>
        <cDV>{chave[-1]}</cDV>
        <tpAmb>{tp_amb}</tpAmb>
        <finNFe>1</finNFe>
        <indFinal>1</indFinal>
        <indPres>1</indPres>
        <procEmi>0</procEmi>
        <verProc>CortexERP-Pro-4.0</verProc>
      </ide>
      <emit>
        <CNPJ>{cnpj_emit}</CNPJ>
        <xNome>{company.get("razao_social")}</xNome>
        <xFant>{company.get("nome_fantasia")}</xFant>
        <enderEmit>
          <xLgr>{company.get("logradouro", "Av. Principal")}</xLgr>
          <nro>{company.get("numero", "S/N")}</nro>
          <xBairro>{company.get("bairro", "Centro")}</xBairro>
          <cMun>{company.get("codigo_ibge_municipio", "5102504")}</cMun>
          <xMun>{company.get("cidade", "Caceres")}</xMun>
          <UF>{company.get("uf", "MT")}</UF>
          <CEP>{_only_digits(company.get("cep", "78200000"))}</CEP>
          <cPais>1058</cPais>
          <xPais>BRASIL</xPais>
        </enderEmit>
        <IE>{_only_digits(company.get("inscricao_estadual", "ISENTO")) or "ISENTO"}</IE>
        <CRT>{crt}</CRT>
      </emit>
      <dest>
        <{tag_doc_dest}>{doc_dest}</{tag_doc_dest}>
        <xNome>{contact.get("name", "CONSUMIDOR FINAL")}</xNome>
        <enderDest>
          <xLgr>{contact.get("street", "Rua Principal")}</xLgr>
          <nro>{contact.get("number", "S/N")}</nro>
          <xBairro>{contact.get("neighborhood", "Centro")}</xBairro>
          <cMun>{contact.get("ibge_code", "5102504")}</cMun>
          <xMun>{contact.get("city", "Caceres")}</xMun>
          <UF>{contact.get("state", "MT")}</UF>
          <CEP>{_only_digits(contact.get("cep", "78200000"))}</CEP>
          <cPais>1058</cPais>
          <xPais>BRASIL</xPais>
        </enderDest>
        <indIEDest>{contact.get("ie_indicator", "9")}</indIEDest>
      </dest>{dets_joined}
      <total>
        <ICMSTot>
          <vBC>0.00</vBC>
          <vICMS>0.00</vICMS>
          <vICMSDeson>0.00</vICMSDeson>
          <vFCP>0.00</vFCP>
          <vBCST>0.00</vBCST>
          <vST>0.00</vST>
          <vFCPST>0.00</vFCPST>
          <vFCPSTRet>0.00</vFCPSTRet>
          <vProd>{v_prod_total:.2f}</vProd>
          <vFrete>{v_frete:.2f}</vFrete>
          <vSeg>0.00</vSeg>
          <vDesc>{v_desc:.2f}</vDesc>
          <vII>0.00</vII>
          <vIPI>0.00</vIPI>
          <vIPIDevol>0.00</vIPIDevol>
          <vPIS>{v_pis:.2f}</vPIS>
          <vCOFINS>{v_cofins:.2f}</vCOFINS>
          <vOutro>0.00</vOutro>
          <vNF>{v_nf:.2f}</vNF>
        </ICMSTot>
      </total>
      <transp>
        <modFrete>9</modFrete>
      </transp>
      <infAdic>
        <infCpl>Documento emitido por ME ou EPP optante pelo Simples Nacional. Nao gera direito a credito fiscal de IPI. Emitido via Cortex ERP Pro+.</infCpl>
      </infAdic>
    </infNFe>
  </NFe>
  <protNFe versao="4.00">
    <infProt>
      <tpAmb>{tp_amb}</tpAmb>
      <verAplic>SVRS202610</verAplic>
      <chNFe>{chave}</chNFe>
      <dhRecbto>{dh_emi}</dhRecbto>
      <nProt>{protocolo}</nProt>
      <digVal>c2VmYXotY29ydGV4LWVycC1hc3NpbmF0dXJhLWRpZ2l0YWw=</digVal>
      <cStat>100</cStat>
      <xMotivo>Autorizado o uso da NF-e</xMotivo>
    </infProt>
  </protNFe>
</nfeProc>"""
    return xml_str


def gerar_html_danfe(company: dict, contact: dict, invoice: dict, items: list[dict]) -> str:
    """Gera o DANFE / DANFSE completo pronto para impressão/PDF em padrão SEFAZ."""
    chave = invoice["access_key"]
    chave_formatada = " ".join([chave[i:i+4] for i in range(0, len(chave), 4)])
    linhas_itens = ""
    for idx, it in enumerate(items, start=1):
        linhas_itens += f"""
        <tr>
            <td>{it.get("sku") or f"PRD-{idx:03d}"}</td>
            <td>{it.get("product_name") or it.get("name")}</td>
            <td style="text-align:center">{it.get("ncm", "84713012")}</td>
            <td style="text-align:center">{it.get("csosn_cst", "102")}</td>
            <td style="text-align:center">{it.get("cfop", "5102")}</td>
            <td style="text-align:center">{it.get("unit", "UN")}</td>
            <td style="text-align:right">{float(it.get("quantity", 1)):.2f}</td>
            <td style="text-align:right">R$ {float(it.get("unit_price", 0)):,.2f}</td>
            <td style="text-align:right"><b>R$ {float(it.get("total_price", 0)):,.2f}</b></td>
        </tr>
        """

    tarja_cancelada = ""
    if invoice.get("status") == "cancelada":
        tarja_cancelada = '<div style="background:#dc2626;color:#fff;padding:10px;text-align:center;font-weight:bold;font-size:18px;margin-bottom:10px;">NOTA FISCAL CANCELADA — SEM VALOR FISCAL</div>'
    elif invoice.get("environment") == "homologacao":
        tarja_cancelada = '<div style="background:#f59e0b;color:#111;padding:6px;text-align:center;font-weight:bold;font-size:13px;margin-bottom:10px;">AMBIENTE DE HOMOLOGAÇÃO SEFAZ — EMITIDA PARA FINS DE TESTE</div>'

    cce_block = ""
    if invoice.get("correction_letter"):
        cce_block = f'<div style="border:1px solid #1d4ed8;background:#eff6ff;padding:8px;margin-top:8px;font-size:11px;"><b>CARTA DE CORREÇÃO ELETRÔNICA (CC-e AVERBADA):</b> {invoice["correction_letter"]}</div>'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>DANFE - NF {invoice["number"]} - {company["nome_fantasia"]}</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #111; margin: 16px; }}
  .box {{ border: 1px solid #222; padding: 6px; margin-bottom: 6px; }}
  .grid {{ display: flex; gap: 6px; }}
  .col {{ flex: 1; border: 1px solid #222; padding: 5px; }}
  .lbl {{ font-size: 8px; text-transform: uppercase; color: #444; display: block; margin-bottom: 2px; }}
  .val {{ font-size: 11px; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  th, td {{ border: 1px solid #222; padding: 5px; font-size: 10px; }}
  th {{ background: #f3f4f6; text-transform: uppercase; font-size: 9px; }}
  .barcode {{ font-family: "Courier New", monospace; letter-spacing: 2px; font-size: 13px; font-weight: bold; background: repeating-linear-gradient(90deg,#000,#000 2px,#fff 2px,#fff 5px); height: 34px; margin: 4px 0; }}
  @media print {{ .no-print {{ display: none; }} }}
</style>
</head>
<body>
  <div class="no-print" style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;background:#1e293b;color:#fff;padding:10px 14px;border-radius:8px;">
    <span><b>Visualização Oficial do DANFE / Nota Fiscal #{invoice["number"]}</b> ({invoice["model"]})</span>
    <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold;">Imprimir / Salvar em PDF</button>
  </div>
  {tarja_cancelada}
  <div class="box" style="border-style:dashed;margin-bottom:10px;">
    <div style="font-size:9px;margin-bottom:8px;">RECEBEMOS DE <b>{company["razao_social"]}</b> OS PRODUTOS E/OU SERVIÇOS CONSTANTES DA NOTA FISCAL INDICADA AO LADO.</div>
    <div class="grid">
      <div class="col" style="max-width:180px;"><span class="lbl">DATA DE RECEBIMENTO</span><br>____/____/________</div>
      <div class="col"><span class="lbl">IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR</span><br>&nbsp;</div>
      <div class="col" style="max-width:160px;text-align:center;"><span class="lbl">{invoice["model"]}</span><span class="val" style="font-size:14px;">Nº {invoice["number"]:06d}</span><br>Série {invoice["series"]}</div>
    </div>
  </div>

  <div class="grid">
    <div class="col" style="flex:1.4">
      <div style="font-size:14px;font-weight:bold;">{company["razao_social"]}</div>
      <div style="font-size:11px;margin-top:3px;"><b>{company["nome_fantasia"]}</b></div>
      <div style="margin-top:4px;font-size:10px;">
        {company.get("logradouro", "")}, {company.get("numero", "")} - {company.get("bairro", "")}<br>
        {company.get("cidade", "")}/{company.get("uf", "")} - CEP: {company.get("cep", "")}<br>
        Tel: {company.get("telefone", "")} | Email: {company.get("email", "")}
      </div>
    </div>
    <div class="col" style="flex:0.7;text-align:center;">
      <div style="font-size:16px;font-weight:bold;">DANFE</div>
      <div style="font-size:9px;">Documento Auxiliar da Nota Fiscal Eletrônica</div>
      <div style="margin:6px 0;font-weight:bold;">1 - SAÍDA</div>
      <div style="font-size:14px;font-weight:bold;">Nº {invoice["number"]:06d}</div>
      <div>SÉRIE: {invoice["series"]}</div>
    </div>
    <div class="col" style="flex:1.6;">
      <span class="lbl">CONTROLE DO FISCO / CÓDIGO DE BARRAS</span>
      <div class="barcode"></div>
      <span class="lbl">CHAVE DE ACESSO SEFAZ (44 DÍGITOS)</span>
      <div class="val" style="font-family:monospace;font-size:11px;letter-spacing:0.5px;">{chave_formatada}</div>
      <div style="margin-top:4px;font-size:9px;">Consulta de autenticidade no portal nacional da NF-e: www.nfe.fazenda.gov.br/portal</div>
    </div>
  </div>

  <div class="grid" style="margin-top:6px;">
    <div class="col" style="flex:2"><span class="lbl">NATUREZA DA OPERAÇÃO</span><span class="val">{invoice.get("nature_operation")}</span></div>
    <div class="col" style="flex:1.5"><span class="lbl">PROTOCOLO DE AUTORIZAÇÃO DE USO SEFAZ</span><span class="val">{invoice.get("protocol")} - {invoice.get("issued_at", "")[:19]}</span></div>
  </div>

  <div class="grid" style="margin-top:6px;">
    <div class="col"><span class="lbl">INSCRIÇÃO ESTADUAL</span><span class="val">{company.get("inscricao_estadual") or "ISENTO"}</span></div>
    <div class="col"><span class="lbl">INSCRIÇÃO MUNICIPAL</span><span class="val">{company.get("inscricao_municipal") or "-"}</span></div>
    <div class="col"><span class="lbl">CNPJ EMITENTE</span><span class="val">{company.get("cnpj")}</span></div>
    <div class="col"><span class="lbl">REGIME TRIBUTÁRIO</span><span class="val">{company.get("regime_tributario", "").upper().replace("_", " ")}</span></div>
  </div>

  <div style="font-weight:bold;margin-top:10px;font-size:10px;">DESTINATÁRIO / REMETENTE</div>
  <div class="grid">
    <div class="col" style="flex:2"><span class="lbl">NOME / RAZÃO SOCIAL</span><span class="val">{contact.get("name") or invoice.get("recipient_name")}</span></div>
    <div class="col"><span class="lbl">CNPJ / CPF</span><span class="val">{contact.get("document") or invoice.get("recipient_doc")}</span></div>
    <div class="col"><span class="lbl">DATA DE EMISSÃO</span><span class="val">{invoice.get("issued_at", "")[:10]}</span></div>
  </div>
  <div class="grid" style="margin-top:4px;">
    <div class="col" style="flex:2"><span class="lbl">ENDEREÇO</span><span class="val">{contact.get("street", "")}, {contact.get("number", "")} - {contact.get("neighborhood", "")}</span></div>
    <div class="col"><span class="lbl">MUNICÍPIO / UF</span><span class="val">{contact.get("city", "Cáceres")} / {contact.get("state") or invoice.get("recipient_uf", "MT")}</span></div>
    <div class="col"><span class="lbl">INSCRIÇÃO ESTADUAL</span><span class="val">{contact.get("state_registration") or "ISENTO"}</span></div>
  </div>

  <div style="font-weight:bold;margin-top:10px;font-size:10px;">CÁLCULO DO IMPOSTO</div>
  <div class="grid">
    <div class="col"><span class="lbl">VALOR DOS PRODUTOS/SERVIÇOS</span><span class="val">R$ {float(invoice.get("total_products", 0)):,.2f}</span></div>
    <div class="col"><span class="lbl">VALOR DO FRETE</span><span class="val">R$ {float(invoice.get("total_shipping", 0)):,.2f}</span></div>
    <div class="col"><span class="lbl">DESCONTO</span><span class="val">R$ {float(invoice.get("total_discounts", 0)):,.2f}</span></div>
    <div class="col"><span class="lbl">PIS / COFINS / ISS</span><span class="val">R$ {(float(invoice.get("total_pis", 0)) + float(invoice.get("total_cofins", 0)) + float(invoice.get("total_iss", 0))):,.2f}</span></div>
    <div class="col" style="background:#f8fafc"><span class="lbl">VALOR TOTAL DA NOTA</span><span class="val" style="font-size:13px;color:#1d4ed8;">R$ {float(invoice.get("total_invoice", 0)):,.2f}</span></div>
  </div>

  <div style="font-weight:bold;margin-top:10px;font-size:10px;">DADOS DOS PRODUTOS / SERVIÇOS</div>
  <table>
    <thead>
      <tr>
        <th>CÓDIGO</th>
        <th>DESCRIÇÃO DO PRODUTO / SERVIÇO</th>
        <th>NCM/SH</th>
        <th>CSOSN</th>
        <th>CFOP</th>
        <th>UN</th>
        <th>QTD</th>
        <th>VLR. UNIT.</th>
        <th>VLR. TOTAL</th>
      </tr>
    </thead>
    <tbody>
      {linhas_itens}
    </tbody>
  </table>

  <div class="box" style="margin-top:10px;">
    <span class="lbl">DADOS ADICIONAIS / INFORMAÇÕES COMPLEMENTARES</span>
    <div>Documento emitido por ME ou EPP optante pelo Simples Nacional. Não gera direito a crédito fiscal de IPI. Chave Pix para pagamento: <b>{company.get("chave_pix")}</b>.</div>
    {cce_block}
  </div>
</body>
</html>"""


def gerar_xml_compra_exemplo() -> str:
    """Gera um XML de NF-e de Fornecedor realista para demonstrar a Entrada Automática de Compras por XML."""
    hoje = date.today().isoformat()
    venc1 = (date.today() + timedelta(days=15)).isoformat()
    venc2 = (date.today() + timedelta(days=30)).isoformat()
    chave = f"35{date.today().strftime('%y%m')}08777123000188550010000884121{random.randint(10000000,99999999)}5"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe{chave}" versao="4.00">
      <ide>
        <nNF>{random.randint(80000, 99999)}</nNF>
        <dhEmi>{hoje}T10:30:00-03:00</dhEmi>
      </ide>
      <emit>
        <CNPJ>08777123000188</CNPJ>
        <xNome>DISTRIBUIDORA NACIONAL DE HARDWARE E TI S.A.</xNome>
        <xFant>Nacional Tech Distribuidora</xFant>
        <IE>110445998112</IE>
        <enderEmit>
          <xLgr>Av. Paulista</xLgr>
          <nro>1578</nro>
          <xBairro>Bela Vista</xBairro>
          <xMun>Sao Paulo</xMun>
          <UF>SP</UF>
          <CEP>01310100</CEP>
        </enderEmit>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>PRD-001</cProd>
          <cEAN>7891234560012</cEAN>
          <xProd>Notebook Corporativo Intel Core i7 16GB SSD 512GB</xProd>
          <NCM>84713012</NCM>
          <CFOP>6102</CFOP>
          <uCom>UN</uCom>
          <qCom>3.0000</qCom>
          <vUnCom>2980.0000</vUnCom>
          <vProd>8940.00</vProd>
        </prod>
      </det>
      <det nItem="2">
        <prod>
          <cProd>PRD-006</cProd>
          <cEAN>7891234560099</cEAN>
          <xProd>Roteador Wi-Fi 6 Empresarial Mesh Dual-WAN</xProd>
          <NCM>85176241</NCM>
          <CFOP>6102</CFOP>
          <uCom>UN</uCom>
          <qCom>5.0000</qCom>
          <vUnCom>410.0000</vUnCom>
          <vProd>2050.00</vProd>
        </prod>
      </det>
      <total>
        <ICMSTot>
          <vNF>10990.00</vNF>
        </ICMSTot>
      </total>
      <cobr>
        <dup>
          <nDup>001</nDup>
          <dVenc>{venc1}</dVenc>
          <vDup>5495.00</vDup>
        </dup>
        <dup>
          <nDup>002</nDup>
          <dVenc>{venc2}</dVenc>
          <vDup>5495.00</vDup>
        </dup>
      </cobr>
    </infNFe>
  </NFe>
</nfeProc>"""


def parse_nfe_compra_xml(xml_text: str) -> dict:
    """Extrai dados do fornecedor, produtos e duplicatas (boletos) de um XML de NF-e de compra."""
    clean_xml = re.sub(r'\sxmlns="[^"]+"', "", xml_text)
    root = ET.fromstring(clean_xml)

    inf_nfe = root.find(".//infNFe")
    chave = inf_nfe.attrib.get("Id", "").replace("NFe", "") if inf_nfe is not None else f"352610{random.randint(10**37, 10**38-1)}"

    n_nf = root.findtext(".//ide/nNF", default="0001")
    dh_emi = root.findtext(".//ide/dhEmi", default=date.today().isoformat())[:10]

    # Emitente (Fornecedor)
    emit_cnpj = root.findtext(".//emit/CNPJ", default="")
    emit_nome = root.findtext(".//emit/xNome", default="Fornecedor XML")
    emit_fant = root.findtext(".//emit/xFant", default=emit_nome)
    emit_ie = root.findtext(".//emit/IE", default="")
    emit_lgr = root.findtext(".//emit/enderEmit/xLgr", default="")
    emit_nro = root.findtext(".//emit/enderEmit/nro", default="")
    emit_bairro = root.findtext(".//emit/enderEmit/xBairro", default="")
    emit_mun = root.findtext(".//emit/enderEmit/xMun", default="")
    emit_uf = root.findtext(".//emit/enderEmit/UF", default="SP")
    emit_cep = root.findtext(".//emit/enderEmit/CEP", default="")

    # Produtos (<det>)
    items = []
    for det in root.findall(".//det"):
        c_prod = det.findtext("prod/cProd", default="PRD-XML")
        c_ean = det.findtext("prod/cEAN", default="")
        if c_ean == "SEM GTIN":
            c_ean = ""
        x_prod = det.findtext("prod/xProd", default="Produto Importado XML")
        ncm = det.findtext("prod/NCM", default="84713012")
        u_com = det.findtext("prod/uCom", default="UN")
        q_com = float(det.findtext("prod/qCom", default="1") or 1)
        v_un = float(det.findtext("prod/vUnCom", default="0") or 0)
        v_prod = float(det.findtext("prod/vProd", default="0") or (q_com * v_un))
        items.append({
            "sku": c_prod,
            "barcode": c_ean,
            "name": x_prod,
            "ncm": ncm,
            "unit": u_com,
            "quantity": q_com,
            "unit_cost": v_un,
            "total_cost": v_prod,
        })

    v_nf = float(root.findtext(".//total/ICMSTot/vNF", default="0") or sum(i["total_cost"] for i in items))

    # Duplicatas (<cobr><dup>)
    duplicatas = []
    for dup in root.findall(".//cobr/dup"):
        n_dup = dup.findtext("nDup", default="001")
        d_venc = dup.findtext("dVenc", default=date.today().isoformat())
        v_dup = float(dup.findtext("vDup", default="0") or 0)
        duplicatas.append({"number": n_dup, "due_date": d_venc, "amount": v_dup})

    if not duplicatas and v_nf > 0:
        duplicatas.append({"number": "001", "due_date": (date.today() + timedelta(days=15)).isoformat(), "amount": v_nf})

    return {
        "access_key": chave,
        "invoice_number": n_nf,
        "issue_date": dh_emi,
        "total_amount": v_nf,
        "supplier": {
            "cnpj": emit_cnpj,
            "name": emit_nome,
            "trade_name": emit_fant,
            "ie": emit_ie,
            "street": emit_lgr,
            "number": emit_nro,
            "neighborhood": emit_bairro,
            "city": emit_mun,
            "state": emit_uf,
            "cep": emit_cep,
        },
        "items": items,
        "installments": duplicatas,
    }


def gerar_ofx_exemplo() -> str:
    """Gera um extrato bancário OFX realista para teste imediato da Conciliação Bancária Inteligente."""
    d0 = date.today().strftime("%Y%m%d")
    d1 = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    d2 = (date.today() - timedelta(days=2)).strftime("%Y%m%d")
    return f"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE
<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>{d0}100000
            <TRNAMT>-645.90
            <FITID>OFX-{d0}-001
            <MEMO>PAGTO BOLETO ENERGISA MATO GROSSO ENERGIA ELETRICA
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>{d1}142000
            <TRNAMT>2450.00
            <FITID>OFX-{d1}-002
            <MEMO>PIX RECEBIDO - VENDA BALCAO E CONSULTORIA TI
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>{d1}161500
            <TRNAMT>-285.00
            <FITID>OFX-{d1}-003
            <MEMO>COMPRA CARTAO POSTO PANTANAL COMBUSTIVEL DIESEL
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>{d2}090000
            <TRNAMT>-49.90
            <FITID>OFX-{d2}-004
            <MEMO>TARIFA BANCARIA PACOTE EMPRESARIAL PIX/TED
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>"""


def parse_ofx_content(ofx_text: str) -> list[dict]:
    """Faz o parse de arquivos .OFX bancários (SGML ou XML) extraindo cada transação <STMTTRN>."""
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", ofx_text, flags=re.DOTALL | re.IGNORECASE)
    results = []
    for idx, blk in enumerate(blocks, start=1):
        amt_match = re.search(r"<TRNAMT>\s*([-+]?\d+(?:[.,]\d+)?)", blk, re.IGNORECASE)
        dt_match = re.search(r"<DTPOSTED>\s*(\d{8})", blk, re.IGNORECASE)
        fit_match = re.search(r"<FITID>\s*([^\r\n<]+)", blk, re.IGNORECASE)
        memo_match = re.search(r"<(?:MEMO|NAME)>\s*([^\r\n<]+)", blk, re.IGNORECASE)

        amount = float(amt_match.group(1).replace(",", ".")) if amt_match else 0.0
        if dt_match:
            raw_d = dt_match.group(1)
            posted_date = f"{raw_d[0:4]}-{raw_d[4:6]}-{raw_d[6:8]}"
        else:
            posted_date = date.today().isoformat()

        fitid = fit_match.group(1).strip() if fit_match else f"OFX-{date.today().isoformat()}-{idx}"
        memo = memo_match.group(1).strip() if memo_match else "Transação OFX"
        results.append({
            "fitid": fitid,
            "posted_date": posted_date,
            "amount": amount,
            "memo": memo,
        })
    return results
