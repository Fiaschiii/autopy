"""Nova tentativa com espera exponencial (backoff)."""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

from .exceptions import RobotError, RobotStopped
from .safety import interruptible_sleep

log = logging.getLogger(__name__)

T = TypeVar("T")


def retry_call(func: Callable[[], T], *, max_attempts: int = 3,
               backoff_seconds: float = 1.0,
               exceptions: tuple[type[BaseException], ...] = (RobotError,),
               on_retry: Callable[[int, BaseException], None] | None = None) -> T:
    """Executa `func`; se falhar com uma das `exceptions`, tenta de novo.

    A espera entre tentativas dobra a cada falha (1s, 2s, 4s...). A parada de
    emergência (RobotStopped) nunca é re-tentada. `on_retry(tentativa, erro)`
    é chamado antes de cada nova tentativa, por exemplo para fechar um pop-up
    ou voltar o sistema a um estado conhecido.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts deve ser >= 1")
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except RobotStopped:
            raise
        except exceptions as exc:
            if attempt == max_attempts:
                log.error("Falhou após %d tentativa(s): %s", attempt, exc)
                raise
            wait = backoff_seconds * 2 ** (attempt - 1)
            log.warning("Tentativa %d/%d falhou (%s). Nova tentativa em %.1fs",
                        attempt, max_attempts, exc, wait)
            interruptible_sleep(wait)
            if on_retry:
                on_retry(attempt, exc)
    raise AssertionError("inalcançável")
