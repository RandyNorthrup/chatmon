"""Write docs/delivery/reports/m1a/mac-owner/bindings.json, for docs/delivery/reports/wave4/bind.py.

usage, from the worktree's root: python docs/delivery/reports/m1a/mac-owner/mkbind.py

3bcd857 adds the owner test to tests/test_install_update.py, so every M1A receipt bound to that file is stale (10 of
33). Each one whose check can run here gets a W4D- receipt from that check, run again on 3bcd857: the Windows suite and
AC-01-USER's drill (run-windows.sh), the Linux tests and drills in WSL (run-wsl.sh), and the macOS suite and drills on
the owner's MacBook Pro. The Packages workflow's two receipts can't be re-run without a push, and stay stale. The new
receipt is the owner drill's. A drill that didn't go green, red and green stops this script.
"""

import json
from pathlib import Path

W = "docs/delivery/reports/m1a/mac-owner"
VENV = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
HEAD = "3bcd857"
WHY = f"Evidence for {HEAD}: improve/assessment-fixes (b5aa9d0) with the owner test added to tests/test_install_update.py."
ELSE = "The command is the one run there; the receipt's environment is the plan's profile (ROADMAP: evidence from elsewhere)."
MAC = ("the owner's MacBook Pro (macOS 15.7.9 24G830, Intel x86_64), owner-approved 2026-11-15, launched from here over ssh with "
       "docs/delivery/reports/m1a/mac/job.sh, with Homebrew's Python 3.13.7, PyQt6 6.11.0 and pytest 9.2.0 in a venv of its own "
       f"(packaging/requirements-test.txt, hash-locked; m1a/mac-owner/context-observed.txt), in a temporary copy of {HEAD}'s files "
       "(git archive; the unpacked tree checked against the commit's, 80fd2bd0)")
WSL = ("in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own "
       f"drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of {HEAD}'s files (mac-owner/files.lst), "
       "from mac-owner/run-wsl.sh")


def red(rid, acs, results, drill, artifact, where, after=""):
    record = {r["id"]: r for r in json.loads(Path(results).read_text(encoding="utf-8"))}.get(drill)
    if record is None or record["status"] != "pass":
        raise SystemExit(f"{drill} in {results} didn't go green, red, green")
    return {"id": rid, "kind": "red", "acceptance": acs, "results": results, "drill": drill, "artifact": artifact,
            "method": f"Red drill {drill} {where}: green; the defect put in, the named test failing with pytest's tests-failed exit and "
                      f"printing what's expected ({record['observed'].strip()[:150]!r}); the file's bytes put back (checked by SHA-256) "
                      "and green again." + (f" {after}" if after else "") + " " + WHY}


receipts = [
    {"id": "W4D-BEH-WINDOWS", "kind": "behavior",
     "acceptance": ["AC-01-VERIFY", "AC-01-USER", "AC-03", "AC-04", "AC-05", "AC-06", "AC-07", "AC-08", "AC-09-ORDER", "AC-09-REMOTE",
                    "AC-11", "AC-12", "AC-M6A-14"],
     "artifact": f"{W}/suite-windows.log", "command": [VENV, "-m", "pytest", "-q", "-p", "no:cacheprovider"], "exit_code": 0,
     "method": f"The whole suite on {HEAD}'s files (the log's header has HEAD and the source digest) on this Windows 11 workstation "
               "(offscreen Qt, the shared venv), which runs every test these criteria's earlier receipts named: 1259 passed, 179 "
               "skipped (other platforms' tests, each skip with its reason; the new owner test is one of them), exit 0. " + WHY},
    {"id": "W4D-BEH-LINUX", "kind": "behavior", "acceptance": ["AC-01-LINUX", "AC-02", "AC-07", "AC-09-ORDER", "AC-09-REMOTE"],
     "artifact": f"{W}/linux-tests.log",
     "command": ["wsl.exe", "-d", "archlinux", "--", "/var/tmp/plans-venv/bin/python", "-m", "pytest", "-v", "-rA", "-p",
                 "no:cacheprovider", "tests/test_install_update.py", "tests/test_packaging.py", "tests/test_agents.py",
                 "tests/test_attachments.py"], "exit_code": 0,
     "method": f"In WSL (Arch Linux; /var/tmp/plans-venv from packaging/requirements-test.txt, PyQt6 6.11.0, Qt 6.11.2, pytest 9.2.0) on "
               f"{HEAD}'s files, through docs/delivery/reports/m1a/mac-owner/run-wsl.sh, as a normal user: the Linux tests CI's Linux job "
               "had shown for these criteria, which can't be re-run without a push. Passed: tests/test_install_update.py's root-side "
               "tests (a signed newer package installed from root's own copy; a tampered list, a bad signature, an older release and a "
               "changed package refused; a caller's checksum never taken; the check loaded only from root's own files), "
               "tests/test_packaging.py's postinstall tests, tests/test_agents.py's private backups and tests/test_attachments.py's Linux "
               "mount and pipe tests: 76 passed, 11 skipped (macOS and Windows only), exit 0, every warning an error. " + ELSE + " " + WHY},
    {"id": "W4D-BEH-MACOS", "kind": "behavior", "acceptance": ["AC-01-MACOS", "AC-02", "AC-09-REMOTE"],
     "artifact": f"{W}/suite-offscreen.log",
     "command": ["/Users/user/chatmon-drills-tmp/venv/bin/python", "-m", "pytest", "-p", "no:cacheprovider", "--deselect",
                 "tests/test_keychain.py::test_macos_keychain_keeps_replaces_and_forgets_a_key"], "exit_code": 0,
     "method": f"The whole suite on {MAC}, run in his signed-in Aqua session by m1a/mac/aqua.sh, offscreen as CI's macOS job runs it: "
               "1236 passed, 201 skipped, 1 deselected (the test that writes to the owner's login keychain), exit 0. All 19 of "
               "tests/test_install_update.py's tests that run on macOS passed, the new test_mac_an_app_that_isnt_roots_is_never_run_as_root "
               "among them (the root code as shipped refuses an app root doesn't own), and so did tests/test_packaging.py's postinstall "
               "tests under BSD ls and tests/test_attachments.py's macOS statfs test; none of those is in the log's skip list. "
               + ELSE + " " + WHY},
]
for drill in ("AC-01-LINUX-launcher-owner", "AC-01-LINUX-refusal-stops", "AC-01-LINUX-installs-the-copy"):
    receipts.append(red(f"W4D-RED-{drill}", ["AC-01-LINUX"], f"{W}/drills-linux-results.json", drill, f"{W}/drills-linux.log", WSL))
