"""Five More Minutes: see and control the screen time on a computer from Home Assistant."""

from __future__ import annotations

from pathlib import Path

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FiveMoreMinutes, FmmError
from .const import CONF_API_KEY, CONF_URL, DOMAIN, SCOPE_STATE
from .coordinator import FmmConfigEntry, FmmCoordinator, FmmData
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


CARD_URL = f"/{DOMAIN}/five-more-minutes-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "five-more-minutes-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Registers the services, which act on a computer by its device, and the dashboard card."""
    async_setup_services(hass)
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serves the card from the integration and loads it on every dashboard, so it is under "Add card" at once.

    Skipped where Home Assistant has no web server or frontend (tests, a bare core): the integration works without it.
    """
    if hass.http is None or "frontend" not in hass.config.components:
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    # The file's age in the address, so a browser fetches the new card after an update instead of its cached one.
    changed = int((await hass.async_add_executor_job(CARD_FILE.stat)).st_mtime)
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={changed}")


async def async_setup_entry(hass: HomeAssistant, entry: FmmConfigEntry) -> bool:
    """Connects to one computer."""
    try:
        client = FiveMoreMinutes(entry.data[CONF_URL], entry.data[CONF_API_KEY], session=async_get_clientsession(hass))
        me = await client.me()
    except FmmError as error:
        if error.kind == "auth":
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="key_refused") from error
        if error.kind in ("config", "network-only"):
            # Trying again will not change a bad address, or a network the service will not answer.
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"reason": str(error)},
            ) from error
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect", translation_placeholders={"reason": str(error)}
        ) from error

    if SCOPE_STATE not in me.scopes:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="missing_state_permission")

    coordinator = FmmCoordinator(hass, entry, client, frozenset(me.scopes))
    # The first look. A key that is refused here starts the re-authentication flow by itself.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = FmmData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start_following()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FmmConfigEntry) -> bool:
    """Stops following the computer and removes its entities."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
