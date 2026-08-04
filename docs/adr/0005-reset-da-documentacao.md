# ADR-0005: Reset da documentação — `docs/adr/` do zero, sem baseline herdado

**Data**: 2026-08-04
**Status**: Accepted
**Contexto**: PayFlow — decisão D5 da `SPEC_FINAL.md`, ticket Wayfinder [0005](../wayfinder/refatoracao-camada-agentica/0005-housekeeping-docs-legado.md)

---

## 1. CONTEXTO (O QUÊ?)

O projeto carregava dois documentos de refatoração da fase Pós-Tech — `REFATORACAO.md` e `produtizando.md` — que descreviam débitos técnicos **já 100% resolvidos** (a jornada notebook → API em produção).

Com a chegada de uma refatoração que é, na prática, projeto novo (ADR-0001), a pergunta era: arquivar esse histórico como ADR-0000 baseline, ou começar limpo?

## 2. DECISÃO (POR QUÊ?)

**Excluir os dois documentos e criar `docs/adr/` vazio, começando no ADR-0001.**

- **Documento que descreve débito resolvido não é histórico útil — é ruído de contexto.** A jornada notebook → produção continua contada no README (onde tem valor narrativo); repetida em arquivo de refatoração morto, só compete por atenção humana e por janela de contexto de agente.
- **Um ADR-0000 baseline daria falsa continuidade.** As decisões novas não derivam das antigas: o dataset muda, o esquema muda, a política de decisão muda. Encadear ADR-0001 num baseline sintético sugeriria uma linhagem que não existe.
- O `git log` preserva o conteúdo excluído — nada foi perdido, só removido do caminho.

**Regra herdada para daqui em diante** (ADR-0006): débito técnico **resolvido** não é deletado — fica ~~riscado~~ no `AGENTS.md` apontando o ADR que o resolveu. O reset vale uma vez, na fronteira entre os dois projetos; depois dela, o histórico é acumulativo.

---

## 3. CONSEQUÊNCIAS

**Positivas:**
- Documentação da refatoração começa sem dívida narrativa.
- Numeração dos ADRs casa 1:1 com as decisões D1–D8, sem offset confuso.

**Negativas / limitações:**
- Quem chegar ao repositório sem `git log` não vê a jornada de produtização — depende do README manter essa narrativa viva.
- Perde-se o exemplo concreto de "débito riscado" que os arquivos antigos documentavam.

---

## 4. ALTERNATIVAS DESCARTADAS

| Opção | Por quê rejeitada |
|-------|----------------------|
| ADR-0000 baseline com o histórico antigo | Falsa continuidade — as decisões novas não derivam das antigas |
| Mover para `docs/legado/` | Mantém o ruído de contexto com custo de organização; `git log` já cumpre o papel |
| Manter na raiz | Arquivo solto documentando débito resolvido é caso de Caos Funcional |

---

## 5. IMPACTO & VALIDAÇÃO

**Métrica de sucesso:** raiz do repositório sem arquivos de refatoração órfãos; `docs/adr/` com numeração contínua a partir de 0001; `AGENTS.md` com a seção de débitos vivos criada **desde o dia zero**, não retroativamente.

---

## 6. LINKS RELACIONADOS

- Ticket `0005-housekeeping-docs-legado.md`
- ADR-0006 (padrão de rigor que institui a política de débito riscado)
- `metodologia/AI_ENGINEERING/01_caos_funcional.md` (base de conhecimento)
