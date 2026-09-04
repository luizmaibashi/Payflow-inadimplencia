# Spec 0001 — Gate de disponibilidade temporal

**Data:** 2026-09-04
**Status:** Implementada — revisão humana pendente
**Dono da decisão e aprovação de merge:** Luiz Maibashi

## 1. Objetivo

Impedir que o PayFlow rode um modelo de risco quando alguma feature não tiver
prova de que estava disponível na data da decisão de crédito. Em termos simples:
antes de corrigir a prova do aluno, precisamos garantir que ele não recebeu o
gabarito antes da prova.

O valor de negócio é reduzir risco metodológico e retrabalho de validação. O
gate não promete reduzir inadimplência diretamente; ele evita que uma métrica
boa seja sustentada por dado do futuro.

## 2. Escopo

### Incluído

- Um contrato explícito para classificar cada feature usada como `PERMITIDA`,
  `BLOQUEADA` ou `DESCONHECIDA`.
- Validação fail-closed: feature sem contrato, com regra bloqueada, data nula,
  data malformada ou data posterior à decisão interrompe a execução.
- Um relatório estruturado dos bloqueios, para explicar ao gestor qual dado
  inviabilizou a rodada.
- Testes unitários dos casos permitidos e dos cinco cenários de borda da
  ADR-0014.

### Fora de escopo

- Treinar ou pontuar o modelo de crédito.
- Declarar seguras as 128 features do Home Credit sem evidência de origem e
  disponibilidade.
- Criar dashboard, API, LLM ou tela Streamlit.
- Estimar retorno financeiro em reais sem carteira, exposição e perda reais.

## 3. Critérios de aceitação

1. Uma feature solicitada sem contrato causa erro explícito que contém seu nome.
2. Uma feature `BLOQUEADA` ou `DESCONHECIDA` causa erro explícito.
3. Quando a regra exigir uma coluna de data, data ausente, nula ou inválida
   causa bloqueio explícito.
4. Uma data posterior à coluna `date_decision` causa bloqueio explícito com a
   quantidade de registros afetados.
5. Dados com contrato `PERMITIDA` e data válida até a decisão passam, retornando
   um relatório sem bloqueios.
6. A suíte nova cobre os cenários acima e a suíte existente continua verde.

## 4. Restrições e riscos

- As entradas são dados públicos e anonimizados do Home Credit; não há PII,
  credenciais ou dados de clientes reais neste escopo.
- A definição textual de uma coluna não comprova que uma agregação numérica foi
  calculada antes da decisão. Portanto, ausência de prova significa
  `DESCONHECIDA`, não `PERMITIDA`.
- O gate protege a qualidade da entrada, mas não substitui monitoramento de
  performance depois que o target amadurece.
- O comportamento padrão precisa ser bloqueio. Uma lista manual não pode abrir
  passagem para uma feature nova por esquecimento.

## 5. Input-policy-check

- **Dados sensíveis:** não; somente dataset público, anonimizado e ignorado pelo
  Git.
- **Escopo autorizado:** apenas contrato e validação temporal, conforme
  ADR-0014 e Wayfinder 0003.
- **Aprovação:** Luiz revisa o diff e os resultados dos testes antes de qualquer
  merge. O agente não aprova a própria alteração.

## 6. Evidência esperada

- Esta spec.
- Teste inicialmente vermelho, antes da implementação.
- Diff da implementação mínima.
- Resultado de `pytest` da suíte nova e completa.
- Revisão do diff por Luiz antes de merge.

**Evidência executada:** teste inicialmente vermelho por ausência do módulo;
depois 12 testes específicos passaram (88% de cobertura do módulo) e a suíte
completa passou com 212 testes.
