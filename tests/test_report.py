from datetime import datetime, timedelta

from PIL import Image

from src.core.recorder import Frame, draw_cursor, merge_identical
from src.records import Record, RecordResult, Status
from src.report import RunInfo, render_html, save_html_report

START = datetime(2026, 11, 16, 22, 0, 0)
INFO = RunInfo("exemplo.xlsx", START, START + timedelta(minutes=2, seconds=5))


def rec(row: int, nome: str = "Ana") -> Record:
    return Record(row, nome, "529.982.247-25", "01/01/2015", "3A", "Bia", "11999999999")


def test_report_summary_and_rows(tmp_path):
    shot = tmp_path / "erro.png"
    Image.new("RGB", (10, 10), "red").save(shot)
    results = [
        RecordResult(rec(2), Status.SUCESSO, attempts=1, duration=5.2),
        RecordResult(rec(3, "Marcos"), Status.REJEITADO, attempts=1, duration=4.9,
                     message="O sistema recusou", screenshot=shot),
        RecordResult(rec(4, "Caio"), Status.NAO_PROCESSADO, message="robô interrompido"),
    ]
    html = render_html(results, INFO)
    assert "2min 05s" in html
    assert "taxa de sucesso <b>33%</b>" in html
    assert html.count('<tr data-status=') == 3
    assert "data:image/png;base64," in html          # print embutido
    assert 'data-filter="falha"' not in html          # sem filtro para status ausente


def test_report_escapes_spreadsheet_content():
    """Um nome malicioso na planilha não pode virar código no relatório."""
    results = [RecordResult(rec(2, "<script>alert(1)</script>"), Status.SUCESSO)]
    html = render_html(results, INFO)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_report_with_no_results(tmp_path):
    path = save_html_report([], INFO, tmp_path / "r" / "relatorio.html")
    assert path.exists() and "0</div>" in path.read_text(encoding="utf-8")


def test_merge_identical_frames_sums_durations():
    a = Image.new("P", (4, 4), 0)
    b = Image.new("P", (4, 4), 1)
    frames = [Frame(a, 100), Frame(a.copy(), 100), Frame(b, 100), Frame(a, 100)]
    merged = merge_identical(frames)
    assert [f.duration_ms for f in merged] == [200, 100, 100]


def test_draw_cursor_ignores_points_outside_the_window():
    img = Image.new("RGB", (20, 20), "white")
    draw_cursor(img, 50, 50)
    assert img.getcolors() == [(400, (255, 255, 255))]
    draw_cursor(img, 2, 2)
    assert len(img.getcolors()) > 1
