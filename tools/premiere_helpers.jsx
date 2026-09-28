// Premiere の ExtendScript（MCP Bridge 経由で送るスクリプト）の先頭に付けて使う補助。
// Mac のファイル名は濁点・半濁点が別の文字（NFD）で返ってくるので、パスや名前は __nfc() でそろえてから比べる。
// 例: var p = __projectByPath("/Users/.../案件.prproj");  → 開いているプロジェクトからパスで探す（無ければ null）
function __nfc(s) {  // 濁点・半濁点が別の文字になっている（NFD）を、1文字にまとめる
  s = String(s); var out = "";
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i), n = i + 1 < s.length ? s.charCodeAt(i + 1) : 0;
    if (n === 0x3099) { out += String.fromCharCode(c === 0x30A6 ? 0x30F4 : (c === 0x3046 ? 0x3094 : c + 1)); i++; }
    else if (n === 0x309A) { out += String.fromCharCode(c + 2); i++; }
    else out += s.charAt(i);
  }
  return out;
}
function __projectByPath(path) {
  var want = __nfc(path);
  for (var i = 0; i < app.projects.numProjects; i++) { var p = app.projects[i]; if (__nfc(p.path) === want) return p; }
  return null;
}
