# rewind.py

Reads local logs, counts things, prints one link. Python 3.9 or newer, standard library only, no network.

```bash
python3 -I rewind.py --since 2026-01-01 --dry-run   # the files it would read
python3 -I rewind.py --since 2026-01-01             # the link
python3 -I rewind.py --since 2026-01-01 --json      # stats, seeds and projects
```

## Flags

| Flag | Meaning | Default |
| --- | --- | --- |
| `--since`, `--until` | Date range, `YYYY-MM-DD`, local time. The story shows the year of `--since`. | 2026-01-01 to 2026-12-31 |
| `--platform` | `claude-code` or `codex` (experimental) | `claude-code` |
| `--claude-dir`, `--codex-dir` | The log folder. Both names set the same value. | `~/.claude` or `~/.codex` |
| `--tz` | IANA time zone, for example `Europe/London` | The system zone |
| `--json` | Print the report, not only the link | Off |
| `--name` | First name, 24 characters | None |
| `--anon` | Show Project A to E, not folder names | Off |
| `--roast` | Roast text, 140 characters | None |
| `--compliment` | Compliment text, 100 characters | None |
| `--moments` | `Jan\|text;Mar\|text`, up to 5, 70 characters each | None |
| `--persona-name` | Custom persona name, 32 characters | From `persona.json` |
| `--site` | Site origin for the link | `DEFAULT_SITE` in `rewind.py` |
| `--dry-run` | Print the file paths, then stop | Off |
| `--version` | Print the version | |

Exit codes: 0 means success. 2 means no sessions in range, a bad flag or an unknown zone. If `history.jsonl` has no `display` field (an older Claude Code), the script prints a note on stderr and uses the session files only.

## Sources

For Claude Code the script always reads two sources and merges them:

1. The session files, `projects/*/*.jsonl`. They hold prompts and replies, but Claude Code deletes them after `cleanupPeriodDays` (30 by default). The days they cover are the **window**.
2. `history.jsonl`. One line per prompt: `display`, `timestamp` (ms), `project`, `sessionId`. Claude Code keeps it. It has no replies.

The session files go first. Then each history line is added unless the same `sessionId` has a session-file prompt within 5 seconds. Slash commands (`/`) and shell lines (`!`) in history are not prompts.

All human-side stats use the merged prompts, so they are exact for the full range. AI-side stats (`wordsAi`, `absolutelyRight`, `greatQuestions`, `tokensOut`) exist only in the window. When history adds prompts, the script scales them: the count in the window, divided by the window prompts, times all prompts. The URL then carries a range of 15 percent each side (`wa=40-55`), which the site reads as an estimate. A range of one number is `~N`. Ratios (tools per assistant message) and the models list come from the window unscaled.

## Output

The default output is one URL. Its query carries `m=receipts&a=0&src=skill`. The format is the URL spec of the web app: canonical key order, `URLSearchParams` encoding, and at most 1,500 characters in the query. If the text is too long, the script shortens `mo`, then `ex`, `ro`, `co`, `pv` and `pn`. The script never writes `ex` (examples of what you asked are chat text); the key is there so that the encoder matches the web one.

When history starts before the session files, the URL also carries `lf` (prompts from, `YYYY-MM-DD`) and `ff` (full logs from). With history only, it carries `lf` only.

`--json` prints this object:

```json
{
  "skill": "1.1.0",
  "range": { "since": "", "until": "", "firstDay": "", "lastDay": "" },
  "coverage": {
    "promptsFrom": "2026-03-09", "promptsTo": "", "fullLogsFrom": "2026-10-08", "fullLogsTo": "",
    "transcriptFiles": 0, "historyFile": true, "historyLines": 0, "merged": 0, "duplicates": 0,
    "windowMessages": 0,
    "estimated": { "wordsAi": { "value": 0, "lo": 0, "hi": 0, "window": 0 } }
  },
  "stats": { "conversations": 0, "messages": 0, "persona": "BDSP" },
  "seeds": ["three plain facts"],
  "projects": [{ "name": "", "share": 0 }],
  "months": [{ "month": "Mar", "messages": 0, "activeDays": 0, "topProject": "" }],
  "url": ""
}
```

`coverage.historyLines` is the number of history prompts in range, `merged` the ones added, and `duplicates` the ones that the session files already had. `estimated` is empty when nothing is scaled. In `stats`, a scaled field holds the estimate.

## What counts

| Stat | Rule |
| --- | --- |
| Conversation | One `sessionId` with at least one human message in range, from a session file or from `history.jsonl`. |
| Human message | A `user` record with a text part. Not meta, sidechain, compaction summary, tool result, slash command output, shell output or interrupt notice. If `origin.kind` exists, it must be `human`. |
| Assistant message | One unique `message.id`, across all the log lines that share it. Subagent files and sidechain records do not count. |
| Duplicates | A resumed session copies old records into a new file. A record `uuid` counts once. A history line within 5 seconds of a session-file prompt of the same session counts once. |
| Active days, streak | Local dates with a human message. Longest run of consecutive dates. |
| Latest hour | Hours before 06:00 count as later than 23:59. |
| Typical hour | The most common hour. A tie goes to the later hour. |
| Night share | Percent of human messages from 00:00 to 05:59. |
| Thank-yous, sorrys | Human messages that match the word list. One message counts once. |
| Absolutely right | Assistant text parts that match the phrase. One part counts once. |
| Words | Whitespace-split words of human text and assistant text. Thinking and tool input do not count. |
| Tokens | The sum of the highest `output_tokens` of each assistant message. |
| Project | The nearest parent folder with `.git`, else the first folder under `~/Documents` or `~`. |
| Persona | Tool uses per assistant message at or above 0.6 gives B, else T. Night share at or above 25, or typical hour at or above 22, gives N, else D. Median human words at or above 40 gives V, else S. Thank-yous per 100 messages at or above 2 gives P, else R. |

The rank is a guess, not a measurement. It comes from human messages per active day:

| Messages per active day | Rank |
| --- | --- |
| 150 or more | Top 1% |
| 100 | Top 2% |
| 60 | Top 5% |
| 40 | Top 10% |
| 25 | Top 20% |
| 15 | Top 35% |
| 8 | Top 50% |
| 3 | Top 70% |
| Less | Top 90% |

The power title comes from the human message count: Rookie, Adventurer (200), Ninja (1,000), Elite Class (2,500), Sage Mode (5,000), Super Saiyan (10,000), God Mode (20,000).

## Privacy

- No `socket`, `urllib` or `http` import. `tests/test_privacy.py` checks this with the syntax tree.
- Output holds no message text. A test checks every 13-character piece of every fixture message.
- `--dry-run` prints paths and reads no log.
- It reads only under the log folder. It does not follow symbolic links there. Outside that folder it only checks whether `.git` exists.
- The only free text in the URL is the project names (removed by `--anon`) and the text flags.

## Files

`persona.json` is a copy of `src/lib/persona.json` in the web repo. Keep the two the same.
