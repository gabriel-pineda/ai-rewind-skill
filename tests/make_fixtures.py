#!/usr/bin/env python3
"""Writes tests/fixtures. Every string below is invented for these tests.

Run it from anywhere: python3 tests/make_fixtures.py
A test checks that the committed files match this script.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = "/Users/demo/app"
OTHER = "/Users/demo/Documents/other/sub"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S2 = "aaaaaaaa-0000-4000-8000-000000000002"
S3 = "bbbbbbbb-0000-4000-8000-000000000003"
S4 = "bbbbbbbb-0000-4000-8000-000000000004"
S5 = "aaaaaaaa-0000-4000-8000-000000000005"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"
OPUS = "claude-opus-5-5-20261001"
HAIKU = "claude-3-5-haiku-20241022"


def line(record):
    if isinstance(record, str):
        return record
    return json.dumps(record, separators=(",", ":"), ensure_ascii=False)


def user(uuid, stamp, session, cwd, content, **extra):
    return {
        "parentUuid": None,
        "isSidechain": False,
        "type": "user",
        "message": {"role": "user", "content": content},
        "uuid": uuid,
        "timestamp": stamp,
        "cwd": cwd,
        "sessionId": session,
        **extra,
    }


HUMAN = {"origin": {"kind": "human"}}


def assistant(uuid, stamp, session, cwd, message_id, model, block, output, **extra):
    return {
        "parentUuid": None,
        "isSidechain": False,
        "type": "assistant",
        "message": {
            "id": message_id,
            "role": "assistant",
            "model": model,
            "content": [block],
            "usage": {"input_tokens": 9, "output_tokens": output, "cache_read_input_tokens": 100},
        },
        "uuid": uuid,
        "timestamp": stamp,
        "cwd": cwd,
        "sessionId": session,
        **extra,
    }


def text(value):
    return {"type": "text", "text": value}


def tool(name, **arguments):
    return {"type": "tool_use", "id": f"toolu_{name}_{len(arguments)}", "name": name, "input": arguments}


def tool_result(value):
    return [{"type": "tool_result", "tool_use_id": "toolu_x", "content": value}]


FIRST = user("u-001", "2026-03-02T09:00:00.000Z", S1, APP, "Please add a login form to the demo page", **HUMAN)
SECOND = user("u-002", "2026-03-02T09:10:00.000Z", S1, APP, [text("thanks, that looks great")], **HUMAN)

SESSION_1 = [
    {"type": "permission-mode", "permissionMode": "default", "sessionId": S1},
    FIRST,
    # One API message across three lines. Thinking and tool input never count as words.
    assistant(
        "a-001",
        "2026-03-02T09:00:05.000Z",
        S1,
        APP,
        "msg_001",
        OPUS,
        {"type": "thinking", "thinking": "Private reasoning that must stay out of every count"},
        3,
    ),
    assistant(
        "a-002",
        "2026-03-02T09:00:06.000Z",
        S1,
        APP,
        "msg_001",
        OPUS,
        text("You're absolutely right, the login form was missing."),
        12,
    ),
    assistant(
        "a-003",
        "2026-03-02T09:00:07.000Z",
        S1,
        APP,
        "msg_001",
        OPUS,
        tool("Edit", file_path="/Users/demo/app/login.tsx", new_string="tool input words stay uncounted"),
        40,
    ),
    user("u-t01", "2026-03-02T09:00:08.000Z", S1, APP, tool_result("edit applied to the login file")),
    SECOND,
    assistant("a-004", "2026-03-02T09:10:05.000Z", S1, APP, "msg_002", OPUS, text("Glad it works for you."), 8),
    assistant("a-005", "2026-03-02T09:10:06.000Z", S1, APP, "msg_002", OPUS, tool("Bash", command="ls"), 20),
    assistant(
        "a-006", "2026-03-02T09:10:07.000Z", S1, APP, "msg_002", OPUS, tool("Read", file_path="/tmp/a", limit=5), 30
    ),
    user("u-003", "2026-03-03T10:00:00.000Z", S1, APP, "fix the failing build on the demo page please", **HUMAN),
    user("u-004", "2026-03-04T23:30:00.000Z", S1, APP, "sorry, one more change to the header", **HUMAN),
    # None of these are prompts a person typed.
    user("u-m01", "2026-03-04T23:30:01.000Z", S1, APP, "Skill text injected by the host", isMeta=True),
    user("u-n01", "2026-03-04T23:31:00.000Z", S1, APP, "<command-name>/clear</command-name>"),
    user("u-n02", "2026-03-04T23:32:00.000Z", S1, APP, "<bash-input>git status</bash-input>"),
    user("u-n03", "2026-03-04T23:33:00.000Z", S1, APP, "<local-command-stdout>done</local-command-stdout>"),
    user("u-n04", "2026-03-04T23:34:00.000Z", S1, APP, [text("[Request interrupted by user]")]),
    user("u-n05", "2026-03-04T23:35:00.000Z", S1, APP, "Compaction summary text", isCompactSummary=True),
    user(
        "u-n06",
        "2026-03-04T23:36:00.000Z",
        S1,
        APP,
        "<task-notification>job finished</task-notification>",
        origin={"kind": "task-notification"},
    ),
    user("u-n07", "2026-03-04T23:37:00.000Z", S1, APP, "note from a peer session", origin={"kind": "peer"}),
    user("u-n08", "2026-03-04T23:38:00.000Z", S1, APP, [{"type": "image", "source": {"type": "base64", "data": "AA"}}]),
    # A sidechain record inside a main file stays out of every count.
    {**user("u-s01", "2026-03-04T23:39:00.000Z", S1, APP, "sidechain prompt thanks sorry"), "isSidechain": True},
    {
        **assistant("a-s01", "2026-03-04T23:39:05.000Z", S1, APP, "msg_s01", OPUS, text("Sidechain reply text."), 500),
        "isSidechain": True,
    },
    # A local error record has the synthetic model and no real message.
    assistant("a-e01", "2026-03-04T23:40:00.000Z", S1, APP, "msg_e01", "<synthetic>", text("API Error text"), 0),
]

SESSION_2 = [
    user("u-005", "2026-03-05T02:15:00.000Z", S2, APP, "thank you for the late night help with the cache bug", **HUMAN),
    assistant(
        "a-007",
        "2026-03-05T02:15:05.000Z",
        S2,
        APP,
        "msg_003",
        OPUS,
        text("You’re completely right about the cache."),
        15,
    ),
    user("u-006", "2026-03-05T03:47:00.000Z", S2, APP, "cheers, ship the fixed version now", **HUMAN),
    # A crash can leave a partial last line.
    '{"type":"user","message":{"role":"user","content":"partial li',
]

LONG_PROMPT = (
    "write a long migration plan that moves the billing tables to the new schema over three weekends with a "
    "rollback step after each stage and a short note for the support team about what customers might notice "
    "during the slow nightly batch runs"
)

SESSION_3 = [
    # Older logs have no origin field.
    user("u-007", "2026-06-20T14:00:00.000Z", S3, OTHER, LONG_PROMPT),
    assistant("a-008", "2026-06-20T14:00:05.000Z", S3, OTHER, "msg_004", HAIKU, text("Great question, here goes."), 25),
    user("u-008", "2026-06-20T14:05:00.000Z", S3, OTHER, "shorter version"),
    user("u-009", "2026-06-20T14:10:00.000Z", S3, OTHER, "add the risks section"),
    user("u-010", "2026-06-20T15:00:00.000Z", S3, OTHER, "looks fine, stop here"),
]

# Out of range in UTC. In Melbourne this is 2026-01-01.
SESSION_4 = [user("u-011", "2025-12-31T23:59:00.000Z", S4, OTHER, "new year task for the old year", **HUMAN)]

# A resumed session copies old records with the same uuid, then adds one new prompt.
SESSION_5 = [FIRST, SECOND, user("u-012", "2026-06-21T08:00:00.000Z", S5, APP, "continue the demo work", **HUMAN)]

# Tool traffic only, so it is not a conversation.
SESSION_6 = [
    user("u-t02", "2026-06-22T08:00:00.000Z", S6, APP, tool_result("no human here")),
    user("u-m02", "2026-06-22T08:00:01.000Z", S6, APP, "meta only here", isMeta=True),
]

SUBAGENT = [
    {
        **user("u-a01", "2026-03-02T09:00:10.000Z", S1, APP, "subagent task prompt thanks", agentId="x"),
        "isSidechain": True,
    },
    {
        **assistant("a-a01", "2026-03-02T09:00:12.000Z", S1, APP, "msg_a01", OPUS, text("Subagent reply words."), 900),
        "isSidechain": True,
        "agentId": "x",
    },
]

HISTORY = [
    {"display": "fix the header spacing", "project": APP, "sessionId": S1, "timestamp": 1772442000000},
    {"display": "/clear", "project": APP, "sessionId": S1, "timestamp": 1772442060000},
    {"display": "thanks, all good", "project": APP, "sessionId": S2, "timestamp": 1772528400000},
]

# --- Merge fixture: history.jsonl from March, session files for 8 and 9 Oct only ---------------------------
# Claude Code deleted the older session files. history.jsonl still has every prompt.

NOTES = "/Users/demo/Documents/notes"
W1 = "cccccccc-0000-4000-8000-000000000001"  # In the window, in both sources.
W2 = "cccccccc-0000-4000-8000-000000000002"  # In the window. One history line is 6 s off, so it is new.
X1 = "dddddddd-0000-4000-8000-000000000001"  # In history only, at the same second as a W1 prompt.
H = ["eeeeeeee-0000-4000-8000-00000000000" + str(index) for index in range(1, 7)]  # History only.


def ms(stamp):
    from datetime import datetime

    return int(datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z").timestamp() * 1000)


def prompt(stamp, session, project, display):
    return {"display": display, "pastedContents": {}, "timestamp": ms(stamp), "project": project, "sessionId": session}


MERGE_W1 = [
    user("m-u01", "2026-10-08T10:00:00.000Z", W1, APP, "sketch the calendar widget layout", **HUMAN),
    assistant("m-a01", "2026-10-08T10:00:05.000Z", W1, APP, "msg_m01", OPUS, text("Here is a calendar sketch."), 30),
    user("m-u02", "2026-10-08T10:10:00.000Z", W1, APP, "make the weekend columns narrower", **HUMAN),
    assistant("m-a02", "2026-10-08T10:10:05.000Z", W1, APP, "msg_m02", OPUS, tool("Edit", file="w.ts"), 20),
    user("m-u03", "2026-10-08T10:20:04.000Z", W1, APP, "now add a dark variant please", **HUMAN),
    assistant("m-a03", "2026-10-08T10:20:09.000Z", W1, APP, "msg_m03", OPUS, text("Dark variant added, see it."), 10),
]

MERGE_W2 = [
    user("m-u04", "2026-10-09T15:00:00.000Z", W2, APP, "the widget overflows on small phones", **HUMAN),
    assistant("m-a04", "2026-10-09T15:00:05.000Z", W2, APP, "msg_m04", OPUS, text("You're absolutely right."), 25),
    user("m-u05", "2026-10-09T15:10:00.000Z", W2, APP, "wrap the labels onto two lines", **HUMAN),
    assistant("m-a05", "2026-10-09T15:10:05.000Z", W2, APP, "msg_m05", OPUS, text("Labels now wrap well."), 15),
]

MERGE_HISTORY = [
    prompt("2025-12-30T10:00:00+0000", H[0], NOTES, "an old prompt from last december"),
    prompt("2026-03-09T10:00:00+0000", H[0], NOTES, "plan a reading list for spring"),
    prompt("2026-03-09T10:01:00+0000", H[0], NOTES, "/clear"),
    prompt("2026-03-09T10:05:00+0000", H[0], NOTES, "shorter list, only five titles"),
    prompt("2026-03-10T23:30:00+0000", H[1], NOTES, "summarise the chapter outline"),
    prompt("2026-06-01T09:00:00+0000", H[2], APP, "thanks, the build passes again"),
    prompt("2026-06-01T09:02:00+0000", H[2], APP, "!ls -la in the build folder"),
    prompt("2026-06-02T09:00:00+0000", H[3], APP, "rename the settings screen fields"),
    prompt("2026-06-03T02:30:00+0000", H[4], APP, "sorry, revert that last rename"),
    prompt("2026-10-08T10:00:00+0000", W1, APP, "sketch the calendar widget layout"),
    prompt("2026-10-08T10:00:00+0000", X1, NOTES, "list three cafes for the meetup"),
    prompt("2026-10-08T10:10:03+0000", W1, APP, "make the weekend columns narrower"),
    prompt("2026-10-08T10:20:00+0000", W1, APP, "now add a dark variant please"),
    prompt("2026-10-09T15:00:01+0000", W2, APP, "the widget overflows on small phones"),
    prompt("2026-10-09T15:10:06+0000", W2, APP, "also check the tablet breakpoint"),
    prompt("2026-11-01T12:00:00+0000", H[5], NOTES, "draft the meetup invite text"),
]

CODEX_ROLLOUT = [
    {
        "timestamp": "2026-04-10T01:00:00.000Z",
        "type": "session_meta",
        "payload": {"id": "cccccccc-0000-4000-8000-000000000001", "cwd": "/Users/demo/app", "originator": "codex_cli"},
    },
    {
        "timestamp": "2026-04-10T01:00:01.000Z",
        "type": "turn_context",
        "payload": {"cwd": APP, "model": "gpt-5.1-codex"},
    },
    {
        "timestamp": "2026-04-10T01:00:02.000Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "<environment_context>demo shell</environment_context>"}],
        },
    },
    {
        "timestamp": "2026-04-10T01:00:03.000Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "thanks for looking at the codex build"}],
        },
    },
    {
        "timestamp": "2026-04-10T01:00:03.000Z",
        "type": "event_msg",
        "payload": {"type": "user_message", "message": "thanks for looking at the codex build"},
    },
    {
        "timestamp": "2026-04-10T01:00:09.000Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "You're right, the build needs a fresh cache."}],
        },
    },
    {
        "timestamp": "2026-04-10T01:00:10.000Z",
        "type": "response_item",
        "payload": {"type": "function_call", "name": "shell", "arguments": "{\"command\":[\"ls\"]}"},
    },
    {
        "timestamp": "2026-04-10T01:00:11.000Z",
        "type": "event_msg",
        "payload": {"type": "token_count", "info": {"total_token_usage": {"output_tokens": 77}}},
    },
]

FILES = {
    "claude/projects/-Users-demo-app/" + S1 + ".jsonl": SESSION_1,
    "claude/projects/-Users-demo-app/" + S1 + "/subagents/agent-x.jsonl": SUBAGENT,
    "claude/projects/-Users-demo-app/" + S2 + ".jsonl": SESSION_2,
    "claude/projects/-Users-demo-app/" + S5 + ".jsonl": SESSION_5,
    "claude/projects/-Users-demo-app/" + S6 + ".jsonl": SESSION_6,
    "claude/projects/-Users-demo-other/" + S3 + ".jsonl": SESSION_3,
    "claude/projects/-Users-demo-other/" + S4 + ".jsonl": SESSION_4,
    "claude-history-only/history.jsonl": HISTORY,
    "claude/merge/projects/-Users-demo-app/" + W1 + ".jsonl": MERGE_W1,
    "claude/merge/projects/-Users-demo-app/" + W2 + ".jsonl": MERGE_W2,
    "claude/merge/history.jsonl": MERGE_HISTORY,
    "codex/sessions/2026/04/10/rollout-2026-04-10T01-00-00-demo.jsonl": CODEX_ROLLOUT,
}


def rendered():
    return {path: "".join(line(record) + "\n" for record in records) for path, records in FILES.items()}


def main():
    for path, body in rendered().items():
        full = os.path.join(HERE, "fixtures", path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(body)
        print(path)


if __name__ == "__main__":
    sys.exit(main())
