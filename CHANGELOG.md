# Changelog

## 1.1.0 (unreleased)

- Always reads `~/.claude/history.jsonl` together with the session files. Claude Code deletes session files after
  30 days by default, but history.jsonl keeps every prompt. Human-side numbers are now exact for the full range.
- Merge without double counting: a history line within 5 seconds of a session-file prompt of the same session is
  the same prompt. Conversations are unique session ids across both sources.
- AI-side numbers (AI words, "absolutely right", tokens) come from the session-file window only. When history adds
  prompts, they are scaled per prompt and sent as a range of 15 percent each side (`wa=40-55`), which the site
  shows with ~. Seeds say "about".
- New `coverage` block in `--json`: promptsFrom, promptsTo, fullLogsFrom, fullLogsTo, transcriptFiles,
  historyFile, historyLines, merged, duplicates, windowMessages, estimated.
- New URL keys `lf` (prompts from) and `ff` (full logs from). New key `ex` in the encoder; the skill never fills it.
- A note on stderr when history.jsonl has no `display` field (an older Claude Code).
- SKILL.md: a one-line coverage sentence, and an offer (asked first, never done without a yes) to set
  `cleanupPeriodDays` to 400 so next year has full logs.
- Tests: a merge fixture (history from March, session files for October) and checks for exact numbers, dedupe,
  ranges and privacy.

## 1.0.0 (unreleased)

- First version of the `ai-wrapped` skill and `rewind.py`.
- Stats from Claude Code logs. Codex support is experimental.
- URL output in the canonical form of the web app.
- Privacy tests: no network imports, no message text in the output.
- Text cleaning matches the web codec exactly: percent escapes decode, JavaScript whitespace rules, and a name
  with no letter (or a placeholder such as null) is dropped. Long names are cut with no ellipsis.
- Seeds use the right plural: "1 message on Apr 10", "Said thanks 1 time".
- Parity tests with the web repo on shared fixtures: personas, text cleaning and the full report.
