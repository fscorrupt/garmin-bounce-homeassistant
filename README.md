<p align="center">
  <img src="https://raw.githubusercontent.com/fscorrupt/garmin-bounce-homeassistant/main/icon.png" alt="Garmin Bounce Home Assistant" width="160" height="160">
</p>

# Garmin Bounce & Garmin Jr. - Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Integrate your **Garmin Bounce 2** (and Garmin Vivofit Jr. smartwatches) directly into **Home Assistant**. Features live GPS location tracking, two-way messaging & family group chat, voice message playback, battery and step telemetry, and on-demand LTE wake-up commands.

---

## ✨ Features

- 📍 **GPS Device Tracker**: Real-time position tracking (`device_tracker`), latitude, longitude, altitude, speed, fix type, and accuracy.
- 💬 **Two-Way Messaging**: Send direct text messages to the watch or to the family group chat via `garmin_bounce.send_message`.
- 🎙️ **Voice Messages & Audio Playback**: Receive audio messages (`.ogg` Opus) from the watch, automatically cached for in-dashboard playback, and send voice recordings via `garmin_bounce.send_voice_message`.
- 📜 **Chat History**: Full message history attribute (`chat_history`) on `sensor.*_last_message` tracking sender, direction, timestamp, and audio.
- 🔋 **Battery Monitoring**: Battery level percentage sensor (`sensor.*_battery_level`) and charging state detection.
- 👟 **Fitness Telemetry**: Daily steps counter (`sensor.*_daily_steps`), daily step goal (`sensor.*_step_goal`), and all-time records.
- 📶 **LTE & Network Status**: Active subscription verification (`sensor.*_lte_status`), satellite count, and GPS fix type (GPS, Wi-Fi Anchor).
- 📡 **Remote Location Refresh Button**: Send an on-demand LTE wake-up instruction (`button.*_refresh_location`) to force the watch to take an immediate GPS fix.
- 📡 **LiveTrack Mode**: Start high-frequency LTE tracking session (`button.*_start_livetrack`).
- 🔄 **Cloud Sync Trigger**: Force an instant cloud re-poll (`button.*_poll_cloud_data`) without waiting for the scan interval.
- 🔐 **Garmin 2FA / MFA Support**: Handles two-factor authentication codes natively in the Home Assistant UI during setup.

---

## 📦 Installation

### Method 1: HACS (Recommended)

1. Open **Home Assistant** and navigate to **HACS** > **Integrations**.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Add repository URL `https://github.com/fscorrupt/garmin-bounce-homeassistant`, choose Category **Integration**, and click **Add**.
4. Search for **Garmin Bounce & Jr.** and click **Download**.
5. Restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/garmin_bounce` directory into your Home Assistant `<config_dir>/custom_components/` folder.
2. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Garmin Bounce & Jr.**.
3. Enter your Garmin Connect account **Email** and **Password**.
4. If your account has two-factor authentication enabled, enter the 6-digit **MFA Code** sent to your email or SMS.
5. The integration will automatically discover all families, kids, and Bounce watches registered to your account!

---

## 📊 Available Entities

| Platform | Entity Name | Description |
| :--- | :--- | :--- |
| `device_tracker` | `device_tracker.<child>_bounce_2` | Live GPS location, accuracy, altitude, and speed |
| `sensor` | `sensor.<child>_battery_level` | Watch battery percentage (0-100%) and charging status |
| `sensor` | `sensor.<child>_daily_steps` | Steps walked today (and yesterday's steps as attribute) |
| `sensor` | `sensor.<child>_step_goal` | Daily target step goal |
| `sensor` | `sensor.<child>_steps_record` | All-time personal step record |
| `sensor` | `sensor.<child>_lte_status` | Subscription status (`ACTIVE`) |
| `sensor` | `sensor.<child>_gps_satellites` | Number of tracked GNSS satellites |
| `sensor` | `sensor.<child>_location_fix_type` | Fix method (`GPS`, `WFPS_ANCHOR`) |
| `sensor` | `sensor.<child>_last_sync` | Timestamp of last cloud sync |
| `sensor` | `sensor.<child>_last_message` | Latest message text, sender, direction, and full `chat_history` attribute |
| `button` | `button.<child>_refresh_location` | Dispatches an LTE command to update GPS fix immediately |
| `button` | `button.<child>_start_livetrack` | Triggers continuous LiveTrack tracking session over LTE |
| `button` | `button.<child>_poll_cloud_data` | Forces an immediate refresh of all cloud data |

---

## 💬 Messaging & Voice Services

The integration exposes dedicated Home Assistant services for two-way communication with the watch:

### 1. `garmin_bounce.send_message`
Send a text message directly to your child's Bounce 2 watch or to the family group chat.

```yaml
service: garmin_bounce.send_message
data:
  target: "child" # "child" or "family"
  message: "Das Essen ist fertig! Bitte komm jetzt nach Hause."
```

### 2. `garmin_bounce.send_voice_message`
Send an audio / voice message (`.ogg` Opus format) to the watch.

```yaml
service: garmin_bounce.send_voice_message
data:
  target: "child"
  audio_file: "/local/garmin_bounce/reminder.ogg"
```

### 3. Voice Message Playback in Dashboards
Voice messages sent by your child from the Bounce watch are automatically cached in `/config/www/garmin_bounce/` and exposed via `audio_url` in the sensor attributes (`/local/garmin_bounce/<id>.ogg`), playable directly in Home Assistant cards.

---

## 💡 Automation Examples

### 1. Alert when Child's Watch Battery is Low
```yaml
alias: "Child Watch Battery Low"
trigger:
  - platform: numeric_state
    entity_id: sensor.mia_battery_level
    below: 20
action:
  - service: notify.notify
    data:
      title: "Garmin Bounce Battery Low"
      message: "Mia's watch battery is down to {{ states('sensor.mia_battery_level') }}%."
```

### 2. Request Fresh Location When Leaving School Zone
```yaml
alias: "Refresh Location on School Departure"
trigger:
  - platform: zone
    entity_id: device_tracker.mia_bounce_2
    zone: zone.school
    event: leave
action:
  - service: button.press
    target:
      entity_id: button.mia_refresh_location
```

### 3. Send Automatic Dinner Reminder to Watch
```yaml
alias: "Send Dinner Reminder to Mia"
trigger:
  - platform: time
    at: "18:00:00"
action:
  - service: garmin_bounce.send_message
    data:
      target: "child"
      message: "Hallo Mia! Das Abendessen ist in 15 Minuten fertig. Bitte komm nach Hause."
```

---

## 🎨 Lovelace Dashboard Cards

Pre-configured YAML cards combining the live Map, Battery & Steps metrics, and Action Buttons are available in [`dashboard_cards.yaml`](dashboard_cards.yaml).

---

## 📄 License

Distributed under the MIT License. This project is not affiliated with, endorsed by, or associated with Garmin Ltd.
