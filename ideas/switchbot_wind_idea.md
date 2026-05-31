# SwitchBot Fan Wind Simulation Idea

## Goal

Build an optional GT7Eng wind simulation output that uses Gran Turismo 7 telemetry to control a SwitchBot circulator fan over local BLE.

The feature should translate car speed into fan speed so the driver feels more airflow at higher speed, while keeping control smooth, safe, and low-frequency enough for smart fan hardware.

This is not a per-frame actuator. GT7 telemetry can update near 60 Hz, but SwitchBot fan control should be rate-limited to roughly 2 Hz with hysteresis and smoothing.

## Hardware Recommendation

Use the SwitchBot Standing Circulator Fan as the preferred device.

Reasons:

- SwitchBot publishes stronger airflow specs for the standing fan: up to 9.15 m3/min airflow, 6.1 m/s wind speed, and 27 m airflow distance.
- It has adjustable height, roughly 47-100 cm, making it easier to aim at a sim-rig seat.
- It can behave as either a standing or desktop-style fan.
- `pySwitchbot` exposes richer controls for the standing fan, including horizontal/vertical oscillation and angle setters.
- It is better suited to longer sessions when plugged in.

The SwitchBot Battery/Desktop Circulator Fan is feasible but secondary.

Reasons:

- `pySwitchbot` supports it as `SwitchbotFan`.
- It can control speed, mode, power, and oscillation.
- It is compact and easy to place on a desk.
- It is less ideal for a serious rig because official airflow performance data is less complete, and battery operation is a practical limit. It should be plugged in for sim use.

## Fan Comparison

| Category | Standing Circulator Fan | Battery/Desktop Circulator Fan |
|---|---|---|
| Best use | Main sim-rig wind fan | Portable or desk setup |
| Published airflow | Up to 9.15 m3/min | Not clearly published on EU page |
| Published wind speed | Up to 6.1 m/s | Not clearly published on EU page |
| Published distance | Up to 27 m | Not clearly published on EU page |
| Placement | Floor or desktop, adjustable height | Desktop/portable |
| Power | Best used wired for sim | Battery capable, but plug in for sim |
| Noise | EU page says as low as 22 dB | Quiet operation advertised |
| Oscillation | Horizontal and vertical | Oscillation supported |
| pySwitchbot model | `SwitchbotStandingFan` | `SwitchbotFan` |
| Wind sim verdict | Recommended | Feasible fallback |

## pySwitchbot Feasibility

`pySwitchbot` 2.2.0 supports both devices over local BLE.

Standing fan:

- Model: `SwitchbotModel.STANDING_FAN`
- Class: `SwitchbotStandingFan`
- Supports:
  - `turn_on()`
  - `turn_off()`
  - `set_percentage(percent)`
  - `set_preset_mode(mode)`
  - `set_horizontal_oscillation(enabled)`
  - `set_vertical_oscillation(enabled)`
  - `set_horizontal_oscillation_angle(30|60|90)`
  - `set_vertical_oscillation_angle(30|60|90)`
  - `set_night_light(state)`

Battery/Desktop fan:

- Model: `SwitchbotModel.CIRCULATOR_FAN`
- Class: `SwitchbotFan`
- Supports:
  - `turn_on()`
  - `turn_off()`
  - `set_percentage(percent)`
  - `set_preset_mode(mode)`
  - `set_oscillation(enabled)`
  - `set_horizontal_oscillation(enabled)`
  - `set_vertical_oscillation(enabled)`

Important detail: use local BLE, not SwitchBot cloud. Cloud introduces latency and `pySwitchbot` appears to have a cloud mapping gap for the standing fan. BLE control is the right transport for live feedback.

## GT7Eng Integration Shape

Add a sibling output manager to the existing pixel display manager.

Proposed module:

- `src/gt7eng/wind.py`

Proposed class:

- `SwitchBotWindManager`

It should mirror the shape of `PixelDisplayManager`:

- `start()`
- `stop()`
- `reconfigure()`
- `publish(snapshot)`
- `status()`

The service already has a good output pattern:

- Telemetry updates create a `RaceSnapshot`.
- `RaceEngineerService.update_frame()` publishes the snapshot to output devices.
- Pixel display already uses this model.
- Wind should do the same.

## Telemetry Inputs

Required for v1:

- `RaceSnapshot.speed_kph`
- `RaceSnapshot.connected`
- `RaceSnapshot.session_phase`

Useful later:

- `throttle`
- `brake`
- `gear`
- acceleration estimate from speed delta

Current repo note:

- `TelemetryFrame` already has `speed_kph`, `throttle`, and `brake`.
- `RaceSnapshot` currently exposes `speed_kph`, but not `throttle` or `brake`.
- For v1, speed-only wind is enough.
- For v2, add `throttle` and `brake` to `RaceSnapshot` if we want gust behavior.

## Control Model

Use speed as the primary signal.

Base mapping:

```text
normalized = clamp(speed_kph / max_speed_kph, 0.0, 1.0)
curved = normalized ** curve_exponent
fan_percent = min_active_percent + curved * (max_percent - min_active_percent)
```

Recommended defaults:

```text
max_speed_kph = 280
curve_exponent = 1.6
min_active_percent = 18
max_percent = 100
update_hz = 2
hysteresis_percent = 3
smoothing_seconds = 1.0
```

Why curve the speed:

