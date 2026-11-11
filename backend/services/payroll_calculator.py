"""
Calculadora de Folha de Pagamento — INSS, IRRF, FGTS (tabelas 2024).
"""
from dataclasses import dataclass


# ── Tabela INSS progressiva 2024 ────────────────────────────────────────────
_INSS_BRACKETS = [
    (1_412.00,  0.075),
    (2_666.68,  0.090),
    (4_000.03,  0.120),
    (7_786.02,  0.140),
]
_INSS_TETO = 908.86  # teto 2024

# ── Tabela IRRF mensal 2024 ──────────────────────────────────────────────────
_IRRF_TABLE = [
    (2_259.20,  0.000, 0.00),
    (2_826.65,  0.075, 169.44),
    (3_751.05,  0.150, 381.44),
    (4_664.68,  0.225, 662.77),
    (float("inf"), 0.275, 896.00),
]
_IRRF_DEDUCTION_PER_DEP = 189.59

# ── FGTS ────────────────────────────────────────────────────────────────────
_FGTS_RATE = 0.08

# ── VT (Vale Transporte) ─────────────────────────────────────────────────────
_VT_EMPLOYEE_RATE = 0.06  # 6% do salário bruto (desconto máximo do funcionário)


@dataclass
class PayrollResult:
    gross_salary: float
    inss: float
    irrf: float
    fgts: float          # encargo do empregador
    vt_discount: float   # desconto do funcionário
    other_discounts: float
    net_salary: float

    def as_dict(self) -> dict:
        return {
            "gross_salary":    round(self.gross_salary, 2),
            "inss":            round(self.inss, 2),
            "irrf":            round(self.irrf, 2),
            "fgts":            round(self.fgts, 2),
            "vt_discount":     round(self.vt_discount, 2),
            "other_discounts": round(self.other_discounts, 2),
            "net_salary":      round(self.net_salary, 2),
        }


def calc_inss(gross: float) -> float:
    """INSS progressivo 2024 com teto."""
    if gross <= 0:
        return 0.0
    total = 0.0
    prev_limit = 0.0
    for limit, rate in _INSS_BRACKETS:
        if gross <= prev_limit:
            break
        base = min(gross, limit) - prev_limit
        total += base * rate
        prev_limit = limit
        if gross <= limit:
            break
    return round(min(total, _INSS_TETO), 2)


def calc_irrf(gross: float, inss: float, dependents: int = 0) -> float:
    """IRRF mensal 2024 sobre base = gross - inss - deduções por dependente."""
    base = gross - inss - (dependents * _IRRF_DEDUCTION_PER_DEP)
    if base <= 0:
        return 0.0
    for limit, rate, deduction in _IRRF_TABLE:
        if base <= limit:
            irrf = base * rate - deduction
            return round(max(irrf, 0.0), 2)
    return 0.0


def calc_fgts(gross: float) -> float:
    return round(gross * _FGTS_RATE, 2)


def calc_vt_discount(gross: float, vt_monthly: float) -> float:
    """Desconto VT do funcionário: mínimo entre 6% do salário e o custo real do VT."""
    if vt_monthly <= 0:
        return 0.0
    max_disc = round(gross * _VT_EMPLOYEE_RATE, 2)
    return round(min(max_disc, vt_monthly), 2)


def calculate_payroll(
    gross_salary: float,
    dependents: int = 0,
    vt_monthly: float = 0.0,
    other_discounts: float = 0.0,
    is_prolabore: bool = False,
) -> PayrollResult:
    """
    Calcula a folha completa de um funcionário.
    Pro-labore: INSS 11% fixo (contribuinte individual), sem FGTS.
    """
    if is_prolabore:
        inss = round(min(gross_salary * 0.11, _INSS_TETO), 2)
        fgts = 0.0
    else:
        inss = calc_inss(gross_salary)
        fgts = calc_fgts(gross_salary)

    irrf = calc_irrf(gross_salary, inss, dependents)
    vt_disc = calc_vt_discount(gross_salary, vt_monthly)
    total_disc = inss + irrf + vt_disc + other_discounts
    net = round(gross_salary - total_disc, 2)

    return PayrollResult(
        gross_salary=gross_salary,
        inss=inss,
        irrf=irrf,
        fgts=fgts,
        vt_discount=vt_disc,
        other_discounts=other_discounts,
        net_salary=net,
    )


