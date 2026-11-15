## Reconciliation, wave 4, round three (2026-11-15)

Round three closes this plan on **a4fe9f8**: `wave4/mac-drills` with `improve/assessment-fixes` merged in. That brings
in the toast merge (cbeed17) and the quit guard (86e84e0). The four red drills that round two left without a place to
run have one now, each approved by the owner that day.

**AC-03E, on testpc2's signed-in desktop.** This workstation's user has notifications off, and testpc2's desktop has
them on. The toast worker's first run there found that the toast test took `hide()`'s word for it. 8c24b1c fixed
that: the test now waits for the hidden toast to leave Action Center. Both `hide()` mutations then failed the test
([reports/m4b/testpc2/](reports/m4b/testpc2/README.md), [reports/m4b/w4c/](reports/m4b/w4c/README.md)). They ran
there again for this round.

**AC-00C, AC-01D and AC-02F, on the owner's MacBook Pro** (macOS 15.7.9, Intel), in his signed-in Aqua session,
where Carbon's hot keys and NSSound reach the window server ([reports/m4b/mac/](reports/m4b/mac/README.md)):

- A Linux-only import at the top of `sound.py` fails `test_it_imports_here[sound]`. The same import in `libdbus.py`
  fails too, but that file is the portal task's, so its drill can't be AC-00C's.
- Carbon's conflict reported as nothing fails the conflict test.
- Leaving out the NSSound's volume fails the NSSound test, at NSSound's own 1.0.

The whole suite also passed there, as CI's macOS job runs it. That replaces CI's macOS receipt, which went stale with
8c24b1c.

**Why everything ran again.** ROADMAP.md was amended for round three (`3586a0d+wave4c`). It is a rule of every plan,
so every receipt here went stale, whatever files a merge changed. Every check was run again on a4fe9f8
([reports/m4b/w4d/](reports/m4b/w4d/README.md)):

- the requirements review;
- the whole suite on this workstation: 1259 passed, 178 skipped;
- the 36 Windows drills;
- in WSL, the Linux tests (58 passed, 7 skipped) and the 7 Linux drills;
- on testpc2, the toast test (12 passed, 1 skipped) and both `hide()` drills;
- on the Mac, the suite (1235 passed, 201 skipped, with the owner's keychain test left out; 8 on Qt's cocoa platform)
  and the three drills.

Every drill went green, red and green again.

**What remains.** Nothing. Every task is verified.

**Receipts.** The earlier passing receipts (W4B-, W4C-) are now stale history, with their hashes untouched. The
deferred ones stay as history too. The W4D- and MAC- receipts replace them.
