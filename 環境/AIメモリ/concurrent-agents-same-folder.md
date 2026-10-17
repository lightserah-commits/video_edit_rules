---
name: concurrent-agents-same-folder
description: "In video_edit_rules, other AI sessions (another Claude session, Codex in the ChatGPT app) edit the same files and drive the same Premiere concurrently; check before overwriting or operating."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 07c6c926-14c7-4c67-b91f-c5ce18a0d24d
  modified: 2026-09-26T03:44:50.966Z
---

Other agents work in this folder and in Premiere at the same time as me. On 2026-09-26 the previous Claude session kept working for ~5 minutes after writing its handoff note (作業状況.md), creating `tools/reproduce.py`, a demo and docs; I then wrote my own `tools/reproduce.py` over it and had to restore it from that session's transcript (stored under `~/.claude/projects/-Users-yoshizawakouichi-Downloads-tenohira-launch/`). The same day Codex launched a second Premiere (2024) next to the user's 2026; both MCP Bridge panels watched `/tmp/premiere-mcp-bridge`, so every command ran in both Premieres.

**Why:** overwriting another session's file silently destroys their work, and a shared bridge folder double-executes imports/exports into the wrong project.

**How to apply:** before creating or rewriting any file here, `ls -laT` it (and `find . -newermt <session start>`) to see whether someone else just wrote it; re-read the handoff note if it changed after the session began. Before any Premiere operation run `python3 tools/premiere_bridge.py status` (needs one Premiere and `bridge_panels: 1`); if not, ask the user instead of operating.
