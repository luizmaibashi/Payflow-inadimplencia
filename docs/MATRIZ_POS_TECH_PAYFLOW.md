# Matriz Pós-Tech → PayFlow confiabilidade

## Para que serve esta matriz

A nova versão do PayFlow não precisa usar todo assunto da Pós-Tech. Precisa
usar cada conhecimento que ajuda a responder uma pergunta concreta:

> Quando chega uma nova coorte, ainda podemos confiar no modelo para apoiar a
> gestão de risco?

A leitura abaixo foi feita sobre os resumos autorais das Fases 1 e 3 e o mapa
local da Fase 3. Os resumos da Fase 2 ainda estão vazios. Portanto, a presença
do material bruto prova disponibilidade do conteúdo, não domínio pessoal.

## Conhecimento que entra no case

| Conhecimento | Tradução simples | Aplicação no PayFlow | Evidência atual | Estado |
|---|---|---|---|---|
| CRISP-DM e dor de negócio | Começar pela decisão, não pelo algoritmo | Define o usuário como gestor de risco e a ação como manter, revisar, aguardar ou bloquear | `docs/tese/` e ADR-0014 | Aplicado |
| Target e target trap | Garantir que a resposta mede o evento certo | Obriga declarar maturação e impede avaliar coorte cedo demais | `PoliticaMaturacao` e ADR-0017 | Aplicado como hipótese de demonstração |
| Unidade de análise | Saber quem cada linha representa | Uma linha por `case_id`; duplicidade e perda no join bloqueiam a execução | `montar_base_proxy()` e testes | Aplicado |
| Qualidade e EDA | Procurar ausências, duplicidades e mudanças | Valida colunas, datas, chaves e completude; distribuição das features ainda entrará no drift | contratos e testes atuais | Parcial |
| Inferência estatística | Não confundir um número pontual com certeza | Reporta `n`, eventos, Wilson para inadimplência e bootstrap para AUC | `estabilidade_coorte.py` | Aplicado |
| Poder e evidência mínima | Não decidir com amostra pequena | Exige mínimo de observações, inadimplentes e limite inferior da AUC | `PoliticaEvidencia` | Aplicado |
| Aprendizado supervisionado | Aprender uma relação entre X e default | Baseline com `HistGradientBoostingClassifier` e seis features | `experimento_proxy_estabilidade.py` | Aplicado |
| Validação temporal e backtest | Treinar no passado e testar no futuro | Treino até 2019-09-30; três coortes posteriores | script reproduzível e testes | Aplicado |
| Avaliação de modelos | Medir separação e qualidade das probabilidades | AUC mede ordenação; Brier mede erro probabilístico | boletim por coorte | Aplicado |
| Overfitting e tuning | Evitar decorar o passado | Hiperparâmetros estão fixos e registrados, mas não foram otimizados por validação temporal aninhada | spec 0007 | Pendente deliberado |
| Feature selection e SHAP | Entender o que o modelo usa | Pode explicar mudança de contribuição entre coortes, depois de provar disponibilidade point-in-time | ainda sem artefato V3 | Pendente |
| Engenharia de dados e ETL | Produzir sempre a mesma tabela de entrada | Join one-to-one e execução reprodutível já existem; lineage e versionamento do snapshot ainda não | script e spec 0007 | Parcial |
| Storytelling para negócio | Transformar métrica em ação | Semáforo separado da decisão de cliente e limitações expostas | relatório Markdown | Aplicado |

## O que não entra agora

- Clustering: poderia segmentar clientes, mas não responde se o modelo atual
  continua confiável.
- Aprendizado por reforço: exigiria ambiente, recompensa e interação que este
  problema não possui.
- LSTM, ARIMA e Transformers: a unidade principal é uma proposta de crédito.
  O tempo organiza as coortes, mas não transforma automaticamente o problema
  em previsão de série temporal.
- LLM como decisor: a V2 já mostrou que uma camada sofisticada não cria sinal
  que o dado não possui. A V3 foca primeiro em confiabilidade do modelo.
- AutoML: comparar muitos algoritmos antes de fechar target, disponibilidade e
  protocolo temporal seria otimizar a pergunta errada.

## Conhecimento que falta além da Pós-Tech

O curso fornece boa parte da ciência de dados necessária. Para um case de
crédito mais próximo do setor, ainda precisamos acrescentar:

1. disponibilidade point-in-time de cada feature;
2. definição institucional do default e da janela de maturação;
3. data drift e concept drift por coorte;
4. calibração e impacto financeiro por faixa de score;
5. fairness, LGPD, governança e trilha de aprovação humana;
6. champion versus challenger e regra de rollback.

Essa camada adicional é justamente o que transforma um exercício de modelagem
em um case de gestão de risco de modelo.
