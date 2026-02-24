"""Theme and configuration management.

Loads palette colours and display settings from ``pitop.toml``, falling
back to sensible defaults when the file is missing or malformed.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Display configuration
# ------------------------------------------------------------------

@dataclass(slots=True)
class DisplayConfig:
    graph_height: int = 3
    max_processes: int = 50
    update_interval: float = 1.0
    max_history: int = 120
    process_update_interval: int = 3  # ticks between process refreshes


# ------------------------------------------------------------------
# Default palette
# ------------------------------------------------------------------

DEFAULT_PALETTE: list[tuple[str, str, str]] = [
    ("header",       "white,bold",     "dark blue"),
    ("footer",       "white",          "dark blue"),
    ("body",         "light gray",     "black"),
    ("bold",         "white,bold",     "black"),
    ("dim",          "dark gray",      "black"),
    ("process",      "light gray",     "black"),
    ("highlighted",  "black,bold",     "light gray"),
    ("normal",       "light green",    "black"),
    ("warning",      "yellow",         "black"),
    ("critical",     "light red,bold", "black"),
    ("graph_normal", "light green",    "black"),
    ("graph_border", "dark cyan",      "black"),
    ("title",        "white,bold",     "black"),
    ("key",          "light cyan,bold", "dark blue"),
    ("key_label",    "white",          "dark blue"),
    ("filter_edit",  "white",          "dark gray"),
    ("popup",        "white",          "dark gray"),
    ("popup_border", "light cyan",     "dark gray"),
    ("disk",         "light cyan",     "black"),
    ("sort_active",  "white,bold",     "black"),
]


# ------------------------------------------------------------------
# Loader
# ------------------------------------------------------------------

def load_config(
    config_path: str | None = None,
) -> tuple[list[tuple[str, str, str]], DisplayConfig]:
    """Load palette and display settings from a TOML file.

    Returns ``(palette, display_config)``.
    """

    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "pitop.toml"
        )

    try:
        with open(config_path, "rb") as fh:
            config = tomllib.load(fh)
    except (FileNotFoundError, Exception) as exc:
        logger.debug("Using default config: %s", exc)
        return list(DEFAULT_PALETTE), DisplayConfig()

    # -- palette overrides ------------------------------------------------
    palette = list(DEFAULT_PALETTE)
    p = config.get("palette", {})

    overrides: dict[str, tuple[str, str]] = {
        "header":      (p.get("header_fg",      "white,bold"),     p.get("header_bg",      "dark blue")),
        "footer":      (p.get("footer_fg",      "white"),          p.get("footer_bg",      "dark blue")),
        "body":        (p.get("body_fg",         "light gray"),     p.get("body_bg",         "black")),
        "normal":      (p.get("normal_fg",       "light green"),    p.get("normal_bg",       "black")),
        "warning":     (p.get("warning_fg",      "yellow"),         p.get("warning_bg",      "black")),
        "critical":    (p.get("critical_fg",     "light red,bold"), p.get("critical_bg",     "black")),
        "highlighted": (p.get("highlighted_fg",  "black,bold"),     p.get("highlighted_bg",  "light gray")),
        "process":     (p.get("process_fg",      "light gray"),     p.get("process_bg",      "black")),
    }

    for i, entry in enumerate(palette):
        name = entry[0]
        if name in overrides:
            fg, bg = overrides[name]
            palette[i] = (name, fg, bg)

    # -- display settings -------------------------------------------------
    d = config.get("display", {})
    display = DisplayConfig(
        graph_height=int(d.get("graph_height", 3)),
        max_processes=int(d.get("max_processes", 50)),
        update_interval=float(d.get("update_interval", 1.0)),
        max_history=int(d.get("max_history", 120)),
        process_update_interval=int(d.get("process_update_interval", 3)),
    )

    return palette, display
