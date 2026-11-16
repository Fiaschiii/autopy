"""
Gera data/exemplo.xlsx com alunos FICTÍCIOS para demonstrar o robô.

Alguns registros são propositalmente inválidos (CPF errado, data inválida,
turma inexistente e CPF duplicado) para demonstrar o tratamento de erros e
o relatório final.

Uso:
    python scripts/gerar_planilha_exemplo.py
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

SEED = 42
TOTAL_VALIDOS = 20
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "exemplo.xlsx"

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabriela", "Heitor",
         "Isabela", "João", "Larissa", "Mateus", "Natália", "Otávio", "Paula",
         "Rafael", "Sofia", "Thiago", "Valentina", "Yuri"]
SOBRENOMES = ["Almeida", "Barbosa", "Costa", "Dias", "Ferreira", "Gomes", "Lima",
              "Martins", "Nunes", "Oliveira", "Pereira", "Ribeiro", "Santos", "Souza"]
TURMAS = ["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B", "5A", "5B"]
COLUNAS = ["nome", "cpf", "nascimento", "turma", "responsavel", "telefone"]


def gerar_cpf(rng: random.Random) -> str:
    digits = [rng.randint(0, 9) for _ in range(9)]
    for size in (9, 10):
        total = sum(d * w for d, w in zip(digits, range(size + 1, 1, -1)))
        digits.append((total * 10) % 11 % 10)
    s = "".join(map(str, digits))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def gerar_aluno(rng: random.Random, nome: str) -> dict:
    sobrenome = rng.choice(SOBRENOMES)
    nascimento = date(2014, 1, 1) + timedelta(days=rng.randint(0, 5 * 365))
    return {
        "nome": f"{nome} {sobrenome}",
        "cpf": gerar_cpf(rng),
        "nascimento": nascimento.strftime("%d/%m/%Y"),
        "turma": rng.choice(TURMAS),
        "responsavel": f"{rng.choice(NOMES)} {sobrenome}",
        "telefone": f"(11) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
    }


def main() -> None:
    rng = random.Random(SEED)
    alunos = [gerar_aluno(rng, nome) for nome in NOMES[:TOTAL_VALIDOS]]

    # Registros inválidos de propósito, intercalados na lista
    cpf_invalido = gerar_aluno(rng, "Marcos") | {"cpf": "123.456.789-00"}
    data_invalida = gerar_aluno(rng, "Clara") | {"nascimento": "31/02/2016"}
    turma_invalida = gerar_aluno(rng, "Lucas") | {"turma": "9Z"}
    cpf_duplicado = gerar_aluno(rng, "Beatriz") | {"cpf": alunos[0]["cpf"]}
    for pos, registro in [(4, cpf_invalido), (9, data_invalida),
                          (14, turma_invalida), (19, cpf_duplicado)]:
        alunos.insert(pos, registro)

    wb = Workbook()
    ws = wb.active
    ws.title = "Alunos"
    ws.append(COLUNAS)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="000080")
    for aluno in alunos:
        ws.append([aluno[c] for c in COLUNAS])
    for col, width in zip("ABCDEF", (28, 18, 14, 8, 28, 18)):
        ws.column_dimensions[col].width = width

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT)
    print(f"Planilha gerada: {OUTPUT} ({len(alunos)} registros, 4 inválidos)")


if __name__ == "__main__":
    main()
