"""Round three (3586a0d): write docs/delivery/reports/<id>/wave4c/bindings.json for one plan: python mkbind3.py ID.

As mkbind2.py, which bound bf9d8ac in round two, with round three's folder, commit, CI run and receipt names (W4C-),
and M10 among the plans. wave4/crash is merged at 3586a0d, so nothing is watched for another branch any more.

Common receipts (readiness, the Windows suite, every drill that went green-red-green, mapped onto the criteria its
earlier receipt covered) are made the same way for every plan; each plan's own (CI legs, WSL runs, manual
observations, deferred checks) come from extra.json beside the bindings.
"""
import json
import re
import shutil
import sys
from pathlib import Path

ID = sys.argv[1]
ROOT = Path.cwd()
PLANS = {"m0": "m0-app-core", "m1a": "m1a-security-updates", "m1b": "m1b-brains-and-stored-data", "m2": "m2-bubbles-askbox",
         "m3": "m3-stage-overlay", "m4a": "m4a-platform-awareness", "m4b": "m4b-hotkey-sound-toasts", "m5": "m5-reminders-offline-locale",
         "m6a": "m6a-ci-tooling", "m6b": "m6b-static-analysis-logging", "m7": "m7-integration", "m8": "m8-translation",
         "m10": "m10-followups"}
