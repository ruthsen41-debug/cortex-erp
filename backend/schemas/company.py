from typing import Optional
from pydantic import BaseModel, Field


class CompanyUpdate(BaseModel):
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    inscricao_estadual: Optional[str] = None
    inscricao_municipal: Optional[str] = None
    regime_tributario: Optional[str] = None
    cnae_principal: Optional[str] = None
    aliquota_simples: Optional[float] = None
    cep: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    chave_pix: Optional[str] = None
    ambiente_fiscal: Optional[str] = None
    motor_fiscal: Optional[str] = None
    api_fiscal_token: Optional[str] = None
    serie_nfe: Optional[int] = None
    proximo_numero_nfe: Optional[int] = None
    serie_nfce: Optional[int] = None
    proximo_numero_nfce: Optional[int] = None
    serie_nfse: Optional[int] = None
    proximo_numero_nfse: Optional[int] = None
    csc_id: Optional[str] = None
    csc_token: Optional[str] = None
