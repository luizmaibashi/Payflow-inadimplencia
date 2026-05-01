import streamlit as st
import requests

import os

# URL da API local ou via container (variável de ambiente)
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000/predict")

# Configuração da página
st.set_page_config(page_title="PayFlow - Risco de Crédito", page_icon="📊", layout="wide")

# Título e Explicação Didática
st.title("📊 PayFlow - Simulador de Risco de Crédito")
st.markdown("""
Bem-vindo ao simulador de crédito da PayFlow! 
Preencha os dados abaixo. Ao clicar em **Analisar**, este site (Front-end) enviará suas respostas para o nosso "Cérebro" na Nuvem (Back-end / API), que processará os dados no modelo de Inteligência Artificial e retornará a decisão em tempo real.
""")

# Layout em colunas
col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ Dados Pessoais")
    idade = st.number_input("Idade", min_value=18, max_value=100, value=35)
    renda_mensal = st.number_input("Renda Mensal (R$)", min_value=0.0, value=4500.0)
    tempo_emprego = st.number_input("Tempo de Emprego (Anos)", min_value=0.0, value=5.0)
    autonomo = st.selectbox("É Autônomo?", ["Não", "Sim"])
    score_credito = st.slider("Score de Crédito Serasa/SPC", min_value=0, max_value=1000, value=620)

    st.subheader("2️⃣ Dados do Empréstimo")
    valor_solicitado = st.number_input("Valor Solicitado (R$)", min_value=0.0, value=8000.0)
    prazo_meses = st.slider("Prazo (Meses)", min_value=1, max_value=72, value=24)
    juros_mensal_pct = st.number_input("Juros Mensal (%)", min_value=0.0, value=2.5)
    tipo_produto = st.selectbox("Tipo de Produto", ["Empréstimo Pessoal", "BNPL", "Cartão"])

with col2:
    st.subheader("3️⃣ Histórico de Crédito")
    qtde_cartoes = st.number_input("Qtd. de Cartões", min_value=0, value=2)
    qtde_contratos_abertos = st.number_input("Qtd. Contratos Abertos", min_value=0, value=1)
    utilizacao_credito = st.slider("Utilização do Limite de Crédito Atual (%)", min_value=0.0, max_value=100.0, value=45.0)
    inadimplencias_anteriores = st.number_input("Já teve inadimplências antes?", min_value=0, value=0)
    dias_atraso_max = st.number_input("Máximo de dias que já atrasou (12m)", min_value=0, value=10)
    reclamacoes_6m = st.number_input("Reclamações no SAC (6m)", min_value=0, value=0)
    possui_avalista = st.selectbox("Possui Avalista / Fiador?", ["Não", "Sim"])

    st.subheader("4️⃣ Outras Informações")
    canal_aquisicao = st.selectbox("Canal de Aquisição", ["App", "Loja", "Parceiro", "Site"])
    regiao = st.selectbox("Região do Cliente", ["Centro-Oeste", "Nordeste", "Norte", "Sudeste", "Sul"])

# Botão de Previsão
st.markdown("---")
if st.button("🚀 Enviar para a Inteligência Artificial (API)", use_container_width=True, type="primary"):
    
    # Montando o pacote de dados (JSON) exatamente como a API espera
    payload = {
        "idade": idade,
        "renda_mensal": renda_mensal,
        "tempo_emprego_anos": tempo_emprego,
        "autonomo": autonomo,
        "score_credito": score_credito,
        "valor_solicitado": valor_solicitado,
        "prazo_meses": prazo_meses,
        "juros_mensal_pct": juros_mensal_pct,
        "tipo_produto": tipo_produto,
        "qtde_cartoes": qtde_cartoes,
        "qtde_contratos_abertos": qtde_contratos_abertos,
        "utilizacao_credito_pct": utilizacao_credito,
        "inadimplencias_anteriores": inadimplencias_anteriores,
        "dias_atraso_max_12m": dias_atraso_max,
        "reclamacoes_6m": reclamacoes_6m,
        "possui_avalista": possui_avalista,
        "canal_aquisicao": canal_aquisicao,
        "regiao": regiao
    }
    
    with st.spinner("Conectando com o servidor no Render e calculando o risco..."):
        try:
            # Enviando via requisição HTTP POST para a nuvem
            resposta = requests.post(API_URL, json=payload)
            
            if resposta.status_code == 200:
                dados_retorno = resposta.json()
                
                probabilidade = dados_retorno["probabilidade_inadimplencia"]
                decisao = dados_retorno["decisao_sugerida"]
                msg = dados_retorno["mensagem_alerta"]
                comprometimento = dados_retorno["comprometimento_renda_pct"]
                
                st.subheader("📋 Resultado Oficial da Análise")
                colA, colB, colC = st.columns(3)
                
                colA.metric("Probabilidade de Calote", f"{probabilidade:.1%}")
                colB.metric("Decisão Recomendada", decisao)
                colC.metric("Comprometimento de Renda", f"{comprometimento:.1%}")
                
                if decisao == "APROVAR":
                    st.success(f"✅ **APROVADO:** {msg}")
                elif decisao == "REVISAR":
                    st.warning(f"⚠️ **ALERTA:** {msg}")
                else:
                    st.error(f"❌ **NEGADO:** {msg}")
                    
            else:
                st.error(f"Erro na API: {resposta.status_code} - {resposta.text}")
                
        except Exception as e:
            st.error(f"Não foi possível conectar à API. Verifique sua conexão. Erro: {e}")
