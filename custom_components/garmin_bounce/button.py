"""Button entity for Garmin Bounce integration."""
from typing import Any, Dict

from homeassistant.components.button import ButtonEntity
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
    """Set up Garmin Bounce button entities."""
    coordinator: GarminBounceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_id, dev_data in coordinator.data.get("devices", {}).items():
        entities.append(GarminBounceLocateButton(coordinator, device_id))
        entities.append(GarminBounceStartLiveTrackButton(coordinator, device_id))
        entities.append(GarminBounceSyncCloudButton(coordinator, device_id))

    async_add_entities(entities)


class _BaseGarminButton(CoordinatorEntity[GarminBounceDataUpdateCoordinator], ButtonEntity):
    """Base class for Garmin Bounce button entities."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize base button entity."""
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def _device_data(self) -> Dict[str, Any]:
        """Return the device dictionary from coordinator."""
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})

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


class GarminBounceLocateButton(_BaseGarminButton):
    """Button to dispatch an on-demand location refresh command over LTE."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize button entity."""
        super().__init__(coordinator, device_id)
        kid_name = self._device_data.get("kid_name", "Child")
        self._attr_name = f"{kid_name} Refresh Location"
        self._attr_unique_id = f"garmin_bounce_{device_id}_locate_button"
        self._attr_icon = "mdi:crosshairs-gps"

    async def async_press(self) -> None:
        """Handle button press: send update-location instruction to the watch."""
        await self.hass.async_add_executor_job(
            self.coordinator.api.request_location_update,
            self._device_id,
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())


class GarminBounceStartLiveTrackButton(_BaseGarminButton):
    """Button to trigger LiveTrack high-frequency tracking mode over LTE."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize button entity."""
        super().__init__(coordinator, device_id)
        kid_name = self._device_data.get("kid_name", "Child")
        self._attr_name = f"{kid_name} Start LiveTrack"
        self._attr_unique_id = f"garmin_bounce_{device_id}_start_livetrack_button"
        self._attr_icon = "mdi:radar"

    async def async_press(self) -> None:
        """Handle button press: send start-family-track instruction to the watch."""
        await self.hass.async_add_executor_job(
            self.coordinator.api.start_live_track,
            self._device_id,
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())


class GarminBounceSyncCloudButton(_BaseGarminButton):
    """Button to force an immediate re-poll of all Garmin cloud APIs."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize button entity."""
        super().__init__(coordinator, device_id)
        kid_name = self._device_data.get("kid_name", "Child")
        self._attr_name = f"{kid_name} Poll Cloud Data"
        self._attr_unique_id = f"garmin_bounce_{device_id}_poll_cloud_button"
        self._attr_icon = "mdi:cloud-sync"

    async def async_press(self) -> None:
        """Handle button press: refresh coordinator data immediately."""
        await self.coordinator.async_request_refresh()
