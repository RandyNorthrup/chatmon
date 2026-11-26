# Dismissible agent notifications

The number beside the companion counts working agents and unread needs-you alerts. Existing alert closing only ended the bubble; waiting state could keep its count forever. Preserve the live waiting status after reading, expose a separate manual reset for missing terminal hooks, and allow later hooks to notify again.

Reuse `Companion.agents`, `MessageQueue.take/withdraw`, `Menus` and the native/stage popup paths. Keep reminder Done/Snooze behavior. The active security/performance audit edits are this session's work and must be preserved. No new runtime dependency or notification subsystem is needed.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "NOTIFICATIONS",
    "title": "Dismissible agent notifications and status badges",
    "scope_revision": 2,
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
        }
      ],
      "status": "verified",
      "evidence": [
        "NTF-E-READY-2",
        "NTF-E-TEST",
        "NTF-E-NTF-read",
        "NTF-E-NTF-clear",
        "NTF-E-NTF-pointer",
        "NTF-E-NTF-keyboard",
        "NTF-E-NTF-newer",
        "NTF-E-NTF-close"
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
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "NTF-E-TEST",
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
      "reason": null
    },
    {
      "id": "NTF-E-NTF-read",
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
      "reason": null
    },
    {
      "id": "NTF-E-NTF-clear",
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
      "reason": null
    },
    {
      "id": "NTF-E-NTF-pointer",
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
      "reason": null
    },
    {
      "id": "NTF-E-NTF-keyboard",
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
      "reason": null
    },
    {
      "id": "NTF-E-NTF-newer",
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
      "reason": null
    },
    {
      "id": "NTF-E-NTF-close",
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
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "a18554aa6ac16495643c55ef980af58a88fe1a2179c6dea9621e7e045a7ddaf7",
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
    "next_action": "Review the changes and restart updated Chatmon; run the full hosted platform matrix before release.",
    "source_revision": "02de8ed125781d93b44b9cb8035bcafbf7ba326e"
  }
}
```
