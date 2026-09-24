<p align="center">
  <img src="https://raw.githubusercontent.com/fscorrupt/garmin-bounce-homeassistant/main/icon.png" alt="Garmin Bounce Home Assistant" width="140" height="140">
  <img src="https://raw.githubusercontent.com/fscorrupt/garmin-bounce-homeassistant/main/icon.png" alt="Garmin Bounce Home Assistant" width="140" height="140">
</p>

# Garmin Bounce & Garmin Jr. - Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Custom component for Home Assistant to integrate the **Garmin Bounce 2** and Garmin Vivofit Jr. wearables. Supports real-time GPS tracking, two-way messaging, voice message playback, device modes (School Mode, Do Not Disturb), geofenced safety zones, activity telemetry, and on-demand LTE commands.
Custom component for Home Assistant to integrate the **Garmin Bounce 2** and Garmin Vivofit Jr. wearables. Supports real-time GPS tracking, two-way messaging, voice message playback, device modes (School Mode, Do Not Disturb), geofenced safety zones, activity telemetry, and on-demand LTE commands.

---

## Features
## Features

- **GPS Location Tracking**: Real-time position tracking (`device_tracker`), latitude, longitude, altitude, speed, fix type, and accuracy.
- **School Mode**: Monitor and switch School Mode (`OFF`, `RESTRICTED`, `ALL`) via switches, selects, and services.
- **Do Not Disturb (DND)**: Toggle and monitor Do Not Disturb on the watch (`switch.*_do_not_disturb`, `sensor.*_do_not_disturb_status`).
- **Safety Zones (Geofences)**: Automatic evaluation of Garmin-configured geofences (e.g. Zuhause, Schule, Hort, Oma) with exact distance calculations.
- **Two-Way Messaging**: Send direct text messages to the watch or to the family group chat, including interactive input helper support.
- **Quick Message Presets**: Send predefined canned message templates directly from a dropdown or card button.
- **Voice Message Playback**: Automatically caches incoming `.ogg` Opus audio messages for in-dashboard playback, and supports sending audio files.
- **Chat Transcript**: Full conversation history attribute on `sensor.*_last_message` tracking sender, direction, timestamp, and audio.
- **Battery & Telemetry**: Battery percentage, charging status, daily steps, step goals, all-time step records, satellite count, and LTE subscription status.
- **Remote LTE Commands**: Instant GPS wake-up ping (`button.*_refresh_location`) and LiveTrack continuous tracking session trigger.
- **Configurable Polling**: Custom cloud polling interval (15s to 1800s, default 60s) via Options Flow with zero watch battery consumption.
- **Authentication**: Supports Garmin SSO login including two-factor authentication (MFA/2FA) and direct token authentication.
- **GPS Location Tracking**: Real-time position tracking (`device_tracker`), latitude, longitude, altitude, speed, fix type, and accuracy.
- **School Mode**: Monitor and switch School Mode (`OFF`, `RESTRICTED`, `ALL`) via switches, selects, and services.
- **Do Not Disturb (DND)**: Toggle and monitor Do Not Disturb on the watch (`switch.*_do_not_disturb`, `sensor.*_do_not_disturb_status`).
- **Safety Zones (Geofences)**: Automatic evaluation of Garmin-configured geofences (e.g. Zuhause, Schule, Hort, Oma) with exact distance calculations.
- **Two-Way Messaging**: Send direct text messages to the watch or to the family group chat, including interactive input helper support.
- **Quick Message Presets**: Send predefined canned message templates directly from a dropdown or card button.
- **Voice Message Playback**: Automatically caches incoming `.ogg` Opus audio messages for in-dashboard playback, and supports sending audio files.
- **Chat Transcript**: Full conversation history attribute on `sensor.*_last_message` tracking sender, direction, timestamp, and audio.
- **Battery & Telemetry**: Battery percentage, charging status, daily steps, step goals, all-time step records, satellite count, and LTE subscription status.
- **Remote LTE Commands**: Instant GPS wake-up ping (`button.*_refresh_location`) and LiveTrack continuous tracking session trigger.
- **Configurable Polling**: Custom cloud polling interval (15s to 1800s, default 60s) via Options Flow with zero watch battery consumption.
- **Authentication**: Supports Garmin SSO login including two-factor authentication (MFA/2FA) and direct token authentication.

