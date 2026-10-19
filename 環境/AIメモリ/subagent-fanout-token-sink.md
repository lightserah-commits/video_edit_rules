---
name: subagent-fanout-token-sink
description: "Why weekly quota drained fast (2026-10-05): parallel subagent fan-out (台本係/検査係/装飾係/赤枠 etc.); since 2026-10-20 don't ask how many — just state the weekly % estimate and go"
metadata:
  node_type: memory
  type: feedback
  originSessionId: ce42714c-40e0-4ad9-bca8-7716c2b2ad4e
  modified: 2026-10-05T03:18:35.987Z
---

User did not ask for subagents/Workflow; they noticed the quota (週のメーター) draining far faster than in the first videos (9/26–9/28) and asked for root cause (2026-10-05).

Findings (transcripts + get_usage): weekly 1% ≈ 12–13M weighted tokens (cache read ×0.1, write ×2, output ×5). First 3 days (2–3 videos, main chat only) ≈ 210M ≈ 17%. One video (1003 AIで稼ぐ系, session 2fc21b56, overnight) ≈ 280M ≈ 22% (weekly 4% → 22%). 66 subagents × ~93 calls, each agent's context grew 58k → ~460k and was re-read every call; cache read 65% + cache write 35%, real output <1%.

Causes: (a) Ultracode ("エフォート最強") was on in 10 sessions 10/2 16:54 JST – 10/5 00:21 and told the AI "use Workflow on every task, token cost is not a constraint"; (b) 作業状況.md / 案件メモ recorded "環境設定 v004 と同じ流れ＝台本係10人＋検査係10人の並列" etc. as the standard procedure, so it continued even with Ultracode off.

**Why:** the user is stressed by the meter; fan-out gave no visible quality gain they asked for.
**Update 2026-10-20:** 小川さん「毎回エージェント何人動かすか聞かれるんだけど、それをなくしたい。週の使用量の目安だけ教えてくれればいい」. Asking every time was friction; the meter worry is handled by the one-line estimate.

**How to apply:** never ask how many agents to run — decide yourself. For ≥3 subagents / Workflow, post one line before starting (e.g.「別の AI：6人（台本係2・検査係2・確かめ係2）。週の使用量 27% → 見込み 35%」, from `get_usage`) and start without waiting for OK, also when the user is away. Ask only if the estimate would push the week past 90% (offer a smaller plan; when away, shrink to fit and report it). If usage grows >1.5× the estimate mid-run, stop stuck/bloated agents and post why and the new estimate. Rule text: 編集の依頼文.md「別の AI の使い方」; keep each agent's context small (no whole transcripts/many images); keep Ultracode off for routine editing; check `get_usage` before/after big steps. See [[concurrent-agents-same-folder]].

See also [[check-usage-before-fan-out]] (written by the overnight session: 5-hour window reached 80% at 06:50 JST, weekly 22%).
