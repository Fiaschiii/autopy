"""
Gera as imagens de referência (templates) do SisEscola 98 de forma automática.

Em vez de recortar prints à mão, o script abre o app no MESMO processo,
navega pelas telas acionando os widgets diretamente (sem mexer no mouse ou
teclado reais) e recorta cada elemento pelas coordenadas do próprio Tkinter.
Assim os templates são reproduzíveis: basta rodar de novo se o app mudar.

Também salva um print de cada tela em tests/fixtures/screens/, usado pelos
testes para garantir que cada template é encontrado na tela certa e
SOMENTE nela.

Uso:
    python scripts/capturar_templates.py
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo_app"))
import fake_erp  # noqa: E402

TEMPLATES_DIR = ROOT / "assets" / "templates"
SCREENS_DIR = ROOT / "tests" / "fixtures" / "screens"

# Margem (px) da borda do campo incluída no template "rótulo + campo".
# Pequena o bastante para não incluir o cursor nem o texto digitado.
FIELD_EDGE = 2
# Recorte dos botões: ignora a moldura (inset) e deixa folga ao redor do texto
BUTTON_INSET = 4
BUTTON_TEXT_PAD = 3

Box = tuple[int, int, int, int]


class Capturer:
    def __init__(self) -> None:
        fake_erp.make_dpi_aware()
        db = Path(tempfile.mkdtemp()) / "db.csv"
        args = argparse.Namespace(usuario="admin", senha="admin", db=str(db),
                                  lentidao_min=1.0, lentidao_max=1.0, chaos=0.0)
        self.app = fake_erp.FakeERP(args)
        self.app.attributes("-topmost", True)
        self.steps: list = []
        self.saved: list[str] = []

    # -- utilidades -----------------------------------------------------------
    @staticmethod
    def box(widget: tk.Misc) -> Box:
        widget.update_idletasks()
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        return x, y, x + widget.winfo_width(), y + widget.winfo_height()

    def grab(self, bbox: Box, path: Path) -> None:
        self.app.update()
        path.parent.mkdir(parents=True, exist_ok=True)
        ImageGrab.grab(bbox, all_screens=True).save(path)
        self.saved.append(str(path.relative_to(ROOT)))

    def template(self, name: str, bbox: Box) -> None:
        self.grab(bbox, TEMPLATES_DIR / f"{name}.png")

    def screen(self, name: str) -> None:
        self.grab(self.box(self.app), SCREENS_DIR / f"{name}.png")

    def widgets(self, cls=None, text: str | None = None, root: tk.Misc | None = None):
        root = root or self.app
        found = []
        for child in root.winfo_children():
            if (cls is None or isinstance(child, cls)) and (
                    text is None or child.cget("text") == text):
                found.append(child)
            found += self.widgets(cls, text, child)
        return found

    def one(self, cls, text: str, root: tk.Misc | None = None):
        return self.widgets(cls, text, root)[0]

    def field(self, name: str, label_text: str) -> None:
        """Template = rótulo + borda esquerda do campo à direita dele."""
        label = self.one(tk.Label, label_text, self.app.content)
        grid = label.master
        info = label.grid_info()
        entry = grid.grid_slaves(row=info["row"], column=1)[0]
        lx0, ly0, lx1, ly1 = self.box(label)
        ex0, ey0, ex1, ey1 = self.box(entry)
        self.template(name, (lx0, min(ly0, ey0), ex0 + FIELD_EDGE, max(ly1, ey1)))

    def button(self, name: str, text: str, root: tk.Misc | None = None) -> None:
        """Template = apenas o TEXTO do botão.

        Os botões têm o mesmo tamanho e moldura cinza; recortando o botão
        inteiro, "Salvar" chegava a 0,87 de semelhança com "Entrar". Só o
        texto deixa cada template inconfundível (falsos positivos <= 0,75).
        """
        x0, y0, x1, y1 = self.box(self.one(tk.Button, text, root or self.app.content))
        self.app.update()
        inner = (x0 + BUTTON_INSET, y0 + BUTTON_INSET, x1 - BUTTON_INSET, y1 - BUTTON_INSET)
        dark = ImageGrab.grab(inner, all_screens=True).convert("L").point(
            lambda p: 255 if p < 100 else 0)
        bx0, by0, bx1, by1 = dark.getbbox()
        p = BUTTON_TEXT_PAD
        self.template(name, (inner[0] + bx0 - p, inner[1] + by0 - p,
                             inner[0] + bx1 + p, inner[1] + by1 + p))

    def dialog(self, trigger, icon: str, screen_name: str, then) -> None:
        """Dispara uma ação que abre um diálogo modal e captura o diálogo."""
        def capture() -> None:
            dlg = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))
            dlg.attributes("-topmost", True)
            dlg.update()
            labels = self.widgets(tk.Label, root=dlg)
            self.template(f"dlg_icone_{icon}", self.box(labels[0]))
            self.button("dlg_btn_ok", "OK", root=dlg)
            self.screen(screen_name)
            dlg.destroy()
            self.app.after(300, then)
        self.app.after(500, capture)
        trigger()

    def fill(self, values: list[str]) -> None:
        entries = self.widgets(tk.Entry, root=self.app.content)
        for entry, value in zip(entries, values):
            entry.delete(0, "end")
            entry.insert(0, value)

    # -- roteiro --------------------------------------------------------------
    def run(self) -> None:
        a = self.app

        def login() -> None:
            self.template("app_cabecalho", self.box(self.one(tk.Label, "SisEscola 98")))
            self.field("login_campo_usuario", "Usuário:")
            self.field("login_campo_senha", "Senha:")
            self.button("login_btn_entrar", "Entrar")
            self.screen("login")
            self.fill(["admin", "admin"])
            self.one(tk.Button, "Entrar", a.content).invoke()
            a.after(300, carregando)

        def carregando() -> None:
            self.template("carregando", self.box(
                self.one(tk.Label, "Carregando, aguarde...", a.content)))
            self.screen("carregando")
            a.after(1200, menu)

        def menu() -> None:
            self.button("menu_btn_cadastro", "Cadastro de Alunos")
            self.screen("menu")
            self.dialog(self.one(tk.Button, "Relatórios", a.content).invoke,
                        "aviso", "dialogo_aviso", go_cadastro)

        def go_cadastro() -> None:
            self.one(tk.Button, "Cadastro de Alunos", a.content).invoke()
            a.after(1500, cadastro)

        def cadastro() -> None:
            for key, text in [("nome", "Nome completo:"), ("cpf", "CPF:"),
                              ("nascimento", "Nascimento (DD/MM/AAAA):"),
                              ("turma", "Turma (1A a 5B):"),
                              ("responsavel", "Responsável:"), ("telefone", "Telefone:")]:
                self.field(f"cadastro_campo_{key}", text)
            self.button("cadastro_btn_salvar", "Salvar")
            self.button("cadastro_btn_voltar", "Voltar")
            self.screen("cadastro")
            self.fill(["João Conceição", "123.456.789-00", "01/01/2015", "3A",
                       "Maria Conceição", "(11) 98765-4321"])
            self.screen("cadastro_preenchido")
            self.dialog(self.one(tk.Button, "Salvar", a.content).invoke,
                        "erro", "dialogo_erro", sucesso)

        def sucesso() -> None:
            self.fill(["João Conceição", "529.982.247-25", "01/01/2015", "3A",
                       "Maria Conceição", "(11) 98765-4321"])
            self.dialog(self.one(tk.Button, "Salvar", a.content).invoke,
                        "info", "dialogo_sucesso", a.destroy)

        a.after(800, login)
        a.mainloop()


if __name__ == "__main__":
    capturer = Capturer()
    capturer.run()
    print(f"{len(capturer.saved)} imagens salvas:")
    for path in sorted(set(capturer.saved)):
        print("  ", path)
