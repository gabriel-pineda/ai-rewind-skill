#!/usr/bin/env python3
"""Build an AI Wrapped link from local Claude Code or Codex logs.

Standard library only. No network. The script reads log files, counts things and
prints one URL. The only free text it can put in that URL is project folder names
(removed by --anon) and the text you pass with the flags.

See README.md next to this file for the flags, the output and the privacy rules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

VERSION = "1.0.0"
# Change this to the final host at domain cut-over.
DEFAULT_SITE = "https://ai-rewind.vercel.app"

DEFAULT_SINCE = "2026-01-01"
DEFAULT_UNTIL = "2026-12-31"

# Same numbers as LIMITS in the web codec (src/lib/codec/schema.ts).
ENCODE_MAX = 1500
MAX_NAME = 24
MAX_PERSONA_NAME = 32
MAX_THEMES = 5
MAX_THEME_NAME = 18
MAX_MOMENTS = 5
MAX_MOMENT_TEXT = 70
MAX_ROAST = 140
MAX_COMPLIMENT = 100
MAX_POWER = 24
MAX_MODELS = 3
MAX_DAYS = 366
TRUNCATE_ORDER = ("mo", "ro", "co", "pv", "pn")
# Same steps as encodeRewind: cut the text to 140, 132, ... 28 characters, then drop the field.
SHORTEN_START = 140
SHORTEN_FLOOR = 24
SHORTEN_STEP = 8
LAST_RESORT = TRUNCATE_ORDER + ("t", "pl", "md")
CANONICAL_ORDER = (
    "v p m a y n c mg d s sr bd bm lh th ns wu wa t ty so ar pc pn pv mo ro co rk pl tk md src"
).split()

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Human messages per active day -> rank percent. A fixed guess, not a measurement.
RANK_CURVE = ((150, 1), (100, 2), (60, 5), (40, 10), (25, 20), (15, 35), (8, 50), (3, 70), (0, 90))
# Human messages -> power title. Same names as git-wrapped.
POWER_TIERS = (
    (20000, "God Mode"),
    (10000, "Super Saiyan"),
    (5000, "Sage Mode"),
    (2500, "Elite Class"),
    (1000, "Ninja"),
    (200, "Adventurer"),
    (0, "Rookie"),
)

SESSION_GAP = timedelta(minutes=30)

THANKS_RE = re.compile(r"\b(?:thanks|thank you|thx|ty|cheers|appreciated?|legend)\b", re.I)
SORRY_RE = re.compile(r"\b(?:sorry|my bad|apologies)\b", re.I)
FIX_RE = re.compile(r"\bfix(?:es|ed|ing)?\b", re.I)
RIGHT_RE = re.compile(
    r"\byou['\N{RIGHT SINGLE QUOTATION MARK}]?re (?:absolutely|completely|totally|exactly) right\b", re.I
)
GREAT_RE = re.compile(r"\bgreat question\b", re.I)
# A regex search is slow on long text. It runs only when one of these is in the lower-case text.
THANKS_HINTS = ("thank", "thx", "ty", "cheers", "appreciat", "legend")
SORRY_HINTS = ("sorry", "my bad", "apolog")
FIX_HINTS = ("fix",)
RIGHT_HINTS = ("right",)
GREAT_HINTS = ("great question",)

# Lines that hold neither of these are not messages. The check runs before json.loads.
USER_MARK = b'"type":"user"'
ASSISTANT_MARK = b'"type":"assistant"'
TOOL_RESULT_MARK = b'"type":"tool_result"'
SPACED_MARK = re.compile(rb'"type"\s+:\s*"(?:user|assistant)"|"type":\s+"(?:user|assistant)"')

# User-typed records in the log that a person did not write as a prompt.
NOISE_PREFIXES = (
    "<command-",
    "<local-command",
    "<bash-",
    "<task-notification",
    "<system-reminder",
    "<user-prompt-submit-hook",
    "[Request interrupted",
    "Caveat:",
    "This session is being continued",
)
CODEX_NOISE_PREFIXES = ("<environment_context", "<user_instructions", "<turn_aborted")

STAMP_RE = re.compile(r"^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)(?:\.\d+)?(Z|[+-]\d\d:?\d\d)?$")

FORM_SAFE = frozenset(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789*-._")
ELLIPSIS = chr(0x2026)
# Emoji, flags, keycaps and variation selectors, as code point ranges. Close to Extended_Pictographic.
EMOJI_RANGES = (
    (0xa9, 0xa9),
    (0xae, 0xae),
    (0x203c, 0x203c),
    (0x2049, 0x2049),
    (0x20e3, 0x20e3),
    (0x2122, 0x2122),
    (0x2139, 0x2139),
    (0x2194, 0x21aa),
    (0x231a, 0x23ff),
    (0x24c2, 0x24c2),
    (0x25aa, 0x25fe),
    (0x2600, 0x27bf),
    (0x2934, 0x2935),
    (0x2b05, 0x2b55),
    (0x3030, 0x3030),
    (0x303d, 0x303d),
    (0x3297, 0x3299),
    (0xfe00, 0xfe0f),
    (0x1f000, 0x1ffff),
)
EMOJI_RE = re.compile("[" + "".join(f"{chr(low)}-{chr(high)}" for low, high in EMOJI_RANGES) + "]")
QUOTES = {
    chr(0x22): chr(0x22),
    chr(0x27): chr(0x27),
    chr(0x60): chr(0x60),
    chr(0x201c): chr(0x201d),
    chr(0x2018): chr(0x2019),
    chr(0x201e): chr(0x201d),
    chr(0xab): chr(0xbb),
}
# A model writes these when it has no value. The decoder treats them as empty.
NO_VALUE_RE = re.compile(r"^(?:null|none|nil|n/?a|unknown|undefined|tbd|\?+|-+|\N{EM DASH}+)$", re.I)
MONTH_WORD = (
    "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    "sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
MOMENT_SPLIT_RE = re.compile(rf";\s*(?=(?:{MONTH_WORD})\.?\s*[|/]\s*)", re.I)
MOMENT_RE = re.compile(rf"^({MONTH_WORD})\.?\s*[|/]\s*(.+)$", re.I)


class ScriptError(Exception):
    """An error for the user. main() prints the text and exits with code 2."""


def load_persona_table() -> dict:
    """persona.json is the same file as src/lib/persona.json in the web repo."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def round_half_up(value: float) -> int:
    """Rounds like JavaScript Math.round, not like Python round."""
    return int(value + 0.5)


