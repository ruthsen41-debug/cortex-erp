from datetime import date
from typing import List, Dict, Any
import re


def _clean(val: Any) -> str:
    return str(val or "").strip().replace("|", "")


def _fmt_date(dt_str: str) -> str:
    if not dt_str:
        return ""
    clean = re.sub(r"\D", "", dt_str[:10])
    if len(clean) == 8:
        # AAAA-MM-DD -> DDMMAAAA
        return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
    return clean


def _fmt_num(val: Any, decimals: int = 2) -> str:
    try:
        n = float(val or 0.0)
        return f"{n:.{decimals}f}".replace(".", ",")
    except Exception:
        return "0,00"


class SpedFiscalGenerator:
    """
    Gerador do SPED Fiscal (EFD ICMS/IPI) em conformidade com o Guia Prático da RFB / SEFAZ.
    Blocos: 0 (Identificação), C (Documentos Fiscais), E (Apuração do ICMS), 9 (Encerramento).
    """

    @staticmethod
    def generate(
        company: Dict[str, Any],
        invoices: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> str:
        lines: List[str] = []
        reg_counts: Dict[str, int] = {}

        def add_line(reg: str, fields: List[str]):
            line = f"|{reg}|{'|'.join(fields)}|"
            lines.append(line)
            reg_counts[reg] = reg_counts.get(reg, 0) + 1

        # ==========================================
        # BLOCO 0: ABERTURA E IDENTIFICAÇÃO
        # ==========================================
        add_line("0000", [
            "018",  # Versão do layout EFD
            "0",    # Finalidade do arquivo: 0 - Remessa original
            _fmt_date(start_date),
            _fmt_date(end_date),
            _clean(company.get("razao_social", "CORTEX ERP SOLUTIONS")),
            re.sub(r"\D", "", str(company.get("cnpj", ""))),
            "",     # CPF
            _clean(company.get("uf", "MT")),
            _clean(company.get("inscricao_estadual", "ISENTO")),
            re.sub(r"\D", "", str(company.get("codigo_ibge_municipio", "5103403"))),
            _clean(company.get("inscricao_municipal", "")),
            "",     # Suframa
            "A",    # Perfil de apresentação
            "0",    # Tipo de atividade: 0 - Industrial ou equiparado a industrial
        ])

        add_line("0001", ["0"])  # Abertura do Bloco 0 (com dados)

        # 0005: Dados Complementares
        add_line("0005", [
            _clean(company.get("nome_fantasia", company.get("razao_social", ""))),
            re.sub(r"\D", "", str(company.get("cep", "78000000"))),
            _clean(company.get("logradouro", "AVENIDA PRINCIPAL")),
            _clean(company.get("numero", "100")),
            _clean(company.get("complemento", "SALA 1")),
            _clean(company.get("bairro", "CENTRO")),
            re.sub(r"\D", "", str(company.get("telefone", "6530000000"))),
            "",  # Fax
            _clean(company.get("email", "fiscal@cortex.com.br")),
        ])

        # 0100: Dados do Contabilista
        add_line("0100", [
            "CONTABILIDADE AUDITORA PARCEIRA LTDA",
            "12345678909",
            "CRC-MT 012345/O",
            re.sub(r"\D", "", str(company.get("cnpj", ""))),
            "78000000",
            "RUA DOS CONTADORES",
            "50",
            "",
            "CENTRO",
            "6533334444",
            "",
            "contador@cortex.com.br",
            "5103403",
        ])

        # 0990: Encerramento Bloco 0
        reg_counts["0990"] = 1
        bloco_0_total = sum(v for k, v in reg_counts.items() if k.startswith("0"))
        lines.append(f"|0990|{bloco_0_total}|")

        # ==========================================
        # BLOCO C: DOCUMENTOS FISCAIS (NOTAS FISCAIS)
        # ==========================================
        add_line("C001", ["0"])  # Abertura do Bloco C

        for inv in invoices:
            mod = "55" if "55" in str(inv.get("model", "")) else "65"
            dt_emi = _fmt_date(inv.get("issued_at", start_date))
            tot_inv = _fmt_num(inv.get("total_invoice", 0.0))
            tot_desc = _fmt_num(inv.get("total_discounts", 0.0))
            tot_prod = _fmt_num(inv.get("total_products", 0.0))
            tot_icms = _fmt_num(inv.get("total_icms", 0.0))
            tot_pis = _fmt_num(inv.get("total_pis", 0.0))
            tot_cofins = _fmt_num(inv.get("total_cofins", 0.0))

            # C100: Nota Fiscal
            add_line("C100", [
                "0",  # 0 - Emissão própria
                "0",  # 0 - Operação de Saída
                str(inv.get("contact_id") or "1"),
                mod,
                "00", # Situação do documento: 00 - Documento regular
                str(inv.get("series", 1)),
                str(inv.get("number", 1)),
                _clean(inv.get("access_key", "")),
                dt_emi,
                dt_emi,
                tot_inv,
                "0",  # Indicador do tipo de pagamento: 0 - À vista
                tot_desc,
                "0,00", # Abatimento
                tot_prod,
                "0",  # Frete: 0 - Por conta do emitente (CIF)
                "0,00", # Frete
                "0,00", # Seguro
                "0,00", # Outras despesas
                tot_prod, # Base ICMS
                tot_icms,
                "0,00", # Base ICMS ST
                "0,00", # Valor ICMS ST
                "0,00", # Valor IPI
                tot_pis,
                tot_cofins,
                "0,00", # PIS ST
                "0,00", # COFINS ST
            ])

            # C190: Registro Analítico da Nota
            add_line("C190", [
                "0102",  # CST ICMS
                "5102",  # CFOP
                "0,00",  # Alíquota ICMS
                tot_prod,
                tot_prod,
                "0,00",
                "0,00",
                "0,00",
                "0,00",
                "",      # Código de observação
            ])

        # C990: Encerramento Bloco C
        reg_counts["C990"] = 1
        bloco_c_total = sum(v for k, v in reg_counts.items() if k.startswith("C"))
        lines.append(f"|C990|{bloco_c_total}|")

        # ==========================================
        # BLOCO E: APURAÇÃO DO ICMS
        # ==========================================
        add_line("E001", ["0"])  # Abertura Bloco E
        add_line("E100", [_fmt_date(start_date), _fmt_date(end_date)])
        add_line("E110", [
            "0,00", "0,00", "0,00", "0,00", "0,00", "0,00",
            "0,00", "0,00", "0,00", "0,00", "0,00", "0,00",
            "0,00", "0,00",
        ])

        reg_counts["E990"] = 1
        bloco_e_total = sum(v for k, v in reg_counts.items() if k.startswith("E"))
        lines.append(f"|E990|{bloco_e_total}|")

        # ==========================================
        # BLOCO 9: CONTROLE E ENCERRAMENTO
        # ==========================================
        add_line("9001", ["0"])  # Abertura Bloco 9

        for reg, count in sorted(reg_counts.items()):
            add_line("9900", [reg, str(count)])

        # 9900 para o próprio 9900 e para o 9990 e 9999
        add_line("9900", ["9900", str(len(reg_counts) + 2)])
        add_line("9900", ["9990", "1"])
        add_line("9900", ["9999", "1"])

        reg_counts["9990"] = 1
        bloco_9_total = sum(v for k, v in reg_counts.items() if k.startswith("9")) + 3
        lines.append(f"|9990|{bloco_9_total}|")

        total_file_lines = len(lines) + 1
        lines.append(f"|9999|{total_file_lines}|")

        return "\r\n".join(lines) + "\r\n"
