"""Whether time is running, whether the computer is locked, and whether it is connected."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import State
from .coordinator import FmmConfigEntry, FmmCoordinator
from .entity import FmmEntity, locked, timer_running

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FmmBinarySensorDescription(BinarySensorEntityDescription):
    """A binary sensor and how to read it."""

    is_on: Callable[[State, datetime], bool]


DESCRIPTIONS = (
    FmmBinarySensorDescription(
        key="timer_running",
        translation_key="timer_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on=timer_running,
    ),
    FmmBinarySensorDescription(
        key="locked",
        translation_key="locked",
        is_on=locked,
    ),
    FmmBinarySensorDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on=lambda state, _now: state.device.online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: FmmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Adds the binary sensors of a computer."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(FmmBinarySensor(coordinator, description) for description in DESCRIPTIONS)


class FmmBinarySensor(FmmEntity, BinarySensorEntity):
    """One yes-or-no fact about the computer."""

    entity_description: FmmBinarySensorDescription

    def __init__(self, coordinator: FmmCoordinator, description: FmmBinarySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on(self.state_now, self.now)
