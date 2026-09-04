# Spec 0006 — Evidência estatística e maturação de coorte

**Data:** 2026-09-04
**Status:** Implementada — revisão humana pendente
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Impedir que o semáforo do PayFlow libere um modelo com evidência insuficiente.
Uma coorte só poderá receber `MANTER` quando seus desfechos tiverem amadurecido
pela janela declarada, a amostra e os eventos mínimos forem atingidos, e AUC e
calibração respeitarem limites explícitos.

## Escopo

Inclui contrato de maturação por data de decisão, política configurável de
evidência, intervalo de confiança da AUC, bloqueio explícito no fluxo integrado
e normalização de datas em UTC. Não inclui re-treino automático, aprovação de
crédito individual, dashboard ou PSI/data drift.

## Critérios de aceitação

1. Target preenchido antes do fim da janela não é tratado como maduro.
2. Coorte abaixo do mínimo de contratos ou inadimplentes recebe `AGUARDAR`.
3. `MANTER` exige AUC e Brier dentro dos limites declarados e IC da AUC acima do
   limite mínimo definido pela política.
4. Bloqueio de disponibilidade retorna `BLOQUEAR` no resultado integrado sem
   chamar o scorer.
5. Datas com e sem timezone são comparadas em UTC ou bloqueadas de forma
   estruturada, nunca por `TypeError` bruto.
6. Testes novos falham antes da implementação e toda a suíte passa depois.

## Riscos e política de entrada

Os limiares não são apetite de risco universal: são parâmetros explícitos da
instituição. O Home Credit prova o mecanismo, não autoriza escolher esses
limiares para uma carteira brasileira real. Não há PII nem credenciais.

## Evidência esperada

Um relatório por coorte contendo `n`, inadimplentes, janela de maturação, AUC e
IC, Brier e a decisão com motivo rastreável.

**Evidência executada:** 236 testes passaram. Os testes cobrem maturação por
janela, amostra/eventos mínimos, IC da AUC, Brier, bloqueio explícito e datas
com timezone misto.
