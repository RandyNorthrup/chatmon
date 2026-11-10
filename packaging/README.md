# Installers and packages

What each release offers besides the wheel, how it's made, and how to make it yourself.

| Platform | File                                   | Made with                          | What it installs                                        |
| -------- | -------------------------------------- | ---------------------------------- | ------------------------------------------------------- |
| Windows  | `Chatmon-<v>-windows-x64-setup.exe`    | PyInstaller, then Inno Setup 6     | `chatmon.exe` (hooks, the command line) and `chatmonw.exe` (no console window) in `%LOCALAPPDATA%\Programs\Chatmon`, or Program Files for everyone; optional Start menu entry, desktop icon, PATH entry and start at login |
| macOS    | `Chatmon-<v>-macos-<arch>.pkg`, `.dmg` | PyInstaller, pkgbuild, hdiutil     | `/Applications/Chatmon.app` (no Dock icon: it's in the menu bar); the `.pkg` also writes `/usr/local/bin/chatmon`, which runs it |
| Linux    | `chatmon_<v>-1_all.deb`, `chatmon-<v>-1.noarch.rpm` | nfpm                  | Chatmon in `/usr/lib/chatmon`, `/usr/bin/chatmon`, an app menu entry and icons; the system's Python and PyQt6 run it |

The Windows and macOS builds carry their own Python and Qt; the Linux ones depend on
`python3-pyqt6` (6.5 or newer) instead, so they look and behave like the rest of the desktop.

## How releases get them

[`.github/workflows/packages.yml`](../.github/workflows/packages.yml) builds every one on a fresh machine of
its kind, installs it there, starts Chatmon without a screen (Qt's offscreen platform), talks to it,
quits it, and uninstalls it. When a release is published, it adds them all to the release, with the
wheel and sdist; the release's tag has to match `chatmon/__init__.py`'s version. A pull request that
touches `packaging/`, or running the workflow by hand, builds and checks them without publishing.

## Making them yourself

On the platform you're building for, from the repository's root:

```sh
python -m pip install -r packaging/requirements.txt   # Windows and macOS
python packaging/build.py windows   # also needs Inno Setup 6 (winget install JRSoftware.InnoSetup)
python packaging/build.py macos     # Xcode's command line tools
python packaging/build.py linux     # nfpm: packaging/linux/get-nfpm.sh downloads and checks it
```

They land in `dist/`. `python packaging/build.py smoke CLI APP` checks an installed one, in a scratch home
of its own (for example `smoke chatmon chatmon` after installing a .deb), and
`pwsh packaging/windows/test-install.ps1 <setup.exe> <version>` puts the Windows installer through what CI
does: install with every option, check each, run it, uninstall, check it's all gone. Don't run that on a
computer whose Chatmon you want to keep set up as it is.

`packaging/make_icons.py` (needs Pillow) makes `packaging/icons` again from the penguin's idle frame.

## Not yet

- **Signing.** The Windows installer and the macOS app aren't signed, so Windows SmartScreen and macOS
  Gatekeeper ask the first time. Signing needs a code-signing certificate on Windows and an Apple
  Developer ID (and notarization) on macOS.
- **Other Linux distributions**: pipx works on any of them (see the README).
- Inno Setup is free for non-commercial use, which Chatmon is; a commercial fork would need its license.
