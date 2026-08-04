---
tipo: pesquisa
status: resolvido
criado: 2026-08-04
---

# Ticket 0007: Escolha de dataset real, premissa de LGD e fontes externas para o agente

## Bloqueio
Três decisões dependem de pesquisa antes de poderem ser fechadas (usuário pediu embasamento, não palpite):

1. **Qual dataset real usar** — comparar Kaggle "Give Me Some Credit" (default cogitado, mas dado de ~2009-2011), "Home Credit Default Risk" (mais moderno e rico, inclui bureau externo), UCI German Credit (clássico mas pequeno), HMDA (crédito imobiliário EUA — relevante pro alvo Loft, mas verificar se tem outcome de default ou só originação). Confirmar também se existe alguma exceção brasileira pública com rótulo real de inadimplência.
2. **Premissa de taxa de recuperação (LGD)** para crédito ao consumidor não garantido — necessária para o cálculo de valor esperado decidido no ticket 0002.
3. **Fontes externas públicas e gratuitas** que o agente da Camada 2 pode consultar de forma honesta (ver ticket 0008) — candidatos: BCB SGS API (SELIC, inflação), IBGE (desemprego/PIB per capita por região).

## Resultado

Pesquisa concluída em 2026-08-04.

### 1. Dataset — recomendado: **Home Credit Default Risk** (Kaggle, 2018)

| Dataset | Tamanho | Veredito |
|---|---|---|
| **Home Credit Default Risk** | ~307k clientes, 122 colunas + tabelas relacionais (bureau, bureau_balance, previous_application, installments, credit_card_balance) | ✅ **Recomendado.** Estrutura relacional fiel a um pipeline real de underwriting (aplicação + bureau + histórico). Mercado emergente (clientes "underbanked") — mais próximo do contexto de crédito ao consumidor brasileiro que dataset americano de cartão. |
| Give Me Some Credit | ~150k linhas, 10 features | 🔶 Secundário. Ainda citado em papers (2022-2025) como benchmark de interpretabilidade/fairness, mas dados de ~2009 e features rasas, sem bureau. Serve como baseline rápido/comparação. |
| UCI German Credit / Statlog | 1.000 linhas, 20 atributos, de 1994 | ❌ Pequeno demais para treino sério. Só didático. |
| HMDA (EUA) | — | ❌ **Descartado.** Registra só originação/aprovação/negação de hipoteca, **sem outcome de default**. Ligar a performance exige base privada (CoreLogic). |
| Brasil (qualquer) | — | ❌ **Confirmado: não existe** base pública com rótulo individual de inadimplência. Sigilo bancário (LC 105) + LGPD. Só existe agregado: BCB SCR.data por UF/modalidade/segmento. |

### 2. LGD / taxa de recuperação — premissa recomendada: recuperação de **15-30%** (LGD 70-85%)

- Basel Foundation IRB fixa LGD supervisionado de **45%** para exposições sênior não garantidas — piso *regulatório*, não empírico de varejo.
- Literatura empírica de *unsecured consumer credit* aponta LGD mais alto: **70-85%** (ScienceDirect, 2023 — LGD de empréstimos ao consumidor não garantidos; cartão de crédito citado em torno de 80% dada recuperação mínima via cobrança/charge-off).
- **Não** foi encontrado número oficial e recente do BCB para LGD de crédito pessoal brasileiro (a busca retorna taxa de *inadimplência*, não de recuperação pós-default).
- **Consequência para o ticket 0002:** a premissa de ~25% de recuperação sugerida inicialmente na sessão está dentro da faixa embasada — mas deve ser documentada no ADR como *estimativa de mercado internacional na ausência de dado público brasileiro*, não como fato brasileiro.

### 3. Fontes externas públicas para o agente (ticket 0008)

| Fonte | Endpoint | Custo/credencial |
|---|---|---|
| **BCB SGS API** | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json` (SELIC=11, IPCA, inadimplência por segmento) | Gratuita, sem chave |
| **BCB Dados Abertos / SCR.data** | `dadosabertos.bcb.gov.br` — inadimplência agregada PF por UF/modalidade | Gratuita, sem autenticação |
| **IBGE SIDRA / Agregados** | `servicodados.ibge.gov.br/api/docs/agregados` — desemprego (PNAD Contínua), PIB per capita por UF | Gratuita, sem chave |

⚠️ **Não existe** API pública gratuita de score de crédito individual no Brasil (Serasa/Boa Vista exigem contrato pago). O agente pode contextualizar risco macro/regional, **nunca** simular consulta a bureau individual.

### ⚠️ Conflito aberto gerado por este resultado

As fontes externas viáveis são **brasileiras**, mas o dataset recomendado (Home Credit) é de **mercados emergentes não-brasileiros** (Rússia, Indonésia, Vietnã etc., com região anonimizada). Consultar SELIC/IBGE para contextualizar um cliente do Home Credit seria incoerente. Ver ticket 0009.
