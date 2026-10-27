from pathlib import Path

import pytest

from sera.prompt import carregar_personality

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def personality():
    return carregar_personality(RAIZ / "personality.yaml")
