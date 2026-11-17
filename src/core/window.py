"""Controle da janela do sistema-alvo: abrir, localizar e garantir o foco."""

from __future__ import annotations

import ctypes
import logging
import shlex
import subprocess
import sys
import time

import pygetwindow as gw

from .config import PROJECT_ROOT
from .exceptions import WindowFocusError, WindowNotFoundError
from .safety import check_stop, interruptible_sleep

log = logging.getLogger(__name__)

Region = tuple[int, int, int, int]  # (left, top, width, height)


def window_pid(hwnd: int) -> int:
    """PID do processo dono de uma janela (Windows)."""
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


class AppWindow:
    """Representa a janela do sistema-alvo, identificada pelo início do título."""

    def __init__(self, title: str, launch_command: str | None = None,
                 timeout: float = 15, poll_interval: float = 0.25) -> None:
        self.title = title
        self.launch_command = launch_command
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._process: subprocess.Popen | None = None

    # -- localizar / abrir ----------------------------------------------------
    def find(self):
        """Retorna a janela ou None. Compara pelo INÍCIO do título para não
        confundir com outros programas que apenas mencionam o nome (ex.: um
        editor com um arquivo chamado 'SisEscola 98.txt')."""
        matches = [w for w in gw.getAllWindows() if w.title.startswith(self.title)]
        return matches[0] if matches else None

    def get(self):
        window = self.find()
        if window is None:
            raise WindowNotFoundError(f"Janela '{self.title}' não encontrada")
        return window

    def wait_until_open(self, timeout: float | None = None):
        deadline = time.monotonic() + (timeout or self.timeout)
        while time.monotonic() < deadline:
            check_stop()
            window = self.find()
            if window is not None:
                return window
            interruptible_sleep(self.poll_interval)
        raise WindowNotFoundError(f"Janela '{self.title}' não abriu em {timeout or self.timeout}s")

    def ensure_open(self):
        """Usa a janela se já estiver aberta; senão executa o launch_command."""
        window = self.find()
        if window is not None:
            log.debug("Janela '%s' já está aberta", self.title)
            return window
        if not self.launch_command:
            raise WindowNotFoundError(f"Janela '{self.title}' não está aberta")
        log.info("Abrindo o sistema: %s", self.launch_command)
        command = shlex.split(self.launch_command, posix=False)
        if command[0].lower() in ("python", "python.exe"):
            command[0] = sys.executable  # usa o Python do venv atual
        self._process = subprocess.Popen(command, cwd=PROJECT_ROOT)
        return self.wait_until_open()

    def close_launched(self) -> None:
        """Encerra o processo, se tiver sido aberto pelo próprio robô."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=5)

    # -- foco -----------------------------------------------------------------
    def is_active(self) -> bool:
        """True se a janela ativa pertence ao sistema-alvo.

        Compara o PROCESSO, não a janela: quando o sistema abre uma caixa de
        mensagem (ex.: "Sucesso"), ela é a janela ativa, e ainda assim o foco
        está corretamente no sistema-alvo.
        """
        window = self.find()
        active = gw.getActiveWindow()
        if not (window and active):
            return False
        return (window._hWnd == active._hWnd
                or window_pid(window._hWnd) == window_pid(active._hWnd))

    def _wait_active(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.is_active():
                return True
            interruptible_sleep(0.05)
        return self.is_active()

    def focus(self) -> None:
        """Traz a janela para frente e CONFIRMA que ela recebeu o foco.

        O `activate()` do PyGetWindow tem um bug conhecido no Windows: pode
        lançar PyGetWindowException com "código 0 - operação concluída com
        êxito" mesmo quando funcionou, ou falhar silenciosamente. Por isso o
        resultado nunca é confiado: o foco é verificado de fato e, se
        necessário, usamos o truque de minimizar/restaurar.
        """
        window = self.get()
        if window.isMinimized:
            window.restore()
        try:
            window.activate()
        except gw.PyGetWindowException as exc:
            log.debug("activate() reportou erro (comum no Windows): %s", exc)
        if self._wait_active(1.0):
            return

        log.debug("Foco não confirmado; tentando minimizar/restaurar")
        window.minimize()
        interruptible_sleep(0.2)
        window.restore()
        if not self._wait_active(1.5):
            raise WindowFocusError(f"Não foi possível dar foco à janela '{self.title}'")

    def require_focus(self) -> None:
        """Garante o foco antes de qualquer ação de teclado/mouse."""
        check_stop()
        if not self.is_active():
            log.debug("Janela perdeu o foco; recuperando")
            self.focus()

    # -- geometria ------------------------------------------------------------
    def region(self) -> Region:
        """Área da janela na tela, usada para restringir a busca de imagens."""
        w = self.get()
        return (max(w.left, 0), max(w.top, 0), w.width, w.height)
