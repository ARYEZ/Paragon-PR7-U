import json

from pr7u import app, family, theme
from pr7u.main_window import RowWidget


def visible(w, key):
    return not w.buttons[key].isHidden()


def test_first_start_offers_the_whole_family(window, fam):
    window.refresh()
    assert window.mode == "choose" and window.heading.text() == "INSTALL THE FAMILY"
    from conftest import LETTERS, VERSIONS
    assert window.chosen() == LETTERS
    total = sum(len(fam.files[f"/PR7-{x}-Setup-{v}.exe"]) for x, v in zip(LETTERS, VERSIONS))
    assert window.summary.text() == f"17 apps  ·  {total / 1e6:.1f} MB to download"
    assert window.buttons["go"].text() == "INSTALL 17 APPS"
    window.widgets["M"].check.setChecked(False)
    assert window.buttons["go"].text() == "INSTALL 16 APPS" and "M" not in window.chosen()
    window._button_none()
    assert not window.buttons["go"].isEnabled() and window.summary.text() == "Nothing ticked"
    window._button_all()
    assert len(window.chosen()) == 17


def test_install_the_chosen_ones(window, fam):
    fam.install("PR7-E", "1.1.0")
    fam.release("PR7-Q", None)
    window.start = "choose"
    window.refresh()
    assert window.mode == "choose"
    assert not window.widgets["E"].check.isChecked() and not window.widgets["Q"].check.isEnabled()
    for k in ["L", "F", "R", "P", "M", "DU", "CB", "IS", "PM", "SM", "HB", "FS", "AR"]:
        window.widgets[k].check.setChecked(False)
    window._button_go()                                   # Z and W
    assert [a[0].rsplit("/", 1)[-1].rsplit("\\", 1)[-1] for a in fam.ran] == ["PR7-Z-Setup-0.4.0.exe",
                                                                              "PR7-W-Setup-0.3.0.exe"]
    assert fam.registry[family.APPS["PR7-Z"]]["DisplayVersion"] == "0.4.0"
    assert window.mode == "progress" and not window.running
    w = window.widgets
    assert w["Z"].status.text() == "INSTALLED 0.4.0" and w["W"].status.text() == "INSTALLED 0.3.0"
    assert w["E"].status.text() == "UP TO DATE" and w["L"].status.text() == "NOT CHOSEN"
    assert window.summary.text() == "2 of 2 done" and window.buttons["go"].text() == "DONE"
    window._button_go()
    assert window.mode == "manage" and window.widgets["Z"].button.text() == "OPEN"


def test_one_failure_does_not_stop_the_others(window, fam):
    fam.failing.add("PR7-W")
    window.refresh()
    window.run_job([("Z", "install"), ("W", "install"), ("L", "install")])
    w = window.widgets
    assert w["W"].status.text() == "FAILED" and "code 5" in w["W"].toolTip()
    assert w["Z"].status.text() == "INSTALLED 0.4.0" and w["L"].status.text() == "INSTALLED 0.7.0"
    assert "1 failed" in window.summary.text()


def test_cancel_stops_the_rest(window, fam):
    window.refresh()

    def runner(args):
        window._button_cancel()                         # pressed while the first one installs
        return fam.runner(args)
    window.runner = runner
    window.run_job([("Z", "install"), ("W", "install")])
    assert window.widgets["Z"].status.text() == "INSTALLED 0.4.0"
    assert window.widgets["W"].status.text() == "CANCELLED" and len(fam.ran) == 1


def test_manage_view_open_update_uninstall(window, fam):
    fam.install("PR7-Z", "0.3.0")
    fam.install("PR7-E", "1.1.0")
    window.refresh()
    assert window.mode == "manage" and window.heading.text() == "YOUR PARAGON APPS"
    w = window.widgets
    assert (w["Z"].button.text(), w["E"].button.text(), w["W"].button.text()) == ("UPDATE", "OPEN", "INSTALL")
    assert window.summary.text() == "1 update  ·  15 apps not installed"
    assert visible(window, "go") and window.buttons["go"].text() == "UPDATE AND INSTALL ALL"
    assert visible(window, "updates") and window.buttons["updates"].text() == "UPDATE ONLY"
    opened = []
    window.answers["launch"] = lambda name, args: opened.append(name) or True
    w["E"].button.click()
    assert opened == ["PR7-E"]
    window._button_updates()                             # UPDATE ONLY: only the installed ones that are behind
    assert len(fam.ran) == 1 and fam.registry[family.APPS["PR7-Z"]]["DisplayVersion"] == "0.4.0"
    window._button_go()                                  # DONE
    window.answers["menu"] = True
    m = window.row_menu("E")
    assert [a.text() for a in m.actions() if a.text()] == ["Release notes...", "PR7-E on GitHub",
                                                           "Uninstall PR7-E..."]
    window.answers["uninstall"] = False
    assert not window.ask_uninstall("E") and family.APPS["PR7-E"] in fam.registry
    window.answers["uninstall"] = True
    assert window.ask_uninstall("E")
    assert family.APPS["PR7-E"] not in fam.registry and window.widgets["E"].status.text() == "UNINSTALLED"
    window.release_notes("Z")
    assert window.said[-1] == ("info", "PR7-Z 0.4.0\n\n## 0.4.0\n- Better PR7-Z.")


