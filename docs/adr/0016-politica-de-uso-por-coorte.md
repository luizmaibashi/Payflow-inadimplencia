# ADR-0016: Política de uso por coorte

**Data:** 2026-09-04
**Status:** Accepted
**Contexto:** PayFlow V3 — decisão de manter, revisar ou bloquear o uso do score

## Contexto

Métricas isoladas não dizem o que fazer. Porém, o dataset público não fornece
apetite de risco, custo de erro ou perda real para inventar limites financeiros.
A política precisa sinalizar evidência, não fingir uma decisão de concessão.

## Decisão

- **BLOQUEAR:** o gate de disponibilidade falha. Nenhum score é produzido.
- **AGUARDAR:** target não amadureceu, previsão está incompleta ou a coorte não
  permite medir AUC.
- **PESQUISA:** execução em modo exploratório; métricas podem ser vistas, mas
  nunca liberam uso operacional.
- **MANTER:** execução estrita, coorte avaliável e AUC não caiu mais de 0,03 em
  relação à referência.
- **REVISAR:** execução estrita e queda de AUC maior que 0,03; investigar dados,
  população e calibração antes de continuar usando o modelo.

O Brier é exibido, mas não dispara decisão sozinho: ele muda junto com a taxa
base de default e precisa de análise de calibração/contexto.

## Por quê

O limiar de 0,03 já é o critério de falsificação da tese. Ele é uma tolerância
metodológica inicial, não apetite de risco de banco. Sem esse limite, um painel
apenas mostra números; com ele, gera uma ação proporcional e revisável.

## Consequências e PAVC

- Evita que AUC baixa ou target ausente seja interpretado como sucesso.
- Não transforma um proxy exploratório em produção, mesmo com AUC estável.
- A política pode ser conservadora demais em coortes pequenas; `n` e IC seguem
  no boletim para que o gestor veja a incerteza antes de agir.
- Uma queda de AUC não prova a causa. `REVISAR` abre investigação; não acusa
  drift, dado ruim ou modelo ruim automaticamente.
