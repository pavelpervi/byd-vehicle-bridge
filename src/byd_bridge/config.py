"""Configuration from environment variables."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _validate_mode(mode: str) -> str:
    """Validate and normalize bridge mode."""
    mode = mode.strip().lower()
    if mode not in ("minimal", "full"):
        import logging

        logging.getLogger("byd-bridge").warning(
            "Unknown BYD_MODE=%r, falling back to 'minimal'", mode
        )
        return "minimal"
    return mode


class Settings:
    """Immutable configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.username: str = os.environ["BYD_USERNAME"]
        self.password: str = os.environ["BYD_PASSWORD"]
        self.country_code: str = os.environ.get("BYD_COUNTRY", "IL")
        self.language: str = os.environ.get("BYD_LANG", "en")
        self.time_zone: str = os.environ.get("TZ", "Asia/Jerusalem")
        self.mode: str = _validate_mode(os.environ.get("BYD_MODE", "minimal"))
        self.poll_interval: int = int(os.environ.get("POLL_INTERVAL", "60"))
        self.port: int = int(os.environ.get("BYD_PORT", "8000"))


class _LazySettings:
    """Lazy singleton — only creates Settings when first accessed."""

    _instance: Settings | None = None

    def __getattr__(self, name: str) -> Any:
        if self._instance is None:
            self._instance = Settings()
        return getattr(self._instance, name)


# Lazy singleton — won't fail on import without env vars
settings = _LazySettings()
