📊**PayFlow — Previsão de Risco de Crédito**

**Projeto de portfólio | Em evolução ativa**
Este é meu primeiro projeto de Data Science, desenvolvido durante a primeira fase da Pós-Tech AI SCIENTIST (FIAP). A documentação acompanha não só o como, mas o porquê de cada decisão, incluindo os erros, correções e aprendizados ao longo do caminho.


**Metodologia — CRISP-DM**
O projeto segue o ciclo CRISP-DM (Cross Industry Standard Process for Data Mining):
1. Entendimento do Negócio   → Definição do problema e métricas-chave
2. Entendimento dos Dados    → EDA, análise de nulos e distribuições
3. Preparação dos Dados      → Imputação, remoção de data leakage, encoding
4. Modelagem                 → Random Forest com e sem balanceamento
5. Avaliação                 → Classification Report + Matriz de Confusão
6. Deploy                    → (em desenvolvimento — ver Próximos Passos)


🎯**Problema de Negócio**
A empresa PayFlow precisa reduzir a inadimplência de sua carteira de crédito. O objetivo é criar um modelo preditivo capaz de identificar, com até 90 dias de antecedência, quais clientes têm alto risco de não honrar seus compromissos financeiros.

Por que isso importa?

Um Falso Negativo (não detectar um inadimplente) = prejuízo total: o crédito foi concedido e não será recuperado.
Um Falso Positivo (barrar um bom pagador) = custo de oportunidade: perda de margem, mas sem perda de capital.

Essa assimetria de custos guiou todas as decisões técnicas do projeto, especialmente a escolha das métricas de avaliação.


🔍**EDA e Preparação dos Dados (Fundamentação)**

Antes da modelagem, realizei uma Análise Exploratória de Dados (EDA) para garantir a qualidade dos inputs:

Tratamento de Dados: Identificação de valores nulos, tratamento de data leakage e tratamento de dados categóricos.


📉**A Jornada de Modelagem: Falhas e Insights**

Tentativa 1: A Armadilha da Acurácia Alta
Inicialmente, treinei o modelo com a base bruta (desbalanceada).

Resultado: 90% de Acurácia, porém recall 1%.

O "Porquê" deu errado: O modelo sofreu um "vício da maioria". Como havia poucos inadimplentes, ele aprendeu a dizer que todos pagariam, errando 99% dos calotes, mas mantendo uma nota alta. Para o negócio, este modelo era  inútil. 

Tentativa 2: Correção Proativa (Foco no Risco)
Entendendo o "porque" do resultado anterior (viés), apliquei o UnderSampling.

O modelo passou a identificar 63% dos inadimplentes, aceitando como trade-off uma taxa maior de falsos positivos — decisão justificada pela assimetria de custos do negócio.
  
📈**Resultados(prévios)**
Comparativo: Modelo Inicial vs. Modelo Corrigido:

| Métrica                  | Modelo Inicial | Modelo Corrigido |
|:-------------------------|:--------------:|:----------------:|
| Acurácia geral           |      87%       |       ~72%       |
| Recall (Inadimplentes)   |    **1%**      |     **63%**      |
| Falsos Negativos         |  125 de 126    |    46 de 126     |
| Verdadeiros Positivos    |       1        |        80        |

O modelo inicial tinha acurácia alta, mas era inútil para o negócio: identificava apenas 1 inadimplente real em 126. Esse foi o principal aprendizado do projeto — acurácia alta ≠ modelo bom.

### Matriz de Confusão (Modelo Corrigido)

|                        | Previsto: Bom Pagador | Previsto: Inadimplente |
|:-----------------------|:---------------------:|:----------------------:|
| **Real: Bom Pagador**  | 637 ✅                | 237 ⚠️                 |
| **Real: Inadimplente** | 46 ❌                 | 80 ✅                  |


O Insight: Em crédito, o custo de um calote é muito superior ao lucro de um bom empréstimo. Ao equilibrar a base, "forcei" o modelo a aprender as características reais da inadimplência. O Recall subiu, e o modelo passou a ter valor real de proteção.


**Melhorias Mapeadas (Próximos Passos)**

Este projeto está em evolução ativa. Com base no feedback recebido, as seguintes melhorias estão planejadas:
 
Validação cruzada (Cross-Validation) — substituir o holdout simples por k-fold para aumentar a confiabilidade dos resultados
 
Comparação de modelos — testar Regressão Logística e XGBoost e justificar a escolha final com métricas
 
Otimização de threshold — definir e documentar o ponto de corte ideal (aprovar / negar / revisar) com base no impacto de negócio
 
Alternativas ao UnderSampling — testar SMOTE e class_weight como alternativas e documentar trade-offs
 
