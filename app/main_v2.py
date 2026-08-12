"""Demo estática da V2 — Camada 2 (agente de underwriting).

NAO gera memo novo, NAO chama LLM. Le os 564 memos ja gerados
(data/processed/piloto_camada2_memos.jsonl), os veredictos do juiz
(data/labels/juiz_task_completion.json) e os labels humanos
(data/labels/task_completion_labels.json), cruza com o desfecho real
(data/processed/zona_cinzenta.parquet) e deixa navegar caso a caso.

POR QUE ESTATICA (decisao 2026-08-12): o backtest do debito #34 ja
mediu que o agente nao separa risco de forma detectavel na zona
cinzenta (AUC do modelo campeao ali e 0.56, quase acaso). O objetivo
desta tela e mostrar a ARQUITETURA funcionando (memo auditavel,
groundado, juiz LLM, cegueira ao score) para quem avalia o projeto -
nao fingir que decide bem. Gerar memo novo ao vivo exigiria reativar
o faturamento do GCP (desvinculado de proposito) sem agregar ao
objetivo declarado.

Uso: streamlit run app/main_v2.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
MEMOS_PATH = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
JUIZ_PATH = RAIZ / "data" / "labels" / "juiz_task_completion.json"
LABELS_PATH = RAIZ / "data" / "labels" / "task_completion_labels.json"
ZONA_PATH = RAIZ / "data" / "processed" / "zona_cinzenta.parquet"

st.set_page_config(
    page_title="PayFlow V2 — Camada 2 (agente de underwriting)",
    page_icon="🧾",
    layout="wide",
)


@st.cache_data
def carregar_dados():
    memos = {}
    with MEMOS_PATH.open(encoding="utf-8") as fh:
        for linha in fh:
            reg = json.loads(linha)
            if reg.get("memo"):
                memos[reg["sk_id_curr"]] = reg

    juiz_dados = json.loads(JUIZ_PATH.read_text(encoding="utf-8"))
    juiz = {j["sk_id_curr"]: j for j in juiz_dados["julgados"]}

    labels_dados = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    humanos = {
        l["sk_id_curr"]: l["task_completion"]
        for l in labels_dados["labels"]
        if l["task_completion"]["veredito"]
    }

    zona = pd.read_parquet(ZONA_PATH)
    target_por_id = dict(zip(zona["SK_ID_CURR"], zona["TARGET"]))

    linhas = []
    for sk_id, reg in memos.items():
        if sk_id not in target_por_id:
            continue
        linhas.append({
            "sk_id_curr": sk_id,
            "recomendacao": reg["memo"]["recomendacao"],
            "TARGET": target_por_id[sk_id],
            "avaliado_juiz": sk_id in juiz,
            "avaliado_humano": sk_id in humanos,
            "veredito_juiz": juiz.get(sk_id, {}).get("juiz"),
            "veredito_humano": humanos.get(sk_id, {}).get("veredito"),
        })

    tabela = pd.DataFrame(linhas)
    return tabela, memos, juiz, humanos


def badge_recomendacao(rec: str) -> str:
    cores = {"APROVAR": "🟢", "NEGAR": "🔴", "DEFERIR": "🟡"}
    return f"{cores.get(rec, '⚪')} {rec}"


def badge_target(target: int) -> str:
    return "🔴 Defaultou (TARGET=1)" if target == 1 else "🟢 Não defaultou (TARGET=0)"


def render_fatos(memo: dict):
    simbolo = {"favoravel": "＋", "desfavoravel": "－", "neutro": "·"}
    for f in memo["fatores_cliente"]:
        st.markdown(f"{simbolo.get(f['peso'], '·')} {f['fato']}  \n`fonte: {f['fonte_tool']}`")


def render_trace(trace: list):
    for c in trace:
        with st.expander(f"🔧 `{c['ferramenta']}`", expanded=False):
            st.json(c["retorno"])


def main():
    tabela, memos, juiz, humanos = carregar_dados()

    st.title("🧾 PayFlow V2 — Camada 2: agente de underwriting")
    st.caption(
        "Demo estática — navega pelos 564 casos já processados na zona cinzenta "
        "(sem gerar memo novo, sem chamada de API)."
    )

    st.warning(
        "**Leitura honesta antes de navegar:** o backtest deste projeto (débito #34, "
        "n=564, poder estatístico real) mediu que o agente **não separa risco real de "
        "forma detectável** nesta população — e nem o melhor modelo do projeto separa "
        "(AUC 0,56 dentro da zona cinzenta, contra 0,776 na população inteira). "
        "Esta tela existe para mostrar a **arquitetura** funcionando (memo auditável, "
        "groundado, avaliado por um juiz LLM, cego ao score) — não para sugerir que "
        "a recomendação de um caso individual está correta. "
        "[Detalhamento completo no AGENTS.md](https://github.com/luizmaibashi/Payflow-inadimplencia/blob/main/AGENTS.md#custo-acumulado--geminigcp-reconstru%C3%ADdo-2026-08-12)."
    )

    aba_casos, aba_stats = st.tabs(["🔍 Explorar casos", "📊 Números do backtest"])

    with aba_casos:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filtro_rec = st.multiselect(
                "Recomendação do agente", ["APROVAR", "NEGAR", "DEFERIR"],
                default=["APROVAR", "NEGAR", "DEFERIR"],
            )
        with col_f2:
            filtro_target = st.selectbox(
                "Desfecho real", ["Todos", "Defaultou", "Não defaultou"],
            )
        with col_f3:
            filtro_avaliado = st.selectbox(
                "Avaliação", ["Todos", "Avaliado pelo juiz", "Revisado por humano"],
            )

        vista = tabela[tabela["recomendacao"].isin(filtro_rec)]
        if filtro_target == "Defaultou":
            vista = vista[vista["TARGET"] == 1]
        elif filtro_target == "Não defaultou":
            vista = vista[vista["TARGET"] == 0]
        if filtro_avaliado == "Avaliado pelo juiz":
            vista = vista[vista["avaliado_juiz"]]
        elif filtro_avaliado == "Revisado por humano":
            vista = vista[vista["avaliado_humano"]]

        st.caption(f"{len(vista)} de {len(tabela)} casos correspondem ao filtro")

        if vista.empty:
            st.info("Nenhum caso corresponde a esse filtro.")
            return

        opcoes = vista["sk_id_curr"].tolist()
        sk_id = st.selectbox(
            "Escolha um cliente (SK_ID_CURR)", opcoes,
            format_func=lambda x: (
                f"{x} — {vista.loc[vista['sk_id_curr']==x, 'recomendacao'].iloc[0]}"
            ),
        )

        reg = memos[sk_id]
        memo = reg["memo"]
        linha = tabela[tabela["sk_id_curr"] == sk_id].iloc[0]

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader(badge_recomendacao(memo["recomendacao"]))
        with col_b:
            st.subheader(badge_target(int(linha["TARGET"])))

        col_c, col_d = st.columns(2)
        with col_c:
            st.markdown("### Fatos citados pelo agente")
            render_fatos(memo)
            if memo.get("informacao_faltante"):
                st.markdown("**Informação declarada como faltante:**")
                for i in memo["informacao_faltante"]:
                    st.markdown(f"- {i}")
        with col_d:
            st.markdown("### Dados brutos consultados")
            render_trace(reg["trace"])

        st.markdown("### Avaliação")
        col_e, col_f = st.columns(2)
        with col_e:
            if linha["avaliado_juiz"]:
                j = juiz[sk_id]
                icone = "✅" if j["juiz"] == "OK" else "❌"
                st.markdown(f"**Juiz LLM:** {icone} `{j['juiz']}`")
                st.caption(j.get("evidencia_juiz", ""))
                if j.get("suspeito_dado_ausente"):
                    st.markdown(
                        "⚠️ **Marcado como suspeito pelo detector do débito #33** — "
                        "a evidência do juiz admite ausência de dado, que não deveria "
                        "por si só justificar `FALHA`."
                    )
            else:
                st.caption("Não avaliado pelo juiz (cota da API travou antes de chegar aqui).")
        with col_f:
            if linha["avaliado_humano"]:
                h = humanos[sk_id]
                icone = "✅" if h["veredito"] == "OK" else "❌"
                st.markdown(f"**Revisor humano:** {icone} `{h['veredito']}`")
                st.caption(h.get("evidencia", ""))
            else:
                st.caption("Não revisado por humano (ground truth cobre 87 dos 722 casos).")

    with aba_stats:
        st.markdown("### Resultado do backtest (débito #34)")
        st.markdown(
            "| Recomendação | Taxa de default real | IC95% |\n"
            "|---|---|---|\n"
            "| APROVAR | 32,7% | [27,3%; 38,6%] |\n"
            "| NEGAR | 34,0% | [28,9%; 39,5%] |\n"
        )
        st.metric(
            "Separação NEGAR − APROVAR", "+1,3%",
            help="IC95% [-6,7%; +9,2%] — cruza zero. Não há separação detectável.",
        )
        st.metric(
            "AUC do modelo campeão dentro da zona cinzenta", "0,5612",
            help="Contra 0,776 na população inteira e 0,50 = acaso puro.",
        )
        st.markdown(
            "Investigação completa (3 hipóteses testadas, 2 checagens de robustez, "
            "correção pública de uma hipótese própria no mesmo dia) no débito #34 do "
            "[`AGENTS.md`](https://github.com/luizmaibashi/Payflow-inadimplencia/blob/main/AGENTS.md) "
            "e no [`README.md`](https://github.com/luizmaibashi/Payflow-inadimplencia)."
        )


if __name__ == "__main__":
    main()