# --- Time ---------------------------------------------------------------------------------------


def resolve_tz(name: Optional[str]):
    """Returns a tzinfo, or None for the system zone."""
    if not name:
        return None
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo(name)
    except Exception as error:
        raise ScriptError(f"Unknown time zone: {name}") from error


def parse_stamp(value) -> Optional[datetime]:
    """Reads an ISO timestamp or epoch milliseconds. Returns an aware datetime or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    match = STAMP_RE.match(value)
    if not match:
        return None
    year, month, day, hour, minute, second, offset = match.groups()
    zone = timezone.utc
    if offset and offset != "Z":
        digits = offset[1:].replace(":", "")
        delta = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        zone = timezone(delta if offset[0] == "+" else -delta)
    try:
        return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=zone)
    except ValueError:
        return None


def parse_day(value: str) -> date:
    try:
        return date(int(value[:4]), int(value[5:7]), int(value[8:10]))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"not a date, use YYYY-MM-DD: {value}") from error


# --- Finding files ------------------------------------------------------------------------------


def walk_jsonl(root: str) -> Iterator[str]:
    """Yields regular .jsonl files under root. Symbolic links are not followed."""
    for folder, subfolders, names in os.walk(root, followlinks=False):
        subfolders.sort()
        for name in sorted(names):
            path = os.path.join(folder, name)
            if name.endswith(".jsonl") and not os.path.islink(path):
                yield path


def claude_sessions(root: str) -> List[str]:
    """Top-level session files only: projects/<project>/<session>.jsonl. Subagent files sit deeper."""
    projects = os.path.join(root, "projects")
    found: List[str] = []
    if not os.path.isdir(projects):
        return found
    for project in sorted(os.scandir(projects), key=lambda entry: entry.name):
        if not project.is_dir(follow_symlinks=False):
            continue
        for entry in sorted(os.scandir(project.path), key=lambda item: item.name):
            if entry.name.endswith(".jsonl") and entry.is_file(follow_symlinks=False):
                found.append(entry.path)
    return found


def fresh_enough(path: str, since: date) -> bool:
    """A log cannot hold a record newer than its mtime. One spare day covers any time zone."""
    try:
        modified = datetime.fromtimestamp(os.stat(path).st_mtime, timezone.utc).date()
    except OSError:
        return False
    return modified >= since - timedelta(days=1)


def find_files(platform: str, root: str, since: date) -> Tuple[List[str], Optional[str]]:
    """Returns (session files to read, history file to use when there are no session files)."""
    if platform == "codex":
        sessions = os.path.join(root, "sessions")
        return [path for path in walk_jsonl(sessions) if fresh_enough(path, since)], None
    every = claude_sessions(root)
    if every:
        return [path for path in every if fresh_enough(path, since)], None
    history = os.path.join(root, "history.jsonl")
    return [], history if os.path.isfile(history) else None


# --- Projects -----------------------------------------------------------------------------------


class ProjectNames:
    """cwd -> project name. Looks for a .git entry, nothing more."""

    def __init__(self, home: str):
        self.home = home.rstrip("/")
        self.cache: Dict[str, str] = {}

    def name(self, cwd: Optional[str]) -> str:
        if not cwd:
            return "misc"
        if cwd not in self.cache:
            self.cache[cwd] = self.resolve(cwd)
        return self.cache[cwd]

    def resolve(self, cwd: str) -> str:
        path = cwd.split("/.claude/worktrees/")[0].rstrip("/") or "/"
        home = self.home
        probe = path
        while probe != home and probe != os.path.dirname(probe):
            if os.path.exists(os.path.join(probe, ".git")):
                return os.path.basename(probe)
            probe = os.path.dirname(probe)
        if path == home:
            return "home"
        if path.startswith(("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/")):
            return "scratch"
        for base in (os.path.join(home, "Documents"), home):
            if path.startswith(base + "/"):
                return path[len(base) + 1 :].split("/")[0]
        return os.path.basename(path) or "home"


# --- Reading records ----------------------------------------------------------------------------


def human_text(record: dict) -> Optional[str]:
    """The text of a real prompt, or None for meta, tool, subagent and system records."""
    if (
        record.get("isMeta")
        or record.get("isSidechain")
        or record.get("isCompactSummary")
        or record.get("isVisibleInTranscriptOnly")
    ):
        return None
    origin = record.get("origin")
    if isinstance(origin, dict) and origin.get("kind", "human") != "human":
        return None
    message = record.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_result":
                return None
            if kind == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        text = "\n".join(parts)
    else:
        return None
    text = text.strip()
    if not text or text.startswith(NOISE_PREFIXES):
        return None
    return text


def found(pattern, hints, text: str, lower: str) -> bool:
    return any(hint in lower for hint in hints) and pattern.search(text) is not None


def assistant_blocks(content) -> Tuple[List[str], int]:
    """Returns (text parts, tool_use count). Thinking and tool inputs are ignored."""
    if isinstance(content, str):
        return [content], 0
    texts: List[str] = []
    tools = 0
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
            elif kind == "tool_use":
                tools += 1
    return texts, tools


def json_lines(path: str, claude_filter: bool) -> Iterator[dict]:
    """Streams one log. Broken lines are skipped. A partly written last line is normal."""
    try:
        handle = open(path, "rb")
    except OSError as error:
        print(f"Skipped a file that could not be opened: {path} ({error.strerror})", file=sys.stderr)
        return
    with handle:
        for line in handle:
            if claude_filter:
                is_user = USER_MARK in line
                if not (is_user or ASSISTANT_MARK in line or SPACED_MARK.search(line)):
                    continue
                if is_user and TOOL_RESULT_MARK in line:
                    continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record


class Tally:
    """Collects counts. It keeps no message text after each add call returns."""

    def __init__(self, since: date, until: date, tz, names: ProjectNames):
        self.since, self.until, self.tz, self.names = since, until, tz, names
        self.seen_records: set = set()
        self.seen_blocks: set = set()
        self.humans = 0
        self.by_day: Counter = Counter()
        self.by_hour: Counter = Counter()
        self.by_project: Counter = Counter()
        self.by_month: Counter = Counter()
        self.month_days: Dict[int, set] = defaultdict(set)
        self.month_projects: Dict[int, Counter] = defaultdict(Counter)
        self.sessions: Dict[str, List[datetime]] = defaultdict(list)
        self.human_words: List[int] = []
        self.latest: Optional[Tuple[int, int]] = None
        self.night = self.thanks = self.late_thanks = self.sorrys = self.fixes = 0
        self.assistant_ids: set = set()
        self.tool_uses = self.words_ai = self.right = self.great = 0
        self.tokens: Dict[str, int] = {}
        self.model_messages: Counter = Counter()

    def localize(self, stamp) -> Optional[datetime]:
        moment = parse_stamp(stamp)
        if moment is None:
            return None
        local = moment.astimezone(self.tz)
        return local if self.since <= local.date() <= self.until else None

    def first_sight(self, record: dict) -> bool:
        """A resumed session copies old records into a new file with the same uuid."""
        uuid = record.get("uuid")
        if not uuid:
            return True
        if uuid in self.seen_records:
            return False
        self.seen_records.add(uuid)
        return True

    def add_human(self, when: datetime, text: str, session: str, cwd: Optional[str]) -> None:
        day, hour = when.date(), when.hour
        project = self.names.name(cwd)
        self.humans += 1
        self.by_day[day] += 1
        self.by_hour[hour] += 1
        self.by_project[project] += 1
        self.by_month[when.month] += 1
        self.month_days[when.month].add(day)
        self.month_projects[when.month][project] += 1
        self.sessions[session].append(when)
        self.human_words.append(len(text.split()))
        clock = (hour + 24 if hour < 6 else hour, when.minute)
        if self.latest is None or clock > self.latest:
            self.latest = clock
        if hour < 6:
            self.night += 1
        lower = text.lower()
        if found(THANKS_RE, THANKS_HINTS, text, lower):
            self.thanks += 1
            if 2 <= hour < 6:
                self.late_thanks += 1
        if found(SORRY_RE, SORRY_HINTS, text, lower):
            self.sorrys += 1
        if found(FIX_RE, FIX_HINTS, text, lower):
            self.fixes += 1

    def add_assistant(
        self, message_id: str, model: Optional[str], texts: Iterable[str], tools: int, output_tokens
    ) -> None:
        """One API message can span many log lines. Pass them all with the same message_id."""
        if message_id not in self.assistant_ids:
            self.assistant_ids.add(message_id)
            if isinstance(model, str) and model:
                self.model_messages[model] += 1
        self.tool_uses += tools
        for text in texts:
            key = (message_id, hash(text))
            if key in self.seen_blocks:
                continue
            self.seen_blocks.add(key)
            self.words_ai += len(text.split())
            lower = text.lower()
            if found(RIGHT_RE, RIGHT_HINTS, text, lower):
                self.right += 1
            if found(GREAT_RE, GREAT_HINTS, text, lower):
                self.great += 1
        if isinstance(output_tokens, int) and not isinstance(output_tokens, bool):
            self.tokens[message_id] = max(self.tokens.get(message_id, 0), output_tokens)


def read_claude(path: str, tally: Tally) -> None:
    for record in json_lines(path, claude_filter=True):
        kind = record.get("type")
        if kind == "user":
            text = human_text(record)
            if text is None:
                continue
            when = tally.localize(record.get("timestamp"))
            if when is not None and tally.first_sight(record):
                tally.add_human(when, text, path, record.get("cwd"))
        elif kind == "assistant":
            if record.get("isSidechain") or record.get("isApiErrorMessage"):
                continue
            message = record.get("message")
            if not isinstance(message, dict) or message.get("model") == "<synthetic>":
                continue
            when = tally.localize(record.get("timestamp"))
            if when is None or not tally.first_sight(record):
                continue
            message_id = message.get("id") or record.get("uuid")
            if not message_id:
                continue
            texts, tools = assistant_blocks(message.get("content"))
            usage = message.get("usage")
            output = usage.get("output_tokens") if isinstance(usage, dict) else None
            tally.add_assistant(message_id, message.get("model"), texts, tools, output)


def read_history(path: str, tally: Tally) -> None:
    """Fallback for a machine with history.jsonl but no project logs. Prompts only."""
    for record in json_lines(path, claude_filter=False):
        text = record.get("display")
        if not isinstance(text, str) or not text.strip() or text.lstrip().startswith("/"):
            continue
        when = tally.localize(record.get("timestamp"))
        if when is not None:
            tally.add_human(when, text.strip(), str(record.get("sessionId") or path), record.get("project"))


def codex_text(content, kinds: Tuple[str, ...]) -> str:
    if not isinstance(content, list):
        return content if isinstance(content, str) else ""
    parts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") in kinds]
    return "\n".join(part for part in parts if isinstance(part, str))


def read_codex(path: str, tally: Tally) -> None:
    """Reads one Codex rollout file. Experimental: the format is not documented by OpenAI."""
    cwd = model = None
    last_stamp = None
    from_events = False
    buffered: List[Tuple[object, str]] = []
    output_tokens = 0
    position = 0
    for record in json_lines(path, claude_filter=False):
        position += 1
        kind = record.get("type")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else record
        last_stamp = record.get("timestamp") or last_stamp
        if kind == "session_meta":
            cwd = payload.get("cwd") or cwd
        elif kind == "turn_context":
            cwd = payload.get("cwd") or cwd
            model = payload.get("model") or model
        elif kind == "event_msg":
            event = payload.get("type")
            if event == "user_message" and isinstance(payload.get("message"), str):
                from_events = True
                text = payload["message"].strip()
                when = tally.localize(last_stamp)
                if when is not None and text and not text.startswith(CODEX_NOISE_PREFIXES):
                    tally.add_human(when, text, path, cwd)
            elif event == "token_count":
                info = payload.get("info")
                usage = info.get("total_token_usage") if isinstance(info, dict) else None
                if isinstance(usage, dict) and isinstance(usage.get("output_tokens"), int):
                    output_tokens = max(output_tokens, usage["output_tokens"])
        elif kind == "response_item" or (kind == "message" and "role" in payload):
            item = payload.get("type")
            if item == "message" and payload.get("role") == "assistant":
                if tally.localize(last_stamp) is not None:
                    text = codex_text(payload.get("content"), ("output_text", "text"))
                    tally.add_assistant(f"{path}:{position}", model, [text], 0, None)
            elif item == "message" and payload.get("role") == "user":
                text = codex_text(payload.get("content"), ("input_text", "text")).strip()
                if text and not text.startswith(CODEX_NOISE_PREFIXES):
                    buffered.append((last_stamp, text))
            elif item in ("function_call", "local_shell_call", "custom_tool_call"):
                if tally.localize(last_stamp) is not None:
                    tally.tool_uses += 1
    if not from_events:
        for stamp, text in buffered:
            when = tally.localize(stamp)
            if when is not None:
                tally.add_human(when, text, path, cwd)
    if output_tokens and path in tally.sessions:
        tally.tokens[path] = output_tokens


# --- Stats --------------------------------------------------------------------------------------


def longest_streak(days: Iterable[date]) -> Tuple[int, Optional[date], Optional[date]]:
    best, start, end = 0, None, None
    run, run_start, previous = 0, None, None
    for day in sorted(days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        run_start = run_start if run > 1 else day
        if run > best:
            best, start, end = run, run_start, day
        previous = day
    return best, start, end


def typical_hour(by_hour: Dict[int, int]) -> Optional[int]:
    """The most common hour. A tie goes to the later hour."""
    return max(by_hour, key=lambda hour: (by_hour[hour], hour)) if by_hour else None


def active_minutes(times: List[datetime]) -> int:
    """Adds the gaps of 30 minutes or less between messages of one session."""
    ordered = sorted(times)
    total = timedelta()
    for earlier, later in zip(ordered, ordered[1:]):
        if later - earlier <= SESSION_GAP:
            total += later - earlier
    return int(total.total_seconds() // 60)


def persona_code(table: dict, tools_per_message, night_share, hour, median_words, thanks_per_100) -> str:
    """Same rules as derivePersona in src/lib/persona.ts."""
    limits = table["thresholds"]
    builder = (tools_per_message or 0) >= limits["toolUsePerAssistantMessage"]
    night = (night_share or 0) >= limits["nightShare"] or (hour or 0) >= limits["typicalHour"]
    verbose = (median_words or 0) >= limits["medianWords"]
    polite = (thanks_per_100 or 0) >= limits["thanksPer100"]
    return ("B" if builder else "T") + ("N" if night else "D") + ("V" if verbose else "S") + ("P" if polite else "R")


def rank_percent(messages_per_day: float) -> int:
    for floor, percent in RANK_CURVE:
        if messages_per_day >= floor:
            return percent
    return RANK_CURVE[-1][1]


def power_title(messages: int) -> str:
    for floor, title in POWER_TIERS:
        if messages >= floor:
            return title
    return POWER_TIERS[-1][1]


def short_model(model: str) -> str:
    """claude-opus-5-5-20261001 -> opus-5.5. claude-3-5-sonnet-20241022 -> sonnet-3.5."""
    name = re.sub(r"\[.*?\]$", "", model.strip())
    name = re.sub(r"^claude-", "", name)
    name = re.sub(r"-\d{8}$", "", name)
    match = re.match(r"^([a-z]+)-(\d+)-(\d+)$", name)
    if match:
        return f"{match.group(1)}-{match.group(2)}.{match.group(3)}"
    match = re.match(r"^(\d+)-(\d+)-([a-z]+)$", name)
    if match:
        return f"{match.group(3)}-{match.group(1)}.{match.group(2)}"
    return name


def month_day(day: date) -> str:
    return f"{MONTHS[day.month - 1]} {day.day}"


def compute_stats(tally: Tally, table: dict) -> dict:
    messages = tally.humans
    active = len(tally.by_day)
    streak, streak_start, streak_end = longest_streak(tally.by_day)
    busiest = min(tally.by_day, key=lambda day: (-tally.by_day[day], day))
    hour = typical_hour(tally.by_hour)
    night_share = round_half_up(100 * tally.night / messages)
    median_words = statistics.median(tally.human_words)
    assistant_messages = len(tally.assistant_ids)
    tools_per_message = tally.tool_uses / assistant_messages if assistant_messages else 0
    thanks_per_100 = 100 * tally.thanks / messages
    code = persona_code(table, tools_per_message, night_share, hour, median_words, thanks_per_100)
    late_hour, late_minute = tally.latest
    models = [short_model(model) for model, _ in tally.model_messages.most_common()]
    unique_models = list(dict.fromkeys(models))
    return {
        "conversations": len(tally.sessions),
        "messages": messages,
        "assistantMessages": assistant_messages,
        "activeDays": active,
        "streak": streak,
        "streakStart": streak_start.isoformat(),
        "streakEnd": streak_end.isoformat(),
        "busiestDay": busiest.isoformat(),
        "busiestDayMessages": tally.by_day[busiest],
        "latestClock": f"{late_hour % 24:02d}:{late_minute:02d}",
        "typicalHour": hour,
        "nightShare": night_share,
        "wordsYou": sum(tally.human_words),
        "wordsAi": tally.words_ai,
        "thankYous": tally.thanks,
        "sorrys": tally.sorrys,
        "absolutelyRight": tally.right,
        "greatQuestions": tally.great,
        "tokensOut": sum(tally.tokens.values()),
        "models": unique_models[:MAX_MODELS],
        "toolUsePerAssistantMessage": round(tools_per_message, 3),
        "medianWords": median_words,
        "thanksPer100": round(thanks_per_100, 2),
        "persona": code,
        "personaName": table["types"][code]["name"],
        "personaLine": table["types"][code]["line"],
        "rankPercent": rank_percent(messages / active),
        "power": power_title(messages),
    }


def project_shares(tally: Tally, anon: bool) -> Tuple[List[dict], Dict[str, str]]:
    """Returns the top projects and the display name of each one."""
    total = tally.humans
    ranked = sorted(tally.by_project.items(), key=lambda item: (-item[1], item[0]))[:MAX_THEMES]
    labels = {}
    for index, (name, _) in enumerate(ranked):
        labels[name] = f"Project {chr(ord('A') + index)}" if anon else theme_name(name)
    return [{"name": labels[name], "share": round_half_up(100 * count / total)} for name, count in ranked], labels


def month_facts(tally: Tally, labels: Dict[str, str], anon: bool) -> List[dict]:
    """Per-month numbers for the moments. A project outside the top 5 stays unnamed under --anon."""
    facts = []
    for month in sorted(tally.by_month):
        top = sorted(tally.month_projects[month].items(), key=lambda item: (-item[1], item[0]))[0][0]
        name = labels.get(top) or ("another project" if anon else theme_name(top))
        facts.append(
            {
                "month": MONTHS[month - 1],
                "messages": tally.by_month[month],
                "activeDays": len(tally.month_days[month]),
                "topProject": name,
            }
        )
    return facts


def plural(count: int, word: str) -> str:
    """1 message, 2 messages. Claude copies the seeds into the roast, so the grammar must be right."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def roast_seeds(tally: Tally, stats: dict, projects: List[dict]) -> List[str]:
    """Three plain facts for the roast. Numbers, dates and model names only, never message text."""
    seeds: List[str] = []
    night_starts: Counter = Counter()
    longest, longest_day = 0, None
    for times in tally.sessions.values():
        first = min(times)
        if first.hour < 6:
            night_starts[tuple(first.isocalendar())[:2]] += 1
        minutes = active_minutes(times)
        if minutes > longest:
            longest, longest_day = minutes, first
    if night_starts and max(night_starts.values()) >= 3:
        seeds.append(f"Started {max(night_starts.values())} sessions after midnight in one week")
    if tally.late_thanks:
        seeds.append(f"Said thanks {plural(tally.thanks, 'time')}, {tally.late_thanks} of them after 2 AM")
    if longest >= 60:
        seeds.append(f"Longest session {longest // 60} h {longest % 60} m on a {WEEKDAYS[longest_day.weekday()]}")
    if tally.fixes >= 5:
        seeds.append(f"Asked to 'fix' something {plural(tally.fixes, 'time')}")
    if projects and projects[0]["share"] >= 40:
        seeds.append(f"Top project took {projects[0]['share']}% of all messages")
    busiest = date.fromisoformat(stats["busiestDay"])
    seeds.append(f"{plural(stats['busiestDayMessages'], 'message')} on {month_day(busiest)}")
    if stats["models"] and stats["wordsAi"]:
        seeds.append(f"{stats['models'][0]} wrote {plural(stats['wordsAi'], 'word')}; you wrote {stats['wordsYou']}")
    if not tally.late_thanks:
        seeds.append(f"Said thanks {plural(tally.thanks, 'time')}")
    return seeds[:3]


