"""Regras do pipeline testadas com telas falsas (sem tela, mouse ou teclado)."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.config import PROJECT_ROOT, load_settings
from src.core.exceptions import ElementNotFoundError, LoginFailedError, RobotStopped
from src.pipeline import Robot, run_pipeline
from src.records import Record, Status
from src.screens import SaveResult

SHOT = Path("print.png")


def make_record(row: int = 2, nome: str = "Ana") -> Record:
    return Record(row, nome, "529.982.247-25", "01/01/2015", "3A", "Bia", "11999999999")


@pytest.fixture
def robot(tmp_path) -> Robot:
    settings = load_settings(PROJECT_ROOT / "config" / "settings.example.yaml")
    settings = replace(settings,
                       retry=replace(settings.retry, max_attempts=3, backoff_seconds=0),
                       output=replace(settings.output, screenshots_dir=tmp_path))
    vision = MagicMock()
    vision.screenshot.return_value = SHOT
    bot = Robot(settings, window=MagicMock(), vision=vision, actions=MagicMock())
    bot.go_to_cadastro = MagicMock()
    bot.cadastro = MagicMock()
    return bot


def test_success(robot):
    robot.cadastro.salvar.return_value = SaveResult(ok=True)
    result = robot.process(make_record())
    assert result.status is Status.SUCESSO
    assert result.attempts == 1


def test_rejection_is_not_retried_and_keeps_evidence(robot):
    robot.cadastro.salvar.return_value = SaveResult(ok=False, screenshot=SHOT)
    result = robot.process(make_record())
    assert result.status is Status.REJEITADO
    assert result.attempts == 1
    assert result.screenshot == SHOT
    assert "duplicidade" not in result.message


def test_technical_failure_is_retried(robot):
    robot.cadastro.preencher.side_effect = [ElementNotFoundError("lento"), None]
    robot.cadastro.salvar.return_value = SaveResult(ok=True)
    result = robot.process(make_record())
    assert result.status is Status.SUCESSO
    assert result.attempts == 2
    assert robot.go_to_cadastro.call_count == 2  # volta à tela antes de re-tentar


def test_gives_up_after_max_attempts(robot):
    robot.go_to_cadastro.side_effect = ElementNotFoundError("sumiu")
    result = robot.process(make_record())
    assert result.status is Status.FALHA
    assert result.attempts == 3
    assert "sumiu" in result.message and result.screenshot == SHOT


def test_warns_possible_duplicate_when_retry_after_save(robot):
    robot.cadastro.salvar.side_effect = [ElementNotFoundError("diálogo não apareceu"),
                                         SaveResult(ok=False, screenshot=SHOT)]
    result = robot.process(make_record())
    assert result.status is Status.REJEITADO
    assert "duplicidade" in result.message


def test_emergency_stop_marks_remaining_as_not_processed(robot):
    robot.cadastro.salvar.side_effect = [SaveResult(ok=True), RobotStopped("Esc")]
    records = [make_record(row) for row in (2, 3, 4, 5)]
    results = run_pipeline(robot, records)
    assert [r.status for r in results] == [Status.SUCESSO] + [Status.NAO_PROCESSADO] * 3
    assert [r.record.row for r in results] == [2, 3, 4, 5]


def test_one_bad_record_does_not_stop_the_others(robot):
    robot.cadastro.salvar.side_effect = [
        SaveResult(ok=True), SaveResult(ok=False, screenshot=SHOT), SaveResult(ok=True)]
    results = run_pipeline(robot, [make_record(row) for row in (2, 3, 4)])
    assert [r.status for r in results] == [Status.SUCESSO, Status.REJEITADO, Status.SUCESSO]


def test_login_failure_is_fatal(robot):
    robot.go_to_cadastro.side_effect = LoginFailedError("senha errada")
    results = run_pipeline(robot, [make_record(row) for row in (2, 3)])
    assert all(r.status is Status.NAO_PROCESSADO for r in results)
    assert robot.go_to_cadastro.call_count == 1  # não insiste com senha errada
