# PayFlow V1 — registro histórico (dado sintético)

> Este documento preserva a narrativa original do projeto, de quando ele usava dado **sintético** e um pipeline mais simples (Random Forest, thresholds fixos). Foi movido pra cá em 2026-08-12 pra manter o [`README.md`](../README.md) principal focado na V2 (dado real, camada agêntica, medição com poder estatístico) — a V1 continua aqui como registro de onde o projeto começou.
>
> **A V1 não está mais no ar nem faz parte do runtime atual.** O deploy foi despublicado em 2026-08-11 e os arquivos executáveis foram removidos do `HEAD` em 2026-09-04 para não serem confundidos com V2/V3. A narrativa, as figuras e o histórico Git foram preservados; veja [ADR-0021](adr/0021-remocao-do-runtime-v1.md).

## O que este projeto assumia abertamente (V1)

- **O dado é sintético.** Não há outcome real de inadimplência. Toda métrica media o acerto contra o gerador do dado, não contra o mundo — não existia backtest possível.
- **Os cortes 0.40 / 0.65 nunca foram derivados.** A assimetria falso negativo × falso positivo estava narrada corretamente, mas nunca virou cálculo. Eram números arbitrários — substituídos por `p*` calculado na V2 ([ADR-0002](adr/0002-motor-de-decisao-por-valor-esperado.md)).
- **O undersampling resolveu o recall e quebrou a calibração.** Reamostrar a classe majoritária desloca a taxa base e infla sistematicamente a probabilidade prevista. Para *ranquear* clientes isso é indiferente; para *decidir* com base no valor da probabilidade, não é. A calibração nunca foi medida (nem reliability diagram, nem Brier) — o AUC não acusava esse tipo de erro.

## Metodologia — CRISP-DM (V1)

| Fase | Descrição |
|------|-----------|
| 1. Entendimento do Negócio | Definição do problema e métricas-chave |
| 2. Entendimento dos Dados | EDA, análise de nulos e distribuições |
| 3. Preparação dos Dados | Imputação, remoção de data leakage, encoding |
| 4. Modelagem | Random Forest com e sem balanceamento |
| 5. Avaliação | Classification Report + Matriz de Confusão |
| 6. Deploy | App interativo via Streamlit, hoje preservado apenas no histórico Git |

## Problema de Negócio

A empresa **PayFlow** precisava reduzir a inadimplência de sua carteira de crédito. O objetivo era criar um modelo preditivo capaz de identificar, com até **90 dias de antecedência**, quais clientes tinham alto risco de não honrar seus compromissos financeiros.

### Por que isso importava

- Um **Falso Negativo** (não detectar um inadimplente) = **prejuízo total**: o crédito foi concedido e não seria recuperado.
- Um **Falso Positivo** (barrar um bom pagador) = **custo de oportunidade**: perda de margem, mas sem perda de capital.

> Essa **assimetria de custos** guiou as decisões técnicas do projeto, especialmente a escolha das métricas de avaliação.

## EDA e Preparação dos Dados

- **Tratamento de Dados:** Identificação de valores nulos, tratamento de **data leakage** e tratamento de dados categóricos.
- **Imputação:** Mediana para renda (resistente a outliers), regra de negócio para tempo de emprego (0 para autônomos).
- **Remoção de Leakage:** Colunas com informações do futuro (`parcelas_pagas_ate_3m`, `atraso_primeira_parcela_dias`, `status_apos_90d`) foram removidas.

## A Jornada de Modelagem: Falhas e Insights

### Tentativa 1: A Armadilha da Acurácia Alta

Inicialmente, o modelo foi treinado com a base bruta (desbalanceada).

- **Resultado:** 90% de Acurácia, porém **recall de apenas 1%**.
- **O "Porquê" deu errado:** O modelo sofreu um **"vício da maioria"**. Como havia poucos inadimplentes, ele aprendeu a dizer que todos pagariam, errando 99% dos calotes, mas mantendo uma nota alta. Para o negócio, **este modelo era inútil**.

<p align="center">
  <img src="../reports/figures/grafico_01.png" alt="Matriz de Confusão" width="519"/>
  <br>
  <em>Matriz de Confusão — Modelo Inicial (desbalanceado)</em>
</p>

### Tentativa 2: Correção Proativa (Foco no Risco)

Entendendo o "porquê" do resultado anterior (viés), foi aplicado **UnderSampling**.

O modelo passou a identificar **63% dos inadimplentes**, aceitando como trade-off uma taxa maior de falsos positivos — decisão justificada pela assimetria de custos do negócio.

<p align="center">
  <img src="../reports/figures/grafico_02.png" alt="Comparativo" width="591"/>
  <br>
  <em>Comparativo: Modelo Corrigido com Undersampling</em>
</p>

### Comparativo: Modelo Inicial vs. Modelo Corrigido

