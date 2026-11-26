# Security and performance audit, 2026-11-26

This follow-up audit starts from `02de8ed125781d93b44b9cb8035bcafbf7ba326e`, with a clean working tree. It covers
the 70 runtime Python modules, packaging entry points, CI workflows, five dependency locks and the checked-out
branch's reachable history. Historical milestone receipts remain unchanged. This is a code and local runtime
audit, not a claim that all possible vulnerabilities, leaks or performance problems have been eliminated.

## Findings and fixes

The existing implementations were traced through their consumers before changes. All fixes extend those paths;
no runtime dependency or alternative transport, persistence layer, UI framework or test harness was added.

| ID | Finding | Change and verification |
|---|---|---|
| SP-01 | High: the 32 MiB reply limit covered buffered HTTP responses, but streamed events, model discovery and command output could grow without it. | `Asker` counts received bytes before retaining or parsing them. stdout and stderr share a budget; answer files use a bounded read. Qt's unread network buffer is capped at 64 KiB. Real local HTTP/process regressions cover every transport. |
| SP-02 | High: command-line errors could display a configured key even though API errors were scrubbed. | Command errors use the existing scrubber before display, and recognizable provider key shapes also pass through the log's existing redactor. Diagnostic text is capped after redaction. |
| SP-03 | Medium: each opened or searched chat stayed in the full-conversation cache indefinitely. | LRU retention is limited to eight conversations and 8 MiB of serialized file sizes combined. A larger chat is returned without a cached duplicate. Listing retention is limited to 2,000 metadata records. These are retention budgets, not exact Python heap limits. |
| SP-04 | Medium: deleting or clearing chats left cached private text alive. A missing file also left its old cache entry. | Save, delete, clear and missing-file paths invalidate their cache entries. Regression tests inspect retention and independent returned copies. This releases references; it is not secure erasure of Python or OS memory. |
| SP-05 | Medium: completed or cancelled Settings tests remained children of the Companion, retaining their Asker, network manager and key-bearing brain. | All four disposal paths call `deleteLater()`. Tests process deferred deletion and verify no `BrainTest` children remain after success or failure. |
| SP-06 | Medium: cancelling from a partial-answer callback still emitted subsequent pieces already parsed from the same chunk. | A cancellation generation guards emission and completion. A real HTTP test cancels on the first piece of a coalesced stream. |
| SP-07 | Medium: full-text search read all conversations synchronously in one UI callback. It also built a concatenated copy of each entire conversation. | Search yields to Qt after eight reads, cancels old work when the query changes or the window hides, and matches messages individually. Existing translated controls and keyboard behavior are retained. |
| SP-08 | Medium: each fragment recopied and rescanned an unfinished stream line, producing quadratic work. | A bytearray and scan offset process only new bytes; fragmented UTF-8, CRLF and final unterminated events remain covered. |
| SP-09 | Low: unused helpers remained after previous refactors. | Removed `attachments.mentioned`, `settings.private`, `Style.entry_colour` and `BubbleArt.minimum`. Whole-repository caller searches preceded removal. `Style.text_colours` was retained because `art/tools/bubble-preview.py` uses it. Qt overrides, native callbacks and test/platform interfaces were retained. |
| SP-10 | High: a provider or command could echo a private question or attachment in its error, which was then logged even after key redaction. | Failure logging retains only the configured brain name and a three-digit HTTP status. Detailed errors remain visible in the ask box. A real provider regression verifies reflected private text is absent from the log. |

Completed HTTP buffers and the model-discovery continuation are also released instead of holding the last
response, prompt, history and attachments until the next question.

The user's follow-up about the number beside the companion is covered by
[NOTIFICATIONS.md](NOTIFICATIONS.md). Agent alerts now have Mark as read, closing the latest alert acknowledges
it, and the clickable badge opens per-agent and bulk reset controls. Reading preserves the real waiting state;
manual reset recovers from missing terminal hooks. Fresh requests still notify, old actions cannot read newer
requests, and reminders retain Done/Snooze. Agent-menu updates avoid refreshing unrelated chat listings.

## Performance observations

Windows, Python 3.14.10, PyQt 6.11.0 / Qt 6.11.2, same machine and workload before and after:

| Workload | Before | After |
|---|---:|---:|
| Unfinished 4 MiB line in 1,024 chunks, median of three runs | 1.033828 s | 0.006958 s |
| 50 saved/loaded chats with 128 KiB questions: cached conversations | 50 | 8 |
| Serialized file sizes retained in that cache | 6,570,156 bytes | 1,051,231 bytes |
| Cached conversations after clearing history | 50 | 0 |

The parser result is about 149 times faster for this adversarial fragmented-input workload. A later concurrent
verification run measured 0.012780 s. Neither number measures normal provider latency, rendering speed, overall
application CPU use or total RSS. `python tests/benchmark_stream.py` repeats the parser workload. Search now
returns to the event loop between batches; an individual large or slow file can still delay its batch.

## Verification

