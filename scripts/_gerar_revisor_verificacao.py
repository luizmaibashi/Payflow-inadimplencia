"""Gera o HTML de VERIFICACAO dos labels contra os memos versionados.

Nao e o revisor original (rotulagem do zero): cada caso ja vem com o label
anterior do Luiz pre-preenchido, e a tarefa e CONFIRMAR ou CORRIGIR contra o
memo de hoje. Existe porque a rodada de 2026-08-08 regerou os memos e o par
label<->memo se desfez parcialmente (ver .gitignore, debito #30).

Uso: python scripts/_gerar_revisor_verificacao.py
Saida: scripts/_revisor_verificacao.html (temporario, nao versionar)
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LABELS = RAIZ / "data" / "labels" / "task_completion_labels.json"
MEMOS = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
SAIDA = RAIZ / "scripts" / "_revisor_verificacao.html"


TEMPLATE = r"""<title>Verificacao de labels - payflow Camada 2</title>
<style>
  :root {
    --bg: #eef2f0;
    --bg-card: #ffffff;
    --bg-raised: #f7f9f8;
    --ink: #1b2422;
    --ink-soft: #55625d;
    --line: #d3ddd8;
    --accent: #1f6f5c;
    --accent-soft: #d9ece6;
    --accent-ink: #0f4438;
    --ok: #2f7d4f;
    --ok-soft: #e2f2e6;
    --falha: #b6392f;
    --falha-soft: #fbe6e3;
    --elim: #a56a10;
    --elim-soft: #f6e9d2;
    --font-display: Iowan Old Style, Palatino Linotype, Georgia, serif;
    --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --font-mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #12181a; --bg-card: #1a2224; --bg-raised: #202a2c;
      --ink: #e8efec; --ink-soft: #9fb0aa; --line: #2c3a3a;
      --accent: #5cc4ab; --accent-soft: #1c3833; --accent-ink: #a9e8d7;
      --ok: #5cb37c; --ok-soft: #16311f;
      --falha: #e08277; --falha-soft: #3a1e1b;
      --elim: #dcac57; --elim-soft: #3a2c11;
    }
  }
  :root[data-theme="dark"] {
    --bg: #12181a; --bg-card: #1a2224; --bg-raised: #202a2c;
    --ink: #e8efec; --ink-soft: #9fb0aa; --line: #2c3a3a;
    --accent: #5cc4ab; --accent-soft: #1c3833; --accent-ink: #a9e8d7;
    --ok: #5cb37c; --ok-soft: #16311f;
    --falha: #e08277; --falha-soft: #3a1e1b;
    --elim: #dcac57; --elim-soft: #3a2c11;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 15px;
    line-height: 1.5;
    -webkit-tap-highlight-color: transparent;
  }
  .wrap { max-width: 720px; margin: 0 auto; padding: 0 0 96px; }

  header.top {
    position: sticky; top: 0; z-index: 20;
    background: var(--bg);
    border-bottom: 1px solid var(--line);
    padding: 10px 16px 12px;
  }
  .top-row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
  .brand { font-family: var(--font-display); font-size: 17px; font-weight: 600; }
  .brand small {
    display: block; font-family: var(--font-body); font-size: 11px;
    color: var(--ink-soft); font-weight: 400; text-transform: uppercase;
    letter-spacing: 0.06em; margin-top: 1px;
  }
  .count { font-variant-numeric: tabular-nums; font-size: 13px; color: var(--ink-soft); white-space: nowrap; }
  .progress { height: 4px; border-radius: 2px; background: var(--line); margin-top: 10px; overflow: hidden; }
  .progress > i { display: block; height: 100%; background: var(--accent); transition: width .25s ease; }

  main { padding: 18px 16px 0; }

  .case-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
  .case-id { font-family: var(--font-display); font-size: 26px; font-variant-numeric: tabular-nums; }
  .case-id span { color: var(--ink-soft); font-size: 14px; font-family: var(--font-body); display: block; margin-bottom: 2px; }
  .badges { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
  .badge {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 3px 8px; border-radius: 20px; font-weight: 600; white-space: nowrap;
  }
  .badge.rec-APROVAR { background: var(--ok-soft); color: var(--ok); }
  .badge.rec-NEGAR { background: var(--falha-soft); color: var(--falha); }
  .badge.rec-DEFERIR { background: var(--elim-soft); color: var(--elim); }
  .badge.novo { background: var(--accent-soft); color: var(--accent-ink); }
  .badge.atencao { background: var(--elim-soft); color: var(--elim); }
  .badge.violacao { background: var(--elim-soft); color: var(--elim); }

  section.block {
    background: var(--bg-card);
    border: 1px solid var(--line);
    border-radius: 10px;
    margin-bottom: 12px;
    overflow: hidden;
  }
  .block-h {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; cursor: pointer; user-select: none;
    border-bottom: 1px solid transparent;
  }
  .block-h.open { border-bottom-color: var(--line); }
  .block-h h2 {
    margin: 0; font-size: 12px; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--ink-soft); font-weight: 600;
  }
  .chev { font-size: 11px; color: var(--ink-soft); transition: transform .15s ease; }
  .block-h.open .chev { transform: rotate(90deg); }
  .block-body { padding: 4px 14px 14px; display: none; }
  .block-body.open { display: block; }

  .tool { margin-bottom: 10px; }
  .tool:last-child { margin-bottom: 0; }
  .tool-name {
    font-family: var(--font-mono); font-size: 12px; color: var(--accent-ink);
    background: var(--accent-soft); display: inline-block; padding: 2px 7px;
    border-radius: 5px; margin-bottom: 5px;
  }
  .kv {
    font-family: var(--font-mono); font-size: 12.5px; color: var(--ink);
    background: var(--bg-raised); border-radius: 7px; padding: 8px 10px;
    display: grid; grid-template-columns: auto 1fr; gap: 2px 10px;
    font-variant-numeric: tabular-nums; overflow-x: auto;
  }
  .kv b { color: var(--ink-soft); font-weight: 400; }

  .fato { display: flex; gap: 8px; padding: 7px 0; border-top: 1px solid var(--line); font-size: 13.5px; }
  .fato:first-of-type { border-top: none; }
  .peso-mark { flex: none; width: 18px; text-align: center; font-weight: 700; font-family: var(--font-mono); }
  .peso-favoravel .peso-mark { color: var(--ok); }
  .peso-desfavoravel .peso-mark { color: var(--falha); }
  .peso-neutro .peso-mark { color: var(--ink-soft); }
  .fato-src { display: block; font-family: var(--font-mono); font-size: 11px; color: var(--ink-soft); margin-top: 2px; }
  .faltante { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line); font-size: 13px; }
  .faltante-title { color: var(--ink-soft); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 4px; }

  /* Label anterior: referencia, nao campo editavel */
  .anterior { background: var(--bg-raised); border-left: 3px solid var(--accent); }
  .anterior .linha-rubrica {
    display: flex; gap: 8px; align-items: baseline; padding: 5px 0;
    border-top: 1px solid var(--line); font-size: 13px;
  }
  .anterior .linha-rubrica:first-child { border-top: none; }
  .anterior .rub-nome { flex: none; width: 116px; color: var(--ink-soft); font-size: 12px; }
  .anterior .rub-v { font-weight: 700; font-size: 12px; }
  .anterior .rub-v.v-OK { color: var(--ok); }
  .anterior .rub-v.v-FALHA { color: var(--falha); }
  .anterior .rub-v.v-null { color: var(--elim); }
  .anterior .rub-ev { color: var(--ink-soft); font-style: italic; }

  .rubrica { border-top: 1px solid var(--line); padding: 14px 0 0; margin-top: 14px; }
  .rubrica:first-child { border-top: none; padding-top: 0; margin-top: 0; }
  .rubrica-h { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .rubrica-h h3 { margin: 0; font-size: 14.5px; font-weight: 600; }
  .rubrica-h .elim-tag { font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color: var(--elim); font-weight: 700; }
  .rubrica-q { font-size: 12.5px; color: var(--ink-soft); margin-bottom: 10px; }

  .toggle { display: flex; gap: 8px; margin-bottom: 10px; }
  .toggle button {
    flex: 1; padding: 9px 0; border-radius: 8px; border: 1px solid var(--line);
    background: var(--bg-raised); color: var(--ink-soft); font-size: 13px;
    font-weight: 600; cursor: pointer; font-family: inherit;
  }
  .toggle button.sel-ok { background: var(--ok-soft); color: var(--ok); border-color: var(--ok); }
  .toggle button.sel-falha { background: var(--falha-soft); color: var(--falha); border-color: var(--falha); }

  label.field-label {
    display: block; font-size: 11px; text-transform: uppercase;
    letter-spacing: .05em; color: var(--ink-soft); margin: 8px 0 4px;
  }
  textarea, select {
    width: 100%; border: 1px solid var(--line); border-radius: 8px;
    background: var(--bg-raised); color: var(--ink); font-family: var(--font-body);
    font-size: 13.5px; padding: 8px 10px;
  }
  textarea { resize: vertical; min-height: 52px; }

  .btn-confirmar {
    width: 100%; padding: 12px 0; border-radius: 8px; border: 1px solid var(--accent);
    background: var(--accent); color: #fff; font-size: 14px; font-weight: 600;
    cursor: pointer; margin-bottom: 12px; font-family: inherit;
  }
  .btn-confirmar.feito { background: var(--ok-soft); color: var(--ok); border-color: var(--ok); }

  nav.bottom {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 20;
    background: var(--bg); border-top: 1px solid var(--line);
    padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
  }
  .nav-row { max-width: 720px; margin: 0 auto; display: flex; gap: 8px; align-items: center; }
  .nav-row button {
    border-radius: 8px; border: 1px solid var(--line); background: var(--bg-card);
    color: var(--ink); font-size: 14px; font-weight: 600; padding: 11px 0;
    cursor: pointer; font-family: inherit;
  }
  .btn-prev, .btn-next { flex: 1; }
  .btn-next.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .btn-prev:disabled { opacity: .35; }
  .btn-export { flex: none; width: 42px; display: flex; align-items: center; justify-content: center; font-size: 16px; }

  .jump { display: flex; flex-wrap: wrap; gap: 4px; padding: 10px 16px 4px; }
  .jump button {
    width: 26px; height: 26px; border-radius: 6px; border: 1px solid var(--line);
    background: var(--bg-card); color: var(--ink-soft); font-size: 10.5px;
    font-variant-numeric: tabular-nums; cursor: pointer; padding: 0; font-family: inherit;
  }
  .jump button.done { background: var(--accent-soft); color: var(--accent-ink); border-color: var(--accent); }
  .jump button.novo { border-color: var(--elim); }
  .jump button.current { outline: 2px solid var(--accent); outline-offset: 1px; }
  .jump-toggle { padding: 8px 16px 0; font-size: 12px; color: var(--accent); cursor: pointer; user-select: none; }

  .aviso {
    margin: 14px 16px 0; padding: 12px 14px; border-radius: 10px;
    background: var(--accent-soft); color: var(--accent-ink); font-size: 13px;
  }
  .aviso b { font-variant-numeric: tabular-nums; }

  .toast {
    position: fixed; bottom: 78px; left: 50%; transform: translateX(-50%) translateY(8px);
    background: var(--ink); color: var(--bg); font-size: 13px; padding: 8px 16px;
    border-radius: 20px; opacity: 0; pointer-events: none;
    transition: opacity .2s ease, transform .2s ease; z-index: 30;
  }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

  .overlay {
    position: fixed; inset: 0; z-index: 40;
    background: color-mix(in srgb, var(--ink) 45%, transparent);
    display: none; align-items: flex-end; justify-content: center;
  }
  .overlay.show { display: flex; }
  .sheet {
    width: 100%; max-width: 720px; max-height: 82vh; background: var(--bg-card);
    border-radius: 16px 16px 0 0; padding: 16px 16px calc(16px + env(safe-area-inset-bottom));
    display: flex; flex-direction: column; gap: 10px;
    box-shadow: 0 -8px 30px rgba(0,0,0,.25);
  }
  .sheet h2 { margin: 0; font-size: 15px; }
  .sheet p { margin: 0; font-size: 12.5px; color: var(--ink-soft); }
  .sheet textarea { flex: 1; min-height: 220px; font-family: var(--font-mono); font-size: 11.5px; white-space: pre; overflow: auto; }
  .sheet-actions { display: flex; gap: 8px; }
  .sheet-actions button {
    flex: 1; border-radius: 8px; border: 1px solid var(--line); background: var(--bg-raised);
    color: var(--ink); font-size: 13.5px; font-weight: 600; padding: 11px 0;
    cursor: pointer; font-family: inherit;
  }
  .sheet-actions button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .sheet-close { align-self: flex-end; background: none; border: none; color: var(--ink-soft); font-size: 13px; cursor: pointer; padding: 4px 0; }

  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>

<div class="wrap">
  <header class="top">
    <div class="top-row">
      <div class="brand">Verificacao de labels<small>payflow &middot; memos de 2026-08-08</small></div>
      <div class="count" id="count">1 / __N_TOTAL__</div>
    </div>
    <div class="progress"><i id="progressBar" style="width:0%"></i></div>
  </header>

  <div class="aviso" id="aviso"></div>

  <div class="jump-toggle" id="jumpToggle">ver todos os casos &#9662;</div>
  <div class="jump" id="jump" style="display:none"></div>

  <main id="main"></main>
</div>

<nav class="bottom">
  <div class="nav-row">
    <button class="btn-prev" id="btnPrev">&larr; Anterior</button>
    <button class="btn-export" id="btnExport" title="Exportar JSON">&#8681;</button>
    <button class="btn-next primary" id="btnNext">Proximo &rarr;</button>
  </div>
</nav>

<div class="toast" id="toast"></div>

<div class="overlay" id="overlay">
  <div class="sheet">
    <button class="sheet-close" id="sheetClose">fechar &#10005;</button>
    <h2>Labels verificados</h2>
    <p>Toque em <strong>copiar</strong> e cole numa mensagem para o Claude.</p>
    <textarea id="sheetText" readonly></textarea>
    <div class="sheet-actions">
      <button id="sheetCopy" class="primary">Copiar JSON</button>
      <button id="sheetDownload">Tentar baixar arquivo</button>
    </div>
  </div>
</div>

<script id="casos-data" type="application/json">__DADOS__</script>
<script>
(function () {
  "use strict";
  var CASOS = JSON.parse(document.getElementById("casos-data").textContent);
  var STORAGE_KEY = "payflow_verificacao_labels_v1";
  var RUBRICAS = [
    { id: "groundedness", nome: "Groundedness", elim: true,
      q: "Todo numero citado nos fatos existe mesmo nos dados brutos da ferramenta?" },
    { id: "task_completion", nome: "Task Completion", elim: false,
      q: "A recomendacao e defensavel pelos fatos listados? Se nao, qual fato ela ignorou?" },
    { id: "trajectory", nome: "Trajectory", elim: false,
      q: "O agente consultou as ferramentas que precisava antes de concluir?" },
    { id: "cegueira_score", nome: "Cegueira ao score", elim: false,
      q: "O memo cita score/probabilidade/modelo? (deveria ser cego a isso)" }
  ];
  var CATEGORIAS = ["", "recomendacao_ignora_fato", "numero_nao_existe", "fato_sem_fonte",
                    "deferir_por_dado_inobtenivel", "cita_score", "outro"];

  var idx = 0;
  var labels = carregar();

  function carregar() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return {};
  }
  function salvar() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(labels)); } catch (e) {}
  }
  function registro(skId) {
    var k = String(skId);
    if (!labels[k]) {
      labels[k] = { sk_id_curr: skId, groundedness: null, task_completion: null,
                    trajectory: null, cegueira_score: null, nota_geral: "" };
    }
    return labels[k];
  }
  function completo(skId) {
    var lbl = labels[String(skId)];
    if (!lbl) return false;
    return RUBRICAS.every(function (r) { return lbl[r.id] && lbl[r.id].veredito; });
  }
  function toast(msg) {
    var el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(function () { el.classList.remove("show"); }, 1600);
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function bloco(titulo, conteudoHtml, aberto) {
    var open = aberto ? " open" : "";
    return '<section class="block">' +
      '<div class="block-h' + open + '" data-toggle="1"><h2>' + titulo + '</h2>' +
      '<span class="chev">&#9656;</span></div>' +
      '<div class="block-body' + open + '">' + conteudoHtml + "</div></section>";
  }

  function htmlMemo(caso) {
    var m = caso.memo;
    var simbolo = { favoravel: "+", desfavoravel: "−", neutro: "·" };
    var fatos = m.fatores_cliente.map(function (f) {
      return '<div class="fato peso-' + esc(f.peso) + '">' +
        '<span class="peso-mark">' + simbolo[f.peso] + "</span>" +
        "<span>" + esc(f.fato) +
        '<span class="fato-src">fonte: ' + esc(f.fonte_tool) + "</span></span></div>";
    }).join("");
    var faltante = "";
    if (m.informacao_faltante && m.informacao_faltante.length) {
      faltante = '<div class="faltante"><div class="faltante-title">Informacao faltante declarada</div>' +
        m.informacao_faltante.map(function (i) { return "&bull; " + esc(i); }).join("<br>") + "</div>";
    }
    var cen = '<div class="faltante"><div class="faltante-title">Cenario assumido</div>' +
      "Perda em caso de calote: " + Math.round(m.cenario_assumido.lgd * 100) + "% " +
      '<span class="fato-src">' + esc(m.cenario_assumido.fonte) + "</span></div>";
    return fatos + cen + faltante;
  }

  function htmlTrace(caso) {
    return caso.trace.map(function (c) {
      var linhas = Object.keys(c.retorno).map(function (k) {
        return "<b>" + esc(k) + "</b><span>" + esc(JSON.stringify(c.retorno[k])) + "</span>";
      }).join("");
      return '<div class="tool"><div class="tool-name">' + esc(c.ferramenta) + "</div>" +
        '<div class="kv">' + linhas + "</div></div>";
    }).join("");
  }

  function htmlAnterior(caso) {
    var a = caso.label_anterior;
    if (!a) return "";
    var linhas = RUBRICAS.map(function (r) {
      var v = a[r.id] || {};
      var val = v.veredito == null ? "sem veredito" : v.veredito;
      var cls = v.veredito == null ? "v-null" : "v-" + v.veredito;
      var ev = v.evidencia ? ' <span class="rub-ev">&mdash; ' + esc(v.evidencia) + "</span>" : "";
      return '<div class="linha-rubrica"><span class="rub-nome">' + r.nome + "</span>" +
        '<span><span class="rub-v ' + cls + '">' + val + "</span>" + ev + "</span></div>";
    }).join("");
    return linhas;
  }

  function htmlRubricas(caso) {
    var reg = registro(caso.sk_id_curr);
    return RUBRICAS.map(function (r) {
      var atual = reg[r.id] || {};
      var v = atual.veredito;
      var opts = CATEGORIAS.map(function (c) {
        var sel = atual.categoria_falha === c ? " selected" : "";
        return '<option value="' + c + '"' + sel + ">" + (c || "(sem categoria)") + "</option>";
      }).join("");
      return '<div class="rubrica" data-rub="' + r.id + '">' +
        '<div class="rubrica-h"><h3>' + r.nome + "</h3>" +
        (r.elim ? '<span class="elim-tag">eliminatoria</span>' : "") + "</div>" +
        '<div class="rubrica-q">' + r.q + "</div>" +
        '<div class="toggle">' +
        '<button data-set="OK" class="' + (v === "OK" ? "sel-ok" : "") + '">OK</button>' +
        '<button data-set="FALHA" class="' + (v === "FALHA" ? "sel-falha" : "") + '">FALHA</button>' +
        "</div>" +
        '<label class="field-label">Evidencia (nomeie o fato e o numero)</label>' +
        "<textarea data-ev>" + esc(atual.evidencia || "") + "</textarea>" +
        '<label class="field-label">Categoria da falha</label>' +
        "<select data-cat>" + opts + "</select>" +
        "</div>";
    }).join("");
  }

  function render() {
    var caso = CASOS[idx];
    var reg = registro(caso.sk_id_curr);
    var novo = !caso.label_anterior;
    var atencao = caso.label_anterior &&
      caso.label_anterior.task_completion &&
      caso.label_anterior.task_completion.veredito === "FALHA";

    var badges = '<span class="badge rec-' + esc(caso.memo.recomendacao) + '">' +
      esc(caso.memo.recomendacao) + "</span>";
    if (novo) badges += '<span class="badge novo">novo</span>';
    if (atencao) badges += '<span class="badge atencao">era FALHA</span>';
    if (caso.violacoes_trajetoria && caso.violacoes_trajetoria.length) {
      badges += '<span class="badge violacao">violacao trajetoria</span>';
    }

    var html =
      '<div class="case-head"><div class="case-id"><span>cliente</span>' +
      caso.sk_id_curr + "</div>" +
      '<div class="badges">' + badges + "</div></div>";

    html += bloco("Memo de hoje &mdash; recomenda " + esc(caso.memo.recomendacao),
                  htmlMemo(caso), true);
    html += bloco("Dados brutos das ferramentas (" + caso.trace.length + ")",
                  htmlTrace(caso), false);

    if (caso.label_anterior) {
      html += '<section class="block anterior">' +
        '<div class="block-h open" data-toggle="1"><h2>Seu label anterior (memo de ontem)</h2>' +
        '<span class="chev">&#9656;</span></div>' +
        '<div class="block-body open">' + htmlAnterior(caso) + "</div></section>";
      html += '<button class="btn-confirmar' + (completo(caso.sk_id_curr) ? " feito" : "") +
        '" id="btnConfirmar">' +
        (completo(caso.sk_id_curr) ? "✓ verificado" : "Confirmar label anterior") +
        "</button>";
    }

    html += '<section class="block"><div class="block-body open" style="display:block">' +
      htmlRubricas(caso) +
      '<label class="field-label">Nota geral (opcional)</label>' +
      '<textarea id="notaGeral">' + esc(reg.nota_geral || "") + "</textarea>" +
      "</div></section>";

    var main = document.getElementById("main");
    main.innerHTML = html;

    document.getElementById("count").textContent = (idx + 1) + " / " + CASOS.length;
    var feitos = CASOS.filter(function (c) { return completo(c.sk_id_curr); }).length;
    document.getElementById("progressBar").style.width =
      (feitos / CASOS.length * 100).toFixed(1) + "%";
    document.getElementById("btnPrev").disabled = idx === 0;

    ligarEventos(caso);
    renderJump();
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function ligarEventos(caso) {
    var reg = registro(caso.sk_id_curr);

    Array.prototype.forEach.call(document.querySelectorAll('[data-toggle]'), function (h) {
      h.addEventListener("click", function () {
        h.classList.toggle("open");
        h.nextElementSibling.classList.toggle("open");
      });
    });

    Array.prototype.forEach.call(document.querySelectorAll(".rubrica"), function (bloco) {
      var rid = bloco.getAttribute("data-rub");
      var ev = bloco.querySelector("[data-ev]");
      var cat = bloco.querySelector("[data-cat]");

      function grava(veredito) {
        reg[rid] = {
          veredito: veredito,
          evidencia: ev.value.trim(),
          categoria_falha: cat.value
        };
        salvar();
      }

      Array.prototype.forEach.call(bloco.querySelectorAll("[data-set]"), function (btn) {
        btn.addEventListener("click", function () {
          var v = btn.getAttribute("data-set");
          bloco.querySelectorAll("[data-set]")[0].className = v === "OK" ? "sel-ok" : "";
          bloco.querySelectorAll("[data-set]")[1].className = v === "FALHA" ? "sel-falha" : "";
          grava(v);
          atualizarConfirmar(caso);
        });
      });
      ev.addEventListener("input", function () {
        if (reg[rid] && reg[rid].veredito) grava(reg[rid].veredito);
      });
      cat.addEventListener("change", function () {
        if (reg[rid] && reg[rid].veredito) grava(reg[rid].veredito);
      });
    });

    var nota = document.getElementById("notaGeral");
    nota.addEventListener("input", function () { reg.nota_geral = nota.value; salvar(); });

    var btnC = document.getElementById("btnConfirmar");
    if (btnC) {
      btnC.addEventListener("click", function () {
        var a = caso.label_anterior;
        RUBRICAS.forEach(function (r) {
          var v = a[r.id] || {};
          reg[r.id] = {
            // veredito null no label antigo vira OK so se o humano confirmar
            // explicitamente depois - aqui copia o que existia, inclusive null
            veredito: v.veredito,
            evidencia: v.evidencia || "",
            categoria_falha: v.categoria_falha || ""
          };
        });
        reg.nota_geral = a.nota_geral || "";
        salvar();
        toast("label anterior copiado");
        render();
      });
    }
  }

  function atualizarConfirmar(caso) {
    var btn = document.getElementById("btnConfirmar");
    if (!btn) return;
    if (completo(caso.sk_id_curr)) {
      btn.className = "btn-confirmar feito";
      btn.textContent = "✓ verificado";
    }
  }

  function renderJump() {
    var jump = document.getElementById("jump");
    jump.innerHTML = CASOS.map(function (c, i) {
      var cls = [];
      if (completo(c.sk_id_curr)) cls.push("done");
      if (!c.label_anterior) cls.push("novo");
      if (i === idx) cls.push("current");
      return '<button class="' + cls.join(" ") + '" data-i="' + i + '">' + (i + 1) + "</button>";
    }).join("");
    Array.prototype.forEach.call(jump.querySelectorAll("button"), function (b) {
      b.addEventListener("click", function () {
        idx = parseInt(b.getAttribute("data-i"), 10);
        render();
      });
    });
  }

  function exportar() {
    var lista = CASOS.map(function (c) {
      return labels[String(c.sk_id_curr)] || {
        sk_id_curr: c.sk_id_curr, groundedness: null, task_completion: null,
        trajectory: null, cegueira_score: null, nota_geral: ""
      };
    });
    var out = {
      gerado_em: new Date().toISOString(),
      fonte_memos: "data/processed/piloto_camada2_memos.jsonl (2026-08-08)",
      n_total: CASOS.length,
      n_julgados: lista.filter(function (l) {
        return RUBRICAS.every(function (r) { return l[r.id] && l[r.id].veredito; });
      }).length,
      labels: lista
    };
    var texto = JSON.stringify(out, null, 2);
    document.getElementById("sheetText").value = texto;
    document.getElementById("overlay").classList.add("show");
  }

  document.getElementById("btnPrev").addEventListener("click", function () {
    if (idx > 0) { idx--; render(); }
  });
  document.getElementById("btnNext").addEventListener("click", function () {
    if (idx < CASOS.length - 1) { idx++; render(); }
    else toast("ultimo caso");
  });
  document.getElementById("btnExport").addEventListener("click", exportar);
  document.getElementById("sheetClose").addEventListener("click", function () {
    document.getElementById("overlay").classList.remove("show");
  });
  document.getElementById("sheetCopy").addEventListener("click", function () {
    var ta = document.getElementById("sheetText");
    ta.select();
    try {
      navigator.clipboard.writeText(ta.value);
      toast("copiado");
    } catch (e) {
      document.execCommand("copy");
      toast("copiado");
    }
  });
  document.getElementById("sheetDownload").addEventListener("click", function () {
    var blob = new Blob([document.getElementById("sheetText").value], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "verificacao_labels.json";
    a.click();
  });
  document.getElementById("jumpToggle").addEventListener("click", function () {
    var j = document.getElementById("jump");
    var aberto = j.style.display !== "none";
    j.style.display = aberto ? "none" : "flex";
    this.innerHTML = aberto ? "ver todos os casos &#9662;" : "esconder casos &#9652;";
  });

  var nNovos = CASOS.filter(function (c) { return !c.label_anterior; }).length;
  var nAtencao = CASOS.filter(function (c) {
    return c.label_anterior && c.label_anterior.task_completion &&
           c.label_anterior.task_completion.veredito === "FALHA";
  }).length;
  document.getElementById("aviso").innerHTML =
    "Os memos foram <b>regerados</b> em 2026-08-08 &mdash; nao sao os mesmos que voce rotulou. " +
    "<b>" + nNovos + "</b> casos novos (sem label, exigem rotulagem do zero) vem primeiro; " +
    "<b>" + nAtencao + "</b> marcados <em>era FALHA</em> merecem leitura atenta (a recomendacao " +
    "pode ter mudado). Os demais so precisam de confirmacao.";

  render();
})();
</script>
"""


def main() -> None:
    labels = {
        c["sk_id_curr"]: c
        for c in json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    }

    casos = []
    with MEMOS.open(encoding="utf-8") as fh:
        for linha in fh:
            reg = json.loads(linha)
            if not reg.get("memo"):
                continue
            sk = reg["sk_id_curr"]
            casos.append({
                "sk_id_curr": sk,
                "n_chamadas": reg.get("n_chamadas"),
                "violacoes_trajetoria": reg.get("violacoes_trajetoria", []),
                "trace": reg["trace"],
                "memo": reg["memo"],
                "label_anterior": labels.get(sk),  # None = caso novo
            })

    # Ordem de trabalho: novos primeiro (rotulagem do zero), depois os que
    # eram FALHA (leitura atenta), depois os confirmaveis.
    def prioridade(c):
        if c["label_anterior"] is None:
            return (0, c["sk_id_curr"])
        tc = c["label_anterior"].get("task_completion") or {}
        if tc.get("veredito") == "FALHA" or tc.get("veredito") is None:
            return (1, c["sk_id_curr"])
        return (2, c["sk_id_curr"])

    casos.sort(key=prioridade)

    n_novos = sum(1 for c in casos if c["label_anterior"] is None)
    n_atencao = sum(1 for c in casos if prioridade(c)[0] == 1)
    print(f"casos com memo valido: {len(casos)}")
    print(f"  novos (sem label):     {n_novos}")
    print(f"  atencao (era FALHA):   {n_atencao}")
    print(f"  so confirmar:          {len(casos) - n_novos - n_atencao}")

    html = TEMPLATE.replace("__DADOS__", json.dumps(casos, ensure_ascii=False))
    html = html.replace("__N_TOTAL__", str(len(casos)))
    SAIDA.write_text(html, encoding="utf-8")
    print(f"escrito: {SAIDA}")


if __name__ == "__main__":
    main()
