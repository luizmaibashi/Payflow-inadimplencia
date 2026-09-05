"""Testes do agente de underwriting (ADR-0003, ADR-0007).

O LLM e substituido por um dublê com roteiro fixo. Isso e proposital: o que
se testa aqui e a ORQUESTRACAO (teto de chamadas, cegueira ao score,
groundedness), que e deterministica. Qualidade de julgamento do modelo e
objeto de eval (ADR-0004), nao de teste unitario.

O teste mais importante do arquivo e `test_contexto_do_agente_nao_contem_o_score`.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agente_underwriting import (  # noqa: E402
    AcaoChamarFerramenta,
    AcaoConcluir,
    AgenteUnderwriting,
    montar_contexto_inicial,
    preparar_lote,
    validar_groundedness,
    validar_groundedness_numerica,
    validar_trajetoria,
    APLICABILIDADE_FERRAMENTAS,
    FERRAMENTAS_DISPONIVEIS,
)
from app.ferramenta_cenario import FerramentaCenario  # noqa: E402
from app.ferramentas_caso import ChamadaFerramenta, FerramentasCaso  # noqa: E402
from app.memo_credito import (  # noqa: E402
    CenarioAssumido,
    FatorCliente,
    MemoCredito,
    Peso,
    Recomendacao,
)


@pytest.fixture
def cenario():
    return FerramentaCenario(buscador=lambda s: 12.5).consultar_cenario()


@pytest.fixture
def ferramentas(tmp_path):
    pd.DataFrame({
        "SK_ID_CURR": [1, 1], "SK_ID_BUREAU": [10, 11],
        "CREDIT_ACTIVE": ["Active", "Closed"], "CREDIT_DAY_OVERDUE": [0, 0],
        "AMT_CREDIT_SUM": [1000.0, 500.0], "AMT_CREDIT_SUM_DEBT": [300.0, 0.0],
    }).to_csv(tmp_path / "bureau.csv", index=False)
    pd.DataFrame({
        "SK_ID_BUREAU": [10, 10], "MONTHS_BALANCE": [-1, -2], "STATUS": ["0", "1"],
    }).to_csv(tmp_path / "bureau_balance.csv", index=False)
    pd.DataFrame({
        "SK_ID_CURR": [1, 1], "DAYS_INSTALMENT": [-60.0, -30.0],
        "DAYS_ENTRY_PAYMENT": [-62.0, -25.0],
        "AMT_INSTALMENT": [100.0, 100.0], "AMT_PAYMENT": [100.0, 100.0],
    }).to_csv(tmp_path / "installments_payments.csv", index=False)
    return FerramentasCaso(raw_dir=tmp_path)


def _memo(fontes=("consultar_bureau",), recomendacao=Recomendacao.NEGAR, **kw):
    fatores = [
        FatorCliente(fato=f"fato {i}", fonte_tool=f, peso=Peso.DESFAVORAVEL)
        for i, f in enumerate(fontes)
    ]
    while len(fatores) < 3:
        fatores.append(FatorCliente(
            fato="fato extra de preenchimento, sem numero",
            fonte_tool=fontes[0], peso=Peso.NEUTRO))
    return MemoCredito(
        cliente_id="1", recomendacao=recomendacao, fatores_cliente=fatores,
        cenario_assumido=CenarioAssumido(lgd=0.78, fonte="BCB SGS 432"), **kw)


class LLMComRoteiro:
    """Dublê: devolve as acoes de um roteiro fixo, em ordem."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.contextos_vistos = []

    def proxima_acao(self, contexto, ferramentas):
        self.contextos_vistos.append(contexto)
        return self.roteiro.pop(0) if self.roteiro else AcaoConcluir(memo=_memo())


# --- INVARIANTE CENTRAL: cegueira ao score (ADR-0003 SS2.1) ---

