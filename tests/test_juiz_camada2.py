"""Testes do juiz de Task Completion (ADR-0004 SS2.2, debito #19).

Mesmo principio de test_agente_underwriting.py: o LLM e um dublê com
resposta fixa. O que se testa aqui e o CONTRATO (parsing do veredito,
construção do prompt, exigência de evidência em FALHA) - nao a qualidade
de julgamento de um modelo real, que é objeto de calibração
(scripts/calibrar_juiz.py) contra os 87 labels humanos, nao de teste
unitário.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clientes_llm import RespostaLLMInvalida  # noqa: E402
from app.ferramentas_caso import ChamadaFerramenta  # noqa: E402
from app.juiz_camada2 import (  # noqa: E402
    ResultadoJuizTaskCompletion,
    VeredictoTaskCompletion,
    _prompt_sistema_juiz,
    _prompt_usuario_juiz,
    julgar_task_completion,
)
from app.memo_credito import (  # noqa: E402
    CenarioAssumido,
    FatorCliente,
    MemoCredito,
    Peso,
    Recomendacao,
)


def _memo(fatores=None, recomendacao=Recomendacao.APROVAR, **kw):
    if fatores is None:
        fatores = [
            FatorCliente(fato="0 parcelas nunca pagas", fonte_tool="consultar_pagamentos", peso=Peso.FAVORAVEL),
            FatorCliente(fato="atraso medio -11.6 dias", fonte_tool="consultar_pagamentos", peso=Peso.FAVORAVEL),
            FatorCliente(fato="utilizacao de credito 68.7%", fonte_tool="consultar_bureau", peso=Peso.DESFAVORAVEL),
        ]
    return MemoCredito(
        cliente_id="181390", recomendacao=recomendacao, fatores_cliente=fatores,
        cenario_assumido=CenarioAssumido(lgd=0.82, fonte="BCB SGS 432"), **kw)


def _trace():
    return [
        ChamadaFerramenta(
            ferramenta="consultar_bureau", argumentos={"sk_id_curr": 181390},
            retorno={"tem_registro": True, "utilizacao": 0.687},
        ),
        ChamadaFerramenta(
            ferramenta="consultar_pagamentos", argumentos={"sk_id_curr": 181390},
            retorno={"n_pagas_com_atraso": 0, "atraso_medio_dias": -11.6},
        ),
    ]


class JuizComRoteiro:
    """Dublê: devolve uma resposta fixa (dict) por chamada, e guarda os
    prompts recebidos para inspecao."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.prompts_sistema = []
        self.prompts_usuario = []

    def perguntar(self, prompt_sistema, prompt_usuario):
        self.prompts_sistema.append(prompt_sistema)
        self.prompts_usuario.append(prompt_usuario)
        return json.dumps(self.respostas.pop(0))


def test_veredito_ok_quando_juiz_aprova_recomendacao():
    juiz = JuizComRoteiro([{"veredito": "OK", "evidencia": "", "categoria_falha": ""}])
    resultado = julgar_task_completion(_memo(), _trace(), juiz)

    assert resultado == ResultadoJuizTaskCompletion(
        veredito=VeredictoTaskCompletion.OK, evidencia="", categoria_falha="")


def test_veredito_falha_com_evidencia_e_categoria():
    juiz = JuizComRoteiro([{
        "veredito": "FALHA",
        "evidencia": "0 parcelas nunca pagas e atraso medio -11.6 dias, mas recomendacao foi NEGAR",
        "categoria_falha": "recomendacao_ignora_fato",
    }])
    resultado = julgar_task_completion(_memo(recomendacao=Recomendacao.NEGAR), _trace(), juiz)

    assert resultado.veredito is VeredictoTaskCompletion.FALHA
    assert "atraso medio" in resultado.evidencia
    assert resultado.categoria_falha == "recomendacao_ignora_fato"


