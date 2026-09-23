"""Sensors for Garmin Bounce integration."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GarminBounceDataUpdateCoordinator

def _format_seconds_to_time(seconds: Any) -> str:
    """Format seconds from midnight to HH:MM string."""
    if not isinstance(seconds, (int, float)):
        return str(seconds or "")
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery_level",
        name="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="steps_today",
        name="Daily Steps",
        icon="mdi:walk",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="steps_goal",
        name="Step Goal",
        icon="mdi:flag-checkered",
        native_unit_of_measurement="steps",
    ),
    SensorEntityDescription(
        key="steps_record",
        name="Steps Record",
        icon="mdi:trophy",
        native_unit_of_measurement="steps",
    ),
    SensorEntityDescription(
        key="subscription_status",
        name="LTE Status",
        icon="mdi:signal-cellular-outline",
    ),
    SensorEntityDescription(
        key="satellite_count",
        name="GPS Satellites",
        icon="mdi:satellite-variant",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="fix_type",
        name="Location Fix Type",
        icon="mdi:crosshairs-gps",
    ),
    SensorEntityDescription(
        key="last_sync_date",
        name="Last Sync",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="last_message",
        name="Last Message",
        icon="mdi:message-text-clock",
    ),
    SensorEntityDescription(
        key="safety_zone",
        name="Safety Zone",
        icon="mdi:map-marker-radius",
    ),
    SensorEntityDescription(
        key="school_mode_status",
        name="School Mode Status",
        icon="mdi:school",
    ),
    SensorEntityDescription(
        key="dnd_status",
        name="Do Not Disturb Status",
        icon="mdi:bell-off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garmin Bounce sensor entities."""
    coordinator: GarminBounceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_id, dev_data in coordinator.data.get("devices", {}).items():
        for description in SENSOR_DESCRIPTIONS:
            entities.append(GarminBounceSensor(coordinator, device_id, description))

    async_add_entities(entities)


class GarminBounceSensor(CoordinatorEntity[GarminBounceDataUpdateCoordinator], SensorEntity):
    """Representation of a Garmin Bounce sensor."""

    def __init__(
        self,
        coordinator: GarminBounceDataUpdateCoordinator,
        device_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        dev_data = self._device_data
        kid_name = dev_data.get("kid_name", "Child")

        self._attr_name = f"{kid_name} {description.name}"
        self._attr_unique_id = f"garmin_bounce_{device_id}_{description.key}"

    @property
    def _device_data(self) -> Dict[str, Any]:
        """Return the device dictionary from coordinator."""
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})

    @property
    def _telemetry(self) -> Dict[str, Any]:
        """Return latest telemetry dictionary."""
        return self._device_data.get("telemetry", {})

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
    def native_value(self) -> Any:
        """Return native value of the sensor."""
        k = self.entity_description.key
        dev = self._device_data
        t = self._telemetry

        if k == "battery_level":
            return t.get("battery_level")
        if k == "steps_today":
            return dev.get("steps_today")
        if k == "steps_goal":
            return dev.get("steps_goal")
        if k == "steps_record":
            return dev.get("steps_record")
        if k == "subscription_status":
            return dev.get("subscription", {}).get("status", "UNKNOWN")
        if k == "satellite_count":
            return t.get("satellite_count")
        if k == "fix_type":
            return t.get("fix_type")
        if k == "last_sync_date":
            ms = dev.get("last_sync_date")
            if ms:
                return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
            return None
        if k == "last_message":
            last_msg = dev.get("last_message")
            if last_msg:
                sender = last_msg.get("sender", "")
                txt = last_msg.get("text", "")
                val = f"{sender}: {txt}" if sender else txt
                return val[:255]
            return "Keine Nachrichten"
        if k == "safety_zone":
            return dev.get("current_zone", "Außerhalb")
        if k == "school_mode_status":
            sm = dev.get("settings", {}).get("schoolMode", {})
            return sm.get("mode", "OFF") if isinstance(sm, dict) else "OFF"
        if k == "dnd_status":
            dnd = dev.get("settings", {}).get("dndEnabled", False)
            return "on" if dnd else "off"

        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra sensor attributes."""
        k = self.entity_description.key
        if k == "battery_level":
            return {
                "charging": self._telemetry.get("battery_charging", False)
            }
        if k == "steps_today":
            return {
                "steps_yesterday": self._device_data.get("steps_yesterday", 0)
            }
        if k == "last_message":
            last_msg = self._device_data.get("last_message") or {}
            canned_list = [
                m.get("messageText")
                for m in self._device_data.get("canned_messages", [])
                if m.get("messageText")
            ]
            return {
                "message_id": last_msg.get("message_id"),
                "sender": last_msg.get("sender"),
                "timestamp": last_msg.get("timestamp"),
                "direction": last_msg.get("direction"),
                "media_type": last_msg.get("media_type"),
                "is_audio": last_msg.get("is_audio", False),
                "audio_url": last_msg.get("audio_url"),
                "canned_messages": canned_list,
                "chat_history": self._device_data.get("chat_history", []),
            }
        if k == "safety_zone":
            return {
                "zones": self._device_data.get("geofences", []),
                "current_latitude": self._telemetry.get("latitude"),
                "current_longitude": self._telemetry.get("longitude"),
            }
        if k == "school_mode_status":
            sm = self._device_data.get("settings", {}).get("schoolMode", {})
            if isinstance(sm, dict):
                return {
                    "mode": sm.get("mode", "OFF"),
                    "start_time": _format_seconds_to_time(sm.get("startTime")),
                    "end_time": _format_seconds_to_time(sm.get("endTime")),
                    "days": sm.get("days", []),
                }
            return {}
        if k == "dnd_status":
            settings = self._device_data.get("settings", {})
            return {
                "dnd_enabled": bool(settings.get("dndEnabled", False)),
                "sound_vibration_enabled": settings.get("soundVibrationEnabled"),
            }
        return {}
