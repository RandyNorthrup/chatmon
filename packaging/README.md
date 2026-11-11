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

## Signing (Windows)

A release's Windows installer, and the uninstaller it puts beside Chatmon, are signed by Randy Northrup
through Azure Artifact Signing, and timestamped, so they stay valid after the certificate expires.
Windows then names Randy Northrup as their publisher. SmartScreen goes by reputation as well as by
signature, and builds it for each new file as people download it, so a new version may still be asked
about for a while; the prompt then names its publisher.

The workflow's `sign-windows` job does it. It's the only job that can sign: Azure trusts GitHub's
sign-in only from this repository's `release` environment, which only `v*` tags can use, and its identity
may only sign with that one certificate profile. It runs nothing from PyPI and none of Chatmon: it takes
the Chatmon the `windows` job froze, and Inno Setup builds the installer around it again, signing each of
the two as it makes it. Another job then installs that installer, runs it, uninstalls it, and checks both
signatures, before it's published.

**`chatmon.exe` and `chatmonw.exe` aren't signed, on purpose.** PyInstaller's bootloader finds the
Python it runs by searching its own file from the end. Windows leaves a file's certificate table out of
what its signature covers ([CVE-2013-3900](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2013-3900);
the stricter check is off unless you turn it on), so anyone could put their own code in a signed copy's
table, where the bootloader would find it first and run it, while Windows still called the file signed
by Randy Northrup. Inno Setup's installer reads its files from where a part its signature covers says
they are, so it can't be led astray like that. SmartScreen asks only about downloaded files, so for most
people the installer's signature is the one that counts. Smart App Control, on the Windows 11 computers
that have it on, checks every program, and may block an unsigned one it doesn't know; signing them
safely needs a bootloader that stops searching where the certificate table starts.

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

- **Signing on macOS.** The macOS app isn't signed, so Gatekeeper asks the first time. That needs an
  Apple Developer ID, and notarization.
- **Other Linux distributions**: pipx works on any of them (see the README).
- Inno Setup is free for non-commercial use, which Chatmon is; a commercial fork would need its license.
