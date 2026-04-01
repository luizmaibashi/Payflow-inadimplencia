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

💎 Ciclo de Lapidação: Evolução Pós-Feedback (2º feedback)
A partir da Fase 8, o projeto PayFlow passou por uma rodada de refinamento técnico e estratégico (lapidação), focada em transformar um modelo de aprendizado de máquina em uma solução real de prateleira para o mercado de crédito.

Fase 8: Testes de Alternativas ao Undersampling
O quê: Teste comparativo entre SMOTE (geração de dados sintéticos) e class_weight='balanced'.

O porquê: O objetivo era avaliar se conseguiríamos manter o volume total de dados de bons pagadores sem perder a sensibilidade para os inadimplentes.

Resultado: Os testes provaram que, para este cenário específico e com o algoritmo Random Forest, o Undersampling continuou sendo a abordagem superior. O SMOTE e o Class Weight entregaram um Recall extremamente baixo (<10%), validando que o desbalanceamento severo exigia uma intervenção mais direta na base de treino para proteger o caixa contra calotes.

Fase 9: Engenharia de Variáveis (A Intuição Econômica)
O quê: Criação de novos indicadores financeiros derivados dos dados brutos.

Comprometimento de Renda: (Parcela Estimada / Renda Mensal).

Intensidade de Crédito: Cruzamento de uso de limite e quantidade de cartões.
O porquê: Um modelo de crédito é mais eficaz quando entende a "capacidade de pagamento" e não apenas o histórico. Essas variáveis tornaram-se os principais drivers de decisão no gráfico de Feature Importance, provando que a lógica econômica aumenta a precisão do algoritmo.

<img width="983" height="553" alt="image" src="https://github.com/user-attachments/assets/fbecee65-2fe6-4285-a62a-1489c8aee5cb" />





Fase 10: Quantificação Financeira (Perda Evitada)
O quê: Tradução da Matriz de Confusão em valores monetários (R$).

O porquê: Métrica de "Acurácia" não paga as contas da empresa. Criamos um relatório de impacto que demonstra:

Perda Evitada: O montante financeiro que deixou de sair do caixa ao identificar corretamente perfis de alto risco.

Custo de Oportunidade: O valor que deixamos de ganhar ao ser excessivamente conservadores com bons clientes.

Resultado: O modelo apresentou um saldo positivo expressivo, justificando sua implementação do ponto de vista executivo.

Fase 11: Arquitetura de Produção e Deploy
O quê: Preparação do modelo para o "mundo real".

O porquê: Para gerar valor, o modelo precisa ser consumido. Desenvolvemos o fluxo de deploy:

Serialização: Exportação do modelo via joblib (.pkl).

Pipeline de Entrada: Estrutura para receber dados via JSON.

Saída Estruturada: A API não responde apenas 0 ou 1, mas sim uma recomendação de ação: Aprovar (Risco < 40%), Revisar (40% - 65%) ou Negar (> 65%).


**CONCLUSÃO FINAL E REFLEXÕES**

Modelo como Estratégia de Negócio
A conclusão deste projeto marca a minha transição de um "estudante de código" para um "analista de soluções". O maior aprendizado não foi o uso da biblioteca Scikit-Learn, mas sim o entendimento de que um modelo com 90% de acurácia pode ser inútil se ele não resolver a dor do caixa.

Ao final da Fase 11, o PayFlow deixou de ser um arquivo .ipynb para se tornar uma estratégia de esteira de crédito:

Decisão Baseada em Dados: Saímos do "acho" para faixas de probabilidade reais.

Visão Financeira: Traduzimos o erro do modelo em Perda Evitada (R$), permitindo que a diretoria visualize o ROI (Retorno sobre Investimento) da área de dados.

Engenharia de Valor: A criação de variáveis como comprometimento_renda provou que a inteligência humana e o conhecimento econômico são o que realmente "ensinam" a máquina a ser precisa.

**Reflexões (Economia → Data Science)**
Como economista formado pela UFMS e agora pós-graduando na FIAP, vejo a Ciência de Dados como a evolução natural da análise econômica. Este projeto foi o primeiro passo para consolidar essa ponte.
A maior lição deste ciclo de feedbacks foi a humildade técnica: testar o SMOTE e o Class Weight e aceitar que o Undersampling era a melhor saída — mesmo sendo uma técnica mais simples — mostra que no mercado real, o que importa é a eficácia e a segurança do capital.


*Nota sobre o uso de Inteligência Artificial*

Diferente de uma abordagem passiva, utilizei a IA como um co-piloto de aprendizado. Para cada linha de código sugerida ou conceito complexo (como a serialização de modelos), fiz o exercício reverso: "Por que isso funciona assim?".

Nesta documentação, não há "caixas pretas". Cada decisão de threshold, cada escolha de hiperparamêtro e cada cálculo financeiro foi validado e compreendido. A IA acelerou a minha curva de aprendizado, mas a estratégia de risco e a narrativa de negócio são frutos do meu critério como analista.
