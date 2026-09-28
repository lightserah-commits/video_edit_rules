// 「よく使う素材」ビンの入れ物を Premiere で作る（tools/build_favorites.py setup から呼ぶ）。
//   __PROJ__ のプロジェクト（開いていなければ開く）に、ビン「よく使う素材」「テロップ（SEつき）」「SE」を作り、
//   __NAMES__ の名前の空のシーケンス（__BASE__ の頭1秒のサブシーケンス。中身は build_favorites.py fill で入れ替える）を「テロップ（SEつき）」に、
//   __SES__（[[パス, 名前], …]）の SE を「SE」に読み込んで名前を付け、保存する。
//   __BASE__ のイン・アウトは元に戻す。作ったシーケンスのタブは閉じる。最後に __CLOSE__ なら閉じる。前面は元のプロジェクト・シーケンスに戻す
(function () {
  var PROJ = "__PROJ__", BASE = "__BASE__", NAMES = __NAMES__, SES = __SES__, CLOSE = __CLOSE__;
  var ROOT = "__BIN_ROOT__", BT = "__BIN_TELOP__", BS = "__BIN_SE__";
  var log = [];
  var prevPath = String(app.project.path), prevSeqId = null;
  try { if (app.project.activeSequence) prevSeqId = String(app.project.activeSequence.sequenceID); } catch (e0) {}
  var p = __projectByPath(PROJ);
  var opened = false;
  if (!p) { app.openDocument(PROJ, true, true, true); p = __projectByPath(PROJ); opened = true; }
  if (!p) return JSON.stringify({error: "could not open"});
  var base = null;
  for (var i = 0; i < p.sequences.numSequences; i++) { if (__nfc(p.sequences[i].name) === __nfc(BASE)) base = p.sequences[i]; }
  if (!base) return JSON.stringify({error: "base sequence not found"});
  p.openSequence(base.sequenceID);
  if (__nfc(String(app.project.path)) !== __nfc(PROJ)) return JSON.stringify({error: "project not active"});

  function child(parent, name) {
    for (var k = 0; k < parent.children.numItems; k++) {
      var c = parent.children[k];
      if (c.type === ProjectItemType.BIN && __nfc(c.name) === __nfc(name)) return c;
    }
    return parent.createBin(name);
  }
  var root = child(p.rootItem, ROOT), bt = child(root, BT), bs = child(root, BS);

  // 既にある同じ名前のシーケンスは作らない
  var have = {};
  for (var h = 0; h < bt.children.numItems; h++) have[__nfc(bt.children[h].name)] = true;
  var inT = base.getInPointAsTime(), outT = base.getOutPointAsTime();
  var made = [], errs = [];
  base.setInPoint(0);
  base.setOutPoint(1);
  for (var n = 0; n < NAMES.length; n++) {
    if (have[__nfc(NAMES[n])]) { log.push("exists " + NAMES[n]); continue; }
    try {
      var s = base.createSubsequence(false);
      s.name = NAMES[n];
      s.projectItem.moveBin(bt);
      try { s.close(); } catch (ec) {}
      made.push(NAMES[n]);
    } catch (e) { errs.push(NAMES[n] + ": " + e); }
  }
  base.setInPoint(inT.seconds);
  base.setOutPoint(outT.seconds);
  p.openSequence(base.sequenceID);

  // SE を読み込んで名前を付ける
  var haveSe = {};
  for (var h2 = 0; h2 < bs.children.numItems; h2++) { try { haveSe[__nfc(bs.children[h2].getMediaPath())] = true; } catch (e5) {} }
  var paths = [];
  for (var q = 0; q < SES.length; q++) if (!haveSe[__nfc(SES[q][0])]) paths.push(SES[q][0]);
  if (paths.length) p.importFiles(paths, true, bs, false);
  var named = 0;
  for (var c2 = 0; c2 < bs.children.numItems; c2++) {
    var it = bs.children[c2], mp = "";
    try { mp = __nfc(it.getMediaPath()); } catch (e6) { continue; }
    for (var q2 = 0; q2 < SES.length; q2++) if (__nfc(SES[q2][0]) === mp) { it.name = SES[q2][1]; named++; }
  }
  p.save();
  log.push("saved");
  if (CLOSE) { p.closeDocument(0, 0); log.push("closed"); }
  try {
    for (var m = 0; m < app.projects.numProjects; m++) {
      var pr = app.projects[m];
      if (__nfc(String(pr.path)) === __nfc(prevPath) && prevSeqId) {
        for (var r = 0; r < pr.sequences.numSequences; r++) { if (String(pr.sequences[r].sequenceID) === prevSeqId) pr.openSequence(prevSeqId); }
      }
    }
  } catch (e3) { log.push("restore failed " + e3); }
  return JSON.stringify({made: made.length, se_imported: paths.length, se_named: named, errs: errs, log: log, in_out_restored: [inT.seconds, outT.seconds], front: String(app.project.name)});
})();
