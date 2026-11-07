---
name: ai-wrapped
description: Build the user's AI Wrapped 2026 (a Wrapped-style year recap) from local Claude Code logs. Computes stats offline with a bundled script and prints a shareable link. Use when the user asks for their AI Wrapped, "wrap my year", or a year-in-review of their Claude Code usage.
---

# AI Wrapped

This skill turns the user's local logs into one link that plays their year as a story. A script does all the counting. You write three short pieces of text.

## What it does and never does

- It reads log files under `~/.claude` only. It also checks whether a `.git` entry exists in the project folders named in the logs.
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

The JSON has `stats`, `seeds` (three plain facts), `projects`, `months` and `url`. Do not show this `url` to the user yet.

If `range.firstDay` is much later than January, tell the user that the logs start on that day. Claude Code removes old logs, by default after 30 days.

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
- **Codex:** `--platform codex` reads `~/.codex/sessions` when it exists. This is experimental.

Unofficial. Not affiliated with Anthropic or OpenAI.
