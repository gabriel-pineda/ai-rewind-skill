---
name: ai-wrapped
description: Build the user's AI Wrapped 2026 (a Wrapped-style year recap) from local Claude Code logs. Computes stats offline with a bundled script and prints a shareable link. Use when the user asks for their AI Wrapped, "wrap my year", or a year-in-review of their Claude Code usage.
---

# AI Wrapped

This skill turns the user's local logs into one link that plays their year as a story. A script does all the counting. You write three short pieces of text.

## What it does and never does

- It reads log files under `~/.claude` (or `~/.codex` with `--platform codex`) only: the session files and `history.jsonl`. It also checks whether a `.git` entry exists in the project folders named in the logs.
- It uses no network. The script has no network code.
- It never puts chat text in its output. The script prints numbers, dates, model names and project folder names.
- The link holds the numbers in its query string. There is no account and no upload. The numbers reach the site only when someone opens the link.
- You must not read the log files. The script gives you all that you need.

`scripts/rewind.py` sits next to this file. Use its full path in the commands below. Use `python3 -I`, so that Python does not load code from the current folder.

## Steps

### 1. Get the numbers

```bash
python3 -I <skill-folder>/scripts/rewind.py --since 2026-01-01 --json
```

The JSON has `coverage`, `stats`, `seeds` (three plain facts), `projects`, `months` and `url`. Do not show this `url` to the user yet.

Tell the user the coverage in one line. Use the dates in `coverage`, written as day and month:

- If `coverage.fullLogsFrom` is later than `coverage.promptsFrom`: "Your prompt history starts 9 Mar. Full logs start 8 Oct, so AI-side numbers are estimates from that window, marked ~."
- If `coverage.fullLogsFrom` is null: "Your prompt history starts 9 Mar. There are no full logs, so the story has no AI-side numbers."
- Else: "Your logs start 9 Mar."

### 1b. Offer to keep full logs (ask first)

Do this step only if `coverage.fullLogsFrom` is later than `coverage.promptsFrom`, or is null.

Explain in one sentence: Claude Code deletes session files after `cleanupPeriodDays` days (30 by default), so next year's Wrapped can have exact AI-side numbers only if that number is larger.

Then ask: "Do you want me to set `cleanupPeriodDays` to 400 in `~/.claude/settings.json`?" Show the exact change:

```json
{
  "cleanupPeriodDays": 400
}
```

This adds one key. The other keys in the file stay the same. If the key exists, only its value changes.

- Make the change only after the user says yes. If the user says no or does not answer, do nothing.
- To make it, read `~/.claude/settings.json`, add or change only that key, and write valid JSON. If the file does not exist, create it with only that key.
- Logs that Claude Code has already deleted do not come back.

### 2. Ask two questions

Ask them together, in one message:

1. What first name should the story use?
2. Show real project names, or use "Project A" to "Project E"? Project names are visible to anyone who gets the link.

If the user has already answered, do not ask again.

### 3. Write the text

Use only `stats`, `seeds`, `projects` and `months`. Do not use the current conversation, and do not read any log.

- **Roast** (`--roast`): one sentence, at most 140 characters. Build it from the seeds. Make it funny and kind. Attack the habit, never the person.
- **Compliment** (`--compliment`): one kind sentence, at most 100 characters.
- **Moments** (`--moments`): up to five items in the form `Mon|one short line`, joined by `;`. Each line has at most 70 characters. Use only the facts in `months`, for example `Mar|412 messages, most of them for app.` Use the months in order.
- A number in `coverage.estimated` is an estimate. If you use it, say "about", for example "about 48,000 words".

Rules for all three:

- Never quote or copy a message from the user.
- Do not name people, companies, customers or file contents.
- If the user chose anonymous projects, use only the "Project A" style of name.
- Do not use `|`, `;` or `/` in a moment.
- Plain text only. The site removes emoji.

### 4. Build the final link

Run the script again with the answers and your text. The script encodes the URL. Never build or edit the URL by hand.

```bash
python3 -I <skill-folder>/scripts/rewind.py --since 2026-01-01 \
  --name "Ana" \
  --roast "..." \
  --compliment "..." \
  --moments "Mar|...;Jun|..."
```

Add `--anon` if the user chose anonymous projects. Add `--persona-name "..."` only if the user wants a custom persona name.

### 5. Give the link to the user

Reply with the link as a markdown link and this one line:

`[Play my AI Wrapped](URL)`

Open it to play. The link holds your numbers; share it if you like.

## Troubleshooting

- **Exit code 2, no sessions:** the logs have no prompts in that date range. Try another range with `--since` and `--until`, or point to another folder with `--claude-dir`.
- **Another year:** pass `--since 2025-01-01 --until 2025-12-31`. The story shows the year of `--since`.
- **Wrong hours or days:** pass the zone with `--tz Europe/London`.
- **Check what it reads:** `--dry-run` prints the file paths and reads no log.
- **"since March" or a ~ in the story:** that is the coverage. Prompt history goes back further than the full logs. See step 1.
- **Codex:** `--platform codex` reads `~/.codex/sessions` when it exists. This is experimental.

Unofficial. Not affiliated with Anthropic or OpenAI.