> O modelo inicial tinha acurácia alta, mas era **inútil para o negócio**: identificava apenas 1 inadimplente real em 126.
> Esse foi o **principal aprendizado da V1** — acurácia alta ≠ modelo bom. É a mesma classe de lição que a V2 reaprendeu de outro jeito: número que parece bom sem intervalo de confiança pode enganar (ver `AGENTS.md`, débito #34).

## Ciclo de Lapidação: Evolução Pós-Feedback

A partir da Fase 8, o projeto passou por rodadas de **refinamento técnico e estratégico**, focadas em transformar um modelo de aprendizado de máquina em uma **solução de prateleira** para o mercado de crédito.

### Fase 8: Testes de Alternativas ao Undersampling

- **O quê:** Teste comparativo entre **SMOTE** (geração de dados sintéticos) e **`class_weight='balanced'`**.
- **O porquê:** Avaliar se seria possível manter o volume total de dados de bons pagadores sem perder a sensibilidade para os inadimplentes.
- **Resultado:** O Undersampling continuou sendo a abordagem superior para este cenário. O SMOTE e o Class Weight entregaram um Recall extremamente baixo (<10%).

### Fase 9: Engenharia de Variáveis (A Intuição Econômica)

- **O quê:** Criação de novos indicadores financeiros derivados dos dados brutos.
  - `comprometimento_renda`: (Parcela Estimada / Renda Mensal)
  - `intensidade_credito`: Cruzamento de uso de limite e quantidade de cartões
- **O porquê:** Um modelo de crédito é mais eficaz quando entende a **"capacidade de pagamento"** e não apenas o histórico.

<p align="center">
  <img src="../reports/figures/grafico_03.png" alt="Feature Importance" width="980"/>
  <br>
  <em>Feature Importance: As variáveis econômicas criadas dominam a decisão do modelo</em>
</p>

### Fase 10: Quantificação Financeira (Perda Evitada)

- **O quê:** Tradução da Matriz de Confusão em **valores monetários (R$)**.
- **O porquê:** Métrica de "Acurácia" não paga as contas da empresa. Foi criado um relatório de impacto que demonstra:
  - **Perda Evitada:** O montante financeiro que deixou de sair do caixa.
  - **Custo de Oportunidade:** O valor que se deixou de ganhar ao ser excessivamente conservador.
- **Resultado:** impacto líquido positivo estimado (números do modelo final abaixo).

### Fase 11: Arquitetura de Produção e Deploy

- **Serialização:** Exportação do modelo via `joblib` (`.pkl`).
- **Pipeline de Entrada:** Estrutura para receber dados via JSON.
- **Saída Estruturada:** A API não respondia apenas 0 ou 1, mas sim uma recomendação de ação:

| Probabilidade de Risco | Decisão |
|------------------------|---------|
| < 40% | ✅ **Aprovar** |
| 40% - 65% | ⚠️ **Revisar** |
| > 65% | ❌ **Negar** |

**Exemplo de Output JSON:**
```json
{
  "id_cliente": 12345,
  "probabilidade_risco": 0.72,
  "decisao": "Negar",
  "motivo": "Risco acima do limite auto-aprovado (65%)"
}
```

## Modelo Serializado (.pkl) — histórico

O modelo final foi exportado via `joblib`. Os binários abaixo foram removidos do estado atual junto com o runtime V1; continuam recuperáveis no histórico Git.

| Arquivo | Tamanho | Conteúdo |
|---------|---------|----------|
| `models/modelo_payflow_v1.pkl` | ~3 MB | RandomForestClassifier treinado (100 estimators) |
| `models/colunas_modelo.pkl` | ~600 bytes | Lista ordenada das 30 features esperadas pelo modelo |

### Métricas do modelo (V1)

| Métrica | Valor |
|---------|-------|
| **Recall (inadimplentes)** | 60% |
| **Perda Evitada** | R$ 380.000,00 |
| **Custo de Oportunidade** | R$ 179.200,00 |
| **Impacto Líquido** | R$ 200.800,00 |

> ⚠️ Um número anterior de "Perda Evitada" (R$ 186.000,00) apareceu em versão anterior desta narrativa, referente a um snapshot diferente do pipeline. A tabela acima é o valor final registrado; a divergência é inconsistência de rascunho da V1, não da V2 — mantida aqui em vez de silenciada.

## Como consultar a V1

A V1 não é suportada no `HEAD` atual. Este documento é a fonte histórica legível. Código, notebook, dataset sintético e modelos antigos podem ser inspecionados em um commit anterior ao ADR-0021, sem misturá-los aos entrypoints suportados hoje.

## Conclusão e Reflexões (V1)

**Modelo como Estratégia de Negócio:** a conclusão desta fase marcou a transição de "estudante de código" pra "analista de soluções". O maior aprendizado não foi o uso do Scikit-Learn, mas o entendimento de que **um modelo com 90% de acurácia pode ser inútil** se não resolver a dor do caixa.

### Lições principais

- **Decisão baseada em dados:** saiu do "acho" pra faixas de probabilidade reais.
- **Visão financeira:** traduziu o erro do modelo em **Perda Evitada (R$)**, permitindo que a diretoria visualizasse o ROI da área de dados.
- **Engenharia de valor:** a criação de variáveis como `comprometimento_renda` mostrou que conhecimento de domínio "ensina" a máquina a ser precisa.
- **Humildade técnica:** testar SMOTE e Class Weight e aceitar que o Undersampling era a melhor saída — mesmo sendo mais simples — é o mesmo tipo de humildade que a V2 exigiu ao aceitar o resultado do débito #34 em vez de forçar uma conclusão positiva.

---

**Continuação:** a V2 reconstrói a Camada 1 sobre dado real (Home Credit) e adiciona uma camada agêntica de underwriting avaliada com rigor estatístico. Ver [`README.md`](../README.md) e [`AGENTS.md`](../AGENTS.md).