# --- URL ----------------------------------------------------------------------------------------


def form_encode(text: str) -> str:
    """The same output as URLSearchParams in the browser. urllib is not imported on purpose."""
    out = []
    for byte in text.encode("utf-8"):
        if byte == 0x20:
            out.append("+")
        elif byte in FORM_SAFE:
            out.append(chr(byte))
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + ELLIPSIS


def strip_link_leak(text: str) -> str:
    """Removes a trailing ) or ] that has no partner."""
    if text[-1:] not in (")", "]"):
        return text
    opening = "(" if text[-1] == ")" else "["
    return text[:-1] if text.count(text[-1]) > text.count(opening) else text


def strip_quotes(text: str) -> str:
    """Removes matching quotes around the value. '"A" and "B"' stays as it is."""
    if len(text) < 2 or QUOTES.get(text[0]) != text[-1]:
        return text
    inner = text[1:-1]
    return text if text[0] in inner or text[-1] in inner else inner


ESCAPE_RUN_RE = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
# The characters of \s in JavaScript. str.split() also splits on \x1c-\x1f and \x85, which tidyText removes
# as control characters instead, and it keeps \ufeff, which tidyText turns into a space.
JS_SPACE_RE = re.compile("[\t\n\x0b\x0c\r \xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+")


def decode_escape_run(match) -> str:
    """Decodes a run such as %E6%97%A5. A byte that starts no valid UTF-8 character stays as it is."""
    tokens = re.findall(r"%[0-9A-Fa-f]{2}", match.group(0))
    out, index = [], 0
    while index < len(tokens):
        for size in range(min(4, len(tokens) - index), 0, -1):
            chunk = bytes(int(token[1:], 16) for token in tokens[index : index + size])
            try:
                out.append(chunk.decode("utf-8"))
                break
            except UnicodeDecodeError:
                continue
        else:
            out.append(tokens[index])
            size = 1
        index += size
    return "".join(out)


