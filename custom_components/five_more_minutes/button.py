"""Buttons for a dashboard: start a timer, add time, end the time now, cancel.

A button exists only if the key may do what it does, so a key that can only watch gives a computer
with nothing to press, instead of buttons that all fail.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SCOPE_CANCEL, SCOPE_EXTEND, SCOPE_START, SCOPE_STOP
from .coordinator import FmmConfigEntry, FmmCoordinator
from .entity import FmmEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class FmmButtonDescription(ButtonEntityDescription):
    """A button, the permission it needs, and what pressing it does."""

    scope: str
    press: Callable[[FmmCoordinator], Awaitable[None]]


DESCRIPTIONS = (
    FmmButtonDescription(
        key="start_timer",
        translation_key="start_timer",
        scope=SCOPE_START,
        # The length comes from the "Timer length" number, which the same permission switches on.
        press=lambda c: c.async_start_timer(minutes=c.timer_length),
    ),
    FmmButtonDescription(
        key="extend_time",
        translation_key="extend_time",
        scope=SCOPE_EXTEND,
        press=lambda c: c.async_extend_timer(),
    ),
    FmmButtonDescription(
        key="end_time",
        translation_key="end_time",
        scope=SCOPE_STOP,
        press=lambda c: c.async_end_time(),
    ),
    FmmButtonDescription(
        key="cancel_timer",
        translation_key="cancel_timer",
        scope=SCOPE_CANCEL,
        press=lambda c: c.async_cancel_timer(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: FmmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Adds the buttons the key allows."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        FmmButton(coordinator, description) for description in DESCRIPTIONS if description.scope in coordinator.scopes
    )


class FmmButton(FmmEntity, ButtonEntity):
    """Something to press."""

    entity_description: FmmButtonDescription

    def __init__(self, coordinator: FmmCoordinator, description: FmmButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press(self.coordinator)
