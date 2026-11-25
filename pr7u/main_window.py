"""PR7-U's window: the nine family apps in one list, shown three ways.

    choose    first start (or nothing installed yet): tick the apps, INSTALL N APPS
    progress  each chosen app downloaded and installed in turn, with its own bar and an overall one
    manage    every app with OPEN / UPDATE / INSTALL and a menu (release notes, uninstall); UPDATE ALL

GitHub is asked on a worker thread (`releases.survey`), and installs run one after another on another; their news
comes back to the window through queued signals. Tests set `sync = True` (everything inline) and `answers`."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from . import finish
from . import __version__, catalog, family, releases, settings, theme, widgets
from .releases import Row
from .updates import UpdateError

PRIMARY = "primary"     # the family gradient button (style sheet below)


def mb(n: int) -> str:
    return f"{n / 1e6:.1f} MB"


def stylesheet() -> str:
    return theme.stylesheet() + f"""
QPushButton[kind="primary"] {{ background: {theme.qss_gradient()}; color: #FFFFFF; border: none; font-weight: 600;
    padding: 8px 22px; }}
QPushButton[kind="primary"]:disabled {{ background: {theme.WIDGET}; color: {theme.TEXT_DIM}; }}
QFrame#row {{ background: {theme.BACKGROUND}; }}
QFrame#row[alt="true"] {{ background: {theme.ALT_ROW}; }}
QScrollArea, QWidget#rows {{ background: {theme.BACKGROUND}; border: none; }}
"""


def _label(text: str = "", role: str | None = None, size: int | None = None, bold: bool = False) -> QLabel:
    w = QLabel(text)
    if role:
        w.setProperty("role", role)
    f = w.font()
    if size:
        f.setPixelSize(size)
    if bold:
        f.setWeight(QFont.Weight.DemiBold)
    w.setFont(f)
    return w


class Pill(QLabel):
    """NEW / UPDATE / UP TO DATE ... as a small outlined tag; lit ones in the family's orange."""

    def __init__(self, text: str, lit: bool = False):
        super().__init__(text)
        f = self.font(); f.setPixelSize(10); f.setWeight(QFont.Weight.DemiBold); self.setFont(f)
        colour = theme.LED_ORANGE if lit else theme.TEXT_DIM
        self.setStyleSheet(f"color: {colour}; border: 1px solid {colour}; border-radius: 9px; padding: 2px 8px;")
        self.setFixedHeight(20)


PILLS = {"new": ("NEW", True), "update": ("UPDATE", True), "current": ("UP TO DATE", False),
         "unreleased": ("NO RELEASE YET", False), "error": ("GITHUB UNREACHABLE", False)}


