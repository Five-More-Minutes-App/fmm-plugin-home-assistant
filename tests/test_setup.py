"""Setting a computer up, and taking it down."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.five_more_minutes.api import FmmError

from .common import COMPUTER_ID, FakeService, make_state


async def test_sets_up_a_computer(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    service.state = make_state(timer_minutes=20, timer_message="Homework")

    entry = await setup_entry()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.elliots_laptop_timer_running").state == "on"
    assert hass.states.get("binary_sensor.elliots_laptop_locked").state == "off"
    assert hass.states.get("binary_sensor.elliots_laptop_connected").state == "on"
    assert hass.states.get("sensor.elliots_laptop_minutes_left").state == "20"
    assert hass.states.get("sensor.elliots_laptop_timer_message").state == "Homework"

    device = dr.async_get(hass).async_get_device_by_identifier(("five_more_minutes", COMPUTER_ID), entry.entry_id)
    assert device is not None
    assert device.name == "Elliots laptop"
    assert device.manufacturer == "Five More Minutes"


async def test_a_key_that_can_only_watch_gets_nothing_to_press(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    service.scopes = ("state:read",)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    domains = {e.domain for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}

    assert domains == {"binary_sensor", "sensor", "event"}


async def test_each_permission_switches_on_its_own_button(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    service.scopes = ("state:read", "timer:extend", "timer:cancel")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    buttons = {
        e.translation_key
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if e.domain == "button"
    }

    assert buttons == {"extend_time", "cancel_timer"}
    assert not [
        e for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) if e.domain == "number"
    ]


async def test_a_refused_key_asks_for_a_new_one(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    service.accepted_key = "something else"
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler("five_more_minutes")
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_an_unreachable_service_is_tried_again_later(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    service.me_error = FmmError("network", "Could not reach Five More Minutes.")
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_network_the_service_refuses_is_an_error_not_a_retry(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    service.me_error = FmmError("network-only", "Five More Minutes only answers plugins on the local network.")
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_a_key_that_cannot_see_the_computer_is_refused(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    service.scopes = ("timer:start",)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unloading_stops_following(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    entry = await setup_entry()
    assert service.polls >= 2, "the first look, and a request held open"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert service.cancelled_polls == 1, "the request being held open was cancelled"
    polls = service.polls
    service.push(make_state(signal=2, timer_minutes=5))
    await hass.async_block_till_done()
    assert service.polls == polls


async def test_can_be_set_up_again_after_unloading(hass: HomeAssistant, setup_entry) -> None:
    entry = await setup_entry()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.elliots_laptop_connected").state == "on"
