"""Orquestração: planilha -> sistema-alvo, registro a registro.

Regras de negócio do pipeline:
  * REJEITADO (o sistema recusou, ex.: CPF inválido) NÃO é re-tentado:
    tentar de novo daria o mesmo resultado.
  * FALHA TÉCNICA (elemento não apareceu, foco perdido...) é re-tentada com
    backoff; antes de cada nova tentativa o robô volta à tela de cadastro.
  * Um registro com problema nunca derruba os demais.
  * Parada de emergência: o registro atual e os seguintes ficam como
    NAO_PROCESSADO, e o resultado parcial é preservado.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pyautogui

from .core.actions import Actions
from .core.config import Settings
from .core.exceptions import (ElementNotFoundError, LoginFailedError, RobotError,
                              RobotStopped, TemplateNotFoundError)
from .core.retry import retry_call
from .core.safety import request_stop
from .core.vision import Vision
from .core.window import AppWindow
from .records import Record, RecordResult, Status
from .screens import CadastroScreen, LoginScreen, MenuScreen, SaveResult, Screen

log = logging.getLogger(__name__)

# Elementos que identificam em qual tela o sistema está
SCREEN_ANCHORS = ("cadastro_btn_salvar", "menu_btn_cadastro", "login_btn_entrar",
                  "dlg_icone_erro", "dlg_icone_info")
MAX_NAVIGATION_STEPS = 5


class Robot:
    def __init__(self, settings: Settings, window: AppWindow, vision: Vision,
                 actions: Actions) -> None:
        self.settings = settings
        self.window = window
        self.vision = vision
        shots = settings.output.screenshots_dir
        self.screen = Screen(vision, actions, shots)
        self.login = LoginScreen(vision, actions, shots)
        self.menu = MenuScreen(vision, actions, shots)
        self.cadastro = CadastroScreen(vision, actions, shots)

    @classmethod
    def from_settings(cls, settings: Settings) -> "Robot":
        t = settings.timing
        window = AppWindow(settings.app.window_title, settings.app.launch_command,
                           timeout=t.default_timeout, poll_interval=t.poll_interval)
        vision = Vision(settings.vision.templates_dir, confidence=settings.vision.confidence,
                        grayscale=settings.vision.grayscale, timeout=t.default_timeout,
                        poll_interval=t.poll_interval, window=window)
        return cls(settings, window, vision, Actions(window, t.typing_interval))

    # -- navegação ------------------------------------------------------------
    def go_to_cadastro(self) -> None:
        """Leva o sistema até a tela de cadastro, venha de onde vier.

        É isso que permite recuperar o robô depois de qualquer falha: ele
        descobre em que tela está e segue o caminho até o cadastro.
        """
        for _ in range(MAX_NAVIGATION_STEPS):
            self.window.require_focus()
            found, _ = self.screen.wait(*SCREEN_ANCHORS)
            if found == "cadastro_btn_salvar":
                return
            if found == "login_btn_entrar":
                self.login.entrar(self.settings.app.username, self.settings.app.password)
            elif found == "menu_btn_cadastro":
                self.menu.abrir_cadastro()
            else:  # diálogo esquecido aberto
                self.screen.close_dialog(found)
        raise ElementNotFoundError("Não foi possível chegar à tela de cadastro")

    # -- registro -------------------------------------------------------------
    def process(self, record: Record) -> RecordResult:
        start = time.monotonic()
        label = f"linha{record.row}"
        attempts = 0
        save_clicks = 0

        def attempt() -> SaveResult:
            nonlocal attempts, save_clicks
            attempts += 1
            self.go_to_cadastro()
            self.cadastro.preencher(record)
            save_clicks += 1
            return self.cadastro.salvar(label)

        def on_retry(attempt_number: int, error: BaseException) -> None:
            self.vision.screenshot(self.settings.output.screenshots_dir,
                                   f"falha_{label}_tentativa{attempt_number}")

        result = RecordResult(record, Status.FALHA)
        try:
            saved = retry_call(attempt, max_attempts=self.settings.retry.max_attempts,
                               backoff_seconds=self.settings.retry.backoff_seconds,
                               exceptions=(RobotError,), on_retry=on_retry)
            if saved.ok:
                result.status = Status.SUCESSO
            else:
                result.status = Status.REJEITADO
                result.screenshot = saved.screenshot
                result.message = "O sistema recusou o registro (ver print)"
                if save_clicks > 1:
                    # Uma tentativa anterior pode ter salvo antes de falhar; a
                    # recusa agora pode ser só "CPF já cadastrado".
                    result.message += ("; atenção: tentativa anterior chegou a clicar em "
                                       "Salvar, confira se não houve duplicidade")
        except RobotError as exc:
            result.message = f"{type(exc).__name__}: {exc}"
            result.screenshot = self.vision.screenshot(
                self.settings.output.screenshots_dir, f"falha_{label}")
        finally:
            result.attempts = attempts
            result.duration = time.monotonic() - start
        return result


def run_pipeline(robot: Robot, records: list[Record]) -> list[RecordResult]:
    """Processa todos os registros e devolve o resultado de cada um."""
    results: list[RecordResult] = []
    total = len(records)
    icons = {Status.SUCESSO: "✅", Status.REJEITADO: "❌", Status.FALHA: "💥"}

    for index, record in enumerate(records, start=1):
        log.info("[%d/%d] Linha %d: %s", index, total, record.row, record.nome)
        try:
            result = robot.process(record)
        except (RobotStopped, pyautogui.FailSafeException) as exc:
            if isinstance(exc, pyautogui.FailSafeException):
                request_stop("failsafe: mouse levado ao canto da tela")
            log.warning("Robô interrompido; %d registro(s) não processado(s)",
                        total - index + 1)
            results += [RecordResult(r, Status.NAO_PROCESSADO, message="robô interrompido")
                        for r in records[index - 1:]]
            break
        except (LoginFailedError, TemplateNotFoundError) as exc:
            # Erros de configuração: afetariam todos os registros igualmente
            log.error("Erro fatal, execução encerrada: %s", exc)
            results += [RecordResult(r, Status.NAO_PROCESSADO, message=f"erro fatal: {exc}")
                        for r in records[index - 1:]]
            break
        results.append(result)
        log.info("    %s %s (%d tentativa(s), %.1fs) %s", icons[result.status],
                 result.status.value, result.attempts, result.duration, result.message)
    return results


def required_templates() -> set[str]:
    """Todos os templates que o pipeline pode precisar (usado pelo --check)."""
    from .screens.base import INTERRUPTIONS
    names = set(SCREEN_ANCHORS) | set(INTERRUPTIONS)
    for screen in (LoginScreen, MenuScreen, CadastroScreen):
        names |= set(screen.TEMPLATES)
    return names


def default_results_path(settings: Settings) -> Path:
    return settings.output.reports_dir / f"resultado_{time.strftime('%Y%m%d_%H%M%S')}.csv"
