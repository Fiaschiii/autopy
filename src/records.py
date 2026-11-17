"""Leitura da planilha de entrada e modelo dos resultados de cada registro."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from openpyxl import load_workbook

FIELDS = ("nome", "cpf", "nascimento", "turma", "responsavel", "telefone")


class SpreadsheetError(Exception):
    """Planilha ausente ou fora do formato esperado."""


@dataclass(frozen=True)
class Record:
    """Uma linha da planilha. `row` é o número da linha no Excel (para o relatório)."""

    row: int
    nome: str
    cpf: str
    nascimento: str
    turma: str
    responsavel: str
    telefone: str

    def values(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in FIELDS}


def to_text(value) -> str:
    """Converte o valor da célula em texto, como a pessoa o digitaria.

    Se a planilha passar pelo Excel, ele pode transformar "01/01/2015" em
    data e "11987654321" em número (às vezes 11987654321.0). Tudo é
    normalizado de volta para texto.
    """
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_records(path: Path, sheet: str | None = None) -> list[Record]:
    """Lê a planilha e devolve os registros, pulando linhas totalmente vazias."""
    if not path.exists():
        raise SpreadsheetError(f"Planilha não encontrada: {path}")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet and sheet not in workbook.sheetnames:
            raise SpreadsheetError(f"Aba '{sheet}' não existe. Abas: {workbook.sheetnames}")
        ws = workbook[sheet] if sheet else workbook.active
        rows = ws.iter_rows(values_only=True)
        header = [to_text(h).lower() for h in next(rows, ())]
        missing = [f for f in FIELDS if f not in header]
        if missing:
            raise SpreadsheetError(f"Colunas obrigatórias ausentes: {missing}")
        index = {name: header.index(name) for name in FIELDS}

        records = []
        for row_number, row in enumerate(rows, start=2):
            values = {name: to_text(row[i]) if i < len(row) else ""
                      for name, i in index.items()}
            if any(values.values()):
                records.append(Record(row=row_number, **values))
        return records
    finally:
        workbook.close()


# -- resultados -----------------------------------------------------------------
class Status(str, Enum):
    SUCESSO = "sucesso"                # cadastrado no sistema
    REJEITADO = "rejeitado"            # o SISTEMA recusou (ex.: CPF inválido)
    FALHA = "falha"                    # problema TÉCNICO após todas as tentativas
    NAO_PROCESSADO = "nao_processado"  # robô interrompido antes de chegar nele


@dataclass
class RecordResult:
    record: Record
    status: Status
    attempts: int = 0
    duration: float = 0.0
    message: str = ""
    screenshot: Path | None = None
    finished_at: datetime = field(default_factory=datetime.now)


def save_results_csv(results: list[RecordResult], path: Path) -> Path:
    """Salva o resultado de cada registro (base para o relatório da etapa 4)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM: abre certo no Excel
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["linha", *FIELDS, "status", "tentativas", "duracao_s",
                         "mensagem", "print", "concluido_em"])
        for r in results:
            writer.writerow([r.record.row, *r.record.values().values(), r.status.value,
                             r.attempts, f"{r.duration:.1f}", r.message,
                             r.screenshot or "", r.finished_at.isoformat(timespec="seconds")])
    return path
