"""The Paragon PR7 family as PR7-U knows it (no Qt): each app's letter, what it is, the program it works like, its
GitHub repository and its permanent AppId (from family.py), and what is installed on this computer.

Installed apps are read from their installers' uninstall entries (HKCU\\...\\Uninstall\\{AppId}_is1, written by
Inno Setup): DisplayVersion, InstallLocation and UninstallString. `reader` replaces the registry in tests."""

from __future__ import annotations

import os
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import family

ICONS = Path(__file__).parent / "icons" / "apps"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{}_is1"


@dataclass(frozen=True)
class App:
    letter: str
    what: str
    like: str
    first_args: tuple = ()        # extra installer switches for a first install only (see PR7-W)

    @property
    def name(self) -> str:
        return f"PR7-{self.letter}"

    @property
    def repo(self) -> str:
        return f"ARYEZ/Paragon-PR7-{self.letter}"

    @property
    def appid(self) -> str:
        return family.APPS[self.name]

    @property
    def icon(self) -> str:
        return str(ICONS / f"{self.letter.lower()}.png")


APPS = [
    App("Z", "Archive manager", "7-Zip"),
    # Its "Replace Windows Notepad" task is ticked by default and asks for administrator permission: a first install
    # from PR7-U leaves it out, so a batch of installs never stops at a UAC prompt (PR7-W's Settings turn it on).
    App("W", "Text editor", "Notepad2", ("/MERGETASKS=!replacenotepad",)),
    App("L", "Tag editor", "Mp3tag"),
    App("F", "File transfer", "FileZilla"),
    App("E", "File manager", "GNOME Files"),
    App("R", "PDF reader", "SumatraPDF"),
    App("P", "Image viewer", "IrfanView"),
    App("M", "Media player", "MPC-HC"),
    App("Q", "Screenshots", "Greenshot"),
    App("DU", "Disk usage", "WizTree"),          # Paragon-PR7-D was already taken: two letters
    App("CB", "Clipboard history", "Ditto"),     # Paragon-PR7-C was too
    # Its index service task needs administrator permission once: a first install from PR7-U leaves it out (no UAC
    # prompt mid-batch); PR7-IS's window then offers INSTALL THE INDEX SERVICE.
    App("IS", "File search", "Everything", ("/MERGETASKS=!service",)),
    App("PM", "Password manager", "KeePassXC"),
]
BY_LETTER = {a.letter: a for a in APPS}


def pick(spec: str) -> list[App]:
    """ "all" or letters / names ("Z,W", "pr7-q") -> apps in catalogue order; unknown ones raise ValueError."""
    if spec.strip().lower() == "all":
        return list(APPS)
    want = set()
    for part in spec.replace(" ", ",").split(","):
        part = part.strip().upper().removeprefix("PR7-")
        if not part:
            continue
        if part not in BY_LETTER:
            raise ValueError(f"No family app called {part!r}.")
        want.add(part)
    return [a for a in APPS if a.letter in want]


@dataclass
class Installed:
    version: str
    location: str = ""
    uninstall: str = ""           # the uninstaller's command line as Windows keeps it
    extra: dict = field(default_factory=dict)

    @property
    def exe(self) -> str:
        return os.path.join(self.location, f"{self.extra.get('name', '')}.exe") if self.location else ""


def _registry(appid: str) -> dict | None:
    if sys.platform != "win32":
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL.format(appid)) as k:
            out = {}
            for name in ("DisplayVersion", "InstallLocation", "UninstallString"):
                try:
                    out[name] = str(winreg.QueryValueEx(k, name)[0])
                except OSError:
                    out[name] = ""
            return out
    except OSError:
        return None


def installed(app: App, reader=None) -> Installed | None:
    """What's installed of `app`, or None. `reader(appid)` -> the uninstall entry's values or None."""
    values = (reader or _registry)(app.appid)
    if not values:
        return None
    return Installed(values.get("DisplayVersion", "") or "?", values.get("InstallLocation", ""),
                     values.get("UninstallString", ""), {"name": app.name})


def uninstall_command(inst: Installed) -> list[str]:
    """The uninstaller, quiet: Inno Setup's unins000.exe with /VERYSILENT (no questions, no windows)."""
    cmd = inst.uninstall.strip()
    if not cmd:
        if not inst.location:
            raise ValueError("Windows has no uninstaller for it.")
        cmd = f'"{os.path.join(inst.location, "unins000.exe")}"'
    parts = shlex.split(cmd, posix=False)
    exe = parts[0].strip('"')
    return [exe, *[p for p in parts[1:] if p.upper() not in ("/SILENT", "/VERYSILENT")],
            "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
