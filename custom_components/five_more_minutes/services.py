"""Actions for automations and scripts: start, extend, end and cancel.

They act on a *computer*, chosen as a device, and go through the same coordinator the buttons do. The
key decides what is allowed: a key without ``timer:start`` gets a clear message, not a failed request.
"""

from __future__ import annotations

from datetime import time
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_MESSAGE,
    ATTR_MINUTES,
    ATTR_UNTIL,
    DOMAIN,
    MAX_MESSAGE_LENGTH,
    MAX_TIMER_MINUTES,
    SERVICE_CANCEL_TIMER,
    SERVICE_END_TIME,
    SERVICE_EXTEND_TIMER,
    SERVICE_START_TIMER,
)
from .coordinator import FmmCoordinator
from .schema import vol

_DEVICES: dict[Any, Any] = {vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}
_MINUTES = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_TIMER_MINUTES))

START_SCHEMA = vol.All(
    vol.Schema(
        {
            **_DEVICES,
            vol.Exclusive(ATTR_MINUTES, "length"): _MINUTES,
            vol.Exclusive(ATTR_UNTIL, "length"): cv.time,
            vol.Optional(ATTR_MESSAGE): vol.All(cv.string, vol.Length(max=MAX_MESSAGE_LENGTH)),
        }
    ),
    cv.has_at_least_one_key(ATTR_MINUTES, ATTR_UNTIL),
)
EXTEND_SCHEMA = vol.Schema({**_DEVICES, vol.Optional(ATTR_MINUTES): _MINUTES})
DEVICE_SCHEMA = vol.Schema(_DEVICES)


def _computers(hass: HomeAssistant, call: ServiceCall) -> list[FmmCoordinator]:
    """The computers a call names, or says why one cannot be used."""
    registry = dr.async_get(hass)
    found: list[FmmCoordinator] = []

    for device_id in call.data[ATTR_DEVICE_ID]:
        device = registry.async_get(device_id)
        if device is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"device": device_id},
            )

        entries = [
            entry
            for entry_id in device.config_entries
            if (entry := hass.config_entries.async_get_entry(entry_id)) is not None and entry.domain == DOMAIN
        ]
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_a_computer",
                translation_placeholders={"device": device.name_by_user or device.name or device_id},
            )

        entry = entries[0]
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_loaded",
                translation_placeholders={"computer": entry.title},
            )
        found.append(entry.runtime_data.coordinator)

    return found


def _clock(value: time) -> str:
    """The service takes a time of day; the API takes ``HH:MM`` in the household's time zone."""
    return f"{value.hour:02d}:{value.minute:02d}"


def async_setup_services(hass: HomeAssistant) -> None:
    """Registers the actions. Called once, when the integration is set up."""

    async def start_timer(call: ServiceCall) -> None:
        for computer in _computers(hass, call):
            await computer.async_start_timer(
                minutes=call.data.get(ATTR_MINUTES),
                until=_clock(call.data[ATTR_UNTIL]) if ATTR_UNTIL in call.data else None,
                message=call.data.get(ATTR_MESSAGE),
            )

    async def extend_timer(call: ServiceCall) -> None:
        for computer in _computers(hass, call):
            await computer.async_extend_timer(call.data.get(ATTR_MINUTES))

    async def end_time(call: ServiceCall) -> None:
        for computer in _computers(hass, call):
            await computer.async_end_time()

    async def cancel_timer(call: ServiceCall) -> None:
        for computer in _computers(hass, call):
            await computer.async_cancel_timer()

    hass.services.async_register(DOMAIN, SERVICE_START_TIMER, start_timer, schema=START_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EXTEND_TIMER, extend_timer, schema=EXTEND_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_END_TIME, end_time, schema=DEVICE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_TIMER, cancel_timer, schema=DEVICE_SCHEMA)