def test_contexto_do_agente_nao_contem_o_score(cenario):
    """Se este teste quebrar, NAO relaxe: o experimento inteiro perde sentido.

    Serializa tudo que o agente ve na abertura e procura qualquer rastro do
    modelo da Camada 1.
    """
    contexto = montar_contexto_inicial(sk_id_curr=100034, cenario=cenario)
    proibidos = ["p_default", "probabilidade de default", "score", "p_hat",
                 "camada 1", "modelo previu", "risco estimado"]
    for termo in proibidos:
        assert termo not in contexto.lower(), f"contexto vaza '{termo}'"


def test_montar_contexto_nao_aceita_parametro_de_score(cenario):
    """Prevencao ESTRUTURAL: nao existe por onde o score entrar."""
    with pytest.raises(TypeError):
        montar_contexto_inicial(sk_id_curr=1, cenario=cenario, p_default=0.42)


def test_contexto_marca_o_cenario_como_premissa_do_lote(cenario):
    """O macro nao pode ser lido como caracteristica do cliente (ADR-0008)."""
    contexto = montar_contexto_inicial(1, cenario).lower()
    assert "premissa da carteira" in contexto
    assert "nao caracteristica deste cliente" in contexto


def test_fila_e_embaralhada_para_nao_vazar_risco_pela_ordem():
    """Fila ordenada por risco faz a POSICAO carregar o score."""
    ordenada = list(range(100))
    assert preparar_lote(ordenada) != ordenada
    assert sorted(preparar_lote(ordenada)) == ordenada, "nao pode perder caso"


def test_embaralhamento_e_reprodutivel():
    assert preparar_lote([1, 2, 3, 4, 5], seed=7) == preparar_lote([1, 2, 3, 4, 5], seed=7)


# --- Groundedness verificada mecanicamente (ADR-0004, eliminatoria) ---

def test_fato_citando_ferramenta_nao_chamada_e_rejeitado(ferramentas, cenario):
    llm = LLMComRoteiro([AcaoConcluir(memo=_memo(fontes=("consultar_pagamentos",)))])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is None, "memo com fonte inventada nao pode passar"
    assert "consultar_pagamentos" in r.erro


def test_fato_citando_ferramenta_chamada_e_aceito(ferramentas, cenario):
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo(fontes=("consultar_bureau",))),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is not None and r.erro is None
    assert validar_groundedness(r.memo, r.trace) == []


# --- Groundedness NUMERICA (debito #26): o valor citado bate com a ferramenta? ---
# validar_groundedness so confere que a FERRAMENTA foi chamada - um fato pode
# citar uma tool real e ainda assim inventar o numero. NAO eliminatoria (mesmo
# tratamento de validar_trajetoria): e heuristica de texto livre, tem falso
# positivo por formatacao (47% vs 0.47), entao registra para o eval contar,
# nao bloqueia o memo.

def test_numero_do_fato_bate_com_retorno_inteiro():
    trace = [_chamada("consultar_bureau", n_contratos=3)]
    memo = _memo(fontes=("consultar_bureau",))
    memo.fatores_cliente[0].fato = "cliente tem 3 contratos em outras instituicoes"

    assert validar_groundedness_numerica(memo, trace) == []


def test_numero_do_fato_bate_com_retorno_em_percentual():
    """utilizacao vem como fracao (0.4712) na ferramenta; o memo escreve em
    percentual (47.1%) - as duas escalas tem que casar."""
    trace = [_chamada("consultar_bureau", utilizacao=0.4712)]
    memo = _memo(fontes=("consultar_bureau",))
    memo.fatores_cliente[0].fato = "utilizacao de credito em 47.1%"

    assert validar_groundedness_numerica(memo, trace) == []


def test_numero_inventado_e_sinalizado():
    trace = [_chamada("consultar_bureau", n_contratos=3, utilizacao=0.20)]
    memo = _memo(fontes=("consultar_bureau",))
    memo.fatores_cliente[0].fato = "cliente tem 7 contratos em outras instituicoes"

    suspeitos = validar_groundedness_numerica(memo, trace)

    assert len(suspeitos) == 1
    assert "7" in suspeitos[0]


def test_fato_sem_numero_nao_e_avaliado():
    trace = [_chamada("consultar_bureau", n_contratos=3)]
    memo = _memo(fontes=("consultar_bureau",))
    memo.fatores_cliente[0].fato = "cliente possui historico de bureau"

    assert validar_groundedness_numerica(memo, trace) == []


