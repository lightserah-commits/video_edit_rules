// 案件のシーケンスを Media Encoder の書き出し待ちに入れて書き出しを始める（Premiere 本体は固まらない）。
// 前面のプロジェクト・シーケンスは変えない（案件のプロジェクトが開いていなければ開いて、最後にユーザーのシーケンスに戻す）。保存しない。
// 元：環境設定 v004 の _work/export_ame_v004.jsx。export.py が埋めて送る
(function () {
  var PROJ = __PROJ__, SEQNAME = __SEQ__, OUT = __OUT__, PRESET = __PRESET__;
  var prevPath = String(app.project.path), prevSeqId = null;
  try { if (app.project.activeSequence) prevSeqId = String(app.project.activeSequence.sequenceID); } catch (e0) {}
  var log = ["front before: " + app.project.name];
  var p = __projectByPath(PROJ);
  if (!p) { app.openDocument(PROJ, true, true, true); p = __projectByPath(PROJ); log.push("opened"); }
  if (!p) return JSON.stringify({error: "could not open"});
  var seq = null;
  for (var i = 0; i < p.sequences.numSequences; i++) { if (__nfc(p.sequences[i].name) === __nfc(SEQNAME)) seq = p.sequences[i]; }
  if (!seq) return JSON.stringify({error: "sequence not found"});
  app.encoder.launchEncoder();
  var job = app.encoder.encodeSequence(seq, OUT, PRESET, 0, 1);
  app.encoder.startBatch();
  try {
    for (var m = 0; m < app.projects.numProjects; m++) {
      var pr = app.projects[m];
      if (__nfc(String(pr.path)) === __nfc(prevPath) && prevSeqId) {
        for (var r = 0; r < pr.sequences.numSequences; r++) { if (String(pr.sequences[r].sequenceID) === prevSeqId) pr.openSequence(prevSeqId); }
      }
    }
  } catch (e3) { log.push("restore failed " + e3); }
  log.push("front after: " + app.project.name);
  return JSON.stringify({job: String(job), out: OUT, log: log});
})();
