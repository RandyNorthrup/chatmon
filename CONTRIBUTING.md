# Working on Chatmon

Thanks for helping. Problems and ideas go in [issues](https://github.com/RandyNorthrup/chatmon/issues); a
security problem goes privately to a security advisory instead (see [SECURITY.md](SECURITY.md)).

## Setting up

Chatmon needs Python 3.11 or newer. From a clone:

```sh
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --require-hashes -r packaging/requirements-dev.txt
python -m chatmon           # Chatmon from this checkout (bin/chatmon does the same)
```

`packaging/requirements-dev.txt` is exactly what CI installs, with every package's hash. `pip install -e ".[dev]"`
installs the same versions without the hashes, and Chatmon with them.

On Linux, Qt needs a few of the system's libraries (CI installs `libegl1 libgl1 libxkbcommon0 libfontconfig1
libdbus-1-3`). Some tests also use `dbus-run-session` and `dbus-monitor` (the `dbus` and `dbus-x11` packages), the
Wayland protocol files (`wayland-protocols`, `libwayland-dev`), and an X server with XTest: run the tests under
`xvfb-run -a` (`xvfb`, `libxtst6`), as CI does. Without them, those tests skip and say why.

`CHATMON_INSTANCE=<name> python -m chatmon` runs a Chatmon apart from the one you use every day: its own address
for hooks, so the two never hear each other.

## Tests

```sh
python -m pytest
```

The tests need no screen: `tests/conftest.py` picks Qt's offscreen platform, and gives the run a Chatmon address
of its own, so no test reaches a Chatmon you have running. `pyproject.toml` turns warnings into errors (all but
`ResourceWarning`, which is listed at the end instead), stops any test that runs past two minutes (pytest-timeout,
which the tests require), and prints why each skipped test skipped. Each platform's own tests run on that platform
and skip elsewhere, which is why CI runs on Linux, Windows and macOS.

A few tests are left out unless asked for, because they touch something outside the test:

| Set this | To run |
|---|---|
| `CHATMON_TEST_CLIPBOARD=1` | Windows' paste tests, which put things on your clipboard |
| `CHATMON_TEST_WINDOWS_UPDATE=1` | the test that asks Windows Update itself, which can take minutes |
| `CHATMON_GNOME_SESSION=1` | GNOME's own answers, from a real Mutter: `tests/gnome-session.sh` runs it in a container |

More checks, as CI runs them:

- **Coverage:** `python -m coverage run -m pytest`, then `python -m coverage report`. CI combines every OS's
  coverage and fails below `fail_under` in `pyproject.toml`.
- **A distribution's own PyQt6:** `docker run --rm -v "$PWD:/src:ro" ubuntu:24.04 sh /src/.github/scripts/distro-tests.sh`
  runs the whole suite on Ubuntu 24.04's Python and PyQt6. CI does this on `debian:trixie` and `fedora:44` too.
- **Red drills:** `python tests/drills/run.py SPEC.json` breaks the code on purpose, in a copy of the
  repository, and checks that the tests notice (see its docstring).

## Lint and types

```sh
ruff check .
mypy --platform linux       # and win32, and darwin: CI checks each
actionlint                  # the workflows; CI also runs shellcheck on their scripts
zizmor --no-online-audits .github
```

mypy checks every module but those `pyproject.toml` exempts (`ignore_errors`). Taking a module off that list,
once it passes on all three platforms, is always welcome.

## How the code is written

- **No new runtime dependencies.** Chatmon needs PyQt6, and psutil if it's there. The system's own features are
  reached through ctypes, QtDBus or the Qt modules already shipped. Test-only tools are fine.
- **Comments and messages are plain English sentences** that say why.
- **The README's privacy promises stay true.** A change that would break one changes the README first, and
  needs a very good reason.
- **Tests use the real thing:** real Qt objects (the `qapp` fixture), and no mock that skips the behaviour
  under test.

## Words people see, and translations

Every string Chatmon shows goes through `chatmon/i18n.py`, so it can be translated (only English ships so far):

- `_("Couldn't open {file}.").format(file=name)`: a whole sentence, its values in named placeholders. Never build
  one from pieces, so a translator can put the words in their language's order.
- `ngettext("{n} reminder", "{n} reminders", n).format(n=n)` for anything with a count, never `"s" if n != 1`;
  `join(items)` for "a, b and c".
- `N_("…")` marks a string in a table built as its module loads; translate it where it's shown, with `_()`.
- Logs, config keys, command-line flags, protocol strings, product and model names, the offline commands'
  phrases (`chatmon/phrases/`) and anything sent to a brain stay as they are.

After adding or changing a string, bring the template up to date with `python packaging/extract_strings.py`
(`tests/test_i18n.py` fails until you do). It also refuses a string that couldn't be translated, such as an
f-string inside `_()`.

A translation is one file: copy `chatmon/locale/chatmon.pot` to `chatmon/locale/<language>.po` (`de.po`,
`pt_BR.po`), fill in each `msgstr` and set its `Plural-Forms` line, with any gettext editor (Poedit, Lokalize) or
by hand. Chatmon reads it as it is; there's nothing to compile. An entry left empty or marked fuzzy shows in
English. The offline commands' phrases and help are translated separately, in `chatmon/phrases/<language>.json`.

## Dependencies

`packaging/requirements*.in` name the versions; each `requirements*.txt` beside them locks those, and every
dependency of theirs, with hashes. To move a pin, edit the `.in` file (and the `dev` extra in `pyproject.toml`,
for the test and dev lists), then lock again with the command at the top of the `.txt` file, for example:

```sh
uv pip compile packaging/requirements-test.in -o packaging/requirements-test.txt --universal --python-version 3.11 --generate-hashes --exclude-newer 2026-10-31
```

Pick releases at least two weeks old; `--exclude-newer` with a date two weeks back does that for every
dependency. `tests/test_requirements.py` checks that the locks, the `.in` files and the `dev` extra agree.
Dependabot proposes newer actions and packages every week, each once it's two weeks old.

## Releasing

1. Write what's new in `chatmon/changelog.md`, and set the version in `chatmon/__init__.py`.
2. Merge it to main, then tag that commit `v<version>` and push the tag.

The [packages workflow](.github/workflows/packages.yml) builds every installer and package, installs and runs
each one, signs them, drafts the release with the changelog's notes and every file, and publishes it once
they're all attached. [packaging/README.md](packaging/README.md) has the details.