def test_falha_sem_evidencia_levanta_erro():
    juiz = JuizComRoteiro([{"veredito": "FALHA", "evidencia": "", "categoria_falha": "recomendacao_ignora_fato"}])

    with pytest.raises(RespostaLLMInvalida, match="sem evidencia"):
        julgar_task_completion(_memo(), _trace(), juiz)


def test_veredito_fora_do_contrato_levanta_erro():
    juiz = JuizComRoteiro([{"veredito": "TALVEZ", "evidencia": "", "categoria_falha": ""}])

    with pytest.raises(RespostaLLMInvalida, match="fora do contrato"):
        julgar_task_completion(_memo(), _trace(), juiz)


def test_resposta_nao_json_levanta_erro():
    class JuizTextoLivre:
        def perguntar(self, prompt_sistema, prompt_usuario):
            return "isso nao e JSON"

    with pytest.raises(RespostaLLMInvalida, match="nao devolveu JSON valido"):
        julgar_task_completion(_memo(), _trace(), JuizTextoLivre())


def test_prompt_usuario_contem_recomendacao_e_fatores():
    prompt = _prompt_usuario_juiz(_memo(recomendacao=Recomendacao.NEGAR), _trace())

    assert "NEGAR" in prompt
    assert "0 parcelas nunca pagas" in prompt
    assert "consultar_pagamentos" in prompt


def test_prompt_usuario_contem_dados_brutos_da_trace():
    prompt = _prompt_usuario_juiz(_memo(), _trace())

    assert "atraso_medio_dias" in prompt
    assert "-11.6" in prompt


def test_prompt_usuario_sem_trace_nao_quebra():
    prompt = _prompt_usuario_juiz(_memo(), [])

    assert "nenhuma chamada" in prompt


# --- Criterio do ADR-0011 no prompt do juiz ---------------------------------
# Estes testes existem porque o criterio vive numa STRING: sem eles, apagar um
# limiar do prompt nao quebra nada e o juiz passa a medir outra coisa em
# silencio - exatamente o modo de falha que a calibracao de 2026-08-08 achou.


@pytest.mark.parametrize("limiar", ["80%", "30 dias", "15%", "90"])
def test_prompt_sistema_cita_os_limiares_do_adr_0011(limiar):
    assert limiar in _prompt_sistema_juiz()


def test_prompt_sistema_separa_grave_de_agravante():
    prompt = _prompt_sistema_juiz()

    assert "SINAIS GRAVES" in prompt
    assert "AGRAVANTES" in prompt
    assert "2+ AGRAVANTES" in prompt


def test_prompt_sistema_proibe_contagem_de_pesos():
    """Regressao do achado de 2026-08-08: contar favoravel/desfavoravel mede a
    REDACAO do memo (o agente escolhe os rotulos), nao o risco do cliente."""
    prompt = _prompt_sistema_juiz().lower()

    assert "nao conte quantos fatores" in prompt
    assert "mede a redacao" in prompt


def test_prompt_sistema_diz_que_deficit_sozinho_nao_nega():
    """Decisão de fronteira do ADR-0011 §2.2.1 — pagar a menor cronicamente é
    caso de limite menor, não de recusa."""
    prompt = _prompt_sistema_juiz().lower()

    assert "cronica" in prompt
    assert "limite menor" in prompt


def test_prompt_sistema_proibe_segunda_camada_de_analise():
    """Regressao do debito #32 (2026-08-09): juiz identificava corretamente
    um sinal grave (que sozinho basta pelo ADR-0011 SS2.1) e mesmo assim
    marcava FALHA depois de ponderar outros fatores ("mas o historico e
    bom demais para negar") - reintroduzia o julgamento implicito que o
    ADR-0011 existe para eliminar. O prompt precisa proibir essa segunda
    camada explicitamente."""
    prompt = _prompt_sistema_juiz().lower()

    assert "unico criterio" in prompt
    assert "pare ai" in prompt
    assert "nao existe segunda camada" in prompt
