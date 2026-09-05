# Ticket 0002 — Qualidade, segurança e reprodutibilidade

## Problema

Um projeto de portfólio precisa funcionar em clone limpo e falhar de forma explícita quando faltam dados, contratos ou segredos.

## Resultado esperado

- executar testes, compilação, verificação de dependências e inspeção de segredos;
- confirmar contratos fail-closed da V3;
- tornar dependências diretas e variáveis de ambiente explícitas;
- registrar riscos que dependem de dado externo ou premissa não medida.

## Fora de escopo

Publicar serviço de produção, chamar APIs pagas, retreinar modelos ou baixar novamente os datasets.
