# ADR-0014: Contrato point-in-time e monitoramento de confiabilidade de crédito

**Data:** 2026-09-04
**Status:** Accepted
**Contexto:** PayFlow V3 — reposicionamento após resultado negativo da Camada 2 e auditoria do Home Credit Stability

---

## 1. Contexto

O PayFlow V2 provou que o agente não adiciona separação de risco detectável na zona cinzenta. O Home Credit Stability abriu uma frente mais aderente: medir se um score continua confiável em novas coortes temporais.

O dado, porém, tem armadilhas. `date_decision` é a data em que o crédito foi decidido; qualquer informação posterior não poderia ter sido usada naquele momento. Na auditoria local:

- `refreshdate_3813885D` foi posterior à decisão em 334.789/334.789 casos válidos da partição de bureau auditada;
- `lastupdate_1112D` foi posterior em 253.537/325.353 casos válidos;
- na tabela estática, `dtlastpmtallstes_4499206D` foi posterior em 126.627/549.540 valores preenchidos.

Sem uma catraca de disponibilidade, um modelo pode parecer melhor porque viu uma pista do futuro.

### Linguagem Ubíqua nova

| Termo | Significado |
|---|---|
| **Point-in-time** | Só usa informação que existia no instante da decisão de crédito. |
| **Contrato de disponibilidade** | Registro que classifica cada feature como permitida, bloqueada ou desconhecida na data de decisão. |
| **Coorte** | Grupo de solicitações decidido no mesmo mês ou semana. |
| **Drift** | Mudança no perfil dos dados ou no desempenho do modelo entre coortes. |
| **Gate fail-closed** | Feature nova ou sem regra conhecida bloqueia a execução; ela nunca passa em silêncio. |

## 2. Decisão

Construir uma V3 separada do pipeline legado, composta por:

1. `contrato_disponibilidade_features`: fonte de verdade por feature, com origem, regra temporal e status permitido/bloqueado/desconhecido;
2. `validar_disponibilidade_temporal`: gate fail-closed que rejeita feature sem contrato e identifica datas posteriores a `date_decision`;
3. `avaliar_estabilidade_coorte`: relatório por coorte com cobertura, taxa de default, AUC, Brier e alerta de drift;
4. uma decisão de uso **VERDE / AMARELO / VERMELHO**, dirigida ao gestor de risco: manter, revisar ou bloquear o modelo.

Não reutilizar o motor de aprovação, o agente LLM ou a zona cinzenta como núcleo da V3. Eles permanecem como histórico da V2.

### Razão principal

Se não fizermos isso, o case corre o risco de mostrar um score aparentemente bom que usa dados indisponíveis na vida real. Se fizermos, o PayFlow demonstra uma competência rara e útil: impedir que um modelo de crédito pareça confiável só porque viu o futuro.

O impacto financeiro em R$ não será estimado sem exposição e perda observadas de uma carteira real. O ROI demonstrável agora é redução de risco metodológico e de retrabalho de auditoria; qualquer valor monetário será hipótese explicitamente rotulada.

## 3. Consequências

### Positivas

- A decisão de crédito passa a ter rastreabilidade de dados, não apenas métrica de AUC.
- O case usa a dor descoberta no dado real, em vez de fingir um problema de cobrança que o dataset não mede.
- Uma nova feature sem regra falha de forma visível, não passa por omissão.

### Negativas e riscos

- Regras de disponibilidade podem ser incompletas; agregações numéricas também podem esconder informação futura.
- AUC e Brier só ficam conhecidos depois que o target amadurece; alertas de dados são imediatos, alertas de performance são tardios.
- O dataset continua sendo de mercado emergente, não brasileiro; a transferência é de método, não de portfólio.

## 4. Alternativas descartadas

| Opção | Vantagem | Por que não agora |
|---|---|---|
| Early warning de cobrança | Dor de negócio mais próxima de recuperação. | Faltam snapshots persistentes de contrato/cliente e outcomes de intervenção. |
| Retomar o agente da zona cinzenta | Reaproveita código da V2. | O backtest já não mostrou lift e o teto de previsibilidade local é baixo. |
| Dashboard genérico de AUC | Mais rápido de demonstrar. | Não resolve a causa mais séria: saber se o dado era permitido antes da decisão. |

## 5. Validação e critério de parada

### Métricas de sucesso

- `validar_disponibilidade_temporal` classifica 100% das features usadas.
- Uma feature desconhecida causa falha explícita, nunca aprovação silenciosa.
- `avaliar_estabilidade_coorte` reproduz o baseline temporal: AUC 0,7749 no 4º trimestre de 2019 (`n=337.005`), 0,7752 no 1º semestre de 2020 (`n=305.657`) e 0,8041 no 2º semestre (`n=150.240`) usando o recorte exploratório atual.
- Após aplicar o contrato seguro, a AUC fora do tempo não pode cair mais que 0,03 em relação à primeira coorte de validação.

### Cenários de borda obrigatórios

| Cenário | Comportamento esperado |
|---|---|
| Coorte vazia ou só uma classe | Relatório informa indisponibilidade; não calcula AUC falsa. |
| Feature nova sem contrato | Gate falha com nome da feature. |
| Data nula ou malformada | Feature vira desconhecida e é bloqueada. |
| Data posterior a `date_decision` | Feature ou registro é bloqueado e explicado. |
| Target ainda não amadureceu | Mostra cobertura/drift, mas não finge medir AUC/Brier. |

## 6. PAVC — auditoria contrária

1. **Agregação numérica pode esconder futuro.** Mitigação: nenhum campo é considerado seguro só por não ser data; o contrato exige origem e justificativa por feature.
2. **Monitorar não conserta um modelo ruim.** Mitigação: VERDE significa apenas “dados e estabilidade passaram”; não significa “crédito aprovado” nem substitui validação humana.
3. **O case pode virar um dashboard sem comprador.** Mitigação: a tela final deve começar pela decisão VERDE/AMARELO/VERMELHO e pelo motivo, não por gráficos decorativos.

**Estado PAVC:** desenho explicado pelo autor e aprovado para implementação. O fluxo é: rodar o modelo em cada nova coorte, esperar o target amadurecer e verificar se ele continua acertando. O gate já prova em 12 testes que bloqueia feature sem contrato, status não permitido, dado ausente, data nula/malformada e data posterior. O relatório prova coorte vazia, target não amadurecido, target sem variação, previsão incompleta e valores fora de domínio.

**Resultado PAVC da primeira entrega:** aprovado apenas para os componentes
isolados. Não aprova uma execução real do baseline enquanto as features não
tiverem contratos de disponibilidade e o encadeamento `gate → score → boletim`
não existir.

## 7. Referências

- `docs/tese/payflow-confiabilidade-decisao/TESE.md`
- `AGENTS.md`, débito #34
- ADR-0001 e ADR-0013
- Home Credit Credit Risk Model Stability — descrição oficial do dataset e da métrica de estabilidade