def test_fato_de_ferramenta_orfa_nao_duplica_achado_de_validar_groundedness():
    """Fonte inexistente na trace ja e pego por validar_groundedness (que e
    eliminatoria) - a checagem numerica nao precisa (e nao deve) repetir."""
    trace = []
    memo = _memo(fontes=("consultar_bureau",))
    memo.fatores_cliente[0].fato = "cliente tem 3 contratos"

    assert validar_groundedness_numerica(memo, trace) == []


def test_analisar_registra_suspeita_numerica_sem_bloquear_o_memo(ferramentas, cenario):
    """Registrada, nao eliminatoria: numero suspeito nao derruba o memo -
    mesmo contrato de violacoes_trajetoria."""
    memo = _memo(fontes=("consultar_bureau",))
    memo.fatores_cliente[0].fato = "cliente tem 999 contratos em outras instituicoes"
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=memo),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is not None and r.erro is None
    assert len(r.suspeitos_groundedness_numerica) == 1
    assert "999" in r.suspeitos_groundedness_numerica[0]


# --- Multi-hop e teto de chamadas (ADR-0007) ---

def test_agente_encadeia_ferramentas_e_registra_a_sequencia(ferramentas, cenario):
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoChamarFerramenta("consultar_historico_bureau", {"sk_id_curr": 1}),
        AcaoChamarFerramenta("consultar_pagamentos", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo(fontes=(
            "consultar_bureau", "consultar_historico_bureau", "consultar_pagamentos"))),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert [c.ferramenta for c in r.trace] == [
        "consultar_bureau", "consultar_historico_bureau", "consultar_pagamentos"]


def test_retorno_da_ferramenta_entra_no_contexto_da_proxima_decisao(ferramentas, cenario):
    """E o que torna o multi-hop real: o 2o salto ve o resultado do 1o."""
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo()),
    ])
    AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    # A asercao mira o RETORNO registrado, nao o nome da ferramenta. Ate
    # 2026-08-06 ela testava `"consultar_bureau" not in contextos_vistos[0]`,
    # que funcionava so por acidente: o prompt inicial nao nomeava as tools.
    # Quando ele passou a nomea-las (conserto do defeito de trajetoria), o
    # proxy quebrou sem que a propriedade testada mudasse. `[consultar_bureau(`
    # e o marcador com que analisar() anexa um retorno ao contexto - so aparece
    # depois da chamada acontecer, que e exatamente o que se quer provar.
    assert "[consultar_bureau(" not in llm.contextos_vistos[0]
    assert "[consultar_bureau(" in llm.contextos_vistos[1]
    assert "tem_historico_mensal" in llm.contextos_vistos[1]


def test_teto_de_chamadas_impede_loop_de_exploracao(ferramentas, cenario):
    llm = LLMComRoteiro(
        [AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1})] * 50)
    r = AgenteUnderwriting(ferramentas, cenario, llm, max_chamadas=4).analisar(1)

    assert r.atingiu_teto is True
    assert r.memo is None
    assert len(r.trace) == 4


def test_ferramenta_inexistente_nao_derruba_a_analise(ferramentas, cenario):
    """Modelo alucina nome de tool; isso vira erro no contexto, nao crash."""
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_serasa", {"sk_id_curr": 1}),
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo()),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is not None
    assert "ERRO" in llm.contextos_vistos[1]


# --- Trajectory efficiency (rubrica #4 do ADR-0004, REGISTRADA nao eliminatoria) ---
#
# Regressao do defeito medido no piloto de 2026-08-06 (caso 344012): o agente
# chamou UMA tool, deferiu, e listou como faltante uma informacao que
# consultar_pagamentos entrega. Ver validar_trajetoria().

def _chamada(nome, **retorno):
    return ChamadaFerramenta(ferramenta=nome, argumentos={"sk_id_curr": 1}, retorno=retorno)


