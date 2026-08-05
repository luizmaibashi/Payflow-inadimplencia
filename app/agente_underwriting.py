"""Camada 2 — agente de underwriting (ADR-0003, ADR-0007).

Recebe um `SK_ID_CURR`, decide QUAIS ferramentas chamar e em que ordem, e
devolve um `MemoCredito` validado. Nada de LLM aqui dentro: o cliente e
INJETADO. Duas razoes, e nenhuma delas e falta de chave de API:

1. A orquestracao (limite de chamadas, cegueira ao score, groundedness)
   e logica deterministica e precisa de teste deterministico. Amarrar isso
   a uma resposta nao-deterministica de LLM tornaria a suite inutil.
2. Trocar de modelo nao pode exigir reescrever a Camada 2.

INVARIANTE MAIS FRAGIL DO PROJETO (ADR-0003 SS2.1): o agente **nunca** ve
`p_default`. A prevencao aqui e ESTRUTURAL, nao por disciplina - as funcoes
que montam contexto so aceitam `sk_id_curr`, entao nao ha por onde o score
entrar. Ha teste que serializa o contexto inteiro e procura o valor.

Vazamento pela FILA tambem conta: se os casos chegarem ordenados por risco,
a posicao na fila vira o score. Por isso `preparar_lote` embaralha.
"""
import random
from dataclasses import dataclass, field
from typing import Protocol

from app.ferramenta_cenario import CenarioMacro
from app.ferramentas_caso import ChamadaFerramenta, FerramentasCaso
from app.memo_credito import MAX_FATORES, MIN_FATORES, MemoCredito

# Teto de chamadas por caso (ADR-0007: "o agente pode entrar em loop de
# exploracao; exige teto"). Sao 3 ferramentas de caso; 6 permite reconsulta
# pontual sem virar exploracao infinita.
MAX_CHAMADAS_POR_CASO = 6

FERRAMENTAS_DISPONIVEIS = {
    "consultar_bureau":
        "Credito do cliente em OUTRAS instituicoes: quantos contratos, quantos "
        "ativos, quantos vencidos hoje, quanto do limite ja usou. Devolve "
        "tem_historico_mensal, que diz se vale chamar consultar_historico_bureau.",
    "consultar_historico_bureau":
        "Comportamento mes a mes nos contratos de outras instituicoes: meses em "
        "dia, em atraso e SEM INFORMACAO, pior severidade e ha quantos meses foi "
        "o ultimo atraso. So faz sentido se consultar_bureau indicou historico.",
    "consultar_pagamentos":
        "Como o cliente pagou os contratos ANTERIORES desta casa, parcela a "
        "parcela: quantas nunca pagou, quantas atrasou, atraso medio (negativo = "
        "adianta), quanto faltou pagar.",
}


@dataclass
class AcaoChamarFerramenta:
    ferramenta: str
    argumentos: dict


@dataclass
class AcaoConcluir:
    memo: MemoCredito


class ClienteLLM(Protocol):
    """Contrato minimo do modelo. Recebe o contexto acumulado, devolve a
    proxima acao: chamar mais uma ferramenta ou concluir o parecer."""

    def proxima_acao(
        self, contexto: str, ferramentas: dict[str, str]
    ) -> AcaoChamarFerramenta | AcaoConcluir:
        ...


@dataclass
class ResultadoAnalise:
    memo: MemoCredito | None
    trace: list[ChamadaFerramenta] = field(default_factory=list)
    atingiu_teto: bool = False
    erro: str | None = None


