---
tipo: pesquisa
status: resolvido
criado: 2026-08-04
---

# Ticket 0006: Mapear o que replicar do stable-treasury

## Bloqueio
`stable-treasury` foi identificado nesta sessão como o padrão-ouro atual do portfólio (9 arquivos de teste, 12 ADRs, val-loop documentado, deploy ao vivo, honestidade explícita sobre limitações). Antes de "trazer esse nível" para o `payflow_inadimplencia`, precisa mapear concretamente **o que** replicar, não só "ser mais rigoroso":

1. Ler a estrutura de `docs/adr/` e `docs/val-loop/` do `stable-treasury` como referência de formato.
2. Identificar quais práticas são genéricas (aplicam a qualquer projeto: ADR por decisão arquitetural, seção "o que este projeto assume abertamente") vs. específicas do domínio de risco de mercado (ex: VaR/ES não se aplica a crédito).
3. Definir a lista mínima de artefatos que o `payflow_inadimplencia` deveria ter ao final da refatoração para estar no mesmo patamar de rigor (ex: N testes cobrindo a Camada 2, ADRs para cada decisão dos tickets 0001-0004, um `AGENTS.md` próprio do projeto com Linguagem Ubíqua).

## Resultado

Mapeado em 2026-08-04, lendo `PROJETOS/02_PORTFOLIO/stable-treasury/` (AGENTS.md, 12 ADRs, docs/audit, docs/val-loop, 9 arquivos de teste).

### O princípio-raiz (o mais importante a replicar)

Do ADR-0011 §6 / ADR-0012 do `stable-treasury`:

> Onde existe dado gratuito que substitua uma **premissa** por **medição**, substituir. Onde o problema é **estrutural**, expor o disclaimer — não fingir uma correção que não existe para ser feita de graça.

Aplicação direta neste projeto: a premissa de LGD (ticket 0002) **não** tem dado público brasileiro → é premissa declarada, com faixa e fonte internacional, nunca um número mágico apresentado como medição. O mesmo vale para o cenário macro (ticket 0009): ou ele move um corte de forma rastreável, ou não entra.

### Práticas genéricas — replicar

| Prática | Como é no `stable-treasury` | Alvo aqui |
|---|---|---|
| **`AGENTS.md` com Linguagem Ubíqua** | Glossário de ~40 termos, **cada um amarrado ao ADR que o definiu** | Criar. Termos-alvo: PD, LGD, EAD, perda esperada, faixa de indiferença, memo de crédito, trajectory quality, cenário de stress, ferramenta de caso × de cenário |
| **`docs/adr/` numerado com status** | 12 ADRs; status inclui `Accepted`, `Proposed`, `Partially Superseded` (ADR pode ser parcialmente substituído por outro, sem apagar histórico) | Um ADR por decisão dos tickets 0001/0002/0003/0004/0008/0009 |
| **Débitos técnicos numerados e vivos** | 26 itens; resolvidos ficam ~~riscados~~ apontando o ADR que resolveu — **não são deletados** | Criar seção no `AGENTS.md` desde o dia zero |
| **Escopo negativo explícito** | Lista do que o projeto **nunca** fará (sem execução real, sem multi-tenant, sem assessoria jurídica) | Definir: sem decisão de crédito autônoma sem humano, sem consulta a bureau individual, sem PII real |
| **Seção de honestidade no README** | "O que este projeto assume abertamente" | Replicar |
| **1 arquivo de teste por módulo** | 9 testes para 9 módulos `src/` | Mesma proporção; a Camada 2 (agente) precisa de teste próprio |
| **`docs/audit/`** | Auditorias datadas com achados numerados e severidade (🔴/🟠/🟡/🟢) | Rodar ao menos uma auditoria ao final da refatoração |
| **`docs/val-loop/`** | Validação de premissa de negócio **antes** de implementar | Usar para validar a premissa de LGD e o desenho do cenário macro |

### Práticas específicas do domínio — **não** replicar

VaR/Expected Shortfall, order book, depeg, IOF, trilhos de pagamento — são do domínio de risco de mercado/tesouraria. O análogo aqui é risco **de crédito**: PD (probabilidade de default), LGD, EAD, perda esperada. Não importar a matemática, importar o **rigor**.

### Lista mínima de artefatos-alvo (definition of done da refatoração)

1. `AGENTS.md` do projeto, com Linguagem Ubíqua + débitos técnicos + escopo negativo.
2. `docs/adr/0001…N` — um ADR por decisão de arquitetura (mínimo 6, um por ticket decidido).
3. Suíte de testes com ao menos 1 arquivo por módulo, incluindo teste de paridade treino-serving reescrito para o esquema do Home Credit.
4. Eval set versionado da Camada 2 + relatório de avaliação com `n` e intervalo de confiança (regra do `AGENTS.md` raiz: nunca reportar proporção sem `n` e sem intervalo).
5. `docs/audit/` com ao menos uma auditoria pós-implementação.
6. README com seção de limitações assumidas abertamente.