class RowWidget(QFrame):
    """One app: its icon, name, what it is; the rest depends on the window's mode."""

    def __init__(self, win: "MainWindow", row: Row, mode: str, alt: bool):
        super().__init__()
        self.win, self.row = win, row
        self.setObjectName("row")
        self.setProperty("alt", alt)
        self.setFixedHeight(64)
        h = QHBoxLayout(self); h.setContentsMargins(18, 0, 22, 0); h.setSpacing(14)
        self.check = QCheckBox()
        self.check.setChecked(row.wanted)
        self.check.setEnabled(row.state in ("new", "update", "current") and row.release is not None)
        self.check.toggled.connect(win._chosen_changed)
        self.check.setVisible(mode == "choose")
        h.addWidget(self.check)
        icon = QLabel()
        pm = QPixmap(row.app.icon).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(2)
        icon.setPixmap(pm)
        h.addWidget(icon)
        names = QVBoxLayout(); names.setSpacing(2)
        names.addStretch(1)
        names.addWidget(_label(row.app.name, size=15, bold=True))
        names.addWidget(_label(f"{row.app.what}  ·  works like {row.app.like}", "dim", 12))
        names.addStretch(1)
        h.addLayout(names, 1)
        self.status = _label("", "dim", 11)
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.bar = QProgressBar(); self.bar.setTextVisible(False); self.bar.setFixedSize(260, 8); self.bar.hide()
        self.button = None
        if mode == "choose":
            self._choose(h)
        elif mode == "progress":
            box = QVBoxLayout(); box.setSpacing(6)
            box.addStretch(1); box.addWidget(self.status); box.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignRight)
            box.addStretch(1)
            h.addLayout(box)
        else:
            self._manage(h)
        if row.error:
            self.setToolTip(row.error)

    def _choose(self, h):
        r = self.row
        text, lit = PILLS[r.state]
        h.addWidget(Pill(text, lit))
        have = r.installed.version if r.installed else ""
        new = r.release.version if r.release else ""
        ver = _label(f"{have}  →  {new}" if r.state == "update" else (new or have), size=12)
        ver.setFixedWidth(110); ver.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(ver)
        size = _label(mb(r.release.size) if r.wanted and r.release.size else "", "dim", 12)
        size.setFixedWidth(70); size.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(size)

    def _manage(self, h):
        r = self.row
        if r.state == "update":
            pill, button = Pill(f"UPDATE {r.release.version}", True), "UPDATE"
        elif r.installed:
            pill, button = Pill(f"INSTALLED {r.installed.version}"), "OPEN"
        elif r.state == "new":
            pill, button = Pill("NOT INSTALLED"), "INSTALL"
        else:
            pill, button = Pill(PILLS[r.state][0]), None
        h.addWidget(pill)
        if button:
            self.button = QPushButton(button)
            self.button.setFixedWidth(96)
            if button != "OPEN":
                self.button.setProperty("kind", PRIMARY)
            self.button.clicked.connect(lambda: self.win.row_action(r.app.letter))
            h.addWidget(self.button)
        else:
            spacer = QWidget(); spacer.setFixedWidth(96); h.addWidget(spacer)
        more = widgets.SmallKey("more", f"More for {r.app.name}")
        more.clicked.connect(lambda: self.win.row_menu(r.app.letter, more))
        h.addWidget(more)
        self.more = more

    def show_progress(self, kind: str, text: str, frac: float | None = None):
        self.status.setText(text)
        self.status.setProperty("role", "ok" if kind == "done" else "error" if kind == "failed" else "dim")
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        if kind in ("download", "install", "uninstall"):
            self.bar.show()
            if frac is None:
                self.bar.setRange(0, 0)       # busy: the installer doesn't say how far it is
            else:
                self.bar.setRange(0, 1000); self.bar.setValue(int(frac * 1000))
        else:
            self.bar.hide()


class _Bridge(QObject):
    """News from the worker threads, delivered on the GUI thread."""
    surveyed = Signal(object)
    stage = Signal(str, str, object, object)      # letter, stage, done, total
    one_done = Signal(str, str, str)              # letter, "done" | "failed" | "cancelled", text
    job_done = Signal()


