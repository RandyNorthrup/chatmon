# Real screen readers and Chatmon's announcements, before v0.10.0 (2026-11-15)

OUTCOME.md's gap for a person: nobody had heard VoiceOver or Narrator speak Chatmon's announcements. This probe ran
Chatmon 0.10.0 from source at **65ed989** (PR #18's merge) with real screen readers, made it announce things the ways a
person meets them, and kept what each reader said as text. Nothing in Chatmon was changed. A shim
([run_chatmon.py](voiceover/scripts/run_chatmon.py.txt)) starts Chatmon as `python -m chatmon` does, and wraps
`a11y.announce`, `a11y.reader`, VoiceOver's queue, `winuia.say`, `wintoast.show` and the message queue to log what
Chatmon handed the reader. The wrappers don't change what those functions do. Hypotheses tested on the way are labelled
**HYPOTHESIS**: the shim applies them only when told to, and only in their own passes.

**Short version.**

- **VoiceOver** speaks an announcement at once while Chatmon is in front.
- **VoiceOver** drops every held announcement Chatmon posts the moment it comes back to the front, and drops the startup
  greeting. With VoiceOver on, typing in the ask box goes nowhere.
- **NVDA** (a fallback for Narrator; see below) speaks both in-front announcements.
- **On Windows**, Chatmon's own full-screen stage makes Windows report "busy", which holds Chatmon's background bubbles
  and suppresses the notification route, so nothing is read while Chatmon is behind.
- **Narrator:** the owner heard it speaking, but its words could not be captured as text.

There are two proposed diffs, [proposed-fix-voiceover.diff](proposed-fix-voiceover.diff) and
[proposed-fix-windows-quiet.diff](proposed-fix-windows-quiet.diff). Neither is committed to Chatmon. Both apply to
65ed989.

**Later the same day, all four problems were fixed** on `wave5/screen-readers` and checked again with the real readers:
see [fixes/README.md](fixes/README.md). The VoiceOver diff went in as proposed; the Windows one was replaced by a fix of
the root cause (the stage is marked `NonRudeHWND`), and two statements below turned out wrong (marked where they stand).

## Results

"Heard" means the reader started speaking that text: VoiceOver's `content of last phrase` or NVDA's log `Speaking`
line. Where VoiceOver was then left alone for 8 s (round 4 onwards), the next phrase it started of its own accord is
given. A phrase that comes later than the words take to say means VoiceOver said them through.

### VoiceOver, macOS 26.7.2 (25G332), GitHub `macos-latest` (arm64)

Chatmon as shipped:

| Case | How it was made to happen | Result | Spoken text (VoiceOver's last phrase) |
|---|---|---|---|
| A1, in front | Ask box open (the shortcut, Cmd+Shift+Space, or System Events), then `chatmon say` | **Heard, 3 of 3** (rounds 1, 2, 4), 0.24-0.46 s after | `Chatmon. Probe A1, said while Chatmon is in front.` (round 4: nothing else for 8 s) |
| G, startup greeting | Chatmon started, active as launched | **Not heard, 4 of 4** (rounds 1-4) | VoiceOver said `Python is not responding`, `Python Chatmon dialog`, `In Chatmon dialog content is empty` instead |
| A2, a typed command | Shortcut, `version` typed (System Events), Return | **Never reached Chatmon, 4 of 4** (rounds 1-4): see problem 2 | Nothing; the field stayed empty |
| Held while behind | `chatmon say` or `chatmon notify needs-you` with Finder in front | **Held, every time** (B, B1-B3, C, C1, C2): no phrase while behind | (none, as designed) |
| B1, say held, back by the shortcut | Then Cmd+Shift+Space | **Not heard, 0 of 2** (rounds 2, 3) | VoiceOver spoke the ask box (`Python dialog Ask Chatmon Enter to ask ...`) instead |
| B3, say held, back by System Events | Then frontmost, as Cmd-Tab or the Dock (no ask box) | **Not heard, 0 of 2** | `Python Chatmon dialog`, `In Chatmon dialog content is empty` |
| C, C1, a needs-you alert held, back by System Events | Important, with its OK button | **Not heard, 0 of 3** (rounds 1, 2, 3) | Same as B3 |
| C2, alert held, back by the shortcut | | **Not heard, 0 of 2** | The ask box's description |
| B (round 1), B2+SE (round 2): held, the ask box already open and VoiceOver on it, then Chatmon made active | `chatmon ask` (didn't activate: see problem 4), then System Events | **Heard, 2 of 2** | `Chatmon. Probe B, held while Chatmon is behind.` 0.4 s after activation; `Chatmon. Probe B2, held while Chatmon is behind.` 0.2 s after |

HYPOTHESIS: held announcements, and anything said in the first moment after Chatmon becomes active (or starts active),
posted N ms after activation instead of at once:

| Settle | Cases | Result |
|---|---|---|
| 1000 ms (round 2) | G, B3, C1, C2 | G started, but VoiceOver's own `In Chatmon dialog content is empty` followed 0.22 s later (cut off); B3, C1, C2 **not heard** |
| 2500 ms (rounds 3 and 4) | G, B1, B3, C1, C2 | **Heard, 10 of 10.** In round 4 VoiceOver's next phrase came 4.75-7.22 s later (its own idle hint), or not within 8 s: said through. 16-word alert: `Claude needs you. Probe S25-C1, waiting for your approval. To answer, type “OK” in the chat.` |
| 4000 ms (round 3) | G, B1, B3, C1, C2 | **Heard, 5 of 5** |
| 2500 ms, and the title's focus proxy (round 5, "proposed") | G, A2, A1, B1, A2 again, C1 | **Heard, 6 of 6**: `Hi, I'm Chatmon! Click me to ask anything.`; `I'm Chatmon 0.10.0.` twice (the typed `version` reached the field: AXTextArea value `version`); `Chatmon. Probe A1, ...`; `Chatmon. Probe P-B1, held while Chatmon is behind.`; `Claude needs you. Probe P-C1, waiting for your approval. To answer, type “OK” in the chat.` |

### NVDA 2026.3.1 (NV Access's portable copy), and Narrator

| Reader, machine | A1: in front, `chatmon say` | A2: in front, `note: water the ferns` typed, Enter | B: behind, `chatmon say` | C: behind, needs-you alert |
|---|---|---|---|---|
| **NVDA**, testpc2, Windows 11 25H2 (26200.9711), real console; synth set to *silence* (see below) | **Heard** 0.45 s after, through UI Automation: `Speaking [LangChangeCommand ('en'), 'Chatmon. Probe one: the build finished while Chatmon was in front.']` | **Heard**, UI Automation: `Speaking [LangChangeCommand ('en'), 'Noted (note 2). delete note 2 takes it back.']` | **Not said: Chatmon never showed it.** Its queue held it for "quiet", from Windows' QUNS_BUSY (problem 3) | **Not heard.** Chatmon sent the toast (its notification route); NVDA said nothing, most likely because Windows shows no banner while busy (problem 3) |
| **NVDA**, GitHub `windows-latest`, Windows Server 2025 (26100.33674), synth OneCore (no audio device) | **Heard**, UI Automation: `Speaking [LangChangeCommand ('en_US'), 'Chatmon. Probe one: the build finished while Chatmon was in front.']` | **Heard**: `Speaking [LangChangeCommand ('en_US'), 'Noted (note 1). delete note 1 takes it back.']` | Not shown (no announce: held, as on testpc2; the runner had no queue trace) | Toast sent; NVDA said nothing |
| **Narrator**, testpc2 | Chatmon in front raised the UI Automation notification (13:16:15.075, `raised: true`). **The owner heard Narrator speaking** in this window (below). **No text captured** | Raised at 13:16:45.488. No text captured | Held (problem 3) | Toast sent. No text captured |

**This NVDA is not Narrator.** Narrator was the preferred reader, but its words couldn't be captured as text:

- **Live captions** (set up for this, and shown to caption testpc2's speakers: a SAPI test sentence came through as
  `Testing live captions on this computer. One. Two three`) captioned nothing of Narrator's speech. Its window
  still showed that test sentence after Narrator had spoken for three minutes, which the owner heard.
- **Narrator's speech recap** (Narrator key + Alt + X) opened (`NarratorSpeechRecapDialog`). From a medium-integrity UI
  Automation client only its title, `Speech recap`, could be read, through the control view, the raw view, and the
  Value and Text patterns.

So NVDA's log is the Windows transcript. NVDA ran on testpc2 with its *silence* synthesizer: the coordinator asked for no
more speech in the owner's room than the checks need. NVDA logs each `Speaking` line before handing it to any synth, so
the transcript is the same. On the runner NVDA had OneCore (and no sound device).

### The owner's own observation (heard by ear)

The coordinator relayed, at **13:18:18 PST** on 2026-11-15 (when it reached this probe), that the owner "can hear
the screen reader speaking" (taken to be testpc2's speakers: "Speakers (Realtek(R) Audio)" was its active output).

At that moment Narrator was on, on testpc2's console, run `narrator2`:

- Turned on at 13:15:24 with Ctrl+Win+Enter, and off at 13:18:40.
- Chatmon had it raise UI Automation notifications at **13:16:15.075**, `Chatmon. Probe one: the build finished while
  Chatmon was in front.`, and at **13:16:45.488**, `Noted (note 1). delete note 1 takes it back.`
- Chatmon was in front for both ([runs/narrator2/chatmon-trace.jsonl](testpc2/runs/narrator2/chatmon-trace.jsonl)).
- Narrator also spoke its own start-up, its "Narrator updates" window, the ask box, and the typed text, which it echoed.
- At 13:18:00 Chatmon's needs-you toast went out.

Before Narrator, at 13:13:40, the speakers played one SAPI sentence for the Live captions check. That wasn't a screen
reader. The logs can't say which words the owner heard. This sits beside the captured text and doesn't replace it.

Every sound this probe played on testpc2:

| When | What |
|---|---|
| 13:13:40 | SAPI test sentence |
| 13:15:24-13:18:40 | Narrator |
| 13:36:00-13:38:15 | Narrator, speech recap attempt 1 (typing echo and hints off) |
| 13:38:56-13:39:52 | Narrator, attempt 2 |

NVDA (13:23:18-13:25:35) was silent.

## Product problems found

### 1. VoiceOver: held announcements, and the startup greeting, are dropped (macOS)

**Behavior:** `VoiceOver.state_changed` posts the held text the instant Qt says ApplicationActive. VoiceOver is then
moving to Chatmon and announcing its newly focused window (`Python Chatmon dialog`, then `In Chatmon dialog content is
empty`, or the ask box's description). It speaks the focus and never the announcement: 0 of 9 held cases across rounds
1-3. The same happens to the greeting posted as Chatmon starts (0 of 4).

**Evidence:** [voiceover/round2](voiceover/round2), [round3](voiceover/round3) and [round4](voiceover/round4).
`chatmon-trace-shipped.jsonl` shows `voiceover-post` at the activation instant, and `voiceover-phrases.jsonl` shows
what VoiceOver said instead. The only held cases heard were those where VoiceOver was already sitting on the open ask
box when Chatmon became active, so it had no window to announce.

**Likely cause:** VoiceOver drops an announcement that arrives while it moves to an app that has just become active,
whatever the priority (the alerts were posted at High, 90).

**Proposed fix** (in [proposed-fix-voiceover.diff](proposed-fix-voiceover.diff), `chatmon/a11y.py`):

- Hold what's said in the first `SETTLE_MS = 2500` after Chatmon becomes active (or is made active), and post the
  held text then, from a single-shot `QTimer`.
- If Chatmon goes behind meanwhile, it stays held.

Tested on real VoiceOver as the hypothesis: 2.5 s 10 of 10 (rounds 3 and 4), plus 3 of 3 (G, B1, C1) in round 5;
4 s 5 of 5; 1 s 0 of 3 held cases, and the greeting cut off after 0.22 s.
Unit tests: `test_voiceover_holds_announcements_until_chatmon_is_in_front` (updated) and the new
`test_voiceover_waits_after_chatmon_comes_in_front`. They are red on 65ed989, green with the change; ruff and mypy
(darwin, win32, linux) are clean.

### 2. VoiceOver: typing in the ask box goes nowhere (macOS)

**Behavior:** the ask box opens with Qt's keyboard focus on its entry. About 0.2 s after Chatmon becomes active,
VoiceOver lands on the box's first element, the title label. With "keyboard focus follows the VoiceOver cursor" (on by
default), Qt's focus moves to that `QLabel 'title'`. AXFocusedUIElement then reports `AXStaticText value: Ask Chatmon`,
and typed text (System Events, both `keystroke` and key codes) never reaches the field.

**Control:** with VoiceOver off, the same keystrokes landed (`AXTextArea ... value: version`).

**Evidence:**

- [round4 chatmon-trace-shipped.jsonl](voiceover/round4/artifact/chatmon-trace-shipped.jsonl) has the `focus` events.
- [round3 results.json](voiceover/round3/artifact/results.json) has the focused elements, and the `no-voiceover`
  case is the control.
- Screenshots: [VoiceOver on, field empty](voiceover/round3/artifact/screen-shipped-A2-typed.png) and
  [VoiceOver off, `version` typed](voiceover/round3/artifact/screen-no-voiceover-typed.png).

**Proposed fix** (same diff, `chatmon/bubble.py`): `self.title.setFocusProxy(self.entry)`.

- Tested on real VoiceOver as the hypothesis (round 5): the focus stayed on the entry, `version` landed, and
  `I'm Chatmon 0.10.0.` was spoken, 2 of 2
  ([screenshot](voiceover/round5/artifact/screen-proposed-A2-typed.png)).
- New test `test_a_screen_reader_on_the_title_leaves_the_keyboard_in_the_field`: red on 65ed989 (focus on the
  QLabel, as on the Mac), green with the change.

### 3. Windows: Chatmon's own stage makes Windows report "busy" (QUNS_BUSY) for as long as it runs

**Behavior:** testpc2, Windows 11 25H2, silent checks with no screen reader
([quns1](testpc2/runs/quns1/quns.log), [quns3](testpc2/logs/quns3.txt)). `SHQueryUserNotificationState` said
5 (accepts notifications) before Chatmon started, 2 (busy) from its second second until it quit (24 of the 25
samples while it ran, in both runs; the first still said 5), and 5 again after. Without Chatmon, 40 samples in a row said 5 ([noise1](testpc2/logs/noise1.txt)).

The stage is `TOPMOST TRANSPARENT LAYERED NOACTIVATE TOOLWINDOW`, `[0, 0, 1600, 900]`: the whole primary monitor,
taskbar included. `presence._win_quiet` maps 2 to "a full-screen app".

Consequences:

- **(a)** Chatmon holds every plain bubble that comes on its own (a hook's `chatmon say`, an agent's
  done/success/error, heads-ups) unless the ask box or menu is open. So nothing is shown or announced: case B on
  testpc2 and on the runner. The queue trace in [runs/nvda1](testpc2/runs/nvda1/chatmon-trace.jsonl) has
  `queue-hold quiet`, `quiet state 2` and `queue-add ... passes: false`.
- **(b)** Windows itself treats the desktop as busy, so toast banners aren't shown. Chatmon's notification route for a
  reader while it's behind (and other apps' notifications) then shows nothing to read. That is consistent with C going
  unread by NVDA on both Windows machines. This is inferred from QUNS_BUSY's meaning, not observed on screen.

M7's CI finding ("on the runner the desktop reports quiet") is most likely this same cause, not the runner.
**Wrong, as measured later:** a fresh GitHub Windows runner says 6 (quiet time, the first hour after a user's first logon)
before Chatmon starts, while it runs and after, with or without the fix ([fixes/windows-runner-quiet-time](fixes/windows-runner-quiet-time)).
M7's runner quiet was that.

**Proposed fix for (a)** ([proposed-fix-windows-quiet.diff](proposed-fix-windows-quiet.diff), `chatmon/presence.py`).
**Superseded, not applied:** the root cause is fixed instead (fixes/README.md), so 2 is a real full-screen app again and
must keep holding bubbles:

- Drop 2 from `_QUNS`.
- Add `_win_full_screen_app()`: another app's window in front that fills its monitor, never Chatmon's own. `quiet()`
  on Windows now consults it.

The new tests are red on 65ed989, green with the change. ruff and mypy are clean. The presence, app smoke,
reminders, M7 and platform-events tests pass offscreen (170 passed).

This fix is not tested on a real desktop, and it doesn't fix (b). **(b) is open:** the stage must stop looking
full-screen to Windows. A stage one pixel short of the monitor (HYPOTHESIS) still gave busy 11 of 25 and 18 of 25
times, against 24-25 of 25, with stray busy readings around runs ([quns2](testpc2/runs/quns2/quns.log), quns4-6).
That's inconclusive, so no diff is proposed for it.

### 4. `chatmon ask` from a script or launcher doesn't make Chatmon active on macOS 26.7

**Behavior:** with Finder in front, `python -m chatmon ask` opened the ask box (VoiceOver even moved to it), but Qt
stayed inactive and Finder frontmost (rounds 1 and 2, three times).

Effects:

- The keyboard stays with the other app.
- VoiceOver keeps holding announcements.

Chatmon's own shortcut (Carbon hotkey, a key press) did activate it, every time in rounds 2-5.

**Likely cause:** macOS 14's cooperative `NSApp.activate()`, which `macnative.activate()` uses, is ignored when the
request doesn't come from the person's own input or from the active app yielding.

**Fixed later** (fixes/README.md): the command activates Chatmon by its process id. No diff here: the way to hand
activation over from a launcher (for example LaunchServices for the bundled app) wasn't tried
here.

## What couldn't be checked

- **Narrator's words as text.** Live captions doesn't caption Narrator, and speech recap's content isn't readable from
  a medium-integrity UI Automation client (an elevated reader wasn't tried, to keep speech in the owner's room down).
  Narrator was heard by the owner; Chatmon's trace shows what it handed Narrator.
- **Windows' behind cases on a desktop that isn't "busy".** Problem 3 blocks them.
- **macOS's own voice** (`speech_fallback = true`): the `say` command isn't VoiceOver, and its speech wasn't captured.
- **Others:**
  - A bundled Chatmon.app: this ran from source, as `Python`.
  - Other macOS versions.
  - Real hands on a keyboard: the probe used System Events and SendInput.
  - JAWS.
- **NVDA's audio on testpc2:** it used the silence synthesizer, on request.

## How it ran

### VoiceOver (and NVDA) on GitHub runners

A throwaway branch `probe/screen-readers` from 65ed989 held only `.github/workflows/probe-screen-readers.yml`.

- **Trigger:** `on: push` to that branch.
- **Permissions:** `permissions: contents: read`, `persist-credentials: false`, no secrets, a `timeout-minutes`.
- **Pins:** `guidepup/setup-action@acf1a64cc26292ebe0db6a28d1341bd1bae93c65` (0.21.0, bundling @guidepup/setup 0.23.0;
  it enables VoiceOver's AppleScript control, writes the runner's TCC grants, and turns on Do Not Disturb). checkout,
  setup-python and upload-artifact use CI's own pins.
- **Packages:** Python 3.14.10, `pip install --require-hashes -r packaging/requirements-test.txt` (PyQt6 6.11.0, Qt
  6.11.2), as CI's macOS leg.
- **VoiceOver:** started with `/System/Library/CoreServices/VoiceOver.app/Contents/MacOS/VoiceOverStarter`, and read by
  polling `osascript -e 'tell application "VoiceOver" to get content of last phrase'` about every 0.2 s (1,691 polls
  in round 2, none failed).
- **Chatmon's settings:** `name = "Chatmon"`, update checks, break reminders and system-update heads-ups off
  ([config.toml](voiceover/round1/artifact/config.toml)).
- **The branch:** five commits, five runs, then the branch was deleted (`git push origin --delete probe/screen-readers`).
  Each round's workflow file, as run, is in its folder.
- **Runs** ([runs.txt](runs.txt) has the job IDs; the artifacts are kept 30 days):

| Round | Commit | Run | What it did |
|---|---|---|---|
| 1 | 7ea5a98 | [43757787218](https://github.com/RandyNorthrup/chatmon/actions/runs/43757787218) | First pass. Its frontmost-app query was malformed (step failed; Qt's state is in the trace) |
| 2 | 35e83c9 | [43758733606](https://github.com/RandyNorthrup/chatmon/actions/runs/43758733606) | Shortcut, cases apart, settle 1000 ms |
| 3 | 9a70e6f | [43759695962](https://github.com/RandyNorthrup/chatmon/actions/runs/43759695962) | Focus checks, typing control without VoiceOver, settle 2500 and 4000 ms |
| 4 | 81e4dbd | [43760593147](https://github.com/RandyNorthrup/chatmon/actions/runs/43760593147) | 8 s of quiet after each phrase, Qt focus traced; plus the `nvda` job on `windows-latest` (it "failed" by design: exit 1 when a case isn't heard) |
| 5 | 84a64fa | [43761201497](https://github.com/RandyNorthrup/chatmon/actions/runs/43761201497) | Both proposed changes together |

The scripts the workflow embeds are in [voiceover/scripts](voiceover/scripts):

- [make_workflow.py](voiceover/scripts/make_workflow.py.txt) writes the workflow from them (`--nvda` adds the Windows job).
- [check_settle.py](voiceover/scripts/check_settle.py.txt) checks the settle hypothesis's logic offscreen.
- The NVDA runner job checked NV Access's installer against its published SHA-256 (`6F80A5B0...F052`), and
  `--create-portable-silent` made the portable copy.

Screenshots: four are kept here. The rest ([screenshots-in-artifacts.txt](screenshots-in-artifacts.txt)) are in each
run's `voiceover-transcript` artifact.

### Narrator and NVDA on testpc2

Following `C:\Users\Randy\TestLab\README.md`. Times are testpc2's (PST). Everything ran over `ssh testpc2` as
Technician; scripts went by `scp` and ran with `powershell -NoProfile -ExecutionPolicy Bypass -File`.

1. **12:24, survey** ([survey-before.log](testpc2/logs/survey-before.log)). Claims:
   - WinAppMigrator held `console` until about 13:35.
   - sak-utility-secfix holds `cpu` until 20:01.
   - The Realtek speaker was the active output. Live captions had never been set up, and NVDA wasn't installed.
2. **12:33, the drive claim** (`claim.ps1 drive 3`, [claim-drive.log](testpc2/logs/claim-drive.log)). W: was pinned
   (SAMSUNG MZVL2512HCJQ-00BH1, serial `0025_38B8_21B7_37C0.`, 512110190592 bytes, not boot) before anything was
   written.
3. **Work folder and before-state** (`setup.ps1 folder`, `setup.ps1 state before`; [state-before.log](testpc2/logs/state-before.log)).
4. **Build** (`setup.ps1 build`, [setup-build.log](testpc2/logs/setup-build.log)):
   - `git archive` of 65ed989 (`chatmon/`, `packaging/requirements*.txt`, `pyproject.toml`; SHA-256 `3F511876...AD24`).
   - A venv from C:\Python314 (3.14.10) with `requirements-test.txt --require-hashes`.
   - The build ran below normal priority, as everything did; secfix held the CPU.
5. **13:01, the console claim**, once WinAppMigrator's claim was gone (`claim.ps1 console 2`, [claim-console.log](testpc2/logs/claim-console.log)).
6. **Console jobs:** `task.ps1 run -Name <job> -ArgLine "<python args>"` ran each one in Technician's console session
   (session 1, Medium integrity), through the on-demand scheduled task `ChatmonScreenReaderProbe`. It had no trigger,
   an interactive logon and Limited run level, and ran [job.ps1](testpc2/scripts/job.ps1). Every job's output is in
   [job-logs](testpc2/job-logs).
7. **Live captions:**
   - Started, consent given (`uia_tool.py invoke LiveCaptionsDesktopWindow AgreeButton`), then
     `ContinueButton`; this installed `MicrosoftWindows.Speech.en-US.1`.
   - Checked with a SAPI sentence (`uia_tool.py captest`, job `lc11`).
8. **13:14 and 13:15, Narrator runs** `narrator1` (Narrator.exe refused CreateProcess with error 740) and `narrator2`:
   `drive_windows.py <out> <src> <shim> narrator`. Narrator was started and stopped with Ctrl+Win+Enter (SendInput).
9. **13:20-13:25, NVDA:**
   - `nvda_fetch.ps1` (`https://download.nvaccess.org/releases/2026.3.1/nvda_2026.3.1.exe`, SHA-256 matched, signature
     Valid, NV Access Limited; [nvda-fetch.log](testpc2/logs/nvda-fetch.log)).
   - `nvda_2026.3.1.exe --create-portable-silent --portable-path=W:\chatmon-sr\nvda`, with [nvda.ini](testpc2/scripts/nvda.ini).
   - Run `nvda1`: `drive_windows.py ... nvda W:\chatmon-sr\nvda\nvda.exe`, with NVDA started as
     `--log-level=12 --log-file=... --minimal` and stopped with `nvda.exe -q`.
10. **13:26-13:35, silent notification-state checks:** `quns_check.py` (plain and `inset`), `quns_noise.py`, and `uia_tool.py quiet`.
11. **13:35-13:40, Narrator speech recap:** `narrator_quiet.ps1` (echo and hints off), then `narrator_recap.py`, twice.
    Narrator didn't take Ctrl+Win+Enter after its recap dialog, so it was stopped with `narrator_stop.ps1` (13:38:15
    and 13:39:52).
12. **13:43-13:45, put back:**
    - [toast_check.py](testpc2/scripts/toast_check.py.txt): no Chatmon toasts left in Action Center.
    - [cleanup.ps1](testpc2/scripts/cleanup.ps1) ([cleanup.log](testpc2/logs/cleanup.log)). Its first run stopped early
      because its process sweep matched the ssh session's own shell; it was fixed and run again.

#### testpc2 before and after

[state-before.log](testpc2/logs/state-before.log), [state-during.log](testpc2/logs/state-during.log) (before
cleanup) and [state-after.log](testpc2/logs/state-after.log) differ only in Chatmon's claim line. That line was in
the before snapshot because it was taken after the drive claim, and it's gone now.

Put back:

- **Narrator:** its settings are back to `NoRoam\RunningState = 0` alone; `NarratorHome` was removed. It's off.
- **Absent before, removed:** `HKCU\Software\Microsoft\LiveCaptions`, `HKCU\...\Windows NT\CurrentVersion\Accessibility`
  (its ATConfig, and the empty `Configuration`), and Chatmon's `AppUserModelId` and notification-settings keys.
- **Speech platform:** three new `Speech_OneCore\Isolated` keys were removed.
- **Live captions' language pack** was removed.
- **Chatmon's `%LOCALAPPDATA%\chatmon`** was removed. `%APPDATA%\nvda` was never made.
- **The scheduled task** was unregistered.
- **Folders and claim:** `C:\Users\Technician\chatmon-sr` was removed and `C:\TESTLAB_CLAIMS\chatmon.txt` deleted.
- **Not ours, untouched:** other projects' windows and processes (S.A.K.'s fix6 build), and their claims.
- **No restart:** last boot is 2026-11-12 11:59:51 throughout.

**Left until testpc2's next restart:** `W:\chatmon-sr\nvda\lib\2026.3.1\x64\IAccessible2proxy.dll` and `ISimpleDOM.dll`.

- NVDA loaded them into explorer.exe (pid 7472, the shell). The shell wasn't restarted, because other projects'
  File Explorer windows were open in it.
- Both files, and their folders up to `W:\chatmon-sr`, are queued for deletion at the next restart
  (`MoveFileEx(..., MOVEFILE_DELAY_UNTIL_REBOOT)`; [leftover.log](testpc2/logs/leftover.log)).
- Recorded in the TestLab README's testpc2 section.

Values Narrator and the speech platform may have changed inside keys that already existed weren't recorded, so they
can't be shown to be the same. Their key lists match.

## Files

| Folder | Contents |
|---|---|
| `voiceover/roundN/` | `probe-screen-readers.yml` as run; `artifact/`: `transcript.txt` (steps and VoiceOver's phrases in order), `voiceover-phrases.jsonl`, `driver.log`, `results.json`, `chatmon-trace*.jsonl`, Chatmon's own `chatmon.log`, `environment.txt` |
| `voiceover/scripts/` | The probe's scripts (final versions; each round's as-run copy is inside its workflow file) |
| `nvda-runner/artifact/` | Round 4's `nvda` job: `nvda.log` (its `Speaking` lines), `nvda-speech.jsonl`, `transcript.txt`, `chatmon-trace.jsonl` |
| `testpc2/runs/` | `narrator1`, `narrator2` (Live captions), `nvda1`, `quns1`, `quns2`, `quns3-6`, `recap1`, `recap2`, `keys` |
| `testpc2/job-logs/` | Every console job's output and exit code |
| `testpc2/scripts/` | The scripts as they ran there; [files-on-testpc2.sha256.txt](testpc2/files-on-testpc2.sha256.txt) has their hashes there |
| `testpc2/logs/` | Survey, claims, setup, states before, during and after, NVDA's download check, cleanup, the leftover |

The run outputs change over the day: the earlier `narrator1` and `narrator2` used `drive_windows.py` before its pid fix
(the venv's `python.exe` is a launcher, so Chatmon's windows belong to a child process). That made those two runs log
"Chatmon isn't in front" while the foreground window was Chatmon's. Chatmon's own trace (`uia-in-front: true`, route
`uia`) is what counts there.
