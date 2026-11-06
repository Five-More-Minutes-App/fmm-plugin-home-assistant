# Changelog

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
