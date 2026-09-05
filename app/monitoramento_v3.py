"""Livro de coortes do PayFlow V3, alimentado por snapshot agregado."""

from pathlib import Path

import pandas as pd
import streamlit as st

from app.snapshot_monitoramento import carregar_snapshot, obter_coorte


RAIZ = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = RAIZ / "data" / "processed" / "monitoramento_v3.json"

CORES = {
    "papel": "#F3F6F8",
    "tinta": "#14212B",
    "evidencia": "#2F5D7E",
    "investigacao": "#C58A2A",
    "bloqueio": "#A5473E",
    "estabilidade": "#39735A",
}

st.set_page_config(
    page_title="PayFlow V3 — Livro de coortes",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _css() -> str:
    return f"""
    <style>
    :root {{
        --papel: {CORES['papel']};
        --tinta: {CORES['tinta']};
        --evidencia: {CORES['evidencia']};
        --investigacao: {CORES['investigacao']};
        --bloqueio: {CORES['bloqueio']};
        --estabilidade: {CORES['estabilidade']};
    }}
    .stApp {{ background: var(--papel); color: var(--tinta); }}
    .block-container {{ max-width: 1240px; padding-top: 5rem; padding-bottom: 4rem; }}
    h1, h2, h3, p, label {{ color: var(--tinta); }}
    h1 {{ font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.035em; }}
    [data-testid="stMetricValue"], code {{
        font-family: Consolas, 'Courier New', monospace;
        color: var(--tinta);
    }}
    .pf-masthead {{
        display: flex; justify-content: space-between; align-items: center;
        border-bottom: 1px solid #B9C5CC; padding-bottom: .75rem; margin-bottom: 1.4rem;
        font-family: 'Segoe UI', Aptos, sans-serif;
    }}
    .pf-brand {{ font-weight: 800; letter-spacing: .12em; font-size: .78rem; }}
    .pf-snapshot {{ font: .72rem Consolas, monospace; color: #566670; }}
    .pf-hero {{
        background: #FFFFFF; border-left: 7px solid var(--evidencia);
        padding: 1.5rem 1.7rem; box-shadow: 0 8px 28px rgba(20,33,43,.07);
        margin-bottom: 1.3rem;
    }}
    .pf-kicker {{ color: var(--evidencia); font-size: .72rem; font-weight: 800;
        letter-spacing: .11em; text-transform: uppercase; margin-bottom: .4rem; }}
    .pf-thesis {{ font: 700 clamp(1.55rem, 3vw, 2.7rem)/1.05 Georgia, serif;
        letter-spacing: -.035em; max-width: 830px; margin: 0 0 1rem; }}
    .pf-decision {{ display: inline-flex; align-items: center; gap: .5rem;
        background: #E8EFF4; color: #244B66; padding: .45rem .72rem;
        font: 800 .76rem Consolas, monospace; letter-spacing: .08em; }}
    .pf-reason {{ margin: .85rem 0 0; color: #40515C; max-width: 900px; }}
    .pf-strip {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .7rem;
        margin: .4rem 0 1.5rem; }}
    .pf-cohort {{ background: #E8EDF0; border-top: 4px solid #9CABB4;
        padding: .8rem 1rem; min-height: 88px; }}
    .pf-cohort.active {{ background: #FFFFFF; border-top-color: var(--evidencia);
        box-shadow: 0 5px 18px rgba(20,33,43,.08); }}
    .pf-cohort strong {{ display: block; font: 800 .92rem Consolas, monospace; }}
    .pf-cohort span {{ color: #566670; font-size: .8rem; }}
    .pf-guide {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem;
        margin: .3rem 0 1.3rem; }}
    .pf-guide-card {{ background: #FFFFFF; border-top: 3px solid var(--evidencia);
        padding: 1rem; min-height: 146px; }}
    .pf-guide-card strong {{ display: block; font: 800 .8rem Consolas, monospace;
        color: var(--evidencia); margin-bottom: .5rem; }}
    .pf-guide-card p {{ margin: 0; color: #40515C; font-size: .88rem; line-height: 1.42; }}
    .pf-delivery {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .55rem;
        margin: .3rem 0 1rem; }}
    .pf-delivery-step {{ border-left: 3px solid #9CABB4; padding: .75rem .75rem .75rem .9rem;
        background: #E8EDF0; min-height: 118px; }}
    .pf-delivery-step strong {{ display: block; font-size: .82rem; margin-bottom: .35rem; }}
    .pf-delivery-step span {{ color: #40515C; font-size: .8rem; line-height: 1.35; }}
    .pf-now {{ background: #FFF7E7; border-left: 5px solid var(--investigacao);
        padding: .85rem 1rem; color: #40515C; font-size: .87rem; }}
    .pf-section {{ font: 800 .74rem 'Segoe UI', sans-serif; letter-spacing: .12em;
        text-transform: uppercase; color: var(--evidencia); border-bottom: 1px solid #C8D1D6;
        padding-bottom: .45rem; margin: 1.8rem 0 1rem; }}
    .pf-callout {{ background: #FFF7E7; border-left: 5px solid var(--investigacao);
        padding: 1rem 1.15rem; margin: .8rem 0 1rem; }}
    .pf-callout strong {{ color: #6D4A12; }}
    .pf-limit {{ background: #E8EDF0; padding: .8rem 1rem; color: #40515C;
        font-size: .86rem; margin-top: 1.4rem; }}
    div[data-testid="stDataFrame"] {{ border: 1px solid #CCD5DA; }}
    @media (max-width: 760px) {{
        .block-container {{ padding: 4.5rem .85rem 2rem; }}
        .pf-masthead {{ align-items: flex-start; gap: .7rem; flex-direction: column; }}
        .pf-strip {{ grid-template-columns: 1fr; }}
        .pf-guide, .pf-delivery {{ grid-template-columns: 1fr; }}
        .pf-hero {{ padding: 1.1rem; }}
    }}
    </style>
    """


def _fmt_pct(valor: float | None, casas: int = 2) -> str:
    return "—" if valor is None else f"{valor:.{casas}%}"


def _contar_drift(coorte) -> dict[str, int]:
    estados = ("ESTAVEL", "ALERTA", "CRITICO", "INSUFICIENTE")
    return {
        estado: sum(item.status == estado for item in coorte.drift)
        for estado in estados
    }


@st.cache_resource
def _carregar():
    return carregar_snapshot(SNAPSHOT_PATH)


def _grafico_evolucao(snapshot) -> None:
    dados = pd.DataFrame(
        [
            {
                "coorte": item.coorte,
                "AUC": item.auc,
                "Brier": item.brier,
            }
            for item in snapshot.coortes
        ]
    )
    esquerda, direita = st.columns(2)
    especificacao_base = {
        "mark": {"type": "line", "point": {"filled": True, "size": 70}, "strokeWidth": 3},
        "encoding": {
            "x": {"field": "coorte", "type": "ordinal", "title": None},
            "tooltip": [
                {"field": "coorte", "type": "nominal"},
            ],
        },
        "height": 190,
        "config": {"view": {"stroke": None}, "axis": {"gridColor": "#DDE4E8"}},
    }
    with esquerda:
        st.caption("AUC · capacidade de ordenar risco")
        spec_auc = especificacao_base | {
            "encoding": especificacao_base["encoding"]
            | {
                "y": {
                    "field": "AUC",
                    "type": "quantitative",
                    "scale": {"zero": False},
                    "title": "AUC",
                },
                "color": {"value": CORES["evidencia"]},
                "tooltip": especificacao_base["encoding"]["tooltip"]
                + [{"field": "AUC", "type": "quantitative", "format": ".4f"}],
            },
        }
        st.vega_lite_chart(dados, spec_auc, width="stretch")
    with direita:
        st.caption("Brier · erro das probabilidades")
        spec_brier = especificacao_base | {
            "encoding": especificacao_base["encoding"]
            | {
                "y": {
                    "field": "Brier",
                    "type": "quantitative",
                    "scale": {"zero": False},
                    "title": "Brier",
                },
                "color": {"value": CORES["investigacao"]},
                "tooltip": especificacao_base["encoding"]["tooltip"]
                + [{"field": "Brier", "type": "quantitative", "format": ".4f"}],
            },
        }
        st.vega_lite_chart(dados, spec_brier, width="stretch")


def _grafico_calibracao(coorte) -> None:
    linhas = []
    for faixa in coorte.calibracao:
        linhas.extend(
            [
                {"faixa": faixa.faixa, "série": "Previsto", "taxa": faixa.previsto},
                {"faixa": faixa.faixa, "série": "Observado", "taxa": faixa.observado},
            ]
        )
    dados = pd.DataFrame(linhas)
    spec = {
        "mark": {"type": "line", "point": {"filled": True, "size": 60}, "strokeWidth": 3},
        "encoding": {
            "x": {"field": "faixa", "type": "ordinal", "title": "Faixa de score"},
            "y": {
                "field": "taxa",
                "type": "quantitative",
                "axis": {"format": ".1%"},
                "title": "Taxa",
            },
            "color": {
                "field": "série",
                "type": "nominal",
                "scale": {
                    "domain": ["Previsto", "Observado"],
                    "range": [CORES["evidencia"], CORES["investigacao"]],
                },
                "legend": {"orient": "top", "title": None},
            },
            "tooltip": [
                {"field": "faixa", "type": "ordinal"},
                {"field": "série", "type": "nominal"},
                {"field": "taxa", "type": "quantitative", "format": ".2%"},
            ],
        },
        "height": 310,
        "config": {"view": {"stroke": None}, "axis": {"gridColor": "#DDE4E8"}},
    }
    st.vega_lite_chart(dados, spec, width="stretch")


def main() -> None:
    st.markdown(_css(), unsafe_allow_html=True)
    try:
        snapshot = _carregar()
    except (FileNotFoundError, ValueError) as erro:
        st.error(str(erro))
        st.stop()

    gerado_em = snapshot.gerado_em.strftime("%d/%m/%Y %H:%M UTC")
    st.markdown(
        f"""
        <div class="pf-masthead">
          <div class="pf-brand">PAYFLOW / LIVRO DE COORTES</div>
          <div class="pf-snapshot">SNAPSHOT DE PESQUISA · {gerado_em}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rotulos = [coorte.coorte for coorte in snapshot.coortes]
    selecionada = st.radio(
        "Coorte em análise",
        rotulos,
        index=len(rotulos) - 1,
        horizontal=True,
    )
    coorte = obter_coorte(snapshot, selecionada)
    contagens = _contar_drift(coorte)
    faixa_alta = max(coorte.calibracao, key=lambda item: item.faixa)

    st.markdown(
        f"""
        <div class="pf-hero">
          <div class="pf-kicker">Decisão sobre uso do modelo · {coorte.coorte}</div>
          <div class="pf-thesis">O modelo ainda ordena o risco, mas esta evidência não autoriza operação.</div>
          <div class="pf-decision">{coorte.decisao}</div>
          <p class="pf-reason">{coorte.motivo} O modo de pesquisa não libera uso operacional.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cartoes = []
    for item in snapshot.coortes:
        ativo = " active" if item.coorte == selecionada else ""
        drift = _contar_drift(item)
        cartoes.append(
            f'<div class="pf-cohort{ativo}"><strong>{item.coorte}</strong>'
            f'<span>AUC {_fmt_pct(item.auc, 2) if item.auc is None else f"{item.auc:.4f}"}<br>'
            f'{drift["ALERTA"]} alertas · {drift["CRITICO"]} críticas</span></div>'
        )
    st.markdown(
        f'<div class="pf-strip">{"".join(cartoes)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="pf-section">Como ler este relatório</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="pf-guide">
          <div class="pf-guide-card">
            <strong>1. COMECE PELA DECISÃO</strong>
            <p><code>PESQUISA</code> significa que a evidência serve para aprender e monitorar.
            Ela não libera concessão de crédito nem substitui um responsável humano.</p>
          </div>
          <div class="pf-guide-card">
            <strong>2. CONFIRA A ORDEM E O NÚMERO</strong>
            <p>AUC pergunta se os casos mais arriscados ficam acima dos menos arriscados. Brier e
            calibração perguntam se a porcentagem escrita no score parece com o que aconteceu.</p>
          </div>
          <div class="pf-guide-card">
            <strong>3. INVESTIGUE ANTES DE AGIR</strong>
            <p>Drift é um aviso de que a população mudou. Ele aponta onde olhar, mas não explica
            a causa e não manda retreinar o modelo sozinho.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="pf-section">Como esta informação chega a quem decide</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="pf-delivery">
          <div class="pf-delivery-step"><strong>1. Rodar o experimento</strong>
          <span>A equipe de modelos mede cada coorte com a mesma régua.</span></div>
          <div class="pf-delivery-step"><strong>2. Gerar o Snapshot agregado</strong>
          <span>Saem apenas métricas e alertas, sem cadastro individual.</span></div>
          <div class="pf-delivery-step"><strong>3. Publicar o painel interno</strong>
          <span>O gestor de risco recebe uma visão comum para a reunião de acompanhamento.</span></div>
          <div class="pf-delivery-step"><strong>4. Decisão humana registrada</strong>
          <span>Investigar dados, manter ou revisar o modelo segue uma política aprovada.</span></div>
        </div>
        <div class="pf-now"><strong>Hoje neste projeto:</strong> as etapas 1 e 2 são reproduzíveis e
        esta tela é um protótipo local. Em uma operação real, as etapas 3 e 4 exigiriam agendamento,
        acesso autenticado, dono responsável e política de escalonamento. Isso ainda não foi implementado.
        O público final deste relatório seria o gestor de risco, não o cliente de crédito.</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="pf-section">Evidência da coorte</div>', unsafe_allow_html=True)
    col_n, col_eventos, col_auc, col_brier = st.columns(4)
    col_n.metric("Propostas avaliadas", f"{coorte.n:,}".replace(",", "."))
    col_eventos.metric("Inadimplentes", f"{coorte.inadimplentes:,}".replace(",", "."))
    col_auc.metric(
        "AUC",
        f"{coorte.auc:.4f}",
        help=f"IC95% [{coorte.auc_ic95_inferior:.4f}; {coorte.auc_ic95_superior:.4f}]",
    )
    col_brier.metric("Brier", f"{coorte.brier:.4f}", help="Quanto menor, menor o erro das probabilidades.")
    st.caption(
        f"Inadimplência observada: {_fmt_pct(coorte.taxa_inadimplencia)} "
        f"· IC95% [{_fmt_pct(coorte.taxa_ic95_inferior)}; "
        f"{_fmt_pct(coorte.taxa_ic95_superior)}] · n={coorte.n:,}"
    )

    _grafico_evolucao(snapshot)

    st.markdown('<div class="pf-section">O que investigar</div>', unsafe_allow_html=True)
    esquerda, direita = st.columns([1.05, 1.35])
    with esquerda:
        st.markdown(
            f"""
            <div class="pf-callout">
              <strong>{contagens['ALERTA']} alertas · {contagens['CRITICO']} críticas</strong><br>
              Drift mostra que a população mudou. Não prova a causa e não manda retreinar sozinho.
            </div>
            """,
            unsafe_allow_html=True,
        )
        nao_estaveis = [item for item in coorte.drift if item.status != "ESTAVEL"]
        tabela_drift = pd.DataFrame(
            [
                {
                    "Feature": item.feature,
                    "Estado": item.status,
                    "KS": f"{item.ks:.4f}",
                    "Delta ausência": _fmt_pct(item.delta_ausencia),
                }
                for item in nao_estaveis
            ]
        )
        st.dataframe(
            tabela_drift,
            hide_index=True,
            width="stretch",
        )
    with direita:
        st.markdown("**Leitura da faixa de maior risco**")
        st.markdown(
            f"Faixa {faixa_alta.faixa}: previsto **{_fmt_pct(faixa_alta.previsto)}** "
            f"e observado **{_fmt_pct(faixa_alta.observado)}** "
            f"(IC95% [{_fmt_pct(faixa_alta.observado_ic95_inferior)}; "
            f"{_fmt_pct(faixa_alta.observado_ic95_superior)}], "
            f"n={faixa_alta.n:,}, {faixa_alta.inadimplentes:,} inadimplentes). "
            f"Estado: `{faixa_alta.status}`."
        )
        st.caption(
            "AUC responde se a ordem está certa. Calibração responde se o número "
            "escrito no score corresponde ao que aconteceu."
        )

    st.markdown('<div class="pf-section">Probabilidade prometida × observada</div>', unsafe_allow_html=True)
    _grafico_calibracao(coorte)
    tabela_calibracao = pd.DataFrame(
        [
            {
                "Faixa": item.faixa,
                "n": item.n,
                "Inadimplentes": item.inadimplentes,
                "Previsto": _fmt_pct(item.previsto),
                "Observado": _fmt_pct(item.observado),
                "IC95% inferior": _fmt_pct(item.observado_ic95_inferior),
                "IC95% superior": _fmt_pct(item.observado_ic95_superior),
                "Gap": _fmt_pct(item.gap),
                "Estado": item.status,
            }
            for item in coorte.calibracao
        ]
    )
    st.dataframe(
        tabela_calibracao,
        hide_index=True,
        width="stretch",
    )

    st.markdown(
        f"""
        <div class="pf-limit">
        <strong>Limite desta evidência.</strong> Snapshot histórico de pesquisa sobre dataset público de mercado
        emergente. As seis features são proxies sem prova point-in-time. Janela de maturação declarada:
        {snapshot.janela_maturacao_dias} dias; data de referência: {snapshot.data_referencia}.
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
