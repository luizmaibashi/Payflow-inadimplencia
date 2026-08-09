"""Gera a tela de verificacao de TASK COMPLETION contra os memos versionados.

UMA rubrica so, de proposito. O juiz de app/juiz_camada2.py avalia Task
Completion e mais nada; calibra-lo (debito #10) exige ground truth dessa
rubrica e de nenhuma outra. As outras tres do ADR-0004 nao precisam de
humano nesta passada:

  - groundedness: mecanica (validar_groundedness). Memo com fonte_tool
    orfa nem chega a existir - o agente devolve erro e memo=None. Todo
    memo neste arquivo ja passou.
  - trajectory:   mecanica (validar_trajetoria). O resultado por caso esta
    em `violacoes_trajetoria` no proprio registro.
  - cegueira ao score: garantida por construcao (MemoCredito tem
    extra="forbid" e nenhum campo de score) e guardada por teste.

Isso derruba o trabalho humano de 4 rubricas x 86 casos para 86 decisoes
binarias. Motivo de existir: a rodada de 2026-08-08 regerou os memos e o par
label<->memo se desfez (debito #30) - os labels de ontem descrevem memos que
nao existem mais.

Uso: python scripts/_gerar_revisor_verificacao.py
Saida: scripts/_revisor_verificacao.html (temporario, nao versionar)
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LABELS = RAIZ / "data" / "labels" / "task_completion_labels.json"
MEMOS = RAIZ / "data" / "processed" / "piloto_camada2_memos.jsonl"
SAIDA = RAIZ / "scripts" / "_revisor_verificacao.html"


TEMPLATE = r"""<title>Task Completion - verificacao payflow</title>
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
    background: var(--bg); color: var(--ink);
    font-family: var(--font-body); font-size: 15px; line-height: 1.5;
    -webkit-tap-highlight-color: transparent;
  }
  .wrap { max-width: 720px; margin: 0 auto; padding: 0 0 150px; }

  header.top {
    position: sticky; top: 0; z-index: 20;
    background: var(--bg); border-bottom: 1px solid var(--line);
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

  main { padding: 16px 16px 0; }

  .pergunta {
    background: var(--accent-soft); color: var(--accent-ink);
    padding: 12px 14px; border-radius: 10px; font-size: 14px;
    margin-bottom: 14px;
  }
  .pergunta b { font-weight: 700; }

  .case-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .case-id { font-family: var(--font-display); font-size: 24px; font-variant-numeric: tabular-nums; }
  .case-id span { color: var(--ink-soft); font-size: 13px; font-family: var(--font-body); display: block; }
  .badges { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
  .badge {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 3px 8px; border-radius: 20px; font-weight: 600; white-space: nowrap;
  }
  .badge.novo { background: var(--accent-soft); color: var(--accent-ink); }
  .badge.atencao { background: var(--elim-soft); color: var(--elim); }
  .badge.violacao { background: var(--elim-soft); color: var(--elim); }

  .rec {
    display: flex; align-items: baseline; gap: 10px;
    padding: 12px 14px; border-radius: 10px; margin-bottom: 12px;
    font-family: var(--font-display); font-size: 22px; font-weight: 600;
  }
  .rec small {
    font-family: var(--font-body); font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .06em; opacity: .75;
  }
  .rec.r-APROVAR { background: var(--ok-soft); color: var(--ok); }
  .rec.r-NEGAR { background: var(--falha-soft); color: var(--falha); }
  .rec.r-DEFERIR { background: var(--elim-soft); color: var(--elim); }

  section.block {
    background: var(--bg-card); border: 1px solid var(--line);
    border-radius: 10px; margin-bottom: 12px; overflow: hidden;
  }
  .block-h { padding: 9px 14px; border-bottom: 1px solid var(--line); }
  .block-h h2 {
    margin: 0; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--ink-soft); font-weight: 600;
  }
  .block-body { padding: 10px 14px 14px; }

  .fato { display: flex; gap: 8px; padding: 7px 0; border-top: 1px solid var(--line); font-size: 13.5px; }
  .fato:first-child { border-top: none; padding-top: 0; }
  .peso-mark { flex: none; width: 16px; text-align: center; font-weight: 700; font-family: var(--font-mono); }
  .peso-favoravel .peso-mark { color: var(--ok); }
  .peso-desfavoravel .peso-mark { color: var(--falha); }
  .peso-neutro .peso-mark { color: var(--ink-soft); }
  .fato-src { display: block; font-family: var(--font-mono); font-size: 11px; color: var(--ink-soft); margin-top: 2px; }

  .tool { margin-bottom: 10px; }
  .tool:last-child { margin-bottom: 0; }
  .tool-name {
    font-family: var(--font-mono); font-size: 12px; color: var(--accent-ink);
    background: var(--accent-soft); display: inline-block; padding: 2px 7px;
    border-radius: 5px; margin-bottom: 5px;
  }
  .kv {
    font-family: var(--font-mono); font-size: 12.5px;
    background: var(--bg-raised); border-radius: 7px; padding: 8px 10px;
    display: grid; grid-template-columns: auto 1fr; gap: 2px 10px;
    font-variant-numeric: tabular-nums; overflow-x: auto;
  }
  .kv b { color: var(--ink-soft); font-weight: 400; }

  .faltante { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line); font-size: 13px; }
  .faltante-title { color: var(--ink-soft); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 4px; }

  .anterior-nota {
    font-size: 12.5px; color: var(--ink-soft); font-style: italic;
    padding: 8px 12px; border-left: 3px solid var(--line);
    background: var(--bg-raised); border-radius: 0 8px 8px 0; margin-bottom: 12px;
  }
  .anterior-nota b { font-style: normal; color: var(--ink); }

  .decisao { display: flex; gap: 10px; margin-bottom: 10px; }
  .decisao button {
    flex: 1; padding: 16px 0; border-radius: 10px; border: 2px solid var(--line);
    background: var(--bg-card); color: var(--ink-soft);
    font-size: 15px; font-weight: 700; cursor: pointer; font-family: inherit;
  }
  .decisao button.sel-ok { background: var(--ok-soft); color: var(--ok); border-color: var(--ok); }
  .decisao button.sel-falha { background: var(--falha-soft); color: var(--falha); border-color: var(--falha); }

  .campos-falha { display: none; }
  .campos-falha.show { display: block; }
  label.field-label {
    display: block; font-size: 11px; text-transform: uppercase;
    letter-spacing: .05em; color: var(--ink-soft); margin: 8px 0 4px;
  }
  textarea, select {
    width: 100%; border: 1px solid var(--line); border-radius: 8px;
    background: var(--bg-raised); color: var(--ink);
    font-family: var(--font-body); font-size: 13.5px; padding: 8px 10px;
  }
  textarea { resize: vertical; min-height: 60px; }

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
  .jump button.falha { background: var(--falha-soft); color: var(--falha); border-color: var(--falha); }
  .jump button.current { outline: 2px solid var(--accent); outline-offset: 1px; }
  .jump-toggle { padding: 8px 16px 0; font-size: 12px; color: var(--accent); cursor: pointer; user-select: none; }

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
  .sheet textarea { flex: 1; min-height: 200px; font-family: var(--font-mono); font-size: 11.5px; white-space: pre; overflow: auto; }
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
      <div class="brand">Task Completion<small>payflow &middot; memos de 2026-08-08</small></div>
      <div class="count" id="count">1 / __N_TOTAL__</div>
    </div>
    <div class="progress"><i id="progressBar" style="width:0%"></i></div>
  </header>

  <div class="jump-toggle" id="jumpToggle">ver todos os casos &#9662;</div>
  <div class="jump" id="jump" style="display:none"></div>

  <main id="main"></main>
