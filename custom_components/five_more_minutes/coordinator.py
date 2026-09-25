"""Follows one computer in Five More Minutes.

This is a *push* integration built on the update coordinator: nothing polls on a timer. A background
task holds a request open that the service answers the moment anything changes (a long poll), and
hands each answer to :meth:`async_set_updated_data`. While nothing happens that is about two requests
a minute, and when a parent presses a button in the portal Home Assistant knows within a moment.

Two things are deliberately *not* left to the service to announce:

* the end of a timer or a lock, and the passing of each minute, are moments Home Assistant already
  knows, so entities are told to look again at exactly those moments;
* what a computer "is" is worked out from the times, not from a flag, so a timer that has run out
  never reads as running because a message was late.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import FiveMoreMinutes, FmmError, State
from .const import (
    DEFAULT_TIMER_MINUTES,
    DOMAIN,
    LOGGER,
    SCOPE_CANCEL,
    SCOPE_EXTEND,
    SCOPE_START,
    SCOPE_STOP,
    WAIT_SECONDS,
)

type FmmConfigEntry = ConfigEntry[FmmData]


@dataclass
class FmmData:
    """What a loaded entry keeps."""

    client: FiveMoreMinutes
    coordinator: FmmCoordinator


async def _pause(seconds: float) -> None:
    """Waits before trying again. A function of its own so that a test can make it quick."""
    await asyncio.sleep(seconds)


def _instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


class FmmCoordinator(DataUpdateCoordinator[State]):
    """The state of one computer, kept up to date by following it."""

    config_entry: FmmConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FmmConfigEntry,
        client: FiveMoreMinutes,
        scopes: frozenset[str],
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=None,  # pushed, not polled
        )
        self.client = client
        self.scopes = scopes
        # The length the "Start timer" button uses; the number entity keeps it.
        self.timer_length: int = DEFAULT_TIMER_MINUTES
        self._moment: CALLBACK_TYPE | None = None
        self._was_failing = False

    # ---------------------------------------------------------------------------------------------
    # Following

    async def _async_update_data(self) -> State:
        """The first look, and any explicit refresh."""
        try:
            return await self.client.state()
        except FmmError as error:
            raise _update_error(error) from error

    def start_following(self) -> None:
        """Begins holding a request open. The task ends when the entry unloads."""
        self.config_entry.async_create_background_task(
            self.hass, self._follow(), name=f"{DOMAIN} follow {self.config_entry.entry_id}"
        )
        self.config_entry.async_on_unload(self._cancel_moment)
        self._schedule_moment()

    async def _follow(self) -> None:
        delay = 1.0

        while True:
            try:
                state = await self.client.state(wait=self._wait_for(), since=self.data.signal)
            except FmmError as error:
                if error.kind == "auth":
                    LOGGER.warning("Five More Minutes no longer accepts the key; asking for a new one")
                    self._give_up(_update_error(error))
                    self.config_entry.async_start_reauth(self.hass)
                    return

                if not error.retryable:
                    LOGGER.error("Five More Minutes cannot be followed: %s", error)
                    self._give_up(_update_error(error))
                    return

                if not self._was_failing:
                    LOGGER.warning("Lost touch with Five More Minutes: %s", error)
                self._was_failing = True
                self.async_set_update_error(_update_error(error))

                pause = error.retry_after or delay
                await _pause(pause + random.uniform(0, 0.25))  # noqa: S311 - jitter, not security
                delay = min(delay * 2, 60.0)
                continue

            if self._was_failing:
                LOGGER.info("Back in touch with Five More Minutes")
                self._was_failing = False
            delay = 1.0
            self.async_set_updated_data(state)

    def _give_up(self, error: UpdateFailed | ConfigEntryAuthFailed) -> None:
        self.async_set_update_error(error)

    def _wait_for(self) -> int:
        """Asks to be answered when something is about to end, so its end is seen then."""
        moment = self._next_moment(dt_util.utcnow())
        if moment is None:
            return WAIT_SECONDS
        seconds = int((moment - dt_util.utcnow()).total_seconds()) + 1
        return max(1, min(WAIT_SECONDS, seconds))

    # ---------------------------------------------------------------------------------------------
    # Moments Home Assistant already knows

    @callback
    def async_set_updated_data(self, data: State) -> None:
        """Takes a new state and schedules the next moment that will change what it means."""
        super().async_set_updated_data(data)
        self._schedule_moment()

    def _next_moment(self, now: datetime) -> datetime | None:
        """The next time what the state *means* changes with no message from the service."""
        state = self.data
        if state is None:
            return None

        moments: list[datetime] = []
        if state.timer is not None:
            ends = _instant(state.timer.ends_at)
            if ends > now:
                moments.append(ends)
                # The minutes left, which is rounded up, drops at every whole minute before the end.
                left = (ends - now).total_seconds()
                whole = int(-(-left // 60))
                if whole > 1:
                    moments.append(ends - timedelta(seconds=(whole - 1) * 60))
        if state.lock is not None:
            ends = _instant(state.lock.ends_at)
            if ends > now:
                moments.append(ends)

        return min(moments) if moments else None

    def _cancel_moment(self) -> None:
        if self._moment is not None:
            self._moment()
            self._moment = None

    def _schedule_moment(self) -> None:
        self._cancel_moment()
        moment = self._next_moment(dt_util.utcnow())
        if moment is not None:
            # A moment after, so that "now" has really passed the end when entities look again.
            self._moment = async_track_point_in_utc_time(
                self.hass, self._moment_reached, moment + timedelta(milliseconds=200)
            )

    @callback
    def _moment_reached(self, _now: datetime) -> None:
        self._moment = None
        self.async_update_listeners()
        self._schedule_moment()

    # ---------------------------------------------------------------------------------------------
    # What can be done

    def require(self, scope: str) -> None:
        """Says plainly when the key cannot do something, before asking the service to refuse."""
        if scope not in self.scopes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_permission",
                translation_placeholders={"scope": scope, "computer": self.config_entry.title},
            )

    async def async_start_timer(
        self, *, minutes: int | None = None, until: str | None = None, message: str | None = None
    ) -> None:
        """Starts time. Starting during a lock lifts it."""
        self.require(SCOPE_START)
        await self._act(self.client.start(minutes=minutes, until=until, message=message))

    async def async_extend_timer(self, minutes: int | None = None) -> None:
        """Adds time to what is running."""
        self.require(SCOPE_EXTEND)
        await self._act(self.client.extend(minutes))

    async def async_end_time(self) -> None:
        """Ends the time now: the timer ends and the lock the rules ask for begins."""
        self.require(SCOPE_STOP)
        await self._act(self.client.stop())

    async def async_cancel_timer(self) -> None:
        """Lets go: the timer ends and nothing else happens."""
        self.require(SCOPE_CANCEL)
        await self._act(self.client.cancel())

    async def _act(self, call: Awaitable[State]) -> None:
        try:
            state = await call
        except FmmError as error:
            raise _action_error(error) from error
        # The answer is the state after the action, so the dashboard need not wait for the next message.
        self.async_set_updated_data(state)


def _update_error(error: FmmError) -> UpdateFailed | ConfigEntryAuthFailed:
    if error.kind == "auth":
        return ConfigEntryAuthFailed(str(error))
    # str(error) never contains the key.
    return UpdateFailed(str(error))


def _action_error(error: FmmError) -> HomeAssistantError:
    """What a failed action says to whoever pressed the button."""
    if error.kind in ("not-possible", "invalid"):
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_possible",
            translation_placeholders={"reason": str(error)},
        )
    if error.kind == "forbidden":
        return ServiceValidationError(
            translation_domain=DOMAIN, translation_key="forbidden", translation_placeholders={"reason": str(error)}
        )
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="cannot_reach",
        translation_placeholders={"reason": str(error)},
    )
