"""DataUpdateCoordinator for Garmin Bounce."""
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GarminBounceApiClient, semicircles_to_degrees
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GarminBounceDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching Garmin Bounce and Jr. data from the cloud."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: GarminBounceApiClient,
        update_interval: Optional[timedelta] = None,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval or DEFAULT_SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch all data from Garmin endpoints."""
        try:
            return await self.hass.async_add_executor_job(self._update_data_sync)
        except Exception as err:
            _LOGGER.exception("Error communicating with Garmin API: %s", err)
            raise UpdateFailed(f"Error communicating with Garmin API: {err}") from err

    def _update_data_sync(self) -> Dict[str, Any]:
        """Synchronously retrieve family, activity, tracker telemetry, and messages."""
        family_info = self.api.get_family_info()
        families = family_info.get("families", [])

        # Fetch recent messages (guardian family messages endpoint)
        raw_messages = self.api.get_messages(limit=50)

        # Prepare local storage directory for voice messages in /config/www/garmin_bounce
        audio_dir = self.hass.config.path("www", "garmin_bounce")
        try:
            os.makedirs(audio_dir, exist_ok=True)
        except Exception as err:
            _LOGGER.debug("Could not create audio cache directory %s: %s", audio_dir, err)

        # Pre-cache audio files for audio/ogg messages
        message_audio_urls: Dict[str, str] = {}
        for msg in raw_messages:
            m_id = msg.get("messageId")
            m_type = msg.get("mediaType", "")
            if m_id and m_type == "audio/ogg":
                audio_path = os.path.join(audio_dir, f"{m_id}.ogg")
                if not os.path.exists(audio_path):
                    audio_content = self.api.get_message_content(m_id)
                    if audio_content:
                        try:
                            with open(audio_path, "wb") as f:
                                f.write(audio_content)
                            message_audio_urls[m_id] = f"/local/garmin_bounce/{m_id}.ogg"
                        except Exception as write_err:
                            _LOGGER.warning("Could not write audio message %s: %s", m_id, write_err)
                else:
                    message_audio_urls[m_id] = f"/local/garmin_bounce/{m_id}.ogg"

        data: Dict[str, Any] = {
            "family_info": family_info,
            "devices": {},
            "raw_messages": raw_messages,
        }

        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        for fam in families:
            family_id = fam.get("familyId")
            kids = fam.get("kids", [])

            for kid in kids:
                kid_id = kid.get("id") or kid.get("kidProfileId")
                connect_id = kid.get("connectId")
                device_id = kid.get("deviceId")
                kid_name = kid.get("name") or kid.get("displayName") or "Child"

                if not device_id or not connect_id:
                    continue

                # 1. Fetch LTE subscription status
                subscription = self.api.get_subscription_status(device_id, family_id)

                # 2. Fetch daily activity (today and fallback to yesterday if unsynced)
                activity_today = self.api.get_daily_activity(kid_id, today_str)
                activity_yesterday = self.api.get_daily_activity(kid_id, yesterday_str)

                steps_today = activity_today.get("steps")
                steps_goal = activity_today.get("stepsGoal") or activity_yesterday.get("stepsGoal") or 0
                last_sync_date = activity_today.get("lastSyncDate") or activity_yesterday.get("lastSyncDate")

                # 3. Fetch latest trackpoints (GPS, battery, telemetry)
                trackpoints = self.api.get_trackpoints(connect_id, days_back=7)
                latest_point: Dict[str, Any] = {}

                if trackpoints:
                    tp = trackpoints[0]
                    pos = tp.get("position", {})
                    lat_semi = pos.get("lat") or pos.get("latitudeSemicircles")
                    lon_semi = pos.get("lon") or pos.get("longitudeSemicircles")

                    latest_point = {
                        "latitude": semicircles_to_degrees(lat_semi),
                        "longitude": semicircles_to_degrees(lon_semi),
                        "battery_level": tp.get("batteryLevel"),
                        "battery_charging": tp.get("isBatteryCharging", False),
                        "accuracy": tp.get("accuracy") or tp.get("accuracyMeters"),
                        "altitude": tp.get("altitude"),
                        "speed": tp.get("speed") or tp.get("speedMetersPerSecond"),
                        "satellite_count": tp.get("satelliteCount"),
                        "fix_type": tp.get("fixType"),
                        "date_time": tp.get("dateTime"),
                        "reported_time": tp.get("reportedTime"),
                    }

                # 4. Filter and structure chat history for this child
                child_chat: List[Dict[str, Any]] = []
                for msg in raw_messages:
                    from_pk = msg.get("fromUserProfilePk")
                    to_pk = msg.get("toUserProfilePk")
                    m_id = msg.get("messageId", "")
                    m_type = msg.get("mediaType", "text/plain")
                    is_audio = (m_type == "audio/ogg")
                    raw_text = msg.get("messageText") or ""

                    # Check if relevant to this child (direct message to/from or family message)
                    if from_pk == connect_id:
                        direction = "incoming"
                        sender = kid_name
                        display_text = "[Sprachnachricht]" if is_audio else (raw_text if raw_text else "[Sticker]")
                    elif to_pk == connect_id:
                        direction = "outgoing"
                        sender = "Eltern / Home Assistant"
                        display_text = "[Sprachnachricht]" if is_audio else raw_text
                    elif to_pk is None:
                        # Family group message
                        direction = "family"
                        sender = kid_name if from_pk == connect_id else "Familienchat"
                        display_text = "[Sprachnachricht]" if is_audio else (raw_text if raw_text else "[Sticker]")
                    else:
                        continue

                    child_chat.append({
                        "message_id": m_id,
                        "timestamp": msg.get("createDateTime"),
                        "direction": direction,
                        "sender": sender,
                        "text": display_text,
                        "media_type": m_type,
                        "is_audio": is_audio,
                        "audio_url": message_audio_urls.get(m_id),
                    })

                # Sort newest first
                child_chat.sort(key=lambda m: m.get("timestamp") or "", reverse=True)
                last_message = child_chat[0] if child_chat else None

                data["devices"][device_id] = {
                    "kid_id": kid_id,
                    "kid_name": kid_name,
                    "connect_id": connect_id,
                    "device_id": device_id,
                    "family_id": family_id,
                    "part_number": kid.get("devicePartNumber") or "Garmin Bounce",
                    "has_lte": kid.get("hasLteDevice", False),
                    "steps_record": kid.get("stepsRecord") or 0,
                    "steps_today": steps_today if steps_today is not None else 0,
                    "steps_yesterday": activity_yesterday.get("steps") or 0,
                    "steps_goal": steps_goal,
                    "last_sync_date": last_sync_date,
                    "subscription": subscription,
                    "telemetry": latest_point,
                    "chat_history": child_chat[:20],
                    "last_message": last_message,
                }

        return data

