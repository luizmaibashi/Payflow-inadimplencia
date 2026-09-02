<p align="center">
  <img src="reports/figures/banner_payflow.png" alt="PayFlow - Previsão de Risco de Crédito" width="100%"/>
</p>

<h1 align="center">PayFlow: Previsão de Risco de Crédito</h1>

<p align="center">
  <strong>Projeto de portfólio | Camada 1 (PD sobre dado real) + Camada 2 (agente de underwriting) medidas com rigor estatístico. Inclui um resultado negativo, investigado até a causa raiz</strong>
</p>
<p align="center">
  <sub>Versão anterior com dado sintético preservada como registro histórico em <a href="docs/LEGADO_V1.md">docs/LEGADO_V1.md</a></sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Scikit--Learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white"/>
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/>
  <img src="https://img.shields.io/badge/Gemini_%2F_Groq-LLM_agent-4285F4?style=for-the-badge&logoColor=white"/>
</p>

---

## Estado atual (2026-08-12)

A **V2** reconstrói a Camada 1 sobre dado real com outcome de default ([Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk)) e adiciona uma camada agêntica de underwriting (LLM) com avaliação formal: juiz calibrado, ADRs documentando cada decisão de risco (12 até aqui, [`docs/adr/`](docs/adr/)), débitos técnicos numerados e vivos ([`AGENTS.md`](AGENTS.md)).

**O que já está medido na V2:** modelo treinado sobre dado real (AUC 0,776, IC95%), zona cinzenta isolada (2.102 casos, 4,3× a taxa de default da carteira), agente com juiz LLM calibrado contra rubrica explícita ([ADR-0011](docs/adr/0011-criterio-de-task-completion.md), 2 bugs de raciocínio achados e corrigidos), 87/87 labels de ground truth como julgamento humano deliberado.

