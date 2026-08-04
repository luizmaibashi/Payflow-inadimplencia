"""Motor de decisao por valor esperado (ADR-0002). Funcoes puras,
sem dependencia de dataframe especifico - usadas tanto no backtest
(scripts/motor_decisao_backtest.py) quanto, no futuro, na API de serving.

p* = margem / (margem + LGD)  -- ver ADR-0002 SS2.2. Nao depende do EAD
quando margem e perda escalam ambas com o principal (ADR-0002 SS2.3).

LIMITACAO DECLARADA (achado desta sessao, nao presente no ADR original):
`application_train.csv` (a aplicacao CORRENTE que a Camada 1 pontua) nao
tem CNT_PAYMENT (prazo do contrato) - esse campo so existe em
previous_application.csv (contratos JA FECHADOS, usados no Gate 0). O
prazo, na pratica, e uma variavel que o Home Credit decide junto com a
aprovacao, nao um dado que chega pronto antes da decisao. Por isso:

- `margem_proxy_anuidade()` usa AMT_ANNUITY/AMT_CREDIT (razao de anuidade
  sobre principal) como proxy de intensidade de margem - NAO e a mesma
  metrica validada no Gate 0 (margem total sobre a vida do contrato,
  que exige CNT_PAYMENT). E uma aproximacao mais simples, declarada.
- `lgd_por_tipo_contrato()` usa NAME_CONTRACT_TYPE de application_train
  (Cash loans / Revolving loans - as UNICAS duas categorias nesse
  dataset), NAO o proxy Consumer/Cash usado no Gate 0 (que vinha de
  previous_application, com categorias diferentes). Revolving (cartao)
  assumido como pior recuperacao que Cash (parcelado, mais estruturado).
"""
import numpy as np
import pandas as pd

LGD_CASH_LOAN = 0.70   # piso da faixa declarada (ADR-0002): parcelado, recuperacao mais estruturada
LGD_REVOLVING = 0.85   # teto da faixa declarada: revolving/cartao, recuperacao mais dificil

# Banda de indiferenca em torno de p* (ADR-0002 SS2.4: a faixa de LGD
# 70-85% move p* em ~3pp isolada). Usada como largura fixa simplificada
# da zona cinzenta - simplificacao declarada, nao uma banda derivada da
# incerteza real da estimativa de PD (debito, ver AGENTS.md).
BANDA_INDIFERENCA_PP = 0.03


def margem_proxy_anuidade(amt_annuity: pd.Series, amt_credit: pd.Series) -> pd.Series:
    """Proxy de m: razao anuidade/credito. NAO equivale a margem total
    sobre a vida do contrato - CONFUNDE PRAZO COM MARGEM (dois contratos
    com a mesma margem real e prazos diferentes tem razoes bem diferentes).

    Mantido para comparacao/regressao, mas SUBSTITUIDO por
    margem_via_prazo_historico_cliente() como proxy principal (achado de
    2026-08-04, ver ADR-0002 SS2.7 e AGENTS.md debito #12/#13).
    """
    return amt_annuity / amt_credit


PRAZO_MEDIANO_FALLBACK_MESES = 12.0  # mediana populacional de CNT_PAYMENT em previous_application


def margem_via_prazo_historico_cliente(
    amt_annuity: pd.Series, amt_credit: pd.Series, prazo_medio_historico: pd.Series
) -> pd.Series:
    """[NAO USADA EM PRODUCAO - registro de experimento negativo, 2026-08-04]

    Reconstroi a formula de margem do Gate 0 (m = anuidade*prazo/credito - 1)
    usando o prazo medio dos contratos ANTERIORES do cliente
    (previous_cnt_payment_mean) como estimativa do prazo do contrato atual.

    POR QUE FOI DESCARTADA: produz margem negativa em 77% dos casos. O
    credito ATUAL precisa de ~20 meses (mediana) so para amortizar o
    principal, mas o historico do cliente tem prazo mediano de 12 meses -
    sao populacoes de contrato diferentes (anteriores = emprestimos
    pequenos de varejo; atual = substancialmente maior). Um nao estima
    o outro.

    Licao: "existe dado disponivel" != "existe dado aplicavel". O prazo
    historico e medicao real, mas de um objeto diferente do que se quer
    medir. Usa-la teria trocado o vies conhecido e declarado de
    margem_proxy_anuidade() por um erro maior e silencioso.

    Mantida com testes como registro do experimento. Ver
    reports/motor_decisao_backtest.md e ADR-0002 SS2.7.
    """
    prazo = prazo_medio_historico.fillna(PRAZO_MEDIANO_FALLBACK_MESES)
    return (amt_annuity * prazo - amt_credit) / amt_credit


def lgd_por_tipo_contrato(name_contract_type: pd.Series) -> pd.Series:
    return np.where(name_contract_type == "Cash loans", LGD_CASH_LOAN, LGD_REVOLVING)


def calcular_p_estrela(margem, lgd):
    """p* = margem / (margem + LGD). Ponto de indiferenca de valor esperado."""
    return margem / (margem + lgd)


def classificar_decisao(p_hat, p_estrela, banda=BANDA_INDIFERENCA_PP):
    """Classifica em APROVAR / ZONA_CINZENTA / NEGAR comparando p_hat
    contra a banda de indiferenca em torno de p*.

    p_hat, p_estrela: escalares ou arrays/Series do mesmo shape.
    """
    p_hat = np.asarray(p_hat, dtype=float)
    p_estrela = np.asarray(p_estrela, dtype=float)

    limite_inferior = p_estrela - banda
    limite_superior = p_estrela + banda

    decisao = np.full(p_hat.shape, "ZONA_CINZENTA", dtype=object)
    decisao[p_hat < limite_inferior] = "APROVAR"
    decisao[p_hat > limite_superior] = "NEGAR"
    return decisao
