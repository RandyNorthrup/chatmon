# M4A reopened: readiness review for M4A-12 (2026-11-15)

The plan was closed at fb19cb9 (wave 4). The wayland worker found that at-spi2-core 2.62 has dropped
`org.a11y.Status ScreenReaderEnabled`, so on Linux a running screen reader other than Orca 49 and later was no longer
detected. This review covers the new requirement, M4A-12, and the plan as a whole after it.

**What 2.62 changed, observed.** In WSL (Arch: at-spi2-core 2.62.1, Orca 51.1), on a private session bus,
`gdbus introspect` of `org.a11y.Bus /org/a11y/bus` shows `org.a11y.Status` with one property, `readwrite b IsEnabled`;
`Get org.a11y.Status ScreenReaderEnabled` answers `InvalidArgs: No such property`. at-spi2-core's NEWS, 2.61.0: the
bus launcher "now listens for ATs registering events and assumes that accessibility is enabled" rather than relying on
a gsettings key. So IsEnabled says that some assistive technology listens (a screen reader, a magnifier, an on-screen
keyboard, Accerciser), not which. GNOME's `org.gnome.desktop.a11y.applications screen-reader-enabled` is still in
gsettings-desktop-schemas 51.

**The requirement.** M4A-12: on Linux, a running screen reader is detected with at-spi2-core 2.62 and later as before
it: Orca's remote controller (49+), `ScreenReaderEnabled` where it's still kept, GNOME's setting, and a screen reader's
own process; nothing waits on the screen's thread, nothing starts a service, and a change is reported as Desk's
`screen_reader_changed`. Criteria AC-12a to AC-12e, task T-10.

**Checked.**
- *Coverage.* Each source has a criterion and a task: the process (AC-12a), Orca's remote controller and speaking
  through it (AC-12b), AT-SPI before and from 2.62 and never starting its bus (AC-12c), GNOME's setting (AC-12d), the
  signal (AC-12e).
- *Conflicts.* IsEnabled alone is not counted as a screen reader: it would hold the ask box as a window and send
  read-aloud notifications for an on-screen keyboard's user. It is used to look again for a reader's process, which is
  what registered. Older at-spi2-core (Ubuntu 24.04's 2.52) keeps ScreenReaderEnabled, which still counts.
- *Failure behavior.* No session bus, AT-SPI's bus not running, no /proc, no gsettings: each source says nothing, the
  others still count. AT-SPI's bus going away forgets what it said. A process read that fails (gone, not ours) is
  passed over.
- *Non-blocking.* The old look made two blocking calls on the screen's thread (`isServiceRegistered`, and a 500 ms
  `Get` that could start AT-SPI's launcher). The new one asks without waiting and reads a cache; the process look is a
  read of /proc.
- *Ownership and contracts.* `a11y.py`, `linuxsession.py`, `presence.py` and their tests are M4A's. `app.py`
  already connects `screen_reader_changed` (M7); no change there. No user-facing string is added
  (`packaging/extract_strings.py --check` passes); "Odilia" and "Fenrir" are names.
- *Effect on the closed tasks.* T-01, T-03, T-05, T-07 and T-09 change paths are touched (T-02 through T-01), so their receipts go stale
  and their checks run again. T-09's end-to-end check is macOS's (CI); it waits for the next CI run.

Result: ready.
