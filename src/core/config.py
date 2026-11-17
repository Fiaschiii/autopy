"""Carregamento da configuração (config/settings.yaml) em objetos tipados."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

#: True quando rodando como executável gerado pelo PyInstaller
FROZEN = getattr(sys, "frozen", False)

# Pasta-base para config/, assets/, data/ e as saídas (logs, relatórios...).
# No .exe, é a pasta onde o executável está (e não a pasta temporária para
# onde o PyInstaller extrai o código), para que o usuário possa editar a
# configuração e trocar templates/planilha sem recompilar.
PROJECT_ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "settings.yaml"
EXAMPLE_SETTINGS = PROJECT_ROOT / "config" / "settings.example.yaml"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppConfig:
    window_title: str
    launch_command: str
    username: str
    password: str


@dataclass(frozen=True)
class InputConfig:
    spreadsheet: Path
    sheet: str


@dataclass(frozen=True)
class VisionConfig:
    templates_dir: Path
    confidence: float
    grayscale: bool


@dataclass(frozen=True)
class TimingConfig:
    default_timeout: float
    poll_interval: float
    action_pause: float
    typing_interval: float


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int
    backoff_seconds: float


@dataclass(frozen=True)
class SafetyConfig:
    stop_hotkey: str
    failsafe: bool


@dataclass(frozen=True)
class OutputConfig:
    logs_dir: Path
    reports_dir: Path
    screenshots_dir: Path


@dataclass(frozen=True)
class Settings:
    app: AppConfig
    input: InputConfig
    vision: VisionConfig
    timing: TimingConfig
    retry: RetryConfig
    safety: SafetyConfig
    output: OutputConfig


def _path(value: str) -> Path:
    """Caminhos relativos são resolvidos a partir da raiz do projeto."""
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_settings(raw: dict) -> Settings:
    """Converte o dicionário do YAML em Settings (KeyError se faltar campo)."""
    v, o, i = raw["vision"], raw["output"], raw["input"]
    return Settings(
        app=AppConfig(**raw["app"]),
        input=InputConfig(spreadsheet=_path(i["spreadsheet"]), sheet=i["sheet"]),
        vision=VisionConfig(templates_dir=_path(v["templates_dir"]),
                            confidence=float(v["confidence"]),
                            grayscale=bool(v["grayscale"])),
        timing=TimingConfig(**{k: float(val) for k, val in raw["timing"].items()}),
        retry=RetryConfig(max_attempts=int(raw["retry"]["max_attempts"]),
                          backoff_seconds=float(raw["retry"]["backoff_seconds"])),
        safety=SafetyConfig(**raw["safety"]),
        output=OutputConfig(**{k: _path(val) for k, val in o.items()}),
    )


def load_settings(path: str | Path | None = None) -> Settings:
    """Lê o settings.yaml; se não existir, usa o settings.example.yaml."""
    path = Path(path) if path else DEFAULT_SETTINGS
    if not path.exists() and path == DEFAULT_SETTINGS:
        log.warning("%s não encontrado; usando %s", path.name, EXAMPLE_SETTINGS.name)
        path = EXAMPLE_SETTINGS
    with path.open(encoding="utf-8") as f:
        return parse_settings(yaml.safe_load(f))
