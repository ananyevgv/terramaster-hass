"""Update platform for the TerraMaster NAS."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TerraMasterConfigEntry
from .coordinator import TerraMasterCoordinator
from .entity import TerraMasterEntity

PARALLEL_UPDATES = 0

async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([TerraMasterUpdate(coordinator)])


class TerraMasterUpdate(TerraMasterEntity, UpdateEntity):
    """Update entity for TOS firmware."""

    _attr_translation_key = "firmware"
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, coordinator: TerraMasterCoordinator) -> None:
        super().__init__(coordinator, "firmware")

    @property
    def installed_version(self) -> str | None:
        return self.coordinator.data.tos_version

    @property
    def latest_version(self) -> str | None:
        if self.coordinator.data.update_available:
            return self.coordinator.data.update_version
        return self.installed_version

    @property
    def release_notes(self) -> str | None:
        return self.coordinator.data.update_release_notes

    async def async_install(self, version: str, backup: bool, **kwargs) -> None:
        """Install the update."""
        await self.coordinator.client.install_update()
        await self.coordinator.async_request_refresh()