def montar_contexto_inicial(sk_id_curr: int, cenario: CenarioMacro) -> str:
    """Contexto que abre a analise.

    Aceita SOMENTE o id do cliente e o cenario do lote. Nao ha parametro por
    onde o score da Camada 1 possa entrar - a cegueira e garantida pela
    assinatura, nao pela boa intencao de quem chama.
    """
    return (
        f"Voce e um analista de credito. Analise o cliente {sk_id_curr} e emita "
        f"um parecer.\n\n"
        f"CENARIO DO LOTE (premissa da carteira, NAO caracteristica deste cliente):\n"
        f"  perda estimada em caso de calote: {cenario.lgd:.0%}\n"
        f"  fonte: {cenario.fonte}\n\n"
        f"Regras do parecer:\n"
        f"  - entre {MIN_FATORES} e {MAX_FATORES} fatos, priorizados por relevancia\n"
        f"  - todo fato precisa citar a ferramenta de onde veio\n"
        f"  - se recomendar DEFERIR, dizer o que faltou apurar\n"
        f"  - o cenario macro nao pode virar fato sobre o cliente\n"
    )


def validar_groundedness(memo: MemoCredito, trace: list[ChamadaFerramenta]) -> list[str]:
    """Todo `fonte_tool` do memo tem que resolver contra uma chamada real.

    E a rubrica eliminatoria do ADR-0004 verificada MECANICAMENTE, antes de
    qualquer juiz LLM. Fato que cita ferramenta nao chamada e alucinacao, e
    isso da para provar sem opiniao.
    """
    chamadas = {c.ferramenta for c in trace}
    return [
        f.fonte_tool for f in memo.fatores_cliente if f.fonte_tool not in chamadas
    ]


def preparar_lote(ids: list[int], seed: int = 42) -> list[int]:
    """Embaralha a fila antes de mandar para o agente.

    Vazamento pela ORDENACAO e vazamento igual: se os casos chegarem
    ordenados por risco, a posicao na fila carrega o score e o agente pode
    ancorar nela sem nunca ver um numero (ADR-0003 SS2.1).
    """
    fila = list(ids)
    random.Random(seed).shuffle(fila)
    return fila


class AgenteUnderwriting:
    """Orquestra o multi-hop e devolve o parecer validado."""

    def __init__(
        self,
        ferramentas: FerramentasCaso,
        cenario: CenarioMacro,
        cliente_llm: ClienteLLM,
        max_chamadas: int = MAX_CHAMADAS_POR_CASO,
    ):
        self.ferramentas = ferramentas
        self.cenario = cenario
        self.llm = cliente_llm
        self.max_chamadas = max_chamadas

    def _executar(self, acao: AcaoChamarFerramenta):
        metodo = getattr(self.ferramentas, acao.ferramenta, None)
        if acao.ferramenta not in FERRAMENTAS_DISPONIVEIS or metodo is None:
            raise ValueError(f"ferramenta desconhecida: {acao.ferramenta}")
        return metodo(**acao.argumentos)

    def analisar(self, sk_id_curr: int) -> ResultadoAnalise:
        contexto = montar_contexto_inicial(sk_id_curr, self.cenario)
        inicio = len(self.ferramentas.trace)

        for _ in range(self.max_chamadas):
            acao = self.llm.proxima_acao(contexto, FERRAMENTAS_DISPONIVEIS)

            if isinstance(acao, AcaoConcluir):
                trace = self.ferramentas.trace[inicio:]
                orfaos = validar_groundedness(acao.memo, trace)
                if orfaos:
                    return ResultadoAnalise(
                        memo=None, trace=trace,
                        erro=f"fato cita ferramenta nao chamada: {sorted(set(orfaos))}",
                    )
                return ResultadoAnalise(memo=acao.memo, trace=trace)

            try:
                retorno = self._executar(acao)
            except (ValueError, TypeError) as e:
                contexto += f"\n[ERRO ao chamar {acao.ferramenta}: {e}]\n"
                continue

            contexto += (
                f"\n[{acao.ferramenta}({acao.argumentos})]\n"
                f"{retorno.model_dump_json(indent=2)}\n"
            )

        return ResultadoAnalise(
            memo=None,
            trace=self.ferramentas.trace[inicio:],
            atingiu_teto=True,
            erro=f"teto de {self.max_chamadas} chamadas atingido sem parecer",
        )
