"""Polling coordinator for a single TerraMaster NAS."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_OVERHEAT_CELSIUS,
    CONF_OVERHEAT_PROTECTION,
    DEFAULT_OVERHEAT_CELSIUS,
    DEFAULT_OVERHEAT_PROTECTION,
    DOMAIN,
)
from .tos import TosAuthError, TosClient, TosError
from .tos.models import (
    NasData,
    NetworkInterface,
    build_cpu,
    build_disks,
    build_memory,
    build_pools,
    build_volumes,
)

_LOGGER = logging.getLogger(__name__)


class TerraMasterCoordinator(DataUpdateCoordinator[NasData]):
    """Fetch the whole NAS picture in one pass."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TosClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data.get('host')}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.entry = entry
        self._overheat_protection = entry.options.get(
            CONF_OVERHEAT_PROTECTION, DEFAULT_OVERHEAT_PROTECTION
        )
        self._overheat_celsius = entry.options.get(
            CONF_OVERHEAT_CELSIUS, DEFAULT_OVERHEAT_CELSIUS
        )

    async def _async_update_data(self) -> NasData:
        try:
            results = await asyncio.gather(
                self.client.hardware(),
                self.client.temperature(),
                self.client.get("/disk/GetDiskStatus"),
                self.client.disks(),
                self.client.get("/disk/GetOverview"),
                self.client.volumes(),
                self.client.pools(),
                self.client.processor(),
                self.client.cpu(),
                self.client.memory(),
                self.client.network(),
                self.client.system(),
            )
        except TosAuthError as err:
            raise ConfigEntryAuthFailed(
                f"authentication with the NAS failed: {err}"
            ) from err
        except (TosError, asyncio.TimeoutError, OSError) as err:
            raise UpdateFailed(f"error talking to the NAS: {err}") from err

        (hardware, temps, status, listing, overview, volumes, pools, cpu,
         cpu_monitor, memory, network, system_info) = results
        data = self._assemble(
            hardware, temps, status, listing, overview, volumes, pools, cpu,
            cpu_monitor, memory, network, system_info,
        )
        await self._guard_against_overheating(data, hardware)
        return data

    async def _guard_against_overheating(
        self, data: NasData, hardware: dict[str, Any]
    ) -> None:
        if not self._overheat_protection or data.fan_is_auto:
            return
        hottest = data.max_disk_temperature
        if hottest is None or hottest < self._overheat_celsius:
            return

        _LOGGER.warning(
            "Hottest disk is %.0f°C (>= %.0f°C) with the fan in manual mode at "
            "level %s; restoring automatic fan control",
            hottest,
            self._overheat_celsius,
            data.fan_level,
        )
        current = dict(hardware.get("data") or {})
        current["fan"] = {"is_auto": True, "level": -1}
        try:
            await self.client.set_hardware(current)
        except TosError as err:
            _LOGGER.error("Could not restore automatic fan control: %s", err)
            return
        data.fan_is_auto = True
        data.fan_level = -1

    @staticmethod
    def _assemble(
        hardware: dict[str, Any],
        temps: dict[str, Any],
        status: dict[str, Any],
        listing: dict[str, Any],
        overview: dict[str, Any],
        volumes: dict[str, Any],
        pools: dict[str, Any],
        cpu: dict[str, Any],
        cpu_monitor: dict[str, Any],
        memory: dict[str, Any],
        network: dict[str, Any],
        system_info: dict[str, Any],
    ) -> NasData:
        fan = (hardware.get("data") or {}).get("fan") or {}
        temp_data = temps.get("data") or {}
        overview_data = overview.get("data") or {}
        cpu_data = cpu.get("data") or {}
        cpu_percent, cpu_cores = build_cpu(cpu_monitor)
        mem_percent, mem_used, mem_total = build_memory(memory)

        # --- network ---
        net_list = network.get("data") or []
        if isinstance(net_list, dict):
            net_list = [net_list]

        interfaces = []
        for i in net_list:
            speed_str = i.get("speed", "")
            speed_mbps = None
            if speed_str:
                match = re.search(r"(\d+)", speed_str)
                if match:
                    speed_mbps = int(match.group(1))
            
            interfaces.append(
                NetworkInterface(
                    name=i.get("eth") or "unknown",
                    ip=i.get("ipaddress"),
                    speed_mbps=speed_mbps,
                    is_up=i.get("online") == 1,
                    has_gateway=i.get("ip4_gw_state") is True,
                )
            )

        # --- system ---
        tos_version = None
        uptime_seconds = None
        sys_list = system_info.get("data") or []
        for item in sys_list:
            label = item.get("label", [])
            if "TOSversion" in label:
                tos_version = item.get("value")
            elif "startTime" in label:
                try:
                    uptime_seconds = int(item.get("value"))
                except (ValueError, TypeError):
                    pass

        return NasData(
            fan_is_auto=fan.get("is_auto"),
            fan_level=fan.get("level"),
            fan_rpm=temp_data.get("fan_speed"),
            cpu_temperature=temp_data.get("cpu_temperature"),
            system_temperature=temp_data.get("sys_temperature"),
            model=overview_data.get("model"),
            device_name=overview_data.get("device_name"),
            processor=cpu_data.get("Processor"),
            cpu_percent=cpu_percent,
            cpu_per_core=cpu_cores,
            memory_percent=mem_percent,
            memory_used=mem_used,
            memory_total=mem_total,
            disks=build_disks(status, listing, overview),
            volumes=build_volumes(volumes),
            pools=build_pools(pools),
            network_interfaces=interfaces,
            tos_version=tos_version,
            uptime_seconds=uptime_seconds,
        )

    async def async_set_hardware(self, mutate: dict[str, Any]) -> None:
        current = dict((await self.client.hardware()).get("data") or {})
        current.update(mutate)
        await self.client.set_hardware(current)
        await self.async_request_refresh()