"""Service switches for the TerraMaster NAS."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TerraMasterConfigEntry
from .const import CONTROLLABLE_SERVICES, DOMAIN
from .coordinator import TerraMasterCoordinator
from .entity import TerraMasterEntity
from .tos import TosError, TosPermissionError

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TerraMasterServiceSwitch(coordinator, name) for name in CONTROLLABLE_SERVICES
    )


class TerraMasterServiceSwitch(TerraMasterEntity, SwitchEntity):
    """Enable or disable a TOS service (SMB, NFS, SSH)."""

    _attr_translation_key = "service"

    def __init__(self, coordinator: TerraMasterCoordinator, service: str) -> None:
        super().__init__(coordinator, f"service_{service}")
        self._service = service
        self._attr_translation_placeholders = {"service": service.upper()}

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.services.get(self._service)

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_service(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_service(False)

    async def _set_service(self, enable: bool) -> None:
        try:
            await self.coordinator.async_set_service(self._service, enable)
        except TosPermissionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_not_permitted",
            ) from err
        except TosError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_service_failed",
                translation_placeholders={"error": str(err)},
            ) from err