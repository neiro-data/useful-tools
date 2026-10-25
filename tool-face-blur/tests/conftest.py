from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def face_path() -> Path:
    return FIXTURES / "face.jpg"


@pytest.fixture
def face_rotated_path() -> Path:
    return FIXTURES / "face_rotated.jpg"


@pytest.fixture
def face_bytes(face_path: Path) -> bytes:
    return face_path.read_bytes()


@pytest.fixture
def noise() -> NDArray[np.uint8]:
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(120, 160, 3), dtype=np.uint8)
