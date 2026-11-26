# Dismissible agent notifications

The number beside the companion counts working agents and unread needs-you alerts. Existing alert closing only ended the bubble; waiting state could keep its count forever. Preserve the live waiting status after reading, expose a separate manual reset for missing terminal hooks, and allow later hooks to notify again.

Reuse `Companion.agents`, `MessageQueue.take/withdraw`, `Menus` and the native/stage popup paths. Keep reminder Done/Snooze behavior. The active security/performance audit edits are this session's work and must be preserved. No new runtime dependency or notification subsystem is needed.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "NOTIFICATIONS",
    "title": "Dismissible agent notifications and status badges",
    "scope_revision": 4,
    "brief": null,
    "brief_reason": "Scoped follow-up explicitly requested during the security/performance audit; the user identified the number beside the companion.",
    "rules": [
      {
        "path": "AGENTS.md",
        "revision": "1"
      },
      {
        "path": "CONTRIBUTING.md",
        "revision": "working-tree-2026-11-26"
      }
    ],
    "inputs": [
      "pyproject.toml",
      "chatmon/messages.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10"
      }
    }
  },
  "requirements": [
    {
      "id": "NTF-1",
      "statement": "Agent notifications have explicit read/dismiss controls, recoverable stale status counts and equivalent keyboard-accessible controls.",
      "priority": "normal",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "NTF-READ",
      "requirement": "NTF-1",
      "given": "An unread agent alert, including an older alert superseded by a fresh event",
      "when": "Mark as read, closing the latest alert, or Mark all as read is used",
      "then": "Only the acknowledged notices leave the queue and badge; live agent status remains available; a fresh event raises a new notice and an old action cannot clear it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "NTF-CLEAR",
      "requirement": "NTF-1",
      "given": "Working or waiting agent states whose terminal hook may never arrive",
      "when": "Clear status for one agent or Clear all statuses is selected",
      "then": "Selected states, badges, tray indicator and pending agent alerts clear immediately without changing reminders; subsequent agent hooks work normally",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "NTF-MENU",
      "requirement": "NTF-1",
      "given": "A badge on the companion or the tray/context menu",
      "when": "The badge is clicked or Notifications is opened with keyboard navigation",
      "then": "Read and clear controls are reachable through the existing accessible native/overlay menu, and the badge is included in the pointer input region",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "NTF-T1",
      "purpose": "Extend canonical agent state, alert lifecycle, menu and badge hit handling with regression tests and isolated drills.",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        },
        {
          "path": "tests/test_stage_features.py",
          "action": "modify"
        },
        {
          "path": "tests/drills/security-performance.json",
          "action": "modify"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "action": "modify"
        },
        {
          "path": "README.md",
          "action": "modify"
        },
        {
          "path": "chatmon/changelog.md",
          "action": "modify"
        },
        {
          "path": ".gitattributes",
          "action": "modify"
        },
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "chatmon/asking.py",
          "action": "modify"
        },
        {
          "path": "chatmon/styles.py",
          "action": "modify"
        },
        {
          "path": "chatmon/__init__.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "NTF-E-READY-4",
        "NTF-E-TEST-4",
        "NTF-E-NTF-read-4",
        "NTF-E-NTF-clear-4",
        "NTF-E-NTF-pointer-4",
        "NTF-E-NTF-keyboard-4",
        "NTF-E-NTF-newer-4",
        "NTF-E-NTF-close-4",
        "NTF-E-NTF-distinct-4"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "NTF-E-READY",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Reviewed clarified badge semantics, canonical callers, existing audit edits, failure behavior, reminder isolation and test/drill coverage; see readiness.txt.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/notifications/readiness.txt",
        "sha256": "b6c0de419d5dfd58ed47e1de3805fd9ab09208533db8d801d86dbea517952538"
      },
      "inputs": [
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "94d1f59e3d2a17e10c4b767fb74bacd8f1b3833411e63a482937dae6c6ac7563"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "pyproject.toml",
          "sha256": "bbe797e79f43f4f0f121d1c435c1c2411043f97cc608805a92f0b1db6ea1775c"
        }
      ],
      "scope_sha256": "6d217001b5a3e9108ce34eb8e60233f4bd6d6282002113457cb70da39e49f9ec",
      "red": null,
      "reason": "Scope amended to preserve exact notification-report bytes and bind canonical LF source bytes; a fresh readiness review follows."
    },
    {
      "id": "NTF-E-READY-2",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Rechecked clarified badge semantics, reminder isolation, action version guards, canonical callers and artifact-byte policy after the scope amendment; readiness.txt records the review.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/notifications/readiness.txt",
        "sha256": "eb8d53bf65a2e1451bd2a127e1be3a2e3b05cd237d85f30437af34252817387b"
      },
      "inputs": [
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": null,
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-TEST",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "tests/test_app_m7.py",
        "tests/test_stage_features.py",
        "-k",
        "reading_an_agent or notification_menu or older_alert or badge_opens or badge_takes"
      ],
      "method": "Six real Qt acceptance cases pass after final canonical LF normalization: read and bulk actions, fresh/old alerts, reminder isolation, pointer input and keyboard activation through native and overlay menus.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/acceptance.log",
        "sha256": "8892fc94710f0b4f207b1b660b0adf5851d658f26852dc97acb39c4a78606af2"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "bbd240999f859fea4eb7fc90ef464de37b1e163e75a7aa144f49aa0d6b7e3829"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cef25639e755f3ab782ba7ed16798969569ef30568e834f7b683ea2b7fffeac5"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "04524758779e534e0fbbc85c41b7bc61b5951b2678fc1fb825c81b0a61592f59"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": null,
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-NTF-read",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Existing isolated-copy drill harness: the named real Qt tests passed, the injected defect caused the intended assertion and exit 1, original source bytes were restored exactly, and the same tests passed again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills.log",
        "sha256": "482f89a1977b53d9756090231386a084be5f22088913840df6eaf21629593f2b"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "bbd240999f859fea4eb7fc90ef464de37b1e163e75a7aa144f49aa0d6b7e3829"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cef25639e755f3ab782ba7ed16798969569ef30568e834f7b683ea2b7fffeac5"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "04524758779e534e0fbbc85c41b7bc61b5951b2678fc1fb825c81b0a61592f59"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._read_agents.update(chosen)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "0f09e337a03d0d12beffda45e31735d531c2c559977a4554e1ac42446d062c95"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ]
      },
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-NTF-clear",
      "acceptance": [
        "NTF-CLEAR"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_notification_menu_can_read_and_reset_states_without_dismissing_reminders"
      ],
      "method": "Existing isolated-copy drill harness: the named real Qt tests passed, the injected defect caused the intended assertion and exit 1, original source bytes were restored exactly, and the same tests passed again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills.log",
        "sha256": "482f89a1977b53d9756090231386a084be5f22088913840df6eaf21629593f2b"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "bbd240999f859fea4eb7fc90ef464de37b1e163e75a7aa144f49aa0d6b7e3829"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cef25639e755f3ab782ba7ed16798969569ef30568e834f7b683ea2b7fffeac5"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "04524758779e534e0fbbc85c41b7bc61b5951b2678fc1fb825c81b0a61592f59"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.agents.pop(s, None)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_notification_menu_can_read_and_reset_states_without_dismissing_reminders",
        "observed_diagnostic": "_ test_notification_menu_can_read_and_reset_states_without_dismissing_reminders _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "ca4422d1ceba5aa44631068b24f0116de7cb1ab143ca06a079351d1f627e7c6a"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ]
      },
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-NTF-pointer",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_features.py::test_the_badge_takes_pointer_input_and_opens_notifications"
      ],
      "method": "Existing isolated-copy drill harness: the named real Qt tests passed, the injected defect caused the intended assertion and exit 1, original source bytes were restored exactly, and the same tests passed again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills.log",
        "sha256": "482f89a1977b53d9756090231386a084be5f22088913840df6eaf21629593f2b"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "bbd240999f859fea4eb7fc90ef464de37b1e163e75a7aa144f49aa0d6b7e3829"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cef25639e755f3ab782ba7ed16798969569ef30568e834f7b683ea2b7fffeac5"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "04524758779e534e0fbbc85c41b7bc61b5951b2678fc1fb825c81b0a61592f59"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.notifications_requested.emit(gpos.toPoint())', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_badge_takes_pointer_input_and_opens_notifications",
        "observed_diagnostic": "_________ test_the_badge_takes_pointer_input_and_opens_notifications __________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "17b78991fe4bf4eacf125564966f76b673558c34704b3a8244863c4cc04bf591"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ]
      },
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-NTF-keyboard",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_badge_opens_notifications_and_keyboard_can_clear_all"
      ],
      "method": "Existing isolated-copy drill harness: the named real Qt tests passed, the injected defect caused the intended assertion and exit 1, original source bytes were restored exactly, and the same tests passed again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills.log",
        "sha256": "482f89a1977b53d9756090231386a084be5f22088913840df6eaf21629593f2b"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "bbd240999f859fea4eb7fc90ef464de37b1e163e75a7aa144f49aa0d6b7e3829"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cef25639e755f3ab782ba7ed16798969569ef30568e834f7b683ea2b7fffeac5"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "04524758779e534e0fbbc85c41b7bc61b5951b2678fc1fb825c81b0a61592f59"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'clear_all.triggered.connect(lambda: c._clear_agent_states())', 'replace': 'clear_all.triggered.connect(lambda: None)'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_badge_opens_notifications_and_keyboard_can_clear_all",
        "observed_diagnostic": "______ test_badge_opens_notifications_and_keyboard_can_clear_all[False] _______",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "9f1f4cc55c052a2d6dc1b18f2f16af499e13e4dc30f5c5c650ded489ebe88489"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
          }
        ]
      },
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-NTF-newer",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Existing isolated-copy drill harness: the named real Qt tests passed, the injected defect caused the intended assertion and exit 1, original source bytes were restored exactly, and the same tests passed again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills.log",
        "sha256": "482f89a1977b53d9756090231386a084be5f22088913840df6eaf21629593f2b"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "bbd240999f859fea4eb7fc90ef464de37b1e163e75a7aa144f49aa0d6b7e3829"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cef25639e755f3ab782ba7ed16798969569ef30568e834f7b683ea2b7fffeac5"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "04524758779e534e0fbbc85c41b7bc61b5951b2678fc1fb825c81b0a61592f59"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': '(since is None or at == since)', 'replace': 'True'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "d749211f81a368ea6666315377080601003b99e272cce3f5967f0d1d04bff9c3"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ]
      },
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-NTF-close",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Existing isolated-copy drill harness: the named real Qt tests passed, the injected defect caused the intended assertion and exit 1, original source bytes were restored exactly, and the same tests passed again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills.log",
        "sha256": "482f89a1977b53d9756090231386a084be5f22088913840df6eaf21629593f2b"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "bbd240999f859fea4eb7fc90ef464de37b1e163e75a7aa144f49aa0d6b7e3829"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "a172939859e9fdab5545bc0518a4778f989d8b8a6acbb184aea32ad465ebcb9f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cef25639e755f3ab782ba7ed16798969569ef30568e834f7b683ea2b7fffeac5"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "04524758779e534e0fbbc85c41b7bc61b5951b2678fc1fb825c81b0a61592f59"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._mark_agents_read(source, self.agents[source][1])', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "78c93abf317f6ab5df6da422a5997050d56ae054ab64337a2649238dfcb5f7a3"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "2050260cc93920353a6c6a4f3db78f29ba509cbf6de279d286f9915e74421db1"
          }
        ]
      },
      "reason": "Hosted Windows/Python 3.11 reproduced coarse-clock aliasing; event revisions replace timestamp identity. Dependency pins in shared pyproject.toml also changed for issue #23. Fresh proof is required."
    },
    {
      "id": "NTF-E-READY-3",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Re-reviewed coarse-clock reproduction, integer event identity, stale-action behavior and current dependency pins; readiness-3.txt records the amendment.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/notifications/readiness-3.txt",
        "sha256": "9a8917d7b9dc941383610b88e54bba2b63574f26fa9035232f35b5c0d625fc78"
      },
      "inputs": [
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": null,
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-TEST-3",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "tests/test_app_m7.py",
        "tests/test_stage_features.py",
        "-k",
        "reading_an_agent or notification_menu or old_menu_action or older_alert or badge_opens or badge_takes"
      ],
      "method": "Seven real Qt cases pass with the updated dev locks: frozen-clock old read/reset actions, latest/queued alerts, reminder isolation, pointer input and native/overlay keyboard actions.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/acceptance-3.log",
        "sha256": "26fcb559f3432116e970e4fc8bff3762e3fa0fcb6ba06dbb98d27497ab34d7f7"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "af1b2edf7dec7a49ee9bfe5b956365e8082543581ff97487d620e61f72832364"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "84514f3b93e29d22a227bbf1920a47d4f2b479fae16aead947f4db5509263ddf"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": null,
      "reason": "Distinct payloads inside the duplicate-hook window must remain separate notifications; source and maintained drill set changed after this observation. Final source requires fresh proof."
    },
    {
      "id": "NTF-E-NTF-read-3",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Isolated copy: original tests pass, injected defect fails the intended assertion, exact original source bytes restored, and same tests pass again. Frozen timestamps exercise revision guards independently of clock resolution.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-3.log",
        "sha256": "6d8f349d14f0ca2dab51ad41d33b5226009b71154fa550b4e2eaf99b0800ee51"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "af1b2edf7dec7a49ee9bfe5b956365e8082543581ff97487d620e61f72832364"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "84514f3b93e29d22a227bbf1920a47d4f2b479fae16aead947f4db5509263ddf"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._read_agents.update(chosen)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "e64b559bd27e8d0bb9653b734aae499e3da1cea88dcfd9e2e7cb6b01f70b2120"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ]
      },
      "reason": "Distinct payloads inside the duplicate-hook window must remain separate notifications; source and maintained drill set changed after this observation. Final source requires fresh proof."
    },
    {
      "id": "NTF-E-NTF-clear-3",
      "acceptance": [
        "NTF-CLEAR"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_notification_menu_can_read_and_reset_states_without_dismissing_reminders"
      ],
      "method": "Isolated copy: original tests pass, injected defect fails the intended assertion, exact original source bytes restored, and same tests pass again. Frozen timestamps exercise revision guards independently of clock resolution.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-3.log",
        "sha256": "6d8f349d14f0ca2dab51ad41d33b5226009b71154fa550b4e2eaf99b0800ee51"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "af1b2edf7dec7a49ee9bfe5b956365e8082543581ff97487d620e61f72832364"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "84514f3b93e29d22a227bbf1920a47d4f2b479fae16aead947f4db5509263ddf"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.agents.pop(s, None)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_notification_menu_can_read_and_reset_states_without_dismissing_reminders",
        "observed_diagnostic": "_ test_notification_menu_can_read_and_reset_states_without_dismissing_reminders _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "c98c77824c9ba37dfb169424b2feb5f30dc026c2a2bdf0f8c321a6518385f19e"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ]
      },
      "reason": "Distinct payloads inside the duplicate-hook window must remain separate notifications; source and maintained drill set changed after this observation. Final source requires fresh proof."
    },
    {
      "id": "NTF-E-NTF-pointer-3",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_features.py::test_the_badge_takes_pointer_input_and_opens_notifications"
      ],
      "method": "Isolated copy: original tests pass, injected defect fails the intended assertion, exact original source bytes restored, and same tests pass again. Frozen timestamps exercise revision guards independently of clock resolution.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-3.log",
        "sha256": "6d8f349d14f0ca2dab51ad41d33b5226009b71154fa550b4e2eaf99b0800ee51"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "af1b2edf7dec7a49ee9bfe5b956365e8082543581ff97487d620e61f72832364"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "84514f3b93e29d22a227bbf1920a47d4f2b479fae16aead947f4db5509263ddf"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.notifications_requested.emit(gpos.toPoint())', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_badge_takes_pointer_input_and_opens_notifications",
        "observed_diagnostic": "_________ test_the_badge_takes_pointer_input_and_opens_notifications __________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "17b78991fe4bf4eacf125564966f76b673558c34704b3a8244863c4cc04bf591"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ]
      },
      "reason": "Distinct payloads inside the duplicate-hook window must remain separate notifications; source and maintained drill set changed after this observation. Final source requires fresh proof."
    },
    {
      "id": "NTF-E-NTF-keyboard-3",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_badge_opens_notifications_and_keyboard_can_clear_all"
      ],
      "method": "Isolated copy: original tests pass, injected defect fails the intended assertion, exact original source bytes restored, and same tests pass again. Frozen timestamps exercise revision guards independently of clock resolution.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-3.log",
        "sha256": "6d8f349d14f0ca2dab51ad41d33b5226009b71154fa550b4e2eaf99b0800ee51"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "af1b2edf7dec7a49ee9bfe5b956365e8082543581ff97487d620e61f72832364"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "84514f3b93e29d22a227bbf1920a47d4f2b479fae16aead947f4db5509263ddf"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'clear_all.triggered.connect(lambda: c._clear_agent_states())', 'replace': 'clear_all.triggered.connect(lambda: None)'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_badge_opens_notifications_and_keyboard_can_clear_all",
        "observed_diagnostic": "______ test_badge_opens_notifications_and_keyboard_can_clear_all[False] _______",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "0ac50da5e2246e3918c5368cc03c611697b9aa1eef683cb460e6a033277dbeb4"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
          }
        ]
      },
      "reason": "Distinct payloads inside the duplicate-hook window must remain separate notifications; source and maintained drill set changed after this observation. Final source requires fresh proof."
    },
    {
      "id": "NTF-E-NTF-newer-3",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "tests/test_app_m7.py::test_an_old_menu_action_cannot_clear_a_new_state_with_the_same_timestamp"
      ],
      "method": "Isolated copy: original tests pass, injected defect fails the intended assertion, exact original source bytes restored, and same tests pass again. Frozen timestamps exercise revision guards independently of clock resolution.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-3.log",
        "sha256": "6d8f349d14f0ca2dab51ad41d33b5226009b71154fa550b4e2eaf99b0800ee51"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "af1b2edf7dec7a49ee9bfe5b956365e8082543581ff97487d620e61f72832364"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "84514f3b93e29d22a227bbf1920a47d4f2b479fae16aead947f4db5509263ddf"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': '(revision is None or self._agent_revisions.get(s) == revision)', 'replace': 'True'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "766c7d3337cbed0f4c539e72990faff5678d3a6348ec650f567f0f3544c27c75"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ]
      },
      "reason": "Distinct payloads inside the duplicate-hook window must remain separate notifications; source and maintained drill set changed after this observation. Final source requires fresh proof."
    },
    {
      "id": "NTF-E-NTF-close-3",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Isolated copy: original tests pass, injected defect fails the intended assertion, exact original source bytes restored, and same tests pass again. Frozen timestamps exercise revision guards independently of clock resolution.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-3.log",
        "sha256": "6d8f349d14f0ca2dab51ad41d33b5226009b71154fa550b4e2eaf99b0800ee51"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "af1b2edf7dec7a49ee9bfe5b956365e8082543581ff97487d620e61f72832364"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "84514f3b93e29d22a227bbf1920a47d4f2b479fae16aead947f4db5509263ddf"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._mark_agents_read(source, self._agent_revisions.get(source))', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "a31df93236f25f6b114322942cd9367f24e98e1f41fe2d045a4c88e2787f3889"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f543e5b098bbc0d46bb956520e879be779837ddbd8d04364d97198090a601c1"
          }
        ]
      },
      "reason": "Distinct payloads inside the duplicate-hook window must remain separate notifications; source and maintained drill set changed after this observation. Final source requires fresh proof."
    },
    {
      "id": "NTF-E-TEST-FINAL",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "tests/test_app_m7.py",
        "tests/test_stage_features.py",
        "-k",
        "reading_an_agent or notification_menu or old_menu_action or older_alert or badge_opens or badge_takes"
      ],
      "method": "Seven real Qt cases: frozen-clock stale read/reset actions, distinct queued payloads, latest-alert closing, reminder isolation, pointer input and native/overlay keyboard activation.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/acceptance-final.log",
        "sha256": "1970d6b64a8da68f4440dbebbe86e6f83975bc6a63b27e130871cbd02d4550bb"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": null,
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-NTF-read-FINAL",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "The isolated-copy harness proves green, intended assertion failure after a mutation, exact source-byte restoration and restored green. Revisions are exercised with frozen clocks; distinct-payload suppression is drilled independently.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._read_agents.update(chosen)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "6fa8fec7812d6a9d6802a7b9659e6316789b569c482330ce60751a3dc5fef87e"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-NTF-clear-FINAL",
      "acceptance": [
        "NTF-CLEAR"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_notification_menu_can_read_and_reset_states_without_dismissing_reminders"
      ],
      "method": "The isolated-copy harness proves green, intended assertion failure after a mutation, exact source-byte restoration and restored green. Revisions are exercised with frozen clocks; distinct-payload suppression is drilled independently.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.agents.pop(s, None)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_notification_menu_can_read_and_reset_states_without_dismissing_reminders",
        "observed_diagnostic": "_ test_notification_menu_can_read_and_reset_states_without_dismissing_reminders _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "3c43e2026a588bf825bc373ddb4809b82d37920d5900ac21bac789cc1d4013ec"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-NTF-pointer-FINAL",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_features.py::test_the_badge_takes_pointer_input_and_opens_notifications"
      ],
      "method": "The isolated-copy harness proves green, intended assertion failure after a mutation, exact source-byte restoration and restored green. Revisions are exercised with frozen clocks; distinct-payload suppression is drilled independently.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.notifications_requested.emit(gpos.toPoint())', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_badge_takes_pointer_input_and_opens_notifications",
        "observed_diagnostic": "_________ test_the_badge_takes_pointer_input_and_opens_notifications __________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "17b78991fe4bf4eacf125564966f76b673558c34704b3a8244863c4cc04bf591"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ]
      },
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-NTF-keyboard-FINAL",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_badge_opens_notifications_and_keyboard_can_clear_all"
      ],
      "method": "The isolated-copy harness proves green, intended assertion failure after a mutation, exact source-byte restoration and restored green. Revisions are exercised with frozen clocks; distinct-payload suppression is drilled independently.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'clear_all.triggered.connect(lambda: c._clear_agent_states())', 'replace': 'clear_all.triggered.connect(lambda: None)'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_badge_opens_notifications_and_keyboard_can_clear_all",
        "observed_diagnostic": "______ test_badge_opens_notifications_and_keyboard_can_clear_all[False] _______",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "0ac50da5e2246e3918c5368cc03c611697b9aa1eef683cb460e6a033277dbeb4"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
          }
        ]
      },
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-NTF-newer-FINAL",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "tests/test_app_m7.py::test_an_old_menu_action_cannot_clear_a_new_state_with_the_same_timestamp"
      ],
      "method": "The isolated-copy harness proves green, intended assertion failure after a mutation, exact source-byte restoration and restored green. Revisions are exercised with frozen clocks; distinct-payload suppression is drilled independently.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': '(revision is None or self._agent_revisions.get(s) == revision)', 'replace': 'True'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "03c99213d942679aa8ea8d61dd0a2ee9181e650d9d881a97a5a93024d9e0d66a"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-NTF-close-FINAL",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "The isolated-copy harness proves green, intended assertion failure after a mutation, exact source-byte restoration and restored green. Revisions are exercised with frozen clocks; distinct-payload suppression is drilled independently.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._mark_agents_read(source, self._agent_revisions.get(source))', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "7766e1c76d981b7ddea7a16bb45753bc0b235d3d8235beaa91dd4d7bbaf99d4d"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-NTF-distinct-FINAL",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_closing_an_older_alert_does_not_read_its_queued_replacement"
      ],
      "method": "The isolated-copy harness proves green, intended assertion failure after a mutation, exact source-byte restoration and restored green. Revisions are exercised with frozen clocks; distinct-payload suppression is drilled independently.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'seen = (source, event, hashlib.sha256(text.encode(\"utf-8\", \"surrogatepass\")).digest())', 'replace': 'seen = (source, event, b\"\")'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_closing_an_older_alert_does_not_read_its_queued_replacement",
        "observed_diagnostic": "______ test_closing_an_older_alert_does_not_read_its_queued_replacement _______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "fc02ff5a75135588a9a053da380f3467f64aeecf24a9dfcff07fe660bc0f5aaa"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "Superseded by final proof after distinct-payload suppression and frozen-clock identity fixes."
    },
    {
      "id": "NTF-E-TEST-DELIVERY",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "tests/test_app_m7.py",
        "tests/test_stage_features.py",
        "-k",
        "reading_an_agent or notification_menu or old_menu_action or older_alert or badge_opens or badge_takes"
      ],
      "method": "Seven real Qt acceptance cases pass with frozen clocks and consecutive distinct requests, reminder isolation, badge input and native/overlay keyboard actions.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/acceptance-final.log",
        "sha256": "1970d6b64a8da68f4440dbebbe86e6f83975bc6a63b27e130871cbd02d4550bb"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": null,
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-NTF-read-DELIVERY",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Isolated harness: green, intended assertion after the injected defect, exact byte restoration, restored green. Distinct-payload handling and frozen-clock action identity are both exercised.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._read_agents.update(chosen)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "6fa8fec7812d6a9d6802a7b9659e6316789b569c482330ce60751a3dc5fef87e"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-NTF-clear-DELIVERY",
      "acceptance": [
        "NTF-CLEAR"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_notification_menu_can_read_and_reset_states_without_dismissing_reminders"
      ],
      "method": "Isolated harness: green, intended assertion after the injected defect, exact byte restoration, restored green. Distinct-payload handling and frozen-clock action identity are both exercised.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.agents.pop(s, None)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_notification_menu_can_read_and_reset_states_without_dismissing_reminders",
        "observed_diagnostic": "_ test_notification_menu_can_read_and_reset_states_without_dismissing_reminders _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "3c43e2026a588bf825bc373ddb4809b82d37920d5900ac21bac789cc1d4013ec"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-NTF-pointer-DELIVERY",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_features.py::test_the_badge_takes_pointer_input_and_opens_notifications"
      ],
      "method": "Isolated harness: green, intended assertion after the injected defect, exact byte restoration, restored green. Distinct-payload handling and frozen-clock action identity are both exercised.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self.notifications_requested.emit(gpos.toPoint())', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_badge_takes_pointer_input_and_opens_notifications",
        "observed_diagnostic": "_________ test_the_badge_takes_pointer_input_and_opens_notifications __________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "17b78991fe4bf4eacf125564966f76b673558c34704b3a8244863c4cc04bf591"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ]
      },
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-NTF-keyboard-DELIVERY",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_badge_opens_notifications_and_keyboard_can_clear_all"
      ],
      "method": "Isolated harness: green, intended assertion after the injected defect, exact byte restoration, restored green. Distinct-payload handling and frozen-clock action identity are both exercised.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'clear_all.triggered.connect(lambda: c._clear_agent_states())', 'replace': 'clear_all.triggered.connect(lambda: None)'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_badge_opens_notifications_and_keyboard_can_clear_all",
        "observed_diagnostic": "______ test_badge_opens_notifications_and_keyboard_can_clear_all[False] _______",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "0ac50da5e2246e3918c5368cc03c611697b9aa1eef683cb460e6a033277dbeb4"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
          }
        ]
      },
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-NTF-newer-DELIVERY",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "tests/test_app_m7.py::test_an_old_menu_action_cannot_clear_a_new_state_with_the_same_timestamp"
      ],
      "method": "Isolated harness: green, intended assertion after the injected defect, exact byte restoration, restored green. Distinct-payload handling and frozen-clock action identity are both exercised.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': '(revision is None or self._agent_revisions.get(s) == revision)', 'replace': 'True'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "03c99213d942679aa8ea8d61dd0a2ee9181e650d9d881a97a5a93024d9e0d66a"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-NTF-close-DELIVERY",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Isolated harness: green, intended assertion after the injected defect, exact byte restoration, restored green. Distinct-payload handling and frozen-clock action identity are both exercised.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'self._mark_agents_read(source, self._agent_revisions.get(source))', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "7766e1c76d981b7ddea7a16bb45753bc0b235d3d8235beaa91dd4d7bbaf99d4d"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-NTF-distinct-DELIVERY",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_closing_an_older_alert_does_not_read_its_queued_replacement"
      ],
      "method": "Isolated harness: green, intended assertion after the injected defect, exact byte restoration, restored green. Distinct-payload handling and frozen-clock action identity are both exercised.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-final.log",
        "sha256": "1a1e0e5752ddc41c8d76716bb06f66b22acaadf45304b9036c48760bfb5dbeb0"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "473e447d976de5d1d08e7a9ad86f5a697edc116c6e1804636f97098b58ae46ac"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "ecca51937544564cd18fba64186859ae2076b8c3542efaeded4836241451201b"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "caa884c0ef93ecc140c2ec85a1085194297f8e0f21f19e2c317688317adef166"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
      "red": {
        "mutation": "{'find': 'seen = (source, event, hashlib.sha256(text.encode(\"utf-8\", \"surrogatepass\")).digest())', 'replace': 'seen = (source, event, b\"\")'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_closing_an_older_alert_does_not_read_its_queued_replacement",
        "observed_diagnostic": "______ test_closing_an_older_alert_does_not_read_its_queued_replacement _______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "fc02ff5a75135588a9a053da380f3467f64aeecf24a9dfcff07fe660bc0f5aaa"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8e1757a5b35690f0ca0acac89f8013df2663a090ca6331268c96e72dfd520643"
          }
        ]
      },
      "reason": "CodeQL identified controller/menu import cycles; shared source labels, clipboard prompts and matching-style metadata move to their owning modules. Next patch version is prepared for real upgrade validation. Fresh proof follows."
    },
    {
      "id": "NTF-E-READY-4",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Reviewed CodeQL cycle, complete caller migration, lower-module ownership, unchanged labels/prompts/style semantics, patch-version preparation and package-test preconditions. See readiness-4.txt.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/notifications/readiness-4.txt",
        "sha256": "1cb92f7d9f7e4e160c85449d8021444640512bd99368f7e2cba09c72e739b4d6"
      },
      "inputs": [
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": null,
      "reason": null
    },
    {
      "id": "NTF-E-TEST-4",
      "acceptance": [
        "NTF-READ",
        "NTF-CLEAR",
        "NTF-MENU"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "tests/test_app_m7.py",
        "tests/test_stage_features.py",
        "-k",
        "reading_an_agent or notification_menu or old_menu_action or older_alert or badge_opens or badge_takes"
      ],
      "method": "Seven real Qt cases pass after shared metadata moved to its owning modules and version 0.10.1 was prepared; notification behavior, frozen-clock revisions, distinct payloads, reminders and native/overlay keyboard/pointer controls remain correct.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/acceptance-4.log",
        "sha256": "2200cd1a93d9423b82458cccc0ac4aca8c07d1e2d409392cea5d97a194a83a0c"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": null,
      "reason": null
    },
    {
      "id": "NTF-E-NTF-read-4",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Existing isolated-copy harness: green, intended assertion failure after one defect, exact byte restoration and restored green.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-4.log",
        "sha256": "dc1484970338c9c9373be87caf2e343427b1807d3bbc22a2660cc883df52f47d"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": {
        "mutation": "{'find': 'self._read_agents.update(chosen)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "78a2855ff4be24c85f0db16b5f0d23aa8b6b5d56e6b65f627805b29f8bccc522"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "NTF-E-NTF-clear-4",
      "acceptance": [
        "NTF-CLEAR"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_notification_menu_can_read_and_reset_states_without_dismissing_reminders"
      ],
      "method": "Existing isolated-copy harness: green, intended assertion failure after one defect, exact byte restoration and restored green.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-4.log",
        "sha256": "dc1484970338c9c9373be87caf2e343427b1807d3bbc22a2660cc883df52f47d"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": {
        "mutation": "{'find': 'self.agents.pop(s, None)', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_notification_menu_can_read_and_reset_states_without_dismissing_reminders",
        "observed_diagnostic": "_ test_notification_menu_can_read_and_reset_states_without_dismissing_reminders _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "643f4423416532bd597e28fb5e91fd9faa47aae9cee520d4e4ba5d85cd7654f5"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "NTF-E-NTF-pointer-4",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_features.py::test_the_badge_takes_pointer_input_and_opens_notifications"
      ],
      "method": "Existing isolated-copy harness: green, intended assertion failure after one defect, exact byte restoration and restored green.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-4.log",
        "sha256": "dc1484970338c9c9373be87caf2e343427b1807d3bbc22a2660cc883df52f47d"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": {
        "mutation": "{'find': 'self.notifications_requested.emit(gpos.toPoint())', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_badge_takes_pointer_input_and_opens_notifications",
        "observed_diagnostic": "_________ test_the_badge_takes_pointer_input_and_opens_notifications __________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "17b78991fe4bf4eacf125564966f76b673558c34704b3a8244863c4cc04bf591"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "NTF-E-NTF-keyboard-4",
      "acceptance": [
        "NTF-MENU"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_badge_opens_notifications_and_keyboard_can_clear_all"
      ],
      "method": "Existing isolated-copy harness: green, intended assertion failure after one defect, exact byte restoration and restored green.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-4.log",
        "sha256": "dc1484970338c9c9373be87caf2e343427b1807d3bbc22a2660cc883df52f47d"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": {
        "mutation": "{'find': 'clear_all.triggered.connect(lambda: c._clear_agent_states())', 'replace': 'clear_all.triggered.connect(lambda: None)'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_badge_opens_notifications_and_keyboard_can_clear_all",
        "observed_diagnostic": "______ test_badge_opens_notifications_and_keyboard_can_clear_all[False] _______",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "19652b0379426eb3e6ab47a0928063d9c7290b75fe720d554d6b9145fb584d0a"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "NTF-E-NTF-newer-4",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "tests/test_app_m7.py::test_an_old_menu_action_cannot_clear_a_new_state_with_the_same_timestamp"
      ],
      "method": "Existing isolated-copy harness: green, intended assertion failure after one defect, exact byte restoration and restored green.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-4.log",
        "sha256": "dc1484970338c9c9373be87caf2e343427b1807d3bbc22a2660cc883df52f47d"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": {
        "mutation": "{'find': '(revision is None or self._agent_revisions.get(s) == revision)', 'replace': 'True'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "298d51d1be766ca375f4e49459eb8b9969fd9d37368a8672ecd7324d3bda72c9"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "NTF-E-NTF-close-4",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one"
      ],
      "method": "Existing isolated-copy harness: green, intended assertion failure after one defect, exact byte restoration and restored green.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-4.log",
        "sha256": "dc1484970338c9c9373be87caf2e343427b1807d3bbc22a2660cc883df52f47d"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": {
        "mutation": "{'find': 'self._mark_agents_read(source, self._agent_revisions.get(source))', 'replace': 'pass'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one",
        "observed_diagnostic": "_ test_reading_an_agent_alert_clears_its_badge_and_old_actions_cannot_read_a_new_one _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "c523adb5ec1c2cb870758c92fa16e271a04312058e1ec85d128272bb47a1fe5c"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "NTF-E-NTF-distinct-4",
      "acceptance": [
        "NTF-READ"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_closing_an_older_alert_does_not_read_its_queued_replacement"
      ],
      "method": "Existing isolated-copy harness: green, intended assertion failure after one defect, exact byte restoration and restored green.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/notifications/drills-4.log",
        "sha256": "dc1484970338c9c9373be87caf2e343427b1807d3bbc22a2660cc883df52f47d"
      },
      "inputs": [
        {
          "path": ".gitattributes",
          "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
        },
        {
          "path": "AGENTS.md",
          "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
        },
        {
          "path": "README.md",
          "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
        },
        {
          "path": "chatmon/__init__.py",
          "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
        },
        {
          "path": "chatmon/changelog.md",
          "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
        },
        {
          "path": "chatmon/styles.py",
          "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
        },
        {
          "path": "pyproject.toml",
          "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
        },
        {
          "path": "tests/drills/security-performance.json",
          "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
        }
      ],
      "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
      "red": {
        "mutation": "{'find': 'seen = (source, event, hashlib.sha256(text.encode(\"utf-8\", \"surrogatepass\")).digest())', 'replace': 'seen = (source, event, b\"\")'}",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_closing_an_older_alert_does_not_read_its_queued_replacement",
        "observed_diagnostic": "______ test_closing_an_older_alert_does_not_read_its_queued_replacement _______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "b607670cf69cf937079c401aa85e049cf43a10c88cecb8d65b31837e04e35af7"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "9acbacd0cbef78806c047d4eb55738ba28d2fa4b07c442f58377397575772704",
    "inputs": [
      {
        "path": ".gitattributes",
        "sha256": "ca46e90148f2b7ec0b58f43a35fc8e59788b70c963647488452908b190b9fa69"
      },
      {
        "path": "AGENTS.md",
        "sha256": "b93598329fc60a3e2f9dae66fdb480a65252898a469babe9777d9a17a867eaa5"
      },
      {
        "path": "CONTRIBUTING.md",
        "sha256": "1cfa1279c477407910b66157d689d664daa38905ae89622302a5066d79a9104e"
      },
      {
        "path": "README.md",
        "sha256": "42e68f7b4eef430bdc1eb71d55b6d8340356736d6228ba7104a9b8af288d46ec"
      },
      {
        "path": "chatmon/__init__.py",
        "sha256": "f8df939af97659f1dc5de672587e546b389c89189ba2bce50f190d86ab6226ba"
      },
      {
        "path": "chatmon/agents.py",
        "sha256": "a63ff5caf030242543084e348882900dcb4132746c73b87e94ebe49d4871ea43"
      },
      {
        "path": "chatmon/app.py",
        "sha256": "4b0725d54e6791240ce0aee074a15df0847a38037c0e97d2e2388963310ac1fb"
      },
      {
        "path": "chatmon/asking.py",
        "sha256": "1fd83d05c65838af7fd47789fc2217297d6cb7be1b3bf13b3eb30a8e48b1df51"
      },
      {
        "path": "chatmon/changelog.md",
        "sha256": "843af399b7c96b551bf6aa0f2eab2df05e57b6e1e87f47cb207335632f3826be"
      },
      {
        "path": "chatmon/locale/chatmon.pot",
        "sha256": "303894f635590758dc372ed4b4b51b308626bd3893874af70edc6e25e5578c47"
      },
      {
        "path": "chatmon/menus.py",
        "sha256": "347b06bbae85c68b2d5a840544569eb2be7b60ba2437c73edf5700ba6fe8e19c"
      },
      {
        "path": "chatmon/messages.py",
        "sha256": "e11af31bf4c01ec52bdee183fc1d8fd034b2213f22a5f839984a7d40e52fe305"
      },
      {
        "path": "chatmon/penguin.py",
        "sha256": "aa7e33d934dc6124bbad6a318a702657c552303dd1979a48dbdcaf7ddd896fc8"
      },
      {
        "path": "chatmon/styles.py",
        "sha256": "431939c739bdfbf9952405ae491816ba0e0014fffb82baff61abea052b28c975"
      },
      {
        "path": "pyproject.toml",
        "sha256": "b84ac9fde00370a114182b90a951fe18ddb96dc12f2e8e6f98c5b5a54c2f8b91"
      },
      {
        "path": "tests/drills/security-performance.json",
        "sha256": "cdee12d19df1626853e660f4b9150513495020bf939cf90692ee77b377e17de3"
      },
      {
        "path": "tests/test_app_m7.py",
        "sha256": "3b1d186ba8469e8c13e5df93d282ea083ca036b2b9c73c4766163c3a11a919ee"
      },
      {
        "path": "tests/test_app_smoke.py",
        "sha256": "2eb32e2e0fa0a2d56bd5875230e639ed2078344bca5d9aad360378f634b0b243"
      },
      {
        "path": "tests/test_stage_features.py",
        "sha256": "adfe8f4d981e841e65fe64b30b8e58360872b59629621f3092d84d32ce4c969d"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10"
      }
    },
    "verified_tasks": [
      "NTF-T1"
    ],
    "pending_operations": [],
    "next_action": "Finish current PR CI, package-upgrade and CodeQL checks; integrate and prune the branch; restart source version 0.10.1.",
    "source_revision": "6345e25325bdd06ad1487b0ecb6f5fc14dbffdbb"
  }
}
```