receipts.append(red("W4D-RED-AC-01-USER-handoff", ["AC-01-USER"], f"{W}/drills-windows-results.json", "AC-01-USER-handoff",
                    f"{W}/drills-windows.log", "through tests/drills/run.py on this Windows workstation (wave4c/drill-spec.json --only "
                    f"AC-01-USER-handoff), in a temporary copy of {HEAD}'s files"))
receipts.append(red("W4D-RED-AC-01-MACOS-writable", ["AC-01-MACOS"], f"{W}/drills-results.json", "MAC-AC-01-MACOS-writable",
                    f"{W}/drills.log", f"on {MAC}",
                    "In _MACOS_ROOT, '-o -perm +022' became '-o -name nothing', so find no longer reports a file that group or others "
                    "can write: test_mac_an_app_others_could_change_is_never_run_as_root failed in its own body at "
                    "tests/test_install_update.py:300, the root script exiting 0 having installed, where 3 and the refusal were asserted. "
                    + ELSE))
receipts.append(red("W4D-RED-AC-01-MACOS-owner", ["AC-01-MACOS"], f"{W}/drills-results.json", "MAC-AC-01-MACOS-owner",
                    f"{W}/drills.log", f"on {MAC}",
                    "In _MACOS_ROOT, '! -user root -o ' was taken out, so find no longer reports a file root doesn't own: "
                    "test_mac_an_app_that_isnt_roots_is_never_run_as_root, which runs the root code as shipped (only the app's path "
                    "changed) on an app only its owner, the test user, can write, failed in its own body at "
                    "tests/test_install_update.py:319, the root script exiting 0 having run the copied app's install-update and installed, "
                    "where 3 and the refusal were asserted. This is the half of the check MAC-RED-AC-01-MACOS's drill couldn't reach. "
                    + ELSE))

bindings = {
    "plan": "docs/delivery/m1a-security-updates.md", "section": None, "rules": {}, "inputs_add": [], "task_changes_add": {},
    "stale_reason": f"Stale at {HEAD} (2026-11-15): tests/test_install_update.py, which it was bound to, gained the owner test; the "
                    "W4D- receipts ran its check again on the workstation, in WSL or on the Mac, and the Packages workflow's runs can't "
                    "be re-run without a push",
    "receipts": receipts, "tasks": {}, "pending": [],
    "next_action": f"None for M1A: every task is verified at {HEAD}. Both halves of _MACOS_ROOT's check now have a test that fails "
                   "without them (W4D-RED-AC-01-MACOS-writable and -owner). The Packages workflow's container and .pkg receipts "
                   "(W4C-BEH-PKG-*) are stale history now; its next run on PR #18 can be read for them again. The narrative is left as it "
                   "is: the scope fingerprint hashes it, so editing it would make every receipt here stale. A merge that changes a file "
                   "these receipts bind, or ROADMAP.md, needs those checks run again.",
    "source_revision": "3bcd8574a181e96fe7dfcb4adb76ba8c47813bd1",
}
Path(f"{W}/bindings.json").write_text(json.dumps(bindings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print(f"{len(receipts)} receipts")
