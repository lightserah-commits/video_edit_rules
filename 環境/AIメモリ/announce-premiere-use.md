---
name: announce-premiere-use
description: User hand-edits other videos in the same Premiere; announce in chat before and after each Premiere step, never save/close their projects, restore their sequence
metadata:
  type: feedback
---

The user sometimes fixes another video by hand in the same Premiere Pro while I work (stated 2026-09-27 in the ワークの完全解説 request). Before any step that drives Premiere (import, open, save, export), say so in one line in chat ("これから Premiere を使います…"), and say "Premiere の作業は終わりました" when done — even if they may be asleep. Never save or close projects that are not AI-made versions; after each operation, bring back the project/sequence that was in front (record `app.project.path` + `activeSequence.sequenceID` at the start of the script and reopen it at the end, including after exporting review frames).

**Why:** a surprise switch of the front project or a save of their project can clobber their manual edits.

**How to apply:** build the restore into every jsx (see work/cowork_kaisetsu_20260927/v001/_work/place_stills_v001.jsx, finish_v001.jsx). Related: [[concurrent-agents-same-folder]].
