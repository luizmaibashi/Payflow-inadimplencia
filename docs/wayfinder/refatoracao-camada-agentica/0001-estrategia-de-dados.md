---
tipo: grilling
status: resolvido
criado: 2026-08-04
---

# Ticket 0001: Estratégia de dados (sintético vs. real)

## Bloqueio
O dataset atual (`data/raw/payflow_credit_risk.csv`) é sintético, gerado para uma empresa fictícia ("PayFlow"). A Camada 1 (Random Forest) já está treinada e validada em produção sobre esse dado. A refatoração pode:

- **(a) Manter o dataset como está**, documentando explicitamente a limitação (como o `stable-treasury` faz na nota de rodapé "não é assessoria...").
- **(b) Manter o modelo treinado, trocar só a narrativa/contexto** do README e da documentação para ancorar em crédito real (ex: crédito pessoal/imobiliário brasileiro, citando Bacen/CVM como referência de mercado), sem retreinar nada.
- **(c) Trocar por dataset público real** (ex: Kaggle "Give Me Some Credit", ou dado agregado do SCR/Bacen) — implica **retreinar a Camada 1**, o que está fora do escopo original (a decisão de arquitetura já tomada foi preservar a Camada 1 como está).

Recomendação já dada na sessão: **(b)** — preserva o que já funciona (paridade treino-serving testada), ganha credibilidade de contexto pro caso de uso (Loft/crédito real) sem abrir uma frente de retrain que não é o foco (o foco é a Camada 2 agêntica).

## Resultado

**Decidido (2026-08-04): opção (c) — dataset público real, com retreino completo da Camada 1.**

Dataset escolhido: **Home Credit Default Risk** (Kaggle, 2018) — ver comparação completa e descartes justificados (HMDA, German Credit, Give Me Some Credit, Brasil) no ticket [0007](0007-dataset-lgd-fontes-externas.md).

### Consequências assumidas

- **A Camada 1 entra no escopo da refatoração.** O dataset novo tem esquema completamente diferente do sintético atual (`canal_aquisicao`, `regiao`, `tipo_produto` não existem no Home Credit). Portanto: EDA nova, feature engineering novo, retreino do zero. Na prática, `app/utils.py::process_credit_features` e `models/*.pkl` são reconstruídos, não adaptados.
- **O que sobrevive do projeto atual:** a *arquitetura* (deep module isolando ML, paridade treino-serving testada, API FastAPI + Streamlit desacoplados, thresholds externalizados) — não o conteúdo. O princípio de `test_paridade.py` continua válido e deve ser reescrito para o esquema novo.
- **Framing:** deixa de ser a empresa fictícia "PayFlow" com dado sintético brasileiro. Passa a ser crédito ao consumidor em mercado emergente, com rótulo real de default e **backtest real** — e com cenário macro brasileiro como stress declarado (ver ticket [0009](0009-conflito-dataset-vs-fontes-externas.md)).
- **Ganho principal:** com rótulo real, a recomendação do agente na faixa cinzenta pode ser validada contra a inadimplência que de fato ocorreu — evidência muito mais forte que eval sobre dado sintético.
