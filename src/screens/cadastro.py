from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..records import FIELDS, Record
from .base import Screen

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SaveResult:
    ok: bool
    screenshot: Path | None = None


class CadastroScreen(Screen):
    TEMPLATES = ("cadastro_btn_salvar", "cadastro_btn_voltar",
                 *(f"cadastro_campo_{f}" for f in FIELDS),
                 "dlg_icone_info", "dlg_icone_erro", "dlg_btn_ok")

    def preencher(self, record: Record) -> None:
        for name, value in record.values().items():
            self.fill_field(f"cadastro_campo_{name}", value)

    def salvar(self, label: str) -> SaveResult:
        """Clica em Salvar e lê a resposta do sistema pelo ícone do diálogo.

        Ícone azul (i) = salvo; X vermelho = o sistema recusou. No caso de
        recusa, um print do diálogo é guardado como evidência para o relatório.
        """
        _, button = self.wait("cadastro_btn_salvar")
        self.actions.click(button)
        found, _ = self.wait("dlg_icone_info", "dlg_icone_erro")
        screenshot = None
        if found == "dlg_icone_erro":
            screenshot = self.vision.screenshot(self.screenshots_dir, f"rejeitado_{label}")
        self.close_dialog(found)
        self.settle()  # após salvar, o sistema pode exibir um aviso
        return SaveResult(ok=found == "dlg_icone_info", screenshot=screenshot)

    def voltar(self) -> None:
        _, button = self.wait("cadastro_btn_voltar")
        self.actions.click(button)
        self.wait("menu_btn_cadastro")
        self.settle()
