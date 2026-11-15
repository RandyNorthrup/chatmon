"""Write docs/delivery/reports/m4b/w4d/bindings.json, for docs/delivery/reports/wave4/bind.py.

usage, from the worktree's root: python docs/delivery/reports/m4b/w4d/mkbind.py

ROADMAP.md's round-three amendment (3586a0d+wave4c) is a rule change, so every passing M4B receipt is stale. Each one
gets a W4D- receipt from its check run again on this branch's merged tree: the readiness review (w4d/readiness.md),
the Windows suite and drills (w4d/run-windows.sh), the Linux tests and drills in WSL (w4d/run-wsl.sh), and testpc2's
toast test and drills (w4d/testpc2/). A receipt covers the same criteria as the one it replaces, and a drill receipt
binds the same drill. The macOS receipts are new: the three red drills and the macOS tests, from the owner's MacBook
Pro (m4b/mac/). A drill that didn't go green, red and green stops this script.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
PLAN = "docs/delivery/m4b-hotkey-sound-toasts.md"
W = "docs/delivery/reports/m4b/w4d"
MAC = "docs/delivery/reports/m4b/mac"
VENV = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
HEAD = sys.argv[1] if len(sys.argv) > 1 else None  # the merged tree's commit, for the receipts' methods
WSL_TESTS = ["tests/test_m4b_imports.py", "tests/test_hotkey.py", "tests/test_hotkey_portal.py", "tests/test_sound.py"]
TP2 = ("testpc2's signed-in desktop, owner-approved 2026-11-15: a scheduled task with an interactive logon in Technician's "
       "console session (session 1, Medium integrity), notifications on (ToastEnabled absent, SHQueryUserNotificationState 5, "
       "Focus off: w4d/testpc2/probe.log), {head}'s files from git archive (its tree checked against the commit's, 6fa4a57f), "
       "a venv of packaging/requirements-test.txt installed with --require-hashes (Python 3.14.10, PyQt6 6.11.0, pytest 9.2.0)")
MACOS = ("the owner's MacBook Pro (macOS 15.7.9 24G830, Intel x86_64), owner-approved 2026-11-15, launched from here over ssh "
         "and run in his signed-in Aqua session by docs/delivery/reports/m1a/mac/aqua.sh (a one-shot launchd job in gui/503) "
         "with job.sh, with Homebrew's Python 3.13.7, PyQt6 6.11.0 and pytest 9.2.0 in a venv of its own (packaging/"
         "requirements-test.txt, hash-locked; m4b/mac/context-observed-aqua.txt), on {head}'s files (git archive)")
ELSEWHERE = "The command is the one run there; the receipt's environment is the plan's profile (ROADMAP: evidence from elsewhere)."
WHY = "Evidence for {head}: wave4/mac-drills with improve/assessment-fixes merged (the toast merge, cbeed17, and the quit guard, 86e84e0)."


def ledger() -> dict:
    text = (ROOT / PLAN).read_text(encoding="utf-8")
    return json.loads(re.search(r"```quality-ledger\n(.*?)\n```", text, re.S).group(1))


def drilled(results: str) -> dict:
    return {r["id"]: r for r in json.loads((ROOT / results).read_text(encoding="utf-8"))}


def red(new_id, acceptance, results, drill, artifact, where, after=""):
    record = drilled(results).get(drill)
    if record is None or record["status"] != "pass":
        raise SystemExit(f"{drill} in {results} didn't go green, red, green")
    return {"id": new_id, "kind": "red", "acceptance": acceptance, "results": results, "drill": drill, "artifact": artifact,
            "method": f"Red drill {drill} {where}: green; the defect put in, the named tests failing with pytest's tests-failed exit "
                      f"and printing what's expected ({record['observed'].strip()[:160]!r}); the file's bytes put back (checked by "
                      f"SHA-256) and green again." + (f" {after}" if after else "")}


def main() -> int:
    head = HEAD[:7] if HEAD else "the merged tree"
    L = ledger()
    receipts = []
    for old in L["evidence"]:
        if old["status"] != "pass":
            continue
        rid, acs = old["id"], old["acceptance"]
        new = "W4D-" + rid.split("-", 1)[1]
        if rid == "W4B-READY":
            receipts.append({"id": "W4D-READY", "kind": "readiness", "acceptance": acs, "artifact": f"{W}/readiness.md",
                             "method": f"Requirements review, round three, on {head} (w4d/readiness.md): M4B-00 to M4B-04 and their 22 "
                                       "criteria re-read against ASSESSMENT.md, ROADMAP.md as amended for round three and pyproject.toml; "
                                       "no conflict or gap; the four drills that needed a place to run now have one, each owner-approved."})
        elif rid == "W4C-BEH-WINDOWS":
            receipts.append({"id": new, "kind": "behavior", "acceptance": acs, "artifact": f"{W}/suite-windows.log",
                             "command": [VENV, "-m", "pytest", "-q", "-p", "no:cacheprovider"], "exit_code": 0,
                             "method": f"The whole suite on {head}'s files (the log's header has HEAD and the source digest) on this "
                                       "Windows 11 workstation (offscreen Qt, the shared venv), which runs every test these criteria's "
                                       f"earlier receipts named: {suite_counts(W + '/suite-windows.log')}, exit 0. Notifications are off for "
                                       "this user (ToastEnabled 0), so the toast tests take their declining branch, which passed. "
                                       + WHY.format(head=head)})
        elif rid == "W4C-BEH-LINUX":
            receipts.append({"id": new, "kind": "behavior", "acceptance": acs, "artifact": f"{W}/linux-tests.log",
                             "command": ["wsl.exe", "-d", "archlinux", "--", "/var/tmp/plans-venv/bin/python", "-m", "pytest", "-v",
                                         "-rA", "-p", "no:cacheprovider", *WSL_TESTS], "exit_code": 0,
                             "method": "In WSL (Arch Linux; /var/tmp/plans-venv from packaging/requirements-test.txt, PyQt6 6.11.0, Qt "
                                       f"6.11.2, pytest 9.2.0) on {head}'s files, through docs/delivery/reports/m4b/w4d/run-wsl.sh: the "
                                       "tests CI's Linux job had shown for these criteria (the imports for AC-00B, the X11 grab on its "
                                       "own Xvfb for AC-01E, the GlobalShortcuts portal on a private bus for AC-01F, the Linux players "
                                       f"for AC-02E): {suite_counts(W + '/linux-tests.log')}, exit 0, every warning an error. "
                                       + ELSEWHERE + " " + WHY.format(head=head)})
        elif rid == "W4C-BEH-TESTPC2-TOASTS":
            receipts.append({"id": new, "kind": "behavior", "acceptance": acs, "artifact": f"{W}/testpc2/plain-test.log",
                             "command": ["W:\\chatmon-m4b\\venv\\Scripts\\python.exe", "-m", "pytest", "-v", "-rA", "-p",
                                         "no:cacheprovider", "tests/test_wintoast.py"], "exit_code": 0,
                             "method": f"tests/test_wintoast.py on {TP2.format(head=head)}. The toast tests take their notifications-on "
                                       "branch: the toast is in Windows' history under its tag, gone from it after hide(), and "
                                       "Dismissed(HIDDEN_BY_CHATMON) comes back on the Qt thread as the last word: "
                                       f"{suite_counts(W + '/testpc2/plain-test.log')}, exit 0. " + ELSEWHERE + " " + WHY.format(head=head)})
        elif old["kind"] == "red":
            drill = rid.split("-RED-", 1)[1]
            if drill.startswith("D-03E-"):
                receipts.append(red(new, acs, f"{W}/testpc2/drills-results.json", drill, f"{W}/testpc2/drills.log",
                                    f"through tests/drills/run.py on {TP2.format(head=head)}, in a temporary copy of those files",
                                    ELSEWHERE))
            elif drill.startswith("D-"):
                receipts.append(red(new, acs, f"{W}/drills-results.json", drill, f"{W}/drills.log",
                                    f"through tests/drills/run.py on this Windows workstation (wave4b/drill-spec.json, all 36), in a "
                                    f"temporary copy of {head}'s files"))
            elif drill == "L-02E-linux-player":
                receipts.append(red(new, acs, f"{W}/wsl-drills-new-results.json", "W4-L-02E-linux-player", f"{W}/wsl-drills-new.log",
                                    "in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to "
                                    "tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a "
                                    f"temporary copy of {head}'s files (w4d/files.lst), from w4d/run-wsl.sh"))
            elif drill.startswith("L-"):
                receipts.append(red(new, acs, f"{W}/wsl-drills-results.json", drill, f"{W}/wsl-drills.log",
                                    "in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to "
                                    "tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a "
                                    f"temporary copy of {head}'s files (w4d/files.lst), from w4d/run-wsl.sh"))
            else:
                raise SystemExit(f"no re-run for {rid}")
        else:
            raise SystemExit(f"no re-run for {rid}")

    mac_where = f"on {MACOS.format(head=head)}, in a temporary copy of those files"
    receipts.append({"id": "MAC-BEH-MACOS", "kind": "behavior", "acceptance": ["AC-00C", "AC-01D", "AC-02F"],
                     "artifact": f"{MAC}/suite-offscreen.log",
                     "command": ["/Users/user/chatmon-drills-tmp/venv/bin/python", "-m", "pytest", "-p", "no:cacheprovider", "--deselect",
                                 "tests/test_keychain.py::test_macos_keychain_keeps_replaces_and_forgets_a_key"], "exit_code": 0,
                     "method": f"The whole suite on {MACOS.format(head=head)}, offscreen as CI's macOS job runs it "
                               f"(m4b/mac/README.md): {suite_counts(MAC + '/suite-offscreen.log')}, exit 0. It ran every macOS test of these "
                               "criteria's: all 8 of tests/test_m4b_imports.py (AC-00C); tests/test_hotkey.py's Carbon tests, registered "
                               "and heard on the application's event target, a second exclusive registration reported as a conflict, "
                               "and unregistered (AC-01D); tests/test_sound.py::test_nssound_plays_at_the_volume (AC-02F). The one test "
                               "left out writes to the owner's login keychain. tests/test_macnative.py passed on Qt's cocoa platform "
                               "too (m4b/mac/suite-macnative-cocoa.log). " + ELSEWHERE + " " + WHY.format(head=head)})
    for new_id, drill, acs in (("MAC-RED-AC-00C", "MAC-00C-linux-import-sound", ["AC-00C"]),
                               ("MAC-RED-AC-01D", "MAC-01D-conflict-unreported", ["AC-01D"]),
                               ("MAC-RED-AC-02F", "MAC-02F-volume-unset", ["AC-02F"])):
        receipts.append(red(new_id, acs, f"{MAC}/drills-results.json", drill, f"{MAC}/drills.log", mac_where,
                            "The same drill went green, red and green on 3586a0d earlier that day (m4b/mac/3586a0d/). " + ELSEWHERE))

    bindings = {
        "plan": PLAN,
        "section": f"{W}/section.md",
        "rules": {"docs/delivery/ROADMAP.md": "3586a0d+wave4c", "pyproject.toml": "3586a0d"},
        "inputs_add": [],
        "task_changes_add": {},
        "stale_reason": "Stale at wave 4's round three (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round "
                        "three (3586a0d+wave4c), and the plan's rules and narrative with it; the W4D- receipts ran its check again on "
                        f"{head}",
        "receipts": receipts,
        "tasks": {},
        "pending": [],
        "next_action": f"None for M4B: every task is verified at {head}. A merge that changes a file these receipts bind, or "
                       "ROADMAP.md, needs those checks run again: on this workstation, in WSL, on testpc2 (AC-03E) and on a Mac "
                       "(AC-00C, AC-01D, AC-02F), each as reports/m4b/w4d/ and reports/m4b/mac/ say.",
        "source_revision": HEAD,
    }
    (ROOT / W / "bindings.json").write_text(json.dumps(bindings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(receipts)} receipts")
    return 0


def suite_counts(log: str) -> str:
    text = (ROOT / log).read_text(encoding="utf-8", errors="replace")
    found = re.findall(r"=+ (\d+ (?:passed|failed).*?) in [\d.]+s", text) or re.findall(r"^(\d+ passed.*?) in [\d.]+s", text, re.M)
    if not found:
        raise SystemExit(f"no pytest summary in {log}")
    return found[-1].strip(" =")


if __name__ == "__main__":
    sys.exit(main())
