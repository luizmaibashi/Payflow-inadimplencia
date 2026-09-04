# Tese: confiabilidade da decisão de crédito

**Status:** rascunho · **Aberta:** 2026-09-04 · **Veredito:** pendente · **Reteste:** 2026-10-04

## A tese em uma frase

Para gestores de risco de crédito, o PayFlow ajuda a decidir se um modelo e suas variáveis podem continuar sendo usados em uma nova coorte de clientes, antes que dados do futuro ou mudança no perfil da carteira contaminem decisões de crédito.

> Esta frase foi redigida pelo agente a pedido explícito do autor. É uma hipótese de portfólio, não uma alegação de venda ou ROI já observado em instituição real.

## Explicação simples

Um modelo de crédito é como uma regra que separa alunos que provavelmente vão passar ou reprovar. Se alguém entrega ao modelo uma prova com a resposta do futuro, ele parece genial, mas está trapaceando. O PayFlow deve ser o fiscal: confere se o modelo só olhou o que já existia no dia da decisão e se continua acertando quando chegam alunos novos.

## As 5 lentes

| Lente | Predição | Análise atual | Δ |
|---|---|---|---|
| Necessidade | Gestores de risco precisam provar que o score continua confiável. | Regulação e prática de risco exigem monitoramento, validação e controles; o dataset público contém campos posteriores à decisão que materializam essa dor. | Confirmada como dor setorial; sem comprador entrevistado. |
| Impacto | O PayFlow bloqueia variáveis não disponíveis e mostra deterioração antes de decisões em escala. | `refreshdate_3813885D` é posterior à decisão em 334.789/334.789 casos válidos da partição auditada. | O dano financeiro real não é mensurável sem carteira/parceiro. |
| Distribuição | O case demonstra competência para gestores de risco, times de model risk e recrutadores de dados/IA. | O canal real ainda é portfólio, não venda direta a uma instituição. | Não confundir visibilidade profissional com validação comercial. |
| Escala | A mesma regra de disponibilidade pode validar várias coortes/modelos. | Cada nova fonte exige dicionário, regra temporal e testes; isso é trabalho de integração, não magia de software. | Escala depende de padronização de metadados. |
| ROI | Evitar uso de informação futura reduz risco de decisão inválida e retrabalho de auditoria. | Não há exposição, margem ou perda observada para converter em R$. | ROI financeiro fica explicitamente pendente. |

## Como isso morre

A tese é falsificada se, depois de aplicar o contrato de disponibilidade, o pipeline não conseguir classificar 100% das features como **permitida**, **bloqueada** ou **desconhecida**, ou se o modelo seguro perder mais de 0,03 de AUC fora do tempo em relação à primeira coorte de validação. Em ambos os casos, o projeto não poderá alegar que entrega monitoramento confiável.

## Evidência nova: menos sinal, mas sinal estável

Um proxy semântico com seis campos aparentes de proposta atual teve AUC de
0,6147 (IC95% aproximado [0,6093; 0,6201]) no 4º trimestre de 2019,
0,6082 ([0,6027; 0,6137]) no 1º semestre de 2020 e 0,6180
([0,6074; 0,6285]) no 2º semestre de 2020. A queda frente ao baseline amplo
(~0,775) mostra o custo de abandonar variáveis potencialmente contaminadas; a
estabilidade mostra que ainda há um sinal mensurável. Como a fonte não prova o
instante de disponibilidade dessas seis variáveis, o resultado é evidência de
pesquisa, não validação point-in-time.

## Veredito e destino

**Pendente.** O próximo experimento é construir o contrato de features point-in-time e medir o baseline apenas com entradas permitidas. Se passar, o projeto segue como case de governança e estabilidade de decisões de crédito. Se falhar, fica como auditoria metodológica, sem prometer monitoramento operacional.

## Os 150

Pendente de texto do autor. O exercício é explicar, em até 150 palavras, por que um modelo de crédito precisa ser fiscalizado antes de continuar tomando decisões.
