"""Config flow for Garmin Bounce integration."""
import logging
import queue
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .const import DOMAIN, CONF_DI_TOKEN, CONF_IT_TOKEN, CONF_TOKEN_DATA
from .api import GarminBounceApiClient

_LOGGER = logging.getLogger(__name__)


class GarminBounceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garmin Bounce."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._email: Optional[str] = None
        self._password: Optional[str] = None
        self._garmin: Optional[Garmin] = None
        self._mfa_in_queue: "queue.Queue[str]" = queue.Queue()
        self._mfa_out_queue: "queue.Queue[str]" = queue.Queue()

    def _prompt_mfa_callback(self) -> str:
        """Callback invoked by garminconnect when 2FA code is needed."""
        self._mfa_out_queue.put("MFA_NEEDED")
        return self._mfa_in_queue.get()

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle initial step where user provides email and password."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]

            # Run login in executor
            result = await self.hass.async_add_executor_job(self._try_login)
            if result == "SUCCESS":
                return await self._create_entry_from_client()
            if result == "MFA_REQUIRED":
                return await self.async_step_mfa()
            if result in ("AUTH_ERROR", "CONNECTION_ERROR", "RATE_LIMIT"):
                errors["base"] = result.lower()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    def _try_login(self) -> str:
        """Attempt login with garminconnect in background executor."""
        try:
            self._garmin = Garmin(
                self._email,
                self._password,
                prompt_mfa=self._prompt_mfa_callback,
            )
            self._garmin.login()
            return "SUCCESS"
        except GarminConnectAuthenticationError:
            # Check if this was caused by an MFA challenge waiting
            try:
                msg = self._mfa_out_queue.get_nowait()
                if msg == "MFA_NEEDED":
                    return "MFA_REQUIRED"
            except queue.Empty:
                pass
            return "AUTH_ERROR"
        except GarminConnectTooManyRequestsError:
            return "RATE_LIMIT"
        except GarminConnectConnectionError:
            return "CONNECTION_ERROR"
        except Exception as err:
            _LOGGER.exception("Unexpected error during Garmin login: %s", err)
            # Check if MFA was requested right before exception
            try:
                msg = self._mfa_out_queue.get_nowait()
                if msg == "MFA_NEEDED":
                    return "MFA_REQUIRED"
            except queue.Empty:
                pass
            return "AUTH_ERROR"

    async def async_step_mfa(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step to prompt user for 2FA / MFA code."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            mfa_code = user_input["mfa_code"]
            self._mfa_in_queue.put(mfa_code)

            # Re-attempt or complete login
            result = await self.hass.async_add_executor_job(self._complete_mfa_login)
            if result == "SUCCESS":
                return await self._create_entry_from_client()
            errors["base"] = "invalid_mfa"

        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema({
                vol.Required("mfa_code"): str,
            }),
            errors=errors,
        )

    def _complete_mfa_login(self) -> str:
        """Finish login after MFA code is provided."""
        try:
            if self._garmin and self._garmin.client.is_authenticated:
                return "SUCCESS"
            return "AUTH_ERROR"
        except Exception:
            return "AUTH_ERROR"

    async def _create_entry_from_client(self) -> FlowResult:
        """Complete the config flow and create entry with tokens."""
        di_token = self._garmin.client.di_token
        client = GarminBounceApiClient(di_token)

        # Exchange IT token to verify GCS access
        it_token = await self.hass.async_add_executor_job(client.exchange_it_token)

        await self.async_set_unique_id(self._email.lower())
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Garmin Jr. ({self._email})",
            data={
                CONF_EMAIL: self._email,
                CONF_DI_TOKEN: di_token,
                CONF_IT_TOKEN: it_token,
            },
        )