def test_offline_still_shows_whats_installed(window, fam):
    fam.install("PR7-Z", "0.4.0")
    from conftest import LETTERS
    fam.broken.update(f"PR7-{x}" for x in LETTERS)
    window.refresh()
    assert window.mode == "manage" and window.widgets["Z"].button.text() == "OPEN"
    assert "GitHub couldn’t be reached" in window.summary.text() and window.widgets["W"].button is None


def test_finish_switch(window, fam):
    window.refresh()
    window.set_finish("aurora")
    assert theme.FINISH == "aurora" and window.header is not None
    row = window.widgets["Z"]
    assert isinstance(row, RowWidget) and theme.BACKGROUND in window.styleSheet()
    window.set_finish("obsidian")


# ---------------------------------------------------------------- the command line
def test_version(capsys):
    from pr7u import __version__
    assert app.main(["--version"]) == 0 and capsys.readouterr().out.strip() == __version__


def test_listing(fam, tmp_path):
    fam.install("PR7-Z", "0.3.0")
    out = tmp_path / "l.json"
    assert app.listing(str(out), fam.fetch, fam.reader) == 0
    got = {d["app"]: d for d in json.loads(out.read_text())}
    assert got["PR7-Z"]["state"] == "update" and got["PR7-Z"]["installed"] == "0.3.0" and got["PR7-Z"]["latest"] == "0.4.0"
    assert len(got) == 17 and got["PR7-W"]["installed"] is None


def test_install_and_uninstall_without_a_window(fam):
    lines = []
    fam.release("PR7-M", None)
    fam.install("PR7-E", "1.1.0")
    assert app.headless("install", "all", fam.fetch, None, fam.runner, fam.reader, lines.append) == 0
    assert "PR7-M: no release yet" in lines and "PR7-E: up to date (1.1.0)" in lines and "PR7-Z: installed 0.4.0" in lines
    assert len(fam.registry) == 16
    lines.clear()
    fam.failing.add("PR7-Q"); fam.release("PR7-Q", "0.2.0")
    assert app.headless("install", "Q", fam.fetch, None, fam.runner, fam.reader, lines.append) == 1
    assert lines[0].startswith("PR7-Q: FAILED")
    lines.clear()
    assert app.headless("uninstall", "all", fam.fetch, None, fam.runner, fam.reader, lines.append) == 0
    assert not fam.registry and "PR7-M: not installed" in lines
    assert app.headless("install", "Z,Y", say=lines.append) == 2


def test_install_and_update_everything_from_your_apps(window, fam):
    fam.install("PR7-Z", "0.3.0")                        # behind
    fam.install("PR7-E", "1.1.0")                        # current
    window.refresh()
    assert window.buttons["go"].text() == "UPDATE AND INSTALL ALL"
    window._button_go()
    ran = [a[0].rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for a in fam.ran]
    assert ran[0] == "PR7-Z-Setup-0.4.0.exe"                                   # the update first
    assert len(ran) == 16 and not any(r.startswith("PR7-E-") for r in ran)    # then every missing app; E left alone
    w_args = next(a for a in fam.ran if "PR7-W-Setup" in a[0])
    assert "/MERGETASKS=!replacenotepad" in w_args                              # first installs keep their switches
    assert all(fam.registry[family.APPS[f"PR7-{k}"]]["DisplayVersion"] for k in ("Z", "W", "SM"))
    window._button_go()                                                         # DONE
    assert window.buttons["go"].text() == "UPDATE ALL" and not window.buttons["go"].isEnabled()
    assert not visible(window, "updates") and window.summary.text() == "Everything is up to date"


def test_install_all_when_nothing_needs_updating(window, fam):
    fam.install("PR7-E", "1.1.0")
    window.start = "done"
    window.refresh()
    assert window.mode == "manage" and window.buttons["go"].text() == "INSTALL ALL" and not visible(window, "updates")
