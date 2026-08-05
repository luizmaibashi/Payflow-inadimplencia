"""Ferramentas de CASO da Camada 2 (ADR-0007, familia "caso").

O agente recebe apenas o SK_ID_CURR e decide o que puxar. As tabelas NAO
vao pre-agregadas no prompt - se fossem, o agente viraria redator e o
multi-hop que justificou o dataset relacional (ADR-0001) morreria.

Tres propriedades que este modulo garante:

1. NENHUMA SAIDA CARREGA O SCORE. As ferramentas leem CSV bruto; nao ha
   caminho ate o modelo da Camada 1. Ha teste guardando isso, porque um
   vazamento invalidaria o experimento inteiro (ADR-0003 SS2.1).

2. TODA CHAMADA FICA NA TRACE. tool, argumentos e retorno. E o que torna
   o `fonte_tool` do memo verificavel: um fato so vale se resolve contra
   uma chamada real (groundedness, ADR-0004).

3. "SEM REGISTRO" E RESPOSTA, NAO ERRO. Cliente sem historico de bureau
   devolve zeros com `tem_registro=False`. Ausencia de divida externa e
   um fato apurado, nao uma falha de consulta.
"""
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "home_credit"

# Status do bureau_balance que contam como atraso (0 = em dia, 1-5 = faixas
# crescentes de dias em atraso, C = encerrado, X = sem informacao).
_STATUS_ATRASO = {"1", "2", "3", "4", "5"}


class ChamadaFerramenta(BaseModel):
    """Uma linha da trace de auditoria."""

    ferramenta: str
    argumentos: dict
    retorno: dict


class ResultadoHistoricoBureau(BaseModel):
    """Comportamento mes a mes nos contratos de OUTRAS instituicoes.

    Separa quem atrasou uma vez de quem atrasa sempre - distincao que a
    consulta de saldo (consultar_bureau) nao consegue fazer.
    """

    tem_registro: bool = Field(..., description="Se ha historico mensal disponivel")
    meses_observados: int = Field(..., ge=0, description="Meses com registro")
    meses_em_dia: int = Field(..., ge=0)
    meses_em_atraso: int = Field(..., ge=0)
    meses_sem_informacao: int = Field(
        ..., ge=0,
        description="Meses com STATUS 'X'. NAO sao meses bons - sao meses "
        "sobre os quais nada se sabe (21% da tabela, EDA 2026-08-05)",
    )
    pior_severidade: int | None = Field(
        None, ge=0, le=5,
        description="Pior faixa de atraso ja registrada (1=1-30d ... 5=>120d)",
    )
    meses_desde_ultimo_atraso: int | None = Field(
        None, ge=0,
        description="Ha quantos meses foi o ultimo atraso. Alto = atraso "
        "antigo e ja recuperado; baixo = problema corrente",
    )



class ResultadoPagamentosHomeCredit(BaseModel):
    """Comportamento de pagamento em contratos ANTERIORES da propria casa.

    Diferenca para as tools de bureau: la e o que outros bancos reportaram;
    aqui e o que a propria Home Credit VIU acontecer, parcela a parcela.
    E o registro mais direto que existe - nao e proxy de capacidade de
    pagamento, e o pagamento.
    """

    tem_registro: bool = Field(..., description="Se ha historico de parcelas")
    n_parcelas: int = Field(..., ge=0, description="Parcelas ja processadas")
    n_nunca_pagas: int = Field(
        ..., ge=0,
        description="Parcelas SEM pagamento registrado. Sinal mais forte que "
        "existe: clientes com isso dao calote em 18,1% contra 8,0% do resto "
        "(EDA 2026-08-05). Nao confundir com 'paga em atraso'",
    )
    n_pagas_com_atraso: int = Field(..., ge=0)
    n_pagas_a_menor: int = Field(
        ..., ge=0, description="Pagou menos que o devido - aperto de caixa"
    )
    atraso_medio_dias: float | None = Field(
        None, description="Media de dias de atraso. NEGATIVO = paga adiantado "
        "(a mediana da base e -9,5 dias)"
    )
    pior_atraso_dias: int | None = Field(None, description="Maior atraso ja registrado")
    dias_desde_ultimo_atraso: int | None = Field(
        None, ge=0,
        description="Ha quantos dias foi o ultimo atraso. Baixo = problema "
        "corrente; alto = ja recuperado",
    )
    deficit_medio_pct: float | None = Field(
        None, ge=0.0,
        description="% medio do valor da parcela que FALTOU pagar. Piso em "
        "zero: pagar a MAIS nao e deficit negativo, e outra coisa (quitacao "
        "antecipada) - misturar os dois produzia media sem sentido, tipo "
        "-4919% (achado ao rodar em dado real, 2026-08-05)",
    )
    n_pagas_a_maior: int = Field(
        0, ge=0,
        description="Parcelas pagas ACIMA do devido - tipicamente quitacao "
        "antecipada. Fica em campo proprio para nao contaminar o deficit",
    )


