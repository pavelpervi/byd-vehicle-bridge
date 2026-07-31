"""Tests for configuration parsing."""

from __future__ import annotations

import pytest

from byd_bridge.config import Settings, _validate_mode


class TestValidateMode:
    @pytest.mark.parametrize("mode", ["minimal", "full"])
    def test_valid_modes(self, mode: str) -> None:
        assert _validate_mode(mode) == mode

    @pytest.mark.parametrize("mode", ["MINIMAL", "  full  ", "Full"])
    def test_mode_normalization(self, mode: str) -> None:
        assert _validate_mode(mode) in ("minimal", "full")

    @pytest.mark.parametrize("mode", ["", "everything", "readwrite", "None"])
    def test_invalid_modes_fall_back_to_minimal(self, mode: str) -> None:
        assert _validate_mode(mode) == "minimal"


class TestSettings:
    def test_defaults(self, minimal_env, monkeypatch: pytest.MonkeyPatch) -> None:
        # Remove optional env vars to test defaults
        monkeypatch.delenv("POLL_INTERVAL", raising=False)
        monkeypatch.delenv("BYD_PORT", raising=False)
        monkeypatch.delenv("BYD_LANG", raising=False)
        monkeypatch.delenv("BYD_COUNTRY", raising=False)
        monkeypatch.delenv("TZ", raising=False)

        settings = Settings()
        assert settings.username == "test@example.com"
        assert settings.password == "test-password"
        assert settings.country_code == "IL"
        assert settings.language == "en"
        assert settings.time_zone == "Asia/Jerusalem"
        assert settings.mode == "minimal"
        assert settings.poll_interval == 60
        assert settings.port == 8000

    def test_full_mode_env(self, full_env) -> None:
        settings = Settings()
        assert settings.mode == "full"
        assert settings.poll_interval == 30
        assert settings.port == 9000

    def test_missing_credentials_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BYD_USERNAME", raising=False)
        monkeypatch.delenv("BYD_PASSWORD", raising=False)
        with pytest.raises(KeyError):
            Settings()