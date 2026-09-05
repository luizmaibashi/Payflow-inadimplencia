<p align="center">
  <img src="reports/figures/banner_payflow.png" alt="PayFlow - Previsão de Risco de Crédito" width="100%"/>
</p>

<h1 align="center">PayFlow: Previsão de Risco de Crédito</h1>

<p align="center">
  <strong>Projeto de portfólio sobre decisão de crédito, limites de modelos e monitoramento de confiabilidade ao longo do tempo</strong>
</p>
<p align="center">
  <sub>Versão anterior com dado sintético preservada como registro histórico em <a href="docs/LEGADO_V1.md">docs/LEGADO_V1.md</a></sub>
</p>

---

## A dor, explicada simples

Imagine que você tem uma pilha de brinquedos e um monte de amigos pedindo emprestado. Alguns amigos sempre devolvem certinho: pode emprestar sem pensar duas vezes. Outros nunca devolvem: melhor nem emprestar. Fácil decidir nos dois extremos.

O problema é o meio do grupo: os amigos que você **não tem certeza**. Não são os melhores, não são os piores. Emprestar pra eles é uma aposta.

É basicamente o problema de um banco decidindo empréstimos:

- Cliente que claramente vai pagar → aprova na hora.
- Cliente que claramente não vai pagar → recusa na hora.
- Um grupo no meio, difícil de julgar (chamamos aqui de **zona cinzenta**). É aí que o banco mais erra e mais perde dinheiro.

Este projeto parte de duas perguntas:

1. **Dá pra ensinar um assistente de IA a julgar melhor esse grupo difícil?** Em vez de só olhar um número de pontuação, o assistente investiga o histórico de cada pessoa como um detetive: consulta pagamentos antigos, dívidas, comportamento, e escreve um parecer justificado.
2. **Depois que um modelo aprende a decidir, ele continua bom pra sempre?** Ou vai "envelhecendo" conforme o mundo muda, como um mapa antigo que não mostra a rua nova do bairro?

As respostas foram medidas com rigor estatístico (intervalo de confiança, tamanho de amostra, testes de robustez), não com achismo. E uma delas é desconfortável: contar isso também é parte do trabalho.

---

## Resumo executivo

