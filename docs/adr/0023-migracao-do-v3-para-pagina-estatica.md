# ADR-0023: Migração do V3 de Streamlit para página estática (GitHub Pages)
**Data:** 2026-09-06
**Status:** Accepted
**Proposto por:** Luiz Maibashi
**Contexto:** dashboard de confiabilidade por coorte (V3)

## Contexto

O ADR-0020 fixou o V3 como app Streamlit alimentado por snapshot JSON, decisão
correta na época: separava a narrativa de confiabilidade da demo agêntica sem
exigir dataset bruto no deploy. Na prática de portfólio, dois problemas
apareceram que o ADR-0020 não previa.

Primeiro, o app não tinha uso operacional além de exibir o snapshot: zero
computação ao vivo, um único widget interativo (`st.radio` de 3 opções). Todo o
peso de rodar um servidor Python ficava sem contrapartida.

Segundo, o custo de visualização. Streamlit Cloud hiberna sem tráfego e leva
dezenas de segundos para acordar. Para quem abre o link vindo de um currículo
ou de uma conversa, esse tempo de espera é o primeiro (e às vezes único)
contato com o projeto.

## Decisão

Reescrever a interface do V3 como página HTML estática, publicada via GitHub
Pages a partir de `docs/index.html`. O gerador (`scripts/site/gerar.py` +
`scripts/site/template.html`) lê o mesmo `data/processed/monitoramento_v3.json`
do ADR-0020 e embute o snapshot inteiro no HTML como JSON inline. Nenhum número
é digitado à mão: o build injeta o contrato já validado, os gráficos (séries de
AUC/Brier, calibração por faixa) são desenhados em SVG por um script de
~300 linhas sem dependência externa.

`app/main_v2.py` (demo com LLM ao vivo) permanece em Streamlit, sem mudança:
computação real justifica o runtime.

## Consequências

### Positivas

- carregamento instantâneo, sem cold start de plataforma gratuita;
- zero dependência de runtime (nenhum `requirements.txt` a manter para a página);
- arquivo único de 51 KB, versionado, auditável por `git diff`;
- o mesmo contrato de dados do ADR-0020 continua sendo a fonte única.

### Negativas

- qualquer mudança de layout exige editar HTML/CSS/JS em vez de Python;
- perde a introspeção interativa livre do Streamlit (o app agora só expõe as
  interações desenhadas no template: seletor de safra, hover nos gráficos,
  scrollytelling guiado);
- atualizar o site exige rodar `scripts/site/gerar.py` e commitar o
  `docs/index.html` resultante, um passo manual a mais que `git push` sozinho.

## Alternativas descartadas

| Alternativa | Vantagem | Motivo da rejeição |
|---|---|---|
| Manter Streamlit, só trocar tema/CSS | Menor esforço | Teto de customização baixo: DOM do Streamlit usa classes com hash que mudam a cada versão, CSS por cima quebra em silêncio. Não resolve o cold start. |
| Framework de dashboard JS (Observable, Plotly Dash) | Mais recursos prontos | Runtime novo para manter, sem ganho real sobre HTML+SVG dado que o dado é só leitura de snapshot. |
| Manter Streamlit Cloud e aceitar o cold start | Zero trabalho de migração | O tempo de espera é exatamente o que afasta quem abre o link uma vez só, o público-alvo do portfólio. |

## Impacto e validação

Sem a migração, o link do V3 arrisca ser abandonado antes de carregar. Com a
página estática, o primeiro frame já mostra o painel completo (sem animação de
construção, sem tela em branco esperando dado). Validação: inspeção visual da
página publicada, gate mecânico de zero caracteres invisíveis/travessão no HTML
gerado (script ad-hoc, não promovido a teste automatizado ainda), e
`git diff docs/index.html` contra o snapshot para confirmar que os números
batem byte a byte com o JSON de origem.
