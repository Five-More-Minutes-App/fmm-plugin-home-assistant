"""Five More Minutes: see and control the screen time on a computer from Home Assistant."""

from __future__ import annotations

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Registers the services, which act on a computer by its device."""
    async_setup_services(hass)
    return True


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
