"""Constants for the Garmin Bounce & Jr. integration."""
from datetime import timedelta

DOMAIN = "garmin_bounce"
PLATFORMS = ["device_tracker", "sensor", "button"]

CONF_TOKEN_DATA = "token_data"
CONF_DI_TOKEN = "di_token"
CONF_IT_TOKEN = "it_token"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_SECONDS = 60
DEFAULT_SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)
USER_AGENT = "GarminJr/5.23 (Android)"

# Garmin API Endpoints
URL_TOKEN_EXCHANGE = "https://services.garmin.com/api/oauth/token?grant_type=connect2_exchange"
URL_VIVOKID_FAMILY_INFO = "https://vivokidapi.garmin.com/GCSVivokidServlet/v3/family/info"
URL_VIVOKID_SUBSCRIPTION = "https://vivokidapi.garmin.com/contact-service/subscription/status"
URL_VIVOKID_ACTIVITY = "https://vivokidapi.garmin.com/GCSVivokidServlet/v2/activity/summary/kid/{kid_id}/{date}"
URL_GCS_TRACKPOINTS = "https://api.gcs.garmin.com/tracker/family/api/v1/trackpoints"
URL_GCS_UPDATE_LOCATION = "https://api.gcs.garmin.com/device-instruction/api/v1/family/{device_id}/update-location"
URL_GCS_START_LIVE_TRACK = "https://api.gcs.garmin.com/device-instruction/api/v1/family/{device_id}/start-family-track"
URL_GCS_MESSAGES_USER = "https://api.gcs.garmin.com/messaging/family/api/v1/messages/user/text"
URL_GCS_MESSAGES_FAMILY = "https://api.gcs.garmin.com/messaging/family/api/v1/messages/family/text"
URL_GCS_GET_MESSAGES = "https://api.gcs.garmin.com/messaging/family/api/v1/guardian/messages"
URL_GCS_MESSAGE_CONTENT = "https://api.gcs.garmin.com/messaging/family/api/v1/messages/{message_id}/content"
URL_GCS_MESSAGES_USER_FILE = "https://api.gcs.garmin.com/messaging/family/api/v1/messages/user/file"
URL_GCS_MESSAGES_FAMILY_FILE = "https://api.gcs.garmin.com/messaging/family/api/v1/messages/family/file"

# Services & Attributes
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_SEND_VOICE_MESSAGE = "send_voice_message"
ATTR_MESSAGE = "message"
ATTR_TARGET = "target"
ATTR_AUDIO_FILE = "audio_file"
ATTR_DEVICE_ID = "device_id"