PLAN = f"docs/delivery/{PLANS[ID]}.md"
R = f"docs/delivery/reports/{ID}"
W4 = f"{R}/wave4c"
SHA = "3586a0dc20ead1774a0fb4fe6d3253579d6c3e8b"
RUN = "43729628408"  # PR #18's CI run on 3586a0d (its Packages run, 43729628343, is named by each receipt that reads it)
VENV = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
SUITE = [VENV, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
CONCURRENT = "Evidence for 3586a0d, wave4/crash merged."
extra = json.loads((ROOT / W4 / "extra.json").read_text(encoding="utf-8"))

text = (ROOT / PLAN).read_text(encoding="utf-8")
L = json.loads(re.search(r"```quality-ledger\n(.*?)\n```", text, re.S).group(1))
active_req = {r["id"] for r in L["requirements"] if not r["superseded_by"]}
active = [a["id"] for a in L["acceptance"] if a["requirement"] in active_req]
auto_checks = {a["id"] for a in L["acceptance"] if "behavior" in a["checks"] and a["requirement"] in active_req}

# Drill results of this wave, by id, from every results file in wave4/ (Windows and WSL).
results = {}
for res in sorted((ROOT / W4).glob("*-results.json")):
    log = res.with_name(res.name.replace("-results.json", ".log"))
    for rec in json.loads(res.read_text(encoding="utf-8")):
        results.setdefault(rec["id"], (res.relative_to(ROOT).as_posix(), log.relative_to(ROOT).as_posix(), rec))
ids = sorted(results, key=len, reverse=True)

# The criteria each earlier red receipt covered, by the drill it names.
covers: dict[str, set] = {}
for e in L["evidence"]:
    if e["kind"] != "red" or e["status"] not in ("pass", "stale"):
        continue
    txt = ((e["red"] or {}).get("mutation") or "") + " " + e["method"] + " " + e["id"]
    hit = next((i for i in ids if re.search(r"(?<!\w)" + re.escape(i) + r"(?![\w-])", txt)), None)
    if hit:
        covers.setdefault(hit, set()).update(e["acceptance"])
for did, acs in extra.get("drill_acceptance", {}).items():  # wave 4's own drills, and corrections
    covers[did] = set(acs)
for did in extra.get("drill_skip", {}):  # a drill whose file its criterion's tasks don't own: it can't be bound there
    covers.pop(did, None)

receipts = [{
    "id": "W4C-READY", "kind": "readiness", "acceptance": active, "artifact": f"{W4}/readiness.md",
    "method": extra["readiness_method"],
}]
win = extra.get("windows_acceptance")
if win is None:  # round two's Windows suite receipt, for the plans round two bound
    win = next((e["acceptance"] for e in L["evidence"] if e["id"] == "W4B-BEH-WINDOWS"), None)
if win is None:
    win = sorted({a for e in L["evidence"] if e["kind"] == "behavior" and e["status"] in ("pass", "stale")
                  and e["environment"]["platform"] == "windows" and not any(k in (e["artifact"] or {}).get("path", "") for k in ("linux", "wsl"))
                  and "linux" not in e["id"].lower() and "wsl" not in e["id"].lower() for a in e["acceptance"]} & auto_checks)
    win = [a for a in active if a in win]
if win:
    receipts.append({
        "id": "W4C-BEH-WINDOWS", "kind": "behavior", "acceptance": win, "artifact": "docs/delivery/reports/wave4c/suite-windows.log",
        "command": SUITE, "exit_code": 0,
        "method": ("The whole suite on 3586a0d's source on this Windows 11 workstation (offscreen Qt, the shared venv), which runs "
                   "every test these criteria's earlier receipts named: 1259 passed, 178 skipped (other platforms' tests, each "
                   "skip with its reason), exit 0; per-test results are mapped from the log by docs/delivery/reports/wave4/cilog.py. "
                   + extra.get("windows_note", "") + " " + CONCURRENT).replace("  ", " "),
    })
receipts.extend(extra.get("receipts", []))

# Which tests each criterion's drills run: the CI receipts name a criterion only where one of them ran there.
tests_of: dict[str, set] = {}
for did, acs in covers.items():
    if did in results:
        for t in results[did][2]["command"]:
            if t.startswith("tests/"):
                for a in acs:
                    tests_of.setdefault(a, set()).add(t)
for a, ts in extra.get("tests_add", {}).items():
    tests_of.setdefault(a, set()).update(ts)
if extra.get("ci"):
    sys.path.insert(0, str(ROOT / "docs/delivery/reports/wave4"))
    import observe_3586a0d as observe  # noqa: E402
    pats = sorted({t for ts in tests_of.values() for t in ts} | set(extra.get("observe_add", [])))
    (ROOT / R / "ci").mkdir(parents=True, exist_ok=True)
    observe.main.__globals__["sys"].argv = ["observe_3586a0d.py", f"{R}/ci/observed-3586a0d.txt", *pats]
    observe.main()
    tables = {c: dict(observe.cilog.results(observe.collection(coll), observe.cilog.text_lines(observe.CI / log, step)))
              for c, log, step, coll in observe.LEGS}
    for meta in sorted(p.name for p in (ROOT / "docs/delivery/reports/wave4c/ci").glob("*.json")):
        shutil.copyfile(ROOT / "docs/delivery/reports/wave4c/ci" / meta, ROOT / R / "ci" / meta)
    for ci in extra["ci"]:
        table = tables[ci["leg"]]
        def ran(t):
            hits = [r for n, r in table.items() if n == t or n.startswith(t + "[") or n.startswith(t + "::") or (t.endswith(".py") and n.startswith(t + "::"))]
            return any(r == "passed" for r in hits), [n for n, r in table.items() if (n == t or n.startswith(t + "[") or n.startswith(t + "::")) and r == "passed"]
        acs = ci.get("acceptance") or [a for a in active if a in auto_checks and any(ran(t)[0] for t in tests_of.get(a, ()))]
        not_run = sorted({n for a in acs for t in tests_of.get(a, ()) for n, r in table.items()
                          if (n == t or n.startswith(t + "[") or n.startswith(t + "::")) and r != "passed"})
        print(f"  {ci['id']} ({ci['leg']}): {len(acs)} criteria; their drill tests not passed there: {not_run}")
        shutil.copyfile(ROOT / "docs/delivery/reports/wave4c/ci" / ci["log"], ROOT / R / "ci" / ci["log"])
        run_id = ci.get("run") or RUN
        job = ci["log"].split("-")[1]
        receipts.append({
            "id": ci["id"], "kind": "behavior", "acceptance": acs, "artifact": f"{R}/ci/{ci['log']}",
            "command": ["gh", "run", "view", run_id, "--repo", "RandyNorthrup/chatmon", "--job", job, "--log"], "exit_code": 0,
            "method": (ci["method"] + " " + ("Read from the job's log (fetched here with the command above, exit 0) by "
                       "docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto 3586a0d's collection and "
                       "checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-3586a0d.txt. The CI "
                       "run's own platform and versions are in the log; this receipt's environment is the plan's profile, the "
                       "workstation that fetched and read it (ROADMAP: evidence from elsewhere). " if not ci.get("no_cilog") else "")
                       + CONCURRENT).replace("  ", " "),
        })
skipped = []
for did, acs in sorted(covers.items()):
    if did not in results:
        skipped.append(did)
        continue
    res, log, rec = results[did]
    if rec["status"] != "pass":
        skipped.append(f"{did} ({rec['status']}: {rec['reason']})")
        continue
    linux = "/var/tmp" in " ".join(rec["command"]) or "linux" in res or "wsl" in res
    where = ("in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's "
             "own drill step, under xvfb-run -a with " + rec["command"][0]) if linux else "through tests/drills/run.py on this Windows workstation"
    where = extra.get("results_where", {}).get(res.rsplit("/", 1)[-1], where)
    wanted = rec["expected"] if isinstance(rec["expected"], list) else [rec["expected"]]
    diagnostic = next((e for e in wanted if e in rec.get("observed", "")), wanted[0])
    artifact, note = log, ""
    if diagnostic not in (ROOT / log).read_text(encoding="utf-8", errors="replace"):
        artifact = res  # the log keeps each run's last lines only, and the failing test's name came before them
        note = (f" The artifact is the harness's results record, whose observed line names the failing test; the red run's "
                f"output tail in {log.rsplit('/', 1)[-1]} begins after that line.")
    receipts.append({
        "id": f"W4C-RED-{did.removeprefix('W4-')}",
        "kind": "red", "acceptance": [a for a in active if a in acs], "results": res, "drill": did, "artifact": artifact,
        "method": extra.get("drill_method", {}).get(did, (f"Red drill {did} {where}, in a temporary copy of 3586a0d's files: green, the defect put in, the named tests "
                   "failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by "
                   "SHA-256) and green again.")) + note + " " + CONCURRENT,
    })
bindings = {
    "plan": PLAN, "section": f"{W4}/section.md",
    "rules": {"docs/delivery/ROADMAP.md": "3586a0d+wave4c", "pyproject.toml": "3586a0d"},
    "inputs_add": extra.get("inputs_add", []),
    "task_changes_add": extra.get("task_changes_add", {}),
    "stale_reason": extra.get("stale_reason", (
        "Stale at wave 4's third round (2026-11-15): ROADMAP.md, a rule of every plan, was amended for round three, and "
        "wave4/crash's merge changed chatmon/app.py, chatmon/brains.py, tests/app_harness.py and tests/test_app_smoke.py; "
        "the W4C- receipts re-ran its check on 3586a0d or read it from CI run 43729628408")),
    "receipts": receipts, "tasks": extra.get("tasks", {}), "pending": extra.get("pending", []),
    "next_action": extra["next_action"], "source_revision": SHA,
}
(ROOT / W4 / "bindings.json").write_text(json.dumps(bindings, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
covered = set()
for r in receipts:
    if r["kind"] == "red":
        covered.update(r["acceptance"])
need_red = [a for a in active if a in {x["id"] for x in L["acceptance"] if "red" in x["checks"]} and a not in covered]
print(f"{ID}: {len(receipts)} receipts ({sum(r['kind'] == 'red' for r in receipts)} red); drills not bound: {skipped}")
print(f"criteria still without a red receipt: {need_red}")
print(f"criteria not in the Windows receipt: {[a for a in active if a not in win]}")
