"""Relatório HTML da execução: um único arquivo, com os prints embutidos.

Por ser autocontido (CSS e imagens dentro do próprio HTML), pode ser enviado
por e-mail ou anexado a um chamado sem perder nada.
"""

from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path

from .records import RecordResult, Status


@dataclass(frozen=True)
class RunInfo:
    spreadsheet: str
    started_at: datetime
    finished_at: datetime

    @property
    def duration(self) -> str:
        seconds = int((self.finished_at - self.started_at).total_seconds())
        return f"{seconds // 60}min {seconds % 60:02d}s"


LABELS = {
    Status.SUCESSO: ("Sucesso", "Cadastrado no sistema"),
    Status.REJEITADO: ("Rejeitado", "O sistema recusou o registro"),
    Status.FALHA: ("Falha técnica", "Não concluído após as novas tentativas"),
    Status.NAO_PROCESSADO: ("Não processado", "Robô interrompido antes deste registro"),
}

CSS = """
:root {
  --bg: #f6f7f9; --card: #ffffff; --text: #1d2330; --muted: #5f6b7a; --line: #e3e7ec;
  --ok: #1a7f37; --ok-bg: #e6f4ea; --rej: #b42318; --rej-bg: #fdecea;
  --fail: #9a6700; --fail-bg: #fff4d6; --skip: #57606a; --skip-bg: #eef1f4;
  --accent: #000080;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151b; --card: #1b2029; --text: #e6e9ee; --muted: #9aa5b4; --line: #2b3240;
    --ok: #5cd47c; --ok-bg: #16301f; --rej: #ff8a80; --rej-bg: #3a1a1a;
    --fail: #f2c34b; --fail-bg: #352a10; --skip: #aab4c0; --skip-bg: #252b35;
    --accent: #8ea2ff;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 15px/1.5 "Segoe UI", system-ui, sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 48px; }
h1 { margin: 0 0 4px; font-size: 26px; }
.meta { color: var(--muted); margin: 0 0 24px; }
.meta b { color: var(--text); font-weight: 600; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
         gap: 12px; margin-bottom: 16px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
        padding: 14px 16px; border-left: 4px solid var(--c); }
.card .n { font-size: 30px; font-weight: 700; color: var(--c); font-variant-numeric: tabular-nums; }
.card .t { font-weight: 600; } .card .d { color: var(--muted); font-size: 13px; }
.bar { display: flex; height: 10px; border-radius: 5px; overflow: hidden;
       background: var(--line); margin-bottom: 28px; }
.bar span { background: var(--c); }
.c-ok { --c: var(--ok); --cb: var(--ok-bg); } .c-rej { --c: var(--rej); --cb: var(--rej-bg); }
.c-fail { --c: var(--fail); --cb: var(--fail-bg); } .c-skip { --c: var(--skip); --cb: var(--skip-bg); }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.filters button { font: inherit; padding: 6px 12px; border-radius: 999px; cursor: pointer;
                  border: 1px solid var(--line); background: var(--card); color: var(--text); }
.filters button[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); font-weight: 600; }
.table-wrap { overflow-x: auto; background: var(--card); border: 1px solid var(--line);
              border-radius: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
tr:last-child td { border-bottom: 0; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 13px;
         font-weight: 600; color: var(--c); background: var(--cb); white-space: nowrap; }
.msg { color: var(--muted); font-size: 14px; }
details summary { cursor: pointer; color: var(--accent); font-size: 14px; }
details img { display: block; max-width: 100%; margin-top: 8px; border: 1px solid var(--line);
              border-radius: 6px; }
footer { margin-top: 24px; color: var(--muted); font-size: 13px; }
@media (max-width: 640px) { .hide-sm { display: none; } }
"""

SCRIPT = """
document.querySelectorAll('.filters button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filters button').forEach(b => b.setAttribute('aria-pressed', b === btn));
    const f = btn.dataset.filter;
    document.querySelectorAll('tbody tr').forEach(tr => {
      tr.hidden = f !== 'todos' && tr.dataset.status !== f;
    });
  });
});
"""

CLASSES = {Status.SUCESSO: "c-ok", Status.REJEITADO: "c-rej",
           Status.FALHA: "c-fail", Status.NAO_PROCESSADO: "c-skip"}


def _embed_image(path: Path | None) -> str:
    if not path or not Path(path).exists():
        return ""
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return (f'<details><summary>ver print</summary>'
            f'<img src="data:image/png;base64,{data}" alt="Print da tela no momento do erro" '
            f'loading="lazy"></details>')


def render_html(results: list[RecordResult], info: RunInfo) -> str:
    counts = Counter(r.status for r in results)
    total = len(results) or 1

    cards = "".join(
        f'<div class="card {CLASSES[s]}"><div class="n">{counts[s]}</div>'
        f'<div class="t">{LABELS[s][0]}</div><div class="d">{LABELS[s][1]}</div></div>'
        for s in Status)
    bar = "".join(f'<span class="{CLASSES[s]}" style="width:{counts[s] / total * 100:.2f}%" '
                  f'title="{LABELS[s][0]}: {counts[s]}"></span>' for s in Status if counts[s])
    filters = '<button data-filter="todos" aria-pressed="true">Todos</button>' + "".join(
        f'<button data-filter="{s.value}" aria-pressed="false">{LABELS[s][0]} ({counts[s]})</button>'
        for s in Status if counts[s])

    rows = []
    for r in results:
        rec = r.record
        rows.append(
            f'<tr data-status="{r.status.value}">'
            f'<td class="num">{rec.row}</td>'
            f'<td>{escape(rec.nome)}</td>'
            f'<td class="num hide-sm">{escape(rec.cpf)}</td>'
            f'<td><span class="badge {CLASSES[r.status]}">{LABELS[r.status][0]}</span></td>'
            f'<td class="num hide-sm">{r.attempts}</td>'
            f'<td class="num hide-sm">{r.duration:.1f}s</td>'
            f'<td><div class="msg">{escape(r.message)}</div>{_embed_image(r.screenshot)}</td>'
            f'</tr>')

    rate = counts[Status.SUCESSO] / total * 100
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório do robô · {info.started_at:%d/%m/%Y %H:%M}</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <h1>Relatório de execução do robô</h1>
  <p class="meta">
    Planilha <b>{escape(info.spreadsheet)}</b> ·
    início <b>{info.started_at:%d/%m/%Y %H:%M:%S}</b> ·
    duração <b>{info.duration}</b> ·
    <b>{len(results)}</b> registros · taxa de sucesso <b>{rate:.0f}%</b>
  </p>
  <section class="cards">{cards}</section>
  <div class="bar" role="img" aria-label="Distribuição dos resultados">{bar}</div>
  <div class="filters" role="toolbar" aria-label="Filtrar por status">{filters}</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Linha</th><th>Nome</th><th class="hide-sm">CPF</th><th>Status</th>
      <th class="hide-sm">Tentativas</th><th class="hide-sm">Tempo</th><th>Detalhes</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
  <footer>Gerado automaticamente pelo autopy em {info.finished_at:%d/%m/%Y %H:%M:%S}.</footer>
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""


def save_html_report(results: list[RecordResult], info: RunInfo, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(results, info), encoding="utf-8")
    return path
