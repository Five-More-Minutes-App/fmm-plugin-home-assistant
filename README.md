# Five More Minutes for Home Assistant

See and control the screen time on your child's computer from Home Assistant.
[Five More Minutes](https://fivemoreminutes.app) decides *when* a computer is
usable; this integration puts it in your dashboards and automations: start a timer, add time, end it, and
react when time starts, runs out, or the computer is locked.

Free, open source (MIT). It talks only to Five More Minutes, with a key that works from your home only, and installs nothing else.

## What you get

**One device per computer**, with:

| Entity | |
|---|---|
| `binary_sensor` **Timer running** | On while time is running |
| `binary_sensor` **Locked** | On while the computer is locked |
| `binary_sensor` **Connected** | Whether the computer is talking to Five More Minutes |
| `sensor` **Minutes left** | Whole minutes, rounded up (it never says 0 while there is time). Drops on the minute |
| `sensor` **Timer ends** / **Lock ends** | A timestamp, so a dashboard can show "in 12 minutes" |
| `sensor` **Timer message** | Why time was given, if it was started with a message |
| `event` **Activity** | Fires when a timer starts, is extended or ends, when the computer is locked or unlocked, and when it comes online or goes offline |
| `button` **Start timer** · **Add time** · **End time now** · **Cancel timer** | For a dashboard. Only the ones your key is allowed to use exist |
| `number` **Timer length** | How many minutes **Start timer** starts (remembered) |

**Actions** (for automations and scripts, on a computer chosen as a device): `five_more_minutes.start_timer`
(`minutes` or `until`, and an optional `message`), `extend_timer`, `end_time`, `cancel_timer`.

English and Swedish.

## Install

### 1. Make a key

In the Five More Minutes portal open **Plugins**, choose the computer, name the key `Home Assistant`, and
tick the permissions you want it to have. Under **Where will the plugin run?** keep **At home, on our own internet
connection**: the portal fills in your home's internet address, and the key works only from there (and your home
network). Do this at home, on your home connection, so the address it fills in is the right one.

| Permission | Gives you |
|---|---|
| `state:read` | **Required.** All the sensors, the activity event |
| `timer:start` | **Start timer** button, **Timer length**, the `start_timer` action |
| `timer:extend` | **Add time**, `extend_timer` |
| `timer:stop` | **End time now**, `end_time` |
| `timer:cancel` | **Cancel timer**, `cancel_timer` |

Give it only what you will use: a key that only shows a countdown needs `state:read`. A key's permissions
cannot be changed later; make a new one instead. The key is shown once. Copy it.

Or press **Add** on this plugin's page in the marketplace and the portal makes the key for you.

### 2. Install the integration

**With HACS** (recommended): **HACS → ⋮ → Custom repositories**, add
`https://github.com/Five-More-Minutes-App/fmm-plugin-home-assistant` as an **Integration**, then install
**Five More Minutes** and restart Home Assistant.

**By hand**: copy the `custom_components/five_more_minutes` folder into your Home Assistant's
`custom_components` folder and restart.

### 3. Add the computer

**Settings → Devices & services → Add integration → Five More Minutes.** It asks for:

- **Address of Five More Minutes**: already filled in with `https://api.fivemoreminutes.app`. Only if you run the Five More Minutes service yourself, change it to its local address, e.g. `http://192.168.1.10:5072` (typing `192.168.1.10:5072` is fine).
- **API key**: the key from step 1.

It checks both, and names the device after the computer.

## Dashboard card

The integration brings its own card, so there is nothing else to install. On a dashboard: **Edit → Add card →
Five More Minutes**, and choose the computer.

It shows the countdown on a ring, when the time ends and any message, or how long a lock has left, and whether the
computer is connected. Under it are the controls the key allows: start time (with an optional message for the
screen), add time, end now (locks the computer, as your rules say) and cancel the timer (stops without a lock). A key
that can only watch shows no buttons.

In YAML:

```yaml
type: custom:five-more-minutes-card
device_id: 0123456789abcdef      # choose the computer in the editor
title: Elliot's laptop           # optional; the computer's name otherwise
start_minutes: [15, 30, 45, 60]  # optional
add_minutes: [5, 15, 30]         # optional
show_message: true               # optional
```

The card can do what the key can do, which is not everything the portal can: approving a child's request, writing to
them, and the rules stay in the portal and the app.

## Examples

Start homework time when a button is pressed, with a message the child sees:

```yaml
automation:
  - alias: Homework time
    triggers:
      - trigger: state
        entity_id: input_button.homework
    actions:
      - action: five_more_minutes.start_timer
        target:
          device_id: 0123456789abcdef   # choose the computer in the editor
        data:
          minutes: 45
          message: Homework
```

