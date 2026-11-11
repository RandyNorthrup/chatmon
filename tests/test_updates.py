"""Updates: which release file updates which install, what a release must look like to be trusted, the
checks a download must pass, and what's new after an update. No network: GitHub's replies are made here."""

import hashlib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from chatmon import __version__, changelog, report, updates

TAG = "v9.0.0"
BASE = updates.DOWNLOADS + TAG + "/"


def release_json(**over):
    data = {
        "tag_name": TAG,
        "draft": False,
        "prerelease": False,
        "body": "## New\n- Something",
        "html_url": f"https://github.com/{updates.REPO}/releases/tag/{TAG}",
        "assets": [
            {"name": "Chatmon-9.0.0-windows-x64-setup.exe", "browser_download_url": BASE + "Chatmon-9.0.0-windows-x64-setup.exe"},
            {"name": "SHA256SUMS.txt", "browser_download_url": BASE + "SHA256SUMS.txt"},
        ],
    }
    data.update(over)
    return data


def test_versions_compare_as_numbers():
    assert updates.newer("0.10.0", "0.9.9") and updates.newer("1.0", "0.99.99")
    assert not updates.newer("0.6.0", "0.6") and not updates.newer("0.5.1", "0.6.0")
    assert changelog.version_key("v0.6.0") == changelog.version_key("0.6")


def test_a_published_release_is_read():
    release = updates.parse_release(release_json())
    assert release.version == "9.0.0" and release.page.endswith("/releases/tag/v9.0.0")
    assert set(release.assets) == {"Chatmon-9.0.0-windows-x64-setup.exe", "SHA256SUMS.txt"}


@pytest.mark.parametrize(
    "over",
    [{"draft": True}, {"prerelease": True}, {"tag_name": "nightly"}, {"tag_name": "v1.2.3-rc1"}, {"tag_name": None}],
)
def test_drafts_prereleases_and_odd_tags_are_never_offered(over):
    assert updates.parse_release(release_json(**over)) is None


def test_only_this_repositorys_own_files_for_that_release_are_taken():
    elsewhere = [
        {"name": "Chatmon-9.0.0-windows-x64-setup.exe", "browser_download_url": "https://evil.example/Chatmon-9.0.0-windows-x64-setup.exe"},
        {"name": "SHA256SUMS.txt", "browser_download_url": updates.DOWNLOADS + "v8.0.0/SHA256SUMS.txt"},  # another release's
        {"name": "x", "browser_download_url": "http://github.com/RandyNorthrup/chatmon/releases/download/v9.0.0/x"},
    ]
    assert updates.parse_release(release_json(assets=elsewhere)).assets == {}


def test_a_release_page_elsewhere_is_replaced_by_the_real_one():
    assert updates.parse_release(release_json(html_url="https://evil.example/")).page == updates.PAGE


def test_anything_else_from_github_is_not_a_release():
    for data in (None, [], "text", 3, {"tag_name": ["v1"]}):
        assert updates.parse_release(data) is None


def test_checksums_are_read_in_sha256sums_own_format():
    a, b = "a" * 64, "B" * 64
    text = f"{a}  Chatmon-9.0.0-windows-x64-setup.exe\n{b} *chatmon_9.0.0-1_all.deb\nnot a line\n{'c' * 63}  short\n"
    assert updates.parse_sums(text) == {"Chatmon-9.0.0-windows-x64-setup.exe": a, "chatmon_9.0.0-1_all.deb": b.lower()}


@pytest.mark.parametrize(
    "kind, machine, name",
    [
        ("windows", "AMD64", "Chatmon-9.0.0-windows-x64-setup.exe"),
        ("macos", "arm64", "Chatmon-9.0.0-macos-arm64.pkg"),
        ("macos", "x86_64", "Chatmon-9.0.0-macos-intel.pkg"),
        ("deb", "x86_64", "chatmon_9.0.0-1_all.deb"),
        ("rpm", "x86_64", "chatmon-9.0.0-1.noarch.rpm"),
        ("pipx", "x86_64", "chatmon-9.0.0-py3-none-any.whl"),
        ("manual", "x86_64", None),
    ],
)
def test_each_install_gets_its_own_installer(kind, machine, name):
    assert updates.asset_name(kind, "9.0.0", machine) == name


def test_a_download_that_doesnt_match_its_checksum_is_refused(tmp_path):
    f = tmp_path / "chatmon_9.0.0-1_all.deb"
    f.write_bytes(b"the real thing")
    good = hashlib.sha256(b"the real thing").hexdigest()
    assert updates.verify(f, good, "deb") is None
    assert "checksum" in updates.verify(f, "0" * 64, "deb")


