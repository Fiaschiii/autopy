from __future__ import annotations

import logging

from ..core.exceptions import LoginFailedError
from .base import Screen

log = logging.getLogger(__name__)


class LoginScreen(Screen):
    TEMPLATES = ("login_btn_entrar", "login_campo_usuario", "login_campo_senha",
                 "dlg_icone_erro", "dlg_btn_ok")

    def entrar(self, usuario: str, senha: str) -> None:
        log.info("🔑 Fazendo login como '%s'", usuario)
        self.fill_field("login_campo_usuario", usuario)
        self.fill_field("login_campo_senha", senha)
        _, button = self.wait("login_btn_entrar")
        self.actions.click(button)

        # Sucesso = o menu aparece (depois do "Carregando..."); falha = diálogo de erro
        found, _ = self.wait("menu_btn_cadastro", "dlg_icone_erro")
        if found == "dlg_icone_erro":
            self.close_dialog(found)
            raise LoginFailedError("O sistema recusou o usuário/senha configurados")
        self.settle()
        log.info("Login realizado")
