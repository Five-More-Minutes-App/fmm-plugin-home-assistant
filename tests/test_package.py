"""The package as a whole: diagnostics, and that the text files agree with each other and with the code."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from homeassistant.core import HomeAssistant

from custom_components.five_more_minutes import services
from custom_components.five_more_minutes.const import (
    CONF_API_KEY,
    CONF_URL,
    EVENT_TYPES,
    SERVICE_CANCEL_TIMER,
    SERVICE_END_TIME,
    SERVICE_EXTEND_TIMER,
    SERVICE_START_TIMER,
)
from custom_components.five_more_minutes.diagnostics import async_get_config_entry_diagnostics

from .common import COMPUTER_ID, KEY, URL, FakeService, make_state

ROOT = Path(__file__).parent.parent
COMPONENT = ROOT / "custom_components" / "five_more_minutes"


async def test_diagnostics_hold_nothing_private(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    service.state = make_state(timer_minutes=10, timer_message="Homework for Elliot")
    entry = await setup_entry()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(diagnostics, default=str)

    for private in (KEY, URL, "192.168.1.10", COMPUTER_ID, "Elliots laptop", "Homework for Elliot"):
        assert private not in text, private
    assert diagnostics["entry"]["data"] == {CONF_URL: "**REDACTED**", CONF_API_KEY: "**REDACTED**"}
    assert diagnostics["permissions"] == sorted(service.scopes)
    assert diagnostics["last_update_success"] is True
    assert diagnostics["state"]["timer"] is not None, "what is useful for a bug report is still there"


def _walk(node: dict, prefix: str = "") -> set[str]:
    return {
        key
        for name, value in node.items()
        for key in ([f"{prefix}{name}"] if not isinstance(value, dict) else _walk(value, f"{prefix}{name}."))
    }


def _load(name: str) -> dict:
    return json.loads((COMPONENT / "translations" / f"{name}.json").read_text(encoding="utf-8"))


def _holes(text: str) -> list[str]:
    return sorted(re.findall(r"\{(\w+)\}", text))


def _get(node: dict, dotted: str) -> str:
    for part in dotted.split("."):
        node = node[part]
    return node  # type: ignore[return-value]


def test_swedish_says_everything_english_does() -> None:
    en, sv = _load("en"), _load("sv")

    assert _walk(sv) == _walk(en)


def test_swedish_keeps_every_placeholder() -> None:
    en, sv = _load("en"), _load("sv")

    for key in _walk(en):
        assert _holes(_get(sv, key)) == _holes(_get(en, key)), key


def test_the_services_are_described_and_translated() -> None:
    described = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))
    names = {SERVICE_START_TIMER, SERVICE_EXTEND_TIMER, SERVICE_END_TIME, SERVICE_CANCEL_TIMER}
    assert set(described) == names

    for language in ("en", "sv"):
        translated = _load(language)["services"]
        assert set(translated) == names, language
        for name, service in described.items():
            assert set(service.get("fields", {})) == set(translated[name].get("fields", {})), f"{language} {name}"


def test_every_event_type_has_a_translation() -> None:
    for language in ("en", "sv"):
        states = _load(language)["entity"]["event"]["activity"]["state_attributes"]["event_type"]["state"]
        assert set(states) == set(EVENT_TYPES), language


def test_every_error_the_flow_can_show_has_words() -> None:
    source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    used = set(
        re.findall(
            r'"(invalid_\w+|network_only|cannot_connect|missing_state_permission|unknown|wrong_computer)"', source
        )
    )

    for language in ("en", "sv"):
        table = _load(language)["config"]
        for key in used:
            assert key in table["error"] or key in table["abort"], f"{language}: {key}"


def test_every_exception_the_code_raises_has_words() -> None:
    raised = set()
    for module in ("__init__.py", "coordinator.py", "services.py"):
        raised |= set(re.findall(r'translation_key="(\w+)"', (COMPONENT / module).read_text(encoding="utf-8")))

    for language in ("en", "sv"):
        assert raised <= set(_load(language)["exceptions"]), language


def test_every_entity_has_a_name_and_an_icon() -> None:
    icons = json.loads((COMPONENT / "icons.json").read_text(encoding="utf-8"))["entity"]
    en = _load("en")["entity"]

    for domain, entities in en.items():
        for key in entities:
            assert key in icons[domain], f"no icon for {domain}.{key}"


def test_the_manifest_is_what_home_assistant_and_hacs_need() -> None:
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert manifest["domain"] == "five_more_minutes"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "local_push", "it is followed, not polled, and never leaves the home network"
    assert manifest["requirements"] == [], "nothing to install"
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert hacs["name"] == "Five More Minutes"


def test_the_service_schemas_cap_what_can_be_asked() -> None:
    assert services.MAX_TIMER_MINUTES == 1440
    assert services.MAX_MESSAGE_LENGTH == 100
