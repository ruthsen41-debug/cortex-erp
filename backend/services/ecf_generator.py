"""
Gerador do SPED ECF (Escrituração Contábil Fiscal).
Blocos: 0 (Abertura e Parâmetros), J (Plano de Contas e Mapeamento Referencial),
        L (Lucro Real: Balanço e DRE), M (e-LALUR/e-LACS Parte A e Parte B),
        N (Apuração IRPJ e CSLL Lucro Real), P (Lucro Presumido),
        Y (Informações Gerais) e 9 (Controle e Encerramento).
Referência: Manual de Orientação do Leiaute da ECF — Receita Federal do Brasil.
"""
import re
from typing import Any, Dict, List


def _c(v: Any) -> str:
    return str(v or "").strip().replace("|", "").replace("\n", " ")


def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def _d(dt: str) -> str:
    clean = re.sub(r"\D", "", str(dt or "")[:10])
    if len(clean) == 8:
        return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
    return clean


def _n(v: Any) -> str:
    try:
        return f"{abs(float(v or 0.0)):.2f}".replace(".", ",")
    except Exception:
        return "0,00"


class EcfGenerator:
    """Gera o arquivo oficial SPED ECF (.txt) pronto para importação no PVA da RFB."""

    @staticmethod
    def generate(
        company: Dict[str, Any],
        year: int,
        accounts: List[Dict[str, Any]],
        lalur_lancs: List[Dict[str, Any]],
        parte_b: List[Dict[str, Any]],
        apuracao: Dict[str, Any],
        receita_bruta: float = 0.0,
    ) -> str:
        lines: List[str] = []
        reg_count: Dict[str, int] = {}

        def emit(*fields: Any) -> None:
            reg = str(fields[0])
            lines.append("|" + "|".join(_c(f) if i > 0 else reg for i, f in enumerate(fields)) + "|\r\n")
            reg_count[reg] = reg_count.get(reg, 0) + 1

        def close_block(prefix: str, close_reg: str) -> None:
            reg_count[close_reg] = reg_count.get(close_reg, 0) + 1
            tot = sum(v for k, v in reg_count.items() if k.startswith(prefix))
            lines.append(f"|{close_reg}|{tot}|\r\n")

        cnpj = _digits(company.get("cnpj"))
        razao = _c(company.get("razao_social") or "EMPRESA")
        regime = (company.get("regime_tributario") or "lucro_presumido").lower()
        forma_trib = "1" if regime == "lucro_real" else ("5" if regime == "lucro_presumido" else "9")
        dt_ini = f"0101{year}"
        dt_fim = f"3112{year}"

        # ── BLOCO 0 ───────────────────────────────────────────────────────────
        emit("0000", "LECF", "0010", cnpj, razao, "0", "", "", "0", dt_ini, dt_fim, "N", "", "N", "")
        emit("0001", "0")
        emit("0010", "", "N", "N", forma_trib, "A" if regime == "lucro_real" else "T", "01", "C", "RRRR", "", "", "", "", "", "", "")
        emit("0020", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N", "N")
        emit("0930", _c(company.get("contador_nome") or "CONTADOR RESPONSAVEL"),
             _digits(company.get("contador_cpf")) or "00000000000",
             "900", _c(company.get("contador_crc") or "CRC-000000/O"),
             _c(company.get("contador_email") or company.get("email")),
             _c(company.get("telefone")))
        close_block("0", "0990")

        # ── BLOCO J — Plano de Contas e Plano Referencial ─────────────────────
        emit("J001", "0")
        for acc in accounts:
            ind = "A" if acc.get("accepts_entries", 1) else "S"
            nivel = str(_c(acc.get("code")).count(".") + 1)
            nat_map = {"ativo": "01", "passivo": "02", "patrimonio_liquido": "03", "receita": "04", "custo": "04", "despesa": "04"}
            emit("J050", dt_ini, nat_map.get(acc.get("account_type", ""), "09"), ind, nivel,
                 _c(acc.get("code")), _c(acc.get("parent_code")), _c(acc.get("name")))
            if ind == "A" and acc.get("referencial_code"):
                emit("J051", "", _c(acc.get("referencial_code")))
        close_block("J", "J990")

        # ── BLOCO L — Lucro Real: Balanço Patrimonial e DRE ───────────────────
        if regime == "lucro_real":
            emit("L001", "0")
            emit("L030", dt_ini, dt_fim, "A00")
            for acc in accounts:
                if not acc.get("accepts_entries", 1):
                    continue
                td = float(acc.get("_total_debit", 0.0) or 0.0)
                tc = float(acc.get("_total_credit", 0.0) or 0.0)
                cod_ref = _c(acc.get("referencial_code") or acc.get("code"))
                if acc.get("account_type") in ("ativo", "passivo", "patrimonio_liquido"):
                    saldo = (td - tc) if acc.get("nature") == "devedora" else (tc - td)
                    dc = "D" if (saldo >= 0 and acc.get("nature") == "devedora") or (saldo < 0 and acc.get("nature") != "devedora") else "C"
                    emit("L100", cod_ref, _c(acc.get("name")), "A", str(cod_ref.count(".") + 1),
                         _c(acc.get("parent_code")), "0,00", "D" if acc.get("nature") == "devedora" else "C",
                         _n(td), _n(tc), _n(saldo), dc)
                elif acc.get("account_type") in ("receita", "custo", "despesa"):
                    saldo = (tc - td) if acc.get("account_type") == "receita" else (td - tc)
                    dc = "C" if acc.get("account_type") == "receita" else "D"
                    emit("L300", cod_ref, _c(acc.get("name")), "A", str(cod_ref.count(".") + 1),
                         _c(acc.get("parent_code")), _n(saldo), dc)
            close_block("L", "L990")

            # ── BLOCO M — e-LALUR e e-LACS ────────────────────────────────────
            emit("M001", "0")
            for idx, pb in enumerate(parte_b, start=1):
                saldo_pb = float(pb.get("saldo") or 0.0)
                emit("M010", f"PB{idx:03d}", _c(pb.get("descricao")), dt_ini,
                     "0,00", _n(saldo_pb), "D" if saldo_pb < 0 else "C", "")
            emit("M300", "2", "ADICOES AO LUCRO REAL", "A", "A", _n(apuracao.get("adicoes", 0.0)), "LALUR PARTE A")
            for lanc in lalur_lancs:
                tp = "A" if lanc.get("tipo") == "adicao" else "E"
                emit("M300", "50" if tp == "A" else "150", _c(lanc.get("descricao")), "A", tp,
                     _n(lanc.get("valor")), _c(lanc.get("parte_b_descricao") or "LALUR"))
                emit("M350", "50" if tp == "A" else "150", _c(lanc.get("descricao")), "A", tp,
                     _n(lanc.get("valor")), "LACS")
            close_block("M", "M990")

            # ── BLOCO N — Cálculo IRPJ / CSLL Lucro Real ──────────────────────
            emit("N001", "0")
            emit("N030", dt_ini, dt_fim, "A00")
            emit("N620", "1", "LUCRO REAL DO PERIODO", _n(apuracao.get("lucro_real", 0.0)))
            emit("N630", "1", "IRPJ 15%", _n(apuracao.get("irpj_15pct", 0.0)))
            emit("N630", "2", "ADICIONAL IRPJ 10%", _n(apuracao.get("irpj_adicional_10pct", 0.0)))
            emit("N660", "1", "BASE DE CALCULO CSLL", _n(apuracao.get("base_calculo_positiva", 0.0)))
            emit("N670", "1", "CSLL 9%", _n(apuracao.get("csll_9pct", 0.0)))
            close_block("N", "N990")

            emit("P001", "1")
            close_block("P", "P990")
        else:
            emit("L001", "1")
            close_block("L", "L990")
            emit("M001", "1")
            close_block("M", "M990")
            emit("N001", "1")
            close_block("N", "N990")

            # ── BLOCO P — Lucro Presumido ─────────────────────────────────────
            emit("P001", "0")
            emit("P030", dt_ini, dt_fim, "T01")
            emit("P100", "1.01.01.01.01", "ATIVO", "S", "1", "", "0,00", "D", "0,00", "D")
            emit("P150", "3.01.01.01.01", "RECEITA BRUTA", "A", "1", "", _n(receita_bruta), "C")
            base_ir = round(receita_bruta * 0.32, 2)
            base_cs = round(receita_bruta * 0.32, 2)
            emit("P200", "1", "BASE DE CALCULO IRPJ PRESUMIDO", _n(base_ir))
            emit("P400", "1", "BASE DE CALCULO CSLL PRESUMIDO", _n(base_cs))
            close_block("P", "P990")

        # ── BLOCO Y ───────────────────────────────────────────────────────────
        emit("Y001", "1")
        close_block("Y", "Y990")

        # ── BLOCO 9 ───────────────────────────────────────────────────────────
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
