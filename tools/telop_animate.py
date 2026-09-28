#!/usr/bin/env python3
"""XMLで読み込んだテロップに、Premiere内でアニメーション（出方の動き）を付ける（試作）。

Final Cut Pro 7 XML には Premiere 専用エフェクト（トランスフォーム・指向性ブラー・色かぶり補正・ストロボ）が載らないため、
読み込んだ後に MCP Bridge 経由でエフェクトを足し、キーフレームを打つ。値は 05_アニメーション.yaml の実測値。

使い方（Pythonから）:
  from telop_animate import animate
  animate(project_name="telop_test_v001.prproj", sequence_name="アニメーションテスト_v002",
          plan={"ここが一番大事": "JUMP_UP", "なんでやねん": "SHAKE"})
"""
import json

from premiere_bridge import run

# 時間は「テロップの開始からの秒」。位置は画面比（0〜1）。値は完成版 みかみCH0726 のキーフレーム実測。
SLIDE_KEYS = [[0.0, [1.3125, 0.5]], [0.167, [0.5, 0.5]]]
POP_WIDTH = [[0.0, 0], [0.022, 59], [0.043, 92], [0.065, 103], [0.086, 104], [0.108, 103], [0.129, 101],
             [0.151, 100], [0.172, 99], [0.194, 100], [0.216, 100]]
SHAKE_KEYS = [[0.0, [0.5, 0.5]], [0.033, [0.495, 0.49]], [0.067, [0.505, 0.51]], [0.1, [0.508, 0.481]],
              [0.133, [0.497, 0.51]], [0.167, [0.495, 0.49]], [0.2, [0.5, 0.5]]]
PRESETS = {
    "SLIDE_RIGHT": [["トランスフォーム", {"位置": SLIDE_KEYS}]],
    "SLIDE_LEFT": [["トランスフォーム", {"位置": [[0.0, [-0.3125, 0.5]], [0.167, [0.5, 0.5]]]}]],
    "SLIDE_BLUR_RIGHT": [["トランスフォーム", {"位置": SLIDE_KEYS}], ["指向性ブラー (レガシー)", {"ブラーの長さ": [[0.0, 90], [0.2, 0]]}]],
    "JUMP_UP": [["トランスフォーム", {"位置": [[0.0, [0.5, 0.932]], [0.076, [0.5, 0.478]], [0.121, [0.5, 0.5]]]}]],
    "SHAKE": [["トランスフォーム", {"位置": SHAKE_KEYS}]],
    "POP": [["トランスフォーム", {"__uniform_off": True, "スケール (幅)": POP_WIDTH}]],
    "POP_FLASH": [["トランスフォーム", {"__uniform_off": True, "スケール (幅)": POP_WIDTH, "不透明度": [[0.0, 0], [0.167, 100]]}],
                  ["色かぶり補正", {"色合いの量": [[0.0, 100], [0.3, 0]]}]],
    "STROBE_IN": [["ストロボ", {"元の画像とブレンド": [[0.0, 0], [0.2, 100]]}]],
    "WIPE_RIGHT": [["クロップ", {"右": [[0.0, 100], [1.37, 0]]}]],
    "FADE_MOVE": [["トランスフォーム", {"不透明度": [[0.0, 0], [0.167, 100]], "位置": [[0.0, [0.5, 0.52]], [0.167, [0.5, 0.5]]]}]],
}

SCRIPT = r'''(function(){
  try {
    var p = app.project;
    if (String(p.name) !== __PROJECT__) return JSON.stringify({error: "active project is " + p.name});
    var seq = null;
    for (var i=0;i<p.sequences.numSequences;i++){ if (String(p.sequences[i].name) === __SEQUENCE__) seq = p.sequences[i]; }
    if (!seq) return JSON.stringify({error: "sequence not found"});
    p.openSequence(seq.sequenceID);
    if (String(app.project.name) !== __PROJECT__) return JSON.stringify({error: "active project changed"});
    app.enableQE();
    var qs = qe.project.getActiveSequence();
    var plan = __PLAN__;
    var log = [];
    for (var ti=0; ti<seq.videoTracks.numTracks; ti++){
      var track = seq.videoTracks[ti];
      var qt = qs.getVideoTrackAt(ti);
      for (var ci=0; ci<track.clips.numItems; ci++){
        var clip = track.clips[ci];
        var nm = String(clip.name);
        var steps = plan[nm];
        if (!steps) continue;
        var qitem = null;
        for (var qi=0; qi<qt.numItems; qi++){ var it = qt.getItemAt(qi); if (it && String(it.name) === nm) { qitem = it; break; } }
        if (!qitem) { log.push(nm + ": QE item not found"); continue; }
        for (var e=0; e<steps.length; e++){
          var effName = steps[e][0], params = steps[e][1];
          qitem.addVideoEffect(qe.project.getVideoEffectByName(effName));
          var comp = null;
          for (var k=0; k<clip.components.numItems; k++){ if (String(clip.components[k].displayName) === effName) comp = clip.components[k]; }
          if (!comp) { log.push(nm + ": effect not attached " + effName); continue; }
          var entry = nm + " +" + effName;
          if (params.__uniform_off) {
            var up = comp.properties.getParamForDisplayName("縦横比を固定");
            if (up) { up.setValue(false, true); entry += " 縦横比=off"; }
          }
          var t0 = clip.inPoint.seconds;
          for (var key in params) {
            if (key === "__uniform_off") continue;
            var prop = comp.properties.getParamForDisplayName(key);
            if (!prop) {
              var names = []; for (var q=0;q<comp.properties.numItems;q++) names.push(String(comp.properties[q].displayName));
              entry += " [no param " + key + " in " + names.join("|") + "]"; continue;
            }
            prop.setTimeVarying(true);
            var keys = params[key];
            for (var kk=0; kk<keys.length; kk++){ var t = t0 + keys[kk][0]; prop.addKey(t); prop.setValueAtKey(t, keys[kk][1], true); }
            var got = prop.getKeys();
            entry += " " + key + ":" + (got ? got.length : 0);
          }
          log.push(entry);
        }
      }
    }
    return JSON.stringify({log: log});
  } catch(err) { return JSON.stringify({err: String(err), line: err.line}); }
})();'''


def animate(project_name, sequence_name, plan):
    """plan: {クリップ名: プリセット名}"""
    steps = {name: PRESETS[preset] for name, preset in plan.items()}
    script = (SCRIPT.replace("__PROJECT__", json.dumps(project_name, ensure_ascii=False))
              .replace("__SEQUENCE__", json.dumps(sequence_name, ensure_ascii=False))
              .replace("__PLAN__", json.dumps(steps, ensure_ascii=False)))
    return run(script, timeout=300)
