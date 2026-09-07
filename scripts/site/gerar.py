"""Gera docs/index.html (GitHub Pages) a partir do snapshot versionado de monitoramento V3.

Uso: python scripts/site/gerar.py
Roda a partir de qualquer diretorio; caminhos sao relativos a este arquivo.
"""

import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SNAPSHOT = RAIZ / "data" / "processed" / "monitoramento_v3.json"
TEMPLATE = AQUI / "template.html"
SAIDA = RAIZ / "docs" / "index.html"

dados = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

# `<` escapado: o JSON vive dentro de <script>, e uma sequencia "</script>"
# em qualquer string do snapshot encerraria a tag no parser do navegador.
embutido = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

html = TEMPLATE.read_text(encoding="utf-8")
if "__SNAPSHOT_JSON__" not in html:
    raise ValueError("template sem o marcador __SNAPSHOT_JSON__")

SAIDA.parent.mkdir(exist_ok=True)
SAIDA.write_text(html.replace("__SNAPSHOT_JSON__", embutido), encoding="utf-8")

print(f"{SAIDA.relative_to(RAIZ)}: {SAIDA.stat().st_size / 1024:.1f} KB")
print(f"coortes: {[c['coorte'] for c in dados['coortes']]}")
