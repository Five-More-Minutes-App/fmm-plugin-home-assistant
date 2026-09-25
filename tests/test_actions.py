"""Buttons and services: what they ask the service to do, and what they say when they cannot."""

from __future__ import annotations

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.five_more_minutes.api import FmmError

from .common import COMPUTER_ID, FakeService, make_state

DOMAIN = "five_more_minutes"


def _device_id(hass: HomeAssistant) -> str:
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, COMPUTER_ID), entry.entry_id)
    assert device is not None
    return device.id


async def _press(hass: HomeAssistant, entity: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity}, blocking=True)


async def test_the_buttons_do_what_they_say(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    await setup_entry()

    await _press(hass, "button.elliots_laptop_start_timer")
    await _press(hass, "button.elliots_laptop_add_time")
    await _press(hass, "button.elliots_laptop_end_time_now")
    await _press(hass, "button.elliots_laptop_cancel_timer")

    assert [c[0] for c in service.calls] == ["start", "extend", "stop", "cancel"]
    assert service.calls[0][2] == {"minutes": 30, "until": None, "message": None}, (
        "the usual length until told otherwise"
    )
    assert service.calls[1][1] == (None,), "the household's usual five more"


async def test_the_start_button_uses_the_timer_length(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    await setup_entry()

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.elliots_laptop_timer_length", "value": 45}, blocking=True
    )
    await _press(hass, "button.elliots_laptop_start_timer")

    assert service.calls[-1][2]["minutes"] == 45


async def test_the_timer_length_has_limits(hass: HomeAssistant, setup_entry) -> None:
    await setup_entry()

    for value in (0, 1441, -5):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": "number.elliots_laptop_timer_length", "value": value},
                blocking=True,
            )


async def test_an_answer_updates_the_dashboard_without_waiting(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    await setup_entry()
    service.state = make_state(signal=2, timer_minutes=30)

    await _press(hass, "button.elliots_laptop_start_timer")

    assert hass.states.get("binary_sensor.elliots_laptop_timer_running").state == "on"


async def test_start_timer_service(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    await setup_entry()
    device = _device_id(hass)

    await hass.services.async_call(
        DOMAIN, "start_timer", {"device_id": device, "minutes": 25, "message": "Reading"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "start_timer", {"device_id": [device], "until": "20:00:00"}, blocking=True)
    await hass.services.async_call(DOMAIN, "start_timer", {"device_id": device, "until": "07:05:59"}, blocking=True)

    assert service.calls[0][2] == {"minutes": 25, "until": None, "message": "Reading"}
    assert service.calls[1][2] == {"minutes": None, "until": "20:00", "message": None}
    assert service.calls[2][2]["until"] == "07:05", "a clock time to the minute, with the hour padded"


@pytest.mark.parametrize(
    "data",
    [
        {},  # neither a length nor a time
        {"minutes": 0},
        {"minutes": 1441},
        {"minutes": "soon"},
        {"minutes": 10, "until": "20:00:00"},  # both
        {"until": "25:00"},
        {"minutes": 10, "message": "x" * 101},
    ],
)
async def test_start_timer_refuses_what_makes_no_sense(
    hass: HomeAssistant, setup_entry, service: FakeService, data: dict
) -> None:
    await setup_entry()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "start_timer", {"device_id": _device_id(hass), **data}, blocking=True)

    assert service.calls == []


async def test_extend_end_and_cancel_services(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    await setup_entry()
    device = _device_id(hass)

    await hass.services.async_call(DOMAIN, "extend_timer", {"device_id": device, "minutes": 10}, blocking=True)
    await hass.services.async_call(DOMAIN, "extend_timer", {"device_id": device}, blocking=True)
    await hass.services.async_call(DOMAIN, "end_time", {"device_id": device}, blocking=True)
    await hass.services.async_call(DOMAIN, "cancel_timer", {"device_id": device}, blocking=True)

    assert [(c[0], c[1]) for c in service.calls] == [
        ("extend", (10,)),
        ("extend", (None,)),
        ("stop", ()),
        ("cancel", ()),
    ]

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "extend_timer", {"device_id": device, "minutes": 0}, blocking=True)


async def test_a_key_without_the_permission_says_so_before_asking(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    service.scopes = ("state:read", "timer:extend")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN, "start_timer", {"device_id": _device_id(hass), "minutes": 5}, blocking=True
        )

    assert raised.value.translation_key == "missing_permission"
    assert raised.value.translation_placeholders == {"scope": "timer:start", "computer": "Elliots laptop"}
    assert service.calls == [], "the service was never asked"

    await hass.services.async_call(DOMAIN, "extend_timer", {"device_id": _device_id(hass)}, blocking=True)
    assert service.calls[0][0] == "extend"


async def test_says_what_the_service_said_when_it_is_not_possible(
    hass: HomeAssistant, setup_entry, service: FakeService
) -> None:
    await setup_entry()
    service.action_error = FmmError(
        "not-possible", "Time is already running on that computer. Add to it instead.", status=409
    )

    with pytest.raises(ServiceValidationError) as raised:
        await _press(hass, "button.elliots_laptop_start_timer")

    assert raised.value.translation_key == "not_possible"
    assert "already running" in raised.value.translation_placeholders["reason"]


async def test_says_when_the_service_cannot_be_reached(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    await setup_entry()
    service.action_error = FmmError("network", "Could not reach Five More Minutes.")

    with pytest.raises(HomeAssistantError) as raised:
        await _press(hass, "button.elliots_laptop_end_time_now")

    assert raised.value.translation_key == "cannot_reach"
    assert not isinstance(raised.value, ServiceValidationError)


async def test_a_service_needs_a_computer(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    await setup_entry()
    toaster_entry = MockConfigEntry(domain="other_integration")
    toaster_entry.add_to_hass(hass)
    toaster = dr.async_get(hass).async_get_or_create(
        config_entry_id=toaster_entry.entry_id, identifiers={("other_integration", "toaster")}, name="Toaster"
    )

    with pytest.raises(ServiceValidationError) as elsewhere:
        await hass.services.async_call(DOMAIN, "end_time", {"device_id": toaster.id}, blocking=True)
    assert elsewhere.value.translation_key == "not_a_computer"
    assert elsewhere.value.translation_placeholders == {"device": "Toaster"}

    with pytest.raises(ServiceValidationError) as missing:
        await hass.services.async_call(DOMAIN, "end_time", {"device_id": "no-such-device"}, blocking=True)
    assert missing.value.translation_key == "device_not_found"

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "end_time", {}, blocking=True)

    assert service.calls == []


async def test_a_computer_that_is_not_connected_says_so(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    entry = await setup_entry()
    device = _device_id(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(DOMAIN, "end_time", {"device_id": device}, blocking=True)

    assert raised.value.translation_key == "not_loaded"
    assert service.calls == []
