"""User configuration loading.

Reads ``~/.config/pdfreader/config.toml`` (if present) and merges it over the
built-in defaults.  Missing or malformed files fall back to the defaults.
"""

import os
import tomllib

DEFAULTS = {
    "night_mode": False,
    "fullscreen_on_open": False,
}


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(base, "pdfreader", "config.toml")


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(config_path(), "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return cfg
    for key in DEFAULTS:
        if key in data:
            cfg[key] = data[key]
    return cfg
