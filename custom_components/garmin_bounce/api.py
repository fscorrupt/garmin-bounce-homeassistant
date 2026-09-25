import base64
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional
import requests

from .const import (
    URL_TOKEN_EXCHANGE,
    URL_DI_OAUTH_TOKEN,
    URL_VIVOKID_FAMILY_INFO,
    URL_VIVOKID_SUBSCRIPTION,
    URL_VIVOKID_ACTIVITY,
    URL_VIVOKID_CANNED_MESSAGES,
    URL_VIVOKID_GEOFENCES,
    URL_CONNECT_DEVICE_SETTINGS,
    URL_GCS_TRACKPOINTS,
    URL_GCS_UPDATE_LOCATION,
    URL_GCS_START_LIVE_TRACK,
    URL_GCS_MESSAGES_USER,
    URL_GCS_MESSAGES_FAMILY,
    URL_GCS_GET_MESSAGES,
    URL_GCS_MESSAGE_CONTENT,
    URL_GCS_MESSAGES_USER_FILE,
    URL_GCS_MESSAGES_FAMILY_FILE,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class GarminBounceApiError(Exception):
    """Base exception for Garmin Bounce API errors."""


class GarminAuthError(GarminBounceApiError):
    """Exception raised when Garmin authentication fails or token cannot be refreshed."""


def semicircles_to_degrees(semicircles: Optional[int]) -> Optional[float]:
    """Convert Garmin semicircles to standard decimal degrees."""
    if semicircles is None:
        return None
    return round(semicircles * (180.0 / 2**31), 6)


def is_jwt_expired_or_expiring_soon(token: str, buffer_seconds: int = 900) -> bool:
    """Check if a JWT access token is expired or within buffer_seconds of expiration."""
    if not token or not isinstance(token, str):
        return True
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return True
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
        exp = float(payload.get("exp", 0))
        return time.time() > (exp - buffer_seconds)
    except Exception:
        return False


class GarminBounceApiClient:
    """Handles communication with Garmin Vivokid and GCS endpoints."""

    def __init__(
        self,
        di_token: str,
        it_token: Optional[str] = None,
        token_data: Optional[Dict[str, Any]] = None,
        on_tokens_updated: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        """Initialize the API client."""
        self._di_token = di_token
        self._it_token = it_token
        self._token_data: Dict[str, Any] = dict(token_data) if token_data else {}
        self._on_tokens_updated = on_tokens_updated
        self._jr_di_token: Optional[str] = None
        self._kid_tokens: Dict[int, str] = {}
        self._kid_token_expires: Dict[int, float] = {}
        self._lock = threading.Lock()

        if self._di_token and "di_token" not in self._token_data:
            self._token_data["di_token"] = self._di_token
        if "di_client_id" not in self._token_data:
            self._token_data["di_client_id"] = "GARMIN_CONNECT_MOBILE_ANDROID_DI_2025Q2"

    @property
    def di_token(self) -> str:
        """Return current DI token."""
        return self._di_token

    @property
    def it_token(self) -> Optional[str]:
        """Return current IT token."""
        return self._it_token

    @property
    def token_data(self) -> Dict[str, Any]:
        """Return token data dictionary."""
        return self._token_data

    def refresh_tokens(self) -> bool:
        """
        Refresh DI token using refresh token, re-exchange IT token, and invoke callback.
        """
        with self._lock:
            refresh_token = self._token_data.get("di_refresh_token")
            client_id = self._token_data.get("di_client_id") or "GARMIN_CONNECT_MOBILE_ANDROID_DI_2025Q2"

            if not refresh_token:
                _LOGGER.warning("No refresh token available to refresh Garmin DI token")
                raise GarminAuthError("No refresh token available. Re-authentication required.")

            headers = {
                "Authorization": "Basic " + base64.b64encode(f"{client_id}:".encode()).decode(),
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-cache",
                "User-Agent": USER_AGENT,
            }
            data = {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
            }

            try:
                resp = requests.post(URL_DI_OAUTH_TOKEN, headers=headers, data=data, timeout=30)
            except Exception as err:
                _LOGGER.error("Network error while refreshing Garmin token: %s", err)
                raise GarminBounceApiError(f"Network error refreshing token: {err}") from err

            if resp.status_code != 200:
                _LOGGER.error("Garmin DI token refresh failed (HTTP %s): %s", resp.status_code, resp.text)
                raise GarminAuthError(f"Garmin token refresh failed (HTTP {resp.status_code}). Please re-authenticate.")

            res = resp.json()
            new_di_token = res.get("access_token")
            new_refresh_token = res.get("refresh_token") or refresh_token

            self._di_token = new_di_token
            self._token_data["di_token"] = new_di_token
            self._token_data["di_refresh_token"] = new_refresh_token
            self._token_data["di_client_id"] = client_id

            # Clear cached tokens derived from the old DI token
            self._jr_di_token = None
            self._kid_tokens.clear()
            self._kid_token_expires.clear()

            # Exchange new IT token
            self.exchange_it_token()

            _LOGGER.info("Garmin DI and IT tokens refreshed successfully")

            if self._on_tokens_updated:
                try:
                    self._on_tokens_updated(self._token_data)
                except Exception as err:
                    _LOGGER.warning("Error invoking on_tokens_updated callback: %s", err)

            return True

    def check_and_refresh_token(self, buffer_seconds: int = 900) -> bool:
        """Check if DI token is expired or expiring soon, and refresh proactively."""
        if not self._di_token or is_jwt_expired_or_expiring_soon(self._di_token, buffer_seconds):
            if self._token_data.get("di_refresh_token"):
                _LOGGER.info("Garmin DI token is expired or expiring soon. Refreshing proactively...")
                return self.refresh_tokens()
        return False

    def exchange_it_token(self) -> str:
        """
        Exchange DI access token for a GCS IT OAuth2 Bearer token.
        This provides GCS_FAMILY_TRACKER and GCS_DEVICE_INSTRUCTION permissions.
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        data = {
            "client_id": "VIVOFIT_JR_ANDROID",
            "connect_access_token": self._di_token,
        }

        resp = requests.post(URL_TOKEN_EXCHANGE, headers=headers, data=data, timeout=15)
        if resp.status_code == 401 and self._token_data.get("di_refresh_token"):
            _LOGGER.info("DI token rejected during IT exchange, attempting refresh...")
            self.refresh_tokens()
            data["connect_access_token"] = self._di_token
            resp = requests.post(URL_TOKEN_EXCHANGE, headers=headers, data=data, timeout=15)

        if resp.status_code != 200:
            _LOGGER.error("Failed to exchange IT token (HTTP %s): %s", resp.status_code, resp.text)
            if resp.status_code == 401:
                raise GarminAuthError(f"IT token exchange unauthorized: HTTP {resp.status_code}")
            raise GarminBounceApiError(f"IT token exchange failed: HTTP {resp.status_code}")

        token_data = resp.json()
        self._it_token = token_data["access_token"]
        return self._it_token

    def _get_vivokid_headers(self) -> Dict[str, str]:
        """Headers for vivokidapi.garmin.com."""
        return {
            "Authorization": f"Bearer {self._di_token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    def _get_gcs_headers(self) -> Dict[str, str]:
        """Headers for api.gcs.garmin.com."""
        if not self._it_token:
            self.exchange_it_token()
        return {
            "Authorization": f"Bearer {self._it_token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    def _request_with_retry(
        self,
        method: str,
        url: str,
        is_gcs: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform an HTTP request with automatic token refresh on 401."""
        self.check_and_refresh_token()
        headers = self._get_gcs_headers() if is_gcs else self._get_vivokid_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        if "timeout" not in kwargs:
            kwargs["timeout"] = 15

        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            _LOGGER.info("HTTP 401 received for %s; attempting token refresh and retry...", url)
            if self._token_data.get("di_refresh_token"):
                self.refresh_tokens()
                headers = self._get_gcs_headers() if is_gcs else self._get_vivokid_headers()
                resp = requests.request(method, url, headers=headers, **kwargs)
            elif is_gcs:
                self.exchange_it_token()
                headers = self._get_gcs_headers()
                resp = requests.request(method, url, headers=headers, **kwargs)

        return resp

    def get_family_info(self) -> Dict[str, Any]:
        """Fetch family and children profiles from vivokidapi."""
        resp = self._request_with_retry("GET", URL_VIVOKID_FAMILY_INFO)
        if resp.status_code == 401:
            raise GarminAuthError("Failed to authenticate with Garmin API (HTTP 401). Please re-authenticate.")
        if resp.status_code != 200:
            raise GarminBounceApiError(f"Failed to fetch family info: HTTP {resp.status_code}")
        return resp.json()

    def get_subscription_status(self, device_id: str, family_id: int) -> Dict[str, Any]:
        """Fetch LTE subscription status for a device."""
        url = f"{URL_VIVOKID_SUBSCRIPTION}?deviceId={device_id}&familyId={family_id}"
        resp = self._request_with_retry("GET", url)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            raise GarminAuthError(f"Unauthorized fetching subscription status for {device_id} (HTTP 401)")
        _LOGGER.warning("Could not fetch subscription for device %s (HTTP %s)", device_id, resp.status_code)
        return {"status": "UNKNOWN", "activeForThisFamily": False}

    def get_daily_activity(self, kid_id: int, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Fetch daily activity summary (steps, goal) for a kid."""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        url = URL_VIVOKID_ACTIVITY.format(kid_id=kid_id, date=date_str)
        resp = self._request_with_retry("GET", url)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            raise GarminAuthError(f"Unauthorized fetching daily activity for kid {kid_id} (HTTP 401)")
        return {}

    def get_trackpoints(self, kid_connect_id: int) -> List[Dict[str, Any]]:
        """Fetch latest GPS trackpoints and battery telemetry from GCS."""
        # Query recent window first (last 24h), fallback to 72h or 7 days if watch was offline/asleep
        for hours_back in (24, 72, 168):
            begin_iso = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )
            url = f"{URL_GCS_TRACKPOINTS}?kidProfileId={kid_connect_id}&begin={begin_iso}&limit=50"
            try:
                resp = self._request_with_retry("GET", url, is_gcs=True)
                if resp.status_code == 401:
                    raise GarminAuthError(f"Unauthorized fetching trackpoints for {kid_connect_id} (HTTP 401)")

                if resp.status_code == 200:
                    points = resp.json()
                    if points:
                        # Page forward if limit=50 was reached so we reach the absolute newest trackpoints
                        while len(points) >= 50:
                            last_time = points[-1].get("reportedTime") or points[-1].get("dateTime")
                            if not last_time:
                                break
                            next_url = f"{URL_GCS_TRACKPOINTS}?kidProfileId={kid_connect_id}&begin={last_time}&limit=50"
                            resp_next = self._request_with_retry("GET", next_url, is_gcs=True)
                            if resp_next.status_code != 200:
                                break
                            next_page = resp_next.json()
                            new_points = [
                                p for p in next_page
                                if (p.get("reportedTime") or p.get("dateTime")) > last_time
                            ]
                            if not new_points:
                                break
                            points.extend(new_points)
                            if len(next_page) < 50:
                                break
                        return points
                else:
                    _LOGGER.warning("Trackpoint fetch returned HTTP %s: %s", resp.status_code, resp.text)
            except GarminAuthError:
                raise
            except Exception as err:
                _LOGGER.error("Error fetching trackpoints for %s: %s", kid_connect_id, err)
                break
        return []

    def request_location_update(self, device_id: str) -> bool:
        """Send an LTE wake-up instruction to the Bounce 2 watch to request an instant GPS fix."""
        url = URL_GCS_UPDATE_LOCATION.format(device_id=device_id)
        try:
            resp = self._request_with_retry("POST", url, is_gcs=True)
            if resp.status_code == 401:
                raise GarminAuthError(f"Unauthorized sending location update to {device_id} (HTTP 401)")

            if resp.status_code == 200:
                _LOGGER.info("Location update instruction sent to device %s successfully", device_id)
                return True
            _LOGGER.warning("Failed to send location update to %s (HTTP %s): %s", device_id, resp.status_code, resp.text)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error dispatching location update to %s: %s", device_id, err)
        return False

    def start_live_track(self, device_id: str) -> bool:
        """Send a start LiveTrack instruction to the Bounce 2 watch over LTE."""
        url = URL_GCS_START_LIVE_TRACK.format(device_id=device_id)
        try:
            resp = self._request_with_retry("POST", url, is_gcs=True)
            if resp.status_code == 401:
                raise GarminAuthError(f"Unauthorized starting LiveTrack on {device_id} (HTTP 401)")

            if resp.status_code == 200:
                _LOGGER.info("Start LiveTrack instruction sent to device %s successfully", device_id)
                return True
            _LOGGER.warning("Failed to start LiveTrack on %s (HTTP %s): %s", device_id, resp.status_code, resp.text)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error starting LiveTrack on %s: %s", device_id, err)
        return False

    def get_messages(self, after_iso: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetch family and direct messages from GCS messaging service."""
        if not after_iso:
            after_iso = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        url = f"{URL_GCS_GET_MESSAGES}?after={after_iso}&limit={limit}&audioMediaType=audio/ogg"
        try:
            resp = self._request_with_retry("GET", url, is_gcs=True)
            if resp.status_code == 401:
                raise GarminAuthError("Unauthorized fetching messages (HTTP 401)")

            if resp.status_code == 200:
                return resp.json().get("messages", [])
            _LOGGER.warning("Failed to fetch messages (HTTP %s): %s", resp.status_code, resp.text)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error fetching messages: %s", err)
        return []

    def send_text_message(self, message_text: str, to_connect_id: Optional[int] = None) -> bool:
        """
        Send a text message to a specific child's watch or the family group chat.
        If to_connect_id is provided, sends direct message. Otherwise sends to family chat.
        """
        message_id = str(uuid.uuid4())
        payload: Dict[str, Any] = {
            "messageId": message_id,
            "mediaType": "text/plain",
            "messageText": message_text,
        }
        if to_connect_id:
            payload["toUserProfilePk"] = to_connect_id
            url = URL_GCS_MESSAGES_USER
        else:
            url = URL_GCS_MESSAGES_FAMILY

        try:
            resp = self._request_with_retry("POST", url, is_gcs=True, json=payload)
            if resp.status_code == 401:
                raise GarminAuthError("Unauthorized sending message (HTTP 401)")

            if resp.status_code in (200, 201):
                _LOGGER.info("Message sent successfully (ID: %s)", message_id)
                return True
            _LOGGER.warning("Failed to send message (HTTP %s): %s", resp.status_code, resp.text)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error sending message: %s", err)
        return False

    def get_message_content(self, message_id: str) -> Optional[bytes]:
        """Download raw media content (audio/ogg or emoji sound) for a message."""
        url = URL_GCS_MESSAGE_CONTENT.format(message_id=message_id)
        try:
            resp = self._request_with_retry("GET", url, is_gcs=True, timeout=20)
            if resp.status_code == 401:
                raise GarminAuthError(f"Unauthorized downloading message content {message_id} (HTTP 401)")

            if resp.status_code == 200:
                return resp.content
            _LOGGER.warning("Failed to download message content for %s (HTTP %s)", message_id, resp.status_code)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error downloading content for message %s: %s", message_id, err)
        return None

    def send_audio_message(
        self, audio_bytes: bytes, to_connect_id: Optional[int] = None, locale: str = "de"
    ) -> bool:
        """Send an audio message (Ogg Opus) to a child's watch or the family group chat."""
        message_id = str(uuid.uuid4())
        if to_connect_id:
            url = f"{URL_GCS_MESSAGES_USER_FILE}?messageId={message_id}&toUserProfilePk={to_connect_id}&locale={locale}"
        else:
            url = f"{URL_GCS_MESSAGES_FAMILY_FILE}?messageId={message_id}&locale={locale}"

        files = {"audio": ("voice.ogg", audio_bytes, "audio/ogg")}

        try:
            resp = self._request_with_retry("POST", url, is_gcs=True, files=files, timeout=30)
            if resp.status_code == 401:
                raise GarminAuthError("Unauthorized sending audio message (HTTP 401)")

            if resp.status_code in (200, 201):
                _LOGGER.info("Audio message sent successfully (ID: %s)", message_id)
                return True
            _LOGGER.warning("Failed to send audio message (HTTP %s): %s", resp.status_code, resp.text)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error sending audio message: %s", err)
        return False

    def exchange_jr_di_token(self) -> str:
        """
        Exchange GCS IT token for a Garmin Junior DI OAuth token.
        This represents the parent in the Junior ecosystem.
        """
        if not self._it_token:
            self.exchange_it_token()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": self._it_token,
            "subject_token_type": "https://services.garmin.com/api/oauth/token",
            "client_id": "VIVOFIT_JR_ANDROID",
        }
        resp = requests.post(URL_DI_OAUTH_TOKEN, headers=headers, data=data, timeout=15)
        if resp.status_code == 401:
            self.exchange_it_token()
            data["subject_token"] = self._it_token
            resp = requests.post(URL_DI_OAUTH_TOKEN, headers=headers, data=data, timeout=15)

        if resp.status_code != 200:
            _LOGGER.error("Failed to exchange Junior DI token (HTTP %s): %s", resp.status_code, resp.text)
            if resp.status_code == 401:
                raise GarminAuthError(f"Junior DI token exchange unauthorized: HTTP {resp.status_code}")
            raise GarminBounceApiError(f"Junior DI token exchange failed: HTTP {resp.status_code}")

        self._jr_di_token = resp.json()["access_token"]
        return self._jr_di_token

    def exchange_kid_token(self, kid_connect_id: int) -> str:
        """
        Exchange Junior DI token for a Child-specific OAuth Bearer token.
        Allows managing device settings directly on the watch profile.
        """
        now = datetime.now(timezone.utc).timestamp()
        if kid_connect_id in self._kid_tokens:
            expires_at = self._kid_token_expires.get(kid_connect_id, 0)
            if now < (expires_at - 300):
                return self._kid_tokens[kid_connect_id]

        if not self._jr_di_token:
            self.exchange_jr_di_token()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        data = {
            "grant_type": "https://connectapi.garmin.com/di-oauth2-service/oauth/grant/gc_kid",
            "access_token": self._jr_di_token,
            "gc_kid_id": kid_connect_id,
            "client_id": "VIVOFIT_JR_ANDROID",
        }
        resp = requests.post(URL_DI_OAUTH_TOKEN, headers=headers, data=data, timeout=15)
        if resp.status_code == 401:
            # Refresh Junior DI token and retry once
            self.exchange_jr_di_token()
            data["access_token"] = self._jr_di_token
            resp = requests.post(URL_DI_OAUTH_TOKEN, headers=headers, data=data, timeout=15)

        if resp.status_code != 200:
            _LOGGER.error("Failed to exchange Kid token for %s (HTTP %s): %s", kid_connect_id, resp.status_code, resp.text)
            if resp.status_code == 401:
                raise GarminAuthError(f"Kid token exchange unauthorized: HTTP {resp.status_code}")
            raise GarminBounceApiError(f"Kid token exchange failed: HTTP {resp.status_code}")

        res = resp.json()
        token = res["access_token"]
        expires_in = res.get("expires_in", 86400)
        self._kid_tokens[kid_connect_id] = token
        self._kid_token_expires[kid_connect_id] = now + expires_in
        return token

    def _get_kid_headers(self, kid_connect_id: int) -> Dict[str, str]:
        """Headers for kid device-service endpoints."""
        token = self.exchange_kid_token(kid_connect_id)
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_device_settings(self, device_id: str, kid_connect_id: int) -> Dict[str, Any]:
        """Fetch full device settings for the watch using kid credentials."""
        url = URL_CONNECT_DEVICE_SETTINGS.format(device_id=device_id)
        try:
            headers = self._get_kid_headers(kid_connect_id)
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 401:
                self._kid_tokens.pop(kid_connect_id, None)
                headers = self._get_kid_headers(kid_connect_id)
                resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                raise GarminAuthError(f"Unauthorized fetching device settings for {device_id} (HTTP 401)")
            _LOGGER.warning("Failed to fetch settings for device %s (HTTP %s): %s", device_id, resp.status_code, resp.text)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error fetching device settings for %s: %s", device_id, err)
        return {}

    def update_device_settings(
        self, device_id: str, kid_connect_id: int, new_settings: Dict[str, Any]
    ) -> bool:
        """Update device settings via PUT using kid credentials."""
        url = URL_CONNECT_DEVICE_SETTINGS.format(device_id=device_id)
        try:
            headers = self._get_kid_headers(kid_connect_id)
            resp = requests.put(url, headers=headers, json=new_settings, timeout=15)
            if resp.status_code == 401:
                self._kid_tokens.pop(kid_connect_id, None)
                headers = self._get_kid_headers(kid_connect_id)
                resp = requests.put(url, headers=headers, json=new_settings, timeout=15)

            if resp.status_code in (200, 204):
                _LOGGER.info("Device settings updated successfully for %s", device_id)
                return True
            if resp.status_code == 401:
                raise GarminAuthError(f"Unauthorized updating device settings for {device_id} (HTTP 401)")
            _LOGGER.warning("Failed to update device settings for %s (HTTP %s): %s", device_id, resp.status_code, resp.text)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error updating device settings for %s: %s", device_id, err)
        return False

    def set_dnd_mode(self, device_id: str, kid_connect_id: int, enabled: bool) -> bool:
        """Toggle Do Not Disturb mode on the watch."""
        settings = self.get_device_settings(device_id, kid_connect_id)
        if not settings:
            return False
        settings["dndEnabled"] = bool(enabled)
        return self.update_device_settings(device_id, kid_connect_id, settings)

    def set_school_mode(self, device_id: str, kid_connect_id: int, mode: str) -> bool:
        """Set School Mode on the watch (OFF, RESTRICTED, ALL)."""
        settings = self.get_device_settings(device_id, kid_connect_id)
        if not settings:
            return False
        if "schoolMode" not in settings or not isinstance(settings["schoolMode"], dict):
            settings["schoolMode"] = {
                "startTime": 28800,
                "endTime": 46800,
                "days": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
            }
        settings["schoolMode"]["mode"] = mode.upper()
        return self.update_device_settings(device_id, kid_connect_id, settings)

    def get_canned_messages(self, kid_id: int) -> List[Dict[str, Any]]:
        """Fetch canned message templates for a kid from vivokidapi."""
        url = URL_VIVOKID_CANNED_MESSAGES.format(kid_id=kid_id)
        try:
            resp = self._request_with_retry("GET", url)
            if resp.status_code == 200:
                msgs = resp.json()
                if isinstance(msgs, list):
                    return sorted(msgs, key=lambda m: m.get("messageOrder", 0))
            if resp.status_code == 401:
                raise GarminAuthError(f"Unauthorized fetching canned messages for kid {kid_id} (HTTP 401)")
            _LOGGER.warning("Failed to fetch canned messages for kid %s (HTTP %s)", kid_id, resp.status_code)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error fetching canned messages for %s: %s", kid_id, err)
        return []

    def get_geofences(self, kid_id: int) -> List[Dict[str, Any]]:
        """Fetch safety zones (geofences) configured for a kid from vivokidapi."""
        url = URL_VIVOKID_GEOFENCES.format(kid_id=kid_id)
        try:
            resp = self._request_with_retry("GET", url)
            if resp.status_code == 200:
                zones = resp.json()
                if isinstance(zones, list):
                    return zones
            if resp.status_code == 401:
                raise GarminAuthError(f"Unauthorized fetching geofences for kid {kid_id} (HTTP 401)")
            _LOGGER.warning("Failed to fetch geofences for kid %s (HTTP %s)", kid_id, resp.status_code)
        except GarminAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Error fetching geofences for %s: %s", kid_id, err)
        return []
