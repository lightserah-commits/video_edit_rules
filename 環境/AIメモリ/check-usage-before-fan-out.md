---
name: check-usage-before-fan-out
description: "Before launching many parallel subagents or long image-review passes, check the plan usage (get_usage); the 1003 case took the 5-hour window to 80% by 06:50 JST"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 2fc21b56-2377-42ca-bde3-2ad9ea610e2c
  modified: 2026-10-04T21:56:23.614Z
---

When a case needs a big fan-out (台本係10・検査係10・装飾係10・赤枠5束…) call `mcp__ccd_session_mgmt__get_usage` first and again between stages; report the usage in 確認_vNNN.md (「使用量」).

**Why:** the 1003 AIで稼ぐ系 case (2026-10-05, user asleep, "あとはよろしく") used ~6 h of continuous fan-out; at 06:50 JST the 5-hour window was at 80% (weekly 22%) with a reset at 07:20 JST. The user has other sessions about 燃費 (token cost) and was told parallel agents can be reduced on request. Hitting the limit mid-Premiere-step would leave the project closed/half-built.

**How to apply:** run the cheap script stages while usage is high, defer image reviews and Addness-writing agents until after a reset, and keep long-running verifier agents bounded (they can think for 10+ minutes per step). Related: [[concurrent-agents-same-folder]].
