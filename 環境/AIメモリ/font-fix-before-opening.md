---
name: font-fix-before-opening
description: Never open a .prproj in Premiere that still contains fonts missing on this Mac; run tools/font_fix.py to a copy first (the フォントを解決 dialog annoys the user)
metadata:
  node_type: memory
  type: feedback
  originSessionId: da09afcf-4bae-4d8e-86f5-0a25078ddcba
  modified: 2026-09-26T15:39:52.359Z
---

On 2026-09-26 and again 2026-09-27 the user complained about Premiere's 「フォントを解決（解決不能）」 dialog: 「毎回出てくるのうざい」「出てこない様に直して」. The second time it came from me opening an analysis copy of the 2本目 project (HiraKakuStdN-W8) that had not been font-fixed. The dialog also blocks ExtendScript openDocument until clicked.

**Why:** the user watches Premiere while I work; a modal popping up on every open is disruptive, and it stalls my scripts.

**How to apply:** before opening any .prproj in Premiere (reference projects, analysis copies, new versions), run `python3 tools/font_fix.py --scan <file>`; if anything is found, write a fixed copy with `tools/font_fix.py <in> <out>` (never overwrite the user's original) and open the copy. Fixed reference copies already exist: `work/gamen_kyoyu_20260926/analysis/ルール調査/ref1/mikami_final_ff.prproj` (完成版) and `…/ref2/ai_jidai_copy_ff.prproj` (2本目). Related: [[concurrent-agents-same-folder]].
