"""
Provedores de Emissão Fiscal — Cortex ERP
==========================================
Seleção pelo campo `motor_fiscal` no cadastro da empresa:

  sefaz_direct  → Geração local de XML (homologação / sem integração ativa)
  nuvem_fiscal  → Nuvem Fiscal API (OAuth 2.0) — RECOMENDADO, plano gratuito disponível
                  api_fiscal_token = "CLIENT_ID|CLIENT_SECRET"
  focus_nfe     → Focus NFe API (HTTP Basic Auth)
                  api_fiscal_token = "SEU_TOKEN_FOCUSNFE"

Nuvem Fiscal: https://nuvemfiscal.com.br  |  Docs: https://dev.nuvemfiscal.com.br
Focus NFe:    https://focusnfe.com.br     |  Docs: https://doc.focusnfe.com.br
"""

import re
import time
import httpx
from datetime import datetime

try:
    from ..fiscal_engine import gerar_xml_nfe_400
except ImportError:
    from fiscal_engine import gerar_xml_nfe_400


def _digits(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


# Mapeamento forma de pagamento → código NF-e (tPag)
_TPAG = {
    "Pix": "17",
    "Boleto": "15",
    "Dinheiro": "01",
    "Cartão de Crédito": "03",
    "Cartão de Débito": "04",
    "Transferência/TED": "18",
    "Cheque": "02",
}

# Mapeamento status Nuvem Fiscal → status interno
_STATUS_NF = {
    "autorizado": "autorizada",
    "processando": "processando",
    "pendente": "processando",
    "rejeitado": "rejeitada",
    "cancelado": "cancelada",
    "denegado": "cancelada",
    "erro": "rejeitada",
}

# Status Focus NFe → status interno
_STATUS_FOC = {
    "autorizado": "autorizada",
    "processando_autorizacao": "processando",
    "erro_autorizacao": "rejeitada",
    "cancelado": "cancelada",
}


# ── Base ──────────────────────────────────────────────────────────────────────

class FiscalProviderBase:
    async def emit_invoice(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        raise NotImplementedError

    async def cancel_invoice(self, company: dict, invoice: dict, reason: str) -> dict:
        raise NotImplementedError

    async def emit_cce(self, company: dict, invoice: dict, text: str) -> dict:
        raise NotImplementedError

    async def inutilize(self, company: dict, model: str, series: int, start_n: int, end_n: int, reason: str) -> dict:
        raise NotImplementedError

    async def manifest(self, company: dict, access_key: str, event_type: str) -> dict:
        raise NotImplementedError

    async def consult_invoice(self, fiscal_ref: str, model: str = "NFe-55") -> dict:
        raise NotImplementedError


# ── Motor Local (Simulação / Homologação sem integração) ──────────────────────

class SEFAZDirectEngine(FiscalProviderBase):
    """Geração local de XML NF-e 4.00 com protocolo simulado — sem envio real à SEFAZ."""

    async def emit_invoice(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        import random
        xml_str = gerar_xml_nfe_400(company, contact, items, inv_meta)
        protocol = f"151{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10, 99)}"
        return {
            "status": "autorizada",
            "protocol": protocol,
            "access_key": inv_meta["access_key"],
            "xml_content": xml_str,
            "fiscal_ref": "",
            "provider": "sefaz_direct",
            "message": "[SIMULAÇÃO] NF-e autorizada localmente — sem envio real à SEFAZ.",
        }

    async def cancel_invoice(self, company: dict, invoice: dict, reason: str) -> dict:
        import random
        return {
            "status": "cancelada",
            "cancel_protocol": f"135{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10, 99)}",
            "message": "[SIMULAÇÃO] Cancelamento simulado.",
        }

    async def emit_cce(self, company: dict, invoice: dict, text: str) -> dict:
        import random
        return {
            "status": "vinculada",
            "cce_protocol": f"136{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10, 99)}",
            "message": "[SIMULAÇÃO] CC-e simulada.",
        }

    async def inutilize(self, company: dict, model: str, series: int, start_n: int, end_n: int, reason: str) -> dict:
        import random
        return {
            "status": "homologado",
            "protocol": f"102{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10, 99)}",
            "message": "[SIMULAÇÃO] Inutilização simulada.",
        }

    async def manifest(self, company: dict, access_key: str, event_type: str) -> dict:
        import random
        return {
            "status": "registrado",
            "protocol": f"135{datetime.now().strftime('%y%m%d%H%M')}{random.randint(10, 99)}",
            "event_type": event_type,
            "message": "[SIMULAÇÃO] Manifestação simulada.",
        }

    async def consult_invoice(self, fiscal_ref: str, model: str = "NFe-55") -> dict:
        return {"status": "autorizada", "message": "Modo simulação — consulta não aplicável."}


# ── Nuvem Fiscal ──────────────────────────────────────────────────────────────

class NuvemFiscalProvider(FiscalProviderBase):
    """
    Integração real com Nuvem Fiscal API REST (OAuth 2.0 client_credentials).

    Configuração no cadastro da empresa:
      motor_fiscal    = "nuvem_fiscal"
      api_fiscal_token = "CLIENT_ID|CLIENT_SECRET"

    Obtenha as credenciais em: https://app.nuvemfiscal.com.br → Configurações → API
    Plano gratuito: até 50 documentos/mês, 1 CNPJ.
    """

    AUTH_URL = "https://auth.nuvemfiscal.com.br/oauth/token"
    BASE_URL = "https://api.nuvemfiscal.com.br"
    SCOPE = "nfe nfce nfse cte"

    def __init__(self, client_id: str, client_secret: str, env: str = "homologacao"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.env = env  # "homologacao" | "producao"
        self._token = ""
        self._token_exp = 0.0

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _get_token(self) -> str:
        """Obtém access token OAuth com cache e auto-refresh."""
        if self._token and time.monotonic() < self._token_exp:
            return self._token
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self.AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Nuvem Fiscal: falha de autenticação ({resp.status_code}). "
                f"Verifique CLIENT_ID e CLIENT_SECRET em Configurações → Empresa → Motor Fiscal."
            )
        data = resp.json()
        self._token = data["access_token"]
        self._token_exp = time.monotonic() + data.get("expires_in", 3600) - 60
        return self._token

    async def _headers(self) -> dict:
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── Ref ──────────────────────────────────────────────────────────────────

    def _make_ref(self, company: dict, number: int, model: str) -> str:
        prefix = {"NFe-55": "N", "NFCe-65": "C", "NFSe": "S"}.get(model, "N")
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"CTX{company.get('id', 1)}{prefix}{number}T{ts}"

    # ── Payloads ──────────────────────────────────────────────────────────────

    def _build_nfe_payload(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        doc_dest = _digits(contact.get("document", ""))
        uf_emit = company.get("uf", "MT")
        uf_dest = contact.get("state", "MT")

        dest: dict = {
            "nome": contact.get("name", "CONSUMIDOR FINAL"),
            "indicador_inscricao_estadual": (
                "contribuinte" if contact.get("ie_indicator") == "1"
                else "isento" if contact.get("ie_indicator") == "2"
                else "nao_contribuinte"
            ),
            "endereco": {
                "logradouro": contact.get("street", "Rua"),
                "numero": contact.get("number", "S/N"),
                "bairro": contact.get("neighborhood", "Centro"),
                "codigo_municipio": contact.get("ibge_code", "5102504"),
                "nome_municipio": contact.get("city", "Cuiaba"),
                "uf": uf_dest,
                "cep": _digits(contact.get("cep", "78000000")),
                "codigo_pais": "1058",
                "nome_pais": "Brasil",
            },
        }
        if len(doc_dest) == 14:
            dest["cpf_cnpj"] = doc_dest
        elif len(doc_dest) == 11:
            dest["cpf_cnpj"] = doc_dest
        if contact.get("state_registration"):
            dest["inscricao_estadual"] = contact["state_registration"]
        if contact.get("email"):
            dest["email"] = contact["email"]

        nfe_items = []
        for idx, it in enumerate(items, 1):
            cfop = _digits(it.get("cfop") or it.get("cfop_internal", "5102"))
            ncm = _digits(it.get("ncm", "84713012")).zfill(8)[:8]
            qty = float(it.get("quantity", 1))
            unit_price = float(it.get("unit_price", 0))
            discount = float(it.get("discount", 0))
            total = round(float(it.get("total_price") or max(0.0, qty * unit_price - discount)), 2)

            item: dict = {
                "numero_item": idx,
                "codigo_produto": str(it.get("sku") or it.get("product_id", idx)),
                "descricao": it.get("product_name") or it.get("name") or f"Item {idx}",
                "codigo_ncm": ncm,
                "cfop": cfop,
                "unidade_comercial": it.get("unit", "UN"),
                "unidade_tributavel": it.get("unit", "UN"),
                "quantidade_comercial": qty,
                "quantidade_tributavel": qty,
                "valor_unitario_comercial": round(unit_price, 4),
                "valor_unitario_tributavel": round(unit_price, 4),
                "valor_bruto": total,
                "inclui_no_total": 1,
                "icms_origem": int(it.get("origin", 0)),
                "icms_situacao_tributaria": str(it.get("csosn_cst", "102")),
                "pis_situacao_tributaria": str(it.get("pis_cst", "07")),
                "cofins_situacao_tributaria": str(it.get("cofins_cst", "07")),
            }
            if discount:
                item["valor_desconto"] = round(discount, 2)
            if it.get("barcode"):
                item["codigo_barras"] = it["barcode"]

            nfe_items.append(item)

        tpag = _TPAG.get(inv_meta.get("forma_pagamento", "Pix"), "17")
        total_inv = round(float(inv_meta.get("total_invoice", 0)), 2)

        payload: dict = {
            "ambiente": self.env,
            "referencia": inv_meta.get("_fiscal_ref", ""),
            "emitente": {
                "cpf_cnpj": _digits(company.get("cnpj", "")),
                "inscricao_estadual": company.get("inscricao_estadual", ""),
                "inscricao_municipal": company.get("inscricao_municipal", ""),
            },
            "natureza_operacao": inv_meta.get("nature_operation", "VENDA DE MERCADORIA"),
            "data_emissao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
            "tipo_operacao": "saida",
            "finalidade_emissao": "normal",
            "consumidor_final": True,
            "presenca_comprador": "presencial",
            "modalidade_frete": "sem_transporte",
            "destino_operacao": "interna" if uf_emit == uf_dest else "interestadual",
            "destinatario": dest,
            "itens": nfe_items,
            "pagamentos": [{"detalhamento_forma_pagamento": tpag, "valor_pagamento": total_inv}],
        }

        if inv_meta.get("total_discounts"):
            payload["valor_desconto"] = round(float(inv_meta["total_discounts"]), 2)
        if inv_meta.get("total_shipping"):
            payload["valor_frete"] = round(float(inv_meta["total_shipping"]), 2)
        if inv_meta.get("informacoes_adicionais"):
            payload["informacoes_adicionais_contribuinte"] = inv_meta["informacoes_adicionais"]

        return payload

    def _build_nfce_payload(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        tpag = _TPAG.get(inv_meta.get("forma_pagamento", "Pix"), "17")
        total_inv = round(float(inv_meta.get("total_invoice", 0)), 2)

        nfce_items = []
        for idx, it in enumerate(items, 1):
            cfop = _digits(it.get("cfop") or it.get("cfop_internal", "5405"))
            ncm = _digits(it.get("ncm", "84713012")).zfill(8)[:8]
            qty = float(it.get("quantity", 1))
            unit_price = float(it.get("unit_price", 0))
            discount = float(it.get("discount", 0))
            total = round(float(it.get("total_price") or max(0.0, qty * unit_price - discount)), 2)

            item: dict = {
                "numero_item": str(idx),
                "codigo_produto": str(it.get("sku") or it.get("product_id", idx)),
                "descricao": it.get("product_name") or it.get("name") or f"Item {idx}",
                "codigo_ncm": ncm,
                "cfop": cfop,
                "unidade_comercial": it.get("unit", "UN"),
                "unidade_tributavel": it.get("unit", "UN"),
                "quantidade_comercial": qty,
                "quantidade_tributavel": qty,
                "valor_unitario_comercial": round(unit_price, 4),
                "valor_unitario_tributavel": round(unit_price, 4),
                "valor_bruto": total,
                "icms_origem": int(it.get("origin", 0)),
                "icms_situacao_tributaria": str(it.get("csosn_cst", "102")),
            }
            if discount:
                item["valor_desconto"] = round(discount, 2)
            nfce_items.append(item)

        payload: dict = {
            "ambiente": self.env,
            "referencia": inv_meta.get("_fiscal_ref", ""),
            "emitente": {"cpf_cnpj": _digits(company.get("cnpj", ""))},
            "presenca_comprador": "presencial",
            "modalidade_frete": "sem_transporte",
            "itens": nfce_items,
            "pagamentos": [{"detalhamento_forma_pagamento": tpag, "valor_pagamento": total_inv}],
        }

        # Destinatário opcional na NFC-e
        doc_dest = _digits(contact.get("document", ""))
        if len(doc_dest) in (11, 14):
            payload["destinatario"] = {
                "cpf_cnpj": doc_dest,
                "nome": contact.get("name", ""),
            }

        return payload

    def _build_nfse_payload(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        total_services = round(sum(
            float(it.get("total_price") or (float(it.get("quantity", 1)) * float(it.get("unit_price", 0))))
            for it in items
        ), 2)

        service_code = None
        discriminacao_parts = []
        for it in items:
            sc = it.get("service_code_lc116", "01.07")
            if sc and not service_code:
                service_code = sc
            discriminacao_parts.append(
                f"{it.get('product_name', 'Serviço')} — "
                f"Qtd: {it.get('quantity', 1)} x R${float(it.get('unit_price', 0)):.2f}"
            )
        discriminacao = "; ".join(discriminacao_parts) or "Prestação de Serviços"

        doc_dest = _digits(contact.get("document", ""))
        tomador: dict = {
            "razao_social": contact.get("name", ""),
            "email": contact.get("email", ""),
            "endereco": {
                "logradouro": contact.get("street", ""),
                "numero": contact.get("number", "S/N"),
                "bairro": contact.get("neighborhood", ""),
                "codigo_municipio": contact.get("ibge_code", "5103403"),
                "nome_municipio": contact.get("city", ""),
                "uf": contact.get("state", "MT"),
                "cep": _digits(contact.get("cep", "")),
            },
        }
        if len(doc_dest) == 14:
            tomador["cpf_cnpj"] = doc_dest
        elif len(doc_dest) == 11:
            tomador["cpf_cnpj"] = doc_dest

        iss_rate = float(items[0].get("iss_rate", 3.0)) / 100 if items else 0.03
        iss_retido = bool(items[0].get("iss_retained", False)) if items else False

        return {
            "ambiente": self.env,
            "referencia": inv_meta.get("_fiscal_ref", ""),
            "prestador": {
                "cpf_cnpj": _digits(company.get("cnpj", "")),
                "inscricao_municipal": company.get("inscricao_municipal", ""),
                "codigo_municipio": company.get("codigo_ibge_municipio", "5102504"),
            },
            "tomador": tomador,
            "servico": {
                "valor_servicos": total_services,
                "iss_retido": iss_retido,
                "item_lista_servico": service_code or "01.07",
                "discriminacao": discriminacao[:2000],
                "codigo_municipio": company.get("codigo_ibge_municipio", "5102504"),
                "aliquota": iss_rate,
            },
        }

    # ── Helpers de resposta ───────────────────────────────────────────────────

    def _parse_emit_response(self, resp: httpx.Response, fiscal_ref: str, inv_meta: dict) -> dict:
        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        status_api = data.get("status", "")
        db_status = _STATUS_NF.get(status_api, "processando")

        if resp.status_code in (200, 201) and status_api in ("autorizado", "processando", "pendente"):
            return {
                "status": db_status,
                "protocol": data.get("protocolo", data.get("numero_protocolo", "")),
                "access_key": data.get("chave_acesso", data.get("chave_nfe", inv_meta.get("access_key", ""))),
                "xml_content": data.get("xml", data.get("link_xml", "")),
                "danfe_url": data.get("link_danfe", data.get("danfe_url", "")),
                "provider": "nuvem_fiscal",
                "fiscal_ref": fiscal_ref,
                "message": data.get("mensagem", f"NF-e {db_status} pela Nuvem Fiscal."),
            }

        if resp.status_code in (200, 201) and status_api in ("rejeitado", "erro"):
            erros = data.get("erros", [])
            msg = data.get("mensagem", "Rejeição pela SEFAZ")
            if erros:
                msg = " | ".join(
                    (e.get("mensagem") or e.get("message") or str(e)) for e in erros if e
                )
            return {
                "status": "rejeitada",
                "protocol": "",
                "access_key": inv_meta.get("access_key", ""),
                "xml_content": "",
                "provider": "nuvem_fiscal",
                "fiscal_ref": fiscal_ref,
                "message": msg,
                "error": msg,
            }

        # Erros 400/422/500
        codigo = data.get("codigo", data.get("type", ""))
        mensagem = data.get("mensagem", data.get("message", f"Erro HTTP {resp.status_code}"))
        erros = data.get("erros", [])
        if erros:
            detalhes = " | ".join(
                f"{e.get('campo', e.get('field', ''))}: {e.get('mensagem', e.get('message', ''))}"
                for e in erros if e
            )
            mensagem = f"{mensagem} | {detalhes}"

        return {
            "status": "erro",
            "protocol": "",
            "access_key": inv_meta.get("access_key", ""),
            "xml_content": "",
            "provider": "nuvem_fiscal",
            "fiscal_ref": fiscal_ref,
            "message": mensagem,
            "error_code": codigo,
            "http_status": resp.status_code,
            "error": mensagem,
        }

    # ── Operações principais ──────────────────────────────────────────────────

    async def emit_invoice(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        if not self.client_id or not self.client_secret:
            engine = SEFAZDirectEngine()
            res = await engine.emit_invoice(company, contact, items, inv_meta)
            res["provider"] = "nuvem_fiscal_simulado"
            res["message"] = (
                "⚠ Configure CLIENT_ID e CLIENT_SECRET da Nuvem Fiscal no cadastro da empresa "
                "(campo Motor Fiscal → Nuvem Fiscal, token = CLIENT_ID|CLIENT_SECRET)."
            )
            return res

        model = inv_meta.get("model", "NFe-55")
        fiscal_ref = self._make_ref(company, inv_meta["number"], model)
        inv_meta["_fiscal_ref"] = fiscal_ref

        if model == "NFe-55":
            endpoint = f"{self.BASE_URL}/nfe"
            payload = self._build_nfe_payload(company, contact, items, inv_meta)
        elif model == "NFCe-65":
            endpoint = f"{self.BASE_URL}/nfce"
            payload = self._build_nfce_payload(company, contact, items, inv_meta)
        else:
            endpoint = f"{self.BASE_URL}/nfse"
            payload = self._build_nfse_payload(company, contact, items, inv_meta)

        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(endpoint, headers=headers, json=payload)
        except RuntimeError as e:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "nuvem_fiscal", "fiscal_ref": fiscal_ref,
                    "message": str(e), "error": str(e)}
        except httpx.TimeoutException:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "nuvem_fiscal", "fiscal_ref": fiscal_ref,
                    "message": "Timeout na comunicação com Nuvem Fiscal. Tente novamente.", "error": "timeout"}
        except Exception as e:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "nuvem_fiscal", "fiscal_ref": fiscal_ref,
                    "message": f"Erro de conexão com Nuvem Fiscal: {e}", "error": str(e)}

        return self._parse_emit_response(resp, fiscal_ref, inv_meta)

    async def consult_invoice(self, fiscal_ref: str, model: str = "NFe-55") -> dict:
        """Consulta o status atual de uma nota pendente na Nuvem Fiscal."""
        ep_map = {"NFe-55": "nfe", "NFCe-65": "nfce", "NFSe": "nfse"}
        ep = ep_map.get(model, "nfe")
        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(f"{self.BASE_URL}/{ep}/{fiscal_ref}", headers=headers)
        except Exception as e:
            return {"status": "erro", "message": str(e)}

        if resp.status_code == 404:
            return {"status": "nao_encontrado", "message": "Referência não encontrada na Nuvem Fiscal."}

        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        status_api = data.get("status", "processando")
        db_status = _STATUS_NF.get(status_api, "processando")

        if db_status == "autorizada":
            return {
                "status": "autorizada",
                "protocol": data.get("protocolo", data.get("numero_protocolo", "")),
                "access_key": data.get("chave_acesso", data.get("chave_nfe", "")),
                "xml_url": data.get("link_xml", data.get("xml", "")),
                "danfe_url": data.get("link_danfe", ""),
                "message": data.get("mensagem", "Autorizado pela SEFAZ"),
            }
        elif db_status == "rejeitada":
            erros = data.get("erros", [])
            msg = data.get("mensagem", "Rejeição SEFAZ")
            if erros:
                msg = " | ".join((e.get("mensagem") or str(e)) for e in erros)
            return {"status": "rejeitada", "message": msg}

        return {"status": db_status, "message": data.get("mensagem", "Ainda em processamento.")}

    async def cancel_invoice(self, company: dict, invoice: dict, reason: str) -> dict:
        if not self.client_id:
            return await SEFAZDirectEngine().cancel_invoice(company, invoice, reason)

        fiscal_ref = invoice.get("fiscal_ref", "")
        if not fiscal_ref:
            return {"status": "erro", "message": "Referência Nuvem Fiscal não encontrada. Só é possível cancelar notas emitidas com a integração ativa."}

        model = invoice.get("model", "NFe-55")
        ep = "nfce" if "65" in model else ("nfse" if "NFSe" in model else "nfe")
        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.delete(
                    f"{self.BASE_URL}/{ep}/{fiscal_ref}",
                    headers=headers,
                    json={"justificativa": reason},
                )
        except Exception as e:
            return {"status": "erro", "message": str(e)}

        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        if resp.status_code in (200, 201):
            status_api = data.get("status", "cancelado")
            return {
                "status": "cancelada" if "cancelad" in status_api else "erro",
                "cancel_protocol": data.get("protocolo", data.get("numero_protocolo", "")),
                "message": data.get("mensagem", "Cancelamento processado."),
            }
        return {"status": "erro", "message": data.get("mensagem", f"Erro HTTP {resp.status_code}")}

    async def emit_cce(self, company: dict, invoice: dict, text: str) -> dict:
        if not self.client_id:
            return await SEFAZDirectEngine().emit_cce(company, invoice, text)

        fiscal_ref = invoice.get("fiscal_ref", "")
        if not fiscal_ref:
            return {"status": "erro", "message": "Referência Nuvem Fiscal não encontrada para CC-e."}

        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/nfe/{fiscal_ref}/carta-correcao",
                    headers=headers,
                    json={"correcao": text},
                )
        except Exception as e:
            return {"status": "erro", "message": str(e)}

        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        if resp.status_code in (200, 201):
            return {
                "status": "vinculada",
                "cce_protocol": data.get("protocolo", data.get("numero_protocolo", "")),
                "message": data.get("mensagem", "CC-e emitida com sucesso."),
            }
        return {"status": "erro", "message": data.get("mensagem", f"Erro HTTP {resp.status_code}")}

    async def inutilize(self, company: dict, model: str, series: int, start_n: int, end_n: int, reason: str) -> dict:
        if not self.client_id:
            return await SEFAZDirectEngine().inutilize(company, model, series, start_n, end_n, reason)

        cnpj = _digits(company.get("cnpj", ""))
        ano = datetime.now().year
        ep = "nfce" if "65" in model else "nfe"
        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/{ep}/inutilizacoes",
                    headers=headers,
                    json={
                        "ambiente": self.env,
                        "emitente": {"cpf_cnpj": cnpj},
                        "numero_serie": series,
                        "numero_inicial": start_n,
                        "numero_final": end_n,
                        "justificativa": reason,
                    },
                )
        except Exception as e:
            return {"status": "erro", "message": str(e)}

        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        if resp.status_code in (200, 201):
            return {
                "status": "homologado",
                "protocol": data.get("protocolo", data.get("numero_protocolo", "")),
                "message": data.get("mensagem", "Inutilização homologada."),
            }
        return {"status": "erro", "message": data.get("mensagem", f"Erro HTTP {resp.status_code}")}

    async def manifest(self, company: dict, access_key: str, event_type: str) -> dict:
        if not self.client_id:
            return await SEFAZDirectEngine().manifest(company, access_key, event_type)

        tipo_map = {
            "ciencia": "ciencia_emissao",
            "confirmacao": "confirmacao_operacao",
            "desconhecimento": "desconhecimento_operacao",
            "nao_realizada": "operacao_nao_realizada",
        }
        try:
            headers = await self._headers()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/nfe/{access_key}/manifesto-destinatario",
                    headers=headers,
                    json={"tipo": tipo_map.get(event_type, event_type)},
                )
        except Exception as e:
            return {"status": "erro", "message": str(e)}

        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        if resp.status_code in (200, 201):
            return {
                "status": "registrado",
                "protocol": data.get("protocolo", ""),
                "event_type": event_type,
                "message": data.get("mensagem", "Manifestação registrada."),
            }
        return {"status": "erro", "message": data.get("mensagem", f"Erro HTTP {resp.status_code}")}


# ── Focus NFe ─────────────────────────────────────────────────────────────────

class FocusNFeProvider(FiscalProviderBase):
    """
    Integração com Focus NFe API (HTTP Basic Auth).
    Configuração: motor_fiscal = "focus_nfe", api_fiscal_token = "SEU_TOKEN"
    Docs: https://doc.focusnfe.com.br
    """

    def __init__(self, token: str, env: str = "homologacao"):
        self.token = token
        self.base_url = (
            "https://api.focusnfe.com.br/v2"
            if env == "producao"
            else "https://homologacao.focusnfe.com.br/v2"
        )

    def _make_ref(self, company: dict, number: int, model: str) -> str:
        prefix = {"NFe-55": "N", "NFCe-65": "C", "NFSe": "S"}.get(model, "N")
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"CTX{company.get('id', 1)}{prefix}{number}T{ts}"

    async def emit_invoice(self, company: dict, contact: dict, items: list, inv_meta: dict) -> dict:
        if not self.token:
            engine = SEFAZDirectEngine()
            res = await engine.emit_invoice(company, contact, items, inv_meta)
            res["provider"] = "focus_nfe_simulado"
            return res

        model = inv_meta.get("model", "NFe-55")
        fiscal_ref = self._make_ref(company, inv_meta["number"], model)
        ep = "nfe" if "55" in model else ("nfce" if "65" in model else "nfse")

        payload: dict = {
            "natureza_operacao": inv_meta.get("nature_operation", "VENDA DE MERCADORIA"),
            "data_emissao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
            "tipo_documento": 1,
            "finalidade_emissao": int(inv_meta.get("finalidade", 1)),
            "consumidor_final": 1,
            "presenca_comprador": int(inv_meta.get("ind_presenca", 1)),
            "modalidade_frete": int(inv_meta.get("modalidade_frete", 9)),
            "cnpj_emitente": _digits(company.get("cnpj", "")),
        }

        doc_dest = _digits(contact.get("document", ""))
        if len(doc_dest) == 14:
            payload["cnpj_destinatario"] = doc_dest
        elif len(doc_dest) == 11:
            payload["cpf_destinatario"] = doc_dest

        payload.update({
            "nome_destinatario": contact.get("name", "CONSUMIDOR FINAL"),
            "logradouro_destinatario": contact.get("street", "Rua"),
            "numero_destinatario": contact.get("number", "S/N"),
            "bairro_destinatario": contact.get("neighborhood", "Centro"),
            "municipio_destinatario": contact.get("city", "Cuiaba"),
            "uf_destinatario": contact.get("state", "MT"),
            "cep_destinatario": _digits(contact.get("cep", "78000000")),
            "indicador_inscricao_estadual_destinatario": contact.get("ie_indicator", "9"),
        })

        payload["items"] = []
        for idx, it in enumerate(items, 1):
            cfop = _digits(it.get("cfop") or it.get("cfop_internal", "5102"))
            ncm = _digits(it.get("ncm", "84713012")).zfill(8)[:8]
            qty = float(it.get("quantity", 1))
            unit_price = float(it.get("unit_price", 0))
            discount = float(it.get("discount", 0))
            total = round(float(it.get("total_price") or max(0.0, qty * unit_price - discount)), 2)
            item_d: dict = {
                "numero_item": idx,
                "codigo_produto": str(it.get("sku") or it.get("product_id", idx)),
                "descricao": it.get("product_name") or it.get("name") or f"Item {idx}",
                "codigo_ncm": ncm,
                "cfop": cfop,
                "unidade_comercial": it.get("unit", "UN"),
                "quantidade_comercial": float(it.get("quantity", 1)),
                "quantidade_tributavel": float(it.get("quantity", 1)),
                "valor_unitario_comercial": float(it.get("unit_price", 0)),
                "valor_unitario_tributavel": float(it.get("unit_price", 0)),
                "valor_bruto": total,
                "inclui_no_total": 1,
                "icms_origem": str(it.get("origin", "0")),
                "icms_situacao_tributaria": str(it.get("csosn_cst", "102")),
                "pis_situacao_tributaria": str(it.get("pis_cst", "07")),
                "cofins_situacao_tributaria": str(it.get("cofins_cst", "07")),
            }
            if discount:
                item_d["valor_desconto"] = round(discount, 2)
            payload["items"].append(item_d)

        tpag = _TPAG.get(inv_meta.get("forma_pagamento", "Pix"), "17")
        payload["formas_pagamento"] = [{"forma_pagamento": tpag, "valor_pagamento": round(float(inv_meta.get("total_invoice", 0)), 2)}]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/{ep}?ref={fiscal_ref}",
                    auth=(self.token, ""),
                    json=payload,
                )
        except httpx.TimeoutException:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "focus_nfe", "fiscal_ref": fiscal_ref,
                    "message": "Timeout na comunicação com Focus NFe.", "error": "timeout"}
        except Exception as e:
            return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "focus_nfe", "fiscal_ref": fiscal_ref,
                    "message": f"Erro de conexão: {e}", "error": str(e)}

        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        if resp.status_code == 202:
            return {"status": "processando", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "focus_nfe", "fiscal_ref": fiscal_ref,
                    "message": "NF-e enviada e aguardando processamento pela SEFAZ."}

        if resp.status_code == 201:
            status_api = data.get("status", "autorizado")
            db_status = _STATUS_FOC.get(status_api, "processando")
            if db_status == "autorizada":
                return {
                    "status": "autorizada",
                    "protocol": data.get("protocolo", ""),
                    "access_key": data.get("chave_nfe", inv_meta.get("access_key", "")),
                    "xml_content": data.get("caminho_xml_nota_fiscal", ""),
                    "provider": "focus_nfe",
                    "fiscal_ref": fiscal_ref,
                    "message": data.get("mensagem_sefaz", "Autorizado pela SEFAZ"),
                }
            erros = data.get("erros", [])
            msg = data.get("mensagem_sefaz", "Rejeição SEFAZ")
            if erros:
                msg = " | ".join(e.get("mensagem", "") for e in erros if e.get("mensagem"))
            return {"status": db_status, "protocol": "", "access_key": inv_meta.get("access_key", ""),
                    "xml_content": "", "provider": "focus_nfe", "fiscal_ref": fiscal_ref,
                    "message": msg, "error": msg}

        codigo = data.get("codigo", "")
        mensagem = data.get("mensagem", f"Erro HTTP {resp.status_code}")
        return {"status": "erro", "protocol": "", "access_key": inv_meta.get("access_key", ""),
                "xml_content": "", "provider": "focus_nfe", "fiscal_ref": fiscal_ref,
                "message": mensagem, "error_code": codigo}

    async def consult_invoice(self, fiscal_ref: str, model: str = "NFe-55") -> dict:
        ep = "nfce" if "65" in model else ("nfse" if "NFSe" in model else "nfe")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(f"{self.base_url}/{ep}/{fiscal_ref}?completa=1", auth=(self.token, ""))
        except Exception as e:
            return {"status": "erro", "message": str(e)}

        if resp.status_code == 404:
            return {"status": "nao_encontrado", "message": "Referência não encontrada."}

        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass

        status_api = data.get("status", "processando_autorizacao")
        db_status = _STATUS_FOC.get(status_api, "processando")

        if db_status == "autorizada":
            return {
                "status": "autorizada",
                "protocol": data.get("protocolo", ""),
                "access_key": data.get("chave_nfe", ""),
                "xml_url": data.get("caminho_xml_nota_fiscal", ""),
                "danfe_url": data.get("caminho_danfe", ""),
                "message": data.get("mensagem_sefaz", "Autorizado"),
            }
        if db_status == "rejeitada":
            erros = data.get("erros", [])
            msg = data.get("mensagem_sefaz", "Rejeição")
            if erros:
                msg = " | ".join(e.get("mensagem", "") for e in erros)
            return {"status": "rejeitada", "message": msg}

        return {"status": db_status, "message": "Em processamento."}

    async def cancel_invoice(self, company: dict, invoice: dict, reason: str) -> dict:
        fiscal_ref = invoice.get("fiscal_ref", "")
        if not self.token or not fiscal_ref:
            return await SEFAZDirectEngine().cancel_invoice(company, invoice, reason)
        model = invoice.get("model", "NFe-55")
        ep = "nfce" if "65" in model else ("nfse" if "NFSe" in model else "nfe")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.delete(f"{self.base_url}/{ep}/{fiscal_ref}",
                                           auth=(self.token, ""), json={"justificativa": reason})
        except Exception as e:
            return {"status": "erro", "message": str(e)}
        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass
        if resp.status_code == 200:
            return {"status": "cancelada", "cancel_protocol": data.get("protocolo_cancelamento", ""),
                    "message": data.get("mensagem_sefaz", "Cancelado.")}
        return {"status": "erro", "message": data.get("mensagem", f"HTTP {resp.status_code}")}

    async def emit_cce(self, company: dict, invoice: dict, text: str) -> dict:
        fiscal_ref = invoice.get("fiscal_ref", "")
        if not self.token or not fiscal_ref:
            return await SEFAZDirectEngine().emit_cce(company, invoice, text)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(f"{self.base_url}/nfe/{fiscal_ref}/carta_correcao",
                                         auth=(self.token, ""), json={"correcao": text})
        except Exception as e:
            return {"status": "erro", "message": str(e)}
        data: dict = {}
        try:
            data = resp.json()
        except Exception:
            pass
        if resp.status_code in (200, 201):
            return {"status": "vinculada", "cce_protocol": data.get("protocolo", ""),
                    "message": data.get("mensagem_sefaz", "CC-e emitida.")}
        return {"status": "erro", "message": data.get("mensagem", f"HTTP {resp.status_code}")}

    async def inutilize(self, company: dict, model: str, series: int, start_n: int, end_n: int, reason: str) -> dict:
        return await SEFAZDirectEngine().inutilize(company, model, series, start_n, end_n, reason)

    async def manifest(self, company: dict, access_key: str, event_type: str) -> dict:
        return await SEFAZDirectEngine().manifest(company, access_key, event_type)


