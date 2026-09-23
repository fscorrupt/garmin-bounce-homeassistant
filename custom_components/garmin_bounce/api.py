import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import requests

from .const import (
    URL_TOKEN_EXCHANGE,
    URL_VIVOKID_FAMILY_INFO,
    URL_VIVOKID_SUBSCRIPTION,
    URL_VIVOKID_ACTIVITY,
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


def semicircles_to_degrees(semicircles: Optional[int]) -> Optional[float]:
    """Convert Garmin semicircles to standard decimal degrees."""
    if semicircles is None:
        return None
    return round(semicircles * (180.0 / 2**31), 6)


class GarminBounceApiClient:
    """Handles communication with Garmin Vivokid and GCS endpoints."""

    def __init__(self, di_token: str, it_token: Optional[str] = None) -> None:
        """Initialize the API client."""
        self._di_token = di_token
        self._it_token = it_token

    @property
    def di_token(self) -> str:
        """Return current DI token."""
        return self._di_token

    @property
    def it_token(self) -> Optional[str]:
        """Return current IT token."""
        return self._it_token

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
        if resp.status_code != 200:
            _LOGGER.error("Failed to exchange IT token (HTTP %s): %s", resp.status_code, resp.text)
            raise RuntimeError(f"IT token exchange failed: HTTP {resp.status_code}")

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

    def get_family_info(self) -> Dict[str, Any]:
        """Fetch family and children profiles from vivokidapi."""
        resp = requests.get(
            URL_VIVOKID_FAMILY_INFO,
            headers=self._get_vivokid_headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch family info: HTTP {resp.status_code}")
        return resp.json()

    def get_subscription_status(self, device_id: str, family_id: int) -> Dict[str, Any]:
        """Fetch LTE subscription status for a device."""
        url = f"{URL_VIVOKID_SUBSCRIPTION}?deviceId={device_id}&familyId={family_id}"
        resp = requests.get(url, headers=self._get_vivokid_headers(), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        _LOGGER.warning("Could not fetch subscription for device %s (HTTP %s)", device_id, resp.status_code)
        return {"status": "UNKNOWN", "activeForThisFamily": False}

    def get_daily_activity(self, kid_id: int, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Fetch daily activity summary (steps, goal) for a kid."""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        url = URL_VIVOKID_ACTIVITY.format(kid_id=kid_id, date=date_str)
        resp = requests.get(url, headers=self._get_vivokid_headers(), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return {}

    def get_trackpoints(self, kid_connect_id: int, days_back: int = 7) -> List[Dict[str, Any]]:
        """Fetch GPS trackpoints and battery telemetry from GCS."""
        begin_iso = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        url = f"{URL_GCS_TRACKPOINTS}?kidProfileId={kid_connect_id}&begin={begin_iso}&limit=10"
        
        try:
            resp = requests.get(url, headers=self._get_gcs_headers(), timeout=15)
            if resp.status_code == 401:
                # Token may have expired, re-exchange once
                _LOGGER.info("GCS token expired, attempting re-exchange...")
                self.exchange_it_token()
                resp = requests.get(url, headers=self._get_gcs_headers(), timeout=15)

            if resp.status_code == 200:
                return resp.json()
            _LOGGER.warning("Trackpoint fetch returned HTTP %s: %s", resp.status_code, resp.text)
        except Exception as err:
            _LOGGER.error("Error fetching trackpoints for %s: %s", kid_connect_id, err)
        return []

    def request_location_update(self, device_id: str) -> bool:
        """Send an LTE wake-up instruction to the Bounce 2 watch to request an instant GPS fix."""
        url = URL_GCS_UPDATE_LOCATION.format(device_id=device_id)
        try:
            resp = requests.post(url, headers=self._get_gcs_headers(), timeout=15)
            if resp.status_code == 401:
                self.exchange_it_token()
                resp = requests.post(url, headers=self._get_gcs_headers(), timeout=15)

            if resp.status_code == 200:
                _LOGGER.info("Location update instruction sent to device %s successfully", device_id)
                return True
            _LOGGER.warning("Failed to send location update to %s (HTTP %s): %s", device_id, resp.status_code, resp.text)
        except Exception as err:
            _LOGGER.error("Error dispatching location update to %s: %s", device_id, err)
        return False

    def start_live_track(self, device_id: str) -> bool:
        """Send a start LiveTrack instruction to the Bounce 2 watch over LTE."""
        url = URL_GCS_START_LIVE_TRACK.format(device_id=device_id)
        try:
            resp = requests.post(url, headers=self._get_gcs_headers(), timeout=15)
            if resp.status_code == 401:
                self.exchange_it_token()
                resp = requests.post(url, headers=self._get_gcs_headers(), timeout=15)

            if resp.status_code == 200:
                _LOGGER.info("Start LiveTrack instruction sent to device %s successfully", device_id)
                return True
            _LOGGER.warning("Failed to start LiveTrack on %s (HTTP %s): %s", device_id, resp.status_code, resp.text)
        except Exception as err:
            _LOGGER.error("Error starting LiveTrack on %s: %s", device_id, err)
        return False

    def get_messages(self, after_iso: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetch family and direct messages from GCS messaging service."""
        if not after_iso:
            after_iso = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        url = f"{URL_GCS_GET_MESSAGES}?after={after_iso}&limit={limit}&audioMediaType=audio/ogg"
        try:
            resp = requests.get(url, headers=self._get_gcs_headers(), timeout=15)
            if resp.status_code == 401:
                self.exchange_it_token()
                resp = requests.get(url, headers=self._get_gcs_headers(), timeout=15)

            if resp.status_code == 200:
                return resp.json().get("messages", [])
            _LOGGER.warning("Failed to fetch messages (HTTP %s): %s", resp.status_code, resp.text)
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
            resp = requests.post(url, headers=self._get_gcs_headers(), json=payload, timeout=15)
            if resp.status_code == 401:
                self.exchange_it_token()
                resp = requests.post(url, headers=self._get_gcs_headers(), json=payload, timeout=15)

            if resp.status_code in (200, 201):
                _LOGGER.info("Message sent successfully (ID: %s)", message_id)
                return True
            _LOGGER.warning("Failed to send message (HTTP %s): %s", resp.status_code, resp.text)
        except Exception as err:
            _LOGGER.error("Error sending message: %s", err)
        return False

    def get_message_content(self, message_id: str) -> Optional[bytes]:
        """Download raw media content (audio/ogg or emoji sound) for a message."""
        url = URL_GCS_MESSAGE_CONTENT.format(message_id=message_id)
        try:
            resp = requests.get(url, headers=self._get_gcs_headers(), timeout=20)
            if resp.status_code == 401:
                self.exchange_it_token()
                resp = requests.get(url, headers=self._get_gcs_headers(), timeout=20)

            if resp.status_code == 200:
                return resp.content
            _LOGGER.warning("Failed to download message content for %s (HTTP %s)", message_id, resp.status_code)
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

        # Do not include Content-Type header so requests sets multipart boundary automatically
        headers = {
            "Authorization": f"Bearer {self._it_token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        files = {"audio": ("voice.ogg", audio_bytes, "audio/ogg")}

        try:
            resp = requests.post(url, headers=headers, files=files, timeout=30)
            if resp.status_code == 401:
                self.exchange_it_token()
                headers["Authorization"] = f"Bearer {self._it_token}"
                resp = requests.post(url, headers=headers, files=files, timeout=30)

            if resp.status_code in (200, 201):
                _LOGGER.info("Audio message sent successfully (ID: %s)", message_id)
                return True
            _LOGGER.warning("Failed to send audio message (HTTP %s): %s", resp.status_code, resp.text)
        except Exception as err:
            _LOGGER.error("Error sending audio message: %s", err)
        return False

