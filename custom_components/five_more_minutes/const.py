"""Constants for the Five More Minutes integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "five_more_minutes"
LOGGER = logging.getLogger(__package__)

CONF_URL: Final = "url"
CONF_API_KEY: Final = "api_key"

# The permissions a key can hold. This integration needs the first; the others switch on the buttons
# and services that use them, so a key that can only watch gives a dashboard with nothing to press.
SCOPE_STATE: Final = "state:read"
SCOPE_START: Final = "timer:start"
SCOPE_EXTEND: Final = "timer:extend"
SCOPE_STOP: Final = "timer:stop"
SCOPE_CANCEL: Final = "timer:cancel"

# How long a request to Five More Minutes is held open waiting for a change. The service's limit is 25.
WAIT_SECONDS: Final = 25

DEFAULT_TIMER_MINUTES: Final = 30
MAX_TIMER_MINUTES: Final = 1440
MAX_MESSAGE_LENGTH: Final = 100

SERVICE_START_TIMER: Final = "start_timer"
SERVICE_EXTEND_TIMER: Final = "extend_timer"
SERVICE_END_TIME: Final = "end_time"
SERVICE_CANCEL_TIMER: Final = "cancel_timer"

ATTR_MINUTES: Final = "minutes"
ATTR_UNTIL: Final = "until"
ATTR_MESSAGE: Final = "message"

# What the activity entity can report (see events.py, whose names these mirror).
EVENT_TYPES: Final = [
    "timer_started",
    "timer_extended",
    "timer_ended",
    "locked",
    "unlocked",
    "came_online",
    "went_offline",
]
