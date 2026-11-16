import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core import safety  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_stop_flag():
    """Garante que a parada de emergência de um teste não vaze para outro."""
    safety.reset_stop()
    yield
    safety.reset_stop()
