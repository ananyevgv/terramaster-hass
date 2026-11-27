"""Shared entity bases for the TerraMaster integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    ChildDeviceInfo,
    DeviceInfo,
    async_get as async_get_device_registry,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TerraMasterCoordinator
from .tos.models import Disk


class TerraMasterEntity(CoordinatorEntity[TerraMasterCoordinator]):
    """Base entity carrying the shared device registry entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TerraMasterCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the parent NAS device info."""
        data = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=(data.device_name if data else None) or "TerraMaster NAS",
            model=data.model if data else None,
            configuration_url=self.coordinator.client.base_url,
        )


class TerraMasterDiskEntity(TerraMasterEntity):
    """Base for entities bound to one physical drive.

    Uses ChildDeviceInfo (new in HA 2026.9) to attach the drive as a
    logical part of the parent NAS.
    """

    def __init__(
        self, coordinator: TerraMasterCoordinator, disk: Disk, suffix: str
    ) -> None:
        super().__init__(coordinator, f"disk_{disk.unique_key}_{suffix}")
        self._slot = disk.slot
        self._attr_translation_placeholders = {"disk_name": disk.name}
        self._disk_identifier = (DOMAIN, f"{coordinator.entry.entry_id}_disk_{disk.unique_key}")
        self._disk_name = disk.name

    @property
    def _disk(self) -> Disk | None:
        return next(
            (d for d in self.coordinator.data.disks if d.slot == self._slot), None
        )

    @property
    def device_info(self) -> ChildDeviceInfo:
        """Return child device info for the drive."""
        registry = async_get_device_registry(self.hass)
        parent_device_id = async_get_device_id_by_identifier(
            self.hass,
            (DOMAIN, self.coordinator.entry.entry_id),
            config_entry_id=self.coordinator.entry.entry_id,
        )
        return ChildDeviceInfo(
            identifiers={self._disk_identifier},
            name=self._disk_name,
            parent_device_id=parent_device_id,
        )