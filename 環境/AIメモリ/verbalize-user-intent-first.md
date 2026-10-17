---
name: verbalize-user-intent-first
description: "When learning from the user's own Premiere edits (e.g. their cuts), articulate their intent in words and get confirmation before applying it to the rest"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1ac766ee-8aa3-4c67-af3a-433a068ad2ff
  modified: 2026-09-27T05:32:22.152Z
---

When the user edits part of a video themselves and asks me to continue "in the same way", first compare what they cut vs kept, put their **intent** into words (a yardstick + concrete principles with kept/cut examples from their edit), show it, and get confirmation before cutting anything.

**Why:** 2026-09-27, 画面解説 v009 — mid-task the user said they want me to verbalize how they intend their cuts before starting work; the listing of "types of cuts" alone wasn't enough, they wanted the why. The confirmed result is kept in `work/gamen_kaisetsu_20260926/analysis/user_edit_v008/カットの意図_v008.md`.

**How to apply:** Diff the before/after timelines by source ranges, list cut and kept lines side by side, write the principle ("does this help the viewer understand or copy X?") plus exceptions, and ask about the borderline cases (e.g. company plugs, authority quotes, CTA) before applying. Related: [[restate-instructions-first]].
