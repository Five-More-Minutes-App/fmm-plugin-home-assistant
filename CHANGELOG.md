# Changelog

## 1.1.1

- Nothing in what the integration does has changed. This is the first release HACS offers to everyone: 1.1.0 was published as a pre-release.
- The version is the same in every file that states it (`pyproject.toml` still said 1.0.0). A test keeps them the same, and a check on every pull request asks for a new version when the integration has changed since the last release.

## 1.1.0

- A dashboard card comes with the integration: the countdown on a ring, the lock, whether the computer is connected, and buttons to start (with a message), add time, end and cancel, as far as the key allows. **Add card → Five More Minutes.**
- **Timer ends** and **Lock ends** say when they began (`started_at`).
- The address is filled in with the hosted service, `https://api.fivemoreminutes.app`, and setup works against it with a key that names your home's internet address. The "only answers on your home network" error now says what to change in the portal.

## 1.0.0

First release.

- One device per computer with sensors, an activity event, buttons and a timer length, all followed by a held-open request instead of polling.
- Actions to start, extend, end and cancel, for automations.
- Buttons and actions exist only for what the key is allowed to do.
- Setup, re-authentication and reconfiguration with clear errors; diagnostics with anything private removed.
- English and Swedish.
