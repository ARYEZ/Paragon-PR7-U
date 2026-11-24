"""Start PR7-U.

    PR7-U.exe                         the window (started again, it brings the running one forward)
    PR7-U.exe --choose                open on "Install the family" (the installer's finish page)
    PR7-U.exe --install all|Z,W,...   install / update those apps without a window, then exit (1 if one failed)
    PR7-U.exe --uninstall all|Z,...   uninstall them without a window
    PR7-U.exe --list OUT.json         what's installed and the newest release of each app, as JSON
    PR7-U.exe --version
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import sys

TIMEOUT_MS = 1500


def server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "user"
    return "Paragon-PR7-U-" + hashlib.sha1(user.encode()).hexdigest()[:12]


def hand_over(view: str) -> bool:
    """If PR7-U is running, bring it forward (on `view` when given); True if it was there."""
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(server_name())
    if not s.waitForConnected(TIMEOUT_MS):
        return False
    s.write(json.dumps({"show": view}).encode() + b"\n")
    s.flush()
    s.waitForBytesWritten(TIMEOUT_MS)
    if not s.waitForDisconnected(TIMEOUT_MS):
        s.disconnectFromServer()
    return True


def listen(window):
    """Later starts hand over to this window (PR7-R's hand-off, with its Windows fix: data already waiting is read
    at once, and a connection closed before readyRead is still read)."""
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(window)
    QLocalServer.removeServer(server_name())
    if not server.listen(server_name()):
        return None

    def connection():
        sock = server.nextPendingConnection()
        if sock is None:
            return
        buf = bytearray()
        done = []

        def read():
            buf.extend(bytes(sock.readAll()))
            if buf.endswith(b"\n") and not done:
                done.append(True)
                try:
                    msg = json.loads(buf.decode())
                except ValueError:
                    return
                window.showNormal(); window.raise_(); window.activateWindow()
                if msg.get("show") == "choose" and not window.running and window.rows:
                    window._show("choose")
                sock.disconnectFromServer()
        sock.readyRead.connect(read)
        sock.disconnected.connect(read)
        if sock.bytesAvailable():
            read()
    server.newConnection.connect(connection)
    window.instance_server = server
    return server


def listing(out: str, fetch=None, reader=None) -> int:
    from . import releases
    rows = releases.survey(fetch=fetch, reader=reader)
    data = [{"app": r.app.name, "state": r.state, "installed": r.installed.version if r.installed else None,
             "latest": r.release.version if r.release else None, "size": r.release.size if r.release else 0,
             "error": r.error} for r in rows]
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    return 1 if any(r.error for r in rows) else 0


def headless(action: str, spec: str, fetch=None, opener=None, runner=None, reader=None, say=print) -> int:
    """--install / --uninstall without a window: one line per app, exit code 1 if any failed."""
    from . import catalog, releases
    from .updates import UpdateError
    try:
        apps = catalog.pick(spec)
    except ValueError as e:
        say(str(e))
        return 2
    rows = releases.survey(apps, fetch=fetch, reader=reader, online=action == "install")
    failed = 0
    for r in rows:
        try:
            if action == "uninstall":
                if r.installed is None:
                    say(f"{r.app.name}: not installed")
                    continue
                releases.uninstall(r, runner=runner, reader=reader)
                say(f"{r.app.name}: uninstalled")
            elif r.state == "error":
                raise UpdateError(r.error)
            elif r.state == "unreleased":
                say(f"{r.app.name}: no release yet")
            elif r.state == "current":
                say(f"{r.app.name}: up to date ({r.installed.version})")
            else:
                before = r.installed.version if r.installed else None
                releases.install(r, opener=opener, runner=runner, reader=reader)
                say(f"{r.app.name}: " + (f"updated {before} -> {r.installed.version}" if before else
                                         f"installed {r.installed.version}"))
        except (UpdateError, OSError, ValueError) as e:
            failed += 1
            say(f"{r.app.name}: FAILED: {e}")
    return 1 if failed else 0


def _stdout() -> None:
    """A windowed program (PR7-U.exe has no console) starts with sys.stdout = None, so the command-line modes' lines
    would vanish; write them to the standard output Windows handed over (a pipe or a console) when there is one."""
    if sys.stdout is not None or sys.platform != "win32":
        return
    import ctypes
    import msvcrt
    get = ctypes.windll.kernel32.GetStdHandle
    get.restype = ctypes.c_void_p
    handle = get(-11)                                     # STD_OUTPUT_HANDLE
    if handle in (None, 0, ctypes.c_void_p(-1).value):
        return
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
        sys.stdout = open(fd, "w", encoding="utf-8", buffering=1)  # noqa: SIM115 - lives as long as the process
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] in (["--version"], ["--list"], ["--install"], ["--uninstall"]):
        _stdout()
    if argv[:1] == ["--version"]:
        from . import __version__
        print(__version__)
        return 0
    if argv[:1] == ["--list"] and len(argv) == 2:
        return listing(argv[1])
    if argv[:1] in (["--install"], ["--uninstall"]):
        return headless(argv[0][2:], argv[1] if len(argv) > 1 else "all")
    from PySide6.QtWidgets import QApplication

    from . import settings, theme
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName("Paragon")
    app.setApplicationName("PR7-U")
    view = "choose" if "--choose" in argv else "auto"
    if hand_over(view):
        return 0
    theme.set_finish(settings.get("finish", "obsidian"))
    theme.load_fonts()
    from PySide6.QtGui import QIcon
    icon = os.path.join(os.path.dirname(__file__), "icons", "app.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    from .main_window import MainWindow
    win = MainWindow(start=view)
    listen(win)
    win.show()
    win.refresh()
    from . import update_ui
    update_ui.start(win)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
