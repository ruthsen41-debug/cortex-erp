from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class InvoiceEmitRequest(BaseModel):
    model: str = Field(default="55", description="55 (NF-e), 65 (NFC-e), nfse (NFS-e)")
    recipient_id: Optional[int] = None
    sale_id: Optional[int] = None
    natureza_operacao: Optional[str] = "VENDA DE MERCADORIA DENTRO DO ESTADO"
    items: List[Dict[str, Any]] = []
    total_amount: Optional[float] = 0.0
    company_id: Optional[int] = 1
    # Identificação avançada
    finalidade: Optional[str] = "1"
    tipo_operacao: Optional[str] = "1"
    destino_operacao: Optional[str] = "1"
    ind_presenca: Optional[str] = "1"
    ind_ie_dest: Optional[str] = "9"
    # Frete e pagamento
    modalidade_frete: Optional[str] = "9"
    shipping_amount: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0
    outras_despesas: Optional[float] = 0.0
    forma_pagamento: Optional[str] = "01"
    # Informações adicionais
    informacoes_adicionais: Optional[str] = ""
    informe_fisco: Optional[str] = ""


class InvoiceCancelRequest(BaseModel):
    reason: str = Field(..., min_length=15, description="Justificativa do cancelamento (mínimo 15 caracteres)")


class InvoiceCceRequest(BaseModel):
    correction_text: str = Field(..., min_length=15, description="Texto da carta de correção")
