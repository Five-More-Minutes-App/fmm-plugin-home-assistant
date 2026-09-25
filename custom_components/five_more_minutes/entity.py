"""The base of every entity: one computer, one device."""

from __future__ import annotations

from datetime import datetime

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import State
from .const import DOMAIN
from .coordinator import FmmCoordinator


class FmmEntity(CoordinatorEntity[FmmCoordinator]):
    """An entity of a computer. Its name and icon come from its translation key."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FmmCoordinator, key: str) -> None:
        super().__init__(coordinator)
        computer = coordinator.data.device
        self._attr_unique_id = f"{computer.id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, computer.id)},
            name=computer.name,
            manufacturer="Five More Minutes",
            model="Computer",
        )

    @property
    def state_now(self) -> State:
        """The latest state. Never None: a coordinator that failed its first look never sets its entities up."""
        return self.coordinator.data

    @property
    def now(self) -> datetime:
        return dt_util.utcnow()


def timer_ends(state: State) -> datetime | None:
    """When the running timer ends, or None when there is none."""
    return datetime.fromisoformat(state.timer.ends_at) if state.timer is not None else None


def lock_ends(state: State) -> datetime | None:
    """When the lock ends, or None when there is none."""
    return datetime.fromisoformat(state.lock.ends_at) if state.lock is not None else None


def timer_running(state: State, now: datetime) -> bool:
    """A timer whose end has passed is over, whether or not the service has said so yet."""
    ends = timer_ends(state)
    return ends is not None and ends > now


def locked(state: State, now: datetime) -> bool:
    """A lock whose end has passed is over, whether or not the service has said so yet."""
    ends = lock_ends(state)
    return ends is not None and ends > now


def minutes_left(state: State, now: datetime) -> int:
    """Whole minutes left, rounded up, so it never reads 0 while there is time."""
    ends = timer_ends(state)
    if ends is None or ends <= now:
        return 0
    seconds = (ends - now).total_seconds()
    return int(-(-seconds // 60))