Baseline: **1,290 passed, 228 skipped**, 223.43 s. Existing Ruff and Windows mypy checks passed. The first new
targeted run reproduced **13 failures** before the fixes; the coalesced-cancellation and search-yield tests each
also failed against the old behavior. A broader intermediate run passed **191 tests**.

The full Windows suite passed **1,312 tests, 228 skipped**, in 234.38 s after the notification implementation.
The final menu-refresh optimization passed **223 Windows tests, five skipped**. Canonical LF input
normalization was followed by all six notification acceptance cases and all 14 mutation drills. Linux's full audit run passed
**1,407 tests, 127 skipped**, in 765.96 s, including real KWin, Hyprland and sway runs. That full run preceded the
notification follow-up; **289 Linux tests passed, three skipped** for the follow-up's app, stage, menus,
overlay/Wayland and translation checks, and the six acceptance cases were rechecked on the final source.
An earlier Windows run caught the moved error message's stale translation-catalog order; it was regenerated.

Standalone Windows branch coverage is **76.2%**, so `coverage report` exits 2 against the **84% combined-OS**
floor. The threshold was retained. Hosted CI checks the combined Linux/Windows/macOS figure; its result is
reported in the delivery pull request's checks. These local numbers do not replace the combined report.
Configured mypy checks pass for all three platforms. Issue #23 later aligned the Ruff lock with local 0.17.4.

Fifteen maintained mutation drills use green/red/restored-green checks in the existing isolated-copy harness. They
disable the output budget, remove command-error redaction, bypass cache eviction, omit cache clearing, omit
Settings-test disposal, ignore cancellation generations, remove search batching and log private provider errors. Each defective child run
exits 1 with the intended assertion; exact source-byte restoration is checked before the final green run.
The notification drills break acknowledgment, local status reset, badge pointer input, native/overlay keyboard
actions, old-action version guards, close-to-read behavior and distinct-payload handling. Results are kept with
the notification plan. The initial eight audit drills and six notification drills were also exercised on Linux
during this session; a seventh notification drill now protects distinct payloads.

```sh
python -m pytest -q
python -m coverage run -m pytest -q
python -m coverage report
ruff check .
mypy --platform win32
mypy --platform linux
mypy --platform darwin
python tests/drills/run.py tests/drills/security-performance.json
python tests/benchmark_stream.py
python -m pip wheel --no-deps --wheel-dir /path/to/temporary/wheels .
```

The wheel builds successfully with build isolation. A trial without isolation could not import setuptools in
the existing development venv; the standard isolated build passed without changing installed runtime packages.
Workflow syntax passes actionlint 1.7.12 (`-shellcheck=''` locally because shellcheck is absent on Windows).
The initial zizmor 1.25.2 check reported no unsuppressed findings and 16 suppressions. After the pin refresh and
new CodeQL workflow, locked zizmor 1.32.0 also passed, reporting 17 suppressions. CI still runs shellcheck.

## Security scans and triage

| Check | Observation |
|---|---|
| Gitleaks 8.30.1, `git --redact` | 331 commits, about 99 MB scanned in a non-shallow checkout. 38 detections trace to synthetic test credentials, published Ed25519 fixture material and their archived mutation logs. No confirmed live secret was found. No history was rewritten and no broad ignore was added. |
| pip-audit 2.10.1 | All five `packaging/requirements*.txt` locks checked with `--disable-pip --no-deps`; zero known vulnerabilities among applicable Windows dependencies. |
| OSV-Scanner 2.6.0 | All five locks, 89 package occurrences including cross-platform entries; zero reported vulnerabilities. |
| Bandit 1.9.2 | 14 low-severity observations: subprocess imports/calls, animation randomness, XML construction and an empty token default. No high/medium findings. Argument arrays, an explicitly chosen login shell, generated toast XML and non-security randomness explain these observations. |
| Semgrep 1.180.0, `p/python` | 151 rules on 78 Python targets; four findings. Three recommend broadening private-directory 0700 permissions to 0644 and are false positives. The fourth is the explicitly selected macOS login shell with a fixed command, passed as an argument array; no shell-source interpolation of external input occurs. Permissions were kept private. |
| Dependency use | PyQt6 is used throughout; psutil is an optional platform/battery fallback. No unused runtime dependency was identified. `pip check` passes. |

Semgrep's `auto` configuration rejected metrics-disabled mode; the explicit `p/python` ruleset ran successfully
with metrics disabled. Scanner rules were fetched at audit time, not vendored or added as a pinned CI gate.
Gitleaks and SAST findings above are triaged results, not zero raw findings. Network vulnerability databases can
change; rerun before release. Redacted scanner output and local verification logs were kept under
`%TEMP%/chatmon-audit-20261126/` during this session.

## Quality coverage and remaining work