def calc_thirteenth(gross_salary: float, months_worked: int = 12) -> dict:
    """13º Salário proporcional (1ª e 2ª parcela)."""
    months_worked = min(max(months_worked, 0), 12)
    value = round(gross_salary * months_worked / 12, 2)
    first = round(value / 2, 2)
    # 2ª parcela: desconta INSS e IRRF sobre o valor integral
    inss = calc_inss(value)
    irrf = calc_irrf(value, inss)
    second = round(value - first - inss - irrf, 2)
    return {
        "months_worked": months_worked,
        "gross_value": value,
        "first_installment": first,
        "inss": inss,
        "irrf": irrf,
        "second_installment": second,
        "total_net": round(first + second, 2),
    }


def calc_vacation(gross_salary: float, days: int = 30, dependents: int = 0) -> dict:
    """Férias (máx. 30 dias) + 1/3 constitucional."""
    daily = gross_salary / 30
    vacation_pay = round(daily * days, 2)
    third = round(vacation_pay / 3, 2)
    gross_total = round(vacation_pay + third, 2)
    inss = calc_inss(gross_total)
    irrf = calc_irrf(gross_total, inss, dependents)
    net = round(gross_total - inss - irrf, 2)
    return {
        "days": days,
        "vacation_pay": vacation_pay,
        "constitutional_third": third,
        "gross_total": gross_total,
        "inss": inss,
        "irrf": irrf,
        "net_total": net,
    }


def calc_termination(
    gross_salary: float,
    admission_date: str,
    termination_date: str,
    type: str = "sem_justa_causa",
) -> dict:
    """
    Verbas rescisórias.
    type: sem_justa_causa | com_justa_causa | pedido_demissao
    """
    from datetime import date as _date
    import re as _re

    def parse(d):
        clean = _re.sub(r"\D", "", str(d)[:10])
        return _date(int(clean[:4]), int(clean[4:6]), int(clean[6:8]))

    adm = parse(admission_date)
    dem = parse(termination_date)
    months = (dem.year - adm.year) * 12 + (dem.month - adm.month)
    years = months / 12

    saldo_dias = dem.day
    saldo = round(gross_salary / 30 * saldo_dias, 2)

    # 13º proporcional
    months_in_year = dem.month if dem.month > 0 else 1
    decimo = round(gross_salary * months_in_year / 12, 2)

    # Férias vencidas + proporcionais
    ferias_vencidas = gross_salary if months >= 12 else 0.0
    ferias_prop = round(gross_salary * months_in_year / 12, 2)
    tercio = round((ferias_vencidas + ferias_prop) / 3, 2)

    # Aviso prévio indenizado (sem justa causa): 30 dias + 3 dias/ano
    aviso = 0.0
    multa_fgts = 0.0
    if type == "sem_justa_causa":
        dias_aviso = min(30 + int(years) * 3, 90)
        aviso = round(gross_salary / 30 * dias_aviso, 2)
        fgts_total = round(gross_salary * 0.08 * months, 2)
        multa_fgts = round(fgts_total * 0.40, 2)

    total_bruto = round(saldo + decimo + ferias_vencidas + ferias_prop + tercio + aviso, 2)
    inss = calc_inss(total_bruto)
    irrf = calc_irrf(total_bruto, inss)
    total_liquido = round(total_bruto - inss - irrf + multa_fgts, 2)

    return {
        "type": type,
        "months_worked": months,
        "saldo_salario": saldo,
        "decimo_terceiro": decimo,
        "ferias_vencidas": ferias_vencidas,
        "ferias_proporcionais": ferias_prop,
        "terco_constitucional": tercio,
        "aviso_previo": aviso,
        "multa_fgts_40pct": multa_fgts,
        "total_bruto": total_bruto,
        "inss": inss,
        "irrf": irrf,
        "total_liquido": total_liquido,
    }