class ResultadoBureau(BaseModel):
    """Retrato do cliente em OUTRAS instituicoes financeiras."""

    tem_registro: bool = Field(..., description="Se o cliente aparece no bureau")
    n_contratos: int = Field(..., ge=0, description="Contratos totais em outros bancos")
    n_ativos: int = Field(..., ge=0, description="Quantos seguem ativos")
    n_em_atraso_hoje: int = Field(..., ge=0, description="Quantos estao vencidos agora")
    divida_total: float | None = Field(None, description="Saldo devedor somado")
    credito_total: float | None = Field(None, description="Credito concedido somado")
    utilizacao: float | None = Field(
        None, description="divida/credito - quanto do limite ja foi consumido"
    )
    tem_historico_mensal: bool = Field(
        ...,
        description="Se ha detalhe mes a mes disponivel (indica se vale "
        "aprofundar em consultar_historico_bureau)",
    )


class FerramentasCaso:
    """Acesso as tabelas relacionais, por cliente e sob demanda.

    Carrega e indexa uma vez; consultas seguintes sao lookup. Instanciar
    uma vez por lote, nao por cliente.
    """

    def __init__(self, raw_dir: Path | None = None):
        self.raw = Path(raw_dir) if raw_dir else RAW
        self._bureau: pd.DataFrame | None = None
        self._ids_com_balance: set[int] | None = None
        self._balance: pd.DataFrame | None = None
        self._parcelas: pd.DataFrame | None = None
        self.trace: list[ChamadaFerramenta] = []

    # --- carregamento preguicoso (so paga o custo se a tool for usada) ---

    def _carregar_bureau(self) -> pd.DataFrame:
        if self._bureau is None:
            df = pd.read_csv(
                self.raw / "bureau.csv",
                usecols=[
                    "SK_ID_CURR", "SK_ID_BUREAU", "CREDIT_ACTIVE",
                    "CREDIT_DAY_OVERDUE", "AMT_CREDIT_SUM", "AMT_CREDIT_SUM_DEBT",
                ],
            )
            self._bureau = df.set_index("SK_ID_CURR").sort_index()
        return self._bureau

    def _carregar_ids_com_balance(self) -> set[int]:
        if self._ids_com_balance is None:
            self._ids_com_balance = set(self._carregar_balance().index.unique())
        return self._ids_com_balance

    def _carregar_balance(self) -> pd.DataFrame:
        if self._balance is None:
            df = pd.read_csv(self.raw / "bureau_balance.csv")
            self._balance = df.set_index("SK_ID_BUREAU").sort_index()
        return self._balance

    def _carregar_parcelas(self) -> pd.DataFrame:
        if self._parcelas is None:
            df = pd.read_csv(
                self.raw / "installments_payments.csv",
                usecols=[
                    "SK_ID_CURR", "DAYS_INSTALMENT", "DAYS_ENTRY_PAYMENT",
                    "AMT_INSTALMENT", "AMT_PAYMENT",
                ],
            )
            self._parcelas = df.set_index("SK_ID_CURR").sort_index()
        return self._parcelas

    # --- registro de auditoria ---

    def _registrar(self, ferramenta: str, argumentos: dict, retorno: BaseModel):
        self.trace.append(
            ChamadaFerramenta(
                ferramenta=ferramenta, argumentos=argumentos, retorno=retorno.model_dump()
            )
        )

    # --- FERRAMENTA: bureau ---

    def consultar_bureau(self, sk_id_curr: int) -> ResultadoBureau:
        """Credito do cliente em OUTRAS instituicoes.

        Ponto de partida natural: mostra o tamanho da exposicao externa e
        se ha atraso corrente. `tem_historico_mensal` diz se vale o
        proximo salto (detalhe mes a mes).
        """
        bureau = self._carregar_bureau()

        if sk_id_curr in bureau.index:
            linhas = bureau.loc[[sk_id_curr]]
        else:
            linhas = bureau.iloc[0:0]

        if linhas.empty:
            resultado = ResultadoBureau(
                tem_registro=False, n_contratos=0, n_ativos=0, n_em_atraso_hoje=0,
                tem_historico_mensal=False,
            )
        else:
            credito = linhas["AMT_CREDIT_SUM"].sum(min_count=1)
            divida = linhas["AMT_CREDIT_SUM_DEBT"].sum(min_count=1)
            utilizacao = (
                float(divida / credito)
                if pd.notna(credito) and pd.notna(divida) and credito > 0
                else None
            )
            com_balance = self._carregar_ids_com_balance()
            resultado = ResultadoBureau(
                tem_registro=True,
                n_contratos=len(linhas),
                n_ativos=int((linhas["CREDIT_ACTIVE"] == "Active").sum()),
                n_em_atraso_hoje=int((linhas["CREDIT_DAY_OVERDUE"] > 0).sum()),
                divida_total=float(divida) if pd.notna(divida) else None,
                credito_total=float(credito) if pd.notna(credito) else None,
                utilizacao=utilizacao,
                tem_historico_mensal=bool(
                    set(linhas["SK_ID_BUREAU"]) & com_balance
                ),
            )

        self._registrar("consultar_bureau", {"sk_id_curr": int(sk_id_curr)}, resultado)
        return resultado

    # --- FERRAMENTA: historico mes a mes do bureau (2o salto do multi-hop) ---

    def consultar_historico_bureau(self, sk_id_curr: int) -> ResultadoHistoricoBureau:
        """Comportamento mes a mes nos contratos de outras instituicoes.

        Segundo salto: so faz sentido depois de consultar_bureau() indicar
        `tem_historico_mensal=True`. Separa quem atrasou uma vez de quem
        atrasa sempre - e diz HA QUANTO TEMPO foi o ultimo atraso, que e a
        diferenca entre problema antigo e problema corrente.
        """
        bureau = self._carregar_bureau()
        balance = self._carregar_balance()

        ids = (
            bureau.loc[[sk_id_curr], "SK_ID_BUREAU"].tolist()
            if sk_id_curr in bureau.index else []
        )
        presentes = [i for i in ids if i in balance.index]

        if not presentes:
            resultado = ResultadoHistoricoBureau(
                tem_registro=False, meses_observados=0, meses_em_dia=0,
                meses_em_atraso=0, meses_sem_informacao=0,
            )
        else:
            hist = balance.loc[presentes]
            status = hist["STATUS"].astype(str)

            # 'C' = contrato encerrado, '0' = em dia, '1'-'5' = faixas de atraso.
            # 'X' NAO entra como bom: e ausencia de informacao (EDA 2026-08-05).
            sem_info = status == "X"
            atraso = status.isin(_STATUS_ATRASO)
            em_dia = status.isin({"0", "C"})

            severidades = status[atraso].astype(int)
            meses_atraso = hist.loc[atraso, "MONTHS_BALANCE"]

            resultado = ResultadoHistoricoBureau(
                tem_registro=True,
                meses_observados=int(len(hist)),
                meses_em_dia=int(em_dia.sum()),
                meses_em_atraso=int(atraso.sum()),
                meses_sem_informacao=int(sem_info.sum()),
                pior_severidade=int(severidades.max()) if len(severidades) else None,
                # MONTHS_BALANCE e negativo (meses atras); o mais recente e o maior
                meses_desde_ultimo_atraso=(
                    int(-meses_atraso.max()) if len(meses_atraso) else None
                ),
            )

        self._registrar(
            "consultar_historico_bureau", {"sk_id_curr": int(sk_id_curr)}, resultado
        )
        return resultado

    # --- FERRAMENTA: pagamentos na propria Home Credit ---

    def consultar_pagamentos(self, sk_id_curr: int) -> ResultadoPagamentosHomeCredit:
        """Como o cliente pagou os contratos ANTERIORES desta casa.

        Todas as outras tools sao proxy de capacidade de pagamento. Esta e
        o registro do pagamento em si - o que ele fez, nao o que declarou.
        """
        par = self._carregar_parcelas()
        linhas = par.loc[[sk_id_curr]] if sk_id_curr in par.index else par.iloc[0:0]

        if linhas.empty:
            resultado = ResultadoPagamentosHomeCredit(
                tem_registro=False, n_parcelas=0, n_nunca_pagas=0,
                n_pagas_com_atraso=0, n_pagas_a_menor=0,
            )
        else:
            nunca_pagou = linhas["DAYS_ENTRY_PAYMENT"].isna()
            atraso = linhas["DAYS_ENTRY_PAYMENT"] - linhas["DAYS_INSTALMENT"]
            atrasadas = atraso > 0

            # deficit so faz sentido onde houve parcela com valor E pagamento
            devido = linhas["AMT_INSTALMENT"]
            pago = linhas["AMT_PAYMENT"]
            valido = (devido > 0) & pago.notna()
            # Piso em zero: pagar a MAIS nao e "deficit negativo". Sem isso a
            # media misturava falta de pagamento com quitacao antecipada e
            # produzia numeros absurdos (visto -4919% em caso real; ha parcela
            # paga 194 mil vezes o valor devido). 1,3% das parcelas da base.
            deficit = ((devido - pago) / devido).where(valido).clip(lower=0)

            venc_atrasadas = linhas.loc[atrasadas, "DAYS_INSTALMENT"]

            resultado = ResultadoPagamentosHomeCredit(
                tem_registro=True,
                n_parcelas=int(len(linhas)),
                n_nunca_pagas=int(nunca_pagou.sum()),
                n_pagas_com_atraso=int(atrasadas.sum()),
                n_pagas_a_menor=int((pago < devido).sum()),
                atraso_medio_dias=(
                    float(atraso.mean()) if atraso.notna().any() else None
                ),
                pior_atraso_dias=(
                    int(atraso.max()) if atraso.notna().any() else None
                ),
                # DAYS_INSTALMENT e negativo (dias atras); o mais recente e o maior
                dias_desde_ultimo_atraso=(
                    int(-venc_atrasadas.max()) if len(venc_atrasadas) else None
                ),
                deficit_medio_pct=(
                    float(deficit.mean()) if deficit.notna().any() else None
                ),
                n_pagas_a_maior=int((pago > devido).sum()),
            )

        self._registrar("consultar_pagamentos", {"sk_id_curr": int(sk_id_curr)}, resultado)
        return resultado
