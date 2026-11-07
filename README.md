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
| `~/.claude/history.jsonl` | Only when there are no session files |
| `~/.codex/sessions/**/*.jsonl` | Only with `--platform codex` (experimental) |

To see the exact files, run this. It prints paths and reads no log:

```bash
python3 -I skills/ai-wrapped/scripts/rewind.py --since 2026-01-01 --dry-run
```

Claude Code removes old logs, by default after 30 days. The story can only show what is still on disk. Set `cleanupPeriodDays` in your Claude Code settings to keep more for next year.

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
