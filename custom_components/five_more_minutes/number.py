"""How long the "Start timer" button starts."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_TIMER_MINUTES, MAX_TIMER_MINUTES, SCOPE_START
from .coordinator import FmmConfigEntry, FmmCoordinator
from .entity import FmmEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: FmmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Adds the timer length, if the key can start a timer."""
    coordinator = entry.runtime_data.coordinator
    if SCOPE_START in coordinator.scopes:
        async_add_entities([FmmTimerLength(coordinator)])


class FmmTimerLength(FmmEntity, RestoreNumber):
    """The minutes the "Start timer" button starts. Remembered across restarts."""

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 1
    _attr_native_max_value = MAX_TIMER_MINUTES
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: FmmCoordinator) -> None:
        super().__init__(coordinator, "timer_length")
        self._attr_native_value = coordinator.timer_length

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None and 1 <= last.native_value <= MAX_TIMER_MINUTES:
            self._attr_native_value = int(last.native_value)
        else:
            self._attr_native_value = DEFAULT_TIMER_MINUTES
        self.coordinator.timer_length = int(self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = int(value)
        self.coordinator.timer_length = int(value)
        self.async_write_ha_state()
