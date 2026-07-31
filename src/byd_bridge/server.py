"""MCP server — tools exposed to AI agents."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.types import Tool, TextContent, CallToolResult

from byd_bridge.config import settings
from byd_bridge.state import state


def _make_text_result(text: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)])


def _data_or_error(data: dict[str, Any] | None, error_msg: str) -> CallToolResult:
    if data is None:
        return _make_text_result(error_msg)
    import json
    return _make_text_result(json.dumps(data, indent=2, default=str))


# Create the MCP server
mcp = MCPServer(
    name="BYD Vehicle Bridge",
    title="BYD Vehicle Bridge",
    instructions=(
        "MCP server for BYD electric vehicle data. "
        "Use get_battery() for SOC and driving basics. "
        "Use get_all_data() for full telemetry. "
        "Use get_health() to check current mode and connection status."
    ),
    version="1.0.0",
)


@mcp.tool(
    name="get_battery",
    description="Get battery SOC, charging status, estimated range, and driving data.",
)
def get_battery() -> CallToolResult:
    """Get battery SOC, charging status, estimated range, and driving data."""
    return _data_or_error(state.battery, "No data yet — bridge is still polling. Try again shortly.")


@mcp.tool(
    name="get_vehicle",
    description="Get vehicle identification and model information (VIN, model, brand, plate, energy type).",
)
def get_vehicle() -> CallToolResult:
    """Get vehicle identification and model information."""
    return _data_or_error(state.vehicle, "No vehicle data yet. Try again shortly.")


@mcp.tool(
    name="get_all_data",
    description="Get all available data. In 'minimal' mode: battery + vehicle. In 'full' mode: also GPS, tires, doors, windows, HVAC, charging details.",
)
def get_all_data() -> CallToolResult:
    """Get all telemetry data in one call. Mode-dependent."""
    return _data_or_error(state.full_data, "Bridge not yet initialized. Try again shortly.")


@mcp.tool(
    name="get_health",
    description="Check the bridge health: connection status, mode, last poll time, and poll interval.",
)
def get_health() -> CallToolResult:
    """Get bridge health status."""
    import json
    return _make_text_result(json.dumps({
        "status": "ok" if state.connected else "degraded",
        "mode": settings.mode,
        "vehicle_connected": state.connected,
        "last_successful_poll": state.last_poll,
        "poll_interval_s": settings.poll_interval,
        "error": state.error,
    }, indent=2, default=str))
