"""
Gerador do SPED Contábil (ECD — Escrituração Contábil Digital).
Blocos: 0 (Identificação), I (Lançamentos Contábeis e Plano de Contas),
        J (Demonstrações Contábeis e Termo de Encerramento), 9 (Controle).
Referência: Guia Prático ECD Leiaute 9 — Receita Federal do Brasil.
"""
import re
from typing import Any, Dict, List


def _c(val: Any) -> str:
    return str(val or "").strip().replace("|", "").replace("\n", " ")


def _digits(val: Any) -> str:
    return re.sub(r"\D", "", str(val or ""))


def _d(dt: str) -> str:
    if not dt:
        return ""
    clean = re.sub(r"\D", "", str(dt)[:10])
    if len(clean) == 8:
        return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
    return clean


def _n(val: Any, dec: int = 2) -> str:
    try:
        return f"{abs(float(val or 0)):.{dec}f}".replace(".", ",")
    except Exception:
        return "0,00"


class EcdGenerator:
    """
    Gera o arquivo ECD (SPED Contábil) em conformidade com o leiaute oficial do PVA RFB.
    """

    @staticmethod
    def generate(
        company: Dict[str, Any],
        accounts: List[Dict[str, Any]],
        entries: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        year: int,
    ) -> str:
        lines: List[str] = []
        reg_count: Dict[str, int] = {}

        def emit(*fields: Any) -> None:
            reg = str(fields[0])
            row = "|" + "|".join(_c(f) if i > 0 else reg for i, f in enumerate(fields)) + "|\r\n"
            reg_count[reg] = reg_count.get(reg, 0) + 1
            lines.append(row)

        def close_block(prefix: str, close_reg: str) -> None:
            reg_count[close_reg] = reg_count.get(close_reg, 0) + 1
            tot = sum(v for k, v in reg_count.items() if k.startswith(prefix))
            lines.append(f"|{close_reg}|{tot}|\r\n")

        cnpj = _digits(company.get("cnpj"))
        razao = _c(company.get("razao_social") or "EMPRESA")
        uf = _c(company.get("uf") or "MT")
        ie = _digits(company.get("inscricao_estadual"))
        im = _c(company.get("inscricao_municipal"))
        cod_mun = _digits(company.get("codigo_ibge_municipio")) or "5103403"
        dt_ini = _d(start_date)
        dt_fim = _d(end_date)

        # ── BLOCO 0 — Abertura, Identificação e Referências ──────────────────
        emit("0000", "LECD", dt_ini, dt_fim, razao, cnpj, uf, ie, cod_mun, im,
             "", "0", "0", "1", "0", "", "", "N", "N", "0", "0", "0")
        emit("0001", "0")
        emit("0007", uf, "")
        emit("0020", "0", cnpj, uf, ie, cod_mun, im, "")
        emit("0150", "1", razao, "01058", cnpj, "", "", uf, ie, "", cod_mun, "", "")
        close_block("0", "0990")

        # ── BLOCO I — Lançamentos Contábeis ───────────────────────────────────
        emit("I001", "0")
        emit("I010", "G", "9.00")  # G = Livro Diário Geral, versão leiaute 9.00
        emit("I030", "TERMO DE ABERTURA", "1", "DIARIO GERAL", "1", razao, "", cnpj,
             dt_ini, "", _c(company.get("cidade") or "CUIABA"), dt_fim)

        dt_alt = dt_ini
        for acc in accounts:
            code = _c(acc.get("code"))
            ind_cta = "A" if acc.get("accepts_entries", 1) else "S"
            nivel = str(code.count(".") + 1)
            nat_map = {
                "ativo": "01",
                "passivo": "02",
                "patrimonio_liquido": "03",
                "receita": "04",
                "custo": "04",
                "despesa": "04",
            }
            cod_nat = nat_map.get(acc.get("account_type", ""), "09")
            emit("I050", dt_alt, cod_nat, ind_cta, nivel, code, _c(acc.get("parent_code")), _c(acc.get("name")))
            ref_code = _c(acc.get("referencial_code"))
            if ind_cta == "A" and ref_code:
                emit("I051", "10", "", ref_code)

        # I150 / I155 — Saldos Periódicos
        analiticas = [a for a in accounts if a.get("accepts_entries", 1)]
        emit("I150", dt_ini, dt_fim)
        for acc in analiticas:
            td = float(acc.get("_total_debit", 0.0) or 0.0)
            tc = float(acc.get("_total_credit", 0.0) or 0.0)
            is_dev = acc.get("nature") == "devedora"
            saldo = (td - tc) if is_dev else (tc - td)
            ind_fin = "D" if (saldo >= 0 and is_dev) or (saldo < 0 and not is_dev) else "C"
            emit("I155", _c(acc.get("code")), "", "0,00", "D" if is_dev else "C",
                 _n(td), _n(tc), _n(saldo), ind_fin)

        # I200 / I250 — Lançamentos Contábeis (Livro Diário)
        for entry in entries:
            eid = str(entry.get("id", ""))
            vl_lcto = float(entry.get("total_debit") or 0.0)
            ind_lcto = "E" if entry.get("entry_type") == "encerramento" else "N"
            emit("I200", eid, _d(entry.get("entry_date", "")), _n(vl_lcto), ind_lcto, "")
            for ln in entry.get("lines", []):
                debit = float(ln.get("debit", 0.0) or 0.0)
                credit = float(ln.get("credit", 0.0) or 0.0)
                ind_dc = "D" if debit > 0 else "C"
                valor = debit if debit > 0 else credit
                if valor <= 0:
                    continue
                emit("I250",
                     _c(ln.get("account_code", ln.get("account_id", ""))),
                     _c(ln.get("cost_center_id") or ""),
                     _n(valor),
                     ind_dc,
                     _c(entry.get("document_number") or ""),
                     "",
                     _c(ln.get("description") or entry.get("description") or "LANCTO CONTABIL"),
                     "")

        # I350 / I355 — Saldos das Contas de Resultado antes do Encerramento
        resultado_accs = [a for a in analiticas if a.get("account_type") in ("receita", "custo", "despesa")]
        if resultado_accs:
            emit("I350", dt_fim)
            for acc in resultado_accs:
                td = float(acc.get("_total_debit", 0.0) or 0.0)
                tc = float(acc.get("_total_credit", 0.0) or 0.0)
                saldo = (td - tc) if acc.get("nature") == "devedora" else (tc - td)
                if abs(saldo) < 0.01:
                    continue
                ind_dc = "D" if (acc.get("nature") == "devedora" and saldo >= 0) or (acc.get("nature") == "credora" and saldo < 0) else "C"
                emit("I355", _c(acc.get("code")), "", _n(saldo), ind_dc)

        close_block("I", "I990")

        # ── BLOCO J — Demonstrações Contábeis ────────────────────────────────
        emit("J001", "0")
        emit("J005", dt_ini, dt_fim, "1", "DEMONSTRACOES CONTABEIS CONSOLIDADAS")

        # J100 — Balanço Patrimonial
        bp_accs = [a for a in accounts if a.get("account_type") in ("ativo", "passivo", "patrimonio_liquido")]
        for acc in bp_accs:
            td = float(acc.get("_total_debit", 0.0) or 0.0)
            tc = float(acc.get("_total_credit", 0.0) or 0.0)
            saldo = (td - tc) if acc.get("nature") == "devedora" else (tc - td)
            ind_grp = "A" if acc.get("account_type") == "ativo" else "P"
            ind_cod = "T" if not acc.get("accepts_entries", 1) else "D"
            ind_dc = "D" if (saldo >= 0 and acc.get("nature") == "devedora") or (saldo < 0 and acc.get("nature") != "devedora") else "C"
            emit("J100", _c(acc.get("code")), ind_cod, str(_c(acc.get("code")).count(".") + 1),
                 _c(acc.get("parent_code")), ind_grp, _c(acc.get("name")), "0,00", "D" if acc.get("nature") == "devedora" else "C",
                 _n(saldo), ind_dc, "")

        # J150 — Demonstração do Resultado do Exercício (DRE)
        dre_accs = [a for a in accounts if a.get("account_type") in ("receita", "custo", "despesa")]
        for idx, acc in enumerate(dre_accs, start=1):
            td = float(acc.get("_total_debit", 0.0) or 0.0)
            tc = float(acc.get("_total_credit", 0.0) or 0.0)
            saldo = (tc - td) if acc.get("account_type") == "receita" else (td - tc)
            ind_vl = "P" if (acc.get("account_type") == "receita" and saldo >= 0) else "N"
            emit("J150", str(idx), _c(acc.get("code")), "D" if acc.get("accepts_entries", 1) else "T",
                 str(_c(acc.get("code")).count(".") + 1), _c(acc.get("parent_code")),
                 _c(acc.get("name")), _n(saldo), ind_vl, "R" if acc.get("account_type") == "receita" else "D", "")

        # J210 — DLPA / DMPL resumida
        emit("J210", "0", "2.3.03", "LUCROS OU PREJUIZOS ACUMULADOS", "0,00", "C", "0,00", "C")

        # J900 / J930 — Termo de Encerramento e Signatários
        total_prev_lines = len(lines) + 8
        emit("J900", "TERMO DE ENCERRAMENTO", "1", "DIARIO GERAL", razao, str(total_prev_lines), dt_ini, dt_fim)
        emit("J930", _c(company.get("razao_social") or "ADMINISTRADOR"), cnpj[:11] or "00000000000",
             "ADMINISTRADOR", "900", "", _c(company.get("email")), _c(company.get("telefone")), uf, "", "", "N")
        emit("J930", _c(company.get("contador_nome") or "CONTADOR RESPONSAVEL"),
             _digits(company.get("contador_cpf")) or "00000000000",
             "CONTADOR", "900", _c(company.get("contador_crc") or "CRC-000000/O"),
             _c(company.get("contador_email") or company.get("email")), "", uf, "", "", "S")
        close_block("J", "J990")

        # ── BLOCO 9 — Controle e Encerramento ─────────────────────────────────
        emit("9001", "0")
        existing = sorted(reg_count.keys())
        all_9900 = dict(reg_count)
        all_9900["9900"] = len(existing) + 3
        all_9900["9990"] = 1
        all_9900["9999"] = 1
        for reg, cnt in sorted(all_9900.items()):
            lines.append(f"|9900|{reg}|{cnt}|\r\n")
            reg_count["9900"] = reg_count.get("9900", 0) + 1

        reg_count["9990"] = 1
        reg_count["9999"] = 1
        b9_tot = sum(v for k, v in reg_count.items() if k.startswith("9"))
        lines.append(f"|9990|{b9_tot}|\r\n")
        lines.append(f"|9999|{len(lines) + 1}|\r\n")

        return "".join(lines)
