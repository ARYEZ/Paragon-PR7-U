"""Each family app's latest release on GitHub, and installing / updating / removing it (no Qt).

The newest version comes from GitHub's public "latest release" address of the app's own repository, the same one
the app's own Check for Updates reads (updates.py), so PR7-U and the app always agree. Nothing about the user is
sent: the request names only PR7-U. The app's own installer (PR7-X-Setup-<version>.exe) is downloaded to a
temporary folder (".part" until whole) and run with /VERYSILENT, so the app installs exactly as it does by hand:
its Explorer menu, Open with and other ticked tasks; an update keeps the choices made before (UsePreviousTasks).

`fetch`, `opener`, `runner` and `reader` replace the network, the installer and the registry in tests."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import catalog, updates
from .catalog import App, Installed
from .updates import Release, UpdateError, is_newer

API = "https://api.github.com/repos/{}/releases/latest"
SETUP_SWITCHES = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]


def _fetch(url: str, timeout: float = 15) -> bytes:
    headers = {"User-Agent": "Paragon-PR7-U", "Accept": "application/vnd.github+json"}
    # CI only: GitHub allows 60 unauthenticated API requests an hour per address, and CI runners share addresses.
    # The workflow passes its own token here; on people's computers this is never set.
    token = os.environ.get("PR7U_GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - a fixed https address
        return r.read()


def latest(app: App, fetch=None) -> Release | None:
    """The app's newest published release with its installer, or None when it has none yet."""
    try:
        data = json.loads((fetch or _fetch)(API.format(app.repo)))
    except OSError as e:
        if getattr(e, "code", None) == 404:      # a repository with no releases answers 404
            return None
        raise UpdateError(f"GitHub couldn’t be reached ({getattr(e, 'reason', e)}).") from e
    except ValueError as e:
        raise UpdateError("GitHub’s answer couldn’t be read.") from e
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    pattern = re.compile(rf"^{re.escape(app.name)}-Setup-[\w.\-]+\.exe$", re.I)
    asset = next((a for a in data.get("assets", []) if pattern.match(a.get("name", ""))), None)
    if asset is None:
        return None
    return Release(data.get("tag_name", "").lstrip("vV"), data.get("html_url", f"https://github.com/{app.repo}"),
                   asset.get("browser_download_url", ""), int(asset.get("size") or 0),
                   (data.get("body") or "").replace("\r\n", "\n").strip())


@dataclass
class Row:
    """One app as the window shows it."""
    app: App
    installed: Installed | None = None
    release: Release | None = None
    error: str = ""

    @property
    def state(self) -> str:
        """new | update | current | unreleased (nothing to install yet) | error (GitHub couldn't be asked)."""
        if self.error:
            return "error"
        if self.release is None:
            return "current" if self.installed else "unreleased"
        if self.installed is None:
            return "new"
        return "update" if is_newer(self.release.version, self.installed.version) else "current"

    @property
    def wanted(self) -> bool:
        """Ticked at first: anything to install or update."""
        return self.state in ("new", "update")


def survey(apps=None, fetch=None, reader=None, online: bool = True) -> list[Row]:
    """Every app's installed version and newest release (asked for all apps at once)."""
    apps = list(apps or catalog.APPS)
    rows = [Row(a, catalog.installed(a, reader)) for a in apps]
    if not online:
        return rows

    def ask(row: Row):
        try:
            row.release = latest(row.app, fetch)
        except UpdateError as e:
            row.error = str(e)
    with ThreadPoolExecutor(max_workers=len(rows) or 1) as pool:
        list(pool.map(ask, rows))
    return rows


class Cancelled(Exception):
    pass


def _run(args: list[str], runner=None) -> int:
    if runner is not None:
        return runner(args)
    if sys.platform != "win32":
        raise UpdateError("Installing is for Windows.")
    return subprocess.run(args, check=False).returncode


def install(row: Row, report=lambda stage, done, total: None, cancelled=lambda: False, folder=None,
            opener=None, runner=None, reader=None) -> Installed:
    """Download the app's installer and run it silently; returns what's installed afterwards.
    report(stage, done, total): ("download", bytes, size), then ("install", 0, 0)."""
    if row.release is None:
        raise UpdateError("It has no release to install yet.")
    first = row.installed is None
    folder = folder or tempfile.mkdtemp(prefix="PR7-U-")
    try:
        try:
            path = updates.download(row.release, folder, lambda got, size: report("download", got, size),
                                    cancelled, opener)
        except UpdateError as e:
            if str(e) == "Cancelled.":
                raise Cancelled() from e
            raise
        if cancelled():
            raise Cancelled()
        report("install", 0, 0)
        args = [path, *SETUP_SWITCHES, *(row.app.first_args if first else ())]
        code = _run(args, runner)
        if code != 0:
            raise UpdateError(f"Its installer stopped with code {code}.")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    after = catalog.installed(row.app, reader)
    if after is None:
        raise UpdateError("Its installer finished but Windows doesn't list it.")
    if is_newer(row.release.version, after.version):
        raise UpdateError(f"Still at {after.version} after installing {row.release.version}.")
    row.installed = after
    return after


def uninstall(row: Row, runner=None, reader=None, wait: float = 120, sleep=time.sleep) -> None:
    """Run the app's own uninstaller quietly. Inno Setup's unins000.exe hands over to a copy of itself in a temporary
    folder and returns at once, so the uninstall entry is watched until Windows drops it."""
    if row.installed is None:
        return
    code = _run(catalog.uninstall_command(row.installed), runner)
    if code != 0:
        raise UpdateError(f"Its uninstaller stopped with code {code}.")
    end = time.monotonic() + wait
    while True:
        row.installed = catalog.installed(row.app, reader)
        if row.installed is None:
            return
        if time.monotonic() >= end:
            raise UpdateError("Windows still lists it.")
        sleep(1)
