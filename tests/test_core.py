"""Testes unitários do núcleo (sem tela, sem mouse, sem teclado)."""

import threading
import time
from pathlib import Path

import pytest

from src.core import safety
from src.core.actions import is_typeable
from src.core.config import PROJECT_ROOT, load_settings
from src.core.exceptions import (ElementNotFoundError, RobotError, RobotStopped,
                                 TemplateNotFoundError)
from src.core.retry import retry_call
from src.core.vision import Match, Vision

EXAMPLE = PROJECT_ROOT / "config" / "settings.example.yaml"


# -- config -------------------------------------------------------------------
def test_settings_example_loads_with_absolute_paths():
    s = load_settings(EXAMPLE)
    assert s.app.window_title == "SisEscola 98"
    assert s.input.spreadsheet.is_absolute() and s.input.spreadsheet.exists()
    assert s.vision.templates_dir.is_dir()
    assert 0 < s.vision.confidence <= 1
    assert s.retry.max_attempts >= 1


# -- digitação ----------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("Ana Pereira", True),
    ("123.456.789-00", True),
    ("(11) 98765-4321", True),
    ("João", False),        # acento: pyautogui ignoraria o "ã"
    ("Conceição", False),
    ("D'Ávila", False),
    ("O'Neil", False),      # ' é tecla morta no ABNT2
    ("~til", False),
])
def test_is_typeable(text, expected):
    assert is_typeable(text) is expected


# -- retry --------------------------------------------------------------------
def test_retry_succeeds_after_failures():
    calls, retried = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ElementNotFoundError("ainda não")
        return "ok"

    result = retry_call(flaky, max_attempts=3, backoff_seconds=0,
                        on_retry=lambda n, e: retried.append(n))
    assert result == "ok"
    assert len(calls) == 3 and retried == [1, 2]


def test_retry_gives_up_and_reraises():
    def always_fails():
        raise RobotError("falhou")

    with pytest.raises(RobotError):
        retry_call(always_fails, max_attempts=2, backoff_seconds=0)


def test_retry_never_retries_emergency_stop():
    calls = []

    def stopped():
        calls.append(1)
        raise RobotStopped("Esc")

    with pytest.raises(RobotStopped):
        retry_call(stopped, max_attempts=5, backoff_seconds=0)
    assert len(calls) == 1


def test_retry_does_not_catch_unexpected_errors():
    with pytest.raises(ZeroDivisionError):
        retry_call(lambda: 1 / 0, max_attempts=3, backoff_seconds=0)


# -- parada de emergência -----------------------------------------------------
def test_interruptible_sleep_wakes_up_on_stop():
    threading.Timer(0.1, safety.request_stop, args=("teste",)).start()
    start = time.monotonic()
    with pytest.raises(RobotStopped):
        safety.interruptible_sleep(10)
    assert time.monotonic() - start < 1


def test_check_stop():
    safety.check_stop()  # sem parada: não levanta
    safety.request_stop("teste")
    with pytest.raises(RobotStopped, match="teste"):
        safety.check_stop()


# -- visão --------------------------------------------------------------------
def test_match_points():
    m = Match("x", left=100, top=50, width=40, height=20)
    assert m.center == (120, 60)
    assert m.point(dx=15, anchor="right") == (155, 60)


def test_missing_template_is_configuration_error(tmp_path: Path):
    with pytest.raises(TemplateNotFoundError):
        Vision(tmp_path).template("nao_existe")


def test_wait_for_any_returns_first_found(monkeypatch):
    vision = Vision(Path("."), timeout=2, poll_interval=0.01)
    seen = iter([None, None, None, Match("dlg_icone_erro", 0, 0, 10, 10)])
    monkeypatch.setattr(vision, "find", lambda name: next(seen) if name else None)
    name, match = vision.wait_for_any("dlg_icone_info", "dlg_icone_erro")
    assert name == "dlg_icone_erro" and match.width == 10


def test_wait_for_times_out(monkeypatch):
    vision = Vision(Path("."), timeout=0.1, poll_interval=0.01)
    monkeypatch.setattr(vision, "find", lambda name: None)
    with pytest.raises(ElementNotFoundError):
        vision.wait_for("botao")


def test_wait_for_respects_emergency_stop(monkeypatch):
    vision = Vision(Path("."), timeout=10, poll_interval=0.01)
    monkeypatch.setattr(vision, "find", lambda name: None)
    threading.Timer(0.1, safety.request_stop, args=("teste",)).start()
    with pytest.raises(RobotStopped):
        vision.wait_for("botao")
