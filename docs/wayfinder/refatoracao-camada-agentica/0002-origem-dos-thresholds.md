---
tipo: grilling
status: resolvido
criado: 2026-08-04
---

# Ticket 0002: Origem dos thresholds de decisão (0.40 / 0.65)

## Bloqueio
Hoje `RISCO_BAIXO_MAX=0.40` e `RISCO_MEDIO_MAX=0.65` estão hardcoded/configuráveis por env var (`app/utils.py::get_decision_thresholds`), mas sem justificativa documentada — não há ADR nem cálculo que explique por que esses valores e não outros.

O README já narra a lógica de negócio que deveria ter gerado esses números:
> "Falso Negativo = prejuízo total (crédito concedido, não recuperado). Falso Positivo = custo de oportunidade (perda de margem, sem perda de capital)."

Essa assimetria nunca foi traduzida num cálculo explícito. Isso é decisão de negócio (só o usuário pode fixar as premissas de custo), não algo que se pesquisa:

1. **Premissa de custo do Falso Negativo**: qual fração do valor do crédito se perde quando um mau pagador é aprovado? (ex: 100% do principal, ou uma taxa de recuperação parcial via cobrança/garantia?)
2. **Premissa de custo do Falso Positivo**: qual é a margem perdida ao recusar um bom pagador? (ex: juros esperados do contrato não capturado)
3. **Método de derivação**: usar a razão de custos pra mover o corte na curva ROC/precision-recall (ex: threshold que minimiza custo esperado = FN_rate × custo_FN + FP_rate × custo_FP), documentado em ADR com o cálculo explícito, substituindo os números arbitrários atuais.

## Resultado

**Decidido (2026-08-04):** usar **valor esperado por observação**, não corte único global.

Ou seja: cada caso tem seu próprio ponto de corte, ponderando o valor em risco daquele empréstimo específico — decisão = comparar custo esperado de aprovar (`p_default × valor_em_risco × (1 − taxa_recuperação)`) contra custo esperado de recusar (margem perdida). É a abordagem mais próxima de case real de empresa, ao custo de ser mais complexa de implementar e de explicar no memo de crédito.

Implicação: os três buckets fixos atuais (APROVAR/REVISAR/NEGAR via `RISCO_BAIXO_MAX`/`RISCO_MEDIO_MAX` em `app/utils.py`) deixam de ser a lógica primária — a faixa "REVISAR" passa a ser definida por uma banda de indiferença em torno do ponto de equilíbrio do valor esperado, não por um número fixo.

**Premissa de LGD (fechada em 2026-08-04, via ticket [0007](0007-dataset-lgd-fontes-externas.md)):** recuperação de **15-30%** (LGD 70-85%) para crédito ao consumidor não garantido, ancorada em literatura empírica (ScienceDirect, 2023) e contrastada com o piso regulatório de Basel FIRB (LGD 45% para sênior não garantido). Documentar no ADR como **estimativa de mercado internacional** — não há número público do BCB para LGD de crédito pessoal brasileiro.

**Acoplamento com o cenário de stress (ticket [0009](0009-conflito-dataset-vs-fontes-externas.md)):** a LGD é justamente o canal pelo qual o cenário macro brasileiro entra na decisão — condições piores deslocam a LGD dentro da faixa, movendo o ponto de corte por observação. Isso é o que impede o cenário macro de ser decorativo.
