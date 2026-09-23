"""The Garmin Bounce & Jr. integration."""
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_DI_TOKEN,
    CONF_IT_TOKEN,
    SERVICE_SEND_MESSAGE,
    SERVICE_SEND_VOICE_MESSAGE,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_AUDIO_FILE,
    ATTR_DEVICE_ID,
)
from .api import GarminBounceApiClient
from .coordinator import GarminBounceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_TARGET, default="child"): vol.In(["child", "family"]),
    }
)

SEND_VOICE_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_AUDIO_FILE): cv.string,
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_TARGET, default="child"): vol.In(["child", "family"]),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Bounce from a config entry."""
    di_token = entry.data[CONF_DI_TOKEN]
    it_token = entry.data.get(CONF_IT_TOKEN)

    api = GarminBounceApiClient(di_token, it_token)
    coordinator = GarminBounceDataUpdateCoordinator(hass, api)

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def async_handle_send_message(call: ServiceCall) -> None:
        """Handle sending text messages via Garmin Bounce."""
        msg_text = call.data[ATTR_MESSAGE]
        target = call.data.get(ATTR_TARGET, "child")
        req_dev_id = call.data.get(ATTR_DEVICE_ID)

        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            _LOGGER.error("No Garmin Bounce integrations loaded")
            return

        coord = coordinators[0]
        to_connect_id = None

        if target == "child" or req_dev_id:
            devices = coord.data.get("devices", {})
            if req_dev_id and req_dev_id in devices:
                to_connect_id = devices[req_dev_id].get("connect_id")
            elif devices:
                first_dev = next(iter(devices.values()))
                to_connect_id = first_dev.get("connect_id")

        success = await hass.async_add_executor_job(
            coord.api.send_text_message, msg_text, to_connect_id
        )
        if success:
            _LOGGER.info("Garmin Bounce message sent successfully")
            await coord.async_request_refresh()
        else:
            _LOGGER.error("Failed to send Garmin Bounce message")

    async def async_handle_send_voice_message(call: ServiceCall) -> None:
        """Handle sending audio / voice messages via Garmin Bounce."""
        audio_file = call.data[ATTR_AUDIO_FILE]
        target = call.data.get(ATTR_TARGET, "child")
        req_dev_id = call.data.get(ATTR_DEVICE_ID)

        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            _LOGGER.error("No Garmin Bounce integrations loaded")
            return

        coord = coordinators[0]
        to_connect_id = None

        if target == "child" or req_dev_id:
            devices = coord.data.get("devices", {})
            if req_dev_id and req_dev_id in devices:
                to_connect_id = devices[req_dev_id].get("connect_id")
            elif devices:
                first_dev = next(iter(devices.values()))
                to_connect_id = first_dev.get("connect_id")

        file_path = audio_file
        if file_path.startswith("/local/"):
            file_path = hass.config.path("www", file_path[len("/local/") :])

        def _read_and_send() -> bool:
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                return coord.api.send_audio_message(content, to_connect_id)
            except Exception as read_err:
                _LOGGER.error("Error reading audio file %s: %s", file_path, read_err)
                return False

        success = await hass.async_add_executor_job(_read_and_send)
        if success:
            _LOGGER.info("Garmin Bounce audio message sent successfully")
            await coord.async_request_refresh()
        else:
            _LOGGER.error("Failed to send Garmin Bounce audio message")

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            async_handle_send_message,
            schema=SEND_MESSAGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_VOICE_MESSAGE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_VOICE_MESSAGE,
            async_handle_send_voice_message,
            schema=SEND_VOICE_MESSAGE_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Clean up services if last entry removed
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
        hass.services.async_remove(DOMAIN, SERVICE_SEND_VOICE_MESSAGE)

    return unload_ok

