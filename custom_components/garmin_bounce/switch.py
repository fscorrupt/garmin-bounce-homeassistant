"""Switch platform for Garmin Bounce integration."""
import logging
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GarminBounceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _format_seconds_to_time(seconds: Any) -> str:
    """Format seconds from midnight to HH:MM string."""
    if not isinstance(seconds, (int, float)):
        return str(seconds or "")
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garmin Bounce switches."""
    coordinator: GarminBounceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_id, dev_data in coordinator.data.get("devices", {}).items():
        entities.append(GarminBounceDndSwitch(coordinator, device_id))
        entities.append(GarminBounceSchoolModeSwitch(coordinator, device_id))

    async_add_entities(entities)


class GarminBounceDndSwitch(
    CoordinatorEntity[GarminBounceDataUpdateCoordinator], SwitchEntity
):
    """Switch to toggle Do Not Disturb (DND) mode on the watch."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize DND switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        dev_data = self._device_data
        kid_name = dev_data.get("kid_name", "Child")
        self._connect_id = dev_data.get("connect_id")

        self._attr_name = f"{kid_name} Do Not Disturb"
        self._attr_unique_id = f"garmin_bounce_{device_id}_dnd"

    @property
    def _device_data(self) -> Dict[str, Any]:
        """Return device data from coordinator."""
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
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
    def icon(self) -> str:
        """Return icon based on state."""
        return "mdi:bell-off" if self.is_on else "mdi:bell-outline"

    @property
    def is_on(self) -> bool:
        """Return true if DND is enabled."""
        settings = self._device_data.get("settings", {})
        return bool(settings.get("dndEnabled", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on DND mode."""
        if not self._connect_id:
            _LOGGER.error("No connect_id for device %s", self._device_id)
            return
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.set_dnd_mode, self._device_id, self._connect_id, True
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off DND mode."""
        if not self._connect_id:
            _LOGGER.error("No connect_id for device %s", self._device_id)
            return
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.set_dnd_mode, self._device_id, self._connect_id, False
        )
        if success:
            await self.coordinator.async_request_refresh()


class GarminBounceSchoolModeSwitch(
    CoordinatorEntity[GarminBounceDataUpdateCoordinator], SwitchEntity
):
    """Switch to toggle School Mode on the watch."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize School Mode switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        dev_data = self._device_data
        kid_name = dev_data.get("kid_name", "Child")
        self._connect_id = dev_data.get("connect_id")

        self._attr_name = f"{kid_name} School Mode"
        self._attr_unique_id = f"garmin_bounce_{device_id}_school_mode"
        self._attr_icon = "mdi:school"

    @property
    def _device_data(self) -> Dict[str, Any]:
        """Return device data from coordinator."""
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})

    @property
    def _school_mode(self) -> Dict[str, Any]:
        """Return school mode configuration dictionary."""
        settings = self._device_data.get("settings", {})
        sm = settings.get("schoolMode")
        return sm if isinstance(sm, dict) else {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
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
    def is_on(self) -> bool:
        """Return true if School Mode is RESTRICTED or ALL."""
        mode = self._school_mode.get("mode", "OFF")
        return str(mode).upper() in ("RESTRICTED", "ALL")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return school mode attributes."""
        sm = self._school_mode
        return {
            "mode": sm.get("mode", "OFF"),
            "start_time": _format_seconds_to_time(sm.get("startTime")),
            "end_time": _format_seconds_to_time(sm.get("endTime")),
            "days": sm.get("days", []),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on School Mode (RESTRICTED)."""
        if not self._connect_id:
            _LOGGER.error("No connect_id for device %s", self._device_id)
            return
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.set_school_mode,
            self._device_id,
            self._connect_id,
            "RESTRICTED",
        )
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off School Mode (OFF)."""
        if not self._connect_id:
            _LOGGER.error("No connect_id for device %s", self._device_id)
            return
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.set_school_mode,
            self._device_id,
            self._connect_id,
            "OFF",
        )
        if success:
            await self.coordinator.async_request_refresh()
