"""Base dos Page Objects: cada tela do sistema-alvo vira uma classe.

O resto do robô nunca fala em "template" ou "coordenada": ele chama ações de
negócio como `login.entrar(usuario, senha)` ou `cadastro.preencher(registro)`.
Se o sistema mudar de visual, só a classe da tela correspondente muda.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from ..core.actions import Actions
from ..core.exceptions import ElementNotFoundError
from ..core.safety import interruptible_sleep
from ..core.vision import Match, Vision

log = logging.getLogger(__name__)

# Pop-ups que podem surgir a qualquer momento e devem ser fechados
INTERRUPTIONS = ("dlg_icone_aviso",)

# Distância (px) da borda direita do template "rótulo + campo" até o ponto de
# clique dentro do campo.
FIELD_CLICK_OFFSET = 20

# Tempo (s) de estabilização após trocar de tela (ver Screen.settle)
SETTLE_SECONDS = 0.5


class Screen:
    #: templates usados pela tela (verificados pelo modo --check)
    TEMPLATES: tuple[str, ...] = ()

    def __init__(self, vision: Vision, actions: Actions, screenshots_dir: Path) -> None:
        self.vision = vision
        self.actions = actions
        self.screenshots_dir = screenshots_dir

    def wait(self, *names: str, timeout: float | None = None) -> tuple[str, Match]:
        """Espera um dos elementos, fechando pop-ups inesperados no caminho."""
        timeout = self.vision.timeout if timeout is None else timeout
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ElementNotFoundError(f"Nenhum de {list(names)} apareceu em {timeout:.1f}s")
            # Pop-ups são verificados PRIMEIRO: o elemento-alvo pode estar
            # visível atrás de um diálogo modal, e clicar nele não teria efeito.
            found, match = self.vision.wait_for_any(*INTERRUPTIONS, *names, timeout=remaining)
            if found in INTERRUPTIONS and found not in names:
                log.warning("⚠️  Pop-up inesperado (%s); fechando e seguindo", found)
                self.close_dialog(found)
                continue
            return found, match

    def settle(self, seconds: float = SETTLE_SECONDS) -> None:
        """Estabilização após trocar de tela.

        Sistemas legados costumam abrir avisos logo DEPOIS de mostrar a tela.
        Esperar um instante e fechar o que tiver surgido evita digitar dentro
        de um pop-up que apareceu no meio do preenchimento.
        """
        interruptible_sleep(seconds)
        for icon in INTERRUPTIONS:
            if self.vision.exists(icon):
                log.warning("⚠️  Pop-up inesperado (%s); fechando e seguindo", icon)
                self.close_dialog(icon)

    def close_dialog(self, icon: str) -> None:
        """Fecha o diálogo aberto clicando em OK e confirma que ele sumiu."""
        ok = self.vision.wait_for("dlg_btn_ok", timeout=5)
        self.actions.click(ok)
        self.vision.wait_until_gone(icon, timeout=5)

    def fill_field(self, template: str, value: str) -> None:
        """Clica no campo (localizado pelo rótulo ao lado) e digita o valor."""
        _, anchor = self.wait(template)
        self.actions.click(anchor, anchor="right", dx=FIELD_CLICK_OFFSET)
        self.actions.type_text(value, clear=True)

    def is_visible(self) -> bool:
        return self.vision.exists(self.TEMPLATES[0])
