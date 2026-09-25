"""What is shown when someone downloads the diagnostics to attach to an issue."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_URL
from .coordinator import FmmConfigEntry

# The key is a password; the address and the computer's name say where someone lives and who.
TO_REDACT = {CONF_API_KEY, CONF_URL, "name", "id", "message", "unique_id", "title"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: FmmConfigEntry) -> dict[str, Any]:
    """The entry and the state it follows, with anything private removed."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry": async_redact_data(
            {"title": entry.title, "unique_id": entry.unique_id, "data": dict(entry.data), "state": str(entry.state)},
            TO_REDACT,
        ),
        "permissions": sorted(coordinator.scopes),
        "last_update_success": coordinator.last_update_success,
        "state": async_redact_data(asdict(coordinator.data), TO_REDACT),
    }
