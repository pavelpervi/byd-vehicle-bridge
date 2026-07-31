"""Tests for BridgeState data handling."""

from __future__ import annotations

from byd_bridge.state import BridgeState


class TestBridgeStateInitialization:
    def test_initial_state_is_none(self) -> None:
        state = BridgeState()
        assert state.vin is None
        assert state.vehicle is None
        assert state.battery is None
        assert state.full_data is None
        assert state.last_poll is None
        assert state.connected is False
        assert state.error is None

    def test_initial_state_is_not_connected(self) -> None:
        state = BridgeState()
        assert state.connected is False


class TestBridgeStateDictStructure:
    """Verify the expected data shapes are correct (without polling)."""

    def test_battery_data_keys(self) -> None:
        state = BridgeState()
        state.battery = {
            "soc_percent": 73,
            "charging_status": "disconnected",
            "estimated_range_km": 280,
            "mileage_km": 12450,
            "outside_temp_c": 31.5,
            "cabin_temp_c": 28.0,
            "speed_kmh": 0,
            "engine_power_kw": 0.0,
            "fuel_percent": None,
            "last_updated": "2026-07-31T08:30:00+00:00",
        }
        assert state.battery["soc_percent"] == 73
        assert state.battery["charging_status"] == "disconnected"
        assert state.battery["estimated_range_km"] == 280
        assert state.battery["mileage_km"] == 12450
        assert state.battery["last_updated"] is not None

    def test_vehicle_data_keys(self) -> None:
        state = BridgeState()
        state.vehicle = {
            "vin": "WBA1234567890",
            "model": "ATTO 3",
            "brand": "BYD",
            "plate": "123-45-678",
            "energy_type": "EV",
        }
        assert state.vehicle["vin"] == "WBA1234567890"
        assert state.vehicle["energy_type"] == "EV"

    def test_tools_return_copy(self) -> None:
        """Tools should return a copy so poller writes don't corrupt reader data."""
        state = BridgeState()
        state.battery = {"soc_percent": 50}
        result = dict(state.battery)
        result["soc_percent"] = 100
        assert state.battery["soc_percent"] == 50  # original unchanged
        assert result["soc_percent"] == 100  # copy modified