"""A scripted stand-in for the Five More Minutes service, for driving the integration deterministically.

Real HTTP is used in ``test_wire.py``. Everything else uses this, because a test that says "the service
now reports a timer" should not have to wait for a socket.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from custom_components.five_more_minutes.api import (
    Computer,
    FiveMoreMinutes,
    FmmError,
    Lock,
    Me,
    State,
    Timer,
)

KEY = "fmmk_" + "0123456789abcdef" * 2 + "_" + "A" * 43
OTHER_KEY = "fmmk_" + "fedcba9876543210" * 2 + "_" + "B" * 43
URL = "http://192.168.1.10:5072"
COMPUTER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_COMPUTER_ID = "22222222-2222-2222-2222-222222222222"
ALL_SCOPES = ("state:read", "timer:start", "timer:extend", "timer:stop", "timer:cancel")


def make_state(
    *,
    signal: int = 1,
    timer_minutes: float | None = None,
    timer_message: str | None = None,
    lock_minutes: float | None = None,
    online: bool = True,
    timer_id: str = "t1",
    name: str = "Elliots laptop",
    now: datetime | None = None,
) -> State:
    """A state relative to *now* (the frozen clock, in tests)."""
    now = now or dt_util.utcnow()

    def at(minutes: float) -> str:
        return (now + timedelta(minutes=minutes)).isoformat()

    return State(
        api_version=1,
        server_time=now.isoformat(),
        signal=signal,
        device=Computer(COMPUTER_ID, name, online),
        timer=None
        if timer_minutes is None
        else Timer(timer_id, at(-1), at(timer_minutes), int(timer_minutes * 60), timer_message),
        lock=None if lock_minutes is None else Lock(at(-1), at(lock_minutes), int(lock_minutes * 60), "Network"),
    )


class FakeService:
    """One computer, and the client the integration is given for it."""

    def __init__(
        self, scopes: tuple[str, ...] = ALL_SCOPES, computer_id: str = COMPUTER_ID, name: str = "Elliots laptop"
    ) -> None:
        self.scopes = scopes
        self.computer_id = computer_id
        self.name = name
        self.state = make_state(name=name)
        self.me_error: FmmError | None = None
        self.accepted_key: str = KEY
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.action_error: FmmError | None = None
        self.state_errors: list[FmmError] = []
        self.polls = 0
        self.cancelled_polls = 0
        self._changed = asyncio.Event()

    # -- what a test does to the "service" ---------------------------------------------------------

    def push(self, state: State) -> None:
        """The service reports a new state, answering the request that is being held open."""
        self.state = state
        self._changed.set()

    def fail_with(self, *errors: FmmError) -> None:
        """The next requests fail, one error each, and then it recovers."""
        self.state_errors = list(errors)
        self._changed.set()

    # -- the client the integration gets ---------------------------------------------------------

    def client(self, key: str = KEY) -> FakeClient:
        return FakeClient(self, key)


class FakeClient:
    """Speaks like ``FiveMoreMinutes``, for one key."""

    def __init__(self, service: FakeService, key: str) -> None:
        self._service = service
        self._key = key

    async def me(self) -> Me:
        s = self._service
        if s.me_error is not None:
            raise s.me_error
        if self._key != s.accepted_key:
            raise FmmError("auth", "The API key was not accepted.", status=401)
        return Me("k1", "Home Assistant", None, tuple(s.scopes), None, s.computer_id, s.name)

    async def state(self, *, wait: int | None = None, since: int | None = None) -> State:
        s = self._service
        s.polls += 1

        if s.state_errors:
            raise s.state_errors.pop(0)

        # A held-open request: answered when the state changes, or when the wait is up.
        if wait is not None and since is not None and since == s.state.signal:
            s._changed.clear()
            try:
                await asyncio.wait_for(s._changed.wait(), timeout=wait)
            except TimeoutError:
                pass
            except asyncio.CancelledError:
                s.cancelled_polls += 1
                raise
            if s.state_errors:
                raise s.state_errors.pop(0)
        return s.state

    async def _act(self, name: str, *args: Any, **kwargs: Any) -> State:
        s = self._service
        s.calls.append((name, args, kwargs))
        if s.action_error is not None:
            raise s.action_error
        return s.state

    async def start(self, *, minutes: int | None = None, until: str | None = None, message: str | None = None) -> State:
        return await self._act("start", minutes=minutes, until=until, message=message)

    async def extend(self, minutes: int | None = None) -> State:
        return await self._act("extend", minutes)

    async def stop(self) -> State:
        return await self._act("stop")

    async def cancel(self) -> State:
        return await self._act("cancel")


def patch_target() -> list[str]:
    """Every place the integration builds a client."""
    return [
        "custom_components.five_more_minutes.FiveMoreMinutes",
        "custom_components.five_more_minutes.config_flow.FiveMoreMinutes",
    ]


def factory(service: FakeService) -> Callable[..., FakeClient]:
    """What replaces the ``FiveMoreMinutes`` class: it still judges the address and key shapes."""

    def build(url: str, api_key: str, **_: Any) -> FakeClient:
        FiveMoreMinutes(url, api_key)  # raises FmmError("config", ...) for a bad address or key
        return service.client(api_key)

    return build
