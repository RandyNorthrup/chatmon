# The four screen-reader problems, fixed and checked again (2026-11-15, later)

The problems found by [the probe](../README.md), fixed on `wave5/screen-readers`, each in a commit of its own on
65ed989's tree, then checked with the real screen readers. Every runner round below applied those commits as a patch
([workflows/fix.patch](workflows/fix.patch), byte for byte `git diff cff1b02 212db99 -- chatmon tests`) to a checkout of
main inside the job, so the probe branch held only its workflow file.

| Commit | Problem | Fix |
|---|---|---|
| cbee1b2 | 1. VoiceOver dropped held announcements, and the greeting | `a11y.VoiceOver.SETTLE_MS = 2500`: what's held, and what's said in the first 2.5 s after Chatmon becomes active (or starts active), is posted then, from a single-shot `QTimer`. AppKit has no "VoiceOver has finished" notification (iOS has `UIAccessibilityAnnouncementDidFinishNotification`; macOS has nothing like it), so the measured time it is. |
| 944897e | 2. With VoiceOver on, typing in the ask box went nowhere | `self.title.setFocusProxy(self.entry)` in `AskBox` |
| 2b148c2 | 3. Windows: Chatmon's own stage made Windows say a full-screen app was running | The stage's native window is marked `NonRudeHWND` (`clickthrough.WindowsPointerToggle`, again whenever Qt gives it a new one). The bubble-hold change proposed earlier was dropped: Windows' "busy" is a real full-screen app again, and it still holds bubbles (tested). |
| 212db99 | 4. `chatmon ask` from a script didn't make Chatmon active on macOS 14+ | Once the box is open, the command asks for it from its own process: `NSRunningApplication activateWithOptions:` by the running Chatmon's process id (its answer to `status`), `macnative.activate_app` |

## Tests and drills

New and changed tests:

- `tests/test_platform_events.py`:
  - `test_voiceover_holds_announcements_until_chatmon_is_in_front` (now with the settle),
  - `test_voiceover_waits_after_chatmon_comes_in_front`,
  - `test_voiceover_is_given_the_time_it_was_measured_to_need`.
- `tests/test_ask_box.py`: `test_a_screen_reader_on_the_title_leaves_the_keyboard_in_the_field`.
- `tests/test_clickthrough.py`: `test_the_stage_isnt_taken_for_a_full_screen_app`, `test_a_new_native_window_is_marked_too`.
- `tests/test_presence.py`: `test_a_full_screen_app_still_holds_bubbles_on_windows`.
- `tests/test_cli.py`: `test_on_macos_ask_makes_chatmon_the_active_app_once_the_box_is_open`,
  `test_making_chatmon_active_is_macos_only_and_never_fails`.
- `tests/test_macnative.py` (macOS only): `test_activating_an_app_by_its_process_id_answers_and_never_raises`.

**Red drills** ([drill-spec.json](drill-spec.json), `tests/drills/run.py`, on Windows):

| Drill | What it takes out | Result |
|---|---|---|
| SR-1-held-posted-at-activation | the settle, on activation | green, red, green |
| SR-1-said-at-once-while-just-active | the settle, as Chatmon starts | green, red, green |
| SR-1-a-second-only | 1000 ms instead of 2500 | green, red, green |
| SR-2-title-takes-the-keyboard | the focus proxy | green, red, green |
| SR-3-stage-left-rude | the `NonRudeHWND` property | green, red, green (both stage tests) |
| SR-3-busy-not-quiet | busy (2) taken out of `_QUNS` | green, red, green |
| SR-4-ask-leaves-it-behind | the client's activation | green, red, green |

All seven passed in one run ([drills.log](drills.log), [drills-results.json](drills-results.json),
[drills-stdout.log](drills-stdout.log)). The first run had SR-4's expected text wrong: its red run failed as intended,
at `tests/test_cli.py:122`, but pytest's shortened diff didn't print the string I'd asked for. After that string was
corrected, all seven ran again.

The macOS-only test (`test_activating_an_app_by_its_process_id_answers_and_never_raises`) can't run here. CI's macOS
legs run it with `QT_QPA_PLATFORM=cocoa python -m pytest tests/test_macnative.py`, and the whole suite with
`python -m pytest` (offscreen), as `.github/workflows/ci.yml` does.

**Gates on Windows:**

- The whole suite: 1,267 passed, 180 skipped, exit 0 (offscreen, below normal priority).
- `mypy --platform linux`, `win32` and `darwin`: no issues in 70 files.
- `ruff check .`: clean.
- `python packaging/extract_strings.py --check`: exit 0. The template is current; no new strings.

## How `chatmon ask` was made to work: two studies on the GitHub macOS runner

With Finder in front, `chatmon ask`, then each way of bringing Chatmon forward was tried from another process.
Chatmon ran from source and as the installed Chatmon.app, built and installed as the packages workflow does (an
accessory app, `LSUIElement`). The frontmost app was asked three ways: AppKit from a fresh process
(`NSWorkspace frontmostApplication`), LaunchServices (`lsappinfo front`), and System Events.

