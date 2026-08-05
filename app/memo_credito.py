"""Contrato do memo de credito produzido pela Camada 2 (ADR-0003).

Este modulo define a FONTE DE VERDADE do parecer: o agente devolve
estrutura, nunca prosa. A narrativa em texto e RENDERIZADA a partir dos
campos (renderizar_narrativa), o que torna impossivel o texto contradizer
os dados - o juiz binario do ADR-0004 avalia estrutura, nao estilo.

Tres invariantes que o contrato garante por construcao:

1. GROUNDEDNESS (rubrica eliminatoria do ADR-0004): todo fato carrega
   `fonte_tool`. Fato sem fonte nao entra - e o que impede o agente de
   inventar numero.

2. SEPARACAO CLIENTE x CENARIO (condicao de rigor #2 do ADR-0008):
   `fatores_cliente` e `cenario_assumido` sao campos distintos. O cenario
   macro nunca vira atributo do cliente.

3. CEGUEIRA AO SCORE (invariante mais fragil do projeto, ADR-0003 SS2.1):
   nenhum campo carrega p_default. Se o agente enxergar o score, ele
   parafraseia o modelo e o eval passa a medir redacao em vez de
   julgamento. Ha teste automatizado guardando isso.
"""
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# Nomes proibidos em qualquer campo do memo - guarda mecanica da cegueira
# ao score (ADR-0003 SS2.1). Usado pelo teste de cegueira.
TERMOS_PROIBIDOS_SCORE = (
    "p_default", "score", "probabilidade", "pd", "p_hat", "risco_modelo",
    "predicao", "camada1", "p_estrela",
)

# Teto de fatos por memo. NAO e chute: veio de medir importancia por
# permutacao nos 2.780 casos da zona cinzenta (2026-08-05). O sinal la e
# ESPALHADO, nao concentrado - top 3 = 43%, top 8 = 63%, top 15 = 81%.
# Como nao existe "os 3 fatos que explicam tudo", qualquer teto deixa
# informacao na mesa e a escolha vira custo de leitura, nao de sinal:
# dos 8 para os 15 ganha-se 18pp e DOBRA-SE o que o humano precisa ler.
# O modelo ja capturou o sinal; o memo existe para um humano JULGAR.
MAX_FATORES = 8

# Piso: em caso de zona cinzenta ha, por definicao, evidencia conflitante.
# Memo com 1-2 fatos sugere que o agente nao explorou as ferramentas.
# RISCO DECLARADO: piso induz enchimento de linguica. O eval (ADR-0004)
# precisa vigiar fato irrelevante incluido so para bater o minimo.
MIN_FATORES = 3


class Recomendacao(str, Enum):
    """Acao recomendada pelo agente.

    DEFERIR e a acao de *deferral* da literatura de Learning to Defer:
    encaminhar a humano. Exige declarar o que faltou saber - deferir sem
    dizer o que falta nao e decisao, e omissao (ADR-0003 SS2.2).
    """

    APROVAR = "APROVAR"
    NEGAR = "NEGAR"
    DEFERIR = "DEFERIR"


class Peso(str, Enum):
    """Direcao em que o fato empurra a decisao."""

    FAVORAVEL = "favoravel"
    DESFAVORAVEL = "desfavoravel"
    NEUTRO = "neutro"


class FatorCliente(BaseModel):
    """Um fato sobre o cliente, obrigatoriamente rastreavel a uma ferramenta."""

    fato: str = Field(..., min_length=1, description="O achado, em linguagem de negocio")
    fonte_tool: str = Field(
        ..., min_length=1,
        description="Nome da ferramenta de CASO que produziu o fato (groundedness)",
    )
    peso: Peso = Field(..., description="Se o fato favorece ou desfavorece a concessao")

    @field_validator("fato", "fonte_tool")
    @classmethod
    def nao_pode_ser_so_espaco(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("campo obrigatorio nao pode ser vazio ou so espaco")
        return v.strip()


class CenarioAssumido(BaseModel):
    """Premissa macro, vinda da ferramenta de CENARIO (1x por lote, nunca por cliente).

    Fica separado de `fatores_cliente` de proposito: o cenario e uma
    condicao do ambiente, nao uma caracteristica da pessoa (ADR-0008).
    """

    lgd: float = Field(
        ..., gt=0.0, le=1.0,
        description="Perda dado o default assumida no cenario (0-1)",
    )
    fonte: str = Field(..., min_length=1, description="Origem rastreavel da premissa")


class MemoCredito(BaseModel):
    """Parecer estruturado. E isto que o agente devolve - sem narrativa.

    A narrativa NAO e campo de entrada: e gerada por renderizar_narrativa().
    Se o agente escrevesse a prosa, ela poderia contradizer os campos.
    """

    cliente_id: str = Field(..., min_length=1)
    recomendacao: Recomendacao
    fatores_cliente: list[FatorCliente] = Field(
        ..., min_length=MIN_FATORES, max_length=MAX_FATORES,
        description=f"Entre {MIN_FATORES} e {MAX_FATORES} fatos, priorizados por relevancia",
    )
    cenario_assumido: CenarioAssumido
    informacao_faltante: list[str] = Field(
        default_factory=list,
        description="O que o agente nao conseguiu apurar. Obrigatorio se DEFERIR.",
    )

    model_config = {"extra": "forbid"}  # bloqueia campo extra (inclusive score)

    @model_validator(mode="after")
    def deferir_exige_dizer_o_que_falta(self) -> "MemoCredito":
        if self.recomendacao is Recomendacao.DEFERIR and not self.informacao_faltante:
            raise ValueError(
                "DEFERIR exige informacao_faltante nao vazia: deferir sem dizer "
                "o que falta nao e decisao, e omissao (ADR-0003 SS2.2)"
            )
        return self


def renderizar_narrativa(memo: MemoCredito) -> str:
    """Gera o texto do parecer A PARTIR dos campos estruturados.

    Existe para que a prosa nao possa divergir dos dados. Toda linha de
    fato sai com a fonte entre colchetes, entao a auditoria de
    groundedness e visual, nao so programatica.
    """
    simbolo = {Peso.FAVORAVEL: "+", Peso.DESFAVORAVEL: "-", Peso.NEUTRO: "."}

    linhas = [
        f"Cliente:      {memo.cliente_id}",
        f"Recomendacao: {memo.recomendacao.value}",
        "",
        "Fatos que pesaram:",
    ]
    for f in memo.fatores_cliente:
        linhas.append(f"  {simbolo[f.peso]} {f.fato}   [fonte: {f.fonte_tool}]")

    linhas += [
        "",
        "Cenario assumido:",
        f"  Perda em caso de calote: {memo.cenario_assumido.lgd:.0%}"
        f"   [fonte: {memo.cenario_assumido.fonte}]",
    ]

    if memo.informacao_faltante:
        linhas += ["", "O que faltou saber:"]
        linhas += [f"  - {i}" for i in memo.informacao_faltante]

    return "\n".join(linhas)