---

## Installation
## Installation

### Method 1: HACS (Recommended)

1. In Home Assistant, open **HACS** > **Integrations**.
2. Click the menu in the top right corner and select **Custom repositories**.
3. Add `https://github.com/fscorrupt/garmin-bounce-homeassistant` with category **Integration**.
1. In Home Assistant, open **HACS** > **Integrations**.
2. Click the menu in the top right corner and select **Custom repositories**.
3. Add `https://github.com/fscorrupt/garmin-bounce-homeassistant` with category **Integration**.
4. Search for **Garmin Bounce & Jr.** and click **Download**.
5. Restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/garmin_bounce` directory into your Home Assistant installation under `<config_dir>/custom_components/`.
1. Copy the `custom_components/garmin_bounce` directory into your Home Assistant installation under `<config_dir>/custom_components/`.
2. Restart Home Assistant.

---

## Configuration
## Configuration

### Initial Setup


1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Garmin Bounce & Jr.**.
3. Enter your Garmin Connect account credentials (**Email** and **Password**).
4. If two-factor authentication is enabled, enter the verification code sent to your email or phone.
5. The integration will automatically discover all families, kids, and Bounce watches registered to your account.

### Polling Interval (Options Flow)

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Garmin Bounce & Jr.**.
2. Click **Configure** (the gear icon).
3. Set the cloud polling interval in seconds (between `15` and `1800` seconds; default: `60`).
4. Click **Submit**. The integration reloads immediately with the new update interval.
3. Enter your Garmin Connect account credentials (**Email** and **Password**).
4. If two-factor authentication is enabled, enter the verification code sent to your email or phone.
5. The integration will automatically discover all families, kids, and Bounce watches registered to your account.

### Polling Interval (Options Flow)

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Garmin Bounce & Jr.**.
2. Click **Configure** (the gear icon).
3. Set the cloud polling interval in seconds (between `15` and `1800` seconds; default: `60`).
4. Click **Submit**. The integration reloads immediately with the new update interval.

> [!NOTE]
> Polling queries Garmin Cloud servers directly from Home Assistant. It does not communicate directly with the watch or drain its battery.
> [!NOTE]
> Polling queries Garmin Cloud servers directly from Home Assistant. It does not communicate directly with the watch or drain its battery.

---

## Available Entities
## Available Entities

| Platform | Entity Name | Description |
| :--- | :--- | :--- |
| `device_tracker` | `device_tracker.<child>_bounce_2` | Live GPS coordinates, altitude, speed, fix type, and safety zone attribute |
| `switch` | `switch.<child>_bounce_2_school_mode` | Toggle School Mode on/off |
| `switch` | `switch.<child>_bounce_2_do_not_disturb` | Toggle Do Not Disturb (DND) on/off |
| `select` | `select.<child>_bounce_2_quick_message` | Dropdown to send predefined message templates to the watch |
| `select` | `select.<child>_bounce_2_school_mode_setting` | Configure School Mode level (`OFF`, `RESTRICTED`, `ALL`) |
| `sensor` | `sensor.<child>_bounce_2_safety_zone` | Current zone name or nearest zone distance |
| `sensor` | `sensor.<child>_bounce_2_school_mode_status` | Current School Mode restriction state and schedule |
| `sensor` | `sensor.<child>_bounce_2_do_not_disturb_status` | Current DND state and vibration settings |
| `sensor` | `sensor.<child>_bounce_2_battery_level` | Battery percentage (0-100%) and charging state |
| `sensor` | `sensor.<child>_bounce_2_daily_steps` | Steps walked today and yesterday's steps |
| `sensor` | `sensor.<child>_bounce_2_step_goal` | Target daily step goal |
| `sensor` | `sensor.<child>_bounce_2_steps_record` | Personal all-time step record |
| `sensor` | `sensor.<child>_bounce_2_lte_status` | Subscription status (`ACTIVE`) |
| `sensor` | `sensor.<child>_bounce_2_gps_satellites` | Number of tracked GNSS satellites |
| `sensor` | `sensor.<child>_bounce_2_location_fix_type` | Fix method (`GPS`, `WFPS_ANCHOR`) |
| `sensor` | `sensor.<child>_bounce_2_last_sync` | Timestamp of last cloud sync |
| `sensor` | `sensor.<child>_bounce_2_last_message` | Latest message text, sender, direction, and full `chat_history` |
| `button` | `button.<child>_bounce_2_refresh_location` | Sends an LTE command to update GPS fix immediately |
| `button` | `button.<child>_bounce_2_start_livetrack` | Starts a continuous LiveTrack session over LTE |
| `button` | `button.<child>_bounce_2_poll_cloud_data` | Forces an immediate refresh of all cloud data |

---

## Services

### `garmin_bounce.send_message`

Sends a text message to a watch or the family group chat. Supports passing raw text or referencing an `input_text` helper entity (which is automatically cleared upon delivery).

```yaml
service: garmin_bounce.send_message
data:
  target: "child" # "child" or "family"
  message: "Das Essen ist fertig! Bitte komm jetzt nach Hause."
  # Or reference an input_text helper:
  # message: "input_text.garmin_bounce_message"
  # Or reference an input_text helper:
  # message: "input_text.garmin_bounce_message"
