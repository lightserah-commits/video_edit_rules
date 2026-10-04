"""Premiere で開いている kankyo_v004.prproj を保存せずに閉じる（作り直す前に。ほかのプロジェクトには触らない）。前面はユーザーが見ていたものに戻す
  python3 v004/_work/close_v004.py"""
import os, sys
ROOT = os.path.expanduser("~/Desktop/video_edit_rules")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from premiere_bridge import run
HERE = os.path.dirname(os.path.abspath(__file__))
proj = os.path.join(os.path.dirname(HERE), "kankyo_v004.prproj")
js = open(os.path.join(ROOT, "tools", "premiere_helpers.jsx"), encoding="utf-8").read() + """
(function () {
  var PROJ = "%s";
  var prevPath = String(app.project.path), prevSeqId = null;
  try { if (app.project.activeSequence) prevSeqId = String(app.project.activeSequence.sequenceID); } catch (e0) {}
  var p = __projectByPath(PROJ);
  if (!p) return JSON.stringify({closed: false, note: "not open", front: String(app.project.name)});
  p.closeDocument(0, 0);
  try {
    for (var m = 0; m < app.projects.numProjects; m++) {
      var pr = app.projects[m];
      if (__nfc(String(pr.path)) === __nfc(prevPath) && prevSeqId) {
        for (var r = 0; r < pr.sequences.numSequences; r++) { if (String(pr.sequences[r].sequenceID) === prevSeqId) pr.openSequence(prevSeqId); }
      }
    }
  } catch (e3) {}
  return JSON.stringify({closed: true, front: String(app.project.name), n: app.projects.numProjects});
})();
""" % proj
print(run(js, timeout=120))
