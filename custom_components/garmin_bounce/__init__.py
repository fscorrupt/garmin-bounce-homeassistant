from datetime import timedelta
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_TOKEN_DATA,
    CONF_DI_TOKEN,
    CONF_IT_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    SERVICE_SEND_MESSAGE,
    SERVICE_SEND_VOICE_MESSAGE,
    SERVICE_SET_DND,
    SERVICE_SET_SCHOOL_MODE,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_AUDIO_FILE,
    ATTR_DEVICE_ID,
    ATTR_ENABLED,
    ATTR_MODE,
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

SET_DND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENABLED): cv.boolean,
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)

SET_SCHOOL_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MODE): vol.In(["OFF", "RESTRICTED", "ALL", "off", "restricted", "all"]),
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Bounce from a config entry."""
    di_token = entry.data[CONF_DI_TOKEN]
    it_token = entry.data.get(CONF_IT_TOKEN)
    token_data = entry.data.get(CONF_TOKEN_DATA)

    def _on_tokens_updated_sync(new_tokens: dict) -> None:
        """Persist refreshed tokens to config entry safely on the main HA event loop."""
        def _update():
            new_data = dict(entry.data)
            new_data[CONF_DI_TOKEN] = new_tokens.get("di_token") or api.di_token
            new_data[CONF_IT_TOKEN] = api.it_token
            new_data[CONF_TOKEN_DATA] = new_tokens
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.info("Persisted refreshed Garmin tokens to config entry for %s", entry.title)

        hass.loop.call_soon_threadsafe(_update)

    api = GarminBounceApiClient(
        di_token=di_token,
        it_token=it_token,
        token_data=token_data,
        on_tokens_updated=_on_tokens_updated_sync,
    )
    scan_interval_sec = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
    coordinator = GarminBounceDataUpdateCoordinator(
        hass, api, update_interval=timedelta(seconds=scan_interval_sec)
    )

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Reload on options update
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def async_handle_send_message(call: ServiceCall) -> None:
        """Handle sending text messages via Garmin Bounce."""
        msg_text = call.data[ATTR_MESSAGE]
        input_entity = None
        if isinstance(msg_text, str) and msg_text.startswith("input_text."):
            input_entity = msg_text
            state_obj = hass.states.get(input_entity)
            if state_obj and state_obj.state not in ("unknown", "unavailable"):
                msg_text = state_obj.state
            else:
                _LOGGER.warning("Entity %s has no text value", input_entity)
                return

        if not msg_text or not str(msg_text).strip():
            _LOGGER.warning("Empty message text received, skipping send")
            return

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
            if input_entity:
                await hass.services.async_call(
                    "input_text", "set_value", {"entity_id": input_entity, "value": ""}
                )
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

    async def async_handle_set_dnd(call: ServiceCall) -> None:
        """Handle setting DND mode on a watch."""
        enabled = call.data[ATTR_ENABLED]
        req_dev_id = call.data.get(ATTR_DEVICE_ID)

        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            return
        coord = coordinators[0]
        devices = coord.data.get("devices", {})

        target_dev = None
        if req_dev_id and req_dev_id in devices:
            target_dev = devices[req_dev_id]
        elif devices:
            target_dev = next(iter(devices.values()))

        if target_dev:
            dev_id = target_dev.get("device_id")
            connect_id = target_dev.get("connect_id")
            success = await hass.async_add_executor_job(
                coord.api.set_dnd_mode, dev_id, connect_id, enabled
            )
            if success:
                _LOGGER.info("DND mode set to %s on %s", enabled, dev_id)
                await coord.async_request_refresh()

    async def async_handle_set_school_mode(call: ServiceCall) -> None:
        """Handle setting School Mode on a watch."""
        mode = call.data[ATTR_MODE].upper()
        req_dev_id = call.data.get(ATTR_DEVICE_ID)

        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            return
        coord = coordinators[0]
        devices = coord.data.get("devices", {})

        target_dev = None
        if req_dev_id and req_dev_id in devices:
            target_dev = devices[req_dev_id]
        elif devices:
            target_dev = next(iter(devices.values()))

        if target_dev:
            dev_id = target_dev.get("device_id")
            connect_id = target_dev.get("connect_id")
            success = await hass.async_add_executor_job(
                coord.api.set_school_mode, dev_id, connect_id, mode
            )
            if success:
                _LOGGER.info("School mode set to %s on %s", mode, dev_id)
                await coord.async_request_refresh()

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

    if not hass.services.has_service(DOMAIN, SERVICE_SET_DND):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_DND,
            async_handle_set_dnd,
            schema=SET_DND_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SCHOOL_MODE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_SCHOOL_MODE,
            async_handle_set_school_mode,
            schema=SET_SCHOOL_MODE_SCHEMA,
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
        hass.services.async_remove(DOMAIN, SERVICE_SET_DND)
        hass.services.async_remove(DOMAIN, SERVICE_SET_SCHOOL_MODE)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)

