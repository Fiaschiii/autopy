"""Segurança do robô: parada de emergência, failsafe e preparo do ambiente.

Todas as esperas e ações do robô passam por `check_stop()`, então ao apertar
a hotkey (padrão: Esc) o robô para em no máximo um ciclo de verificação,
inclusive no meio de uma espera longa.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading

import pyautogui

from .exceptions import RobotStopped

log = logging.getLogger(__name__)

_stop_event = threading.Event()
_stop_reason = ""


def request_stop(reason: str = "parada solicitada") -> None:
    """Sinaliza que o robô deve parar (seguro para chamar de outra thread)."""
    global _stop_reason
    if not _stop_event.is_set():
        _stop_reason = reason
        _stop_event.set()
        log.warning("🛑 Parada de emergência: %s", reason)


def reset_stop() -> None:
    _stop_event.clear()


def is_stop_requested() -> bool:
    return _stop_event.is_set()


def check_stop() -> None:
    """Levanta RobotStopped se a parada foi solicitada."""
    if _stop_event.is_set():
        raise RobotStopped(_stop_reason)


def interruptible_sleep(seconds: float) -> None:
    """Como time.sleep, mas acorda imediatamente se a parada for solicitada."""
    if _stop_event.wait(timeout=max(0.0, seconds)):
        check_stop()


def enable_dpi_awareness() -> None:
    """Faz o Windows informar coordenadas reais (físicas) da tela.

    Sem isso, em telas com escala de 125%/150% o Windows "virtualiza" as
    coordenadas e as capturas de tela, e os cliques caem no lugar errado.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Windows 7/8
        except (AttributeError, OSError):
            log.debug("Não foi possível ativar o DPI awareness")


def prepare_environment(failsafe: bool = True, action_pause: float = 0.05) -> None:
    """Configurações globais do PyAutoGUI. Chamar uma vez no início do robô."""
    enable_dpi_awareness()
    pyautogui.FAILSAFE = failsafe        # mouse no canto superior esquerdo = parar
    pyautogui.PAUSE = action_pause       # pausa automática entre chamadas
    size = pyautogui.size()
    log.debug("Ambiente preparado: tela %sx%s, failsafe=%s, pause=%ss",
              size.width, size.height, failsafe, action_pause)


class EmergencyStop:
    """Registra uma hotkey global que interrompe o robô.

    Uso:
        with EmergencyStop("esc"):
            ... # robô trabalhando
    """

    def __init__(self, hotkey: str = "esc") -> None:
        self.hotkey = hotkey
        self._handle = None

    def __enter__(self) -> "EmergencyStop":
        import keyboard  # import tardio: só exige a lib quando realmente usada

        reset_stop()
        self._handle = keyboard.add_hotkey(
            self.hotkey, lambda: request_stop(f"tecla '{self.hotkey}' pressionada"))
        log.info("Pressione '%s' a qualquer momento para parar o robô", self.hotkey)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        import keyboard

        if self._handle is not None:
            keyboard.remove_hotkey(self._handle)
            self._handle = None
        if exc_type is pyautogui.FailSafeException:
            # Converte o failsafe do PyAutoGUI na nossa exceção de parada
            request_stop("failsafe: mouse levado ao canto da tela")
            raise RobotStopped("failsafe acionado") from exc
        return False
