from pathlib import Path

import pytest

from pr7u import catalog, family, releases
from pr7u.updates import UpdateError


def test_the_catalog_is_the_whole_family():
    from conftest import LETTERS
    assert [a.name for a in catalog.APPS] == [f"PR7-{x}" for x in LETTERS]
    assert len({a.appid for a in catalog.APPS}) == 11 and family.APPS["PR7-U"] not in {a.appid for a in catalog.APPS}
    for a in catalog.APPS:
        assert Path(a.icon).is_file() and a.repo == f"ARYEZ/Paragon-{a.name}"
    assert [a.letter for a in catalog.pick("q, PR7-z")] == ["Z", "Q"]       # catalogue order
    assert len(catalog.pick("all")) == 11 and [a.name for a in catalog.pick("du")] == ["PR7-DU"]
    with pytest.raises(ValueError):
        catalog.pick("Z,X")


def test_latest_release_reads_githubs_answer(fam):
    rel = releases.latest(catalog.BY_LETTER["Z"], fam.fetch)
    assert rel.version == "0.4.0" and rel.installer.endswith("/PR7-Z-Setup-0.4.0.exe")    # the setup, not the zip
    assert rel.size == len(fam.files["/PR7-Z-Setup-0.4.0.exe"]) and rel.notes == "## 0.4.0\n- Better PR7-Z."
    fam.release("PR7-Q", None)
    assert releases.latest(catalog.BY_LETTER["Q"], fam.fetch) is None          # 404: no release yet
    fam.broken.add("PR7-W")
    with pytest.raises(UpdateError):
        releases.latest(catalog.BY_LETTER["W"], fam.fetch)


def test_survey_states(fam):
    fam.install("PR7-Z", "0.3.0")       # older
    fam.install("PR7-E", "1.1.0")       # current
    fam.install("PR7-L", "0.8.0")       # newer than the release (a local build): not offered as an update
    fam.release("PR7-Q", None)
    fam.broken.add("PR7-F")
    rows = {r.app.letter: r for r in releases.survey(fetch=fam.fetch, reader=fam.reader)}
    assert {k: r.state for k, r in rows.items()} == {"Z": "update", "W": "new", "L": "current", "F": "error",
                                                       "E": "current", "R": "new", "P": "new", "M": "new",
                                                       "Q": "unreleased", "DU": "new", "CB": "new"}
    assert rows["Z"].wanted and not rows["E"].wanted and "network down" in rows["F"].error


def test_install_downloads_and_runs_the_apps_own_setup_silently(fam, tmp_path):
    seen = []
    row = releases.survey([catalog.BY_LETTER["W"]], fetch=fam.fetch, reader=fam.reader)[0]
    got = releases.install(row, lambda *a: seen.append(a), folder=str(tmp_path / "dl"), runner=fam.runner,
                           reader=fam.reader)
    assert got.version == "0.3.0" and row.state == "current"
    args = fam.ran[0]
    assert Path(args[0]).name == "PR7-W-Setup-0.3.0.exe"
    assert args[1:5] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]
    assert "/MERGETASKS=!replacenotepad" in args                     # first install: no UAC prompt mid-batch
    assert seen[-1] == ("install", 0, 0) and seen[-2][0] == "download" and seen[-2][1] == seen[-2][2]
    assert not (tmp_path / "dl").exists()                             # the downloaded setup is cleaned away
    fam.release("PR7-W", "0.3.1")
    row = releases.survey([catalog.BY_LETTER["W"]], fetch=fam.fetch, reader=fam.reader)[0]
    releases.install(row, runner=fam.runner, reader=fam.reader)
    assert "/MERGETASKS=!replacenotepad" not in fam.ran[1]          # an update keeps the earlier choices
    assert row.installed.version == "0.3.1"


def test_failures_say_what_went_wrong(fam):
    z = catalog.BY_LETTER["Z"]
    fam.short.add("PR7-Z")
    row = releases.survey([z], fetch=fam.fetch, reader=fam.reader)[0]
    with pytest.raises(UpdateError, match="incomplete"):
        releases.install(row, runner=fam.runner, reader=fam.reader)
    assert fam.ran == []                                              # a broken download is never run
    fam.short.clear(); fam.failing.add("PR7-Z")
    with pytest.raises(UpdateError, match="code 5"):
        releases.install(row, runner=fam.runner, reader=fam.reader)
    with pytest.raises(releases.Cancelled):
        releases.install(row, cancelled=lambda: True, runner=fam.runner, reader=fam.reader)


def test_uninstall_runs_the_uninstaller_quietly_and_waits_for_windows(fam):
    fam.install("PR7-M", "0.1.0")
    row = releases.survey([catalog.BY_LETTER["M"]], reader=fam.reader, online=False)[0]
    releases.uninstall(row, runner=fam.runner, reader=fam.reader)
    assert fam.ran[0] == [f"{fam.home}\\PR7-M\\unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    assert row.installed is None
    # Inno's uninstaller returns before it's finished: the entry is watched until it goes
    fam.install("PR7-M", "0.1.0")
    row = releases.survey([catalog.BY_LETTER["M"]], reader=fam.reader, online=False)[0]
    ticks = []
    late = lambda args: 0                                             # noqa: E731 - returns at once, removes nothing
    releases.uninstall(row, runner=late, reader=fam.reader, wait=10,
                       sleep=lambda s: ticks.append(s) or (len(ticks) == 3 and fam.registry.clear()))
    assert len(ticks) == 3 and row.installed is None
    fam.install("PR7-M", "0.1.0")
    row = releases.survey([catalog.BY_LETTER["M"]], reader=fam.reader, online=False)[0]
    with pytest.raises(UpdateError, match="still lists"):
        releases.uninstall(row, runner=late, reader=fam.reader, wait=0)
