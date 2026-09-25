"""Following a computer: what the entities show, and when."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events, async_fire_time_changed

from custom_components.five_more_minutes.api import FmmError

from .common import FakeService, make_state

_real_sleep = asyncio.sleep


@pytest.fixture(autouse=True)
def quick_retries() -> Generator[None]:
    """A retry after a lost connection waits a second or more; here it waits a moment."""

    async def quick(_seconds: float) -> None:
        await _real_sleep(0.01)

    with patch("custom_components.five_more_minutes.coordinator._pause", new=quick):
        yield


RUNNING = "binary_sensor.elliots_laptop_timer_running"
LOCKED = "binary_sensor.elliots_laptop_locked"
CONNECTED = "binary_sensor.elliots_laptop_connected"
MINUTES = "sensor.elliots_laptop_minutes_left"
ENDS = "sensor.elliots_laptop_timer_ends"
LOCK_ENDS = "sensor.elliots_laptop_lock_ends"
MESSAGE = "sensor.elliots_laptop_timer_message"
ACTIVITY = "event.elliots_laptop_activity"


async def test_shows_a_change_as_soon_as_the_service_reports_it(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    await setup_entry()
    assert hass.states.get(RUNNING).state == "off"
    assert hass.states.get(MINUTES).state == "0"

    service.push(make_state(signal=2, timer_minutes=30, timer_message="Homework"))
    await hass.async_block_till_done()

    assert hass.states.get(RUNNING).state == "on"
    assert hass.states.get(MINUTES).state == "30"
    assert hass.states.get(MESSAGE).state == "Homework"
    assert dt_util.parse_datetime(hass.states.get(ENDS).state) is not None


async def test_shows_a_lock_and_the_computer_going_offline(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    await setup_entry()

    service.push(make_state(signal=2, lock_minutes=20, online=False))
    await hass.async_block_till_done()

    assert hass.states.get(LOCKED).state == "on"
    assert hass.states.get(CONNECTED).state == "off"
    assert hass.states.get(RUNNING).state == "off"
    assert dt_util.parse_datetime(hass.states.get(LOCK_ENDS).state) is not None
    assert hass.states.get(ENDS).state == "unknown"


async def test_the_minutes_left_drop_on_the_minute_and_the_end_is_seen_at_the_end(
    hass: HomeAssistant, setup_entry, service: FakeService, request: pytest.FixtureRequest
) -> None:
    service.state = make_state(timer_minutes=2.5)  # 150 seconds
    await setup_entry()
    freezer: FrozenDateTimeFactory = request.getfixturevalue(
        "freezer"
    )  # frozen once set up: setup has timers of its own
    assert hass.states.get(MINUTES).state == "3"

    # The minute changes 30 seconds in, with no message from the service.
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(MINUTES).state == "2"
    assert hass.states.get(RUNNING).state == "on"

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(MINUTES).state == "1"

    # And the end: nothing arrives from the service, and the timer is over.
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(RUNNING).state == "off"
    assert hass.states.get(MINUTES).state == "0"
    assert hass.states.get(ENDS).state == "unknown"


async def test_a_lock_ends_by_itself_too(
    hass: HomeAssistant, setup_entry, service: FakeService, request: pytest.FixtureRequest
) -> None:
    service.state = make_state(lock_minutes=1)
    await setup_entry()
    freezer: FrozenDateTimeFactory = request.getfixturevalue("freezer")
    assert hass.states.get(LOCKED).state == "on"

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(LOCKED).state == "off"


async def test_asks_to_be_answered_when_something_is_about_to_end(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    waits: list[int | None] = []
    client_state = service.client().state

    async def spy(*, wait: int | None = None, since: int | None = None):
        waits.append(wait)
        return await client_state(wait=wait, since=since)

    service.state = make_state(timer_minutes=0.05)  # three seconds
    with patch.object(type(service.client()), "state", side_effect=spy, autospec=False):
        await setup_entry()

    held = [w for w in waits if w is not None]
    assert held
    assert max(held) <= 5, f"waited up to {max(held)}s though the timer ends in 3"


async def test_the_activity_entity_reports_what_it_saw_happen(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    t0 = dt_util.utcnow()  # the service's own times do not drift between reports
    service.state = make_state(timer_minutes=10, timer_message="Already running", now=t0)
    await setup_entry()
    assert hass.states.get(ACTIVITY).state == "unknown", "a timer that was already running is not announced"

    service.push(make_state(signal=2, timer_minutes=10, timer_id="t1", now=t0))  # nothing changed
    await hass.async_block_till_done()
    assert hass.states.get(ACTIVITY).state == "unknown"

    service.push(make_state(signal=3, timer_minutes=25, timer_id="t1", now=t0))
    await hass.async_block_till_done()
    assert hass.states.get(ACTIVITY).attributes["event_type"] == "timer_extended"

    service.push(make_state(signal=4, lock_minutes=30, now=t0))
    await hass.async_block_till_done()
    assert hass.states.get(ACTIVITY).attributes["event_type"] == "locked"
    assert hass.states.get(ACTIVITY).attributes["minutes"] == 31  # the lock began a minute before "now"

    # Starting time during a lock lifts it: two things happened, and an automation sees both, in order.
    changes = async_capture_events(hass, "state_changed")
    service.push(make_state(signal=5, timer_minutes=15, timer_message="Reading", timer_id="t2", now=t0))
    await hass.async_block_till_done()
    seen = [
        (e.data["new_state"].attributes["event_type"], e.data["new_state"].attributes.get("message"))
        for e in changes
        if e.data["entity_id"] == ACTIVITY
    ]
    assert seen == [("timer_started", "Reading"), ("unlocked", None)]

    service.push(make_state(signal=6, timer_minutes=15, timer_id="t2", online=False, now=t0))
    await hass.async_block_till_done()
    assert hass.states.get(ACTIVITY).attributes["event_type"] == "went_offline"


async def test_every_event_type_is_declared(hass: HomeAssistant, setup_entry) -> None:
    await setup_entry()

    assert hass.states.get(ACTIVITY).attributes["event_types"] == [
        "timer_started",
        "timer_extended",
        "timer_ended",
        "locked",
        "unlocked",
        "came_online",
        "went_offline",
    ]


async def test_goes_unavailable_when_the_service_is_lost_and_comes_back(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    await setup_entry()
    assert hass.states.get(RUNNING).state == "off"

    service.fail_with(
        FmmError("network", "Could not reach Five More Minutes."),
        FmmError("network", "Could not reach Five More Minutes."),
    )
    await hass.async_block_till_done()
    await _real_sleep(0.05)
    await hass.async_block_till_done()

    # By now the failures have been used up and it has recovered; what matters is that it noticed and returned.
    service.fail_with(*[FmmError("network", "down")] * 200)
    await hass.async_block_till_done()
    await _real_sleep(0.05)
    assert hass.states.get(RUNNING).state == "unavailable"

    service.state_errors.clear()
    service.push(make_state(signal=9, timer_minutes=5))
    await _real_sleep(0.1)
    await hass.async_block_till_done()

    assert hass.states.get(RUNNING).state == "on"


async def test_a_key_refused_while_following_asks_for_a_new_one_and_stops(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    entry = await setup_entry()

    service.fail_with(FmmError("auth", "The API key was not accepted.", status=401))
    await hass.async_block_till_done()

    assert hass.states.get(RUNNING).state == "unavailable"
    flows = hass.config_entries.flow.async_progress_by_handler("five_more_minutes")
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]
    polls = service.polls
    await _real_sleep(0.1)
    assert service.polls == polls, "a refused key is not tried again"
    assert entry.state is ConfigEntryState.LOADED


async def test_a_lock_or_service_that_cannot_be_followed_is_reported_once_and_left(
    hass: HomeAssistant, setup_entry, service: FakeService, caplog: pytest.LogCaptureFixture
) -> None:
    await setup_entry()

    service.fail_with(FmmError("network-only", "Five More Minutes only answers plugins on the local network."))
    await hass.async_block_till_done()

    assert hass.states.get(RUNNING).state == "unavailable"
    assert caplog.text.count("cannot be followed") == 1


async def test_never_logs_the_key(
    hass: HomeAssistant, entry: MockConfigEntry, setup_entry, service: FakeService, caplog: pytest.LogCaptureFixture
) -> None:
    from .common import KEY

    await setup_entry()
    service.fail_with(FmmError("network", "Could not reach Five More Minutes."))
    await hass.async_block_till_done()
    await _real_sleep(0.05)

    assert KEY not in caplog.text
