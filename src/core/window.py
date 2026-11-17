"""Controle da janela do sistema-alvo: abrir, localizar e garantir o foco."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import shlex
import subprocess
import sys
import time

import pygetwindow as gw

from .config import FROZEN, PROJECT_ROOT
from .exceptions import WindowFocusError, WindowNotFoundError
from .safety import check_stop, interruptible_sleep

log = logging.getLogger(__name__)

Region = tuple[int, int, int, int]  # (left, top, width, height)


def window_pid(hwnd: int) -> int:
    """PID do processo dono de uma janela (Windows)."""
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


SW_RESTORE = 9


def force_foreground(hwnd: int) -> None:
    """Traz a janela para frente contornando a "trava de primeiro plano".

    O Windows só deixa um processo trocar a janela em primeiro plano se ele
    recebeu a última entrada do usuário; caso contrário SetForegroundWindow
    falha (é por isso que o activate() falha às vezes). Anexando
    temporariamente a nossa thread à fila de entrada da janela que está na
    frente, ganhamos essa permissão, sem precisar simular teclas.
    """
    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    foreground = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(foreground, None)
    our_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    attached = fg_thread and fg_thread != our_thread and user32.AttachThreadInput(
        our_thread, fg_thread, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(our_thread, fg_thread, False)


DWMWA_EXTENDED_FRAME_BOUNDS = 9

# Tamanho mínimo (px) para considerar a janela "pronta" (ver AppWindow.is_ready)
MIN_READY_SIZE = 100


def visible_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) da parte visível da janela, sem as bordas
    invisíveis do Windows 10/11. None se o DWM não estiver disponível."""
    rect = ctypes.wintypes.RECT()
    try:
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect), ctypes.sizeof(rect))
    except (AttributeError, OSError):
        return None
    if result != 0:
        return None
    return rect.left, rect.top, rect.right, rect.bottom


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

    def is_ready(self, window) -> bool:
        """Janela visível, não minimizada e já com tamanho real.

        A janela passa a existir (com título) ANTES de terminar de abrir, e
        durante a animação de restaurar ela fica minúscula por alguns
        instantes. Procurar imagens nesse momento não faz sentido.
        """
        if window is None or window.isMinimized or not window.visible:
            return False
        _, _, width, height = self._region_of(window)
        return width >= MIN_READY_SIZE and height >= MIN_READY_SIZE

    def wait_until_ready(self, timeout: float | None = None):
        """Espera a janela existir E estar pronta (ver is_ready)."""
        timeout = timeout or self.timeout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            check_stop()
            window = self.find()
            if self.is_ready(window):
                return window
            interruptible_sleep(self.poll_interval)
        raise WindowNotFoundError(f"Janela '{self.title}' não ficou pronta em {timeout}s")

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
        if command[0].lower() in ("python", "python.exe") and not FROZEN:
            command[0] = sys.executable  # usa o Python do venv atual
        self._process = subprocess.Popen(command, cwd=PROJECT_ROOT)
        return self.wait_until_ready()

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
        êxito" mesmo quando funcionou, ou falhar por causa da trava de
        primeiro plano. Por isso o resultado nunca é confiado: o foco é
        verificado de fato, com três estratégias em sequência.
        """
        window = self.get()
        if window.isMinimized:
            self._restore(window)

        # 1) caminho normal
        try:
            window.activate()
        except gw.PyGetWindowException as exc:
            log.debug("activate() reportou erro (comum no Windows): %s", exc)
        if self._wait_active(1.0):
            return

        # 2) contornando a trava de primeiro plano
        log.debug("Foco não confirmado; usando AttachThreadInput")
        force_foreground(window._hWnd)
        if self._wait_active(1.0):
            return

        # 3) último recurso: minimizar e restaurar
        log.debug("Foco ainda não confirmado; tentando minimizar/restaurar")
        window.minimize()
        self._wait_minimized(window, 1.0)
        self._restore(window)
        force_foreground(window._hWnd)
        if not self._wait_active(1.5):
            raise WindowFocusError(f"Não foi possível dar foco à janela '{self.title}'")

    @staticmethod
    def _wait_minimized(window, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not window.isMinimized and time.monotonic() < deadline:
            interruptible_sleep(0.05)
        interruptible_sleep(0.3)  # deixa a animação de minimizar terminar

    def _restore(self, window, attempts: int = 3) -> None:
        """Restaura e espera a janela ficar pronta, repetindo se o Windows
        ignorar o pedido (acontece se ele chega durante uma animação)."""
        for _ in range(attempts):
            window.restore()
            try:
                self.wait_until_ready(timeout=1.5)
                return
            except WindowNotFoundError:
                log.debug("Restaurar foi ignorado; tentando de novo")
        raise WindowFocusError(f"A janela '{self.title}' não saiu do estado minimizado")

    def require_focus(self) -> None:
        """Garante o foco antes de qualquer ação de teclado/mouse."""
        check_stop()
        if not self.is_active():
            log.debug("Janela perdeu o foco; recuperando")
            self.focus()

    # -- geometria ------------------------------------------------------------
    def region(self) -> Region:
        """Área VISÍVEL da janela na tela (busca de imagens e gravação).

        No Windows 10/11 o retângulo informado pelo PyGetWindow inclui uma
        borda invisível de ~8 px (usada para redimensionar). Capturar essa
        área mostraria pedaços do que está ATRÁS da janela. O DWM informa o
        retângulo realmente desenhado.
        """
        return self._region_of(self.get())

    @staticmethod
    def _region_of(w) -> Region:
        left, top, right, bottom = visible_bounds(w._hWnd) or (
            w.left, w.top, w.left + w.width, w.top + w.height)
        left, top = max(left, 0), max(top, 0)
        return (left, top, max(right - left, 0), max(bottom - top, 0))
