# ADR-0006: Padrão de rigor herdado do `stable-treasury`

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D6 da `SPEC_FINAL.md`, ticket Wayfinder [0006](../wayfinder/refatoracao-camada-agentica/0006-nivel-de-disciplina-stable-treasury.md)

---

## 1. CONTEXTO (O QUÊ?)

`stable-treasury` é o padrão-ouro atual do portfólio: 12 ADRs, 9 suítes de teste, auditorias datadas, val-loop, 26 débitos técnicos vivos, escopo negativo explícito. "Trazer esse nível para o PayFlow" é frase vazia se não virar lista de artefatos verificáveis.

Este ADR existe para transformar uma intenção em **Definition of Done**.

## 2. DECISÃO (POR QUÊ?)

### 2.1 O princípio-raiz (o que realmente se herda)

> **Onde existe dado gratuito que substitua uma premissa por medição, substituir. Onde o problema é estrutural, expor o disclaimer — não fingir uma correção que não existe para ser feita de graça.**
> *(stable-treasury, ADR-0011 §6)*

Aplicações diretas neste projeto:

| Situação | Aplicação do princípio |
|---|---|
| LGD | Não existe número público do BCB para crédito pessoal → **premissa declarada** com faixa e fonte internacional, jamais número mágico apresentado como medição |
| Margem (`M`) | **Existe** dado gratuito (juros implícitos do contrato) → vira **medição**, não premissa (ADR-0002 §2.4) |
| Dispersão de `m/ℓ` | **Existe** dado → medir antes de implementar o motor, em vez de assumir que varia (ADR-0002 §5) |
| Cenário macro | Ou move um corte de forma rastreável, ou **não entra no sistema** (ADR-0008) |
| Cliente brasileiro | Estrutural: o dataset não é BR → disclaimer, nunca correção fingida |

### 2.2 Práticas genéricas — replicar

| Prática | Alvo aqui |
|---|---|
| `AGENTS.md` com Linguagem Ubíqua, cada termo amarrado ao ADR que o definiu | ✅ criado |
| `docs/adr/` numerado com status (`Accepted`/`Proposed`/`Partially Superseded` — ADR nunca é apagado, é superseded) | ✅ 8 ADRs |
| Débitos técnicos numerados e **vivos**: resolvidos ficam ~~riscados~~ apontando o ADR, nunca deletados | ✅ 11 itens desde o dia zero |
| Escopo negativo explícito | ✅ no `AGENTS.md` |
| Seção de honestidade no README ("o que este projeto assume abertamente") | ✅ criada (v1 e v2 separadas) |
| ≥1 arquivo de teste por módulo; a Camada 2 tem teste próprio | ⬜ pendente |
| `docs/audit/` com achados numerados e severidade (🔴/🟠/🟡/🟢) | ⬜ pendente (≥1 pós-implementação) |
| `docs/val-loop/` — validar premissa de negócio **antes** de implementar | ⬜ usar para a premissa de LGD e para o desenho do cenário macro |

### 2.3 O que **não** se herda

VaR/Expected Shortfall, order book, depeg, IOF, trilhos de pagamento — matemática do domínio de risco de mercado. O análogo aqui é risco **de crédito**: PD, LGD, EAD, perda esperada.

> **Importar o rigor, não a matemática.** Copiar VaR para um projeto de crédito seria cargo cult — o oposto do que este ADR pretende.

### 2.4 Definition of Done da refatoração

1. `AGENTS.md` com Linguagem Ubíqua + débitos numerados + escopo negativo. ✅
2. `docs/adr/0001…N` — mínimo 6, um por decisão. ✅ (8)
3. Testes: ≥1 arquivo por módulo, incluindo paridade treino-serving reescrita para o esquema Home Credit. ⬜
4. Eval set versionado + relatório com `n` e intervalo. ⬜
5. `docs/audit/` com ≥1 auditoria pós-implementação. ⬜
6. README com seção "o que este projeto assume abertamente". ✅

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- "Ser mais rigoroso" vira checklist verificável, não intenção.
- Débito vivo e riscado dá ao leitor externo a trilha de amadurecimento do projeto — sinal forte em avaliação técnica.

**Negativas / limitações:**
- Custo real de documentação por decisão; o risco é o doc andar mais rápido que o código e virar ficção.
- **Rigor documental não é rigor de engenharia.** Um projeto com 8 ADRs e nenhum teste é pior que o inverso: cria aparência de disciplina sem lastro. Os itens 3–6 da DoD são o lastro, e estão todos pendentes.

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| "Ser mais rigoroso" sem lista | Não verificável; morre na primeira sessão apressada |
| Copiar a estrutura completa do `stable-treasury`, incluindo domínio | Cargo cult — VaR/ES não tem função em crédito |
| Documentar só ao final da implementação | Perde o efeito principal do ADR: forçar a decisão a ser explícita **antes** de virar código |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** os 6 itens da DoD marcados, com evidência (arquivo, teste passando, relatório com `n`).

**Risco de regressão vigiado:** proporção entre linhas de documentação e linhas de código/teste. Se a documentação crescer e os itens 3–6 seguirem ⬜ na próxima sessão, o projeto está produzindo aparência de rigor — e este ADR terá falhado no seu propósito.

---

## 6. LINKS RELACIONADOS

- Ticket `0006-nivel-de-disciplina-stable-treasury.md`
- `PROJETOS/02_PORTFOLIO/stable-treasury/` (AGENTS.md, `docs/adr/`, `docs/audit/`, `docs/val-loop/`)
- ADR-0005 (reset que abriu espaço para este padrão)
