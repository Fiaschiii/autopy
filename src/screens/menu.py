from __future__ import annotations

import logging

from .base import Screen

log = logging.getLogger(__name__)


class MenuScreen(Screen):
    TEMPLATES = ("menu_btn_cadastro",)

    def abrir_cadastro(self) -> None:
        log.info("📂 Abrindo o Cadastro de Alunos")
        _, button = self.wait("menu_btn_cadastro")
        self.actions.click(button)
        self.wait("cadastro_btn_salvar")  # espera passar o "Carregando..."
        self.settle()
