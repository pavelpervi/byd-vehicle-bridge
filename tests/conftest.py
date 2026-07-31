"""Shared test fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure src/ is importable
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a minimal valid environment for the bridge."""
    monkeypatch.setenv("BYD_USERNAME", "test@example.com")
    monkeypatch.setenv("BYD_PASSWORD", "test-password")
    monkeypatch.setenv("BYD_COUNTRY", "IL")
    monkeypatch.setenv("BYD_MODE", "minimal")


@pytest.fixture
def full_env(minimal_env, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment for full mode."""
    monkeypatch.setenv("BYD_MODE", "full")
    monkeypatch.setenv("POLL_INTERVAL", "30")
    monkeypatch.setenv("BYD_PORT", "9000")