</div>

<nav class="bottom">
  <div class="nav-row">
    <button class="btn-prev" id="btnPrev">&larr;</button>
    <button class="btn-export" id="btnExport" title="Exportar JSON">&#8681;</button>
    <button class="btn-next primary" id="btnNext">Proximo &rarr;</button>
  </div>
</nav>

<div class="toast" id="toast"></div>

<div class="overlay" id="overlay">
  <div class="sheet">
    <button class="sheet-close" id="sheetClose">fechar &#10005;</button>
    <h2>Labels de Task Completion</h2>
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
  var STORAGE_KEY = "payflow_task_completion_v2";
  var CATEGORIAS = ["recomendacao_ignora_fato", "deferir_por_dado_inobtenivel",
                    "recomendacao_sem_base", "outro"];

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
  function reg(skId) {
    var k = String(skId);
    if (!labels[k]) labels[k] = { veredito: null, evidencia: "", categoria_falha: "" };
    return labels[k];
  }
  function feito(skId) {
    var l = labels[String(skId)];
    return !!(l && l.veredito);
  }
  function toast(msg) {
    var el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(function () { el.classList.remove("show"); }, 1500);
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render() {
    var caso = CASOS[idx];
    var r = reg(caso.sk_id_curr);
    var m = caso.memo;
    var simbolo = { favoravel: "+", desfavoravel: "−", neutro: "·" };

    var badges = "";
    if (!caso.label_anterior) badges += '<span class="badge novo">caso novo</span>';
    if (caso.era_falha) badges += '<span class="badge atencao">era FALHA</span>';
    if (caso.grupo === 2) badges += '<span class="badge atencao">OK suspeito</span>';
    if (caso.violacoes_trajetoria.length) badges += '<span class="badge violacao">violacao trajetoria</span>';

    var fatos = m.fatores_cliente.map(function (f) {
      return '<div class="fato peso-' + esc(f.peso) + '">' +
        '<span class="peso-mark">' + simbolo[f.peso] + "</span>" +
        "<span>" + esc(f.fato) +
        '<span class="fato-src">' + esc(f.fonte_tool) + "</span></span></div>";
    }).join("");

    var faltante = "";
    if (m.informacao_faltante && m.informacao_faltante.length) {
      faltante = '<div class="faltante"><div class="faltante-title">Diz que faltou apurar</div>' +
        m.informacao_faltante.map(function (i) { return "&bull; " + esc(i); }).join("<br>") + "</div>";
    }

    var trace = caso.trace.map(function (c) {
      var linhas = Object.keys(c.retorno).map(function (k) {
        return "<b>" + esc(k) + "</b><span>" + esc(JSON.stringify(c.retorno[k])) + "</span>";
      }).join("");
      return '<div class="tool"><div class="tool-name">' + esc(c.ferramenta) + "</div>" +
        '<div class="kv">' + linhas + "</div></div>";
    }).join("");

    var anterior = "";
    if (caso.label_anterior) {
      var a = caso.label_anterior;
      anterior = '<div class="anterior-nota">Ontem voce disse <b>' +
        (a.veredito || "sem veredito") + "</b>" +
        (a.evidencia ? ": &ldquo;" + esc(a.evidencia) + "&rdquo;" : "") +
        " &mdash; mas sobre um memo diferente, regerado desde entao.</div>";
    }

    var opts = CATEGORIAS.map(function (c) {
      return '<option value="' + c + '"' + (r.categoria_falha === c ? " selected" : "") + ">" + c + "</option>";
    }).join("");

    document.getElementById("main").innerHTML =
      '<div class="pergunta">A recomendacao abaixo e <b>defensavel</b> pelos fatos que o proprio agente levantou?' +
      '<br><span style="font-size:12px;opacity:.8">por que este caso caiu aqui: ' + esc(caso.motivo) + "</span></div>" +
      '<div class="case-head"><div class="case-id"><span>cliente</span>' + caso.sk_id_curr +
      '</div><div class="badges">' + badges + "</div></div>" +
      '<div class="rec r-' + esc(m.recomendacao) + '"><small>recomenda</small>' + esc(m.recomendacao) + "</div>" +
      anterior +
      '<section class="block"><div class="block-h"><h2>Fatos que o agente citou</h2></div>' +
      '<div class="block-body">' + fatos + faltante + "</div></section>" +
      '<section class="block"><div class="block-h"><h2>Dados brutos das ferramentas</h2></div>' +
      '<div class="block-body">' + trace + "</div></section>" +
      '<div class="decisao">' +
      '<button data-set="OK" class="' + (r.veredito === "OK" ? "sel-ok" : "") + '">Defensavel</button>' +
      '<button data-set="FALHA" class="' + (r.veredito === "FALHA" ? "sel-falha" : "") + '">FALHA</button>' +
      "</div>" +
      '<div class="campos-falha' + (r.veredito === "FALHA" ? " show" : "") + '" id="camposFalha">' +
      '<label class="field-label">Qual fato a recomendacao ignorou? (cite o numero)</label>' +
      "<textarea id=\"ev\">" + esc(r.evidencia) + "</textarea>" +
      '<label class="field-label">Categoria</label>' +
      '<select id="cat">' + opts + "</select></div>";

    document.getElementById("count").textContent = (idx + 1) + " / " + CASOS.length;
    var n = CASOS.filter(function (c) { return feito(c.sk_id_curr); }).length;
    document.getElementById("progressBar").style.width = (n / CASOS.length * 100).toFixed(1) + "%";
    document.getElementById("btnPrev").disabled = idx === 0;

    ligar(caso);
    renderJump();
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function ligar(caso) {
    var r = reg(caso.sk_id_curr);
    var ev = document.getElementById("ev");
    var cat = document.getElementById("cat");
    var campos = document.getElementById("camposFalha");
    var botoes = document.querySelectorAll("[data-set]");

    Array.prototype.forEach.call(botoes, function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-set");
        r.veredito = v;
        botoes[0].className = v === "OK" ? "sel-ok" : "";
        botoes[1].className = v === "FALHA" ? "sel-falha" : "";
        if (v === "FALHA") {
          campos.classList.add("show");
          if (!r.categoria_falha) { r.categoria_falha = cat.value; }
        } else {
          campos.classList.remove("show");
          r.evidencia = "";
          r.categoria_falha = "";
          ev.value = "";
        }
        salvar();
        renderJump();
        document.getElementById("progressBar").style.width =
          (CASOS.filter(function (c) { return feito(c.sk_id_curr); }).length / CASOS.length * 100).toFixed(1) + "%";
        // OK segue sozinho para o proximo: e o caminho de 67 dos 86 casos.
        if (v === "OK" && idx < CASOS.length - 1) { idx++; render(); }
      });
    });

    ev.addEventListener("input", function () { r.evidencia = ev.value; salvar(); });
    cat.addEventListener("change", function () { r.categoria_falha = cat.value; salvar(); });
  }

  function renderJump() {
    var jump = document.getElementById("jump");
    if (jump.style.display === "none") return;
    jump.innerHTML = CASOS.map(function (c, i) {
      var l = labels[String(c.sk_id_curr)];
      var cls = [];
      if (l && l.veredito === "OK") cls.push("done");
      if (l && l.veredito === "FALHA") cls.push("falha");
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
      var l = labels[String(c.sk_id_curr)] || { veredito: null, evidencia: "", categoria_falha: "" };
      return {
        sk_id_curr: c.sk_id_curr,
        task_completion: {
          veredito: l.veredito,
          evidencia: l.evidencia || "",
          categoria_falha: l.categoria_falha || ""
        },
        // Mecanicas: NAO julgadas por humano nesta passada. Vem dos
        // validadores que ja rodaram no pipeline.
        groundedness: { veredito: "OK", evidencia: "mecanico: validar_groundedness", categoria_falha: "" },
        trajectory: {
          veredito: c.violacoes_trajetoria.length ? "FALHA" : "OK",
          evidencia: c.violacoes_trajetoria.join("; ") || "mecanico: validar_trajetoria",
          categoria_falha: c.violacoes_trajetoria.length ? "trajetoria_incompleta" : ""
        },
        cegueira_score: { veredito: "OK", evidencia: "mecanico: schema MemoCredito extra=forbid", categoria_falha: "" },
        nota_geral: ""
      };
    });
    var out = {
      gerado_em: new Date().toISOString(),
      fonte_memos: "data/processed/piloto_camada2_memos.jsonl (2026-08-08, versionado)",
      rubrica_humana: "task_completion",
      // PARCIAL de proposito: so os casos que exigiam humano. Os demais
      // reaproveitam o label de 2026-08-07 e sao mesclados no lado do Claude.
      escopo: "revisao_parcial",
      n_total: CASOS.length,
      n_julgados: lista.filter(function (l) { return l.task_completion.veredito; }).length,
      labels: lista
    };
    document.getElementById("sheetText").value = JSON.stringify(out, null, 2);
    document.getElementById("overlay").classList.add("show");
  }

  document.getElementById("btnPrev").addEventListener("click", function () {
    if (idx > 0) { idx--; render(); }
  });
  document.getElementById("btnNext").addEventListener("click", function () {
    if (idx < CASOS.length - 1) { idx++; render(); } else toast("ultimo caso");
  });
  document.getElementById("btnExport").addEventListener("click", exportar);
  document.getElementById("sheetClose").addEventListener("click", function () {
    document.getElementById("overlay").classList.remove("show");
  });
  document.getElementById("sheetCopy").addEventListener("click", function () {
    var ta = document.getElementById("sheetText");
    ta.select();
    try { navigator.clipboard.writeText(ta.value); toast("copiado"); }
    catch (e) { document.execCommand("copy"); toast("copiado"); }
  });
  document.getElementById("sheetDownload").addEventListener("click", function () {
    var blob = new Blob([document.getElementById("sheetText").value], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "task_completion_labels.json";
    a.click();
  });
  document.getElementById("jumpToggle").addEventListener("click", function () {
    var j = document.getElementById("jump");
    var aberto = j.style.display !== "none";
    j.style.display = aberto ? "none" : "flex";
    this.innerHTML = aberto ? "ver todos os casos &#9662;" : "esconder casos &#9652;";
    if (!aberto) renderJump();
  });

  render();
})();
</script>
"""


def main() -> None:
    labels = {
        c["sk_id_curr"]: c
        for c in json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    }

    def contradiz_pesos(memo: dict) -> str | None:
        """Assinatura da falha que o revisor humano achou por conta propria em
        2026-08-07: recomendar NEGAR com fatos majoritariamente favoraveis (ou
        o espelho). Proxy MECANICO, nao veredito - serve so para escolher o
        que vale a pena reler."""
        fav = sum(1 for f in memo["fatores_cliente"] if f["peso"] == "favoravel")
        des = sum(1 for f in memo["fatores_cliente"] if f["peso"] == "desfavoravel")
        if memo["recomendacao"] == "NEGAR" and fav > des:
            return "NEGAR com maioria de fatos favoraveis"
        if memo["recomendacao"] == "APROVAR" and des > fav:
            return "APROVAR com maioria de fatos desfavoraveis"
        return None

    casos = []
    n_mantidos = 0
    with MEMOS.open(encoding="utf-8") as fh:
        for linha in fh:
            reg = json.loads(linha)
            if not reg.get("memo"):
                continue
            sk = reg["sk_id_curr"]
            anterior = labels.get(sk)
            tc = (anterior or {}).get("task_completion") or {}
            veredito_anterior = tc.get("veredito")
            suspeita = contradiz_pesos(reg["memo"])

            # QUEM PRECISA DE HUMANO (os demais reaproveitam o label de ontem):
            #  0. caso novo - nunca teve label
            #  1. era FALHA ou ficou sem veredito - etiqueta fragil: se o agente
            #     passou a recomendar o que o humano disse ser correto, o label
            #     virou factualmente errado (medido: 100525 e 353468)
            #  2. era OK mas o memo de hoje contradiz o peso dos proprios fatos
            if anterior is None:
                grupo, motivo = 0, "caso novo, sem label anterior"
            elif veredito_anterior in ("FALHA", None):
                grupo, motivo = 1, "label anterior fragil (era FALHA ou sem veredito)"
            elif suspeita:
                grupo, motivo = 2, f"label OK, mas hoje: {suspeita}"
            else:
                n_mantidos += 1
                continue

            casos.append({
                "sk_id_curr": sk,
                "violacoes_trajetoria": reg.get("violacoes_trajetoria", []),
                "trace": reg["trace"],
                "memo": reg["memo"],
                "label_anterior": {
                    "veredito": veredito_anterior,
                    "evidencia": tc.get("evidencia", ""),
                } if anterior else None,
                "era_falha": veredito_anterior == "FALHA",
                "grupo": grupo,
                "motivo": motivo,
            })

    casos.sort(key=lambda c: (c["grupo"], c["sk_id_curr"]))

    for g, nome in enumerate(["novos", "label fragil (era FALHA)", "OK suspeito"]):
        n = sum(1 for c in casos if c["grupo"] == g)
        print(f"  {nome:<28} {n}")
    print(f"  {'reaproveitados sem revisao':<28} {n_mantidos}")
    print(f"  {'TOTAL a revisar':<28} {len(casos)}")

    html = TEMPLATE.replace("__DADOS__", json.dumps(casos, ensure_ascii=False))
    html = html.replace("__N_TOTAL__", str(len(casos)))
    SAIDA.write_text(html, encoding="utf-8")
    print(f"escrito: {SAIDA}")


if __name__ == "__main__":
    main()
