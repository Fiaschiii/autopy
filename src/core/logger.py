"""Configuração de logging: console (resumido) + arquivo por execução (detalhado)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> Path:
    """Configura o logger raiz e retorna o caminho do arquivo de log criado."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"robo_{datetime.now():%Y%m%d_%H%M%S}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT, datefmt="%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers[:] = [file_handler, console]

    # Bibliotecas de terceiros muito verbosas
    for noisy in ("PIL", "pyscreeze"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_file
