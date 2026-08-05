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