def percent_decode(text: str) -> str:
    """The percent step of tidyText. A doubly encoded value from the browser decodes the same way here."""
    return ESCAPE_RUN_RE.sub(decode_escape_run, text)


def clean_text(value: Optional[str], limit: int) -> str:
    """The same steps as tidyText in the web codec, so a decoded value stays the same."""
    text = value or ""
    previous = None
    while text != previous:
        previous = text
        text = percent_decode(text)
        text = JS_SPACE_RE.sub(" ", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf", "Cs"))
        text = re.sub(" {2,}", " ", EMOJI_RE.sub("", text)).strip(" ")
        text = strip_quotes(strip_link_leak(text)).strip(" ")
    return "" if NO_VALUE_RE.match(text) else cap(text, limit)


def clean_name(value: Optional[str]) -> str:
    """Same steps as cleanName in the web codec: letters, marks, space, hyphen and apostrophe, cut with no
    ellipsis. A name with no letter, or a placeholder such as null, is no name."""
    text = value or ""
    previous = None
    while text != previous:
        previous = text
        text = clean_text(text, 10**9).replace(chr(0x2019), "'")
        text = " ".join("".join(ch for ch in text if ch in " '-" or unicodedata.category(ch)[0] in "LM").split())
    if not any(unicodedata.category(ch)[0] == "L" for ch in text) or NO_VALUE_RE.match(text):
        return ""
    return text[:MAX_NAME].strip()


def theme_name(value: str) -> str:
    """A separator in a folder name would split the t= list, so it becomes a hyphen."""
    return cap(re.sub(r"[:,;|]+", "-", clean_text(value, 1000)).strip("-") or "project", MAX_THEME_NAME)


def parse_moments(raw: Optional[str]) -> List[Tuple[str, str]]:
    """Reads 'Jan|text;Mar|text'. A ';' splits only before a month. A bad item is dropped with a note."""
    items: List[Tuple[str, str]] = []
    for part in MOMENT_SPLIT_RE.split(" ".join((raw or "").split())):
        if not part.strip():
            continue
        match = MOMENT_RE.match(part.strip())
        text = clean_text(match.group(2), MAX_MOMENT_TEXT) if match else ""
        if not text:
            print("Skipped one moment: use Mon|text, for example Mar|Shipped the beta.", file=sys.stderr)
            continue
        items.append((match.group(1)[:3].title(), text))
    return items[:MAX_MOMENTS]


def render_moments(items: List[Tuple[str, str]]) -> str:
    return ";".join(f"{month}|{text}" for month, text in items)


def render(fields: Dict[str, object]) -> str:
    pairs = []
    for key in CANONICAL_ORDER:
        value = fields.get(key)
        if value is None or value == "" or value == []:
            continue
        text = render_moments(value) if key == "mo" else ",".join(value) if key in ("t", "md") else str(value)
        pairs.append(f"{key}={form_encode(text)}")
    return "&".join(pairs)


def shortened(fields: Dict[str, object], key: str, limit: int) -> Optional[Dict[str, object]]:
    """One shorter copy of the fields, or None when this limit changes nothing."""
    value = fields.get(key)
    if key == "mo":
        if not value or not any(len(text) > limit for _, text in value):
            return None
        return {**fields, key: [(month, cap(text, limit)) for month, text in value]}
    if not value or len(str(value)) <= limit:
        return None
    return {**fields, key: cap(str(value), limit)}


def dropped(fields: Dict[str, object], key: str) -> Optional[Dict[str, object]]:
    """A copy with less of this field, or None when the field is empty."""
    value = fields.get(key)
    if not value:
        return None
    if key in ("mo", "t"):
        return {**fields, key: value[:-1]}
    return {**fields, key: None}


def fit_query(fields: Dict[str, object], limit: int = ENCODE_MAX) -> str:
    """Same steps as encodeRewind: shorten mo, ro, co, pv, pn, then drop them, then t, pl and md."""
    query = render(fields)
    for key in TRUNCATE_ORDER:
        text_limit = SHORTEN_START
        while text_limit >= SHORTEN_FLOOR and len(query) > limit:
            shorter = shortened(fields, key, text_limit)
            if shorter:
                fields = shorter
                query = render(fields)
            text_limit -= SHORTEN_STEP
    for key in LAST_RESORT:
        while len(query) > limit:
            less = dropped(fields, key)
            if less is None:
                break
            fields = less
            query = render(fields)
    return query


def build_fields(args, stats: dict, projects: List[dict]) -> Dict[str, object]:
    fields: Dict[str, object] = {
        "v": 1,
        "p": args.platform,
        "m": "receipts",
        "a": 0,
        "y": args.since.year,
        "n": clean_name(args.name),
        "c": stats["conversations"],
        "mg": stats["messages"],
        "d": min(stats["activeDays"], MAX_DAYS),
        "s": min(stats["streak"], MAX_DAYS),
        "sr": f"{stats['streakStart'][5:]}..{stats['streakEnd'][5:]}",
        "bd": stats["busiestDay"][5:],
        "bm": stats["busiestDayMessages"],
        "lh": stats["latestClock"],
        "th": stats["typicalHour"],
        "ns": stats["nightShare"],
        "wu": stats["wordsYou"],
        "t": [f"{item['name']}:{item['share']}" for item in projects],
        "ty": stats["thankYous"],
        "so": stats["sorrys"],
        "pc": stats["persona"],
        "pn": clean_text(args.persona_name, MAX_PERSONA_NAME),
        "mo": parse_moments(args.moments),
        "ro": clean_text(args.roast, MAX_ROAST),
        "co": clean_text(args.compliment, MAX_COMPLIMENT),
        "rk": stats["rankPercent"],
        "pl": clean_text(stats["power"], MAX_POWER),
        "src": "skill",
    }
    # Numbers that need the assistant side. History-only runs have none, so they stay out.
    if stats["assistantMessages"]:
        fields.update(wa=stats["wordsAi"], ar=stats["absolutelyRight"], tk=stats["tokensOut"])
        fields["md"] = [clean_text(re.sub(r"[,;]", " ", name), MAX_PERSONA_NAME) for name in stats["models"]]
    return fields


def normalize_site(raw: Optional[str]) -> str:
    """Bare origin with no trailing slash. Bad input gives the default."""
    value = (raw or "").strip()
    match = re.match(r"^(https?://)?([^/?#\s]+)", value, re.I)
    if not match:
        return DEFAULT_SITE
    return f"{(match.group(1) or 'https://').lower()}{match.group(2)}"


# --- Command line -------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rewind.py",
        description="Build an AI Wrapped link from local logs. No network. No chat text in the output.",
    )
    parser.add_argument("--since", type=parse_day, default=parse_day(DEFAULT_SINCE), help="first day, YYYY-MM-DD")
    parser.add_argument("--until", type=parse_day, default=parse_day(DEFAULT_UNTIL), help="last day, YYYY-MM-DD")
    parser.add_argument("--platform", choices=("claude-code", "codex"), default="claude-code")
    parser.add_argument("--claude-dir", "--codex-dir", dest="log_dir", help="log folder, default ~/.claude or ~/.codex")
    parser.add_argument("--tz", help="IANA time zone, default the system zone")
    parser.add_argument("--json", action="store_true", help="print stats, seeds and projects as JSON")
    parser.add_argument("--name", help="first name to show")
    parser.add_argument("--anon", action="store_true", help="show Project A to E, not folder names")
    parser.add_argument("--roast", help="roast text, up to 140 characters")
    parser.add_argument("--compliment", help="compliment text, up to 100 characters")
    parser.add_argument("--moments", help="moments as Jan|text;Mar|text, up to 5")
    parser.add_argument("--persona-name", help="custom persona name, up to 32 characters")
    parser.add_argument("--site", default=DEFAULT_SITE, help="site origin for the link")
    parser.add_argument("--dry-run", action="store_true", help="print the files it would read, then exit")
    parser.add_argument("--version", action="version", version=f"rewind.py {VERSION}")
    return parser


