"""BYD Vehicle Bridge — MCP Server for BYD car data.

Connects to the BYD cloud API via pyBYD, polls vehicle data in the background,
and exposes it through MCP (Model Context Protocol) tools.

Modes:
  minimal — Battery SOC, range, driving basics (default). No GPS, no doors.
  full    — All read-only data: GPS, tires, doors, windows, HVAC, charging.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pybyd import BydClient, BydConfig

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_logger = logging.getLogger("byd-bridge")

# ── Config ──────────────────────────────────────────────────────────────

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
BRIDGE_MODE = os.getenv("BYD_MODE", "minimal").strip().lower()
BYD_PORT = int(os.getenv("BYD_PORT", "8000"))

if BRIDGE_MODE not in ("minimal", "full"):
    _logger.warning("Unknown BYD_MODE=%r, falling back to 'minimal'", BRIDGE_MODE)
    BRIDGE_MODE = "minimal"


# ── Bridge State ────────────────────────────────────────────────────────

class BridgeState:
    """Holds the latest cached vehicle data, populated by a background poller."""

    def __init__(self) -> None:
        self.vin: str | None = None
        self.vehicle: dict[str, Any] | None = None
        self.battery: dict[str, Any] | None = None
        self.full_data: dict[str, Any] | None = None
        self.last_poll: str | None = None
        self.connected: bool = False
        self.error: str | None = None
    async def update(self) -> None:
        """Poll the BYD API and update cached state."""
        config = BydConfig(
            username=os.environ["BYD_USERNAME"],
            password=os.environ["BYD_PASSWORD"],
            country_code=os.environ.get("BYD_COUNTRY", "IL"),
            language=os.environ.get("BYD_LANG", "en"),
            time_zone=os.environ.get("TZ", "Asia/Jerusalem"),
        )

        try:
            async with BydClient(config) as client:
                # ── Vehicles ────────────────────────────────────────
                vehicles = await client.get_vehicles()
                if not vehicles:
                    self.error = "No vehicles found on account"
                    self.connected = False
                    _logger.warning(self.error)
                    return

                car = vehicles[0]
                vin = car.vin
                self.vin = vin

                self.vehicle = {
                    "vin": vin,
                    "model": getattr(car, "model_name", None) or getattr(car, "model", None),
                    "brand": getattr(car, "brand_name", None) or getattr(car, "brand", None),
                    "plate": getattr(car, "auto_plate", None) or getattr(car, "license_plate", None),
                    "energy_type": str(getattr(car, "energy_type", "") or ""),
                    "total_mileage": getattr(car, "total_mileage", None),
                }

                # ── Realtime data (always) ──────────────────────────
                realtime = await client.get_vehicle_realtime(vin)

                online_state = getattr(realtime, "online_state", None)
                if online_state is not None:
                    self.vehicle["online_state"] = str(online_state)

                self.battery = {
                    "soc_percent": realtime.elec_percent,
                    "charging_status": str(getattr(realtime, "charging_status", "") or ""),
                    "estimated_range_km": getattr(realtime, "elec_range", None),
                    "mileage_km": getattr(realtime, "mileage", None),
                    "outside_temp_c": getattr(realtime, "outside_temp", None),
                    "cabin_temp_c": getattr(realtime, "cabin_temp", None),
                    "speed_kmh": getattr(realtime, "speed", None),
                    "engine_power_kw": getattr(realtime, "engine_power", None),
                    "fuel_percent": getattr(realtime, "fuel_percent", None),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }

                # ── Full-mode data ──────────────────────────────────
                if BRIDGE_MODE == "full":
                    extras = await self._collect_full_data(client, vin, realtime)
                else:
                    extras = {}

                self.full_data = {
                    "vehicle": self.vehicle,
                    "battery": self.battery,
                    **extras,
                    "last_poll": datetime.now(timezone.utc).isoformat(),
                    "mode": BRIDGE_MODE,
                }

                self.last_poll = datetime.now(timezone.utc).isoformat()
                self.error = None
                self.connected = True
                _logger.info(
                    "Polled OK — VIN=...%s SOC=%d%% Mode=%s",
                    vin[-4:],
                    self.battery["soc_percent"],
                    BRIDGE_MODE,
                )

        except Exception as exc:
            self.connected = False
            self.error = str(exc)
            _logger.error("Poll failed: %s", exc)

    async def _collect_full_data(
        self,
        client: BydClient,
        vin: str,
        realtime: Any,
    ) -> dict[str, Any]:
        """Collect all additional read-only data for full mode."""
        extras: dict[str, Any] = {}

        # ── Tires ──────────────────────────────────────────────────
        extras["tires"] = {
            "left_front_bar": getattr(realtime, "left_front_tire_pressure", None),
            "right_front_bar": getattr(realtime, "right_front_tire_pressure", None),
            "left_rear_bar": getattr(realtime, "left_rear_tire_pressure", None),
            "right_rear_bar": getattr(realtime, "right_rear_tire_pressure", None),
            "unit": str(getattr(realtime, "tire_pressure_unit", "") or ""),
        }

        # ── Doors ──────────────────────────────────────────────────
        extras["doors"] = {
            "left_front_door": str(getattr(realtime, "left_front_door", "") or ""),
            "right_front_door": str(getattr(realtime, "right_front_door", "") or ""),
            "left_rear_door": str(getattr(realtime, "left_rear_door", "") or ""),
            "right_rear_door": str(getattr(realtime, "right_rear_door", "") or ""),
            "trunk": str(getattr(realtime, "trunk", "") or ""),
            "hood": str(getattr(realtime, "hood", "") or ""),
            "lock_state": str(getattr(realtime, "lock_state", "") or ""),
        }

        # ── Windows ────────────────────────────────────────────────
        extras["windows"] = {
            "left_front_window": str(getattr(realtime, "left_front_window", "") or ""),
            "right_front_window": str(getattr(realtime, "right_front_window", "") or ""),
            "left_rear_window": str(getattr(realtime, "left_rear_window", "") or ""),
            "right_rear_window": str(getattr(realtime, "right_rear_window", "") or ""),
            "sunroof": str(getattr(realtime, "sunroof", "") or ""),
        }

        # ── Charging details ───────────────────────────────────────
        try:
            charging = await client.get_charging_status(vin)
            extras["charging_details"] = {
                "charge_rate_kw": getattr(charging, "charge_rate_kw", None),
                "charging_voltage_v": getattr(charging, "charging_voltage_v", None),
                "charging_current_a": getattr(charging, "charging_current_a", None),
                "time_to_full_min": getattr(charging, "time_to_full_min", None),
                "charge_limit_percent": getattr(charging, "charge_limit_percent", None),
                "plug_connected": getattr(charging, "plug_connected", None),
            }
        except Exception as exc:
            _logger.warning("Charging details unavailable: %s", exc)

        # ── GPS ────────────────────────────────────────────────────
        try:
            gps = await client.get_gps_info(vin)
            extras["gps"] = {
                "latitude": getattr(gps, "latitude", None),
                "longitude": getattr(gps, "longitude", None),
                "heading": getattr(gps, "direction", None),
                "gps_speed_kmh": getattr(gps, "speed", None),
            }
        except Exception as exc:
            _logger.warning("GPS data unavailable: %s", exc)

        # ── HVAC ───────────────────────────────────────────────────
        try:
            hvac = await client.get_hvac_status(vin)
            extras["hvac"] = {
                "ac_on": getattr(hvac, "ac_on", None),
                "target_temp_c": getattr(hvac, "target_temp", None),
                "fan_speed": getattr(hvac, "fan_speed", None),
                "front_defrost": getattr(hvac, "front_defrost", None),
                "rear_defrost": getattr(hvac, "rear_defrost", None),
            }
        except Exception as exc:
            _logger.warning("HVAC data unavailable: %s", exc)

        return extras


# ── Global State ────────────────────────────────────────────────────────

state = BridgeState()


# ── Background Poller ──────────────────────────────────────────────────

async def poller_loop() -> None:
    """Continuously poll BYD API at POLL_INTERVAL."""
    await state.update()
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        await state.update()


def _run_poller_in_thread() -> None:
    """Run the async poller loop in a daemon thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poller_loop())


