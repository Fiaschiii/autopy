"""
SisEscola 98 — sistema legado FICTÍCIO usado como alvo da automação.

Simula um ERP desktop antigo, sem API, onde a única forma de inserir dados
é pela interface gráfica. Inclui comportamentos "do mundo real" para testar
a robustez do robô:

  * lentidão aleatória ao trocar de tela (--lentidao-min / --lentidao-max)
  * pop-ups inesperados do sistema (--chaos, probabilidade de 0 a 1)
  * validações de campos com mensagens de erro (CPF, data, turma...)

Uso:
    python demo_app/fake_erp.py
    python demo_app/fake_erp.py --chaos 0.2 --lentidao-max 3
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import random
import re
import sys
import tkinter as tk
from datetime import date, datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# Aparência (estilo Windows 98) — tudo com tamanhos fixos para que o app
# seja renderizado pixel a pixel igual em qualquer máquina/escala de tela.
# ----------------------------------------------------------------------------
WINDOW_TITLE = "SisEscola 98 - Sistema de Gestão Escolar"
WINDOW_SIZE = (800, 560)

BG = "#c0c0c0"
NAVY = "#000080"
WHITE = "#ffffff"
FONT = ("Tahoma", 9)
FONT_BOLD = ("Tahoma", 9, "bold")
FONT_TITLE = ("Tahoma", 14, "bold")

TURMAS = ["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B", "5A", "5B"]

DB_FIELDS = ["codigo", "nome", "cpf", "nascimento", "turma", "responsavel",
             "telefone", "cadastrado_em"]


def make_dpi_aware() -> None:
    """Evita que o Windows "estique" a janela em telas com escala > 100%."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


# ----------------------------------------------------------------------------
# Validações
# ----------------------------------------------------------------------------
def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def is_valid_cpf(cpf: str) -> bool:
    digits = only_digits(cpf)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(d) * w for d, w in zip(digits[:size], range(size + 1, 1, -1)))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True


def parse_birth_date(value: str) -> date | None:
    try:
        parsed = datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None
    return parsed if parsed <= date.today() else None


# ----------------------------------------------------------------------------
# "Banco de dados" (CSV)
# ----------------------------------------------------------------------------
class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def count(self) -> int:
        return len(self._rows())

    def cpf_exists(self, cpf: str) -> bool:
        return any(row["cpf"] == cpf for row in self._rows())

    def insert(self, record: dict) -> str:
        rows = self._rows()
        code = f"{len(rows) + 1:06d}"
        is_new = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=DB_FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow({
                "codigo": code,
                **record,
                "cadastrado_em": datetime.now().isoformat(timespec="seconds"),
            })
        return code


# ----------------------------------------------------------------------------
# Widgets reutilizáveis
# ----------------------------------------------------------------------------
def button(parent: tk.Misc, text: str, command, width: int = 12) -> tk.Button:
    return tk.Button(parent, text=text, command=command, width=width, font=FONT,
                     bg=BG, activebackground=BG, relief="raised", bd=2)


def entry(parent: tk.Misc, width: int = 30, show: str = "") -> tk.Entry:
    return tk.Entry(parent, width=width, font=FONT, bg=WHITE, relief="sunken",
                    bd=2, show=show)


class Dialog(tk.Toplevel):
    """Caixa de mensagem modal com visual próprio (independe do tema do SO)."""

    ICONS = {"info": ("i", NAVY), "erro": ("X", "#c00000"), "aviso": ("!", "#806000")}

    def __init__(self, master: tk.Tk, title: str, message: str, kind: str = "info") -> None:
        super().__init__(master)
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(master)

        body = tk.Frame(self, bg=BG, padx=16, pady=14)
        body.pack()
        symbol, color = self.ICONS[kind]
        tk.Label(body, text=symbol, font=("Tahoma", 18, "bold"), fg=WHITE, bg=color,
                 width=2).grid(row=0, column=0, padx=(0, 12), sticky="n")
        tk.Label(body, text=message, font=FONT, bg=BG, justify="left",
                 wraplength=320).grid(row=0, column=1, sticky="w")
        ok = button(body, "OK", self.destroy, width=10)
        ok.grid(row=1, column=0, columnspan=2, pady=(14, 0))

        self.bind("<Return>", lambda _e: self.destroy())
        self.bind("<Escape>", lambda _e: self.destroy())

        # Centraliza sobre a janela principal
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self.grab_set()
        ok.focus_set()
        master.wait_window(self)