**A contribuição central do projeto (o backtest que mede se as recomendações do agente separam risco real de fato) está medida, com poder estatístico, e a resposta é honesta e desconfortável.** Amostra estendida de 722 casos (`scripts/backtest_camada2.py`, débito #34, 2026-08-11, ~US$7,52; mesma extração determinística da amostra de 86 anterior, seed reusada de propósito para reprodutibilidade): 563 memos válidos, `n=564` no backtest final. Taxa de default real: `APROVAR` 32,7% [27,3%; 38,6%], `NEGAR` 34,0% [28,9%; 39,5%]. **Separação NEGAR−APROVAR: +1,3%, IC95% [-6,7%; +9,2%], cruza zero com folga, resultado estável em 5 seeds de bootstrap testadas.** Com `n` suficiente pra detectar 10pp, **o agente não demonstra separar risco real de forma estatisticamente detectável** dentro da zona cinzenta. Isso não invalida a arquitetura (memo auditável, groundado, cego ao score são propriedades valiosas por si), mas invalida qualquer alegação de que "o agente decide melhor que o acaso" sem essa qualificação. Ver débito #34 no `AGENTS.md` para verificação completa e hipóteses não testadas sobre a causa.

### O que esse resultado significa

A pergunta que motivou o backtest era simples: o agente separa risco real melhor que o acaso, ou só parece bom porque ninguém mediu direito? A primeira medição (`n=86`, ad-hoc) dava uma separação de +7,2pp, um número que parece bom, mas com intervalo de confiança largo o bastante pra cruzar zero. Em vez de aceitar esse número, o passo seguinte foi calcular quanto `n` seria necessário pra confiar num resultado (poder estatístico 0,80, separação de 10pp → ~722 casos) e gastar o que isso custava (~US$7,52, ~4h) de propósito, em vez de rodar "o quanto der" e torcer.

Com `n` suficiente, a separação caiu pra +1,3pp. O intervalo cruza zero com folga, e o resultado é estável em múltiplas seeds de bootstrap testadas. **O agente não separa risco real de forma detectável na zona cinzenta.**

O passo mais importante não foi medir isso, foi investigar por quê, em vez de parar em "não funcionou". Primeira hipótese: os sinais que o critério do agente usa pra justificar `NEGAR` (utilização de crédito, pior atraso, déficit de pagamento) têm correlação essencialmente **zero** com o `TARGET` real: clientes com "sinal grave" presente até defaultam **menos** que os sem sinal (30,8% vs. 33,7%). A hipótese seguinte foi mais ambiciosa: talvez o agente só não tivesse acesso ao sinal certo. O modelo campeão da Camada 1 (AUC 0,776) é dominado por três variáveis (`EXT_SOURCE_1/2/3`, escores de crédito externos) que o agente nunca vê. Testar essa ideia contra os dados **antes** de gastar API revelou o oposto: dentro da zona cinzenta especificamente, `EXT_SOURCE` também perde quase toda a correlação com `TARGET` (de -0,16/-0,18 no dataset inteiro pra -0,02/-0,04 ali). E o teste final, mais direto de todos: **o AUC do próprio modelo campeão, calculado só dentro da zona cinzenta, é 0,5612, IC95% [0,5368; 0,5846]** (0,50 é acaso puro, 0,776 é o AUC dele na população inteira). Ver [`reports/auc_zona_cinzenta.md`](reports/auc_zona_cinzenta.md).

Isso muda a conclusão de "o critério do agente é ruim" pra algo mais fundamental: **a zona cinzenta, definida pelos dados do Home Credit disponíveis, está genuinamente perto do limite do que é previsível.** O melhor classificador que este projeto já construiu, com acesso a toda variável disponível e relações não-lineares, mal bate a moeda especificamente na fatia onde o agente decide.

Uma precisão que o intervalo trouxe e o ponto sozinho escondia: **o IC não contém 0,50**. A afirmação exata é "o modelo discrimina fracamente, mas de forma detectável", não "é indistinguível de uma moeda". A diferença importa porque a segunda é mais forte do que o dado sustenta, e este projeto já corrigiu erro parecido antes (débito #14). Duas explicações alternativas para esse 0,56 foram testadas e descartadas: não é artefato da calibração isotônica (o score bruto, sem nenhum empate, dá 0,5643 com intervalo praticamente sobreposto) e não é fronteira desenhada larga demais (as três sub-fatias por proximidade ao centro da banda ficam **abaixo** do AUC da zona inteira, com intervalos corrigidos por Bonferroni). Não é falta de ferramenta certa. É que a decisão ali é estruturalmente próxima de aleatória com os dados que existem, e essa conclusão resistiu a três ângulos de ataque diferentes.

Uma quarta hipótese foi testada em 2026-09-01 e também não sustentou: talvez a média global escondesse separação nos casos em que o agente tinha evidência clara. Segmentando os 564 memos pela unanimidade da evidência citada, **nenhum grupo separa risco de forma detectável**, nem o de evidência mais unânime ([`reports/separacao_por_confianca.md`](reports/separacao_por_confianca.md)). Os pontos crescem na direção que a hipótese previa (−3,7 → +2,0 → +5,5pp), mas os intervalos têm ~30pp de largura e todos cruzam zero: o teste descarta um sinal **grande** escondido ali, não um pequeno. Com n≈190 por grupo, o estudo está ~4× subdimensionado, e a leitura honesta é "não achamos", não "não existe".

Isso não é "agentes LLM não decidem crédito bem". É uma afirmação mais específica e mais interessante sobre os limites do próprio dataset. Detalhamento completo da investigação, incluindo os números de cada verificação, está no débito #34 do [`AGENTS.md`](AGENTS.md).

**Demo (`app/main_v2.py`):** navega os 564 casos já processados da zona cinzenta: memo do agente, dados brutos consultados, veredito do juiz, e o desfecho real (`TARGET`), com a limitação do débito #34 (AUC 0,56 na zona) explícita na própria tela. **Deliberadamente estática**: não gera memo novo, não chama LLM, não depende do faturamento do GCP (desvinculado em 2026-08-12). O objetivo é mostrar a arquitetura (memo auditável, groundado, avaliado por juiz, cego ao score) funcionando, não sugerir que o agente decide bem nesta população.

```bash
pip install -r requirements.txt
streamlit run app/main_v2.py
```

*(A demo da V1, Streamlit Cloud + Render, dado sintético, foi despublicada em 2026-08-11, débito #11, pra não ser confundida com o estado atual do projeto.)*

---

## Arquitetura

```
Home Credit ──► CAMADA 1 (PD, calibrada) ──► MOTOR DE DECISÃO (valor esperado
                                              por observação: p* = M/(M+LGD·EAD))
                                                    │
                                       só a ZONA CINZENTA
                                                    ▼
                              CAMADA 2: agente (NÃO vê p_default)
                              tools de CASO (multi-hop) + tool de CENÁRIO (1×/lote)
                                       → memo JSON (APROVAR|NEGAR|DEFERIR)
                                                    │
                        ┌───────────────────────────┼───────────────────────┐
                     JUIZ LLM                  DEMO ESTÁTICA             BACKTEST
                (rubrica ADR-0011,          (app/main_v2.py,           (débito #34,
                 validação determinística    navega os 564 casos        MEDIDO: AUC
                 pós-resposta, ADR-0012)     já processados)             0,56 na zona)
```

**Ponto crítico do desenho:** o agente forma parecer **independente** do score (`p_default` nunca entra no contexto: garantido por schema, não por disciplina, [ADR-0003](docs/adr/0003-contrato-do-memo-e-agente-cego-ao-score.md)). O confronto parecer × score acontece depois, no backtest, e é o que permitiu medir, e não supor, que o agente não agrega separação de risco mensurável nesta população.

**Sobre a tela de revisão humana (produção):** decisão de escopo **tomada, não pendente**: não foi construída de propósito. Uma tela de revisão de verdade faz sentido pra um sistema em produção, decidindo crédito real; não faz sentido investir nisso depois que o próprio backtest mostrou que o agente não agrega separação de risco mensurável nesta população (débito #34). O que existe em vez disso é a demo estática acima, que mostra a arquitetura (memo, juiz, dados brutos) sem fingir que há um fluxo de produção por trás.

## O que este projeto assume abertamente

- **O dataset é de mercados emergentes, não do Brasil.** A transferência é de **método**, declarada. O contexto macro brasileiro (BCB/IBGE) entra apenas como cenário de stress rotulado, deslocando a premissa de perda dada a inadimplência, nunca como atributo do cliente ([ADR-0008](docs/adr/0008-cenario-macro-brasileiro-pela-lgd.md)).
- **A LGD (70-85%) é premissa, não medição.** Ancorada em literatura internacional; não existe número público do Banco Central para crédito pessoal brasileiro.
- **Não há decisão de crédito autônoma.** O agente propõe e um humano decide. "Deferir" é ação de primeira classe, embora medido em apenas 0,18% dos casos do backtest (débito #34); decisão deliberada anterior (débito #28), não descuido.
- **Sem consulta a bureau individual**: não existe API pública no Brasil, e o projeto não finge consultar o que não pode.
- **A zona cinzenta está perto do limite do previsível com os dados disponíveis** (débito #34), dito acima e repetido aqui porque é o achado mais importante do projeto, não um detalhe a esconder na lista.

Os débitos técnicos completos, numerados e vivos, estão em [`AGENTS.md`](AGENTS.md#débitos-técnicos-conhecidos): 34 até aqui, a maioria fechada, os últimos com a investigação completa do backtest.

---

## Metodologia: CRISP-DM

| Fase | O que foi feito na V2 |
|------|-----------|
| 1. Entendimento do Negócio | ADRs 0001-0002: dor, ROI, `p*` derivado (não arbitrário), baseline declarado |
| 2. Entendimento dos Dados | EDA completa do Home Credit (`reports/eda_application.md`, `reports/eda_tabelas_relacionais.md`) + **teto de previsibilidade da zona cinzenta medido antes de decidir investir na Camada 2** (lição extraída pra `metodologia/AI_ENGINEERING/11_teto_de_previsibilidade.md` na base de conhecimento do autor) |
| 3. Preparação dos Dados | Agregação de 5 tabelas relacionais (bureau, previous_application, installments, POS_CASH, credit_card), split treino/calibração/teste antes de qualquer processamento |
| 4. Modelagem | `HistGradientBoostingClassifier` + calibração isotônica (Camada 1) + agente LLM com ferramentas de caso/cenário (Camada 2) |
| 5. Avaliação | AUC/Brier com IC bootstrap (Camada 1); juiz LLM calibrado contra 87 labels humanos + backtest com poder estatístico real (Camada 2); ver débito #34 |
| 6. Deploy | Demo estática (`app/main_v2.py`): decisão consciente de não reativar API paga pra uma tela de exibição |

## Estrutura do projeto

```
payflow_inadimplencia/
├── app/
│   ├── agente_underwriting.py    # Orquestração multi-hop da Camada 2
│   ├── ferramentas_caso.py       # Tools de caso (bureau, pagamentos)
│   ├── ferramenta_cenario.py     # Tool de cenário macro (BCB), 1x/lote
│   ├── memo_credito.py           # Contrato do parecer (Pydantic)
│   ├── juiz_camada2.py           # Juiz LLM + detector determinístico (#33)
│   ├── clientes_llm.py           # Adaptadores Gemini/Groq
│   ├── motor_decisao.py          # Motor de decisão por valor esperado
│   ├── main_v2.py                # Demo Streamlit da V2 (atual)
│   └── main.py, api.py, service.py, utils.py, schemas.py  # V1 (legado)
├── scripts/                      # Treino, EDA, calibração, backtest; ver AGENTS.md
├── docs/
│   ├── adr/                      # 13 ADRs, decisões de arquitetura
│   ├── DICIONARIO_DADOS.md
│   └── LEGADO_V1.md              # Narrativa completa da V1
├── data/labels/, data/processed/ # Ground truth e memos versionados (débitos #30/#31)
├── reports/                      # Backtest, calibração do juiz, EDAs, gates
├── models/                       # Camada 1 (V2) + modelo legado (V1)
├── tests/                        # 169 testes
├── AGENTS.md                     # Débitos técnicos + ADRs, vivo
└── README.md
```

## Material de apoio

| O quê | Onde |
|---|---|
| **Resultado do backtest (a pergunta central do projeto)** | [`reports/backtest_camada2.md`](reports/backtest_camada2.md) |
| Calibração do juiz LLM | [`reports/calibracao_juiz.md`](reports/calibracao_juiz.md) |
| Treino e métricas da Camada 1 | [`reports/camada1_treino_final.md`](reports/camada1_treino_final.md) |
| EDA (application + tabelas relacionais) | [`reports/eda_application.md`](reports/eda_application.md), [`reports/eda_tabelas_relacionais.md`](reports/eda_tabelas_relacionais.md) |
| Dicionário de dados (colunas + features criadas) | [`docs/DICIONARIO_DADOS.md`](docs/DICIONARIO_DADOS.md) |
| Todas as decisões de arquitetura (13 ADRs) | [`docs/adr/`](docs/adr/) |
| Débitos técnicos, numerados e vivos (34) | [`AGENTS.md`](AGENTS.md) |
| Versão anterior (dado sintético) | [`docs/LEGADO_V1.md`](docs/LEGADO_V1.md) |

---

## Nota sobre o uso de Inteligência Artificial

Este projeto foi construído com IA como parceira ativa de engenharia, não só de código, mas de rigor: a checagem que refutou a primeira hipótese sobre `EXT_SOURCE` (ADR-0013), os testes de robustez do backtest, e a investigação em camadas até o AUC 0,56 foram conduzidos junto com um agente de IA, com decisões de escopo e interpretação sempre confirmadas antes de virar código ou texto final. O objetivo declarado nunca foi esconder isso, é documentar como um resultado negativo, bem medido, também é entregável.

## Autor

**Luiz Fernando Saguma Maibashi**
- Economista | Pós-Tech AI Scientist FIAP
- São Paulo - SP
- [![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/luiz-fernando-maibashi-515073212/)
- [![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat&logo=github&logoColor=white)](https://github.com/luizmaibashi)
