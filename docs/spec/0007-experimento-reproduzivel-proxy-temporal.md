# Spec 0007 — Experimento reproduzível do proxy temporal

**Data:** 2026-09-04
**Status:** Implementada; revisão humana pendente
**Dono da aprovação de merge:** Luiz Maibashi

## Objetivo

Substituir a execução ad hoc do proxy de seis variáveis por um experimento
versionado que reconstrói os dados, treina o mesmo tipo de modelo, pontua as
coortes futuras e entrega métricas e decisões auditáveis.

## Escopo

Inclui junção `train_base` + partições `train_static_0`, corte de treino em
2019-09-30, `HistGradientBoostingClassifier` determinístico e avaliação em
2019-Q4, 2020-H1 e 2020-H2. O resultado passa pelo contrato proxy, maturação,
boletim e política de uso.

Não inclui otimização de hiperparâmetros, comparação de vários algoritmos,
salvamento de modelo produtivo, PSI, aprovação point-in-time das features ou
alegação de transferência direta para uma carteira brasileira.

## Critérios de aceitação

1. A execução falha se faltar coluna, houver `case_id` duplicado ou a junção
   deixar casos sem features estáticas.
2. Nenhum caso posterior a 2019-09-30 entra no treino.
3. Datas recebem exatamente uma partição temporal conhecida.
4. Modelo e bootstrap usam seed fixa e parâmetros registrados.
5. O relatório inclui amostra, eventos, inadimplência com IC, AUC com IC,
   Brier, decisão e as limitações de proxy/maturação.
6. Os números canônicos ficam próximos da reconstrução diagnóstica desta spec:
   AUC 0,6148 / 0,6089 / 0,6194.
7. Testes começam vermelhos e a suíte completa termina verde.

## Restrições e riscos

O target da competição representa default, mas a página oficial não informa
um horizonte que autorize escolher 30, 90 ou 180 dias. Por isso
`data_referencia` e `janela_dias` são entradas obrigatórias e o relatório as
marca como hipótese de demonstração. As seis features seguem como
`PROXY_SEMANTICA`, logo a decisão operacional esperada é `PESQUISA`.

Não há PII, credenciais, rede ou dado de cliente real.

## Evidência de execução

Execução canônica em 2026-09-04:

```bash
python scripts/proxy_estabilidade_reproduzivel.py --data-referencia 2021-01-04 --janela-dias 90 --bootstrap 100
```

| Coorte | n | Inadimplentes | Taxa (IC95%) | AUC (IC95%) | Brier | Decisão |
|---|---:|---:|---:|---:|---:|---|
| 2019-Q4 | 337.005 | 12.147 | 3,60% [3,54%; 3,67%] | 0,6148 [0,6105; 0,6200] | 0,0346 | PESQUISA |
| 2020-H1 | 305.657 | 11.771 | 3,85% [3,78%; 3,92%] | 0,6089 [0,6044; 0,6139] | 0,0368 | PESQUISA |
| 2020-H2 | 150.240 | 3.175 | 2,11% [2,04%; 2,19%] | 0,6194 [0,6105; 0,6299] | 0,0206 | PESQUISA |

O experimento reconstrói 1.526.659 casos e usa 733.757 no treino. O
resultado `PESQUISA` não reprova o desempenho. Ele impede que features sem
prova point-in-time sejam confundidas com insumos autorizados para produção.

## Auditoria PAVC

### Três formas de a solução enganar

1. As features podem conter informação conhecida apenas depois da decisão.
   Mitigação: contrato `PROXY_SEMANTICA`, modo exploratório e proibição de
   `MANTER` operacional.
2. A janela de 90 dias pode não representar a definição real do target.
   Mitigação: parâmetro obrigatório e hipótese escrita no relatório.
3. O rótulo `PESQUISA` poderia esconder queda de AUC ou piora de Brier.
   Mitigação: a política agora verifica deterioração antes de aplicar a
   restrição de uso exploratório, com teste de regressão específico.

### Cinco cenários de borda

| Cenário | Comportamento verificado |
|---|---|
| Vazio | Coorte vazia não vira sucesso; treino ou avaliação vazios falham. |
| Extremo | A execução completa processou 1.526.659 linhas; escala maior ainda não foi testada. |
| Corrupto | Data malformada, target não binário, chave duplicada e join incompleto falham explicitamente. |
| Concorrência | Não aplicável nesta etapa: o fluxo é local, somente leitura e não atualiza estado compartilhado. |
| Temporal | Corte de treino e coortes não se sobrepõem; datas são normalizadas em UTC. |

Resultado PAVC: aprovado para demonstração reproduzível. Reprovado para
uso institucional até existir contrato point-in-time e definição real de
maturação do target.

Gate final: `242 passed` em 2026-09-04 e `git diff --check` sem erro.
