## Reopened: screen readers with at-spi2-core 2.62 (2026-11-15, T-10)

The wayland worker found that at-spi2-core 2.62 has dropped `org.a11y.Status ScreenReaderEnabled`, the way Chatmon
found a running screen reader other than Orca 49 and later on Linux. New requirement M4A-12, criteria AC-12a to AC-12e,
task T-10, on branch `wave4/a11y`. Review: [readers/readiness.md](reports/m4a/readers/readiness.md).

**What 2.62 changed.** Seen in WSL (at-spi2-core 2.62.1): `org.a11y.Status` now has `IsEnabled` alone;
`ScreenReaderEnabled` answers "No such property". From 2.61.0 the bus launcher turns `IsEnabled` on as an assistive
technology registers for events, rather than from a gsettings key (at-spi2-core's NEWS). So `IsEnabled` says that
something listens, not that it's a screen reader.

**What Chatmon looks at now** (`linuxsession.ScreenReaders`, one per app, made by Desk at the start):

- Orca's remote controller (`org.gnome.Orca1.Service`, then `org.gnome.Orca.Service`), registered or gone, through a
  `QDBusServiceWatcher` and one `NameHasOwner` each at the start. Chatmon speaks through it.
- AT-SPI's `ScreenReaderEnabled`, where at-spi2-core still keeps it (2.52 on Ubuntu 24.04). It's read with `GetAll`
  once AT-SPI's bus is there, and followed through `PropertiesChanged`.
- GNOME's `org.gnome.desktop.a11y.applications screen-reader-enabled`, on GNOME, through `gsettings monitor`.
- A screen reader's own process (`orca`, `odilia`, `fenrir` in `/proc/PID/comm`, this user's), looked for again
  whenever `IsEnabled` changes and at each `a11y.reader()`. That's how an Orca before 49, or another reader, is found
  under 2.62.

`IsEnabled` alone isn't counted: a magnifier's or an on-screen keyboard's user would get the ask box as a window and
read-aloud notifications. Nothing waits: the old look's blocking `isServiceRegistered` and its 500 ms `Get`, every 15
seconds on the screen's thread, are gone. Nothing starts a service: the `Get` could start AT-SPI's launcher, and now
AT-SPI is asked only once its bus is there. Desk passes each change on as `screen_reader_changed`, which `app.py`
already follows (it looks again, and puts the ask box where a reader can find it).

Qt 6.12's `QDBusServiceWatcher.setWatchedServices` never returned on a real session bus. The services are added one at
a time.

**Verification.** Windows: `tests/test_screen_readers.py` (each source with real D-Bus messages, /proc as a folder),
the M4A tests, the whole suite, and red drills (`readers/drill-spec.json`). WSL (at-spi2-core 2.62.1, Orca 51.1), on
private session buses:

- at-spi2-core's own launcher, where a reader's process starts as `IsEnabled` turns on;
- a pretend launcher of the kind before 2.62 (`tests/fake_a11y_bus.py`);
- GNOME's setting, through gsettings with a keyfile of the test's own;
- the real-sway screen-reader tests with the real Orca;
- red drills (`readers/drill-spec-linux.json`).

Every M4A drill in `wave4/` ran again, as T-01, T-02, T-03, T-05, T-07 and T-09 share the changed files. T-09's macOS
check is CI's, so it's pending until the next run.
