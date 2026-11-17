from datetime import datetime

import pytest
from openpyxl import Workbook

from src.core.config import PROJECT_ROOT
from src.records import FIELDS, SpreadsheetError, read_records, to_text


@pytest.mark.parametrize("value, expected", [
    (None, ""),
    ("  Ana  ", "Ana"),
    (datetime(2015, 1, 1), "01/01/2015"),   # Excel converteu a data
    (11987654321.0, "11987654321"),         # Excel converteu o telefone
    (42, "42"),
])
def test_to_text(value, expected):
    assert to_text(value) == expected


def test_reads_example_spreadsheet():
    records = read_records(PROJECT_ROOT / "data" / "exemplo.xlsx", "Alunos")
    assert len(records) == 24
    assert records[0].row == 2
    assert records[0].nome and records[0].cpf


def _workbook(tmp_path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Alunos"
    for row in rows:
        ws.append(row)
    path = tmp_path / "entrada.xlsx"
    wb.save(path)
    return path


def test_skips_blank_rows_and_keeps_excel_row_numbers(tmp_path):
    path = _workbook(tmp_path, [
        list(FIELDS),
        ["Ana", "1", "01/01/2015", "1A", "Bia", "11999999999"],
        [None] * 6,
        ["Caio", "2", datetime(2016, 2, 3), "2B", "Dani", 11988887777],
    ])
    records = read_records(path, "Alunos")
    assert [r.row for r in records] == [2, 4]
    assert records[1].nascimento == "03/02/2016"
    assert records[1].telefone == "11988887777"


def test_header_is_case_insensitive_and_column_order_free(tmp_path):
    header = [f.upper() for f in reversed(FIELDS)]
    path = _workbook(tmp_path, [header, ["tel", "resp", "1A", "nasc", "cpf", "nome"]])
    record = read_records(path, "Alunos")[0]
    assert record.nome == "nome" and record.telefone == "tel"


def test_missing_column_is_reported(tmp_path):
    path = _workbook(tmp_path, [["nome", "cpf"], ["Ana", "1"]])
    with pytest.raises(SpreadsheetError, match="nascimento"):
        read_records(path, "Alunos")


def test_missing_file_and_sheet(tmp_path):
    with pytest.raises(SpreadsheetError):
        read_records(tmp_path / "nao_existe.xlsx")
    path = _workbook(tmp_path, [list(FIELDS)])
    with pytest.raises(SpreadsheetError, match="Aba"):
        read_records(path, "Outra")