class MainWindow(QMainWindow):
    def __init__(self, fetch=None, opener=None, runner=None, reader=None, start: str = "auto"):
        super().__init__()
        self.fetch, self.opener, self.runner, self.reader = fetch, opener, runner, reader
        self.answers: dict = {}
        self.sync = False
        self.start = start               # "choose" (the installer's finish page), "manage" or "auto"
        self.rows: list[Row] = []
        self.widgets: dict[str, RowWidget] = {}
        self.mode = "manage"
        self.job: list[tuple[str, str]] = []      # (letter, "install" | "uninstall") left to do
        self.job_bytes = (0, 0)
        self.results: dict[str, str] = {}
        self._cancel = threading.Event()
        self.running = False
        self.bridge = _Bridge()
        self.bridge.surveyed.connect(self._surveyed)
        self.bridge.stage.connect(self._stage)
        self.bridge.one_done.connect(self._one_done)
        self.bridge.job_done.connect(self._job_done)
        self.setWindowTitle("Paragon PR7-U")
        self.resize(980, 860)
        self.setMinimumSize(760, 560)
        self._build()
        self.restyle()

    # ---------------------------------------------------------------- the frame
    def _build(self):
        body = QWidget(); self.setCentralWidget(body)
        v = QVBoxLayout(body); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.header = widgets.Header()
        v.addWidget(self.header)
        top = QHBoxLayout(); top.setContentsMargins(22, 18, 22, 12)
        texts = QVBoxLayout(); texts.setSpacing(4)
        self.heading = _label("", "heading")
        self.blurb = _label("", "dim"); self.blurb.setWordWrap(True)
        texts.addWidget(self.heading); texts.addWidget(self.blurb)
        top.addLayout(texts, 1)
        self.menu_key = widgets.SmallKey("more", "PR7-U")
        self.menu_key.clicked.connect(self.main_menu)
        top.addWidget(self.menu_key, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(top)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        v.addWidget(self.scroll, 1)
        foot = QHBoxLayout(); foot.setContentsMargins(22, 14, 22, 18); foot.setSpacing(10)
        col = QVBoxLayout(); col.setSpacing(6)
        self.summary = _label("", size=13)
        self.total_bar = QProgressBar(); self.total_bar.setTextVisible(False); self.total_bar.setFixedHeight(8)
        self.total_bar.setRange(0, 1000); self.total_bar.hide()
        col.addWidget(self.summary); col.addWidget(self.total_bar)
        foot.addLayout(col, 1)
        foot.addSpacing(20)
        self.buttons = {}
        for key, text in (("all", "SELECT ALL"), ("none", "NONE"), ("check", "CHECK NOW"), ("cancel", "CANCEL"),
                          ("updates", "UPDATE ONLY"), ("go", "INSTALL")):
            b = QPushButton(text)
            if key == "go":
                b.setProperty("kind", PRIMARY)
            b.clicked.connect(getattr(self, f"_button_{key}"))
            foot.addWidget(b)
            self.buttons[key] = b
        v.addLayout(foot)

    def restyle(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        app.setPalette(theme.palette())
        self.setStyleSheet(stylesheet())
        self.header.update()
        if self.rows:
            self._show(self.mode)

    # ---------------------------------------------------------------- asking GitHub
    def refresh(self):
        """Read what's installed (at once) and ask GitHub for every app's newest release (in the background)."""
        self.summary.setText("Asking GitHub for the newest versions...")
        if not self.rows:
            self.rows = releases.survey(fetch=self.fetch, reader=self.reader, online=False)
            self._show("manage")
            self.summary.setText("Asking GitHub for the newest versions...")
        self.buttons["check"].setEnabled(False)
        self._background(lambda: releases.survey(fetch=self.fetch, reader=self.reader), self.bridge.surveyed.emit)

    def _background(self, fn, then):
        if self.sync:
            then(fn())
            return
        threading.Thread(target=lambda: then(fn()), daemon=True).start()

    def _surveyed(self, rows: list[Row]):
        self.rows = rows
        self.buttons["check"].setEnabled(True)
        if self.running:
            return
        nothing = not any(r.installed for r in rows)
        if self.start == "choose" or (self.start == "auto" and nothing):
            self.start = "done"
            self._show("choose")
        else:
            self.start = "done"
            self._show("manage")

    def row(self, letter: str) -> Row:
        return next(r for r in self.rows if r.app.letter == letter)

    # ---------------------------------------------------------------- the three views
    def _show(self, mode: str):
        self.mode = mode
        # The old rows: taken out and deleted later, never by setWidget (that deletes them in C++ at once, while their
        # Python wrappers live on in signal cycles; the garbage collector then crashed freeing them: a segfault on
        # CI and here once the family had 13 apps).
        old = self.scroll.takeWidget()
        self.widgets = {}
        if old is not None:
            old.hide()
            old.deleteLater()
        holder = QWidget(); holder.setObjectName("rows")
        v = QVBoxLayout(holder); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.widgets = {}
        for i, r in enumerate(self.rows):
            w = RowWidget(self, r, mode, i % 2 == 1)
            self.widgets[r.app.letter] = w
            v.addWidget(w)
        v.addStretch(1)
        self.scroll.setWidget(holder)
        b = self.buttons
        for key in b:
            b[key].setVisible(False)
        self.total_bar.setVisible(mode == "progress")
        if mode == "choose":
            self.heading.setText("INSTALL THE FAMILY")
            self.blurb.setText("Tick the apps you want. Each comes from its latest release on GitHub and installs "
                               "for you only (no administrator).")
            for key in ("all", "none", "go"):
                b[key].setVisible(True)
            self._chosen_changed()
        elif mode == "progress":
            self.heading.setText("INSTALLING" if any(a == "install" for _, a in self.job) else "REMOVING")
            self.blurb.setText("Each app is downloaded, then its own installer runs silently, with its Explorer menu "
                               "and Open with as usual.")
            b["cancel"].setVisible(True); b["cancel"].setText("CANCEL"); b["cancel"].setEnabled(True)
        else:
            self.heading.setText("YOUR PARAGON APPS")
            self.blurb.setText("Open, update or remove each app. PR7-U checks for new versions once a day.")
            b["check"].setVisible(True)
            b["go"].setVisible(True)
            # One button for what's waiting: updates, the apps not installed yet, or both (then UPDATE ONLY too, to
            # bring your apps up to date without adding the rest of the family).
            ups, missing = self.waiting()
            b["go"].setText("UPDATE AND INSTALL ALL" if ups and missing else "INSTALL ALL" if missing else "UPDATE ALL")
            b["go"].setEnabled(bool(ups or missing))
            b["updates"].setVisible(bool(ups and missing))
            self.summary.setText(self.manage_summary())

    def waiting(self) -> tuple[list[str], list[str]]:
        """(installed apps with a newer release, released apps not installed yet), as letters in family order."""
        ups = [r.app.letter for r in self.rows if r.state == "update"]
        missing = [r.app.letter for r in self.rows if r.state == "new"]
        return ups, missing

    def manage_summary(self) -> str:
        ups = sum(r.state == "update" for r in self.rows)
        missing = sum(r.state == "new" for r in self.rows)
        errors = sum(r.state == "error" for r in self.rows)
        parts = []
        if ups:
            parts.append(f"{ups} update" + ("s" if ups > 1 else ""))
        if missing:
            parts.append(f"{missing} app{'s' if missing > 1 else ''} not installed")
        if errors:
            parts.append("GitHub couldn’t be reached")
        return "  ·  ".join(parts) or "Everything is up to date"

    def chosen(self) -> list[str]:
        return [k for k, w in self.widgets.items() if w.check.isChecked() and w.check.isEnabled()
                and w.row.state in ("new", "update")]

    def _chosen_changed(self, *_):
        if self.mode != "choose":
            return
        letters = self.chosen()
        size = sum(self.row(k).release.size for k in letters)
        n = len(letters)
        self.summary.setText(f"{n} app{'s' if n != 1 else ''}  ·  {mb(size)} to download" if n else
                             "Nothing ticked" if any(r.wanted for r in self.rows) else
                             "Everything is up to date")
        self.buttons["go"].setText(f"INSTALL {n} APP{'S' if n != 1 else ''}" if n else "INSTALL")
        self.buttons["go"].setEnabled(bool(n))

    def _button_all(self):
        for w in self.widgets.values():
            if w.check.isEnabled():
                w.check.setChecked(True)

    def _button_none(self):
        for w in self.widgets.values():
            w.check.setChecked(False)

    def _button_check(self):
        self.refresh()

    def _button_go(self):
        if self.mode == "choose":
            self.run_job([(k, "install") for k in self.chosen()])
        elif self.mode == "manage":                # updates first, then the new apps (each with its first-install switches)
            ups, missing = self.waiting()
            self.run_job([(k, "install") for k in ups + missing])
        else:                                  # progress finished: DONE
            self._show("manage")

    def _button_updates(self):
        """UPDATE ONLY: the installed apps that are behind, nothing new added."""
        self.run_job([(k, "install") for k in self.waiting()[0]])

    def _button_cancel(self):
        self._cancel.set()
        self.buttons["cancel"].setEnabled(False)
        self.summary.setText("Stopping after this step...")

    # ---------------------------------------------------------------- one app's buttons and menu
    def row_action(self, letter: str):
        r = self.row(letter)
        if r.state in ("update", "new"):
            self.run_job([(letter, "install")])
        elif r.installed:
            self.open_app(r)

    def open_app(self, r: Row):
        launch = self.answers.get("launch", family.launch)
        if not launch(r.app.name, []):
            self._say("warning", f"{r.app.name} couldn’t be started. Try updating it.")

    def row_menu(self, letter: str, anchor=None):
        r = self.row(letter)
        m = QMenu(self)
        notes = m.addAction("Release notes...")
        notes.setEnabled(r.release is not None)
        notes.triggered.connect(lambda: self.release_notes(letter))
        page = m.addAction(f"{r.app.name} on GitHub")
        page.triggered.connect(lambda: self._open_url(f"https://github.com/{r.app.repo}"))
        m.addSeparator()
        rm = m.addAction(f"Uninstall {r.app.name}...")
        rm.setEnabled(r.installed is not None and not self.running)
        rm.triggered.connect(lambda: self.ask_uninstall(letter))
        self.last_menu = m
        if "menu" in self.answers:
            return m
        m.exec((anchor or self).mapToGlobal((anchor or self).rect().bottomLeft()))
        return m

    def release_notes(self, letter: str):
        r = self.row(letter)
        if r.release is None:
            return
        self._say("info", f"{r.app.name} {r.release.version}\n\n{r.release.notes or 'No notes.'}")

    def ask_uninstall(self, letter: str) -> bool:
        r = self.row(letter)
        if not self._ask("uninstall", f"Uninstall {r.app.name}? Its settings stay, so installing it again "
                                      "picks up where you were."):
            return False
        self.run_job([(letter, "uninstall")])
        return True

    def main_menu(self):
        m = QMenu(self)
        for name in ("obsidian", "aurora"):
            a = m.addAction(name.upper())
            a.setCheckable(True); a.setChecked(theme.FINISH == name)
            a.triggered.connect(lambda _=False, n=name: self.set_finish(n))
        m.addSeparator()
        m.addAction("Check PR7-U for updates...").triggered.connect(self.check_self)
        m.addAction("About PR7-U").triggered.connect(
            lambda: self._say("info", f"Paragon PR7-U {__version__}\nInstalls and updates the Paragon PR7 family."))
        if "menu" in self.answers:
            return m
        m.exec(self.menu_key.mapToGlobal(self.menu_key.rect().bottomLeft()))
        return m

    def set_finish(self, name: str):
        theme.set_finish(name)
        finish.set(theme.FINISH)                 # every family app follows (finish.py)
        settings.set("finish", name)
        self.restyle()

    def check_self(self):
        from . import update_ui
        update_ui.check(self, manual=True)

    # ---------------------------------------------------------------- installing and removing
    def run_job(self, steps: list[tuple[str, str]]):
        """Install / update / uninstall the apps in `steps`, one after another."""
        steps = [s for s in steps if s[0] in {r.app.letter for r in self.rows}]
        if not steps or self.running:
            return
        self.job = list(steps)
        self.results = {}
        self._cancel.clear()
        self.running = True
        self.job_bytes = (0, sum(self.row(k).release.size for k, act in steps
                                 if act == "install" and self.row(k).release))
        self._show("progress")
        doing = {k for k, _ in steps}
        for k, w in self.widgets.items():
            r = w.row
            if k in doing:
                w.show_progress("wait", "WAITING")
            else:
                w.show_progress("skip", "UP TO DATE" if r.state == "current" else "NOT CHOSEN")
        self._progress_summary()
        self._background(self._work, lambda _: self.bridge.job_done.emit())

    def _work(self):
        for letter, action in list(self.job):
            if self._cancel.is_set():
                self.bridge.one_done.emit(letter, "cancelled", "CANCELLED")
                continue
            r = self.row(letter)
            try:
                if action == "install":
                    before = r.installed.version if r.installed else ""
                    releases.install(r, lambda stage, done, total, k=letter: self.bridge.stage.emit(
                        k, stage, done, total), self._cancel.is_set, opener=self.opener, runner=self.runner,
                        reader=self.reader)
                    text = (f"UPDATED TO {r.installed.version}" if before else f"INSTALLED {r.installed.version}")
                else:
                    self.bridge.stage.emit(letter, "uninstall", 0, 0)
                    releases.uninstall(r, runner=self.runner, reader=self.reader,
                                       **({"wait": 0} if self.sync else {}))
                    text = "UNINSTALLED"
                self.bridge.one_done.emit(letter, "done", text)
            except releases.Cancelled:
                self.bridge.one_done.emit(letter, "cancelled", "CANCELLED")
            except (UpdateError, OSError, ValueError) as e:
                self.bridge.one_done.emit(letter, "failed", str(e))
        return None

    def _stage(self, letter: str, stage: str, done, total):
        w = self.widgets.get(letter)
        if w is None:
            return
        if stage == "download":
            w.show_progress("download", f"{mb(done)} OF {mb(total)}" if total else mb(done),
                            done / total if total else None)
            self._current = (letter, done)
        elif stage == "install":
            w.show_progress("install", "INSTALLING...")
        else:
            w.show_progress("uninstall", "UNINSTALLING...")
        self._progress_summary()

    def _one_done(self, letter: str, how: str, text: str):
        self.results[letter] = how
        w = self.widgets.get(letter)
        if w is not None:
            if how == "failed":
                w.show_progress("failed", "FAILED")
                w.status.setToolTip(text)
                w.setToolTip(text)
            else:
                w.show_progress("done" if how == "done" else "skip", text)
        self._current = None
        self._progress_summary()

    def _progress_summary(self):
        n = len(self.job)
        done = len(self.results)
        got = sum(self.row(k).release.size for k, a in self.job
                  if a == "install" and k in self.results and self.row(k).release)
        cur = getattr(self, "_current", None)
        if cur and cur[0] not in self.results:
            got += cur[1]
        total = self.job_bytes[1]
        text = f"{done} of {n} done"
        if total:
            text += f"  ·  {got / 1e6:.0f} of {total / 1e6:.0f} MB"
        if self.running:
            self.summary.setText(text)
        frac = (got / total) if total else (done / n if n else 1)
        self.total_bar.setValue(int(min(1.0, frac) * 1000))

    def _job_done(self):
        self.running = False
        failed = [k for k, how in self.results.items() if how == "failed"]
        n = len(self.job)
        ok = sum(how == "done" for how in self.results.values())
        self.summary.setText(f"{ok} of {n} done" + (f"  ·  {len(failed)} failed (point at FAILED to see why)"
                                                   if failed else ""))
        self.total_bar.setValue(1000)
        self.buttons["cancel"].setVisible(False)
        self.buttons["go"].setVisible(True)
        self.buttons["go"].setEnabled(True)
        self.buttons["go"].setText("DONE")

    # ---------------------------------------------------------------- questions
    def _ask(self, kind: str, text: str) -> bool:
        if kind in self.answers:
            a = self.answers[kind]
            return a(text) if callable(a) else a
        return QMessageBox.question(self, "Paragon PR7-U", text) == QMessageBox.StandardButton.Yes

    def _say(self, kind: str, text: str):
        if "say" in self.answers:
            self.answers["say"](kind, text)
            return
        (QMessageBox.warning if kind == "warning" else QMessageBox.information)(self, "Paragon PR7-U", text)

    def _open_url(self, url: str):
        if "url" in self.answers:
            self.answers["url"](url)
            return
        QDesktopServices.openUrl(QUrl(url))

    def closeEvent(self, e):
        if self.running and not self._ask("close_running", "Apps are still being installed. Stop after the one "
                                                           "that's running now and close?"):
            e.ignore()
            return
        self._cancel.set()
        e.accept()
