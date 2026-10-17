---
name: youtube-preview-upload
description: "Previews go to the user's personal YouTube channel as private via tools/youtube_upload.py — never みかみCH, never unlisted/public"
metadata:
  node_type: memory
  type: project
  originSessionId: 8f7dba17-95e6-4063-be4e-0a6de2dcd991
  modified: 2026-10-16T07:01:59.114Z
---

2026-10-16: the user wants to watch exported versions on their phone while out (Jump Desktop is painful). Chosen: upload to **their personal YouTube channel, private only**, with `tools/youtube_upload.py` (stdlib only; keys in `~/.video_edit_rules/youtube/`).

**Why:** unaudited Google Cloud projects get API uploads locked to private anyway, and private is enough for self-viewing. みかみCH is excluded (drafts piling up in Studio, accidental publish, BGM claims).

**How to apply:** after export + length/blackout checks, run `upload --dry`, show file/title/channel in chat, upload only after OK, then put the URL in chat and the case's Addness goal. If the user wants a shareable link for others, that needs the YouTube API audit; raise it, don't work around it. Setup status and next steps live in the Addness child goal under the overall goal. Related: [[announce-premiere-use]]
