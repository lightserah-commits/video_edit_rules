// 案件のプロジェクト（PROJ）を開き（開いていなければ）、右上のタイトルのトラック（TT。0 から数える。既定 V8・V9）の
// 最初のクリップの頭にクロスディゾルブ（FR コマ）を付けて保存し、JOBS（[[タイムコード, 書き出し先], …]）の画像を書き出す。
// FR が 0 なら付けず、保存もしない。案件のプロジェクトは開いたままにし、前面はユーザーが見ていたプロジェクト・シーケンスに戻す。
// 元：環境設定 v004 の _work/finish_v004.jsx。finish.py が埋めて送る
(function () {
  var PROJ = __PROJ__, SEQNAME = __SEQ__, JOBS = __JOBS__, WAIT = __WAIT__, FR = __DISSOLVE__, TT = __TITLE_TRACKS__;
  var log = [];
  var prevPath = String(app.project.path), prevSeqId = null;
  try { if (app.project.activeSequence) prevSeqId = String(app.project.activeSequence.sequenceID); } catch (e0) {}
  log.push("front before: " + app.project.name);
  var p = __projectByPath(PROJ);
  if (!p) { app.openDocument(PROJ, true, true, true); p = __projectByPath(PROJ); log.push("opened"); }
  if (!p) return JSON.stringify({error: "could not open"});
  var seq = null;
  for (var i = 0; i < p.sequences.numSequences; i++) { if (__nfc(p.sequences[i].name) === __nfc(SEQNAME)) seq = p.sequences[i]; }
  if (!seq) return JSON.stringify({error: "sequence not found"});
  p.openSequence(seq.sequenceID);
  if (__nfc(app.project.path) !== __nfc(PROJ)) return JSON.stringify({error: "not active"});
  app.enableQE();
  var qs = qe.project.getActiveSequence();
  if (FR > 0) {
    var tr = qe.project.getVideoTransitionByName("クロスディゾルブ");
    if (!tr) tr = qe.project.getVideoTransitionByName("Cross Dissolve");
    if (!tr) return JSON.stringify({error: "cross dissolve not found"});
    var dur = "00:00:00:" + (FR < 10 ? "0" : "") + FR;
    for (var t = 0; t < TT.length; t++) {
      var v = TT[t];
      var qt = qs.getVideoTrackAt(v);
      var first = null;
      for (var k = 0; k < qt.numItems; k++) { var it = qt.getItemAt(k); if (it && it.type === "Clip") { first = it; break; } }
      if (first) {
        try { first.addTransition(tr, true, dur); log.push("dissolve V" + (v + 1) + " at " + first.start.timecode); }
        catch (eT) { log.push("dissolve V" + (v + 1) + " failed: " + eT); }      // QE の addTransition がたまに失敗する。失敗しても書き出しは続ける
      }
    }
    p.save();
    log.push("saved");
  }
  var offline = [];
  function walk(item) {
    for (var q = 0; q < item.children.numItems; q++) {
      var c = item.children[q];
      if (c.type === 2) { walk(c); continue; }
      try { if (c.isOffline && c.isOffline()) offline.push(String(c.name)); } catch (e1) {}
    }
  }
  walk(p.rootItem);
  if (WAIT) $.sleep(WAIT);
  var n = 0, errs = [];
  for (var j = 0; j < JOBS.length; j++) { try { qs.exportFramePNG(JOBS[j][0], JOBS[j][1]); n++; } catch (e) { errs.push(String(e)); } }
  if (__nfc(prevPath) !== __nfc(PROJ)) {
    try {
      for (var m = 0; m < app.projects.numProjects; m++) {
        var pr = app.projects[m];
        if (__nfc(String(pr.path)) === __nfc(prevPath) && prevSeqId) {
          for (var r = 0; r < pr.sequences.numSequences; r++) { if (String(pr.sequences[r].sequenceID) === prevSeqId) pr.openSequence(prevSeqId); }
        }
      }
    } catch (e3) { log.push("restore failed " + e3); }
  }
  log.push("front after: " + app.project.name);
  return JSON.stringify({exported: n, errs: errs, log: log, offline: offline});
})();