- Real aerodynamic pressure rises roughly with speed squared.
- A linear fan curve may feel too strong at low speed or too weak at high speed.
- `1.6` is a pragmatic starting point between linear and squared.

Example output:

| Speed | Approx fan target |
|---:|---:|
| 0 kph | off |
| 50 kph | about 23-28% |
| 100 kph | about 34-42% |
| 150 kph | about 50-60% |
| 200 kph | about 68-78% |
| 250+ kph | about 90-100% |

## Runtime Behavior

When racing:

- Keep fan on.
- Set mode to normal.
- Set oscillation off by default.
- Update speed at low frequency.
- Only send a new command when the target percent changes meaningfully.

When paused, loading, in menu, finished, disconnected, or stale:

- Ramp down for comfort.
- Then turn off.
- Avoid leaving the fan running if telemetry stops.

Recommended shutdown behavior:

```text
if snapshot is stale or not racing:
    target_percent = 0
    after ramp-down, turn fan off
```

## BLE Command Strategy

Do not send every telemetry frame.

Use:

- One long-lived BLE connection where possible.
- Command deduplication.
- Hysteresis to avoid tiny percent changes.
- Rate limit around 2 Hz.
- Reconnect with backoff.
- A status field showing last command, last error, connected state, and current target.

Avoid:

- Cloud API for active driving.
- 60 Hz updates.
- Constant oscillation toggling.
- Using natural/sleep/baby fan modes for the base simulation.

## Configuration

Proposed env vars:

```text
GT7ENG_SWITCHBOT_WIND_ENABLED=false
GT7ENG_SWITCHBOT_WIND_ADDRESS=
GT7ENG_SWITCHBOT_WIND_MODEL=standing
GT7ENG_SWITCHBOT_WIND_UPDATE_HZ=2
GT7ENG_SWITCHBOT_WIND_MAX_SPEED_KPH=280
GT7ENG_SWITCHBOT_WIND_MIN_ACTIVE_PERCENT=18
GT7ENG_SWITCHBOT_WIND_MAX_PERCENT=100
GT7ENG_SWITCHBOT_WIND_CURVE_EXPONENT=1.6
GT7ENG_SWITCHBOT_WIND_SMOOTHING_SECONDS=1.0
GT7ENG_SWITCHBOT_WIND_HYSTERESIS_PERCENT=3
GT7ENG_SWITCHBOT_WIND_PAUSED_BEHAVIOR=off
GT7ENG_SWITCHBOT_WIND_OSCILLATION=off
```

Optional later config:

```text
GT7ENG_SWITCHBOT_WIND_THROTTLE_BOOST=0.0
GT7ENG_SWITCHBOT_WIND_BRAKE_DAMPING=0.0
GT7ENG_SWITCHBOT_WIND_IDLE_PERCENT=0
GT7ENG_SWITCHBOT_WIND_STARTUP_PERCENT=20
GT7ENG_SWITCHBOT_WIND_FAILSAFE_SECONDS=3
```

## UI And Controls

Minimum v1:

- Env-based configuration.
- `gt7eng doctor` reports whether `PySwitchbot` is installed.
- `/api/status` includes wind status.

Nice v1.1:

- HUD toggle for wind enabled/disabled.
- HUD display of current fan target percent.
- Start/stop buttons similar to pixel display.
- A test button that runs 20%, 50%, 100%, off.

Do not overbuild the first version. Config plus status is enough to validate the idea with real hardware.

## Test Plan

Unit tests:

- Speed-to-fan-percent mapping.
- Clamp below 0 and above max speed.
- Curve exponent behavior.
- Smoothing behavior.
- Hysteresis prevents noisy command spam.
- Paused/menu/loading/stale snapshots command shutdown.
- Disabled config sends no commands.
- Fake BLE client receives expected calls.

Integration-style tests:

- Replay telemetry and assert fan commands are rate-limited.
- Simulate disconnect and reconnect.
- Simulate command failure and confirm status records error.

Hardware acceptance test:

1. Install optional dependency.
2. Configure fan BLE address.
3. Run doctor.
4. Start GT7Eng.
5. Confirm fan turns on when car starts moving.
6. Confirm fan ramps up with speed.
7. Confirm fan turns off when telemetry pauses/stales.
8. Confirm no command spam or BLE instability during a 20-minute session.

## Open Questions For When The Fan Arrives

- What is the real BLE command latency in this room?
- Does `set_percentage()` feel smooth enough at 2 Hz?
- Does the fan need a minimum percent higher than 18 to overcome spin-up?
- Is the standing fan too powerful at 100% for close sim-rig placement?
- Should max percent default to 70-80 for comfort?
- Does the fan remember mode/oscillation after power cycling?
- Does pySwitchbot report reliable state after each command?
- Is the best placement front-center, side-left, side-right, or two-fan later?

## Sources

- SwitchBot Standing Circulator Fan EU page: https://eu.switch-bot.com/products/switchbot-standing-circulator-fan
- SwitchBot Battery Circulator Fan EU page: https://eu.switch-bot.com/products/switchbot-battery-circulator-fan
- Battery fan runtime support article: https://support.switch-bot.com/hc/en-us/articles/25125725966231-About-the-Operation-Time-of-SwitchBot-Battery-Circulator-Fan
- pySwitchbot fan implementation: https://github.com/sblibs/pySwitchbot/blob/2.2.0/switchbot/devices/fan.py
- pySwitchbot fan constants: https://github.com/sblibs/pySwitchbot/blob/2.2.0/switchbot/const/fan.py

