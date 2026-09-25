"""What happened, as events an automation can trigger on."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import State
from .const import EVENT_TYPES
from .coordinator import FmmConfigEntry, FmmCoordinator
from .entity import FmmEntity
from .events import events_between

PARALLEL_UPDATES = 0

# events.py names an event "timer-started"; Home Assistant's event types are lower_snake_case, and a
# lock is said the way a person says it.
_TYPES = {
    "timer-started": "timer_started",
    "timer-extended": "timer_extended",
    "timer-ended": "timer_ended",
    "lock-started": "locked",
    "lock-ended": "unlocked",
    "came-online": "came_online",
    "went-offline": "went_offline",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: FmmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Adds the activity entity of a computer."""
    async_add_entities([FmmActivity(entry.runtime_data.coordinator)])


def _minutes_between(start: str, end: str) -> int:
    return max(0, round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60))


def _attributes(event: str, state: State) -> dict[str, str | int]:
    """What an automation can use about an event."""
    if event == "timer-started" and state.timer is not None:
        return {
            "minutes": _minutes_between(state.timer.starts_at, state.timer.ends_at),
            "message": state.timer.message or "",
        }
    if event == "timer-extended" and state.timer is not None:
        return {"minutes_left": -(-state.timer.seconds_left // 60)}
    if event == "lock-started" and state.lock is not None:
        return {"minutes": _minutes_between(state.lock.starts_at, state.lock.ends_at)}
    return {}


class FmmActivity(FmmEntity, EventEntity):
    """Fires when a timer starts, is extended or ends, when the computer is locked or unlocked, and
    when it comes online or goes offline.

    It reports what it *saw* happen. When Home Assistant starts it does not announce a timer that
    began an hour ago.
    """

    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: FmmCoordinator) -> None:
        super().__init__(coordinator, "activity")
        self._previous: State | None = coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        state = self.coordinator.data
        for event in events_between(self._previous, state):
            self._trigger_event(_TYPES[event], _attributes(event, state))
            # One write per event: an update can carry two (time started, lock lifted), and an
            # automation triggering on this entity should see each of them, in order.
            self.async_write_ha_state()
        self._previous = state
        super()._handle_coordinator_update()
