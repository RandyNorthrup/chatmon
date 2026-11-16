"""The plans round for v0.10.0, bound again at 56caddd: write docs/delivery/reports/<id>/wave5b/bindings.json:
python mkbind7.py ID.

As mkbind6.py, with the folder wave5b/, receipt names W5B- and the second binding's commit and CI: PR #24's run
43794815103 of ci.yml on 56caddd (the coordinator's df3e93c and 56caddd on 7816159; its logs in wave5b/ci/, read by
observe_56caddd.py). A plan whose requirements changed (M6A's
Dependabot entry) carries its "ledger_edits" in extra.json; they are applied here, before the plan's active criteria
are counted, and passed on to bind.py, which applies them to the plan.

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
W4 = f"{R}/wave5b"
SHA = "56caddd66b69420e073e9a7d2c5ec40eabb5840b"
RUN = "43794815103"  # PR #24's CI run on 56caddd (each receipt that reads another run names it)
VENV = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
SUITE = [VENV, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
CONCURRENT = "Evidence for 56caddd: v0.10.0's 7816159 with the coordinator's df3e93c (layer.py's two QGuiApplication.instance() calls typed, CONTRIBUTING.md's opt-in table) and 56caddd (test_hide_menu_and_reload waits for the greeting)."
SUITE_LOG = ROOT / "docs/delivery/reports/wave5b/suite-windows.log"
COUNTS = re.findall(r"(\d+ passed, \d+ skipped)", SUITE_LOG.read_text(encoding="utf-8", errors="replace"))[-1]
extra = json.loads((ROOT / W4 / "extra.json").read_text(encoding="utf-8"))

text = (ROOT / PLAN).read_text(encoding="utf-8")
L = json.loads(re.search(r"```quality-ledger\n(.*?)\n```", text, re.S).group(1))
if extra.get("ledger_edits"):  # the plan as bind.py will make it: superseded requirements out, their replacements in
    sys.path.insert(0, str(ROOT / "docs/delivery/reports/wave4"))
    from bind import apply_edits  # noqa: E402

    apply_edits(L, extra["ledger_edits"])
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
    "id": "W5B-READY", "kind": "readiness", "acceptance": active, "artifact": f"{W4}/readiness.md",
    "method": extra["readiness_method"],
}]
win = extra.get("windows_acceptance")
if win is None:  # the latest Windows suite receipt: the final round's (either binding), or round three's
    win = next((e["acceptance"] for rid in ("W5-BEH-WINDOWS", "W4F-BEH-WINDOWS", "W4E-BEH-WINDOWS", "W4C-BEH-WINDOWS") for e in L["evidence"] if e["id"] == rid), None)
if win is None:
    win = sorted({a for e in L["evidence"] if e["kind"] == "behavior" and e["status"] in ("pass", "stale")
                  and e["environment"]["platform"] == "windows" and not any(k in (e["artifact"] or {}).get("path", "") for k in ("linux", "wsl"))
                  and "linux" not in e["id"].lower() and "wsl" not in e["id"].lower() for a in e["acceptance"]} & auto_checks)
    win = [a for a in active if a in win]
if win:
    receipts.append({
        "id": "W5B-BEH-WINDOWS", "kind": "behavior", "acceptance": win, "artifact": "docs/delivery/reports/wave5b/suite-windows.log",
        "command": SUITE, "exit_code": 0,
        "method": ("The whole suite on 56caddd's source on this Windows 11 workstation (offscreen Qt, the shared venv, BelowNormal priority, a CHATMON_INSTANCE "
                   "of its own), which runs every test these criteria's earlier receipts named: " + COUNTS + " (other platforms' tests, each "
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
    import observe_56caddd as observe  # noqa: E402
    pats = sorted({t for ts in tests_of.values() for t in ts} | set(extra.get("observe_add", [])))
    (ROOT / R / "ci").mkdir(parents=True, exist_ok=True)
    observe.main.__globals__["sys"].argv = ["observe_56caddd.py", f"{R}/ci/observed-56caddd.txt", *pats]
    observe.main()
    tables = {c: dict(observe.cilog.results(observe.collection(coll), observe.cilog.text_lines(observe.CI / log, step)))
              for c, log, step, coll in observe.LEGS}
    for meta in sorted(p.name for p in (ROOT / "docs/delivery/reports/wave5b/ci").glob("*.json")):
        shutil.copyfile(ROOT / "docs/delivery/reports/wave5b/ci" / meta, ROOT / R / "ci" / meta)
    for ci in extra["ci"]:
        table = tables[ci["leg"]]
        def ran(t):
            hits = [r for n, r in table.items() if n == t or n.startswith(t + "[") or n.startswith(t + "::") or (t.endswith(".py") and n.startswith(t + "::"))]
            return any(r == "passed" for r in hits), [n for n, r in table.items() if (n == t or n.startswith(t + "[") or n.startswith(t + "::")) and r == "passed"]
        acs = ci.get("acceptance") or [a for a in active if a in auto_checks and any(ran(t)[0] for t in tests_of.get(a, ()))]
        not_run = sorted({n for a in acs for t in tests_of.get(a, ()) for n, r in table.items()
                          if (n == t or n.startswith(t + "[") or n.startswith(t + "::")) and r != "passed"})
        print(f"  {ci['id']} ({ci['leg']}): {len(acs)} criteria; their drill tests not passed there: {not_run}")
        shutil.copyfile(ROOT / "docs/delivery/reports/wave5b/ci" / ci["log"], ROOT / R / "ci" / ci["log"])
        run_id = ci.get("run") or RUN
        job = ci["log"].split("-")[1]
        receipts.append({
            "id": ci["id"], "kind": "behavior", "acceptance": acs, "artifact": f"{R}/ci/{ci['log']}",
            "command": ["gh", "run", "view", run_id, "--repo", "RandyNorthrup/chatmon", "--job", job, "--log"], "exit_code": 0,
            "method": (ci["method"] + " " + ("Read from the job's log (fetched here with the command above, exit 0) by "
                       "docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto 56caddd's collection and "
                       "checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-56caddd.txt. The CI "
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
        "id": f"W5B-RED-{did.removeprefix('W4-')}",
        "kind": "red", "acceptance": [a for a in active if a in acs], "results": res, "drill": did, "artifact": artifact,
        "method": extra.get("drill_method", {}).get(did, (f"Red drill {did} {where}, in a temporary copy of 56caddd's files: green, the defect put in, the named tests "
                   "failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by "
                   "SHA-256) and green again.")) + note + " " + CONCURRENT,
    })
bindings = {
    "plan": PLAN, "section": f"{W4}/section.md",
    "rules": {},  # ROADMAP.md and pyproject.toml are unchanged since round three, and stay so (every plan binds them)
    "inputs_add": extra.get("inputs_add", []),
    "task_changes_add": extra.get("task_changes_add", {}),
    "ledger_edits": extra.get("ledger_edits", {}),
    "stale_reason": extra.get("stale_reason", (
        "Stale in the plans round's second binding (2026-11-15): the coordinator's df3e93c and 56caddd changed files it was "
        "bound to, or the plans it binds, or this round's section, which every receipt's scope includes. The W5B- receipts "
        "re-ran its check on 56caddd or read it from PR #24's CI run 43794815103")),
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