def test_on_windows_the_installer_must_be_signed_by_randy_northrup(tmp_path, monkeypatch):
    f = tmp_path / "setup.exe"
    f.write_bytes(b"setup")
    good = hashlib.sha256(b"setup").hexdigest()
    ours = "CN=Randy Northrup, O=Randy Northrup, L=Ventura, S=California, C=US"  # as Windows words it, from a real release
    microsoft = "CN=Microsoft ID Verified CS AOC CA 04, O=Microsoft Corporation, C=US"
    for status, signer, issuer, ok in (
        ("Valid", ours, microsoft, True),
        ("Valid", "CN=Randy Northrup, O=Randy Northrup, L=Austin, S=Texas, C=US", "CN=Microsoft ID Verified CS EOC CA 01, O=Microsoft Corporation, C=US", True),
        ("Valid", "CN=Randy Northrup, O=Randy Northrup, C=US", microsoft, True),
        ("Valid", "CN=Randy Northrup", microsoft, False),  # a namesake: no organization
        ("Valid", "CN=Randy Northrup, O=Someone Else Inc, C=US", microsoft, False),
        ("Valid", "CN=Randy Northrupp, O=Randy Northrup, C=US", microsoft, False),
        ("Valid", ours + ", OU=extra", microsoft, False),
        ("Valid", ours, "CN=Some Other CA, O=Other, C=US", False),  # not Microsoft's identity-verified signing
        ("Valid", ours, "CN=Microsoft ID Verified CS AOC CA 04, O=Not Microsoft, C=US", False),
        ("HashMismatch", ours, microsoft, False),
        ("NotSigned", "", "", False),
    ):
        monkeypatch.setattr(updates, "windows_signer", lambda path, s=status, n=signer, i=issuer: (s, n, i))
        assert (updates.verify(f, good, "windows") is None) is ok, (status, signer, issuer)


def test_the_installer_is_never_handed_the_path_as_part_of_a_script(tmp_path):
    pkg = tmp_path / 'it"s $(rm -rf ~) & a.pkg'
    program, args, env = updates.installer_command("macos", pkg)
    assert program == "/usr/bin/osascript" and str(pkg) not in " ".join(args) and env == {"CHATMON_UPDATE": str(pkg)}
    program, args, env = updates.installer_command("windows", tmp_path / "setup.exe")
    assert program == str(tmp_path / "setup.exe") and "/VERYSILENT" in args and "/relaunch=1" in args


def test_a_chatmon_it_cant_update_says_how_instead(monkeypatch):
    monkeypatch.setattr(updates, "_editable", lambda: True)
    assert "git pull" in updates.how_to_update("manual", "9.0.0")
    assert "installer" in updates.how_to_update("windows", "9.0.0")


def test_a_source_checkout_is_never_updated_by_itself(monkeypatch):
    monkeypatch.setattr(updates.paths, "frozen", lambda: False)
    monkeypatch.setattr(updates, "_editable", lambda: True)
    assert updates.install_kind() == "manual"


def test_the_changelog_has_this_version_and_reads_back():
    releases = changelog.load()
    assert releases and changelog.version_key(releases[0].version) == changelog.version_key(__version__), "write what's new in chatmon/changelog.md"
    assert all(r.sections for r in releases)
    assert [changelog.version_key(r.version) for r in releases] == sorted((changelog.version_key(r.version) for r in releases), reverse=True)


def test_whats_new_covers_every_version_skipped():
    text = "## 2.0\n### New\n- B\n  more of B\n### Fixes\n- C\n\n## 1.5\n### Fixes\n- A\n\n## 1.0\n### New\n- old\n"
    releases = changelog.parse(text)
    assert releases[0].sections == {"New": ["B more of B"], "Fixes": ["C"]}
    skipped = changelog.since("1.0", "2.0", releases)
    assert [r.version for r in skipped] == ["2.0", "1.5"]
    notes = changelog.notes(skipped)
    assert "**2.0**" in notes and "**1.5**" in notes and "old" not in notes
    assert changelog.notes(skipped[:1]).startswith("### New\n- B more of B")


def test_a_problem_report_carries_nothing_personal(monkeypatch, tmp_path):
    monkeypatch.setenv("USER", "secret-user-name")
    link = report.url(install="windows", brain="Claude Code", title="It froze")
    parts = urlsplit(link)
    fields = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert parts.scheme == "https" and parts.netloc == "github.com" and parts.path == f"/{updates.REPO}/issues/new"
    assert fields["template"] == report.BUG and fields["version"] == __version__ and fields["install"] == "Windows installer"
    assert fields["brain"] == "Claude Code" and fields["title"] == "It froze"
    assert set(fields) == {"template", "version", "system", "install", "brain", "title"}
    assert "secret-user-name" not in link and str(Path.home()) not in link and str(tmp_path) not in link
    assert fields["system"].split()[0] in ("Windows", "macOS", "Linux", "FreeBSD") and "Qt " in fields["system"]


# -- the whole way, against a pretend GitHub on this computer


class Inline:
    """Background, without the thread: the work runs at once."""

    def run(self, work, then):
        try:
            result = work()
        except Exception as exc:
            result = exc
        then(result)


