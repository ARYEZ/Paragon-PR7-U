"""Mock-up pictures of PR7-U, drawn offscreen with real Qt widgets: python tools/mockup.py OUT_DIR

The versions and sizes are stand-ins; the real window reads them from GitHub and the installed apps."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT.parent                      # the other apps' checkouts, for their real icons
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar,  # noqa: E402
                               QPushButton, QVBoxLayout, QWidget)

from pr7u import theme, widgets  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/mockup")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()

APPS = [  # letter, what it is, works like, installed, latest, MB
    ("Z", "Archive manager", "7-Zip", "0.3.0", "0.4.0", 36.4),
    ("W", "Text editor", "Notepad2", "0.2.0", "0.3.0", 27.4),
    ("L", "Tag editor", "Mp3tag", "", "0.7.0", 36.9),
    ("F", "File transfer", "FileZilla", "", "0.5.0", 42.1),
    ("E", "File manager", "GNOME Files", "1.1.0", "1.1.0", 42.4),
    ("R", "PDF reader", "SumatraPDF", "", "0.1.0", 38.0),
    ("P", "Image viewer", "IrfanView", "", "0.1.0", 37.2),
    ("M", "Media player", "MPC-HC", "", "0.1.0", 61.5),
    ("Q", "Screenshots", "Greenshot", "", "0.1.0", 35.4),
]


def icon(letter: str, size: int = 40) -> QPixmap:
    path = FAMILY / f"paragon-pr7-{letter.lower()}" / f"pr7{letter.lower()}" / "icons" / "app.png"
    pm = QPixmap(str(path))
    return pm.scaled(QSize(size, size) * 2, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)


def label(text, role=None, size=None, bold=False):
    w = QLabel(text)
    if role:
        w.setProperty("role", role)
    if size or bold:
        f = w.font()
        if size:
            f.setPixelSize(size)
        if bold:
            f.setWeight(QFont.Weight.DemiBold)
        w.setFont(f)
    return w


PRIMARY = (f"QPushButton {{ background: {theme.qss_gradient()}; color: #FFFFFF; border: none; font-weight: 600; "
           "padding: 9px 22px; }")


class Pill(QLabel):
    """INSTALLED / UPDATE / NOT INSTALLED, as a small outlined tag."""

    def __init__(self, text, lit=False):
        super().__init__(text)
        f = self.font(); f.setPixelSize(10); f.setWeight(QFont.Weight.DemiBold); self.setFont(f)
        colour = theme.LED_ORANGE if lit else theme.TEXT_DIM
        self.setStyleSheet(f"color: {colour}; border: 1px solid {colour}; border-radius: 9px; padding: 2px 8px;")
        self.setFixedHeight(20)


def row(a, mode, state=None, alt=False):
    letter, what, like, have, latest, mb = a
    w = QFrame()
    w.setFixedHeight(64)
    w.setStyleSheet(f"QFrame {{ background: {theme.ALT_ROW if alt else theme.BACKGROUND}; }}")
    h = QHBoxLayout(w); h.setContentsMargins(18, 0, 22, 0); h.setSpacing(14)
    if mode == "choose":
        cb = QCheckBox(); cb.setChecked(have != latest); h.addWidget(cb)
    ic = QLabel(); pm = icon(letter); pm.setDevicePixelRatio(2); ic.setPixmap(pm); h.addWidget(ic)
    names = QVBoxLayout(); names.setSpacing(2)
    names.addStretch(1)
    names.addWidget(label(f"PR7-{letter}", size=15, bold=True))
    names.addWidget(label(f"{what}  ·  works like {like}", "dim", 12))
    names.addStretch(1)
    h.addLayout(names, 1)
    if mode == "choose":
        pill = (Pill("UP TO DATE") if have == latest else Pill("UPDATE", True) if have else Pill("NEW", True))
        h.addWidget(pill)
        ver = label(f"{have}  →  {latest}" if have and have != latest else latest, size=12)
        ver.setFixedWidth(110); ver.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(ver)
        size = label("" if have == latest else f"{mb:.1f} MB", "dim", 12)
        size.setFixedWidth(70); size.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(size)
    elif mode == "progress":
        kind, frac, text = state
        box = QVBoxLayout(); box.setSpacing(6)
        box.addStretch(1)
        t = label(text, "ok" if kind == "done" else "dim", 11)
        t.setAlignment(Qt.AlignmentFlag.AlignRight)
        box.addWidget(t)
        if kind in ("down", "install"):
            bar = QProgressBar(); bar.setTextVisible(False); bar.setFixedSize(260, 8)
            if kind == "install":
                bar.setRange(0, 100); bar.setValue(100)
            else:
                bar.setValue(int(frac * 100))
            box.addWidget(bar)
        box.addStretch(1)
        h.addLayout(box)
    else:  # manage
        have_ = latest if letter not in "LF" else have
        pill = Pill("UPDATE " + latest, True) if letter == "W" else Pill(f"INSTALLED {latest}")
        if letter in "LF":
            pill = Pill("NOT INSTALLED")
        h.addWidget(pill)
        b = QPushButton("INSTALL" if letter in "LF" else "UPDATE" if letter == "W" else "OPEN")
        b.setFixedWidth(96)
        if letter in "LFW":
            b.setStyleSheet(PRIMARY.replace("padding: 9px 22px", "padding: 7px 0"))
        h.addWidget(b)
        more = widgets.SmallKey("more", "More")
        h.addWidget(more)
    return w


def window(mode, states=None):
    win = QWidget()
    win.resize(980, 860)
    win.setPalette(theme.palette()); win.setStyleSheet(theme.stylesheet())
    win.setAutoFillBackground(True)
    v = QVBoxLayout(win); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
    v.addWidget(widgets.Header())
    top = QVBoxLayout(); top.setContentsMargins(22, 18, 22, 12); top.setSpacing(4)
    heading = {"choose": "INSTALL THE FAMILY", "progress": "INSTALLING", "manage": "YOUR PARAGON APPS"}[mode]
    top.addWidget(label(heading, "heading"))
    top.addWidget(label({
        "choose": "Tick the apps you want. Each comes from its latest release on GitHub and installs for you "
                  "only (no administrator).",
        "progress": "Each app is downloaded, then its own installer runs silently, with its Explorer menu and "
                    "Open with as usual.",
        "manage": "Open, update or remove each app. PR7-U checks for new versions once a day.",
    }[mode], "dim"))
    v.addLayout(top)
    for i, a in enumerate(APPS):
        v.addWidget(row(a, mode, states[i] if states else None, i % 2 == 1))
    v.addStretch(1)
    foot = QHBoxLayout(); foot.setContentsMargins(22, 14, 22, 18); foot.setSpacing(10)
    if mode == "choose":
        foot.addWidget(label("8 apps  ·  357 MB to download", size=13))
        foot.addStretch(1)
        foot.addWidget(QPushButton("SELECT ALL")); foot.addWidget(QPushButton("NONE"))
        go = QPushButton("INSTALL 8 APPS"); go.setStyleSheet(PRIMARY); foot.addWidget(go)
    elif mode == "progress":
        col = QVBoxLayout(); col.setSpacing(6)
        col.addWidget(label("3 of 8 done  ·  151 of 357 MB", size=13))
        bar = QProgressBar(); bar.setTextVisible(False); bar.setValue(42); bar.setFixedHeight(8)
        col.addWidget(bar)
        foot.addLayout(col, 1)
        foot.addSpacing(20)
        foot.addWidget(QPushButton("CANCEL"))
    else:
        foot.addWidget(label("1 update  ·  2 apps not installed", size=13))
        foot.addStretch(1)
        foot.addWidget(QPushButton("CHECK NOW"))
        go = QPushButton("UPDATE ALL"); go.setStyleSheet(PRIMARY); foot.addWidget(go)
    v.addLayout(foot)
    win.show(); app.processEvents()
    return win


def shoot(win, name):
    pm = win.grab()
    pm.save(str(out / name))
    print(out / name)
    win.close()


shoot(window("choose"), "1_choose.png")
STATES = [("done", 1, "UPDATED TO 0.4.0"), ("done", 1, "UPDATED TO 0.3.0"), ("done", 1, "INSTALLED 0.7.0"),
          ("install", 1, "INSTALLING..."), ("skip", 0, "UP TO DATE"), ("down", .46, "17.5 OF 38.0 MB"),
          ("wait", 0, "WAITING"), ("wait", 0, "WAITING"), ("wait", 0, "WAITING")]
shoot(window("progress", STATES), "2_installing.png")
theme.set_finish("aurora")
shoot(window("manage"), "3_manage_aurora.png")
