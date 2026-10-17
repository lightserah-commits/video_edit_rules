---
name: show-visual-options-as-screenshots
description: "When the user must choose between telop/visual styles, export labeled Premiere screenshots of each candidate instead of describing them in words"
metadata:
  node_type: memory
  type: feedback
  originSessionId: da09afcf-4bae-4d8e-86f5-0a25078ddcba
  modified: 2026-09-26T13:18:01.649Z
---

On 2026-09-26, when I described three candidate 代弁 text styles and four telop types only in words, the user replied 「両方見せてください。スクリーンショットで見せてください」 and could not decide until they saw images. They then decided quickly from a labeled comparison sheet (A/B/C, one frame per candidate, name written above each).

**Why:** style names like シュール明朝 / 代弁(水色) / 白背景 mean nothing to the user without the picture; they judge by look.

**How to apply:** for any "which look do you want?" question, export real frames from the source projects in Premiere (tools/premiere_bridge.py, set player position + QE exportFramePNG), compose one labeled sheet with PIL, send it with SendUserFile, then ask. If source media is offline, say so on the sheet. Related: [[restate-instructions-first]], [[concurrent-agents-same-folder]].
