from pydantic import BaseModel, Field

class CreditRequest(BaseModel):
    idade: int = Field(..., ge=18, le=100, description="Idade do cliente")
    renda_mensal: float = Field(..., ge=0.0, description="Renda mensal em R$")
    tempo_emprego_anos: float = Field(..., ge=0.0, description="Tempo de emprego atual em anos")
    autonomo: str = Field(..., description="'Sim' ou 'Não'")
    score_credito: int = Field(..., ge=0, le=1000, description="Score de crédito do cliente")
    valor_solicitado: float = Field(..., ge=0.0, description="Valor do empréstimo solicitado")
    prazo_meses: int = Field(..., ge=1, le=72, description="Prazo em meses")
    juros_mensal_pct: float = Field(..., ge=0.0, description="Taxa de juros mensal (%)")
    tipo_produto: str = Field(..., description="BNPL, Cartão ou Empréstimo Pessoal")
    
    qtde_cartoes: int = Field(..., ge=0, description="Quantidade de cartões de crédito")
    qtde_contratos_abertos: int = Field(..., ge=0, description="Quantidade de contratos de crédito ativos")
    utilizacao_credito_pct: float = Field(..., ge=0.0, le=100.0, description="Utilização do limite de crédito (%)")
    inadimplencias_anteriores: int = Field(..., ge=0, description="Número de inadimplências passadas")
    dias_atraso_max_12m: int = Field(..., ge=0, description="Máximo de dias em atraso nos últimos 12 meses")
    reclamacoes_6m: int = Field(..., ge=0, description="Número de reclamações nos últimos 6 meses")
    possui_avalista: str = Field(..., description="'Sim' ou 'Não'")
    
    canal_aquisicao: str = Field(..., description="App, Loja, Parceiro, Site")
    regiao: str = Field(..., description="Centro-Oeste, Nordeste, Norte, Sudeste, Sul")

class CreditResponse(BaseModel):
    probabilidade_inadimplencia: float
    decisao_sugerida: str
    comprometimento_renda_pct: float
    mensagem_alerta: str
