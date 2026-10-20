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


class InvoiceCancelRequest(BaseModel):
    reason: str = Field(..., min_length=15, description="Justificativa do cancelamento (mínimo 15 caracteres)")


class InvoiceCceRequest(BaseModel):
    correction_text: str = Field(..., min_length=15, description="Texto da carta de correção")