def run(args) -> int:
    default_dir = "~/.codex" if args.platform == "codex" else "~/.claude"
    root = os.path.abspath(os.path.expanduser(args.log_dir or default_dir))
    files, history = find_files(args.platform, root, args.since)

    if args.dry_run:
        paths = files + ([history] if history else [])
        for path in paths:
            print(path)
        return 0 if paths else 2

    tz = resolve_tz(args.tz)
    tally = Tally(args.since, args.until, tz, ProjectNames(os.path.expanduser("~")))
    reader = read_codex if args.platform == "codex" else read_claude
    for path in files:
        reader(path, tally)
    if history:
        read_history(history, tally)
    if not tally.humans:
        print(f"No sessions found in {root} from {args.since} to {args.until}.", file=sys.stderr)
        return 2

    table = load_persona_table()
    stats = compute_stats(tally, table)
    projects, labels = project_shares(tally, args.anon)
    site = normalize_site(args.site)
    url = f"{site}/r?{fit_query(build_fields(args, stats, projects))}"
    if not args.json:
        print(url)
        return 0
    days = sorted(tally.by_day)
    report = {
        "skill": VERSION,
        "range": {
            "since": args.since.isoformat(),
            "until": args.until.isoformat(),
            "firstDay": days[0].isoformat(),
            "lastDay": days[-1].isoformat(),
        },
        "stats": stats,
        "seeds": roast_seeds(tally, stats, projects),
        "projects": projects,
        "months": month_facts(tally, labels, args.anon),
        "url": url,
    }
    print(json.dumps(report, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    if sys.version_info < (3, 9):  # noqa: UP036
        print("This script needs Python 3.9 or newer.", file=sys.stderr)
        return 2
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ScriptError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