Lights amber when time is up:

```yaml
automation:
  - alias: Time is up
    triggers:
      - trigger: state
        entity_id: event.elliots_laptop_activity
        attribute: event_type
        to: timer_ended
    actions:
      - action: light.turn_on
        target: { entity_id: light.hallway }
        data: { color_name: orange }
```

A heads-up at five minutes:

```yaml
automation:
  - alias: Five minutes left
    triggers:
      - trigger: numeric_state
        entity_id: sensor.elliots_laptop_minutes_left
        below: 6
        above: 4
    actions:
      - action: notify.mobile_app_phone
        data: { message: "Five minutes left on the computer." }
```

End the day at bedtime (the computer locks, as it would if time ran out):

```yaml
automation:
  - alias: Bedtime
    triggers:
      - trigger: time
        at: "20:30:00"
    conditions:
      - condition: state
        entity_id: binary_sensor.elliots_laptop_timer_running
        state: "on"
    actions:
      - action: five_more_minutes.end_time
        target:
          device_id: 0123456789abcdef
```

The activity event has attributes you can use: `minutes` and `message` when a timer starts, `minutes_left`
when it is extended, `minutes` when the computer is locked.

## How it behaves

- **Pushed, not polled.** It holds a request open that Five More Minutes answers the moment something changes, so the dashboard follows a parent's button press within a moment, with about two requests a minute while nothing happens.
- **The end of a timer is seen at its end**, and the minutes drop on the minute, from the times themselves: nothing waits for a message.
- **The activity event reports what it saw happen.** When Home Assistant starts, it does not announce a timer that began an hour ago. When an update carries two things (time started *and* the lock lifted), you get both events, in order.
- **If Five More Minutes is unreachable** the entities go *unavailable*, it says so once in the log, keeps trying (backing off up to a minute), and says once when it is back.
- **If the key stops working** (revoked or expired), Home Assistant shows a notice on the integration asking you for a new one, and stops asking until you enter it. The new key has to be for the same computer.
- Change the address or key any time: **the device → ⋮ → Reconfigure**.

## Security

- The key opens **one computer**, and only from your **home**: your home network, or the home internet address the key names. If it leaked, whoever held it would need to be at your home, and could do only what you ticked.
- It is stored in Home Assistant's config entry like any integration's credentials, asked for as a password field, never put in a log line, an error message, or the **diagnostics** download (which also hides the address, the computer's name and any message).
- The client refuses redirects, so the key can never be sent to a place the service redirects to.
- Actions check that the key may do what is asked *before* asking: a key without `timer:start` gets a clear message, not a failed request.
- It installs no dependencies. The client is a small file (`api.py`) you can read.

## When it doesn't work

| You see | Do this |
|---|---|
| "The key was not accepted" | Wrong, revoked or expired. Make a new key in the portal. |
| "did not recognise where Home Assistant is calling from" | The key does not name your home's internet address, or your router has been given a new one. In the portal: **Plugins → the key → Change where it works from**. |
| "Could not reach Five More Minutes" | Is it running? Can Home Assistant's computer open the address? From a container, `localhost` is the container itself: use the real address. |
| "does not have the … permission" | Make a new key with that permission ticked. |
| "Not possible right now: Time is already running" | A timer is running. Use **Add time**, or **Cancel timer** first. |
| No buttons | The key can only watch. Make a key with `timer:*` permissions, and use **Reconfigure** with it. |
| Everything **unavailable** | See the log: it says why. It recovers by itself when the service is back. |

## Development

```bash
pip install pytest-homeassistant-custom-component ruff mypy
pytest                       # 72 tests, against real Home Assistant
ruff check . && ruff format --check .
mypy custom_components
```

Home Assistant does not run natively on Windows; use WSL or a container (the CI does).

- `coordinator.py`: follows the computer, and schedules the moments Home Assistant already knows (an end, a new minute).
- `api.py` and `events.py`: the client and the event helper, vendored unchanged from [fmm-plugin-template-python](https://github.com/Five-More-Minutes-App/fmm-plugin-template-python).
- Most tests use a scripted fake service (fast, deterministic); `tests/test_wire.py` runs the real client over real HTTP against a faithful mock of the service.

### What has and has not been tested

Tested: everything above, automatically, against **Home Assistant 2026.9.3**. **Not tested against a real
Five More Minutes installation with a real computer** (the mock follows the API documentation), and
**not on other Home Assistant versions**: `hacs.json` asks for 2026.9 or newer because that is what was
tested. If it works on an older one, or something differs, please open an issue.

## Licence

MIT. See [LICENSE](LICENSE).