# ----------------------------------------------------------------------------
# Aplicação
# ----------------------------------------------------------------------------
class FakeERP(tk.Tk):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self.args = args
        self.db = Database(Path(args.db))
        self.user: str | None = None

        # Escala fixa de 96 DPI: fontes com o mesmo tamanho em pixels em
        # qualquer máquina (essencial para o reconhecimento de imagem).
        self.tk.call("tk", "scaling", 96 / 72)

        self.title(WINDOW_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        w, h = WINDOW_SIZE
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Cabeçalho fixo
        header = tk.Frame(self, bg=NAVY, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="SisEscola 98", font=FONT_TITLE, fg=WHITE,
                 bg=NAVY).pack(side="left", padx=12)
        tk.Label(header, text="Módulo Secretaria", font=FONT, fg=WHITE,
                 bg=NAVY).pack(side="right", padx=12)

        # Barra de status
        self.status = tk.Label(self, font=FONT, bg=BG, anchor="w", relief="sunken", bd=1)
        self.status.pack(side="bottom", fill="x")

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)

        self.show_login()

    # -- navegação ------------------------------------------------------------
    def _clear(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _update_status(self) -> None:
        user = self.user or "-"
        self.status.config(text=f"  Usuário: {user}    |    Registros: {self.db.count()}"
                                f"    |    Versão 1.98.4")

    def navigate(self, screen) -> None:
        """Troca de tela com um atraso aleatório, como um sistema lento."""
        self._clear()
        tk.Label(self.content, text="Carregando, aguarde...", font=FONT_BOLD,
                 bg=BG).place(relx=0.5, rely=0.45, anchor="center")
        self.config(cursor="watch")
        delay = random.uniform(self.args.lentidao_min, self.args.lentidao_max)
        self.after(int(delay * 1000), lambda: self._finish_navigation(screen))

    def _finish_navigation(self, screen) -> None:
        self.config(cursor="")
        self._clear()
        screen()
        self._update_status()
        self.after(150, self._maybe_chaos)

    def _maybe_chaos(self) -> None:
        if random.random() < self.args.chaos:
            Dialog(self, "Aviso do Sistema",
                   random.choice([
                       "O backup automático será executado às 18:00.",
                       "Existem atualizações pendentes. Contate o suporte.",
                       "Sua senha expira em 5 dias.",
                   ]), kind="aviso")

    # -- telas ----------------------------------------------------------------
    def show_login(self) -> None:
        self.user = None
        self._update_status()
        box = tk.LabelFrame(self.content, text=" Acesso ao Sistema ", font=FONT_BOLD,
                            bg=BG, padx=20, pady=16)
        box.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(box, text="Usuário:", font=FONT, bg=BG).grid(row=0, column=0, sticky="e", pady=4)
        user = entry(box, 24)
        user.grid(row=0, column=1, pady=4)
        tk.Label(box, text="Senha:", font=FONT, bg=BG).grid(row=1, column=0, sticky="e", pady=4)
        password = entry(box, 24, show="*")
        password.grid(row=1, column=1, pady=4)

        def do_login(_event=None) -> None:
            if (user.get(), password.get()) == (self.args.usuario, self.args.senha):
                self.user = user.get()
                self.navigate(self.show_menu)
            else:
                Dialog(self, "Erro de Acesso", "Usuário ou senha inválidos.", kind="erro")
                password.delete(0, "end")
                password.focus_set()

        button(box, "Entrar", do_login).grid(row=2, column=0, columnspan=2, pady=(12, 0))
        password.bind("<Return>", do_login)
        user.focus_set()

    def show_menu(self) -> None:
        box = tk.LabelFrame(self.content, text=" Menu Principal ", font=FONT_BOLD,
                            bg=BG, padx=24, pady=16)
        box.place(relx=0.5, rely=0.45, anchor="center")
        options = [
            ("Cadastro de Alunos", lambda: self.navigate(self.show_cadastro)),
            ("Consultar Alunos", self._not_available),
            ("Relatórios", self._not_available),
            ("Sair", lambda: self.navigate(self.show_login)),
        ]
        for i, (text, cmd) in enumerate(options):
            button(box, text, cmd, width=24).grid(row=i, column=0, pady=4)

    def _not_available(self) -> None:
        Dialog(self, "Indisponível", "Módulo não licenciado nesta estação.", kind="aviso")

    def show_cadastro(self) -> None:
        box = tk.LabelFrame(self.content, text=" Cadastro de Alunos ", font=FONT_BOLD,
                            bg=BG, padx=20, pady=14)
        box.place(relx=0.5, rely=0.47, anchor="center")

        labels = [
            ("nome", "Nome completo:", 40),
            ("cpf", "CPF:", 18),
            ("nascimento", "Nascimento (DD/MM/AAAA):", 14),
            ("turma", f"Turma ({TURMAS[0]} a {TURMAS[-1]}):", 6),
            ("responsavel", "Responsável:", 40),
            ("telefone", "Telefone:", 18),
        ]
        fields: dict[str, tk.Entry] = {}
        for row, (key, text, width) in enumerate(labels):
            tk.Label(box, text=text, font=FONT, bg=BG).grid(row=row, column=0, sticky="e",
                                                            padx=(0, 8), pady=4)
            fields[key] = entry(box, width)
            fields[key].grid(row=row, column=1, sticky="w", pady=4)

        def clear() -> None:
            for field in fields.values():
                field.delete(0, "end")
            fields["nome"].focus_set()

        def save() -> None:
            data = {k: f.get().strip() for k, f in fields.items()}
            error = self._validate(data)
            if error:
                Dialog(self, "Erro de Validação", error, kind="erro")
                return
            data["cpf"] = only_digits(data["cpf"])
            data["telefone"] = only_digits(data["telefone"])
            data["turma"] = data["turma"].upper()
            code = self.db.insert(data)
            self._update_status()
            Dialog(self, "Sucesso", f"Aluno cadastrado com sucesso!\nCódigo: {code}")
            clear()
            self._maybe_chaos()

        actions = tk.Frame(box, bg=BG)
        actions.grid(row=len(labels), column=0, columnspan=2, pady=(14, 0))
        button(actions, "Salvar", save).pack(side="left", padx=4)
        button(actions, "Limpar", clear).pack(side="left", padx=4)
        button(actions, "Voltar", lambda: self.navigate(self.show_menu)).pack(side="left", padx=4)

        self.bind("<F2>", lambda _e: save())
        fields["nome"].focus_set()

    def _validate(self, data: dict) -> str | None:
        if len(data["nome"]) < 3:
            return "Campo 'Nome completo' é obrigatório."
        if not is_valid_cpf(data["cpf"]):
            return "CPF inválido."
        if self.db.cpf_exists(only_digits(data["cpf"])):
            return "CPF já cadastrado no sistema."
        if parse_birth_date(data["nascimento"]) is None:
            return "Data de nascimento inválida. Use o formato DD/MM/AAAA."
        if data["turma"].upper() not in TURMAS:
            return f"Turma inexistente. Turmas válidas: {', '.join(TURMAS)}."
        if len(data["responsavel"]) < 3:
            return "Campo 'Responsável' é obrigatório."
        if len(only_digits(data["telefone"])) not in (10, 11):
            return "Telefone inválido. Informe DDD + número."
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SisEscola 98 — sistema legado fictício")
    parser.add_argument("--usuario", default="admin")
    parser.add_argument("--senha", default="admin")
    parser.add_argument("--db", default=str(Path(__file__).with_name("db.csv")),
                        help="arquivo CSV onde os registros são gravados")
    parser.add_argument("--lentidao-min", type=float, default=0.3,
                        help="atraso mínimo (s) ao trocar de tela")
    parser.add_argument("--lentidao-max", type=float, default=1.5,
                        help="atraso máximo (s) ao trocar de tela")
    parser.add_argument("--chaos", type=float, default=0.0,
                        help="probabilidade (0-1) de surgir um pop-up inesperado")
    return parser.parse_args()


if __name__ == "__main__":
    make_dpi_aware()
    FakeERP(parse_args()).mainloop()
