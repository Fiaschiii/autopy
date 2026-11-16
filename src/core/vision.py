"""Os "olhos" do robô: encontrar elementos na tela por reconhecimento de imagem.

Princípios:
  * nunca usar coordenadas fixas: tudo é localizado por imagem (templates);
  * nunca usar sleep fixo: esperar ATÉ o elemento aparecer (com timeout);
  * buscar só dentro da janela do sistema-alvo (mais rápido e sem falsos
    positivos em outros programas);
  * tolerância a pequenas variações de pixel com `confidence` (OpenCV).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyautogui
import pyscreeze
from PIL import Image

from .exceptions import ElementNotFoundError, TemplateNotFoundError
from .safety import check_stop, interruptible_sleep
from .window import AppWindow, Region

log = logging.getLogger(__name__)

_NOT_FOUND = (pyautogui.ImageNotFoundException, pyscreeze.ImageNotFoundException)


@dataclass(frozen=True)
class Match:
    """Elemento encontrado na tela."""

    name: str
    left: int
    top: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return self.left + self.width // 2, self.top + self.height // 2

    @property
    def right(self) -> int:
        return self.left + self.width

    def point(self, dx: int = 0, dy: int = 0, anchor: str = "center") -> tuple[int, int]:
        """Ponto relativo ao elemento. anchor: 'center' ou 'right' (borda direita).

        Útil para clicar em um campo a partir do rótulo ao lado dele.
        """
        x, y = self.center
        if anchor == "right":
            x = self.right
        return x + dx, y + dy


class Vision:
    def __init__(self, templates_dir: Path, *, confidence: float = 0.85,
                 grayscale: bool = True, timeout: float = 15,
                 poll_interval: float = 0.25, window: AppWindow | None = None) -> None:
        self.templates_dir = Path(templates_dir)
        self.confidence = confidence
        self.grayscale = grayscale
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.window = window
        self._cache: dict[str, Image.Image] = {}

    # -- templates ------------------------------------------------------------
    def template(self, name: str) -> Image.Image:
        """Carrega (uma única vez) a imagem de referência `<name>.png`."""
        if name not in self._cache:
            path = self.templates_dir / f"{name}.png"
            if not path.exists():
                raise TemplateNotFoundError(f"Template inexistente: {path}")
            with Image.open(path) as img:
                self._cache[name] = img.convert("RGB")
        return self._cache[name]

    def _region(self) -> Region | None:
        return self.window.region() if self.window else None

    # -- busca ----------------------------------------------------------------
    def find(self, name: str, *, confidence: float | None = None,
             haystack: Image.Image | None = None) -> Match | None:
        """Procura o elemento UMA vez. Retorna Match ou None.

        `haystack` permite procurar dentro de uma imagem em vez da tela
        (usado nos testes automatizados).
        """
        needle = self.template(name)
        options = {"confidence": confidence or self.confidence, "grayscale": self.grayscale}
        try:
            if haystack is not None:
                box = pyautogui.locate(needle, haystack, **options)
            else:
                box = pyautogui.locateOnScreen(needle, region=self._region(), **options)
        except _NOT_FOUND:
            return None
        if box is None:
            return None
        return Match(name, int(box.left), int(box.top), int(box.width), int(box.height))

    def exists(self, name: str, **kwargs) -> bool:
        return self.find(name, **kwargs) is not None

    def wait_for(self, name: str, timeout: float | None = None) -> Match:
        """Espera o elemento aparecer. Levanta ElementNotFoundError no timeout."""
        return self.wait_for_any(name, timeout=timeout)[1]

    def wait_for_any(self, *names: str, timeout: float | None = None) -> tuple[str, Match]:
        """Espera QUALQUER um dos elementos aparecer e diz qual apareceu.

        Ex.: depois de clicar em "Salvar", esperar o diálogo de sucesso OU o
        de erro, e reagir conforme o resultado.
        """
        timeout = self.timeout if timeout is None else timeout
        start = time.monotonic()
        while True:
            check_stop()
            for name in names:
                match = self.find(name)
                if match:
                    log.debug("'%s' encontrado em %.2fs em %s", name,
                              time.monotonic() - start, match.center)
                    return name, match
            if time.monotonic() - start >= timeout:
                raise ElementNotFoundError(
                    f"Nenhum de {list(names)} apareceu em {timeout:.1f}s")
            interruptible_sleep(self.poll_interval)

    def wait_until_gone(self, name: str, timeout: float | None = None) -> None:
        """Espera o elemento SUMIR (ex.: a tela "Carregando...")."""
        timeout = self.timeout if timeout is None else timeout
        start = time.monotonic()
        while self.exists(name):
            check_stop()
            if time.monotonic() - start >= timeout:
                raise ElementNotFoundError(f"'{name}' não sumiu em {timeout:.1f}s")
            interruptible_sleep(self.poll_interval)

    # -- evidências -----------------------------------------------------------
    def screenshot(self, directory: Path, label: str = "tela") -> Path:
        """Salva um print da janela (ou da tela inteira) para diagnóstico."""
        directory.mkdir(parents=True, exist_ok=True)
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        path = directory / f"{datetime.now():%Y%m%d_%H%M%S_%f}_{safe_label}.png"
        try:
            region = self._region()
        except Exception:  # janela pode ter fechado; captura a tela inteira
            region = None
        pyautogui.screenshot(str(path), region=region)
        log.info("📸 Print salvo: %s", path)
        return path
