"""The dashboard card: what it reads from the entities, and the file the integration serves."""

from __future__ import annotations

import re

from homeassistant.core import HomeAssistant

from custom_components.five_more_minutes import CARD_FILE

from .common import FakeService, make_state


async def test_what_ends_says_when_it_began(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    # The card's ring shows how far through the time or the lock is, so it needs the start as well as the end.
    service.state = make_state(timer_minutes=20, lock_minutes=None)
    await setup_entry()

    timer = hass.states.get("sensor.elliots_laptop_timer_ends")
    assert timer.attributes["started_at"] == service.state.timer.starts_at
    assert "started_at" not in hass.states.get("sensor.elliots_laptop_lock_ends").attributes


async def test_a_lock_says_when_it_began(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    service.state = make_state(lock_minutes=10)
    await setup_entry()

    assert hass.states.get("sensor.elliots_laptop_lock_ends").attributes["started_at"] == service.state.lock.starts_at
    assert "started_at" not in hass.states.get("sensor.elliots_laptop_timer_ends").attributes


async def test_sets_up_without_a_web_server(hass: HomeAssistant, setup_entry, service: FakeService) -> None:
    # Tests and a bare core have no frontend: the card is skipped, and the computer works as before.
    service.state = make_state(timer_minutes=5)
    await setup_entry()
    assert hass.states.get("sensor.elliots_laptop_minutes_left").state == "5"


def test_the_card_file_is_there_and_names_its_card() -> None:
    script = CARD_FILE.read_text(encoding="utf-8")
    assert 'const CARD = "five-more-minutes-card";' in script
    assert "customElements.define(CARD" in script
    # It may not fetch anything from elsewhere: everything it shows is in the file.
    assert not re.search(r"https?://(?!github\.com/Five-More-Minutes-App/)", script)


def test_the_card_speaks_both_languages_alike() -> None:
    script = CARD_FILE.read_text(encoding="utf-8")
    english = script[script.index("  en: {") : script.index("  sv: {")]
    swedish = script[script.index("  sv: {") : script.index("};", script.index("  sv: {"))]
    keys = lambda block: re.findall(r"^\s{4}(\w+):", block, re.MULTILINE)  # noqa: E731
    assert keys(english) == keys(swedish)


def test_the_card_calls_only_actions_that_exist() -> None:
    script = CARD_FILE.read_text(encoding="utf-8")
    called = set(re.findall(r'\["(\w+)", ', script))
    assert called == {"start_timer", "extend_timer", "end_time", "cancel_timer"}
