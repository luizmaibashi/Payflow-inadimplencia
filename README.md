**PayFlow — Previsão de Risco de Crédito**

**Projeto de portfólio | Em evolução ativa**
Este é meu primeiro projeto de Data Science, desenvolvido durante a transição de carreira de Economista para Cientista de Dados. A documentação acompanha não só o como, mas o porquê de cada decisão — incluindo os erros, correções e aprendizados ao longo do caminho.

**Problema de Negócio**
A empresa PayFlow precisa reduzir a inadimplência de sua carteira de crédito. O objetivo é criar um modelo preditivo capaz de identificar, com até 90 dias de antecedência, quais clientes têm alto risco de não honrar seus compromissos financeiros.
Por que isso importa?

Um Falso Negativo (não detectar um inadimplente) = prejuízo total: o crédito foi concedido e não será recuperado.
Um Falso Positivo (barrar um bom pagador) = custo de oportunidade: perda de margem, mas sem perda de capital.

Essa assimetria de custos guiou todas as decisões técnicas do projeto, especialmente a escolha das métricas de avaliação.

**Solução**
Modelo de classificação binária (default_90d: 0 = adimplente, 1 = inadimplente) utilizando Random Forest com balanceamento de classes via UnderSampling manual.

**Metodologia — CRISP-DM**
O projeto segue o ciclo CRISP-DM (Cross Industry Standard Process for Data Mining):
1. Entendimento do Negócio   → Definição do problema e métricas-chave
2. Entendimento dos Dados    → EDA, análise de nulos e distribuições
3. Preparação dos Dados      → Imputação, remoção de data leakage, encoding
4. Modelagem                 → Random Forest com e sem balanceamento
5. Avaliação                 → Classification Report + Matriz de Confusão
6. Deploy                    → (em desenvolvimento — ver Próximos Passos)


  **Resultados**
Comparativo: Modelo Inicial vs. Modelo Corrigido:

| Métrica                  | Modelo Inicial | Modelo Corrigido |
|:-------------------------|:--------------:|:----------------:|
| Acurácia geral           |      87%       |       ~72%       |
| Recall (Inadimplentes)   |    **1%**      |     **63%**      |
| Falsos Negativos         |  125 de 126    |    46 de 126     |

O modelo inicial tinha acurácia alta, mas era inútil para o negócio: identificava apenas 1 inadimplente real em 126. Esse foi o principal aprendizado do projeto — acurácia alta ≠ modelo bom.

### Matriz de Confusão (Modelo Corrigido)

|                        | Previsto: Bom Pagador | Previsto: Inadimplente |
|:-----------------------|:---------------------:|:----------------------:|
| **Real: Bom Pagador**  | 637 ✅                | 237 ⚠️                 |
| **Real: Inadimplente** | 46 ❌                 | 80 ✅                  |

O modelo passou a identificar 63% dos inadimplentes reais, aceitando como trade-off uma taxa maior de falsos positivos — decisão justificada pela assimetria de custos do negócio.


**Stack Técnica**
      **Categoria**                        **Ferramentas**
      Linguagem                        Python 3.x
      Manipulação de dados             Pandas, NumPy
      Machine Learning                 Scikit-learn (RandomForestClassifier)
      Visualização                     Matplotlib, Seaborn
      Metodologia                      CRISP-DM, Holdout (80/20)




      **Melhorias Mapeadas (Próximos Passos)**
Este projeto está em evolução ativa. Com base no feedback recebido, as seguintes melhorias estão planejadas:
 **Validação cruzada (Cross-Validation)** — substituir o holdout simples por k-fold para aumentar a confiabilidade dos resultados
 
 **Comparação de modelos** — testar Regressão Logística e XGBoost e justificar a escolha final com métricas
 
 **Otimização de threshold** — definir e documentar o ponto de corte ideal (aprovar / negar / revisar) com base no impacto de negócio
 
 **Alternativas ao UnderSampling** — testar SMOTE e class_weight como alternativas e documentar trade-offs
 
 **Especificação de Deploy** — detalhar os inputs do modelo, o que ele retorna (probabilidade ou decisão) e a regra de negócio aplicada