@pytest.fixture
def github(tmp_path, monkeypatch):
    """A local web server holding a release, its installer and its checksums."""
    import http.server
    import json
    import threading

    files: dict[str, bytes] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = files.get(self.path)
            self.send_response(200 if body is not None else 404)
            self.send_header("Content-Length", str(len(body or b"")))
            self.end_headers()
            self.wfile.write(body or b"")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setattr(updates, "LATEST", base + "/latest")
    monkeypatch.setattr(updates, "DOWNLOADS", base + "/download/")
    monkeypatch.setattr(updates, "SECURE", "http://127.0.0.1:")  # in tests only: the real one is https
    monkeypatch.setattr(updates.paths, "state_dir", lambda: tmp_path / "state")
    monkeypatch.setattr(updates, "installer_command", lambda kind, path: ("installer", [str(path)], {}))

    def publish(installer: bytes, sums_for: bytes | None = None):
        name = "chatmon_9.0.0-1_all.deb"
        files["/download/v9.0.0/" + name] = installer
        files["/download/v9.0.0/SHA256SUMS.txt"] = f"{hashlib.sha256(sums_for or installer).hexdigest()}  {name}\n".encode()
        files["/latest"] = json.dumps({
            "tag_name": "v9.0.0", "draft": False, "prerelease": False, "body": "## New\n- Nine",
            "html_url": "", "assets": [{"name": n.rsplit("/", 1)[1], "browser_download_url": base + n} for n in files if n.startswith("/download/")],
        }).encode()

    yield publish
    server.shutdown()


def run_updater(qapp, kind="deb"):
    from PyQt6.QtCore import QEventLoop, QTimer

    updater = updates.Updater(Inline())
    seen = []
    loop = QEventLoop()
    for signal, name in ((updater.available, "available"), (updater.newer_only, "newer"), (updater.up_to_date, "up to date"), (updater.failed, "failed")):
        signal.connect(lambda *args, name=name: (seen.append((name, args)), loop.quit()))
    QTimer.singleShot(10_000, loop.quit)
    updater.check(kind)
    loop.exec()
    return updater, seen


def test_a_newer_release_is_downloaded_checked_and_offered(qapp, github):
    github(b"the real installer")
    updater, seen = run_updater(qapp)
    assert [name for name, _ in seen] == ["available"], seen
    assert seen[0][1][0].version == "9.0.0" and seen[0][1][0].notes == "## New\n- Nine"
    assert updater.ready.read_bytes() == b"the real installer" and not list(updater.ready.parent.glob("*.part"))


def test_a_tampered_download_is_thrown_away_never_offered(qapp, github):
    github(b"something else", sums_for=b"the real installer")
    updater, seen = run_updater(qapp)
    assert [name for name, _ in seen] == ["failed"] and "checksum" in seen[0][1][0]
    assert updater.ready is None and not any(updates.folder().iterdir())


def test_a_download_past_the_limit_is_stopped(qapp, github, monkeypatch):
    monkeypatch.setattr(updates, "MAX_DOWNLOAD", 1000)
    github(b"x" * 5000)
    updater, seen = run_updater(qapp)
    assert [name for name, _ in seen] == ["failed"] and updater.ready is None
    assert not any(updates.folder().iterdir())


def test_nothing_newer_says_so(qapp, github, monkeypatch):
    github(b"x")
    monkeypatch.setattr(updates, "__version__", "9.0.0")
    monkeypatch.setattr(updates, "newer", lambda version, than="9.0.0": changelog.version_key(version) > changelog.version_key(than))
    _, seen = run_updater(qapp)
    assert [name for name, _ in seen] == ["up to date"]


def test_a_chatmon_that_cant_install_it_is_only_told(qapp, github):
    github(b"x")
    _, seen = run_updater(qapp, kind="manual")
    assert [name for name, _ in seen] == ["newer"]


def test_an_update_is_checked_again_just_before_its_installed(qapp, github, monkeypatch):
    from PyQt6.QtCore import QEventLoop, QTimer

    github(b"the real installer")
    updater, seen = run_updater(qapp)
    assert seen[0][0] == "available"
    updater.ready.write_bytes(b"swapped while it waited")  # anything that changed it since
    started = []
    monkeypatch.setattr(updates.QProcess, "startDetached", lambda *a: started.append(a) or (True, 0))
    failed = []
    updater.failed.connect(failed.append)
    updater.install()
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec()
    assert failed and "checksum" in failed[0] and not started and updater.ready is None


def test_an_installer_that_wont_start_says_so_and_frees_the_updater(qapp, github):
    from PyQt6.QtCore import QEventLoop, QTimer

    github(b"the real installer")
    updater, _ = run_updater(qapp)  # its installer_command is "installer", which doesn't exist
    failed = []
    updater.failed.connect(failed.append)
    updater.install()
    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)
    loop.exec()
    assert failed and "couldn't start" in failed[0] and not updater.busy and updater.ready.exists()
