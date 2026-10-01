"""The schema library Home Assistant uses, whichever one this Home Assistant has.

Home Assistant 2026.10 replaced ``voluptuous`` with ``probatio``, a drop-in with the same names. The
integration supports Home Assistant from 2025.10 (hacs.json), which still has ``voluptuous``, so it takes
whichever one is installed. Everything that builds a schema imports ``vol`` from here.
"""

from __future__ import annotations

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.10
    import voluptuous as vol  # type: ignore[no-redef]

__all__ = ["vol"]
