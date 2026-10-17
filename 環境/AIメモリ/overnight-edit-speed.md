---
name: overnight-edit-speed
description: User noticed an overnight edit was slower than usual (2026-10-17 security case); give ETAs and watch for stuck renders
metadata:
  node_type: memory
  type: feedback
  originSessionId: 7c93d702-dcf7-4d80-88b5-2e27e33cd08a
  modified: 2026-10-17T02:13:16.554Z
---

2026-10-17 朝、セキュリティについての案件（夜に「朝までに」と頼まれた）で、小川さんに「遅くね？いつもより編集」と言われた。原因は、確かめ係を2回まわして版を v003 まで作ったこと・図解の描画が止まった Chrome（headless）の残りで約4時間止まっていたのに気づくのが遅れたこと・朝になって音の段差が見つかったこと。

**Why:** 小川さんは朝に出来上がりを見る前提で寝ている。止まっていても報告が無いと、待たされている理由が分からない。

**How to apply:** 夜の作業も、10分を超える段は始める前に終わる見込みの表を出す（依頼文の「長い作業・急ぎの時」）。図解の描画は、始める前と止まった時に、残っている `--headless=new` の Chrome を探して止める（run_zukai.py を使う）。待ちの until ループには上限時間を付け、止まったらすぐ気づけるようにする。見込みより遅れたら、その時点でチャットに理由と新しい見込みを書く。関連：[[check-usage-before-fan-out]]・[[subagent-fanout-token-sink]]