# ── PlugNotas (stub — mantido para compatibilidade) ────────────────────────────

class PlugNotasProvider(NuvemFiscalProvider):
    """PlugNotas não está implementado — redireciona para Nuvem Fiscal ou simulação."""
    def __init__(self, token: str, env: str = "homologacao"):
        super().__init__(client_id="", client_secret="", env=env)


# ── Factory ───────────────────────────────────────────────────────────────────

class FiscalProviderFactory:
    @staticmethod
    def get_provider(company: dict) -> FiscalProviderBase:
        motor = (company.get("motor_fiscal") or "sefaz_direct").lower()
        token = (company.get("api_fiscal_token") or "").strip()
        env = (company.get("ambiente_fiscal") or "homologacao").lower()

        if "sefaz_real" in motor or motor == "sefaz_direto_real":
            try:
                from .sefaz_direct_real import SEFAZDirectRealEngine
            except ImportError:
                from sefaz_direct_real import SEFAZDirectRealEngine
            return SEFAZDirectRealEngine()

        if "nuvem" in motor:
            # token formato: "CLIENT_ID|CLIENT_SECRET"
            parts = token.split("|", 1)
            client_id = parts[0].strip()
            client_secret = parts[1].strip() if len(parts) > 1 else ""
            return NuvemFiscalProvider(client_id=client_id, client_secret=client_secret, env=env)

        if "focus" in motor:
            return FocusNFeProvider(token=token, env=env)

        if "plug" in motor:
            return PlugNotasProvider(token=token, env=env)

        return SEFAZDirectEngine()
