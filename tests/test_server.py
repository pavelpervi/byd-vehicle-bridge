"""Tests for MCP server tools."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set env vars before importing byd_bridge modules
os.environ["BYD_USERNAME"] = "test@example.com"
os.environ["BYD_PASSWORD"] = "test-password"
os.environ["BYD_COUNTRY"] = "IL"
os.environ["BYD_MODE"] = "minimal"

from byd_bridge.server import mcp
from byd_bridge.state import state


class TestToolsInitialState:
    """Tools should return graceful error messages when no data yet."""

    @pytest.mark.asyncio
    async def test_get_battery_before_poll(self) -> None:
        state.battery = None
        result = await mcp.call_tool("get_battery", {})
        text = result.content[0].text
        assert "No data yet" in text

    @pytest.mark.asyncio
    async def test_get_vehicle_before_poll(self) -> None:
        state.vehicle = None
        result = await mcp.call_tool("get_vehicle", {})
        text = result.content[0].text
        assert "No vehicle data yet" in text

    @pytest.mark.asyncio
    async def test_get_all_data_before_poll(self) -> None:
        state.full_data = None
        result = await mcp.call_tool("get_all_data", {})
        text = result.content[0].text
        assert "not yet initialized" in text

    @pytest.mark.asyncio
    async def test_get_health_always_returns(self) -> None:
        """Health should never fail, even before first poll."""
        result = await mcp.call_tool("get_health", {})
        data = json.loads(result.content[0].text)
        assert "status" in data
        assert "mode" in data
        assert data["mode"] in ("minimal", "full")


class TestToolsWithData:
    """Tools should return proper data after poller has populated state."""

    def setup_method(self) -> None:
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
        state.vehicle = {
            "vin": "WBA1234567890",
            "model": "ATTO 3",
            "brand": "BYD",
            "plate": "123-45-678",
            "energy_type": "EV",
            "total_mileage": 12450.0,
        }
        state.full_data = {
            "vehicle": state.vehicle,
            "battery": state.battery,
            "last_poll": "2026-07-31T08:30:00+00:00",
            "mode": "minimal",
        }
        state.connected = True
        state.last_poll = "2026-07-31T08:30:00+00:00"
        state.error = None

    @pytest.mark.asyncio
    async def test_get_battery_returns_data(self) -> None:
        result = await mcp.call_tool("get_battery", {})
        data = json.loads(result.content[0].text)
        assert data["soc_percent"] == 73
        assert data["charging_status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_get_vehicle_returns_data(self) -> None:
        result = await mcp.call_tool("get_vehicle", {})
        data = json.loads(result.content[0].text)
        assert data["vin"] == "WBA1234567890"
        assert data["model"] == "ATTO 3"

    @pytest.mark.asyncio
    async def test_get_all_data_returns_full(self) -> None:
        result = await mcp.call_tool("get_all_data", {})
        data = json.loads(result.content[0].text)
        assert "battery" in data
        assert "vehicle" in data
        assert data["battery"]["soc_percent"] == 73

    @pytest.mark.asyncio
    async def test_get_health_ok(self) -> None:
        result = await mcp.call_tool("get_health", {})
        data = json.loads(result.content[0].text)
        assert data["status"] == "ok"
        assert data["vehicle_connected"] is True
        assert data["last_successful_poll"] is not None


class TestMcpServerRegistration:
    """Verify the MCP server is properly configured."""

    def test_server_name(self) -> None:
        assert mcp.name == "BYD Vehicle Bridge"

    @pytest.mark.asyncio
    async def test_tool_list(self) -> None:
        """Verify all expected tools are registered."""
        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}
        assert "get_battery" in tool_names
        assert "get_vehicle" in tool_names
        assert "get_all_data" in tool_names
        assert "get_health" in tool_names

    @pytest.mark.asyncio
    async def test_tool_descriptions_not_empty(self) -> None:
        tools = await mcp.list_tools()
        for tool in tools:
            assert tool.description, f"Tool '{tool.name}' has no description"
