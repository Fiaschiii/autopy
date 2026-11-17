"""Gravação da execução em GIF (para documentação e demonstração).

Detalhes:
  * grava SOMENTE a área da janela do sistema-alvo, nunca a tela inteira
    (notificações e outros programas do usuário ficam fora do vídeo);
  * `pyautogui.screenshot()` não captura o ponteiro do mouse, então ele é
    desenhado em cada quadro a partir de `pyautogui.position()`;
  * quadros idênticos consecutivos são fundidos (só a duração aumenta),
    o que reduz bastante o tamanho do GIF.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pyautogui
from PIL import Image, ImageDraw

log = logging.getLogger(__name__)

Region = tuple[int, int, int, int]

# Seta do mouse (pontos relativos à ponta)
CURSOR = [(0, 0), (0, 17), (4, 13), (7, 20), (10, 19), (7, 12), (12, 12)]


@dataclass
class Frame:
    image: Image.Image   # já reduzido e com paleta (modo "P")
    duration_ms: int


def draw_cursor(img: Image.Image, x: int, y: int) -> None:
    if 0 <= x < img.width and 0 <= y < img.height:
        ImageDraw.Draw(img).polygon([(x + dx, y + dy) for dx, dy in CURSOR],
                                    fill="black", outline="white")


def merge_identical(frames: list[Frame]) -> list[Frame]:
    merged: list[Frame] = []
    for frame in frames:
        if merged and merged[-1].image.tobytes() == frame.image.tobytes():
            merged[-1].duration_ms += frame.duration_ms
        else:
            merged.append(Frame(frame.image, frame.duration_ms))
    return merged


class ScreenRecorder:
    def __init__(self, region: Callable[[], Region], fps: float = 6,
                 max_width: int = 640, max_seconds: float = 600) -> None:
        self.region = region
        self.interval = 1 / fps
        self.max_width = max_width
        self.max_seconds = max_seconds
        self.frames: list[Frame] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _capture(self) -> Image.Image:
        left, top, width, height = self.region()
        img = pyautogui.screenshot(region=(left, top, width, height))
        mx, my = pyautogui.position()
        draw_cursor(img, mx - left, my - top)
        if img.width > self.max_width:
            ratio = self.max_width / img.width
            img = img.resize((self.max_width, round(img.height * ratio)), Image.LANCZOS)
        return img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)

    def _loop(self) -> None:
        start = last = time.monotonic()
        image = None
        while not self._stop.is_set() and time.monotonic() - start < self.max_seconds:
            try:
                new_image = self._capture()
            except Exception as exc:  # janela fechando, etc.: não derruba o robô
                log.debug("Quadro ignorado: %s", exc)
                new_image = image
            now = time.monotonic()
            if image is not None:
                self.frames.append(Frame(image, int((now - last) * 1000)))
            image, last = new_image, now
            self._stop.wait(self.interval)
        if image is not None:
            self.frames.append(Frame(image, 1500))  # segura o último quadro no fim

    def start(self) -> "ScreenRecorder":
        self._thread = threading.Thread(target=self._loop, name="gravador", daemon=True)
        self._thread.start()
        log.info("🎥 Gravando a janela do sistema")
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def save_gif(self, path: Path) -> Path | None:
        frames = merge_identical(self.frames)
        if not frames:
            log.warning("Nenhum quadro gravado")
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        first, *rest = frames
        first.image.save(path, save_all=True, append_images=[f.image for f in rest],
                         duration=[f.duration_ms for f in frames], loop=0, optimize=True,
                         disposal=1)
        size_mb = path.stat().st_size / 1_048_576
        log.info("🎥 GIF salvo: %s (%d quadros, %.1f MB)", path, len(frames), size_mb)
        return path
