"""Garante que cada template é encontrado nas telas certas e SOMENTE nelas.

Usa os prints de tests/fixtures/screens (gerados por
scripts/capturar_templates.py), então roda sem abrir o app e sem mexer no
mouse/teclado. Se um template novo "vazar" para outra tela (falso positivo),
este teste falha antes de o robô clicar no lugar errado.
"""

from pathlib import Path

import pytest
from PIL import Image

from src.core.config import load_settings
from src.core.vision import Vision
from src.screens.base import FIELD_CLICK_OFFSET

ROOT = Path(__file__).resolve().parent.parent
SCREENS_DIR = ROOT / "tests" / "fixtures" / "screens"

SCREENS = ["login", "carregando", "menu", "dialogo_aviso", "cadastro",
           "cadastro_preenchido", "dialogo_erro", "dialogo_sucesso"]
CADASTRO = {"cadastro", "cadastro_preenchido"}
CADASTRO_COM_DIALOGO = CADASTRO | {"dialogo_erro", "dialogo_sucesso"}

# template -> telas em que ele DEVE aparecer (em todas as outras, não pode)
EXPECTED: dict[str, set[str]] = {
    "app_cabecalho": set(SCREENS),
    "login_campo_usuario": {"login"},
    "login_campo_senha": {"login"},
    "login_btn_entrar": {"login"},
    "carregando": {"carregando"},
    "menu_btn_cadastro": {"menu"},
    "cadastro_campo_nome": CADASTRO_COM_DIALOGO,
    "cadastro_campo_cpf": CADASTRO,  # coberto pelos diálogos
    "cadastro_campo_nascimento": CADASTRO | {"dialogo_erro"},
    "cadastro_campo_turma": CADASTRO | {"dialogo_erro"},
    "cadastro_campo_responsavel": CADASTRO | {"dialogo_erro"},
    "cadastro_campo_telefone": CADASTRO | {"dialogo_erro"},
    "cadastro_btn_salvar": CADASTRO_COM_DIALOGO,
    "cadastro_btn_voltar": CADASTRO_COM_DIALOGO,
    "dlg_icone_info": {"dialogo_sucesso"},
    "dlg_icone_erro": {"dialogo_erro"},
    "dlg_icone_aviso": {"dialogo_aviso"},
    "dlg_btn_ok": {"dialogo_aviso", "dialogo_erro", "dialogo_sucesso"},
}


@pytest.fixture(scope="module")
def vision() -> Vision:
    cfg = load_settings(ROOT / "config" / "settings.example.yaml").vision
    return Vision(cfg.templates_dir, confidence=cfg.confidence, grayscale=cfg.grayscale)


@pytest.fixture(scope="module")
def screens() -> dict[str, Image.Image]:
    return {name: Image.open(SCREENS_DIR / f"{name}.png").convert("RGB") for name in SCREENS}


def test_every_template_file_is_covered():
    files = {p.stem for p in (ROOT / "assets" / "templates").glob("*.png")}
    assert files == set(EXPECTED), "atualize EXPECTED ao criar/remover templates"


@pytest.mark.parametrize("template", sorted(EXPECTED))
def test_template_found_only_on_expected_screens(vision, screens, template):
    found = {name for name, img in screens.items() if vision.find(template, haystack=img)}
    assert found == EXPECTED[template]


FIELDS_BY_SCREEN = {
    "login": ["login_campo_usuario", "login_campo_senha"],
    "cadastro": [f"cadastro_campo_{f}" for f in
                 ("nome", "cpf", "nascimento", "turma", "responsavel", "telefone")],
}


@pytest.mark.parametrize("screen, template",
                         [(s, t) for s, names in FIELDS_BY_SCREEN.items() for t in names])
def test_field_click_point_lands_inside_the_input(vision, screens, screen, template):
    """O robô clica à direita do rótulo: o ponto precisa cair no campo BRANCO."""
    match = vision.find(template, haystack=screens[screen])
    x, y = match.point(dx=FIELD_CLICK_OFFSET, anchor="right")
    assert screens[screen].getpixel((x, y)) == (255, 255, 255)
