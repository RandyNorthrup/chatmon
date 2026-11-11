# Installers and packages

What each release offers besides the wheel, how it's made, and how to make it yourself.

| Platform | File                                   | Made with                          | What it installs                                        |
| -------- | -------------------------------------- | ---------------------------------- | ------------------------------------------------------- |
| Windows  | `Chatmon-<v>-windows-x64-setup.exe`    | Nuitka, then Inno Setup 6          | `chatmon.exe` (hooks, the command line) and `chatmonw.exe` (no console window) in `%LOCALAPPDATA%\Programs\Chatmon`, or Program Files for everyone; optional Start menu entry, desktop icon, PATH entry and start at login |
| macOS    | `Chatmon-<v>-macos-<arch>.pkg`, `.dmg` | Nuitka, pkgbuild, hdiutil          | `/Applications/Chatmon.app` (no Dock icon: it's in the menu bar); the `.pkg` also writes `/usr/local/bin/chatmon`, which runs it |
| Linux    | `chatmon_<v>-1_all.deb`, `chatmon-<v>-1.noarch.rpm` | nfpm                  | Chatmon in `/usr/lib/chatmon`, `/usr/bin/chatmon`, an app menu entry and icons; the system's Python and PyQt6 run it |

The Windows and macOS builds carry their own Python and Qt; the Linux ones depend on
`python3-pyqt6` (6.5 or newer) instead, so they look and behave like the rest of the desktop.

## How releases get them

[`.github/workflows/packages.yml`](../.github/workflows/packages.yml) builds every one on a fresh machine of
its kind, installs it there, starts Chatmon without a screen (Qt's offscreen platform), talks to it,
quits it, and uninstalls it. When a release is published, it adds them all to the release, with the
wheel and sdist; the release's tag has to match `chatmon/__init__.py`'s version. A pull request that
touches `packaging/`, or running the workflow by hand, builds and checks them without publishing.

## Signing (Windows)

A release's Windows installer, the uninstaller it puts beside Chatmon, Chatmon's own programs
(`chatmon.exe`, `chatmonw.exe`) and every library beside them that its maker didn't sign are signed by
Randy Northrup through Azure Artifact Signing, and timestamped, so they stay valid after the certificate
expires. Windows then names Randy Northrup as their publisher, and Smart App Control can tell them
apart from unknown programs. SmartScreen goes by reputation as well as by signature, and builds it for
each new file as people download it, so a new version may still be asked about for a while; the prompt
then names its publisher.

The workflow's `sign-windows` job does it. It's the only job that can sign: Azure trusts GitHub's
sign-in only from this repository's `release` environment, which only `v*` tags can use, and its identity
may only sign with that one certificate profile. It runs nothing from PyPI and none of Chatmon: it signs
the Chatmon the `windows` job compiled, and Inno Setup builds the installer around it again, signing the
installer and uninstaller as it makes them. Another job then installs that installer, runs it,
uninstalls it, and checks every signature, before it's published.

**Why Nuitka.** A signature covers a whole program except its certificate table, which Windows leaves out
of what it checks ([CVE-2013-3900](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2013-3900);
the stricter check is off unless you turn it on). So a signed program must never run anything it finds
there, or anywhere its signature doesn't reach. PyInstaller's programs search their own file from the end
for the Python they run, which would find code planted in that table first, and read more Python from a
zip file beside them. Nuitka compiles Chatmon, and the standard library it uses, into the program itself:
what it runs is in signed programs and signed libraries, and `build.py` checks that neither program
carries anything after its last section. Inno Setup's installer reads its files from where a part its
signature covers says they are, so it can't be led astray either.

## Making them yourself

On the platform you're building for, from the repository's root:

```sh
python -m pip install -r packaging/requirements.txt   # Windows and macOS
python packaging/build.py windows   # Visual Studio's C++ build tools, and Inno Setup 6 (winget install JRSoftware.InnoSetup)
python packaging/build.py macos     # Xcode's command line tools
python packaging/build.py linux     # nfpm: packaging/linux/get-nfpm.sh downloads and checks it
```

They land in `dist/`. Nuitka compiles all of Chatmon to C, so a build takes a while: Windows compiles it
twice, once for each program. `python packaging/build.py smoke CLI APP` checks an installed one, in a scratch home
of its own (for example `smoke chatmon chatmon` after installing a .deb), and
`pwsh packaging/windows/test-install.ps1 <setup.exe> <version> -Unsigned` puts the Windows installer through what CI
does: install with every option, check each, run it, uninstall, check it's all gone. Don't run that on a
computer whose Chatmon you want to keep set up as it is.

`packaging/make_icons.py` (needs Pillow) makes `packaging/icons` again from the penguin's idle frame.

## Not yet

- **Signing on macOS.** The macOS app isn't signed, so Gatekeeper asks the first time. That needs an
  Apple Developer ID, and notarization.
- **Other Linux distributions**: pipx works on any of them (see the README).
- Inno Setup is free for non-commercial use, which Chatmon is; a commercial fork would need its license.
