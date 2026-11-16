"""As "mãos" do robô: mouse e teclado com proteções.

Toda ação passa por `_guard()`, que:
  1. verifica se a parada de emergência foi solicitada;
  2. confirma que a janela do sistema-alvo está com o foco.
Assim o robô NUNCA digita em outro programa por engano.
"""

from __future__ import annotations

import logging

import pyautogui
import pyperclip

from .safety import check_stop, interruptible_sleep
from .vision import Match
from .window import AppWindow

log = logging.getLogger(__name__)


# Em teclados ABNT2/internacionais estes são "teclas mortas": digitar ' e
# depois a produz á. Digitá-los tecla a tecla corromperia o texto.
DEAD_KEYS = set("'\"`~^")


def is_typeable(text: str) -> bool:
    """True se é seguro digitar o texto tecla a tecla com `pyautogui.write`.

    O PyAutoGUI só digita ASCII: caracteres como 'á', 'ç', 'ã' são IGNORADOS
    em silêncio ("João" viraria "Joo"). Teclas mortas também ficam de fora.
    """
    return all(32 <= ord(ch) < 127 and ch not in DEAD_KEYS for ch in text)


class Actions:
    def __init__(self, window: AppWindow, typing_interval: float = 0.01) -> None:
        self.window = window
        self.typing_interval = typing_interval

    def _guard(self) -> None:
        check_stop()
        self.window.require_focus()

    # -- mouse ----------------------------------------------------------------
    def click(self, target: Match | tuple[int, int], *, dx: int = 0, dy: int = 0,
              anchor: str = "center", clicks: int = 1) -> None:
        """Clica num elemento encontrado (Match) ou num ponto (x, y)."""
        self._guard()
        if isinstance(target, Match):
            x, y = target.point(dx, dy, anchor)
            label = target.name
        else:
            x, y = target[0] + dx, target[1] + dy
            label = f"({x}, {y})"
        log.debug("Clique em %s -> (%s, %s)", label, x, y)
        pyautogui.click(x, y, clicks=clicks)

    # -- teclado --------------------------------------------------------------
    def type_text(self, text: str, *, clear: bool = False) -> None:
        """Digita o texto no campo com foco.

        Texto com acentos é colado pela área de transferência (Ctrl+V), e o
        conteúdo original da área de transferência do usuário é restaurado.
        """
        self._guard()
        if clear:
            self.clear_field()
        text = str(text)
        if is_typeable(text):
            pyautogui.write(text, interval=self.typing_interval)
            return
        log.debug("Texto com caracteres especiais; colando via área de transferência")
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous = None
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        interruptible_sleep(0.05)  # dá tempo do app ler o clipboard
        if previous is not None:
            pyperclip.copy(previous)

    def clear_field(self) -> None:
        """Apaga o conteúdo do campo com foco (Home, Shift+End, Delete).

        Funciona em praticamente qualquer campo, ao contrário de Ctrl+A,
        que em alguns sistemas legados não seleciona tudo.
        """
        self._guard()
        pyautogui.press("home")
        pyautogui.hotkey("shift", "end")
        pyautogui.press("delete")

    def press(self, *keys: str) -> None:
        self._guard()
        for key in keys:
            pyautogui.press(key)

    def hotkey(self, *keys: str) -> None:
        self._guard()
        pyautogui.hotkey(*keys)
