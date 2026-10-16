// 案件のプロジェクト（PROJ）のシーケンス（SEQNAME）の、つなぎ目（TICKS＝SEC 秒）に Premiere Composer の「Pan [Left]」（FILE）を付けて保存し、閉じて前面を戻す。
// Composer のパネルが押した時と同じ関数（$.mhac.importUtils.safeInsertTransition）を呼ぶ。Premiere で Composer のパネルを一度開いておくこと（関数が読み込まれる）。
// このプロジェクトが開いている時は何もしない（ユーザーの保存していない直しを一緒に保存しない。close.py で閉じてから）。
// 元：1015claude project開設 v007 の _work/apply_pan.py・_work/composer/apply_pan.jsx（2026-10-16）。pan.py が埋めて送る
(function () {
  var PROJ = __PROJ__, SEQNAME = __SEQ__, FILE = __FILE__, TICKS = __TICKS__, SEC = __SEC__;
  var prevPath = app.project ? String(app.project.path) : "", prevSeqId = null;
  try { if (app.project.activeSequence) prevSeqId = String(app.project.activeSequence.sequenceID); } catch (e0) {}
  if (typeof $.mhac === "undefined" || !$.mhac.importUtils || !$.mhac.importUtils.safeInsertTransition)
    return JSON.stringify({ok: false, err: "Composer の関数が無い（Premiere で Composer のパネルを一度開く）"});
  if (__projectByPath(PROJ)) return JSON.stringify({ok: false, err: "このプロジェクトはもう開いている（close.py で閉じてから）"});
  app.openDocument(PROJ, true, false, false, true);
  $.sleep(3000);
  var p = __projectByPath(PROJ);
  if (!p) return JSON.stringify({ok: false, err: "開けない"});
  var res = {ok: false};
  try {
    var seq = null;
    for (var i = 0; i < p.sequences.numSequences; i++) { if (__nfc(p.sequences[i].name) === __nfc(SEQNAME)) seq = p.sequences[i]; }
    if (!seq) throw "シーケンスが無い: " + SEQNAME;
    p.openSequence(seq.sequenceID);
    if (__nfc(String(app.project.path)) !== __nfc(PROJ)) throw "前面がこのプロジェクトにならない: " + app.project.name;
    var act = app.project.activeSequence;
    if (!act || __nfc(act.name) !== __nfc(SEQNAME)) throw "開いているシーケンスが違う";
    var nv0 = act.videoTracks.numTracks, na0 = act.audioTracks.numTracks;
    act.setPlayerPosition(TICKS);
    // 長さ 0.5005秒・切り替わりの点は Composer の Pan [Left] の値（1015 v007 でパネルが渡していたもの）
    $.mhac.importUtils.safeInsertTransition(FILE, {duration: 0.5005, splitPoints: [0.13346666666666668], videoTracks: 2, audioTracks: 1}, true);
    var found = [];
    for (var v = 0; v < act.videoTracks.numTracks; v++) {
      var tr = act.videoTracks[v];
      for (var c = 0; c < tr.clips.numItems; c++) {
        var cl = tr.clips[c];
        if (v >= nv0 && cl.start.seconds > SEC - 1 && cl.start.seconds < SEC + 1) found.push("V" + (v + 1) + " " + cl.name + " " + cl.start.seconds.toFixed(3) + "-" + cl.end.seconds.toFixed(3));
      }
    }
    for (var a = 0; a < act.audioTracks.numTracks; a++) {
      var at = act.audioTracks[a];
      for (var d = 0; d < at.clips.numItems; d++) {
        var ac = at.clips[d];
        if (a >= na0 && ac.start.seconds > SEC - 1 && ac.start.seconds < SEC + 1) found.push("A" + (a + 1) + " " + ac.name + " " + ac.start.seconds.toFixed(3) + "-" + ac.end.seconds.toFixed(3));
      }
    }
    res = {ok: true, tracks_before: [nv0, na0], tracks_after: [act.videoTracks.numTracks, act.audioTracks.numTracks], found: found, pos: act.getPlayerPosition().seconds};
    p.save();
    res.saved = true;
  } catch (e1) { res = {ok: false, err: String(e1)}; }
  p.closeDocument(0, 0);
  try {
    for (var m = 0; m < app.projects.numProjects; m++) {
      var pr = app.projects[m];
      if (__nfc(String(pr.path)) === __nfc(prevPath) && prevSeqId) {
        for (var q = 0; q < pr.sequences.numSequences; q++) { if (String(pr.sequences[q].sequenceID) === prevSeqId) pr.openSequence(prevSeqId); }
      }
    }
  } catch (e3) {}
  res.front_after = app.project ? String(app.project.name) : "";
  return JSON.stringify(res);
})();
