"""M7's red drills, written into drill-spec.json beside the CI ones: python drills_m7.py

Each drill names the requirement it guards, a defect put into a production file (or the shared test harness, for
CI-01), and the tests that must fail for the intended reason. `--check` only says whether each find occurs exactly
once in the working tree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # docs/delivery/reports/m7 -> the repository
A = "chatmon/app.py"
ANS, REM, M7, SW, CW = "tests/test_app_answers.py", "tests/test_app_reminders.py", "tests/test_app_m7.py", "tests/test_settingswin.py", "tests/test_chatswin.py"


def d(did, req, file, find, replace, tests):
    tests = [tests] if isinstance(tests, str) else tests
    return {"id": did, "requirement": req, "file": file, "find": find, "replace": replace, "test": tests,
            "expect": [t.split("::")[1] for t in tests]}


DRILLS = [
    d("M7-01-only-newest-piece", "AC-01-1", A, "first, q.partial = not q.partial, q.partial + text", "first, q.partial = not q.partial, text",
      f"{ANS}::test_an_answer_shows_as_it_streams_in_and_survives_the_box_being_drawn_again"),
    d("M7-01-closing-drops", "AC-01-2", A, "        # A question on its way carries on: its answer is kept in the chat, and a bubble says it came (_answered).",
      "        self.asker.cancel()\n        self.questions.drop()", f"{ANS}::test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came"),
    d("M7-01-answered-unsaid", "AC-01-2", A, 'self.say(f"{label or \'The AI\'} answered", buttons=[("Read", self._read_answer)]',
      'self._read_aloud(f"{label or \'The AI\'} answered", buttons=[("Read", self._read_answer)]',
      f"{ANS}::test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came"),
    d("M7-01-stop-loses-what-came", "AC-01-3", A, "        if q.partial.strip():\n", "        if False:\n",
      f"{ANS}::test_the_box_says_who_is_answering_and_stop_ends_it"),
    d("M7-01-no-busy", "AC-01-3", A, "        self.ask_box.set_busy(brain.label, q.started)\n", "\n",
      f"{ANS}::test_the_box_says_who_is_answering_and_stop_ends_it"),
    d("M7-02-no-next-brain", "AC-02-1", A, "        if other is not None:\n            buttons.append", "        if False:\n            buttons.append",
      f"{ANS}::test_a_failed_question_offers_to_try_again_ask_the_next_brain_or_open_settings"),
    d("M7-02-fallback-every-time", "AC-02-2", A, "        if self._fallback_told == picked:\n", "        if False:\n",
      f"{ANS}::test_a_brain_picked_that_cant_answer_is_announced_once_for_that_pick"),
    d("M7-02-welcome-without-brain", "AC-02-3", A, 'line = f"Your questions go to **{brain.label}**; **Brain** in my menu picks another."', 'line = ""',
      f"{ANS}::test_after_naming_it_says_which_brain_will_answer_or_how_to_set_one_up"),
    d("M7-02-server-not-kept", "AC-02-4", A, '        self.state.set("trusted_servers", brains.confirmed_servers())\n', "\n",
      f"{ANS}::test_a_model_server_that_isnt_yours_is_offered_once_and_kept_once_confirmed"),
    d("M7-03-key-not-saved", "AC-03-1", A, "            problem = keychain.set(name, key)\n", "            problem = None\n",
      f"{M7}::test_a_key_saved_in_settings_goes_to_the_keychain_only"),
    d("M7-03-key-not-handed-back", "AC-03-1", "chatmon/settingswin.py", '"api_key": (self._brain_name(), key) if key and self._brain_name() in self._keys else None,',
      '"api_key": None,', f"{SW}::test_the_key_field_shows_only_for_an_api_brain_and_a_key_typed_is_handed_back_once"),
    d("M7-03-test-without-typed-key", "AC-03-1", "chatmon/settingswin.py",
      'self.test_requested.emit(name, self.key.text().strip() if name in self._keys else "")', 'self.test_requested.emit(name, "")',
      f"{SW}::test_test_and_remove_key_ask_the_companion"),
    d("M7-03-text-scale-unapplied", "AC-03-2", A, "        self.stage.bubble.set_text_scale(scale)\n", "\n",
      f"{M7}::test_text_size_and_how_long_bubbles_stay_apply_at_once"),
    d("M7-03-cues-not-handed-back", "AC-03-2", "chatmon/settingswin.py", '"cues": {name: box.isChecked() for name, box in self.cues.items()},', '"cues": {},',
      f"{SW}::test_the_accessibility_tab_hands_back_what_was_set"),
    d("M7-03-snooze-from-breaks", "AC-03-3", A, '        return float(self.config["reminders"]["snooze_minutes"])', '        return float(self.config["breaks"]["snooze_minutes"])',
      f"{REM}::test_reminders_snooze_by_their_own_setting_not_the_breaks"),
    d("M7-03-interval-needs-restart", "AC-03-4", A, "        self._updates_timer.setInterval(", "        (lambda ms: None)(",
      f"{M7}::test_the_update_check_interval_applies_without_a_restart"),
    d("M7-03-battery-order-window", "AC-03-5", "chatmon/settingswin.py", "self.battery_critical.setMaximum(max(1, low - 1) if low else 50)",
      "self.battery_critical.setMaximum(50)", f"{SW}::test_reminders_have_their_own_snooze_and_almost_empty_stays_below_low"),
    d("M7-03-battery-order-file", "AC-03-5", "chatmon/settings.py", '0 < heads_up.get("battery_low", 0) <= heads_up.get("battery_critical", 0)', "False",
      "tests/test_settings.py::test_almost_empty_stays_below_low_in_the_settings_file"),
    d("M7-04-done-keeps-it", "AC-04-1", A, "        if self.reminders.acknowledge(rid, time.time()):", "        if self.reminders.get(rid):",
      f"{REM}::test_a_reminder_that_comes_due_waits_until_done_or_snoozed"),
    d("M7-04-later-missing", "AC-04-1", A, '            ("Later…", partial(self._offer_snoozes, r.id)),\n', "\n",
      f"{REM}::test_a_repeating_reminder_moves_on_when_done_and_later_offers_every_snooze"),
    d("M7-04-not-restored", "AC-04-2", A, "        self._show_due_reminders()  # fired and not yet done or snoozed", "        pass  # fired and not yet done or snoozed",
      f"{REM}::test_reminders_fired_and_not_done_come_back_at_the_next_start"),
    d("M7-04-focus-held-forever", "AC-04-2", A, '        for r in [r for r in due if r.kind == "focus"]:\n', '        for r in []:\n',
      f"{REM}::test_reminders_fired_and_not_done_come_back_at_the_next_start"),
    d("M7-04-edit-ignores-time", "AC-04-3", A, '            changes["when"] = when.due.timestamp()\n', "            pass\n",
      f"{REM}::test_each_reminder_in_the_menu_can_be_changed_repeated_or_cancelled"),
    d("M7-04-repeat-dropped", "AC-04-4", "chatmon/commands.py", "command.kind, repeat=command.repeat)", "command.kind, repeat=None)",
      f"{REM}::test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time"),
    d("M7-04-cli-no-explanation", "AC-04-4", "chatmon/cli.py", 'why = reminders.explain(command, markdown=False) if command is not None and command.kind == "unclear" else ""',
      'why = ""', "tests/test_cli.py::test_a_reminder_it_cant_read_says_so_and_exits_2"),
    d("M7-05-no-summary", "AC-05-1", A, '        return self.messages.take(lambda m: m in held and not m.buttons)', "        return []",
      "tests/test_app_smoke.py::test_a_focus_session_holds_what_comes_on_its_own_until_its_over_then_sums_it_up"),
    d("M7-06-not-recent", "AC-06-1", A, "        self._recent.append((time.time(), message))\n", "\n", f"{M7}::test_recent_messages_are_in_the_menu_and_show_again"),
    d("M7-06-click-ignores-missed", "AC-06-2", A, "        elif self._missed and not self.stage.message_visible():", "        elif False:",
      f"{M7}::test_a_bubble_that_went_by_while_you_were_away_comes_back_with_a_click"),
    d("M7-06-dropped-not-missed", "AC-06-2", A, "self._missed += [m for m in self.messages.add(message) if m is not message]", "self.messages.add(message)",
      f"{M7}::test_plain_bubbles_the_queue_dropped_count_as_missed"),
    d("M7-07-no-tooltip", "AC-07-1", A, '        self.tray.setToolTip(f"Chatmon\\n{states}" if states else "Chatmon")', '        self.tray.setToolTip("Chatmon")',
      f"{M7}::test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you"),
    d("M7-07-no-badge", "AC-07-1", A, "            return QIcon(_with_badge(frame.pixmap) if self._tray_badge else frame.pixmap)", "            return QIcon(frame.pixmap)",
      f"{M7}::test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you"),
    d("M7-07-agents-command-is-help", "AC-07-2", "chatmon/commands.py", '"agents": _agents,', '"agents": _help,',
      f"{M7}::test_the_agents_command_says_how_each_stands"),
    d("M7-07-no-reply", "AC-07-3", A, "                            sock.write(events.reply_line(reply))", "                            pass",
      f"{M7}::test_chatmon_status_hears_the_live_states_from_the_running_chatmon"),
    d("M7-07-cli-ignores-live", "AC-07-3", "chatmon/cli.py", "    if live is not None:\n", "    if False:\n",
      "tests/test_cli.py::test_status_says_whether_its_running_the_brain_reminders_and_agents"),
    d("M7-08-text-not-attached", "AC-08-1", A, "            self._attach(lambda: attachments.from_text(payload))  # attached, however short", "            pass  # attached, however short",
      f"{M7}::test_quick_actions_attach_the_clipboard_only_when_chosen_and_type_the_prompt"),
    d("M7-09-no-search-inside", "AC-09-1", "chatmon/chatswin.py", "                inside.add(listed.id)\n", "                pass\n",
      f"{CW}::test_the_window_lists_every_chat_and_searches_titles_then_words_inside"),
    d("M7-09-no-all-chats", "AC-09-1", "chatmon/menus.py", '    sub.addAction("All chats…", c.open_chats)\n', "\n",
      "tests/test_app_smoke.py::test_the_menu_lists_the_newest_chats_and_all_chats_opens_the_window"),
    d("M7-09-answer-not-by", "AC-09-2", A, 'self.chat.add(chats.Message("assistant", answer, brain=label, by=name))', 'self.chat.add(chats.Message("assistant", answer, brain=label))',
      f"{ANS}::test_a_chat_keeps_its_brain_and_another_brain_can_answer_the_last_question"),
    d("M7-09-chat-brain-ignored", "AC-09-2", A, 'picked, prefer = self.config["ai"]["brain"], self.state.get("brain"), self.chat.brain or None',
      'picked, prefer = self.config["ai"]["brain"], self.state.get("brain"), None', f"{ANS}::test_carrying_a_chat_on_asks_its_own_brain_before_the_one_picked"),
    d("M7-09-restore-not-reread", "AC-09-3", A, '        self.reminders = reminders.ReminderBook.from_list(self.state.get("reminders", []))\n        self._sync_focus_hold()\n        self.reload(quietly=True)',
      '        self.reload(quietly=True)', f"{M7}::test_back_up_and_bring_back_from_settings"),
    d("M7-09-listing-rereads", "AC-09-4", "chatmon/chats.py", "            if seen is None or seen[:2] != (info.st_mtime_ns, info.st_size):", "            if True:",
      f"{CW}::test_the_listing_reads_each_file_once_while_it_doesnt_change"),
    d("M7-10-copy-unwired", "AC-10-1", A, "        self.ask_box.copy_requested.connect(self._copy)\n", "\n", f"{M7}::test_copy_puts_an_answer_on_the_clipboard"),
    d("M7-10-ctrl-number-ignored", "AC-10-2", A, "                return self._press_bubble_button(key - Qt.Key.Key_1.value)", "                return False",
      f"{M7}::test_ctrl_and_a_number_press_a_bubbles_buttons_while_the_box_is_open"),
    d("M7-10-expired-unanswerable", "AC-10-3", A, "            self._answerable = (now, list(message.buttons))\n", "            pass\n",
      f"{M7}::test_a_buttons_label_typed_after_its_bubble_went_is_answerable_for_a_while"),
    d("M7-11-lock-keeps-drawing", "AC-11-1", A, "            self.stage.set_drawing(not locked)  # nothing is drawn while nobody can see it", "            pass",
      f"{M7}::test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box"),
    d("M7-11-box-ignores-saver", "AC-11-1", A, "        self.ask_box.set_power_saving(on)\n", "\n",
      f"{M7}::test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box"),
    d("M7-11-palette-ignored", "AC-11-2", A, "            QTimer.singleShot(0, self._palette_changed)\n", "            pass\n",
      f"{M7}::test_the_desktops_colours_and_reduced_motion_apply_at_once"),
    d("M7-11-sound-in-quiet", "AC-11-3", A, "        if self._quiet or self.reminders.focus() is not None:\n            return False\n        return self._play(name)",
      "        return self._play(name)", f"{M7}::test_sounds_play_for_alerts_only_unless_turned_on_and_never_in_quiet_or_focus"),
    d("M7-12-carry-on-forgotten", "AC-12-1", A, "            self._set_aside = set_aside\n", "            pass\n",
      f"{M7}::test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back"),
    d("M7-12-drops-question", "AC-12-1", A, "and bool(self.chat.messages) and self.questions.current is None and", "and bool(self.chat.messages) and",
      f"{M7}::test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back"),
    d("M7-13-hello-every-unlock", "AC-13-1", A, '        if self.state.get("hello_day") == today.isoformat():\n            return False\n', "",
      f"{M7}::test_the_first_unlock_of_the_day_names_reminders_agents_and_updates_once"),
    d("M0-06-table-unfiltered", "AC-M0-6", "chatmon/commands.py", "        return command if command in COMMANDS else None", "        return command",
      "tests/test_commands.py::test_a_phrase_is_found_as_typed_give_or_take_case_and_punctuation"),
    d("M0-07-waits-for-brain", "AC-M0-7", A, "quick = brains.choose(self.brains, configured, picked, wait=False, prefer=prefer)",
      "quick = brains.choose(self.brains, configured, picked, wait=True, prefer=prefer)", f"{ANS}::test_asking_never_waits_on_the_screens_thread_to_find_the_brain"),
    d("M0-08-connections-unchecked", "AC-M0-8", A, '            if sys.platform == "win32" and not _client_is_me(sock):', "            if False:",
      f"{M7}::test_on_windows_each_connection_is_checked_to_be_yours"),
    d("M0-10-any-process-forward", "AC-M0-10", "chatmon/cli.py", "    target = pid if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 else ASFW_ANY",
      "    target = ASFW_ANY", "tests/test_cli.py::test_on_windows_ask_lets_only_chatmon_come_forward_before_sending"),
    d("M1B-07-files-brain-sees-all", "AC-M1B-7", A, "pairs = chat.history(brain.label, name=brain.name, own_only=guard, before=q.before)",
      "pairs = chat.history(brain.label, name=brain.name, own_only=False, before=q.before)", f"{ANS}::test_a_brain_that_reads_files_gets_only_its_own_answers_and_summaries"),
    d("M1B-09-overrides-unchecked", "AC-M1B-9", A, "            config, more = coerce(merge(config, overrides))", "            config, more = merge(config, overrides), []",
      f"{M7}::test_wrong_settings_are_named_one_by_one_and_the_rest_apply"),
    d("M1B-10-damage-unsaid", "AC-M1B-10", A, "        for problem in (self.state.problem, self.memory.problem):", "        for problem in ():",
      f"{M7}::test_a_damaged_file_recovered_at_start_is_said"),
    d("M2-more-unwired", "AC-M2-1", A, "        self.stage.bubble.on_more = self._show_more", "        pass",
      f"{M7}::test_more_opens_the_whole_text_and_the_box_remembers_its_size_and_says_shift_enter"),
    d("M5-chat-times-12h", "AC-M5-1", "chatmon/chats.py", '        return f"today {localefmt.time_of_day(d)}"',
      '        return f"today {(d.hour % 12) or 12}:{d.minute:02d} {\'AM\' if d.hour < 12 else \'PM\'}"', f"{CW}::test_chat_times_follow_the_locale"),
    d("M7-07-no-stage-badge", "AC-07-1", A, "        self.stage.set_badge(sum(1 for state, _ in self.agents.values() if state == \"working\"), waiting)\n", "\n",
      f"{M7}::test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you"),
    d("M7-11-player-never-quiet", "AC-11-3", A, "quiet=lambda: self._quiet or self.reminders.focus() is not None)", "quiet=lambda: False)",
      f"{M7}::test_the_player_is_told_the_settings_and_asks_whether_its_a_time_for_quiet"),
    d("M7-11-hotkey-unregistered", "AC-11-4", A, "        error = hotkey.register(sequence, self._hotkey_pressed, failed=self._hotkey_failed)", "        error = None",
      f"{M7}::test_the_hotkey_is_registered_from_settings_toggles_the_box_and_a_problem_is_said_once"),
    d("M7-11-balloon-not-toast", "AC-11-4", A, "            if wintoast.show(title, text, list(buttons), scenario) is not None:", "            if False:",
      f"{M7}::test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons"),
    d("M7-11-box-always-hosted", "AC-11-5", A, "            self.stage.set_hosting(not self._ask_box_as_window())", "            pass",
      f"{M7}::test_the_ask_box_is_a_window_with_a_screen_reader_where_the_overlay_draws_it"),
    d("M7-11-follow-ignored", "AC-11-5", A, "        self.stage.follow_pointer_screen(bool(self.config[\"follow_screen\"]))", "        self.stage.follow_pointer_screen(False)",
      f"{M7}::test_follow_me_across_monitors_is_a_setting"),
    d("M7-11-magnifier-not-placed", "AC-11-6", A, "        wincaret.place(self.stage.native_window(),", "        (lambda *a: None)(self.stage.native_window(),",
      f"{M7}::test_on_windows_magnifier_goes_to_each_bubble_and_lets_go_when_it_closes"),
]


def main() -> int:
    spec_path = HERE / "drill-spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    ci = [x for x in spec["drills"] if x["id"].startswith("CI-")]
    bad = 0
    for drill in DRILLS:
        raw = (ROOT / drill["file"]).read_bytes().decode("utf-8")
        if "\r\n" in raw:  # the harness matches the file's own bytes: its line endings, as checked out now
            drill["find"], drill["replace"] = drill["find"].replace("\n", "\r\n"), drill["replace"].replace("\n", "\r\n")
        found = raw.count(drill["find"])
        if found != 1:
            bad += 1
            print(f"{drill['id']}: find occurs {found} times in {drill['file']}")
    if "--check" in sys.argv:
        return 1 if bad else 0
    spec["drills"] = ci + DRILLS
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(spec['drills'])} drills written ({bad} with a find that doesn't occur once)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
