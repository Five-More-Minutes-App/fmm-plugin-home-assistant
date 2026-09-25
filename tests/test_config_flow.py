"""The setup, re-authentication and reconfiguration flows."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.five_more_minutes.api import FmmError
from custom_components.five_more_minutes.const import CONF_API_KEY, CONF_URL, DOMAIN

from .common import COMPUTER_ID, KEY, OTHER_COMPUTER_ID, OTHER_KEY, URL, FakeService


async def _start(hass: HomeAssistant) -> dict:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_adds_a_computer(hass: HomeAssistant, service: FakeService) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_API_KEY: KEY})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Elliots laptop"
    assert result["data"] == {CONF_URL: URL, CONF_API_KEY: KEY}
    assert result["result"].unique_id == COMPUTER_ID
    assert result["result"].state is ConfigEntryState.LOADED


async def test_forgives_how_the_address_is_typed_and_stray_spaces_around_the_key(
    hass: HomeAssistant, service: FakeService
) -> None:
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "  192.168.1.10:5072/  ", CONF_API_KEY: f"  {KEY}\n"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: "http://192.168.1.10:5072", CONF_API_KEY: KEY}


async def test_keeps_a_path_for_a_service_behind_a_proxy(hass: HomeAssistant, service: FakeService) -> None:
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "https://home.example/fmm/", CONF_API_KEY: KEY}
    )

    assert result["data"][CONF_URL] == "https://home.example/fmm"


@pytest.mark.parametrize(
    ("url", "key", "arrange", "error"),
    [
        ("ftp://192.168.1.10", KEY, None, "invalid_url"),
        ("http://user:pass@192.168.1.10", KEY, None, "invalid_url"),
        (URL, "not-a-key", None, "invalid_key"),
        (URL, OTHER_KEY, lambda s: setattr(s, "accepted_key", KEY), "invalid_auth"),
        (URL, KEY, lambda s: setattr(s, "me_error", FmmError("network-only", "local only")), "network_only"),
        (URL, KEY, lambda s: setattr(s, "me_error", FmmError("network", "down")), "cannot_connect"),
        (URL, KEY, lambda s: setattr(s, "me_error", FmmError("unexpected", "odd")), "cannot_connect"),
        (URL, KEY, lambda s: setattr(s, "scopes", ("timer:start",)), "missing_state_permission"),
    ],
)
async def test_says_what_is_wrong_and_lets_you_try_again(
    hass: HomeAssistant, service: FakeService, url, key, arrange, error
) -> None:
    if arrange:
        arrange(service)
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: url, CONF_API_KEY: key})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert KEY not in str(result["errors"]) and OTHER_KEY not in str(result["errors"])

    # Put right, it goes through, and the address typed is still there to correct.
    service.me_error = None
    service.scopes = ("state:read", "timer:start")
    service.accepted_key = KEY
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_API_KEY: KEY})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_the_key_is_asked_for_as_a_password(hass: HomeAssistant, service: FakeService) -> None:
    result = await _start(hass)

    schema = result["data_schema"].schema
    key_field = next(v for k, v in schema.items() if k.schema == CONF_API_KEY)

    assert key_field.config["type"] == "password"


async def test_one_entry_per_computer_and_a_new_key_updates_it(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    entry.add_to_hass(hass)
    service.accepted_key = OTHER_KEY
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "http://192.168.1.99:5072", CONF_API_KEY: OTHER_KEY}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_URL: "http://192.168.1.99:5072", CONF_API_KEY: OTHER_KEY}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_two_computers_are_two_entries(hass: HomeAssistant, entry: MockConfigEntry, service: FakeService) -> None:
    entry.add_to_hass(hass)
    service.computer_id = OTHER_COMPUTER_ID
    service.name = "Alvas desktop"
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_API_KEY: KEY})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def _reauth(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id, "unique_id": entry.unique_id},
        data=entry.data,
    )


async def test_reauthentication_takes_a_new_key_for_the_same_computer(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    entry.add_to_hass(hass)
    service.accepted_key = OTHER_KEY
    result = await _reauth(hass, entry)
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["computer"] == "Elliots laptop"
    assert CONF_URL not in result["data_schema"].schema, "only the key is asked for"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: OTHER_KEY})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == OTHER_KEY
    assert entry.data[CONF_URL] == URL
    assert entry.state is ConfigEntryState.LOADED


async def test_reauthentication_says_when_the_new_key_is_no_good(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    entry.add_to_hass(hass)
    service.accepted_key = "somebody else"
    result = await _reauth(hass, entry)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: OTHER_KEY})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_API_KEY] == KEY, "nothing changed"


async def test_reauthentication_refuses_a_key_for_another_computer(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    entry.add_to_hass(hass)
    service.computer_id = OTHER_COMPUTER_ID
    service.accepted_key = OTHER_KEY
    result = await _reauth(hass, entry)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: OTHER_KEY})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_computer"
    assert entry.data[CONF_API_KEY] == KEY, "a key for another computer never replaces this one"


async def test_reconfiguring_changes_the_address_and_key(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    entry.add_to_hass(hass)
    service.accepted_key = OTHER_KEY
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "192.168.1.50:5072", CONF_API_KEY: OTHER_KEY}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_URL: "http://192.168.1.50:5072", CONF_API_KEY: OTHER_KEY}


async def test_reconfiguring_refuses_another_computer(
    hass: HomeAssistant, entry: MockConfigEntry, service: FakeService
) -> None:
    entry.add_to_hass(hass)
    service.computer_id = OTHER_COMPUTER_ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_API_KEY: KEY})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_computer"
    assert entry.unique_id == COMPUTER_ID
