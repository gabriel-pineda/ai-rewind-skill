# ai-rewind-skill

An open-source skill that builds your AI Wrapped, a Wrapped-style story of your year with your AI. It counts on your machine and gives you one link. Your chat text never leaves your computer.

```bash
npx skills add gabriel-pineda/ai-rewind-skill
```

Then ask Claude Code: **make my AI Wrapped**.

Claude runs the script, asks for your first name, writes a short roast from the numbers, and gives you the link. Open it to play. Share it if you like.

## What it reads

| Reads | Why |
| --- | --- |
| `~/.claude/projects/*/*.jsonl` | Your sessions: timestamps, counts, models, project folders |
| `~/.claude/history.jsonl` | Every prompt you typed, with its time, folder and session. The script counts them and keeps no text |
| `~/.codex/sessions/**/*.jsonl` | Only with `--platform codex` (experimental) |

To see the exact files, run this. It prints paths and reads no log:

```bash
python3 -I skills/ai-wrapped/scripts/rewind.py --since 2026-01-01 --dry-run
```

### Why some numbers have a ~

Claude Code deletes old session files, by default after 30 days (the `cleanupPeriodDays` setting). It keeps `history.jsonl`, which has every prompt you typed but no replies. So the script reads both:

- Your side (conversations, messages, days, streak, hours, thank-yous, projects) is exact for the full range. It counts each prompt once: a history line within 5 seconds of a prompt in a session file of the same session is the same prompt.
- The AI side (AI words, "absolutely right", tokens) exists only in the session files. The script measures it per prompt in those files and multiplies by all your prompts. The link shows it as a range, and the story marks it with ~.

`--json` has a `coverage` block with the dates: `promptsFrom` (history start) and `fullLogsFrom` (session files start). Claude tells you both in one line.

To keep full logs for next year, set `"cleanupPeriodDays": 400` in `~/.claude/settings.json`. The skill offers to do this and asks first.

## Privacy

- No network. The script has no network code, and a test checks that.
- No chat text in the output. The script prints numbers, dates, model names and project folder names.
- `--anon` shows Project A to E, not folder names.
- The link carries the numbers in its query string. There is no database. The site gets the numbers only when someone opens the link, and the site host keeps request logs for a short time. Anyone with the link can see the numbers.
- Claude writes the roast, the compliment and the moments from the numbers only. Read them before you share.

## Run it without the skill

```bash
python3 -I skills/ai-wrapped/scripts/rewind.py --since 2026-01-01 --name Ana --anon
```

The flags, the JSON output and the rule for each stat are in [skills/ai-wrapped/scripts/README.md](skills/ai-wrapped/scripts/README.md).

## Codex

`--platform codex` reads `~/.codex/sessions`. It is experimental. It has been tested only with synthetic files, because the file format has no public specification.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff
.venv/bin/pytest -q
.venv/bin/ruff check .
```

The fixtures in `tests/fixtures` are invented. `tests/make_fixtures.py` writes them. Never add real logs.

Unofficial. Not affiliated with Anthropic or OpenAI. MIT license.