| Area | Status and limit |
|---|---|
| Formatting | Existing layout retained, as `pyproject.toml` explicitly requires. No repository-wide reformat. Source whitespace checks pass; preserved tool output retains its original CRLF and whitespace. |
| Lint | Existing security, performance and correctness rules pass. Exploratory `--select ALL` reported 3,865 diagnostics, mostly documentation/annotation/style rules; this audit does not silently enable incompatible rules or rewrite the entire app. |
| Types | Configured checks pass for all three platforms. Exploratory `--check-untyped-defs` found 45 pre-existing errors in `bubble.py`, `winuia.py` and two portal callbacks in `app.py`, mostly optional Qt return types and constructor-stub limitations. Full strict typing remains follow-up work. |
| Dead code | Four verified unused helpers removed. Vulture's three 100%-confidence observations are required redirect/native callback arguments; lower-confidence Qt, ctypes and platform/test interfaces need caller review, not blanket deletion. No unused runtime dependency found. |
| Constants and legacy code | Resource budgets have names. No blanket extraction of idiomatic literals or suppression of type/security checks. Whole-tree absence of magic values, commented-out code and silent fallback behavior is not certified. |
| Secret/dependency checks | Completed with the explicit findings and scope above. Locks and hash-checked CI installs retained. |
| CI | Existing SHA pins, permissions, timeouts and locked installs retained. New deterministic drills run on Python 3.14 legs and propagate failure directly. Hosted follow-up and scan configuration are recorded below. |
| Sanitizers | No owned C/C++/Rust runtime source to instrument; Qt and OS libraries are external. Python tests treat ResourceWarning as an error. No native sanitizer claim. |
| Coverage | Branch coverage and the existing combined-OS 84% gate retained. Local coverage results and platform gaps are recorded with the final verification below. |
| Pre-commit | No hook installed into the user's Git configuration; existing CI remains the enforcement path. |
| Build/docs | Wheel build, contributor commands for changed behavior, README and shipped changelog updated. Installer signing, publication, remote update installation and every historical README command were not rerun. |

Before release, review the delivery pull request's hosted CI, packaging and CodeQL results. Large real chat
collections on slow storage and the remaining strict-typing work are further maintenance tasks. This audit's
measurements establish specific improvements, not a universal performance or security guarantee.

## Repository follow-up

The first [hosted run](https://github.com/RandyNorthrup/chatmon/actions/runs/45864669735) passed 17 jobs, including
macOS's real window-server tests, and exposed one Windows/Python 3.11 failure; combined coverage was skipped
because of that failure. Consecutive hook events can have the same coarse clock value on that runtime, so
timestamps were replaced with monotonic event revisions for old-action guards. Frozen-clock regressions now
cover both read and reset actions. Duplicate suppression also distinguishes different message payloads without
retaining an otherwise hidden reply. Fresh local verification passed all seven notification acceptance cases
and the maintained mutation drills; the full hosted matrix is rerun through the delivery pull request.

[Issue #23](https://github.com/RandyNorthrup/chatmon/issues/23) was implemented with its exact cutoff,
`2026-11-09T06:54:00Z`, using uv 0.13.6: coverage 7.17.2, hypothesis 6.170.15, Nuitka 4.3.5, Ruff 0.17.4,
uv 0.13.7 and zizmor 1.32.0, plus mypy-extensions 1.2.0. Universal markers and hashes were retained, and the
subsequent pins report found nothing left to move at that cutoff. Requirements, pins and packaging tests passed;
the refreshed locks also passed pip-audit and OSV checks. Qt and pytest stayed on their existing release lines.

GitHub's provider secret scanning, push protection, Dependabot alerts and security updates were confirmed
enabled. The new [CodeQL workflow](../../.github/workflows/codeql.yml) uses the `security-and-quality` suite for
Python and Actions, with a mature pinned action, least-privilege permissions and weekly/PR/main triggers.
GitHub's separate paid Code Quality setup endpoint returned unavailable (404); this public repository uses
the free CodeQL suite plus its existing required quality gates. Additional non-provider/validity settings
remain disabled and are not claimed as enabled.

Branch cleanup removed 31 merged local branches and three merged remote branches. A further patch-equivalent
local Windows branch was removed after preserving its exact tip as `archive/windows-stage-fixes-20261126`.
Only main and the active delivery branch were retained during verification. Automatic deletion of merged
branches is now enabled; the delivery branch is removed after integration.

The application matrix subsequently passed all 19 checks with **86.7% combined coverage**. CodeQL's first run
found one import-cycle quality note; shared source labels, clipboard prompts and matching-style metadata were
moved out of the controller to their existing owning modules. Public behavior and translations are preserved.

Package CI also exposed stale test assumptions: the published 0.10.0 helper requires signed-list arguments,
while the upgrade smoke test still passed a bare checksum. The existing container test harness now supports
the real previous package with an ephemeral test trust key. macOS smoke tests establish a root-owned PATH
fixture while retaining the installer's unsafe-prefix refusal tests. Version **0.10.1** is prepared so upgrade
tests exercise a genuinely newer package; the published 0.10.0 changelog is preserved. No release tag is created.

Automatic approval review blocked recursive cleanup of the generated `build/` and `chatmon.egg-info/` folders,
returning only "blocked by policy". Both remain ignored. No permission escalation was attempted.
