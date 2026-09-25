"""Fixtures: a fake service, and a config entry that is set up against it."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.five_more_minutes.const import CONF_API_KEY, CONF_URL, DOMAIN

from .common import COMPUTER_ID, KEY, URL, FakeService, factory, patch_target

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Lets Home Assistant load the integration from custom_components."""


@pytest.fixture
def service() -> Generator[FakeService]:
    """The service every client in the test talks to."""
    fake = FakeService()
    with ExitStack() as stack:
        for target in patch_target():
            stack.enter_context(patch(target, side_effect=factory(fake)))
        yield fake


@pytest.fixture
def entry() -> MockConfigEntry:
    """A computer, as if it had been set up with a key."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Elliots laptop",
        unique_id=COMPUTER_ID,
        data={CONF_URL: URL, CONF_API_KEY: KEY},
    )


@pytest.fixture
def setup_entry(hass: HomeAssistant, entry: MockConfigEntry, service: FakeService) -> Callable[[], object]:
    """Sets the entry up and waits for it."""

    async def run() -> MockConfigEntry:
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return run
