"""Bridge state — holds cached vehicle data and background poller."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from pybyd import BydClient, BydConfig

from byd_bridge.config import settings

_logger = logging.getLogger("byd-bridge")


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
            username=settings.username,
            password=settings.password,
            country_code=settings.country_code,
            language=settings.language,
            time_zone=settings.time_zone,
        )

        try:
            async with BydClient(config) as client:
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

                extras = await self._collect_full_data(client, vin, realtime) if settings.mode == "full" else {}

                self.full_data = {
                    "vehicle": self.vehicle,
                    "battery": self.battery,
                    **extras,
                    "last_poll": datetime.now(timezone.utc).isoformat(),
                    "mode": settings.mode,
                }

                self.last_poll = datetime.now(timezone.utc).isoformat()
                self.error = None
                self.connected = True
                _logger.info(
                    "Polled OK — VIN=...%s SOC=%d%% Mode=%s",
                    vin[-4:],
                    self.battery["soc_percent"],
                    settings.mode,
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

        extras["tires"] = {
            "left_front_bar": getattr(realtime, "left_front_tire_pressure", None),
            "right_front_bar": getattr(realtime, "right_front_tire_pressure", None),
            "left_rear_bar": getattr(realtime, "left_rear_tire_pressure", None),
            "right_rear_bar": getattr(realtime, "right_rear_tire_pressure", None),
            "unit": str(getattr(realtime, "tire_pressure_unit", "") or ""),
        }

        extras["doors"] = {
            "left_front_door": str(getattr(realtime, "left_front_door", "") or ""),
            "right_front_door": str(getattr(realtime, "right_front_door", "") or ""),
            "left_rear_door": str(getattr(realtime, "left_rear_door", "") or ""),
            "right_rear_door": str(getattr(realtime, "right_rear_door", "") or ""),
            "trunk": str(getattr(realtime, "trunk", "") or ""),
            "hood": str(getattr(realtime, "hood", "") or ""),
            "lock_state": str(getattr(realtime, "lock_state", "") or ""),
        }

        extras["windows"] = {
            "left_front_window": str(getattr(realtime, "left_front_window", "") or ""),
            "right_front_window": str(getattr(realtime, "right_front_window", "") or ""),
            "left_rear_window": str(getattr(realtime, "left_rear_window", "") or ""),
            "right_rear_window": str(getattr(realtime, "right_rear_window", "") or ""),
            "sunroof": str(getattr(realtime, "sunroof", "") or ""),
        }

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


# Global singleton
state = BridgeState()


async def poller_loop() -> None:
    """Continuously poll BYD API at the configured interval."""
    _logger.info("Poller started — interval=%ds mode=%s", settings.poll_interval, settings.mode)
    await state.update()
    while True:
        await asyncio.sleep(settings.poll_interval)
        await state.update()