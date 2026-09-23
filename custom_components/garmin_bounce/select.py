"""Select platform for Garmin Bounce integration."""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GarminBounceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCHOOL_MODE_OPTIONS = ["OFF", "RESTRICTED", "ALL"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garmin Bounce select entities."""
    coordinator: GarminBounceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_id, dev_data in coordinator.data.get("devices", {}).items():
        entities.append(GarminBounceCannedMessageSelect(coordinator, device_id))
        entities.append(GarminBounceSchoolModeSelect(coordinator, device_id))

    async_add_entities(entities)


class GarminBounceCannedMessageSelect(
    CoordinatorEntity[GarminBounceDataUpdateCoordinator], SelectEntity
):
    """Select entity to send pre-defined canned messages (message templates) to the watch."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize canned message select."""
        super().__init__(coordinator)
        self._device_id = device_id
        dev_data = self._device_data
        kid_name = dev_data.get("kid_name", "Child")
        self._connect_id = dev_data.get("connect_id")

        self._attr_name = f"{kid_name} Quick Message"
        self._attr_unique_id = f"garmin_bounce_{device_id}_canned_message"
        self._attr_icon = "mdi:message-reply-text"
        self._current_option: Optional[str] = None

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
    def options(self) -> List[str]:
        """Return list of canned message options."""
        raw_msgs = self._device_data.get("canned_messages", [])
        opts = [
            m.get("messageText")
            for m in raw_msgs
            if m.get("messageText") and str(m.get("messageText")).strip()
        ]
        return opts if opts else ["OK", "Ja", "Nein", "Danke"]

    @property
    def current_option(self) -> Optional[str]:
        """Return current option."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Send the selected message template immediately to the watch."""
        if not option:
            return
        self._current_option = option
        self.async_write_ha_state()

        _LOGGER.info("Sending canned template message '%s' to child %s", option, self._connect_id)
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.send_text_message, option, self._connect_id
        )
        if success:
            await self.coordinator.async_request_refresh()


class GarminBounceSchoolModeSelect(
    CoordinatorEntity[GarminBounceDataUpdateCoordinator], SelectEntity
):
    """Select entity to configure the School Mode mode (OFF, RESTRICTED, ALL)."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize School Mode select."""
        super().__init__(coordinator)
        self._device_id = device_id
        dev_data = self._device_data
        kid_name = dev_data.get("kid_name", "Child")
        self._connect_id = dev_data.get("connect_id")

        self._attr_name = f"{kid_name} School Mode Setting"
        self._attr_unique_id = f"garmin_bounce_{device_id}_school_mode_select"
        self._attr_icon = "mdi:school-outline"

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
    def options(self) -> List[str]:
        """Return school mode options."""
        return SCHOOL_MODE_OPTIONS

    @property
    def current_option(self) -> Optional[str]:
        """Return currently configured school mode."""
        settings = self._device_data.get("settings", {})
        sm = settings.get("schoolMode")
        if isinstance(sm, dict):
            mode = str(sm.get("mode", "OFF")).upper()
            if mode in SCHOOL_MODE_OPTIONS:
                return mode
        return "OFF"

    async def async_select_option(self, option: str) -> None:
        """Change school mode option on the watch."""
        if option not in SCHOOL_MODE_OPTIONS or not self._connect_id:
            return
        success = await self.hass.async_add_executor_job(
            self.coordinator.api.set_school_mode,
            self._device_id,
            self._connect_id,
            option,
        )
        if success:
            await self.coordinator.async_request_refresh()