- [Study 1](activation-study-1) (run 43767504101, second attempt) asked System Events alone. It reported the accessory
  app never frontmost, and that turned out to be System Events' blind spot.
- [Study 2](activation-study-2) (run 43768643364) asked AppKit and LaunchServices. Each way was tried twice:

| Way | From source | Chatmon.app |
|---|---|---|
| `chatmon ask` alone (Chatmon's own `NSApp.activate`) | not frontmost, 2/2 | not frontmost, 2/2 |
| Chatmon's shortcut (Cmd+Shift+Space) | frontmost, 2/2 | frontmost, 2/2 |
| `NSRunningApplication activateWithOptions:`, from the command's process | frontmost, 2/2 | frontmost, 2/2 |
| `activateFromApplication:options:` (macOS 14) | (study 1 only) | frontmost, 2/2 |
| `NSWorkspace openApplicationAtURL:configuration:` (activates) | frontmost, 2/2 | frontmost, 2/2 |
| `open -a <bundle>` | (study 1 only) | frontmost, 2/2 |

`activateWithOptions:` was chosen: it works on macOS 13 too (Chatmon's minimum), from source as well as bundled, and
needs no bundle path. One more thing showed in the screenshots: an active accessory app leaves the menu bar showing
the previous app's menus. So the menu bar is no sign of which app is active
([not active](activation-study-2/screen-bundle-none-1.png), [active](activation-study-2/screen-bundle-options-1.png)).

## VoiceOver with the fixes

Run 43769638917, job `voiceover`, on macOS 26.7.2: [voiceover-verification](voiceover-verification). Chatmon ran from
source (traced) and as the installed Chatmon.app built from the same fixed tree. After each phrase VoiceOver was left
alone for 8 s.

| Case | From source | Chatmon.app |
|---|---|---|
| G, the greeting | **said** 5.3 s after start: `Hi, I'm Chatmon! Click me to ask anything.` | **said** 4.9 s after |
| A1, in front (the shortcut), `chatmon say` | **said** 0.15 s after: `Chatmon. Probe source A1, said while Chatmon is in front.` | **said** 0.19 s after |
| A2, `version` typed in the ask box, Return | **said** 0.77 s after: `I'm Chatmon 0.10.0.` (the field had the keyboard: AXTextArea) | **said** 0.71 s after |
| B1, a message held, back by the shortcut | held, then **said** 2.65 s after: `Chatmon. Probe source B1, held while Chatmon is behind.` | — |
| B3, a message held, back by Cmd-Tab (System Events) | held, then **said** 2.62 s after | held, then **said** 2.58 s after |
| C1, an agent's alert held, back by Cmd-Tab | held, then **said** 2.77 s after: `Claude needs you. Probe source C1, waiting for your approval. To answer, type “OK” in the chat.` | held, then **said** 2.77 s after |
| C2, an alert held, back by the shortcut | held, then **said** 2.57 s after | — |
| D1, a message held, then **`chatmon ask` from a script** | Chatmon active (AppKit); held, then **said** 2.83 s after | Chatmon active; held, then **said** 2.75 s after |
| D2, then `version` typed | **said** 0.69 s after: `I'm Chatmon 0.10.0.` | **said** 0.73 s after |
| S1, `settings` typed: where Settings' keyboard focus lands | the tab bar (`QTabBar`, AXRadioButton), not a label | — |

Each held case was silent while Chatmon was behind (`held_while_behind: true`), and was said 2.6-2.8 s after Chatmon
came forward: the 2.5 s settle, then VoiceOver. Every announcement was said through: VoiceOver's next phrase was its
own idle hint, 3.6-6.7 s later, or nothing within 8 s.

**The Chats window** (runs 43770472588 and 43770720300, source, [chats-window](chats-window)):

- How it was opened: `history` typed in the ask box opens the History menu, and its "All chats…" opens the window.
- The first run pressed Down twice. A native menu stops on its dimmed "No saved chats yet", so the Return closed the
  menu instead.
- The second run pressed Down three times. Focus landed on the search field (`QLineEdit` "Search your chats",
  AXTextField), 2 of 2.

So with the ask box fixed, none of the three windows puts the keyboard on a label.

## Windows with the fix

Run 43769638917, job `windows`, on a GitHub `windows-latest` runner: Windows Server 2025, 10.0.26100.33674
([windows-verification](windows-verification)). A fresh runner is in quiet time (state 6) for the first hour after
logon, and that hides the state this needs, so the job waited until Windows said 5 (23:29:25 UTC,
[wait-quns.log](windows-verification/wait-quns.log)). testpc2 was claimed by S.A.K. (below).

**Root cause, measured.** Chatmon ran for 25 s, as shipped (65ed989) and fixed in turn. Windows'
`SHQueryUserNotificationState` was read every second ([quns-summary.txt](windows-verification/quns-summary.txt)):

| Run | Before Chatmon | While it runs | After |
|---|---|---|---|
| shipped-1 | 5 (10 of 10) | **2, busy**: 22 of 25 (the first three said 5) | 5 |
| fixed-1 | 5 | **5**: 25 of 25 | 5 |
| shipped-2 | 5 | **2, busy**: 25 of 25 | 5 |
| fixed-2 | 5 | **5**: 25 of 25 | 5 |

testpc2's earlier readings (Windows 11 25H2) matched the shipped rows: 5 before, 2 for 24 of 25 samples, 5 after. The
hypothesis runs that couldn't settle it (the 1-px inset, and `MarkFullscreenWindow(FALSE)`, which the runner's quiet
time hid) weren't needed.

**A real full-screen app still holds the bubbles**, fixed build ([fullscreen](windows-verification/fullscreen)):

- Another process showed a full-screen window in front, and Windows went from 5 to 2 within a second.
- `chatmon say` during that time was queued with the quiet hold on (`passes: false`).
- The window closed, Windows went back to 5, and the bubble was shown.
- Result: `{'held_while_full_screen': True, 'shown_after_it_closed': True}`.

**NVDA 2026.3.1** (NV Access's own installer, SHA-256 checked, made a portable copy), fixed build; its log's `Speaking`
lines ([nvda](windows-verification/nvda)):

| Case | Chatmon's route | NVDA said |
|---|---|---|
| G, the greeting (Chatmon starts behind) | notification | `New notification from Chatmon, Hi, I'm Chatmon!, Hi, I'm Chatmon! Click me to ask anything... 1 of 1` |
| A1, in front (`chatmon ask`, then `chatmon say`) | UI Automation | `Chatmon. Probe one: the build finished while Chatmon was in front.` (0.32 s after) |
| A2, `note: water the ferns` typed, Enter | UI Automation | `Noted (note 1). delete note 1 takes it back.` |
| B, behind (File Explorer in front), `chatmon say` | notification | `New notification from Chatmon, Chatmon, Chatmon. Probe two: the tests passed while Chatmon was behind... 1 of 1` |
| C, behind, an agent's needs-you alert | notification | `New notification from Chatmon, Claude needs you, Claude needs you. Probe three: Claude is waiting for your approval. To answer, type “OK” in the chat... . Actions. 1 of 1` |

Before the fix, B was never shown and C's toast was never read, on the runner and on testpc2 (../README.md). NVDA
reports a toast as its banner appears ("New notification from …"), so these lines are the banners. The probe's own
banner check looked for Windows 11's "New notification" window and found none on Windows Server 2025, which names it
otherwise: NVDA's words are the evidence there.

## For the coordinator: changelog and README lines (not edited here)

`chatmon/changelog.md`, 0.10.0, under Changes, after the "Screen readers" line:

- **VoiceOver says what Chatmon held back, and its greeting, a moment after you come to Chatmon** (it used to lose them
  as Chatmon came forward), and typing in the ask box works with VoiceOver on.
- **Windows shows notifications while Chatmon runs**: its overlay no longer looks like a full-screen app to Windows,
  which hid every app's notification banners and held Chatmon's own bubbles back.
- **`chatmon ask` brings Chatmon to the front with the keyboard on macOS 14 and later**, from a script or a launcher
  too.

`README.md`, the Accessibility paragraph: "by VoiceOver when you come back to Chatmon" becomes "by VoiceOver a moment
after you come back to Chatmon".

## Runs

| Run | Commit on the probe branch | What |
|---|---|---|
| 43766746579 | 389bc80 | **A bad commit, mine:** made without a checkout in its worktree, it held the workflow alone and so deleted every other file on that branch. It was pushed at 21:59:58 UTC, its run failed in 18 s, and the branch was deleted within about two minutes and made again from main. Nothing else was touched. |
| 43766879805 | d824b14 | Study 1: stopped at the `.pkg` check (the runner's `/usr/local/bin` isn't root's alone, so the installer rightly adds no `chatmon` command) |
| 43767139778 | 805bc78 | Study 1: guidepup's setup failed ("Not authorized to send Apple events to System Events", turning on Do Not Disturb) |
| 43767504101 | 94f9dd1 | Study 1: failed the same way, then passed on its second attempt (results above) |
| 43767937946 | e8dc7ba | Windows runner's notification state: 6 (quiet time) throughout, with and without each hypothesis ([windows-runner-quiet-time](windows-runner-quiet-time)) |
| 43768643364 | 0c106e3 | Study 2 |
| 43769638917 | 4d6dc58 | Verification: `voiceover` and `windows` jobs |
| 43770472588 | 7fe2c7e | Chats window, two Downs (the menu's dimmed item stopped it) |
| 43770720300 | c60f0fd | Chats window, three Downs |

Each run's workflow is in [workflows](workflows), and the probe scripts are in [scripts](scripts) (`.py.txt`, so the
repo's linters skip copies kept as they ran). [screenshots-in-artifacts.txt](screenshots-in-artifacts.txt) lists the
screenshots left in the runs' artifacts.

**testpc2 wasn't used for this round.** It restarted at 14:08 PST for S.A.K.'s final Partition Manager certification,
which claims its `console`, `reboot` and both test drives until 19:30. Chatmon's queued deletion of `W:\chatmon-sr` ran
at that restart. The only thing done there was reading the claims; one small folder made for that was removed at once.
The Windows checks ran on the GitHub runner instead, after its first-hour quiet time.
