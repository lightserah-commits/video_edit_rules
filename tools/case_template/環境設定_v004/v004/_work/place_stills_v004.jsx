// Air v001 の土台（最終）：見本集のコピー（__BASE__）を開き、土台の XML（__XML__）を読み込み、
// オフラインの素材（見本集の SE・BGM など）を 素材/ などの同じ名前のファイルにつなぎ直し、
// 画面の赤枠の画像（__STILLS__：[[パス, 映像トラック番号(0始まり), 開始ticks, 終了ticks], …]）を置いて保存して閉じる。
// 操作のあと、ユーザーが見ていたプロジェクト・シーケンスに戻す。
(function () {
  var BASE = "__BASE__", XML = "__XML__", SEQNAME = "__SEQ__", STILLS = __STILLS__, DIRS = __DIRS__;
  var log = [];
  var prevPath = String(app.project.path);
  var prevSeqId = null;
  try { if (app.project.activeSequence) prevSeqId = String(app.project.activeSequence.sequenceID); } catch (e0) {}
  log.push("front before: " + app.project.name);
  if (__projectByPath(BASE)) return JSON.stringify({error: "base is already open"});
  app.openDocument(BASE, true, true, true);
  var p = __projectByPath(BASE);
  if (!p) return JSON.stringify({error: "could not open base"});
  p.importFiles([XML], true, p.rootItem, false);
  var seq = null;
  for (var i = 0; i < p.sequences.numSequences; i++) { if (__nfc(p.sequences[i].name) === __nfc(SEQNAME)) seq = p.sequences[i]; }
  if (!seq) return JSON.stringify({error: "sequence not found after import", log: log});
  p.openSequence(seq.sequenceID);
  if (__nfc(app.project.path) !== __nfc(BASE)) return JSON.stringify({error: "base not active", log: log});
  // オフラインの素材をつなぎ直す
  var relinked = [], still_offline = [];
  function walk(item) {
    for (var k = 0; k < item.children.numItems; k++) {
      var c = item.children[k];
      if (c.type === 2) { walk(c); continue; }
      var off = false;
      try { off = c.isOffline && c.isOffline(); } catch (e1) {}
      if (!off) continue;
      var nm = String(c.name), done = false;
      for (var d = 0; d < DIRS.length && !done; d++) {
        var f = new File(DIRS[d] + "/" + nm);
        if (f.exists) {
          try { if (c.canChangeMediaPath() && c.changeMediaPath(f.fsName, true)) { relinked.push(nm); done = true; } } catch (e2) {}
        }
      }
      if (!done) still_offline.push(nm);
    }
  }
  walk(p.rootItem);
  // 赤枠の画像
  var paths = [];
  for (var s = 0; s < STILLS.length; s++) paths.push(STILLS[s][0]);
  if (paths.length) p.importFiles(paths, true, p.rootItem, false);
  function findItem(path) {
    for (var k = p.rootItem.children.numItems - 1; k >= 0; k--) {
      var c = p.rootItem.children[k];
      try { if (c.getMediaPath && __nfc(c.getMediaPath()) === __nfc(path)) return c; } catch (e) {}
    }
    return null;
  }
  var missing = [];
  for (var q = 0; q < STILLS.length; q++) {
    var st = STILLS[q], item = findItem(st[0]);
    if (!item) { missing.push(st[0]); continue; }
    var tin = new Time(); tin.ticks = "0";
    var tout = new Time(); tout.ticks = String(Number(st[3]) - Number(st[2]));
    item.setInPoint(tin, 4);
    item.setOutPoint(tout, 4);
    var at = new Time(); at.ticks = String(st[2]);
    seq.videoTracks[st[1]].overwriteClip(item, at);
  }
  var info = {clips: []};
  for (var v = 0; v < seq.videoTracks.numTracks; v++) info.clips.push("V" + (v + 1) + ":" + seq.videoTracks[v].clips.numItems);
  for (var a = 0; a < seq.audioTracks.numTracks; a++) info.clips.push("A" + (a + 1) + ":" + seq.audioTracks[a].clips.numItems);
  p.save();
  p.closeDocument(0, 0);
  try {
    for (var m = 0; m < app.projects.numProjects; m++) {
      var pr = app.projects[m];
      if (__nfc(String(pr.path)) === __nfc(prevPath) && prevSeqId) {
        for (var n = 0; n < pr.sequences.numSequences; n++) { if (String(pr.sequences[n].sequenceID) === prevSeqId) pr.openSequence(prevSeqId); }
      }
    }
  } catch (e3) { log.push("restore failed " + e3); }
  log.push("front after: " + app.project.name);
  return JSON.stringify({ok: true, log: log, info: info, relinked: relinked, still_offline: still_offline, missing: missing});
})();
