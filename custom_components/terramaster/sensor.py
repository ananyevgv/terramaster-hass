"""Sensor entities for the TerraMaster NAS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TerraMasterConfigEntry
from .coordinator import TerraMasterCoordinator
from .entity import TerraMasterDiskEntity, TerraMasterEntity
from .tos.models import NasData, NetworkInterface

PARALLEL_UPDATES = 0

CAPACITY = {
    "device_class": SensorDeviceClass.DATA_SIZE,
    "native_unit_of_measurement": UnitOfInformation.BYTES,
    "suggested_unit_of_measurement": UnitOfInformation.GIBIBYTES,
    "suggested_display_precision": 1,
}


@dataclass(frozen=True, kw_only=True)
class TerraMasterSensorDescription(SensorEntityDescription):
    value_fn: Callable[[NasData], float | int | str | None]


SYSTEM_SENSORS: tuple[TerraMasterSensorDescription, ...] = (
    TerraMasterSensorDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.cpu_temperature,
        icon="mdi:cpu-64-bit",
    ),
    TerraMasterSensorDescription(
        key="system_temperature",
        translation_key="system_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.system_temperature,
        icon="mdi:thermometer",
    ),
    TerraMasterSensorDescription(
        key="max_disk_temperature",
        translation_key="max_disk_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.max_disk_temperature,
        icon="mdi:thermometer-alert",
    ),
    TerraMasterSensorDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.cpu_percent,
        icon="mdi:cpu-64-bit",
    ),
    TerraMasterSensorDescription(
        key="memory_usage",
        translation_key="memory_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.memory_percent,
        icon="mdi:memory",
    ),
    TerraMasterSensorDescription(
        key="memory_used",
        translation_key="memory_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.memory_used,
        icon="mdi:memory",
    ),
    TerraMasterSensorDescription(
        key="fan_speed",
        translation_key="fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.fan_rpm,
        icon="mdi:fan",
    ),
    #TerraMasterSensorDescription(
    #    key="tos_version",
    #    translation_key="tos_version",
    #    entity_category=EntityCategory.DIAGNOSTIC,
    #    value_fn=lambda data: data.tos_version,
    #    icon="mdi:information-outline",
    #),
    TerraMasterSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.uptime_seconds,
        icon="mdi:clock-outline",
    ),
)

VOLUME_SENSORS: dict[str, tuple[str, dict]] = {
    "volume_total": ("total", CAPACITY),
    "volume_used": ("used", CAPACITY),
    "volume_free": ("available", CAPACITY),
    "volume_usage": ("usage", {"native_unit_of_measurement": PERCENTAGE}),
}

POOL_SENSORS: dict[str, tuple[str, dict]] = {
  #  "pool_total": ("total", CAPACITY),
  #  "pool_free": ("free", CAPACITY),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    data = coordinator.data

    entities: list[SensorEntity] = [
        TerraMasterSensor(coordinator, description) for description in SYSTEM_SENSORS
    ]

    for disk in data.disks:
        entities.append(TerraMasterDiskTemperature(coordinator, disk))
        entities.append(TerraMasterDiskPowerOnHours(coordinator, disk))
        entities.append(TerraMasterDiskCapacity(coordinator, disk))
        # Сенсоры скорости дисков (раскомментируйте, если нужно)
        # entities.append(TerraMasterDiskReadSpeed(coordinator, disk))
        # entities.append(TerraMasterDiskWriteSpeed(coordinator, disk))

    entities.extend(
        TerraMasterVolumeSensor(coordinator, volume, key)
        for volume in data.volumes
        for key in VOLUME_SENSORS
    )
    entities.extend(
        TerraMasterPoolSensor(coordinator, pool, key)
        for pool in data.pools
        for key in POOL_SENSORS
    )

    # --- NEW: sensors for each network interface ---
    for iface in data.network_interfaces:
        # Пропускаем пустые интерфейсы (PPPoE и т.д.)
        if not iface.ip and not iface.speed_mbps:
            continue
        entities.append(TerraMasterNetworkIpSensor(coordinator, iface))
        entities.append(TerraMasterNetworkSpeedSensor(coordinator, iface))

    async_add_entities(entities)


class TerraMasterSensor(TerraMasterEntity, SensorEntity):
    entity_description: TerraMasterSensorDescription

    def __init__(
        self,
        coordinator: TerraMasterCoordinator,
        description: TerraMasterSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        data = self.coordinator.data
        if self.entity_description.key == "cpu_usage":
            return {"processor": data.processor, **data.cpu_per_core} or None
        if self.entity_description.key == "memory_used":
            return {"total": data.memory_total}
        return None


class TerraMasterDiskTemperature(TerraMasterDiskEntity, SensorEntity):
    _attr_translation_key = "disk_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:harddisk"

    def __init__(self, coordinator: TerraMasterCoordinator, disk) -> None:
        super().__init__(coordinator, disk, "temperature")

    @property
    def native_value(self) -> float | None:
        disk = self._disk
        return disk.temperature if disk else None

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | None] | None:
        if (disk := self._disk) is None:
            return None
        return {
            "slot": disk.slot,
            "model": disk.model,
            "serial": disk.serial,
            "device": disk.device,
            "capacity": disk.capacity,
            "read_speed": disk.read_speed,
            "write_speed": disk.write_speed,
        }


class TerraMasterDiskPowerOnHours(TerraMasterDiskEntity, SensorEntity):
    _attr_translation_key = "disk_power_on_hours"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: TerraMasterCoordinator, disk) -> None:
        super().__init__(coordinator, disk, "power_on_hours")

    @property
    def native_value(self) -> int | None:
        disk = self._disk
        return disk.power_on_hours if disk else None


class TerraMasterDiskCapacity(TerraMasterDiskEntity, SensorEntity):
    _attr_translation_key = "disk_capacity"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_suggested_unit_of_measurement = UnitOfInformation.GIBIBYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:database"

    def __init__(self, coordinator: TerraMasterCoordinator, disk) -> None:
        super().__init__(coordinator, disk, "capacity")

    @property
    def native_value(self) -> int | None:
        disk = self._disk
        return disk.capacity_bytes if disk else None


# --- НОВЫЕ СЕНСОРЫ СКОРОСТИ ДИСКОВ (пока отключены в async_setup_entry) ---

class TerraMasterDiskReadSpeed(TerraMasterDiskEntity, SensorEntity):
    """Read speed of one physical drive."""
    _attr_translation_key = "disk_read_speed"
    _attr_native_unit_of_measurement = "B/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_unit_of_measurement = UnitOfInformation.KIBIBYTES
    _attr_icon = "mdi:download"

    def __init__(self, coordinator: TerraMasterCoordinator, disk) -> None:
        super().__init__(coordinator, disk, "read_speed")

    @property
    def native_value(self) -> int | None:
        disk = self._disk
        if not disk or disk.read_speed is None:
            return None
        try:
            return int(disk.read_speed)
        except (ValueError, TypeError):
            return None


class TerraMasterDiskWriteSpeed(TerraMasterDiskEntity, SensorEntity):
    """Write speed of one physical drive."""
    _attr_translation_key = "disk_write_speed"
    _attr_native_unit_of_measurement = "B/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_unit_of_measurement = UnitOfInformation.KIBIBYTES
    _attr_icon = "mdi:upload"

    def __init__(self, coordinator: TerraMasterCoordinator, disk) -> None:
        super().__init__(coordinator, disk, "write_speed")

    @property
    def native_value(self) -> int | None:
        disk = self._disk
        if not disk or disk.write_speed is None:
            return None
        try:
            return int(disk.write_speed)
        except (ValueError, TypeError):
            return None


# --- ОСТАЛЬНЫЕ СЕНСОРЫ ---

class TerraMasterVolumeSensor(TerraMasterEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: TerraMasterCoordinator, volume, translation_key: str
    ) -> None:
        super().__init__(coordinator, f"volume_{volume.uuid}_{translation_key}")
        self._uuid = volume.uuid
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = {"volume_name": volume.name}
        self._attribute, extra = VOLUME_SENSORS[translation_key]
        for name, value in extra.items():
            setattr(self, f"_attr_{name}", value)

    @property
    def _volume(self):
        return next(
            (v for v in self.coordinator.data.volumes if v.uuid == self._uuid), None
        )

    @property
    def native_value(self) -> float | int | None:
        if (volume := self._volume) is None:
            return None
        value = getattr(volume, self._attribute)
        if self._attribute == "usage" and value is not None:
            return round(value, 1)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, str | None] | None:
        if (volume := self._volume) is None:
            return None
        return {"filesystem": volume.filesystem, "mount_path": volume.mount_path}

    @property
    def icon(self) -> str:
        if self._attr_translation_key == "volume_usage":
            return "mdi:gauge"
        return "mdi:database"


class TerraMasterPoolSensor(TerraMasterEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: TerraMasterCoordinator, pool, translation_key: str
    ) -> None:
        super().__init__(coordinator, f"pool_{pool.uuid}_{translation_key}")
        self._uuid = pool.uuid
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = {"pool_name": pool.name}
        self._attribute, extra = POOL_SENSORS[translation_key]
        for name, value in extra.items():
            setattr(self, f"_attr_{name}", value)

    @property
    def _pool(self):
        return next(
            (p for p in self.coordinator.data.pools if p.uuid == self._uuid), None
        )

    @property
    def native_value(self) -> int | None:
        return getattr(pool, self._attribute) if (pool := self._pool) else None

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None] | None:
        if (pool := self._pool) is None:
            return None
        return {"raid_level": pool.level, "health": pool.health, "status": pool.status}

    @property
    def icon(self) -> str:
        return "mdi:server"


class TerraMasterNetworkIpSensor(TerraMasterEntity, SensorEntity):
    """IP address of a specific network interface."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:ip-network"

    def __init__(self, coordinator: TerraMasterCoordinator, iface: NetworkInterface) -> None:
        super().__init__(coordinator, f"network_{iface.name}_ip")
        self._iface_name = iface.name
        self._attr_translation_key = "network_interface_ip"
        # Передаем имя интерфейса в перевод
        self._attr_translation_placeholders = {"interface": iface.name.replace("ovs_", "")}

    @property
    def native_value(self) -> str | None:
        iface = next((i for i in self.coordinator.data.network_interfaces if i.name == self._iface_name), None)
        return iface.ip if iface else None


class TerraMasterNetworkSpeedSensor(TerraMasterEntity, SensorEntity):
    """Link speed of a specific network interface."""
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = "Mbit/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:ethernet"

    def __init__(self, coordinator: TerraMasterCoordinator, iface: NetworkInterface) -> None:
        super().__init__(coordinator, f"network_{iface.name}_speed")
        self._iface_name = iface.name
        self._attr_translation_key = "network_interface_speed"
        self._attr_translation_placeholders = {"interface": iface.name.replace("ovs_", "")}

    @property
    def native_value(self) -> int | None:
        iface = next((i for i in self.coordinator.data.network_interfaces if i.name == self._iface_name), None)
        return iface.speed_mbps if iface else None