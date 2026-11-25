# Paragon PR7-U: notes for Claude

**Paragon PR7-U** is the owner's family installer: Python (**PySide6**) that installs, updates and removes the Paragon
PR7 family (PR7-Z, W, L, F, E, R, P, M, Q `ARYEZ/Paragon-PR7-*`), each from its own latest GitHub release, in the
family look. Windows 10/11 x64 is the target; it runs on Linux for tests. The owner writes Python; explain the why.

## How it's built

- `pr7u/catalog.py` (no Qt): `APPS` (letter, what it is, works like; repo and AppId derived, AppIds from `family.py`),
  `pick("all"|"Z,W")`, `installed(app, reader)` from HKCU `Uninstall\{AppId}_is1` (DisplayVersion, InstallLocation,
  UninstallString), `uninstall_command` (unins000.exe /VERYSILENT ...). A new family app: add it to `family.APPS`, to
  `catalog.APPS`, copy its `icons/app.png` to `pr7u/icons/apps/<letter>.png`, and add its AppId to every app's family.py.
- `pr7u/releases.py` (no Qt): `latest(app, fetch)` (GitHub's releases/latest of the app's repo; 404 = no release; the
  asset `PR7-X-Setup-*.exe`), `Row.state` new / update / current / unreleased / error, `survey` (all apps at once),
  `install` (updates.download to a temp folder, then the setup with /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
  /CLOSEAPPLICATIONS plus the app's `first_args` on a first install, then the version re-read), `uninstall` (waits for
  the entry to go: Inno's uninstaller returns before it's done). `PR7U_GITHUB_TOKEN` is for CI only (rate limit).
- PR7-W's "Replace Windows Notepad" task is ticked by default and needs UAC: a first install passes
  `/MERGETASKS=!replacenotepad` (catalog `first_args`), so a batch never stops at a UAC prompt.
- `pr7u/main_window.py`: one list of `RowWidget`s rebuilt per mode (choose / progress / manage); survey and jobs on
  worker threads, news through `_Bridge` queued signals; `sync = True` runs them inline (tests); `answers` for every
  question (`_ask`, `_say`, launch, url, menu). `app.py`: one window per user (QLocalSocket hand-off, PR7-R's Windows
  fix), `--choose`, `--install/--uninstall SPEC`, `--list OUT.json`; `_stdout` gives the windowed exe a stdout.
- Installer `installer/pr7u.iss` (per user, AppId {12226380-56E6-4D77-8F5C-8052A0AE4183} permanent); the finish page runs
  `--choose`. CI installs it, `tools/verify_install.py installed` uses the installed PR7-U for real: --list, --install
  all (each app at its latest release), --uninstall all; then uninstalls PR7-U, `... uninstalled`.
- Updates (PR7-U itself): `pr7u/updates.py` / `update_ui.py`, the family's files (keep them in step); PR7-U's own update_ui never offers itself; `family.py`.

## The look (family rules)

- Theme is PR7-Q's (OBSIDIAN + AURORA via `theme.set_finish`; the window's `stylesheet()` adds the gradient button
  `kind="primary"` and rows). Colours: the family's only; Inter; labels UPPER CASE.
- The PR7-U mark: PR7 `Logo.cpp` geometry plus a U (`widgets.U_SHAPE`); icon by `tools/make_icon.py`, wizard art by
  `tools/make_installer_art.py`. Check visuals with `QT_SCALE_FACTOR=2 python tools/screenshots.py OUT`.

## Rules

- Tests: `python -m pytest` (offscreen) against a stand-in family (`conftest.Family`: GitHub's JSON, setups on a local
  web server, uninstall entries, installers that write them). Never the real settings, registry or network.
- Releases: bump `__version__` in `pr7u/__init__.py`, add a `## x.y.z` section to CHANGELOG.md; Run workflow with
  "Publish a release" (or a `v*` tag) publishes.