| Pergunta | Resposta medida | Onde aprofundar |
|---|---|---|
| A IA decide o grupo difícil melhor que o acaso? | **Não, de forma detectável.** Resultado negativo, medido com poder estatístico e investigado a fundo (não só reportado). | [Investigação V2](#investigação-v2-a-ia-decide-melhor-que-o-acaso) |
| O modelo continua confiável quando chegam clientes novos? | **Sim, nas safras testadas**, mas ainda como pesquisa, não como decisão autorizada. | [Confiabilidade V3](#confiabilidade-v3-o-modelo-ainda-serve-amanhã) |

O repositório tem dois entregáveis, cada um respondendo a uma pergunta:

- **Demo V2** (`app/main_v2.py`): mostra a investigação do assistente de IA e por que o resultado deu negativo.
- **Dashboard V3** (`app/monitoramento_v3.py`): mostra se o placar de risco continua confiável em clientes novos, com AUC, calibração e alerta de mudança de padrão (*drift*).

A V1, com dado sintético, existe só como registro histórico em [`docs/LEGADO_V1.md`](docs/LEGADO_V1.md); o runtime dela foi removido ([ADR-0021](docs/adr/0021-remocao-do-runtime-v1.md)).

```bash
pip install -r requirements.txt
streamlit run app/monitoramento_v3.py   # Dashboard V3: confiabilidade
streamlit run app/main_v2.py            # Demo V2: investigação do assistente
```

---

## Confiabilidade V3: o modelo ainda serve amanhã?

A V2 (abaixo) respondeu uma pergunta difícil com um resultado negativo. A V3 parte desse aprendizado e muda a pergunta: quando chega uma safra nova de contratos, **o modelo ainda representa o comportamento atual, ou estamos decidindo com um retrato velho?**

**O experimento:** o modelo foi treinado com dados até setembro de 2019 e testado em três safras futuras, sobre 1.526.659 propostas.

| Safra testada | AUC (poder de discriminação) |
|---|---|
| Coorte 1 | 0,6148 |
| Coorte 2 | 0,6089 |
| Coorte 3 | 0,6194 |

*(AUC vai de 0,5, jogar moeda, a 1,0, discriminação perfeita. Cada número acima vem com tamanho de amostra, contagem de inadimplentes e intervalo de confiança, não só o ponto.)*

**Ainda é pesquisa, não decisão real.** As seis variáveis usadas não têm prova de que estavam disponíveis no exato instante da concessão, e a janela de 90 dias foi declarada só para a demonstração. Por isso o sistema sempre devolve `PESQUISA`, nunca `MANTER`, e se AUC ou Brier piorarem além da tolerância, devolve `REVISAR`.

**Vigilância automática (drift):** o sistema verifica se os clientes novos estão "diferentes demais" dos antigos. Na safra `2020-H2`, três das seis variáveis mudaram de distribuição (`annuity_780A`, `inittransactionamount_650A` mudaram de padrão; `price_1097A` teve mais dados ausentes, de 14,39% para 21,26%), e nenhuma entrou em estado crítico. A AUC continuou em torno de 0,61: a população mudou, mas sem sinal de queda na capacidade de discriminar risco. O monitor aponta onde investigar; ele não prova a causa nem retreina sozinho.

**Calibração: a pergunta que a AUC não responde.** Não basta o modelo *ordenar* bem quem é mais arriscado, o número que ele entrega também precisa **bater com a realidade**. Dez faixas de score foram fixadas pelos quantis do treino e reaplicadas às três safras. Em `2020-H2`, nove das dez ficaram dentro da tolerância prática de 1 ponto percentual. Na faixa de maior risco, o modelo previu 5,25% de inadimplência e a realidade foi 5,35% (708 eventos em 13.241 propostas, IC95% [4,98%; 5,74%]): a cauda mais arriscada continuou aproximadamente calibrada mesmo com a população mudando.

```bash
python scripts/proxy_estabilidade_reproduzivel.py --data-referencia 2021-01-04 --janela-dias 90 --bootstrap 100
```

O dashboard V3 lê só o snapshot agregado e versionado (nunca dado bruto nem API externa) e mostra tamanho de amostra, eventos e intervalos ao lado de cada métrica, nunca um número isolado.

```bash
streamlit run app/monitoramento_v3.py
```

Desenho técnico completo nas [specs 0007 a 0011](docs/spec/). Ligação com o conteúdo da Pós-Tech na [matriz de conhecimento](docs/MATRIZ_POS_TECH_PAYFLOW.md).

---

## Investigação V2: a IA decide melhor que o acaso?

A **V2** reconstrói a Camada 1 sobre dado real com outcome de default ([Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk)) e adiciona uma camada agêntica de underwriting (LLM), com avaliação formal: juiz calibrado, decisões registradas em [`docs/adr/`](docs/adr/), débitos numerados em [`AGENTS.md`](AGENTS.md).

**Já medido antes do assistente entrar em cena:**
- Modelo treinado sobre dado real, AUC 0,776 (IC95%).
- Zona cinzenta isolada: 2.102 casos, 4,3× a taxa de default da carteira inteira.
- Juiz LLM calibrado contra rubrica explícita ([ADR-0011](docs/adr/0011-criterio-de-task-completion.md)), 2 bugs de raciocínio achados e corrigidos.
- 87/87 labels de referência são julgamento humano deliberado, não conferência mecânica de número.

### A pergunta central, e a resposta desconfortável

A primeira medição, com poucos casos (`n=86`, ad-hoc), sugeria que o assistente separava risco 7,2 pontos percentuais melhor que o acaso, número bom, mas com intervalo largo o bastante pra cruzar zero. Em vez de aceitar isso, calculamos quantos casos seriam necessários pra confiar num resultado (poder estatístico 0,80, separação de 10pp → ~722 casos) e gastamos o que isso custava de propósito: ~US$7,52, ~4 horas.

Com amostra suficiente (563 memos válidos, `n=564` no backtest final):

| Grupo | Taxa de default real |
|---|---|
| Assistente recomendou `APROVAR` | 32,7% [27,3%; 38,6%] |
| Assistente recomendou `NEGAR` | 34,0% [28,9%; 39,5%] |

**Separação NEGAR menos APROVAR: +1,3 pontos percentuais, IC95% [-6,7%; +9,2%], cruza zero com folga.** Estável em 5 seeds de bootstrap testadas. **O assistente não demonstra separar risco real de forma estatisticamente detectável na zona cinzenta.**

Isso não invalida a arquitetura em si (parecer auditável, com evidência citada, e cego ao score do modelo continuam propriedades valiosas), mas invalida qualquer alegação de que "a IA decide melhor que o acaso" sem essa qualificação.

### Por que isso aconteceu: a investigação, não só o número

O passo mais importante não foi medir, foi investigar a causa em vez de parar em "não funcionou":

1. **Hipótese 1: os sinais usados pelo assistente não têm relação com o resultado real.** Confirmada: clientes com "sinal grave" presente (uso alto de crédito, atraso, déficit de pagamento) até defaultam **menos** que os sem sinal (30,8% vs. 33,7%).
2. **Hipótese 2: talvez faltasse o dado certo.** O modelo campeão da Camada 1 (AUC 0,776 no total) é dominado por três variáveis externas (`EXT_SOURCE_1/2/3`) que o assistente nunca vê. Testamos essa ideia contra o dado **antes** de gastar API, e o resultado foi o oposto do esperado: dentro da zona cinzenta, essas mesmas variáveis também perdem quase toda a correlação com o resultado real (de -0,16/-0,18 no todo, para -0,02/-0,04 ali).
3. **Teste mais direto:** o AUC do próprio modelo campeão, calculado só dentro da zona cinzenta, é **0,5612**: quase moeda (0,50), muito longe do 0,776 que ele atinge na população inteira.

**Conclusão: não é que o critério do assistente seja ruim, é que essa fatia de clientes, com os dados disponíveis do Home Credit, está genuinamente perto do limite do que é previsível.** O melhor classificador que este projeto já construiu, com acesso a toda variável e relação não-linear disponível, mal bate a moeda especificamente onde o assistente decide.

Uma leitura mais precisa que o intervalo de confiança trouxe: **o IC não contém 0,50.** A afirmação correta é "discrimina fracamente, mas de forma detectável", não "indistinguível de uma moeda": a segunda seria mais forte do que o dado sustenta. Duas explicações alternativas para o 0,56 foram testadas e descartadas: não é artefato de calibração (o score bruto, sem empates, dá 0,5643, intervalo quase sobreposto) e não é fronteira mal desenhada (sub-fatias por proximidade ao centro da banda ficam **abaixo** do AUC da zona inteira, com correção de Bonferroni). A conclusão resistiu a três ângulos de ataque.

Uma quarta hipótese, testada em 2026-09-01: talvez a média global escondesse separação nos casos onde o assistente tinha evidência mais unânime. Segmentando os 564 casos por unanimidade da evidência citada, nenhum grupo separou risco de forma detectável, mas os pontos cresceram na direção prevista (−3,7 → +2,0 → +5,5pp), com intervalos de ~30pp de largura. Leitura honesta: "não achamos sinal grande", não "não existe sinal nenhum". O estudo ficou ~4× subdimensionado pra detectar algo pequeno ([`reports/separacao_por_confianca.md`](reports/separacao_por_confianca.md)).

**Isso não é "assistentes de IA não decidem crédito bem".** É uma afirmação mais específica: os limites do próprio dataset, na fatia mais difícil, são estreitos demais pra qualquer classificador testado aqui, humano ou IA. Detalhamento completo no débito #34 do [`AGENTS.md`](AGENTS.md).

**Demo (`app/main_v2.py`):** navega os 564 casos já processados da zona cinzenta (parecer do assistente, dados brutos consultados, veredito do juiz e o desfecho real), com a limitação acima explícita na própria tela. Deliberadamente estática: não gera parecer novo, não chama LLM, não depende de faturamento de API (desvinculado em 2026-08-12). Mostra a arquitetura funcionando, não sugere que o assistente decide bem nesta população.

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
                              CAMADA 2: assistente (NÃO vê p_default)
                              tools de CASO (multi-hop) + tool de CENÁRIO (1×/lote)
                                       → parecer JSON (APROVAR|NEGAR|DEFERIR)
                                                    │
                        ┌───────────────────────────┼───────────────────────┐
                     JUIZ LLM                  DEMO ESTÁTICA             BACKTEST
                (rubrica ADR-0011,          (app/main_v2.py,           (débito #34,
                 validação determinística    navega os 564 casos        MEDIDO: AUC
                 pós-resposta, ADR-0012)     já processados)             0,56 na zona)
```

**Ponto crítico do desenho:** o assistente forma parecer **independente** do score (`p_default` nunca entra no contexto: garantido por schema, não por disciplina, [ADR-0003](docs/adr/0003-contrato-do-memo-e-agente-cego-ao-score.md)). O confronto parecer × score acontece depois, no backtest: é o que permitiu **medir**, e não supor, que o assistente não agrega separação de risco mensurável nesta população.

**Sobre a tela de revisão humana (produção):** decisão de escopo **tomada, não pendente**. Não foi construída de propósito. Faria sentido para um sistema em produção decidindo crédito real; não faz sentido investir nisso depois que o próprio backtest mostrou que o assistente não agrega separação de risco mensurável (débito #34). Em vez disso, a demo estática acima mostra a arquitetura (parecer, juiz, dados brutos) sem fingir que há um fluxo de produção por trás.

## O que este projeto assume abertamente

- **O dataset é de mercados emergentes, não do Brasil.** A transferência é de **método**, declarada. O contexto macro brasileiro (BCB/IBGE) entra só como cenário de stress rotulado, deslocando a premissa de perda dada a inadimplência, nunca como atributo do cliente ([ADR-0008](docs/adr/0008-cenario-macro-brasileiro-pela-lgd.md)).
- **A LGD (70-85%) é premissa, não medição.** Ancorada em literatura internacional; não existe número público do Banco Central para crédito pessoal brasileiro.
- **Não há decisão de crédito autônoma.** O assistente propõe e um humano decide. "Deferir" é ação de primeira classe, embora medida em só 0,18% dos casos do backtest: decisão deliberada (débito #28), não descuido.
- **Sem consulta a bureau individual:** não existe API pública no Brasil, e o projeto não finge consultar o que não pode.
- **A zona cinzenta está perto do limite do previsível com os dados disponíveis** (débito #34), repetido aqui de propósito, porque é o achado mais importante do projeto, não um detalhe pra esconder na lista.

Os débitos técnicos completos, numerados e vivos, estão em [`AGENTS.md`](AGENTS.md#débitos-técnicos-conhecidos): 34 até aqui, a maioria fechada, os últimos com a investigação completa do backtest.

---

## Metodologia: CRISP-DM

| Fase | O que foi feito na V2 |
|------|-----------|
| 1. Entendimento do Negócio | ADRs 0001-0002: dor, ROI, `p*` derivado (não arbitrário), baseline declarado |
| 2. Entendimento dos Dados | EDA completa do Home Credit (`reports/eda_application.md`, `reports/eda_tabelas_relacionais.md`) + **teto de previsibilidade da zona cinzenta medido antes de decidir investir na Camada 2** (lição extraída para `metodologia/AI_ENGINEERING/11_teto_de_previsibilidade.md`) |
| 3. Preparação dos Dados | Agregação de 5 tabelas relacionais (bureau, previous_application, installments, POS_CASH, credit_card), split treino/calibração/teste antes de qualquer processamento |
| 4. Modelagem | `HistGradientBoostingClassifier` + calibração isotônica (Camada 1) + assistente com ferramentas de caso/cenário (Camada 2) |
| 5. Avaliação | AUC/Brier com IC bootstrap (Camada 1); juiz LLM calibrado contra 87 labels humanos + backtest com poder estatístico real (Camada 2); ver débito #34 |
| 6. Deploy | Demo estática (`app/main_v2.py`): decisão consciente de não reativar API paga para uma tela de exibição |

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
│   ├── monitoramento_v3.py       # Livro de coortes da V3
│   ├── snapshot_monitoramento.py # Contrato agregado e fail-closed da V3
├── scripts/                      # Treino, EDA, calibração, backtest; ver AGENTS.md
├── docs/
│   ├── adr/                      # Decisões de arquitetura e retenção
│   ├── DICIONARIO_DADOS.md
│   ├── LEGADO_V1.md              # Narrativa histórica, não executável
│   └── spec/                     # Contratos de implementação e aceite
├── data/labels/, data/processed/ # Ground truth e memos versionados (débitos #30/#31)
├── reports/                      # Backtest, calibração do juiz, EDAs, gates
├── models/                       # Modelo calibrado da Camada 1 (V2)
├── tests/                        # 301 testes no fechamento da V3
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
| Todas as decisões de arquitetura | [`docs/adr/`](docs/adr/) |
| Débitos técnicos, numerados e vivos (34) | [`AGENTS.md`](AGENTS.md) |
| Auditoria de fechamento | [`docs/audit/fechamento_2026-09-04.md`](docs/audit/fechamento_2026-09-04.md) |
| Versão anterior (registro histórico) | [`docs/LEGADO_V1.md`](docs/LEGADO_V1.md) |

---

## Nota sobre o uso de Inteligência Artificial

Este projeto foi construído com IA como parceira ativa de engenharia, não só de código, mas de rigor: a checagem que refutou a primeira hipótese sobre `EXT_SOURCE` (ADR-0013), os testes de robustez do backtest e a investigação em camadas até o AUC 0,56 foram conduzidos junto com um agente de IA, com decisões de escopo e interpretação sempre confirmadas antes de virar código ou texto final. O objetivo nunca foi esconder isso: é documentar como um resultado negativo, bem medido, também é entregável.

## Autor

**Luiz Fernando Saguma Maibashi**
- Economista | Pós-Tech AI Scientist FIAP
- São Paulo - SP
- [![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/luiz-fernando-maibashi-515073212/)
- [![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat&logo=github&logoColor=white)](https://github.com/luizmaibashi)
