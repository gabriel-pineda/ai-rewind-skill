# Changelog

## 1.0.0 (unreleased)

- First version of the `ai-wrapped` skill and `rewind.py`.
- Stats from Claude Code logs. Codex support is experimental.
- URL output in the canonical form of the web app.
- Privacy tests: no network imports, no message text in the output.
- Text cleaning matches the web codec exactly: percent escapes decode, JavaScript whitespace rules, and a name
  with no letter (or a placeholder such as null) is dropped. Long names are cut with no ellipsis.
- Seeds use the right plural: "1 message on Apr 10", "Said thanks 1 time".
- Parity tests with the web repo on shared fixtures: personas, text cleaning and the full report.
