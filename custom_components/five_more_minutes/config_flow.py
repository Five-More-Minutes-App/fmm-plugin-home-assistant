"""Setting up a computer: an address and a key, checked before anything is saved."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import FiveMoreMinutes, FmmError, Me
from .const import CONF_API_KEY, CONF_URL, DOMAIN, LOGGER, SCOPE_STATE

# A key of the right shape that opens nothing, used to tell a bad address from a bad key.
_SHAPE_ONLY = f"fmmk_{'0' * 32}_{'A' * 43}"


def normalize_url(text: str) -> str:
    """Turns ``192.168.1.10:5072`` into ``http://192.168.1.10:5072``, which is what people type."""
    text = text.strip()
    if text and "://" not in text:
        text = f"http://{text}"
    parts = urlsplit(text)
    # The path is kept (the service may sit behind a reverse proxy at one); the end slash is not.
    return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}" if parts.netloc else text


KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="off"))


def _schema(url: str = "", *, ask_url: bool = True) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if ask_url:
        fields[vol.Required(CONF_URL, default=url)] = str
    fields[vol.Required(CONF_API_KEY)] = KEY_SELECTOR
    return vol.Schema(fields)


class FiveMoreMinutesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adds a computer with an address and a key made in the portal."""

    VERSION = 1

    async def _check(self, url: str, key: str) -> tuple[Me | None, str | None]:
        """Asks the service who the key is. Returns the answer, or the name of what is wrong."""
        try:
            FiveMoreMinutes(url, _SHAPE_ONLY)
        except FmmError:
            return None, "invalid_url"

        try:
            client = FiveMoreMinutes(url, key, session=async_get_clientsession(self.hass))
        except FmmError:
            return None, "invalid_key"

        try:
            me = await client.me()
        except FmmError as error:
            LOGGER.debug("Could not check the key: %s", error)
            return None, {"auth": "invalid_auth", "network-only": "network_only"}.get(error.kind, "cannot_connect")

        if SCOPE_STATE not in me.scopes:
            return None, "missing_state_permission"
        return me, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The first step: where Five More Minutes is, and the key."""
        errors: dict[str, str] = {}
        url = ""

        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            key = user_input[CONF_API_KEY].strip()
            me, problem = await self._check(url, key)

            if me is not None:
                # One entry per computer, however many keys there are for it.
                await self.async_set_unique_id(me.device_id)
                self._abort_if_unique_id_configured(updates={CONF_URL: url, CONF_API_KEY: key})
                return self.async_create_entry(title=me.device_name, data={CONF_URL: url, CONF_API_KEY: key})
            errors["base"] = problem or "unknown"

        return self.async_show_form(step_id="user", data_schema=_schema(url), errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The key stopped working: ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """A new key, for the same computer."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            me, problem = await self._check(entry.data[CONF_URL], key)

            if me is None:
                errors["base"] = problem or "unknown"
            elif me.device_id != entry.unique_id:
                # A key for another computer would silently turn this entry into that one.
                return self.async_abort(reason="wrong_computer")
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_API_KEY: key})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_schema(ask_url=False),
            description_placeholders={"computer": entry.title},
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """A new address and/or key, for the same computer."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        url = entry.data[CONF_URL]

        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            key = user_input[CONF_API_KEY].strip()
            me, problem = await self._check(url, key)

            if me is None:
                errors["base"] = problem or "unknown"
            elif me.device_id != entry.unique_id:
                return self.async_abort(reason="wrong_computer")
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_URL: url, CONF_API_KEY: key})

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(url),
            description_placeholders={"computer": entry.title},
            errors=errors,
        )
