"""When the timer and lock end, how long is left, and why time was given."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import State
from .coordinator import FmmConfigEntry, FmmCoordinator
from .entity import FmmEntity, lock_ends, locked, minutes_left, timer_ends, timer_running

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FmmSensorDescription(SensorEntityDescription):
    """A sensor and how to read it."""

    value: Callable[[State, datetime], datetime | int | str | None]


def _message(state: State, now: datetime) -> str | None:
    return state.timer.message if timer_running(state, now) and state.timer is not None else None


DESCRIPTIONS = (
    FmmSensorDescription(
        key="timer_ends",
        translation_key="timer_ends",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda state, now: timer_ends(state) if timer_running(state, now) else None,
    ),
    FmmSensorDescription(
        key="lock_ends",
        translation_key="lock_ends",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda state, now: lock_ends(state) if locked(state, now) else None,
    ),
    FmmSensorDescription(
        key="minutes_left",
        translation_key="minutes_left",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value=minutes_left,
    ),
    FmmSensorDescription(
        key="timer_message",
        translation_key="timer_message",
        value=_message,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: FmmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Adds the sensors of a computer."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(FmmSensor(coordinator, description) for description in DESCRIPTIONS)


class FmmSensor(FmmEntity, SensorEntity):
    """One reading about the computer."""

    entity_description: FmmSensorDescription

    def __init__(self, coordinator: FmmCoordinator, description: FmmSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> datetime | int | str | None:
        return self.entity_description.value(self.state_now, self.now)