```

### `garmin_bounce.send_voice_message`

Sends an audio/voice recording (`.ogg` Opus format) to the watch.
### `garmin_bounce.send_voice_message`

Sends an audio/voice recording (`.ogg` Opus format) to the watch.

```yaml
service: garmin_bounce.send_voice_message
data:
  target: "child" # "child" or "family"
  target: "child" # "child" or "family"
  audio_file: "/local/garmin_bounce/reminder.ogg"
```

### `garmin_bounce.set_school_mode`
### `garmin_bounce.set_school_mode`

Configures the School Mode restriction state on the watch.
Configures the School Mode restriction state on the watch.

```yaml
service: garmin_bounce.set_school_mode
data:
  mode: "RESTRICTED" # "OFF", "RESTRICTED", or "ALL"
service: garmin_bounce.set_school_mode
data:
  mode: "RESTRICTED" # "OFF", "RESTRICTED", or "ALL"
```

### `garmin_bounce.set_dnd_mode`

Enables or disables Do Not Disturb mode on the watch.

### `garmin_bounce.set_dnd_mode`

Enables or disables Do Not Disturb mode on the watch.

```yaml
service: garmin_bounce.set_dnd_mode
data:
  enabled: true
service: garmin_bounce.set_dnd_mode
data:
  enabled: true
```

---

## Dashboard Cards

Ready-to-use Lovelace card configurations (both Mushroom-based and Native Lovelace) are available in [`HomeAssistant/dashboard_cards.yaml`](HomeAssistant/dashboard_cards.yaml).

Included features:
- Live GPS Map card
- Status chips (Battery, Daily Steps, LTE, Safety Zone)
- Mode toggles for School Mode and Do Not Disturb
- Action buttons for LTE GPS Locate, LiveTrack, and Cloud Sync
- Interactive manual text messaging via `input_text` helper
- Quick message preset selection and 1-click preset buttons
- Live conversation feed with audio player for voice messages

---

## Reverse Engineering

For technical details on the APK decompilation analysis, token exchange architecture, and REST API endpoints, see [`REVERSE_ENGINEERING.md`](REVERSE_ENGINEERING.md).

---

## Frequently Asked Questions

### Why does HACS show "(icon not available)" during search?
The HACS repository search overview checks the centralized Home Assistant brands repository for icons. Because custom repositories added manually are not in the central core catalog, HACS displays `(icon not available)` in the search list. Once installed, the integration icon displays normally under **Settings** > **Devices & Services** from the bundled component files.

---

## License
## License

Distributed under the MIT License. This project is independent and not affiliated with or endorsed by Garmin Ltd.
Distributed under the MIT License. This project is independent and not affiliated with or endorsed by Garmin Ltd.
