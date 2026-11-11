"""
Gerador do SPED Contábil (ECD — Escrituração Contábil Digital).
Blocos: 0 (Identificação), I (Plano de Contas), J (Demonstrações), L (Livro Diário), 9 (Encerramento).
Referência: Guia Prático ECD v9.1 — Receita Federal do Brasil.
"""
import re
from datetime import date
from typing import Any, Dict, List


def _c(val: Any) -> str:
    return str(val or "").strip().replace("|", "").replace("\n", " ")


def _d(dt: str) -> str:
    if not dt:
        return ""
    clean = re.sub(r"\D", "", str(dt)[:10])
    if len(clean) == 8:
        return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
    return clean


def _n(val: Any, dec: int = 2) -> str:
    try:
        return f"{float(val or 0):.{dec}f}".replace(".", ",")
    except Exception:
        return "0,00"


def _row(*fields) -> str:
    return "|" + "|".join(str(f) for f in fields) + "|\r\n"


class EcdGenerator:
    """
    Gera o arquivo ECD (SPED Contábil) a partir dos dados da empresa e dos
    lançamentos contábeis armazenados nas tabelas accounting_*.
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

        def emit(*fields):
            row = _row(*fields)
            reg = str(fields[0])
            reg_count[reg] = reg_count.get(reg, 0) + 1
            lines.append(row)

        cnpj = re.sub(r"\D", "", _c(company.get("cnpj", "")))
        razao = _c(company.get("razao_social", "EMPRESA"))
        uf = _c(company.get("uf", "MT"))
        ie = re.sub(r"\D", "", _c(company.get("inscricao_estadual", "")))
        im = _c(company.get("inscricao_municipal", ""))
        email = _c(company.get("email", ""))
        regime = _c(company.get("regime_tributario", "simples_nacional"))
        ind_sit_esp = ""
        ind_nire = "0"
        hoje = date.today()

        # ── BLOCO 0 ───────────────────────────────────────────────────
        emit("0000", "LECD", "03.00", _d(start_date), _d(end_date),
             razao, cnpj, "", uf, ie, im, email,
             "0",    # ind_sit_ini: 0=regular
             ind_nire, ind_sit_esp, "1")  # ind_grande_porte: 0=não

        emit("0001", "1")  # abre bloco 0 (com dados)

        emit("0007",        # Identificação dos signatários
             "ADMINISTRADOR", "0", "10", cnpj, "1", "", "")

        emit("0150",        # Tabela de Cadastro do Participante
             "1", razao, "0", cnpj, "", "", "", uf, ie, im, email,
             _c(company.get("cep", "")),
             _c(company.get("logradouro", "")),
             _c(company.get("numero", "")),
             _c(company.get("complemento", "")),
             _c(company.get("bairro", "")),
             _c(company.get("cidade", "")),
             "", "")

        emit("0999", reg_count.get("0001", 0) + reg_count.get("0007", 0) +
             reg_count.get("0150", 0) + 2)  # +2: 0000 e 0999

        # ── BLOCO I — Plano de Contas ─────────────────────────────────
        i_count = 0
        emit("I001", "1")
        i_count += 1

        for acc in accounts:
            # Mapeia account_type p/ indicadores ECD
            tp = acc.get("account_type", "")
            ind_cta = "A" if acc.get("accepts_entries", 1) else "S"  # A=analítica S=sintética
            # Nível hierárquico: contagem de pontos no código + 1
            nivel = str(_c(acc.get("code", "")).count(".") + 1)
            # Natureza: D=devedora C=credora
            nat = "D" if acc.get("nature") == "devedora" else "C"

            emit("I010",
                 _c(acc.get("code")),   # cd_cta_ref
                 _c(acc.get("name")),   # nome_cta
                 _c(acc.get("code")),   # cod_cta (mesmo código)
                 nivel,
                 ind_cta,
                 nat,
                 _c(acc.get("parent_code", "")),
                 "")
            i_count += 1

            # Saldo inicial (zero para nova implementação)
            if acc.get("accepts_entries", 1):
                emit("I012", _c(acc.get("code")), _d(start_date), "0,00", nat)
                i_count += 1

        emit("I999", i_count + 2)

        # ── BLOCO J — Balanços ────────────────────────────────────────
        j_count = 0
        emit("J001", "1")
        j_count += 1

        # J100 — Plano de Contas Referencial (simplificado)
        for acc in accounts:
            if not acc.get("accepts_entries", 1):
                continue
            nat = "D" if acc.get("nature") == "devedora" else "C"
            td = round(float(acc.get("_total_debit", 0.0)), 2)
            tc = round(float(acc.get("_total_credit", 0.0)), 2)
            saldo = round((td - tc) if acc.get("nature") == "devedora" else (tc - td), 2)
            emit("J100",
                 _d(end_date),
                 "0",           # DT_INI_BCIA
                 _c(acc.get("code")),
                 _n(td), _n(tc), _n(abs(saldo)), nat)
            j_count += 1

        emit("J999", j_count + 2)

        # ── BLOCO L — Livro Diário ────────────────────────────────────
        l_count = 0
        emit("L001", "1")
        l_count += 1

        # L020 — cabeçalho de cada lançamento
        for entry in entries:
            eid = str(entry.get("id", ""))
            emit("L020",
                 _d(entry.get("entry_date", "")),
                 eid,                             # núm. lançamento
                 _c(entry.get("description", "")),
                 _c(entry.get("document_number", "")),
                 "")
            l_count += 1

            for ln in entry.get("lines", []):
                debit  = float(ln.get("debit", 0.0))
                credit = float(ln.get("credit", 0.0))
                ind_dc = "D" if debit > 0 else "C"
                valor  = debit if debit > 0 else credit
                emit("L022",
                     _c(ln.get("account_code", ln.get("account_id", ""))),
                     ind_dc,
                     _n(valor),
                     _c(ln.get("description", "")))
                l_count += 1

        emit("L999", l_count + 2)

        # ── BLOCO 9 — Encerramento ────────────────────────────────────
        emit("9001", "1")
        total_lines = sum(reg_count.values()) + 4  # +4 p/ 9001..9999
        emit("9900", "0", reg_count.get("0000", 0))
        emit("9900", "I", sum(v for k, v in reg_count.items() if k.startswith("I")))
        emit("9900", "J", sum(v for k, v in reg_count.items() if k.startswith("J")))
        emit("9900", "L", sum(v for k, v in reg_count.items() if k.startswith("L")))
        emit("9900", "9", 6)
        emit("9999", total_lines + 10)

        return "".join(lines)
