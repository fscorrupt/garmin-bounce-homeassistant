"""Config flow for Garmin Bounce integration."""
import json
import logging
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

from .const import (
    DOMAIN,
    CONF_DI_TOKEN,
    CONF_IT_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
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

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle initial step where user provides email and password or token JSON."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL].strip()
            self._password = user_input.get(CONF_PASSWORD, "")
            token_json = user_input.get("token_json", "").strip()

            # 1. Fast Token Login (bypasses Garmin SSO 429 IP rate limits)
            if token_json:
                try:
                    data = json.loads(token_json)
                    di_token = data.get("di_token") or data.get("access_token")
                    if not di_token:
                        errors["base"] = "auth_error"
                    else:
                        client = GarminBounceApiClient(di_token)
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
                except Exception as err:
                    _LOGGER.warning("Token login parsing error: %s", err)
                    errors["base"] = "auth_error"

            # 2. Standard SSO Login with Password & MFA
            elif not self._password:
                errors["base"] = "auth_error"
            else:
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
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional("token_json", default=""): str,
            }),
            errors=errors,
        )

    def _try_login(self) -> str:
        """Attempt initial login with garminconnect returning early on MFA."""
        try:
            self._garmin = Garmin(
                self._email,
                self._password,
                return_on_mfa=True,
            )
            mfa_status, _ = self._garmin.login()
            if mfa_status == "needs_mfa":
                _LOGGER.info("Garmin 2FA/MFA challenge triggered, requesting code from user")
                return "MFA_REQUIRED"

            if self._garmin.client.is_authenticated:
                return "SUCCESS"
            return "AUTH_ERROR"
        except GarminConnectAuthenticationError as err:
            _LOGGER.warning("Garmin authentication error: %s", err)
            return "AUTH_ERROR"
        except GarminConnectTooManyRequestsError:
            _LOGGER.warning("Garmin rate limit (429) hit")
            return "RATE_LIMIT"
        except GarminConnectConnectionError as err:
            _LOGGER.warning("Garmin connection error: %s", err)
            return "CONNECTION_ERROR"
        except Exception as err:
            _LOGGER.exception("Unexpected error during Garmin login: %s", err)
            return "AUTH_ERROR"

    async def async_step_mfa(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step to prompt user for 2FA / MFA verification code."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            mfa_code = user_input["mfa_code"].strip()

            result = await self.hass.async_add_executor_job(self._complete_mfa_login, mfa_code)
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

    def _complete_mfa_login(self, mfa_code: str) -> str:
        """Finish login after MFA code is provided."""
        try:
            if not self._garmin:
                return "AUTH_ERROR"

            self._garmin.resume_login(None, mfa_code)
            if self._garmin.client.is_authenticated:
                return "SUCCESS"
            return "AUTH_ERROR"
        except Exception as err:
            _LOGGER.warning("MFA code verification failed: %s", err)
            return "INVALID_MFA"

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

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return GarminBounceOptionsFlowHandler(config_entry)


class GarminBounceOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Garmin Bounce."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=15, max=1800)),
                }
            ),
        )
