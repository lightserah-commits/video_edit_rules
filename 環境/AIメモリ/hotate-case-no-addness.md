---
name: hotate-case-no-addness
description: ほたてちゃんねるの案件（hotate_taisho_20261009）は Addness に置かない。記録は edit/00_案件メモ.md だけ
metadata:
  node_type: memory
  type: project
  originSessionId: 4bb4aec8-ff73-4f25-bac9-f1d6e51cebc7
  modified: 2026-10-09T05:49:42.098Z
---

ほたてちゃんねる「大将」（`~/Desktop/ほたてバックアップ/中出し/コピー_大将/edit/`、案件ID hotate_taisho_20261009）は Addness に置かない（2026-10-09 小川さん「addnessには置かないで」）。みかみCH ではない別チャンネルの仕事。トンマナの正は YouTube の見本（ほたてちゃんねる「2回目のデートに繋がらない男性」）で、みかみCH の見た目のルールは使わない。

**Why:** みかみCH のゴール（創太さんの「月に30本YouTube上げる」の下）とは関係のない仕事なので。
**How to apply:** この案件では get_goal_context・append_goal_memory などの Addness への書き込みをしない。cases_local.json の `"addness": false` で Stop フックの催促から外してある（.claude/hooks/addness_common.py の local_records）。ほかのほたての案件が来たら、同じでよいか一度聞く。関連：[[addness-goal-placement]]
