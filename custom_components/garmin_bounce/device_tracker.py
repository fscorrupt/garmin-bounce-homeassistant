"""Support for Garmin Bounce GPS device tracker."""
from typing import Any, Dict, Optional

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GarminBounceDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garmin Bounce device tracker entities."""
    coordinator: GarminBounceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_id, dev_data in coordinator.data.get("devices", {}).items():
        entities.append(GarminBounceDeviceTracker(coordinator, device_id))

    async_add_entities(entities)


class GarminBounceDeviceTracker(CoordinatorEntity[GarminBounceDataUpdateCoordinator], TrackerEntity):
    """Representation of a Garmin Bounce GPS tracker."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize tracker entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        dev_data = self._device_data
        kid_name = dev_data.get("kid_name", "Child")

        self._attr_name = f"{kid_name} Bounce 2"
        self._attr_unique_id = f"garmin_bounce_{device_id}_tracker"

    @property
    def _device_data(self) -> Dict[str, Any]:
        """Return the device dictionary from coordinator data."""
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})

    @property
    def _telemetry(self) -> Dict[str, Any]:
        """Return latest telemetry dictionary."""
        return self._device_data.get("telemetry", {})

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of the device."""
        return self._telemetry.get("latitude")

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of the device."""
        return self._telemetry.get("longitude")

    @property
    def location_accuracy(self) -> int:
        """Return location accuracy in meters."""
        return self._telemetry.get("accuracy") or 0

    @property
    def altitude(self) -> Optional[float]:
        """Return altitude in meters."""
        return self._telemetry.get("altitude")

    @property
    def battery_level(self) -> Optional[int]:
        """Return battery level percentage."""
        return self._telemetry.get("battery_level")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        dev_data = self._device_data
        kid_name = dev_data.get("kid_name", "Child")
        part_number = dev_data.get("part_number", "Garmin Bounce")

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"{kid_name}'s Bounce 2",
            manufacturer="Garmin",
            model=part_number,
            sw_version="5.23",
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return device tracker attributes."""
        t = self._telemetry
        return {
            "speed": t.get("speed"),
            "fix_type": t.get("fix_type"),
            "satellite_count": t.get("satellite_count"),
            "battery_charging": t.get("battery_charging"),
            "recorded_time": t.get("date_time"),
            "reported_time": t.get("reported_time"),
            "device_id": self._device_id,
            "kid_profile_id": self._device_data.get("kid_id"),
            "safety_zone": self._device_data.get("current_zone", "Außerhalb"),
        }