Especificação de Deploy — detalhar os inputs do modelo, o que ele retorna (probabilidade ou decisão) e a regra de negócio aplicada



**Refinamento (Pós-Feedback)**
Após avaliação de especialistas, implementei as seguintes melhorias:

Validação Cruzada (K-Fold): Substituí o teste simples por 5 rodadas de validação, garantindo que o desempenho do modelo é estável e não fruto do acaso.

Comparação de Modelos: Validei o Random Forest contra a Regressão Logística, provando matematicamente a superioridade da "floresta" para capturar padrões de risco.

Threshold de Negócio: Abandonei a decisão binária (0 ou 1) pelo uso de probabilidades (predict_proba).


📈**Impacto Real e Regras de Negócio**

Ao aplicar o modelo em uma base de 1.000 novos clientes, transformamos a matemática em operação financeira estratégica:

| Decisão | Faixa de Risco | Volume | Impacto na Operação |
| :--- | :--- | :--- | :--- |
| **Aprovação Automática** | < 40% | 463 | Escala e rapidez para o bom cliente. |
| **Esteira de Revisão** | 40% - 65% | 438 | Segurança: Casos encaminhados para análise humana. |
| **Negação Automática** | > 65% | 99 | Proteção: Barrou 34/99 inadimplentes reais. |

> **Insight de Negócio:** Essa segmentação permite que a PayFlow automatize quase metade das decisões de crédito(operação), focando o esforço humano apenas nos casos de incerteza moderada, enquanto blinda o capital(financeiro) contra os perfis de altíssimo risco.


A escolha dos thresholds de 40% e 65% foi baseada na assimetria de custos do setor financeiro.

Abaixo de 40%: Priorizamos a Eficiência (aprovando rápido quem tem baixo risco).

Acima de 65%: Priorizamos a Segurança (barrando onde a probabilidade de calote é alta).

O Intervalo Central: É a otimização de recurso humano, focando os analistas de crédito apenas nos casos onde o modelo detecta maior incerteza.


🚀 **Especificação de Deploy (Pronto para Produção)**

O modelo foi preparado para ser consumido via API, retornando uma resposta estruturada para o sistema da PayFlow:

Input: Dados do cliente (Idade, Renda, Tempo de Emprego, etc).

Processamento: Carregamento do modelo .joblib e cálculo de probabilidade.

Output (JSON):

{

  "id_cliente": 12345,
  
  "probabilidade_risco": 0.72,
  
  "decisao": "Negar",
  
  "motivo": "Risco acima do limite auto-aprovado (65%)"
  
}




**CONCLUSÃO FINAL E REFLEXÕES**
Neste projeto de ciência de dados (crédito), aprendi que o "valor real" é muito mais do que entregar um código que funciona. Como estou migrando da análise de dados para a ciência de dados, este trabalho foi o meu "campo de prova" para entender que, na vida real, um modelo estatisticamente "perfeito" pode ser um desastre para o negócio.

O que este projeto me ensinou?

Acurácia não é tudo: No início, fiquei empolgado com os 90% de acurácia, mas logo entendi que o modelo estava sendo enviesado. Ele ignorava o inadimplente para manter uma nota alta. Aprendi que, em crédito, o Recall (a nossa rede de proteção) vale muito mais do que uma média geral bonita.

O valor da segmentação: Ao implementar as probabilidades e os thresholds de 40% e 65%, percebi que a Ciência de Dados não precisa (e nem deve) tomar todas as decisões sozinha. Aprender a Esteira de Revisão foi o ponto alto: é aqui que a tecnologia ajuda o humano a focar onde realmente existe dúvida.

Ciclo de Melhoria Contínua: O projeto que entrego hoje é muito superior à primeira versão. A inclusão da Validação Cruzada e a comparação com a Regressão Logística me deram a segurança técnica de que os resultados são robustos e não apenas "sorte" de um sorteio de dados.


*Nota sobre o uso de Inteligência Artificial*

*Não tenho como negar que utilizei a Inteligência Artificial como uma ferramenta de co-piloto e estudo durante este processo.     Para um analista em transição, ter acesso a uma tecnologia que ajuda a explicar conceitos complexos (como o funcionamento matemático do K-Fold ou a lógica de uma API) acelerou muito o meu aprendizado.*

*No entanto, ressalto que nenhum código foi colado sem ser questionado e até endender cada palavracontida nele. Meu foco foi usar a IA para aprender o "como" e, principalmente, o "porquê" de cada técnica/conduta. A IA me deu as ferramentas, mas a estratégia de negócio, o ajuste das faixas de risco e a interpretação dos resultados foram decisões, baseadas no que acredito ser o melhor para a saúde financeira da PayFlow.*
