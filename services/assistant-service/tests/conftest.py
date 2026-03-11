import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure project root (assistant-service folder) is in sys.path
ROOT = Path(__file__).resolve().parents[1]  # services/assistant-service
sys.path.insert(0, str(ROOT))

# Use local redis by default (docker exposed port)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from src.main import app  # ✅ matches uvicorn src.main:app


@pytest.fixture()
def client():
    return TestClient(app)