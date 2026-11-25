import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PARAGON_FAMILY_FILE"] = os.path.join(__import__("tempfile").mkdtemp(prefix="family-"), "finish")  # never the real choice
os.environ.pop("PR7U_GITHUB_TOKEN", None)
LETTERS = ["Z", "W", "L", "F", "E", "R", "P", "M", "Q", "DU", "CB", "IS", "PM", "SM", "HB", "FS", "AR", "WM", "HX", "DB", "UN", "LN"]
VERSIONS = ["0.4.0", "0.3.0", "0.7.0", "0.5.0", "1.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0"]


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    # Tests never write the real settings: QSettings goes to INI files in a temp folder.
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from pr7u import theme
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings")))
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    theme.load_fonts()
    app.setPalette(theme.palette())
    yield app
    for w in app.topLevelWidgets():
        w.close()
    app.processEvents()


@pytest.fixture
def clean_settings(qapp):
    from PySide6.QtCore import QSettings
    s = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, "Paragon", "PR7-U")
    s.clear(); s.sync()
    yield
    s.clear(); s.sync()


class Family:
    """A stand-in for GitHub and Windows: each app's latest release (JSON as GitHub sends it), its setup file on a
    local web server, the uninstall entries in the registry, and installers that write them the way Inno Setup does.

    A setup file's bytes are "SETUP <name> <version>"; running it installs that version (`ran` records each run)."""

    def __init__(self, server_root: str):
        self.base = server_root
        self.latest: dict[str, str | None] = {}        # "PR7-Z" -> "0.4.0" (None: no release)
        self.registry: dict[str, dict] = {}           # AppId -> uninstall entry
        self.ran: list[list[str]] = []
        self.broken: set[str] = set()                 # apps whose GitHub answer fails
        self.failing: set[str] = set()                # apps whose installer fails
        self.short: set[str] = set()                  # apps whose download stops early
        self.files: dict[str, bytes] = {}
        self.home = "C:\\Users\\me\\AppData\\Local\\Programs"

    def release(self, name: str, version: str | None):
        self.latest[name] = version
        if version:
            self.files[f"/{name}-Setup-{version}.exe"] = f"SETUP {name} {version}\n".encode() + b"x" * 5000

    def install(self, name: str, version: str):
        from pr7u import family
        self.registry[family.APPS[name]] = {"DisplayVersion": version, "InstallLocation": f"{self.home}\\{name}",
                                            "UninstallString": f'"{self.home}\\{name}\\unins000.exe"'}

    # ------------------------------------------------ what PR7-U is handed
    def fetch(self, url: str) -> bytes:
        name = url.split("/repos/ARYEZ/Paragon-")[1].split("/")[0]
        if name in self.broken:
            raise OSError("network down")
        v = self.latest.get(name)
        if not v:
            import urllib.error
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        asset = f"{name}-Setup-{v}.exe"
        size = len(self.files[f"/{asset}"])
        return json.dumps({"tag_name": f"v{v}", "html_url": f"https://github.com/ARYEZ/Paragon-{name}/releases/v{v}",
                           "draft": False, "prerelease": False, "body": f"## {v}\r\n- Better {name}.",
                           "assets": [{"name": f"{name}-v{v}-windows-x64.zip", "size": 1,
                                       "browser_download_url": f"{self.base}/zip"},
                                      {"name": asset, "size": size,
                                       "browser_download_url": f"{self.base}/{asset}"}]}).encode()

    def reader(self, appid: str):
        return self.registry.get(appid)

    def runner(self, args: list[str]) -> int:
        self.ran.append(list(args))
        exe = args[0]
        if exe.lower().endswith("unins000.exe"):
            from pr7u import family
            name = exe.replace("\\", "/").split("/")[-2]
            self.registry.pop(family.APPS[name], None)
            return 0
        content = Path(exe).read_bytes().split(b"\n")[0].decode().split()
        _, name, version = content
        if name in self.failing:
            return 5
        self.install(name, version)
        return 0


@pytest.fixture
def fam(tmp_path):
    state = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            f = state["fam"]
            body = f.files.get(self.path)
            if body is None:
                self.send_response(404); self.end_headers(); return
            name = self.path[1:].split("-Setup-")[0]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body[: len(body) // 2] if name in f.short else body)

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    f = Family(f"http://127.0.0.1:{server.server_address[1]}")
    state["fam"] = f
    for letter, v in zip(LETTERS, VERSIONS):
        f.release(f"PR7-{letter}", v)
    yield f
    server.shutdown()


@pytest.fixture
def window(qapp, clean_settings, fam):
    from pr7u.main_window import MainWindow
    w = MainWindow(fetch=fam.fetch, runner=fam.runner, reader=fam.reader)
    w.sync = True
    w.answers["say"] = lambda kind, text: w.said.append((kind, text))
    w.said = []
    w.show()
    yield w
    w.running = False
    # rows a view rebuild replaced wait for deleteLater: delete them now, while their window is still whole (a later
    # test's event loop would otherwise delete them as Python cleans the window up: a segfault)
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    w.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    del w
    import gc
    gc.collect()        # now, on the main thread: not at a random later moment, maybe on a server thread (a segfault)
