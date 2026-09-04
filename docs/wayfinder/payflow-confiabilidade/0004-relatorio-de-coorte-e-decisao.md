---
tipo: tarefa-simples
status: resolvido
criado: 2026-09-04
---

# Ticket 0004: Relatório de coorte e decisão

## Bloqueio

Métricas soltas não dizem ao gestor o que fazer. AUC e Brier também só existem depois que o target amadurece.

## Resultado

Parcialmente entregue em `app/estabilidade_coorte.py`, com 9 testes em
`tests/test_estabilidade_coorte.py`. O relatório mede cobertura, taxa de
default com `n` e IC 95% de Wilson, AUC e Brier somente para coorte completa.
Coorte vazia, target não amadurecido, previsão incompleta e target sem variação
ficam explícitos e não recebem métricas falsas.

A política de uso foi entregue pela ADR-0016: o dado bloqueado não é pontuado,
coorte sem evidência aguarda, proxy recebe `PESQUISA`, queda de AUC superior a
0,03 recebe `REVISAR` e execução estrita estável recebe `MANTER`. A tolerância
de 0,03 é metodológica para o case, não apetite de risco de uma instituição.

O encadeamento seguro foi entregue em `app/monitoramento_coorte.py`: primeiro
o gate, depois o scorer injetado e por último o boletim. Cinco testes provam
que o scorer não é chamado quando o gate falha, o modo exploratório é preservado
e coorte vazia não parece sucesso. A política de semáforo continua pendente de
uma tolerância de risco que o dado público não define.

A execução reproduzível foi entregue pela spec 0007 e pelo script
`scripts/proxy_estabilidade_reproduzivel.py`. Ela reconstrói 1.526.659 casos,
treina em 733.757 e avalia 2019-Q4, 2020-H1 e 2020-H2. As AUCs observadas foram
0,6148, 0,6089 e 0,6194, todas com IC95%, Brier, `n` e eventos no relatório.

A ADR-0017 fechou a evidência mínima: tamanho da amostra, número de defaults,
limite inferior do IC da AUC e tolerância de Brier. O status exploratório não
libera uso operacional, mas também não mascara deterioração: AUC ou Brier fora
da tolerância agora produz `REVISAR` antes da classificação `PESQUISA`.
