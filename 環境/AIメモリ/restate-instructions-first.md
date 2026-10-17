---
name: restate-instructions-first
description: The user dictates video-edit fixes by voice in batches; restate them as an organized list and get confirmation before doing any work
metadata:
  node_type: memory
  type: feedback
  originSessionId: 7640e84d-1f12-4710-a4b6-e1be705178ae
  modified: 2026-10-17T05:19:05.758Z
---

The user gives edit corrections by voice input (transcription errors, rambling, timecodes like 1分29秒21 = 00:01:29:21 at 30fps), usually per 10-minute section of the video. On 2026-09-26 I started investigating right away and the user stopped me: 「違う、作業しにいく前に、俺の指示を言語で整理してみて」.

**Why:** the dictated text is ambiguous; the user wants to check my interpretation before I spend time building.

**How to apply:** first reply with a numbered list (global items vs. per-timecode items, my interpretation, and short questions for anything ambiguous), plus proposals for rules that should also apply to later sections. Start building only after they confirm. Related: [[concurrent-agents-same-folder]].

The list must be written out **in the chat text itself**. On 2026-10-17 (security v003→v004, Loom review) I wrote the list only to `指示の整理.md` and showed just an "OK" button. The user clicked OK, then asked 「修正点の一覧の確認は？」 because they had never seen the list. A file link plus a button does not count as showing it. Loom reviews work the same way: read the player's captions, match each comment to the version's timecodes using paused frames, and paste the full organized list in chat.