# Start the background poller immediately when the module loads
poller_thread = threading.Thread(target=_run_poller_in_thread, daemon=True)
poller_thread.start()


# ── MCP Server ─────────────────────────────────────────────────────────

mcp = FastMCP(
    "BYD Vehicle Bridge",
    instructions=(
        "MCP server for BYD electric vehicle data. "
        f"Current mode: {BRIDGE_MODE}. "
        "Use get_battery() for SOC and driving basics in any mode. "
        "Use get_all_data() for full telemetry in 'full' mode."
    ),
)


@mcp.tool(description="Get the battery state of charge and driving data (SOC %, charging status, range, mileage, temps, speed, power). Always available.")
def get_battery() -> dict[str, Any]:
    """Get battery SOC, charging status, estimated range, and driving data."""
    if state.battery is None:
        return {"error": "No data yet — bridge is still polling. Try again shortly."}
    return dict(state.battery)


@mcp.tool(description="Get vehicle information (VIN, model, brand, plate, energy type). Always available.")
def get_vehicle() -> dict[str, Any]:
    """Get vehicle identification and model information."""
    if state.vehicle is None:
        return {"error": "No vehicle data yet. Try again shortly."}
    return dict(state.vehicle)


@mcp.tool(description="Get all available data. In 'minimal' mode: battery + vehicle. In 'full' mode: also GPS, tires, doors, windows, HVAC, charging details.")
def get_all_data() -> dict[str, Any]:
    """Get all telemetry data in one call. Mode-dependent."""
    if state.full_data is None:
        return {"error": "Bridge not yet initialized. Try again shortly."}
    return dict(state.full_data)


@mcp.tool(description="Check the bridge health: connection status, mode, last poll time, and poll interval.")
def get_health() -> dict[str, Any]:
    """Get bridge health status."""
    return {
        "status": "ok" if state.connected else "degraded",
        "mode": BRIDGE_MODE,
        "vehicle_connected": state.connected,
        "last_successful_poll": state.last_poll,
        "poll_interval_s": POLL_INTERVAL,
        "error": state.error,
    }


# ── Entrypoint ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    _logger.info(
        "Starting BYD bridge MCP server — mode=%s poll_interval=%ds",
        BRIDGE_MODE,
        POLL_INTERVAL,
    )
    mcp.run(transport="sse")