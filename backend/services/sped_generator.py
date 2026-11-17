from typing import Any, Dict, List, Optional
import re


def _clean(val: Any) -> str:
    return str(val or "").strip().replace("|", "").replace("\n", " ")


def _digits(val: Any) -> str:
    return re.sub(r"\D", "", str(val or ""))


def _fmt_date(dt_str: str) -> str:
    if not dt_str:
        return ""
    clean = re.sub(r"\D", "", str(dt_str)[:10])
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
    Gerador do SPED Fiscal (EFD ICMS/IPI — Leiaute 018) em conformidade com o Guia Prático RFB / SEFAZ.
    Blocos: 0 (Identificação/Participantes), C (Documentos Fiscais), E (Apuração ICMS),
            G (CIAP), H (Inventário), 1 (Outras Info) e 9 (Encerramento exato).
    """

    @staticmethod
    def generate(
        company: Dict[str, Any],
        invoices: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        fiscal_entries: Optional[List[Dict[str, Any]]] = None,
        apuration_icms: Optional[Dict[str, Any]] = None,
        fixed_assets: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        lines: List[str] = []
        reg_counts: Dict[str, int] = {}

        def add_line(reg: str, fields: List[str]) -> None:
            lines.append(f"|{reg}|{'|'.join(str(f) for f in fields)}|")
            reg_counts[reg] = reg_counts.get(reg, 0) + 1

        def close_block(prefix: str, close_reg: str) -> None:
            reg_counts[close_reg] = reg_counts.get(close_reg, 0) + 1
            total = sum(v for k, v in reg_counts.items() if k.startswith(prefix))
            lines.append(f"|{close_reg}|{total}|")

        cnpj_emp = _digits(company.get("cnpj"))
        cod_mun = _digits(company.get("codigo_ibge_municipio")) or "5103403"

        # ── Unifica invoices e fiscal_entries (evitando duplicidade) ───────────
        docs: List[Dict[str, Any]] = []
        linked_inv_ids = {
            e.get("origem_id") for e in (fiscal_entries or [])
            if e.get("origem_tipo") == "invoice" and e.get("origem_id")
        }
        for fe in (fiscal_entries or []):
            tipo = fe.get("tipo", "saida")
            if tipo not in ("entrada", "saida"):
                continue
            mod = str(fe.get("modelo") or "55")
            if mod not in ("55", "65", "01", "1B", "04"):
                continue
            docs.append({
                "ind_oper": "0" if tipo == "entrada" else "1",
                "ind_emit": "1" if tipo == "entrada" else "0",
                "part_doc": _digits(fe.get("participante_doc")),
                "part_nome": _clean(fe.get("participante_nome") or "PARTICIPANTE"),
                "part_uf": _clean(fe.get("uf_origem") if tipo == "entrada" else fe.get("uf_destino")) or _clean(company.get("uf", "MT")),
                "cod_part": f"P{_digits(fe.get('participante_doc')) or fe.get('contact_id') or fe.get('id')}",
                "modelo": mod.zfill(2)[:2],
                "serie": _clean(fe.get("serie") or "1"),
                "numero": _clean(fe.get("numero") or fe.get("id")),
                "chave": _digits(fe.get("chave_acesso")),
                "dt_doc": _fmt_date(fe.get("data_emissao") or start_date),
                "dt_es": _fmt_date(fe.get("data_escrituracao") or fe.get("data_emissao") or start_date),
                "vl_doc": float(fe.get("valor_contabil") or 0.0),
                "vl_desc": float(fe.get("valor_desconto") or 0.0),
                "vl_merc": float(fe.get("valor_produtos") or fe.get("valor_contabil") or 0.0),
                "vl_frt": float(fe.get("valor_frete") or 0.0),
                "cst_icms": str(fe.get("cst_icms") or "00").zfill(3)[-3:],
                "cfop": _digits(fe.get("cfop") or ("1102" if tipo == "entrada" else "5102")) or "5102",
                "aliq_icms": float(fe.get("aliquota_icms") or 0.0),
                "bc_icms": float(fe.get("base_icms") or 0.0),
                "vl_icms": float(fe.get("valor_icms") or 0.0),
                "bc_st": float(fe.get("base_icms_st") or 0.0),
                "vl_st": float(fe.get("valor_icms_st") or 0.0),
                "vl_ipi": float(fe.get("valor_ipi") or 0.0),
                "vl_pis": float(fe.get("valor_pis") or 0.0),
                "vl_cofins": float(fe.get("valor_cofins") or 0.0),
            })

        for inv in invoices:
            if inv.get("id") in linked_inv_ids:
                continue
            mod_raw = str(inv.get("model") or "")
            if "nfse" in mod_raw.lower():
                continue
            mod = "65" if "65" in mod_raw else "55"
            part_doc = _digits(inv.get("recipient_doc"))
            tot_prod = float(inv.get("total_products") or inv.get("total_invoice") or 0.0)
            tot_icms = float(inv.get("total_icms") or 0.0)
            aliq_est = round((tot_icms / tot_prod * 100.0), 2) if (tot_prod > 0 and tot_icms > 0) else 0.0
            docs.append({
                "ind_oper": "1",
                "ind_emit": "0",
                "part_doc": part_doc,
                "part_nome": _clean(inv.get("recipient_name") or "CONSUMIDOR"),
                "part_uf": _clean(inv.get("recipient_uf") or company.get("uf", "MT")),
                "cod_part": f"P{part_doc or inv.get('contact_id') or inv.get('id') or '1'}",
                "modelo": mod,
                "serie": _clean(inv.get("series") or "1"),
                "numero": _clean(inv.get("number") or inv.get("id") or "1"),
                "chave": _digits(inv.get("access_key")),
                "dt_doc": _fmt_date(inv.get("issued_at") or start_date),
                "dt_es": _fmt_date(inv.get("issued_at") or start_date),
                "vl_doc": float(inv.get("total_invoice") or 0.0),
                "vl_desc": float(inv.get("total_discounts") or 0.0),
                "vl_merc": tot_prod,
                "vl_frt": float(inv.get("total_shipping") or 0.0),
                "cst_icms": "000" if tot_icms > 0 else "102",
                "cfop": "5102",
                "aliq_icms": aliq_est,
                "bc_icms": tot_prod if tot_icms > 0 else 0.0,
                "vl_icms": tot_icms,
                "bc_st": 0.0,
                "vl_st": 0.0,
                "vl_ipi": 0.0,
                "vl_pis": float(inv.get("total_pis") or 0.0),
                "vl_cofins": float(inv.get("total_cofins") or 0.0),
            })

        # ==========================================
        # BLOCO 0: ABERTURA E IDENTIFICAÇÃO
        # ==========================================
        add_line("0000", [
            "018",
            "0",
            _fmt_date(start_date),
            _fmt_date(end_date),
            _clean(company.get("razao_social", "EMPRESA")),
            cnpj_emp,
            "",
            _clean(company.get("uf", "MT")),
            _clean(company.get("inscricao_estadual", "")),
            cod_mun,
            _clean(company.get("inscricao_municipal", "")),
            "",
            "A",
            "0",
        ])

        add_line("0001", ["0"])

        add_line("0005", [
            _clean(company.get("nome_fantasia", company.get("razao_social", ""))),
            _digits(company.get("cep")) or "78000000",
            _clean(company.get("logradouro", "AVENIDA PRINCIPAL")),
            _clean(company.get("numero", "S/N")),
            _clean(company.get("complemento", "")),
            _clean(company.get("bairro", "CENTRO")),
            _digits(company.get("telefone")),
            "",
            _clean(company.get("email", "")),
        ])

        # 0100: Dados do Contabilista (reais do cadastro da empresa)
        add_line("0100", [
            _clean(company.get("contador_nome") or "CONTADOR RESPONSAVEL"),
            _digits(company.get("contador_cpf")) or "00000000000",
            _clean(company.get("contador_crc") or "CRC-000000/O"),
            _digits(company.get("contador_cnpj")) or cnpj_emp,
            _digits(company.get("contador_cep")) or _digits(company.get("cep")) or "78000000",
            _clean(company.get("contador_endereco") or company.get("logradouro") or "CENTRO"),
            _clean(company.get("contador_numero") or "S/N"),
            "",
            _clean(company.get("contador_bairro") or "CENTRO"),
            _digits(company.get("contador_telefone") or company.get("telefone")),
            "",
            _clean(company.get("contador_email") or company.get("accountant_email") or company.get("email") or ""),
            _digits(company.get("contador_cod_mun")) or cod_mun,
        ])

        # 0150: Cadastro de Participantes únicos
        seen_parts = set()
        for d in docs:
            cp = d["cod_part"]
            if cp in seen_parts:
                continue
            seen_parts.add(cp)
            doc_num = d["part_doc"]
            cnpj_p = doc_num if len(doc_num) == 14 else ""
            cpf_p = doc_num if len(doc_num) == 11 else ""
            add_line("0150", [
                cp,
                d["part_nome"][:100],
                "01058",
                cnpj_p,
                cpf_p,
                "",
                cod_mun,
                "",
                "ENDERECO NAO INFORMADO",
                "S/N",
                "",
                "CENTRO",
            ])

        close_block("0", "0990")

        # ==========================================
        # BLOCO C: DOCUMENTOS FISCAIS
        # ==========================================
        add_line("C001", ["0" if docs else "1"])

        for d in docs:
            add_line("C100", [
                d["ind_oper"],
                d["ind_emit"],
                d["cod_part"],
                d["modelo"],
                "00",
                d["serie"],
                d["numero"],
                d["chave"],
                d["dt_doc"],
                d["dt_es"],
                _fmt_num(d["vl_doc"]),
                "0",
                _fmt_num(d["vl_desc"]),
                "0,00",
                _fmt_num(d["vl_merc"]),
                "9",
                _fmt_num(d["vl_frt"]),
                "0,00",
                "0,00",
                _fmt_num(d["bc_icms"]),
                _fmt_num(d["vl_icms"]),
                _fmt_num(d["bc_st"]),
                _fmt_num(d["vl_st"]),
                _fmt_num(d["vl_ipi"]),
                _fmt_num(d["vl_pis"]),
                _fmt_num(d["vl_cofins"]),
                "0,00",
                "0,00",
            ])

            add_line("C190", [
                d["cst_icms"],
                d["cfop"],
                _fmt_num(d["aliq_icms"]),
                _fmt_num(d["vl_doc"]),
                _fmt_num(d["bc_icms"]),
                _fmt_num(d["vl_icms"]),
                _fmt_num(d["bc_st"]),
                _fmt_num(d["vl_st"]),
                "0,00",
                _fmt_num(d["vl_ipi"]),
                "",
            ])

        close_block("C", "C990")

        # ==========================================
        # BLOCO E: APURAÇÃO DO ICMS
        # ==========================================
        add_line("E001", ["0"])
        add_line("E100", [_fmt_date(start_date), _fmt_date(end_date)])

        if apuration_icms:
            deb = float(apuration_icms.get("debitos") or 0.0)
            cred = float(apuration_icms.get("creditos") or 0.0)
            sld_ant = float(apuration_icms.get("saldo_credor_anterior") or 0.0)
            vl_rec = float(apuration_icms.get("valor_a_recolher") or 0.0)
            sld_transp = float(apuration_icms.get("saldo_credor_transportar") or 0.0)
            venc = _fmt_date(apuration_icms.get("vencimento") or end_date)
        else:
            deb = sum(d["vl_icms"] for d in docs if d["ind_oper"] == "1")
            cred = sum(d["vl_icms"] for d in docs if d["ind_oper"] == "0")
            sld_ant = 0.0
            liq = deb - cred - sld_ant
            vl_rec = max(0.0, round(liq, 2))
            sld_transp = max(0.0, round(-liq, 2))
            venc = _fmt_date(end_date)

        sld_apur = max(0.0, round(deb - cred, 2))
        add_line("E110", [
            _fmt_num(deb),
            "0,00",
            "0,00",
            "0,00",
            _fmt_num(cred),
            "0,00",
            "0,00",
            "0,00",
            _fmt_num(sld_ant),
            _fmt_num(sld_apur),
            "0,00",
            _fmt_num(vl_rec),
            _fmt_num(sld_transp),
            "0,00",
        ])

        if vl_rec > 0:
            mes_ano = _fmt_date(start_date)[2:8]
            add_line("E116", [
                "000",
                _fmt_num(vl_rec),
                venc,
                "1112",
                "",
                "",
                "",
                "",
                mes_ano,
            ])

        close_block("E", "E990")

        # ==========================================
        # BLOCO G: CIAP (ATIVO PERMANENTE)
        # ==========================================
        ciap_assets = [a for a in (fixed_assets or []) if a.get("status") in ("ativo", "depreciado")]
        if ciap_assets:
            add_line("G001", ["0"])
            total_parc = sum(round((float(a.get("icms_credit_total") or (float(a.get("acquisition_value") or 0) * 0.17))) / 48.0, 2) for a in ciap_assets)
            tot_saidas = sum(d["vl_doc"] for d in docs if d["ind_oper"] == "1") or 1.0
            add_line("G110", [
                _fmt_date(start_date),
                _fmt_date(end_date),
                "0,00",
                _fmt_num(total_parc),
                _fmt_num(tot_saidas),
                _fmt_num(tot_saidas),
                "1,00000000",
                _fmt_num(total_parc),
                "0,00",
            ])
            for idx, a in enumerate(ciap_assets, start=1):
                icms_tot = float(a.get("icms_credit_total") or (float(a.get("acquisition_value") or 0) * 0.17))
                parc = round(icms_tot / 48.0, 2)
                add_line("G125", [
                    f"BEM-{a.get('id', idx)}",
                    _fmt_date(a.get("acquisition_date") or start_date),
                    "SI",
                    _fmt_num(icms_tot),
                    "0,00",
                    "0,00",
                    "0,00",
                    "1",
                    _fmt_num(parc),
                ])
            close_block("G", "G990")
        else:
            add_line("G001", ["1"])
            close_block("G", "G990")

        # ==========================================
        # BLOCO H E BLOCO 1
        # ==========================================
        add_line("H001", ["1"])
        close_block("H", "H990")

        add_line("1001", ["1"])
        add_line("1010", ["N"] * 13)
        close_block("1", "1990")

        # ==========================================
        # BLOCO 9: CONTROLE E ENCERRAMENTO
        # ==========================================
        add_line("9001", ["0"])

        existing_regs = sorted(reg_counts.keys())
        # Inclui os próprios registros de controle 9900, 9990 e 9999
        all_9900 = dict(reg_counts)
        all_9900["9900"] = len(existing_regs) + 3
        all_9900["9990"] = 1
        all_9900["9999"] = 1

        for reg, count in sorted(all_9900.items()):
            lines.append(f"|9900|{reg}|{count}|")
            reg_counts["9900"] = reg_counts.get("9900", 0) + 1

        reg_counts["9990"] = 1
        reg_counts["9999"] = 1
        bloco_9_total = sum(v for k, v in reg_counts.items() if k.startswith("9"))
        lines.append(f"|9990|{bloco_9_total}|")

        total_file_lines = len(lines) + 1
        lines.append(f"|9999|{total_file_lines}|")

        return "\r\n".join(lines) + "\r\n"
