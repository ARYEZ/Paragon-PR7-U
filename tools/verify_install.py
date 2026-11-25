"""Check a real install of PR7-U-Setup.exe (CI, Windows): python tools/verify_install.py installed|uninstalled

`installed` checks PR7-U's own files and entries, then uses the installed PR7-U.exe for real against GitHub:
--list (every app's newest release), --install all (each app's own installer, silently), and checks that every
app with a release is installed at that version, with its program where Windows says; then --uninstall all and
checks they're gone. Apps with no release yet are reported, not failed. `uninstalled` checks PR7-U is gone."""
import json
import os
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

HKCU = winreg.HKEY_CURRENT_USER
APP = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "PR7-U"
SHORTCUT = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Paragon PR7-U.lnk"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{}_is1"
OWN_ID = "{12226380-56E6-4D77-8F5C-8052A0AE4183}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pr7u import catalog, family  # noqa: E402


def value(path, name=""):
    try:
        with winreg.OpenKey(HKCU, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def check(ok, what, p):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        p.append(what)


def pr7u(*args, timeout=1800):
    r = subprocess.run([str(APP / "PR7-U.exe"), *args], capture_output=True, text=True, timeout=timeout,
                       check=False)
    print(r.stdout.strip())
    if r.stderr.strip():
        print(r.stderr.strip())
    return r.returncode


def installed():
    p = []
    exe = APP / "PR7-U.exe"
    for f in (exe, APP / "unins000.exe", APP / "_internal" / "pr7u" / "fonts" / "Inter-Regular.ttf",
              APP / "_internal" / "pr7u" / "icons" / "apps" / "q.png"):
        check(f.is_file(), f"file {f}", p)
    check(SHORTCUT.is_file(), "Start menu shortcut", p)
    check(value(UNINSTALL.format(OWN_ID), "DisplayName") == "Paragon PR7-U", "Installed apps entry", p)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "list.json"
        code = pr7u("--list", str(out), timeout=120)
        rows = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
        check(code == 0 and len(rows) == len(catalog.APPS), f"--list read every app's release ({len(rows)} of {len(catalog.APPS)})", p)
    released = {r["app"]: r["latest"] for r in rows if r.get("latest")}
    for r in rows:
        if not r.get("latest"):
            print(f"note  {r['app']} has no release yet")
    check(pr7u("--install", "all") == 0, "--install all", p)
    for name, version in released.items():
        key = UNINSTALL.format(family.APPS[name])
        have = value(key, "DisplayVersion")
        where = value(key, "InstallLocation") or ""
        check(have == version, f"{name} installed at {version} ({have})", p)
        check((Path(where) / f"{name}.exe").is_file(), f"{name}.exe in {where}", p)
    check(pr7u("--install", "all") == 0, "--install all again (everything up to date: nothing to do)", p)
    check(pr7u("--uninstall", "all") == 0, "--uninstall all", p)
    for name in released:
        check(value(UNINSTALL.format(family.APPS[name]), "DisplayName") is None, f"{name} uninstalled", p)
    return p


def uninstalled():
    deadline = time.time() + 60
    while True:
        p = []
        check(not (APP / "PR7-U.exe").exists(), "program files removed", p)
        check(not SHORTCUT.exists(), "Start menu shortcut removed", p)
        check(value(UNINSTALL.format(OWN_ID), "DisplayName") is None, "Installed apps entry removed", p)
        if not p or time.time() > deadline:
            return p
        print("... waiting for the uninstaller to finish")
        time.sleep(3)


if __name__ == "__main__":
    problems = {"installed": installed, "uninstalled": uninstalled}[sys.argv[1]]()
    print("\nALL OK" if not problems else f"\n{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