def _memo_deferir(fontes):
    return _memo(fontes=fontes, recomendacao=Recomendacao.DEFERIR,
                 informacao_faltante=["historico de pagamentos nesta instituicao"])


def test_deferir_sem_consultar_pagamentos_e_violacao():
    """O defeito exato do caso 344012."""
    trace = [_chamada("consultar_bureau", tem_historico_mensal=False)]
    violacoes = validar_trajetoria(_memo_deferir(("consultar_bureau",)), trace)

    assert len(violacoes) == 1
    assert "consultar_pagamentos" in violacoes[0]


def test_deferir_apos_consultar_as_sempre_aplicaveis_nao_e_violacao():
    trace = [_chamada("consultar_bureau", tem_historico_mensal=False),
             _chamada("consultar_pagamentos")]
    assert validar_trajetoria(_memo_deferir(("consultar_bureau",)), trace) == []


def test_aprovar_ou_negar_sem_esgotar_ferramentas_nao_e_violacao():
    """A regra vale so para DEFERIR: decidir com menos informacao e uma
    escolha legitima; ALEGAR FALTA do que nao se buscou e que nao e."""
    trace = [_chamada("consultar_bureau", tem_historico_mensal=True)]
    for rec in (Recomendacao.APROVAR, Recomendacao.NEGAR):
        assert validar_trajetoria(_memo(recomendacao=rec), trace) == []


def test_deferir_ignorando_historico_disponivel_e_violacao():
    trace = [_chamada("consultar_bureau", tem_historico_mensal=True),
             _chamada("consultar_pagamentos")]
    violacoes = validar_trajetoria(_memo_deferir(("consultar_bureau",)), trace)

    assert len(violacoes) == 1
    assert "consultar_historico_bureau" in violacoes[0]


def test_nao_chamar_historico_inexistente_nao_e_violacao():
    """O 2o salto e CONDICIONAL. Cobra-lo sempre penalizaria o agente por
    respeitar o desenho do multi-hop (ADR-0007)."""
    trace = [_chamada("consultar_bureau", tem_historico_mensal=False),
             _chamada("consultar_pagamentos")]
    assert validar_trajetoria(_memo_deferir(("consultar_bureau",)), trace) == []


def test_violacao_de_trajetoria_nao_barra_o_memo(ferramentas, cenario):
    """NAO e eliminatoria - so groundedness e (ADR-0004 SS2.2). O memo volta
    com a violacao registrada, para o eval contar e o humano julgar."""
    llm = LLMComRoteiro([
        AcaoChamarFerramenta("consultar_bureau", {"sk_id_curr": 1}),
        AcaoConcluir(memo=_memo_deferir(("consultar_bureau",))),
    ])
    r = AgenteUnderwriting(ferramentas, cenario, llm).analisar(1)

    assert r.memo is not None, "trajetoria ruim nao pode barrar o memo"
    assert r.erro is None
    assert r.violacoes_trajetoria, "mas a violacao tem que ficar registrada"


def test_prompt_manda_apurar_antes_de_concluir(cenario):
    """Metade do conserto e mecanica (validar_trajetoria); a outra metade e
    instruir o gerador a nao cair no defeito."""
    contexto = montar_contexto_inicial(1, cenario).lower()
    assert "consultar_pagamentos" in contexto
    assert "deferir so vale" in contexto


def test_toda_ferramenta_publica_tem_politica_de_aplicabilidade():
    publicas = {
        nome
        for nome in dir(FerramentasCaso)
        if nome.startswith("consultar_") and callable(getattr(FerramentasCaso, nome))
    }

    assert set(FERRAMENTAS_DISPONIVEIS) == publicas
    assert set(APLICABILIDADE_FERRAMENTAS) == publicas


# --- Cenario e do lote, nao do cliente (ADR-0008) ---

def test_varios_clientes_do_lote_recebem_o_mesmo_cenario(ferramentas):
    f = FerramentaCenario(buscador=lambda s: 12.5)
    cen = f.consultar_cenario()
    for sk in (1, 2, 3):
        montar_contexto_inicial(sk, cen)
    assert f.n_buscas_externas == 1, "cenario nao pode ser buscado por cliente"
