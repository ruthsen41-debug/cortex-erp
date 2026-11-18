from typing import Optional
from pydantic import BaseModel, Field


class EmployeeFicha(BaseModel):
    """Campos complementares da ficha do empregado (padrão Domínio / S-2200)."""
    # Pessoais
    nome_social: Optional[str] = None
    estado_civil: Optional[str] = None      # 1 solteiro 2 casado 3 divorciado 4 separado 5 viúvo 6 união estável
    raca_cor: Optional[str] = None          # 1 branca 2 preta 3 parda 4 amarela 5 indígena 6 não informado
    grau_instrucao: Optional[str] = None    # tabela eSocial 01..12
    nacionalidade: Optional[str] = None
    pais_nascimento: Optional[str] = None
    naturalidade: Optional[str] = None
    uf_nascimento: Optional[str] = None
    cod_municipio_nasc: Optional[str] = None
    nome_mae: Optional[str] = None
    nome_pai: Optional[str] = None
    deficiencia: Optional[str] = None
    celular: Optional[str] = None
    tipo_sanguineo: Optional[str] = None
    # Documentos
    rg_orgao: Optional[str] = None
    rg_uf: Optional[str] = None
    rg_emissao: Optional[str] = None
    ctps_serie: Optional[str] = None
    ctps_uf: Optional[str] = None
    ctps_emissao: Optional[str] = None
    titulo_eleitor: Optional[str] = None
    titulo_zona: Optional[str] = None
    titulo_secao: Optional[str] = None
    cnh: Optional[str] = None
    cnh_categoria: Optional[str] = None
    cnh_validade: Optional[str] = None
    cnh_uf: Optional[str] = None
    reservista: Optional[str] = None
    conselho_classe: Optional[str] = None
    conselho_numero: Optional[str] = None
    conselho_uf: Optional[str] = None
    # Endereço
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None
    cod_municipio: Optional[str] = None
    # Contrato
    tipo_admissao: Optional[str] = None
    ind_admissao: Optional[str] = None
    tipo_contrato: Optional[str] = None     # indeterminado | determinado | experiencia | intermitente
    data_termino_contrato: Optional[str] = None
    experiencia_dias: Optional[int] = Field(default=None, ge=0, le=90)
    experiencia_prorrogacao: Optional[int] = Field(default=None, ge=0, le=90)
    primeiro_emprego: Optional[int] = None
    regime_previdenciario: Optional[str] = None
    centro_custo: Optional[str] = None
    funcao: Optional[str] = None
    local_trabalho: Optional[str] = None
    sindicato_nome: Optional[str] = None
    sindicato_cnpj: Optional[str] = None
    data_base_mes: Optional[str] = None
    contribuicao_sindical: Optional[int] = None
    # Salário e jornada
    tipo_salario: Optional[str] = None      # undSalFixo: 1 hora 2 dia 3 semana 4 quinzena 5 mês 6 tarefa 7 só variável
    categoria_especial: Optional[str] = Field(default=None, pattern="^(|professor)$")
    aulas_semanais: Optional[float] = Field(default=None, ge=0, le=80)
    cct_id: Optional[int] = Field(default=None, ge=0)   # 0 = automático (a única convenção vigente)
    forma_pagamento: Optional[str] = None
    adiantamento_pct: Optional[float] = Field(default=None, ge=0, le=100)
    jornada_tipo: Optional[str] = None
    horas_semana: Optional[float] = Field(default=None, gt=0, le=60)
    escala: Optional[str] = None
    horario_entrada: Optional[str] = None
    horario_saida: Optional[str] = None
    intervalo_inicio: Optional[str] = None
    intervalo_fim: Optional[str] = None
    descricao_jornada: Optional[str] = None
    insalubridade_grau: Optional[str] = None  # '', minimo, medio, maximo
    periculosidade: Optional[int] = None
    filhos_sal_familia: Optional[int] = None
    # Bancário / PIX
    bank_code: Optional[str] = None
    bank_account_type: Optional[str] = None
    pix_tipo: Optional[str] = None
    pix_chave: Optional[str] = None
    # Saúde ocupacional / FGTS
    aso_admissional_data: Optional[str] = None
    aso_resultado: Optional[str] = None
    fgts_aniversario: Optional[int] = None
    fgts_opcao_data: Optional[str] = None


class EmployeeCreate(EmployeeFicha):
    name: str
    cpf: str
    rg: Optional[str] = ""
    pis_pasep: Optional[str] = ""
    ctps: Optional[str] = ""
    birth_date: Optional[str] = None
    sexo: Optional[str] = "M"
    admission_date: str
    role: str
    cbo: Optional[str] = "111105"
    department: Optional[str] = ""
    salary: float = Field(..., ge=0)   # zero só para remuneração variável (tipo_salario 6 ou 7)
    is_prolabore: Optional[bool] = False
    dependents: int = Field(default=0, ge=0)
    vt_monthly: Optional[float] = 0.0
    esocial_category: Optional[str] = "101"  # 101=CLT
    bank_name: Optional[str] = ""
    bank_agency: Optional[str] = ""
    bank_account: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    cep: Optional[str] = ""
    address: Optional[str] = ""
    matricula: Optional[str] = ""
    notes: Optional[str] = ""
    company_id: Optional[int] = 1


class EmployeeUpdate(EmployeeFicha):
    name: Optional[str] = None
    cpf: Optional[str] = None
    rg: Optional[str] = None
    pis_pasep: Optional[str] = None
    ctps: Optional[str] = None
    birth_date: Optional[str] = None
    sexo: Optional[str] = None
    admission_date: Optional[str] = None
    role: Optional[str] = None
    cbo: Optional[str] = None
    department: Optional[str] = None
    salary: Optional[float] = Field(default=None, ge=0)
    dependents: Optional[int] = Field(default=None, ge=0)
    vt_monthly: Optional[float] = None
    is_prolabore: Optional[bool] = None
    esocial_category: Optional[str] = None
    bank_name: Optional[str] = None
    bank_agency: Optional[str] = None
    bank_account: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cep: Optional[str] = None
    address: Optional[str] = None
    matricula: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class EmployeeDependent(BaseModel):
    nome: str = Field(..., min_length=2)
    cpf: Optional[str] = ""
    data_nascimento: Optional[str] = ""
    parentesco: Optional[str] = "03"   # tpDep eSocial: 01 cônjuge 02 companheiro 03 filho/enteado 04 universitário 06 irmão/neto 09 pais 99 agregado
    sexo: Optional[str] = ""
    irrf: Optional[int] = 1
    salario_familia: Optional[int] = 0
    plano_saude: Optional[int] = 0


class PayrollRunCreate(BaseModel):
    competence: str = Field(..., description="YYYY-MM", pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    company_id: Optional[int] = 1
    pagar_horas_extras: bool = True  # False = horas extras vão para o banco de horas


class PayrollItemOverride(BaseModel):
    employee_id: int
    extra_earnings: Optional[float] = 0.0
    extra_discounts: Optional[float] = 0.0
    notes: Optional[str] = ""


class TerminationRequest(BaseModel):
    termination_date: str
    termination_type: str = "sem_justa_causa"
    # sem_justa_causa | com_justa_causa | pedido_demissao
    motivo_esocial: Optional[str] = "03"
    # 01=aposentadoria 02=pedido demissão 03=dispensa s/jc 04=dispensa c/jc
