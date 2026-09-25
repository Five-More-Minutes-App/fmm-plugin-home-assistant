"""The same integration against the real client, talking real HTTP to a faithful mock of the service.

Everything else uses a scripted fake client, so a mistake in how the two fit together (the shape of a
request, a header, what a refusal looks like) would pass there and fail here.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.five_more_minutes.const import CONF_API_KEY, CONF_URL, DOMAIN

from .common import COMPUTER_ID
from .mock_fmm import ALL, DEVICE_ID, KEY, MockFmm

pytestmark = pytest.mark.usefixtures("socket_enabled", "enable_custom_integrations")


@pytest.fixture
async def mock() -> AsyncGenerator[tuple[MockFmm, str]]:
    server = MockFmm()
    url = await server.start()
    yield server, url
    await server.close()


async def _set_up(hass: HomeAssistant, url: str, key: str = KEY) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="Elliots laptop", unique_id=DEVICE_ID, data={CONF_URL: url, CONF_API_KEY: key}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_follows_a_real_service_and_acts_on_it(hass: HomeAssistant, mock: tuple[MockFmm, str]) -> None:
    server, url = mock
    entry = await _set_up(hass, url)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.elliots_laptop_timer_running").state == "off"

    # Time is pressed on a button: the request goes out, and the answer is shown.
    await hass.services.async_call("button", "press", {"entity_id": "button.elliots_laptop_start_timer"}, blocking=True)
    assert hass.states.get("binary_sensor.elliots_laptop_timer_running").state == "on"
    assert server.timer is not None

    # And a change on the service's side (a parent in the portal) arrives without being asked for.
    server.parent_locks(20)
    for _ in range(100):
        await hass.async_block_till_done()
        if hass.states.get("binary_sensor.elliots_laptop_locked").state == "on":
            break
        await hass.async_block_till_done(wait_background_tasks=False)
        import asyncio

        await asyncio.sleep(0.05)
    assert hass.states.get("binary_sensor.elliots_laptop_locked").state == "on"
    assert hass.states.get("binary_sensor.elliots_laptop_timer_running").state == "off"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_sends_the_key_as_a_bearer_token_and_only_to_the_service(
    hass: HomeAssistant, mock: tuple[MockFmm, str]
) -> None:
    server, url = mock
    entry = await _set_up(hass, url)

    assert server.requests, "it asked"
    assert {r["headers"].get("Authorization") for r in server.requests} == {f"Bearer {KEY}"}
    assert all(KEY not in r["path"] and KEY not in str(r.get("query")) for r in server.requests), "never in an address"

    await hass.config_entries.async_unload(entry.entry_id)


async def test_a_key_that_only_watches_gets_no_buttons_and_a_clear_message(hass: HomeAssistant) -> None:
    server = MockFmm(scopes=["state:read"])
    url = await server.start()
    try:
        entry = await _set_up(hass, url)
        assert hass.states.get("button.elliots_laptop_start_timer") is None

        device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, DEVICE_ID), entry.entry_id)
        with pytest.raises(ServiceValidationError) as raised:
            await hass.services.async_call(DOMAIN, "end_time", {"device_id": device.id}, blocking=True)
        assert raised.value.translation_key == "missing_permission"
        assert not [r for r in server.requests if r["path"].endswith("/timer/stop")]

        await hass.config_entries.async_unload(entry.entry_id)
    finally:
        await server.close()


async def test_a_refused_key_starts_re_authentication(hass: HomeAssistant, mock: tuple[MockFmm, str]) -> None:
    _, url = mock
    entry = await _set_up(hass, url, key="fmmk_" + "f" * 32 + "_" + "B" * 43)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [f["context"]["source"] for f in hass.config_entries.flow.async_progress_by_handler(DOMAIN)] == ["reauth"]


async def test_the_scopes_it_uses_are_the_ones_the_starter_declares() -> None:
    assert set(ALL) == {"state:read", "timer:start", "timer:extend", "timer:stop", "timer:cancel"}
    assert COMPUTER_ID == DEVICE_ID, "the fake and the mock describe the same computer"
