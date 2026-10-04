// 案件のプロジェクト（PROJ）を保存せずに閉じる。閉じる前に、開いているシーケンス（SEQNAME）のトラックごとのクリップの始まり・終わり（ticks）が
// AI の最後の組み立ての .prproj と同じかを見る（EXPECT。null なら見ない）。違えば閉じない（ユーザーの保存していない直しを消さない）。
// ほかのプロジェクトには触らない。前面はユーザーが見ていたものに戻す。元：環境設定 v004 の _work/close_v004.py。close.py が埋めて送る
(function () {
  var PROJ = __PROJ__, SEQNAME = __SEQ__, EXPECT = __EXPECT__;
  var prevPath = String(app.project.path), prevSeqId = null;
  try { if (app.project.activeSequence) prevSeqId = String(app.project.activeSequence.sequenceID); } catch (e0) {}
  var p = __projectByPath(PROJ);
  if (!p) return JSON.stringify({closed: false, note: "not open", front: String(app.project.name)});
  var diffs = [];
  if (EXPECT) {
    try {
      var seq = null;
      for (var i = 0; i < p.sequences.numSequences; i++) { if (__nfc(p.sequences[i].name) === __nfc(SEQNAME)) seq = p.sequences[i]; }
      if (!seq) diffs.push("sequence not found: " + SEQNAME);
      else {
        var kinds = [["V", seq.videoTracks, EXPECT.video], ["A", seq.audioTracks, EXPECT.audio]];
        for (var k = 0; k < kinds.length; k++) {
          var tag = kinds[k][0], tracks = kinds[k][1], exp = kinds[k][2];
          if (tracks.numTracks !== exp.length) diffs.push(tag + " tracks " + tracks.numTracks + " / " + exp.length);
          for (var t = 0; t < Math.min(tracks.numTracks, exp.length); t++) {
            var tr = tracks[t], rows = [];
            for (var c = 0; c < tr.clips.numItems; c++) rows.push([String(tr.clips[c].start.ticks), String(tr.clips[c].end.ticks)]);
            rows.sort(function (x, y) { return Number(x[0]) - Number(y[0]); });
            var e = exp[t];
            if (rows.length !== e.length) { diffs.push(tag + (t + 1) + " clips " + rows.length + " / " + e.length); continue; }
            for (var r = 0; r < rows.length; r++) {
              if (rows[r][0] !== e[r][0] || rows[r][1] !== e[r][1]) { diffs.push(tag + (t + 1) + " clip " + r + " " + rows[r].join("-") + " / " + e[r].join("-")); break; }
            }
          }
        }
      }
    } catch (eC) { diffs.push("check failed: " + eC); }
    if (diffs.length) return JSON.stringify({closed: false, note: "live differs from the AI build", diffs: diffs.slice(0, 20), front: String(app.project.name)});
  }
  p.closeDocument(0, 0);
  try {
    for (var m = 0; m < app.projects.numProjects; m++) {
      var pr = app.projects[m];
      if (__nfc(String(pr.path)) === __nfc(prevPath) && prevSeqId) {
        for (var q = 0; q < pr.sequences.numSequences; q++) { if (String(pr.sequences[q].sequenceID) === prevSeqId) pr.openSequence(prevSeqId); }
      }
    }
  } catch (e3) {}
  return JSON.stringify({closed: true, checked: !!EXPECT, front: String(app.project.name), n: app.projects.numProjects});
})();
