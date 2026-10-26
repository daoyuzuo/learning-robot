"""Write one-time user environment configuration.

The module never logs or returns secret values. Tests inject a fake writer so
they do not touch the real Windows registry.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urlsplit


class EnvWriteError(Exception):
    """The user environment could not be written."""


class EnvWriter(Protocol):
    def set_user_env(self, values: Mapping[str, str]) -> None: ...


class WindowsUserEnv:
    """Write HKCU\\Environment and notify new processes."""

    def set_user_env(self, values: Mapping[str, str]) -> None:
        if os.name != "nt":
            raise EnvWriteError("Windows user environment is only available on Windows")
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
            ) as key:
                for name, value in values.items():
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        except OSError as exc:
            raise EnvWriteError(type(exc).__name__) from None
        _broadcast_environment_change()


def _broadcast_environment_change() -> None:
    import ctypes

    hwnd_broadcast = 0xFFFF
    wm_settingchange = 0x001A
    smto_abortifhung = 0x0002
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        hwnd_broadcast,
        wm_settingchange,
        0,
        "Environment",
        smto_abortifhung,
        5000,
        ctypes.byref(result),
    )


def write_user_env(
    values: Mapping[str, str], *, writer: EnvWriter | None = None
) -> None:
    selected = writer or WindowsUserEnv()
    selected.set_user_env(dict(values))


def export_lines(values: Mapping[str, str]) -> list[str]:
    return [
        f'export {name}="{str(value).replace(chr(34), chr(92) + chr(34))}"'
        for name, value in values.items()
    ]


def display_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return "(invalid)"
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return "(invalid)"
    host = parts.hostname
    if port:
        host = f"{host}:{port}"
    return f"{parts.scheme}://{host}"


def secret_status(value: str | None) -> str:
    return f"set ({len(value)} chars)" if value else "missing"
