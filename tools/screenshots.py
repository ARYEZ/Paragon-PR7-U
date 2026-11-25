"""Screenshots of the real PR7-U window on a stand-in family (no network, nothing installed):
QT_SCALE_FACTOR=2 python tools/screenshots.py OUT_DIR"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tempfile  # noqa: E402

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())   # not the real ones

from pr7u import family, theme  # noqa: E402
from pr7u.main_window import MainWindow  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()

LATEST = dict(zip(["Z", "W", "L", "F", "E", "R", "P", "M", "Q", "DU", "CB", "IS", "PM", "SM"], ["0.4.0", "0.3.0", "0.7.0", "0.5.0", "1.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0", "0.1.0"]))
SIZES = dict(zip(["Z", "W", "L", "F", "E", "R", "P", "M", "Q", "DU", "CB", "IS", "PM", "SM"], [36.4, 27.4, 36.9, 42.1, 42.4, 38.0, 37.2, 61.5, 35.4, 34.8, 35.6, 35.9, 41.2, 37.8]))
registry = {}


def fetch(url):
    k = url.split("/repos/ARYEZ/Paragon-PR7-")[1].split("/")[0]
    v = LATEST[k]
    return json.dumps({"tag_name": f"v{v}", "html_url": "", "body": "",
                       "assets": [{"name": f"PR7-{k}-Setup-{v}.exe", "size": int(SIZES[k] * 1e6),
                                   "browser_download_url": "http://localhost/x"}]}).encode()


def have(k, v):
    registry[family.APPS[f"PR7-{k}"]] = {"DisplayVersion": v, "InstallLocation": "", "UninstallString": ""}


def window():
    w = MainWindow(fetch=fetch, reader=registry.get)
    w.sync = True
    w.resize(980, 860)
    w.show()
    return w


def shoot(w, name):
    app.processEvents()
    w.grab().save(str(out / name))
    print(out / name)


have("Z", "0.3.0"); have("W", "0.2.0"); have("E", "1.1.0")
w = window(); w.start = "choose"; w.refresh()
shoot(w, "choose.png")

w.running = True
w.job = [(k, "install") for k in "ZWLFRPMQ"]
w.results = {}
w.job_bytes = (0, int(sum(SIZES[k] for k in "ZWLFRPMQ") * 1e6))
w._show("progress")
states = {"Z": ("done", "UPDATED TO 0.4.0"), "W": ("done", "UPDATED TO 0.3.0"), "L": ("done", "INSTALLED 0.7.0"),
          "F": ("install", "INSTALLING..."), "E": ("skip", "UP TO DATE"), "R": ("download", "17.5 MB OF 38.0 MB"),
          "P": ("wait", "WAITING"), "M": ("wait", "WAITING"), "Q": ("wait", "WAITING")}
for k, (kind, text) in states.items():
    w.widgets[k].show_progress(kind, text, 0.46 if kind == "download" else None)
    if kind == "done":
        w.results[k] = "done"
w._current = ("R", int(17.5e6))
w._progress_summary()
shoot(w, "installing.png")
w.running = False
w.close()

for k in "LFRPMQ":
    have(k, LATEST[k])
registry.pop(family.APPS["PR7-L"]); registry.pop(family.APPS["PR7-F"])
have("Z", "0.4.0")
w = window()
w.set_finish("aurora")
w.refresh()
shoot(w, "manage_aurora.png")
w.set_finish("obsidian")
w.close()
