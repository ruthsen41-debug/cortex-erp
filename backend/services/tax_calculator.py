from typing import Dict, Any


ICMS_INTERNO_UF: Dict[str, float] = {
    "AC": 19.0, "AL": 19.0, "AM": 20.0, "AP": 18.0, "BA": 20.5, "CE": 20.0,
    "DF": 20.0, "ES": 17.0, "GO": 19.0, "MA": 22.0, "MG": 18.0, "MS": 17.0,
    "MT": 17.0, "PA": 19.0, "PB": 20.0, "PE": 20.5, "PI": 21.0, "PR": 19.5,
    "RJ": 20.0, "RN": 18.0, "RO": 19.5, "RR": 20.0, "RS": 17.0, "SC": 17.0,
    "SE": 19.0, "SP": 18.0, "TO": 20.0,
}
_SUL_SUDESTE_EXCETO_ES = {"SP", "RJ", "MG", "PR", "RS", "SC"}


def get_icms_rate(uf_origem: str, uf_destino: str, importado: bool = False) -> float:
    """Retorna a alíquota de ICMS conforme regra interestadual do Senado / interna por UF."""
    orig = (uf_origem or "MT").strip().upper()[:2]
    dest = (uf_destino or orig).strip().upper()[:2]
    if orig == dest:
        return ICMS_INTERNO_UF.get(orig, 17.0)
    if importado:
        return 4.0
    if orig in _SUL_SUDESTE_EXCETO_ES and dest not in _SUL_SUDESTE_EXCETO_ES:
        return 7.0
    return 12.0


class TaxCalculator:
    """
    Motor Avançado de Tributação e Apuração Fiscal Brasileiro
    Suporta Simples Nacional, Lucro Presumido, Lucro Real, Substituição Tributária e DIFAL/FCP.
    """

    @staticmethod
    def calculate_item_taxes(
        item: Dict[str, Any],
        regime: str = "simples_nacional",
        uf_origem: str = "MT",
        uf_destino: str = "MT",
        is_consumidor_final: bool = True,
        is_contribuinte: bool = False,
    ) -> Dict[str, Any]:
        qty = float(item.get("quantity") or 1.0)
        unit_price = float(item.get("unit_price") or item.get("sale_price") or 0.0)
        subtotal = round(qty * unit_price, 2)
        discount = float(item.get("discount") or 0.0)
        base_calc = max(0.0, subtotal - discount)

        orig = (uf_origem or "MT").strip().upper()[:2]
        dest = (uf_destino or orig).strip().upper()[:2]
        is_interestadual = orig != dest
        importado = str(item.get("origin") or "0") in ("1", "2", "3", "8")

        result = {
            "subtotal": subtotal,
            "base_calculo": base_calc,
            "icms_base": 0.0,
            "icms_aliquota": 0.0,
            "icms_valor": 0.0,
            "icms_credito_aliquota": 0.0,
            "icms_credito_valor": 0.0,
            "pis_base": 0.0,
            "pis_aliquota": 0.0,
            "pis_valor": 0.0,
            "cofins_base": 0.0,
            "cofins_aliquota": 0.0,
            "cofins_valor": 0.0,
            "iss_base": 0.0,
            "iss_aliquota": 0.0,
            "iss_valor": 0.0,
            "difal_aliquota": 0.0,
            "difal_valor": 0.0,
            "fcp_valor": 0.0,
            "total_impostos": 0.0,
        }

        # 1. SERVIÇOS (ISSQN)
        if item.get("type") == "servico" or "servico" in str(item.get("cfop", "")):
            iss_rate = float(item.get("iss_rate") or 3.0)
            iss_val = round(base_calc * (iss_rate / 100.0), 2)
            result["iss_base"] = base_calc
            result["iss_aliquota"] = iss_rate
            result["iss_valor"] = iss_val
            result["total_impostos"] = iss_val
            return result

        # 2. MERCADORIAS (ICMS / PIS / COFINS)
        if regime in ("simples_nacional", "mei"):
            csosn = str(item.get("csosn_cst") or item.get("csosn") or "102")
            if csosn == "101":
                # Permite aproveitamento de crédito
                cred_rate = float(item.get("aliquota_credito_simples") or 2.84)
                cred_val = round(base_calc * (cred_rate / 100.0), 2)
                result["icms_credito_aliquota"] = cred_rate
                result["icms_credito_valor"] = cred_val

            # No Simples, impostos federais e ICMS são recolhidos no DAS unificado
            # alíquota média padrão do Simples Nacional (~4.5% comércio faixa 1)
            simples_rate = float(item.get("aliquota_simples") or 4.5)
            result["total_impostos"] = round(base_calc * (simples_rate / 100.0), 2)

        elif regime == "lucro_presumido":
            # PIS Cumulativo: 0,65%
            pis_rate = 0.65
            pis_val = round(base_calc * (pis_rate / 100.0), 2)

            # COFINS Cumulativo: 3,00%
            cofins_rate = 3.00
            cofins_val = round(base_calc * (cofins_rate / 100.0), 2)

            # ICMS
            icms_rate = float(item.get("icms_rate") or 0.0) or get_icms_rate(orig, dest, importado)
            icms_val = round(base_calc * (icms_rate / 100.0), 2)

            result["pis_base"] = base_calc
            result["pis_aliquota"] = pis_rate
            result["pis_valor"] = pis_val

            result["cofins_base"] = base_calc
            result["cofins_aliquota"] = cofins_rate
            result["cofins_valor"] = cofins_val

            result["icms_base"] = base_calc
            result["icms_aliquota"] = icms_rate
            result["icms_valor"] = icms_val

            result["total_impostos"] = round(pis_val + cofins_val + icms_val, 2)

        elif regime == "lucro_real":
            # PIS Não-Cumulativo: 1,65%
            pis_rate = 1.65
            pis_val = round(base_calc * (pis_rate / 100.0), 2)

            # COFINS Não-Cumulativo: 7,60%
            cofins_rate = 7.60
            cofins_val = round(base_calc * (cofins_rate / 100.0), 2)

            # ICMS
            icms_rate = float(item.get("icms_rate") or 0.0) or get_icms_rate(orig, dest, importado)
            icms_val = round(base_calc * (icms_rate / 100.0), 2)

            result["pis_base"] = base_calc
            result["pis_aliquota"] = pis_rate
            result["pis_valor"] = pis_val

            result["cofins_base"] = base_calc
            result["cofins_aliquota"] = cofins_rate
            result["cofins_valor"] = cofins_val

            result["icms_base"] = base_calc
            result["icms_aliquota"] = icms_rate
            result["icms_valor"] = icms_val

            result["total_impostos"] = round(pis_val + cofins_val + icms_val, 2)

        # 3. DIFAL (Diferencial de Alíquota) em vendas interestaduais a consumidor final não contribuinte
        if is_interestadual and is_consumidor_final and not is_contribuinte:
            aliq_inter = get_icms_rate(orig, dest, importado)
            aliq_intra_dest = ICMS_INTERNO_UF.get(dest, 18.0)
            difal_rate = max(0.0, aliq_intra_dest - aliq_inter)
            difal_val = round(base_calc * (difal_rate / 100.0), 2)
            fcp_val = round(base_calc * (1.0 / 100.0), 2)  # 1% FCP

            result["difal_aliquota"] = difal_rate
            result["difal_valor"] = difal_val
            result["fcp_valor"] = fcp_val
            result["total_impostos"] = round(result["total_impostos"] + difal_val + fcp_val, 2)

        return result
