#!/usr/bin/env python3
"""別のPC（Mac）で、このフォルダをコピーするだけで今と同じ編集環境にする（2026-10-17 小川さん「コピー&ペーストで俺と同じ環境が手に入る様に」）。
手順と決まりは `別のPCの準備.md`。どの Mac でも /usr/bin/python3（3.9）で動く。

使い方:
  python3 tools/setup_mac.py                 … 確かめるだけ（何も変えない）。足りないものと入れ方を出す
  python3 tools/setup_mac.py --install       … 足りないものを1つずつ聞きながら入れる（y で入れる）
  python3 tools/setup_mac.py --install --only fonts,panel --yes
                                             … 決めたものだけ、聞かずに入れる（AI が流す時。先にチャットで OK をもらう）
  python3 tools/setup_mac.py --pack          … 運ぶ前に（元の PC で）：Claude の AIメモリ・予定タスク・新しく入れたフォント・Composer の Pan を 環境/ に写す

入れるもの（--only の名前）:
  place   置き場所：~/Desktop/video_edit_rules でない所に置いた時は、そこへのリンクを作る（案件のスクリプトと Premiere のプロジェクトがこの場所を見る）
  brew    Homebrew の ffmpeg・whisper-cpp・python@3.14
  env     道具の Python（env/）と文字起こしのモデル（models/）。無ければ tools/setup_env.sh（ダウンロードあり）
  fonts   環境/フォント/ → ~/Library/Fonts（Adobe Fonts は Creative Cloud にログインして同期）
  panel   Premiere の MCP Bridge パネル（tools/premiere_panel/MCPBridgeCEP）と、署名なしのパネルを許す設定（PlayerDebugMode）
  composer  Premiere Composer の Starter Pack の Pan（本体は Mister Horse の Product Manager で入れる）
  memory  環境/AIメモリ/ → Claude の AI メモリの場所（~/.claude/projects/<このフォルダの場所から作る名前>/memory/）
  local   Mac ごとの設定：.claude/settings.local.json の追加フォルダをこの Mac の場所に直す・.claude/addness/cases_local.json
  links   ~/Downloads/コピー_… → 完成版/…（見本集の .prproj が完成版をこの場所で覚えている）
  keys    鍵（OpenAI の API キー・YouTube）があるか見るだけ。入れ方を出す（鍵はフォルダに入れない。2026-10-17 小川さん）
  git     GitHub に送れるか（gh auth status）
  hook    開始時の【Addness】の案内が出るか
"""
import argparse
import filecmp
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # このフォルダ（tools/ の1つ上）
HOME = Path.home()
STD_PLACE = HOME / "Desktop" / "video_edit_rules"
ENV_DIR = ROOT / "環境"
FONTS_SRC = ENV_DIR / "フォント"
FONTS_DST = HOME / "Library" / "Fonts"
PANEL_SRC = ROOT / "tools" / "premiere_panel" / "MCPBridgeCEP"
PANEL_DST = HOME / "Library" / "Application Support" / "Adobe" / "CEP" / "extensions" / "MCPBridgeCEP"
CSXS = ["com.adobe.CSXS.11", "com.adobe.CSXS.12"]
COMPOSER_SRC = ENV_DIR / "PremiereComposer" / "(3) Transitions"
COMPOSER_PRODUCT = HOME / "Library" / "Application Support" / "MisterHorse" / "ProductManager" / "Products" / "3283"
COMPOSER_DST = COMPOSER_PRODUCT / "Items" / "Starter Pack" / "(3) Transitions"
MEMORY_SRC = ENV_DIR / "AIメモリ"
TASK_SRC = ENV_DIR / "予定タスク" / "video-edit-addness-sync"
TASK_LOCAL = HOME / ".claude" / "scheduled-tasks" / "video-edit-addness-sync"
KEY_DIR = HOME / ".video_edit_rules" / "youtube"
CASES_DIR_NAME = "みかみ案件依頼書"


def memory_dir():
    """Claude の AI メモリの場所。フォルダの絶対パスの英数字以外を「-」にした名前（例 -Users-xxx-Desktop-video-edit-rules）"""
    return HOME / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(ROOT)) / "memory"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def same_tree(a, b):
    """a の中のファイルが、b に全部同じ中身である"""
    if not b.is_dir():
        return False
    for p in a.rglob("*"):
        if p.is_file() and p.name != ".DS_Store":
            q = b / p.relative_to(a)
            if not q.is_file() or not filecmp.cmp(p, q, shallow=False):
                return False
    return True


def merge_index(src, dst):
    """MEMORY.md は行を足し合わせる（両方の PC で書き足すので、新しい方で上書きすると行が消える）"""
    have = dst.read_text(encoding="utf-8").splitlines() if dst.exists() else []
    add = [l for l in src.read_text(encoding="utf-8").splitlines() if l.strip() and l not in have]
    if add:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("\n".join(have + add).rstrip("\n") + "\n", encoding="utf-8")
    return len(add)


def sync_memory(src_dir, dst_dir):
    """src_dir の AI メモリを dst_dir へ。無いか古いファイルだけ写す（新しい方を残す）。MEMORY.md は行を足し合わせる"""
    n = 0
    for p in sorted(src_dir.glob("*.md")):
        q = dst_dir / p.name
        if p.name == "MEMORY.md":
            n += 1 if merge_index(p, q) else 0
        elif not q.exists() or p.stat().st_mtime > q.stat().st_mtime + 1:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
            n += 1
    return n


def memory_missing():
    dst = memory_dir()
    out = []
    for p in sorted(MEMORY_SRC.glob("*.md")):
        q = dst / p.name
        if p.name == "MEMORY.md":
            have = q.read_text(encoding="utf-8").splitlines() if q.exists() else []
            if any(l.strip() and l not in have for l in p.read_text(encoding="utf-8").splitlines()):
                out.append(p.name)
        elif not q.exists() or p.stat().st_mtime > q.stat().st_mtime + 1:
            out.append(p.name)
    return out


# ---------- 1つずつの確かめと入れ方。check は (済み?, 説明) を返す ----------

def check_place():
    if ROOT == STD_PLACE.resolve():
        return True, f"置き場所 {ROOT}"
    if STD_PLACE.exists() or STD_PLACE.is_symlink():
        return False, f"{STD_PLACE} に別のものがある（このフォルダは {ROOT}）。どちらを使うか小川さんに聞く"
    return False, f"このフォルダは {ROOT}。{STD_PLACE} にリンクが無い（案件のスクリプトが見つけられない）"


def install_place():
    if STD_PLACE.exists() or STD_PLACE.is_symlink():
        print(f"  {STD_PLACE} に別のものがあるので何もしない")
        return
    STD_PLACE.symlink_to(ROOT)
    print(f"  リンクを作った：{STD_PLACE} → {ROOT}")


BREW_TOOLS = {"ffmpeg": "ffmpeg", "whisper-cli": "whisper-cpp", "python3.14": "python@3.14"}


def brew_missing():
    path = os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin"
    return [pkg for cmd, pkg in BREW_TOOLS.items() if not shutil.which(cmd, path=path)]


def check_brew():
    miss = brew_missing()
    return (not miss), ("Homebrew の道具はそろっている" if not miss else "足りない：" + "・".join(miss))


def install_brew():
    brew = shutil.which("brew", path=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin")
    if not brew:
        print("  Homebrew が無い。https://brew.sh の1行を、小川さんにターミナルで流してもらう（パスワードが要る）")
        return
    miss = brew_missing()
    print("  brew install " + " ".join(miss))
    subprocess.run([brew, "install"] + miss)


def check_env():
    py = ROOT / "env" / "bin" / "python"
    models = [ROOT / "models" / "whisper-large-v3-turbo" / "weights.safetensors", ROOT / "models" / "ggml-small.bin"]
    if not py.exists():
        return False, "env/ が無い"
    r = run([str(py), "-c", "import numpy, PIL, yaml, mlx_whisper"])
    if r.returncode != 0:
        return False, "env/ の Python が動かない（Apple Silicon と Homebrew の python@3.14 が要る。作り直すなら tools/setup_env.sh）：" + (r.stderr.strip().splitlines() or ["?"])[-1]
    miss = [str(m.relative_to(ROOT)) for m in models if not m.exists()]
    if miss:
        return False, "文字起こしのモデルが無い：" + "・".join(miss)
    return True, "道具の Python と文字起こしのモデルが動く"


def install_env():
    print("  zsh tools/setup_env.sh（env/ の作り直しと、無いモデルのダウンロード。約2GB）")
    subprocess.run(["zsh", str(ROOT / "tools" / "setup_env.sh")])


def fonts_missing():
    if not FONTS_SRC.is_dir():
        return []
    return [p for p in sorted(FONTS_SRC.iterdir()) if p.is_file() and p.name != ".DS_Store" and not (FONTS_DST / p.name).exists()]


def check_fonts():
    if not FONTS_SRC.is_dir():
        return False, "環境/フォント/ が無い（元の PC で --pack するか、フォルダごとコピーし直す）"
    miss = fonts_missing()
    return (not miss), ("フォントはそろっている（Adobe Fonts は別。Creative Cloud にログインして同期）" if not miss else f"入っていないフォント {len(miss)} 個：" + "・".join(p.name for p in miss[:6]) + ("…" if len(miss) > 6 else ""))


def install_fonts():
    FONTS_DST.mkdir(parents=True, exist_ok=True)
    for p in fonts_missing():
        shutil.copy2(p, FONTS_DST / p.name)
        print("  入れた：" + p.name)
    print("  A1ゴシック（AP-OTF-A1GOTHICSTD-BOLD）はモリサワの有料フォント。この PC に入れてよいかはライセンスで確かめる")


def debug_mode_off():
    return [d for d in CSXS if run(["defaults", "read", d, "PlayerDebugMode"]).stdout.strip() != "1"]


def check_panel():
    if not same_tree(PANEL_SRC, PANEL_DST):
        return False, f"Premiere のパネルが入っていないか古い（{PANEL_DST}）"
    off = debug_mode_off()
    if off:
        return False, "署名なしのパネルを許す設定が無い：" + "・".join(off)
    return True, "Premiere のパネルが入っている（Premiere の「ウィンドウ > エクステンション > MCP Bridge (CEP)」で開き、premiere_bridge.py status で bridge_panels: 1 を見る）"


def install_panel():
    PANEL_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PANEL_SRC, PANEL_DST, dirs_exist_ok=True)
    print(f"  パネルを入れた：{PANEL_DST}")
    for d in debug_mode_off():
        subprocess.run(["defaults", "write", d, "PlayerDebugMode", "1"])
        print(f"  defaults write {d} PlayerDebugMode 1")
    print("  Premiere を開き直すとパネルが出る")


def check_composer():
    if not COMPOSER_PRODUCT.is_dir():
        return False, "Premiere Composer が無い。Mister Horse の Product Manager で Premiere Composer と Starter Pack を入れる（締めの Pan。02 の transitions.closing_pan）"
    if not COMPOSER_DST.is_dir():
        return False, "Composer はあるが Starter Pack のトランジションが無い"
    return True, "Premiere Composer の Pan がある"


def install_composer():
    if not COMPOSER_PRODUCT.is_dir():
        print("  Composer の本体は Mister Horse の Product Manager で入れる（アカウントが要るので小川さんに頼む）")
        return
    if COMPOSER_SRC.is_dir():
        shutil.copytree(COMPOSER_SRC, COMPOSER_DST, dirs_exist_ok=True)
        print(f"  Pan を写した：{COMPOSER_DST}")


def check_memory():
    if not MEMORY_SRC.is_dir():
        return False, "環境/AIメモリ/ が無い"
    miss = memory_missing()
    return (not miss), ("AI メモリが入っている（" + str(memory_dir()) + "）" if not miss else f"AI メモリに無いか古いもの {len(miss)} 個（{memory_dir()}）")


def install_memory():
    n = sync_memory(MEMORY_SRC, memory_dir())
    print(f"  AI メモリを {n} 件入れた：{memory_dir()}")


LOCAL_SETTINGS = ROOT / ".claude" / "settings.local.json"
CASES_LOCAL = ROOT / ".claude" / "addness" / "cases_local.json"


def local_dirs_fixed():
    """settings.local.json の追加フォルダを、この Mac の場所に直したもの（無いフォルダは外す）"""
    import json
    data = json.loads(LOCAL_SETTINGS.read_text()) if LOCAL_SETTINGS.exists() else {}
    dirs = (data.get("permissions") or {}).get("additionalDirectories") or []
    out = []
    for d in dirs:
        p = Path(re.sub(r"^/Users/[^/]+", str(HOME), d))
        if p.is_dir() and str(p) not in out:
            out.append(str(p))
    cases = HOME / "Desktop" / CASES_DIR_NAME
    if cases.is_dir() and str(cases) not in out:
        out.append(str(cases))
    return data, dirs, out


def check_local():
    _, dirs, fixed = local_dirs_fixed()
    if not LOCAL_SETTINGS.exists():
        return False, ".claude/settings.local.json が無い（案件フォルダを書けない）"
    if dirs != fixed:
        return False, "追加フォルダがこの Mac の場所になっていない：" + "・".join(dirs)
    if not CASES_LOCAL.exists():
        return False, ".claude/addness/cases_local.json が無い"
    return True, "Mac ごとの設定はこの Mac 用（追加フォルダ：" + "・".join(fixed) + "）"


def install_local():
    import json
    data, _, fixed = local_dirs_fixed()
    perms = data.setdefault("permissions", {})
    perms["additionalDirectories"] = fixed
    # 元の PC の許可（/Users/<別の名前>/… を指すもの）は、この Mac では意味が無いので外す
    perms["allow"] = [a for a in perms.get("allow", []) if not re.search(r"/Users/(?!%s/)" % re.escape(HOME.name), a)]
    LOCAL_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print("  .claude/settings.local.json の追加フォルダ：" + "・".join(fixed))
    if not CASES_LOCAL.exists():
        CASES_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        CASES_LOCAL.write_text('{"cases": {}}\n')
        print("  .claude/addness/cases_local.json を作った")


def link_targets():
    d = ROOT / "完成版"
    return [p for p in sorted(d.glob("コピー_*")) if p.is_dir()] if d.is_dir() else []


def check_links():
    tg = link_targets()
    if not tg:
        return True, "完成版/ が無い（運ばなかった）。完成版と比べる時だけ要る"
    miss = [p.name for p in tg if not (HOME / "Downloads" / p.name).exists()]
    return (not miss), ("~/Downloads/コピー_… のリンクがある" if not miss else "~/Downloads にリンクが無い：" + "・".join(miss))


def install_links():
    for p in link_targets():
        q = HOME / "Downloads" / p.name
        if not q.exists() and not q.is_symlink():
            q.symlink_to(p)
            print(f"  リンクを作った：{q} → {p}")


def check_keys():
    notes = []
    if run(["security", "find-generic-password", "-s", "openai_api_key"]).returncode != 0:
        notes.append("OpenAI の API キーがキーチェーンに無い（画像生成 tools/gen_image.py）")
    if not (KEY_DIR / "token.json").exists():
        notes.append("YouTube の許可が無い（tools/youtube_upload.py）")
    return (not notes), ("鍵がある" if not notes else "；".join(notes))


def install_keys():
    print("  鍵はフォルダに入れない（2026-10-17 小川さん）。この PC で入れ直す：")
    print('  - OpenAI：キーをコピーしてから、小川さんにターミナルで  security add-generic-password -U -a "$USER" -s openai_api_key -w "$(pbpaste)"')
    print("  - YouTube：Air の ~/.video_edit_rules/youtube/client_secret.json を AirDrop で受け取り、python3 tools/youtube_upload.py auth --import <受け取った JSON>")


def check_git():
    gh = shutil.which("gh", path=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin")
    if not gh:
        return False, "gh が無い（brew install gh。GitHub に送るため）"
    r = run([gh, "auth", "status"])
    return r.returncode == 0, ("GitHub にログインしている" if r.returncode == 0 else "GitHub にログインしていない（小川さんに gh auth login を打ってもらう）")


def install_git():
    print("  小川さんにターミナルで  gh auth login  を打ってもらう（ブラウザでログイン）")


def check_hook():
    r = run([sys.executable, str(ROOT / ".claude" / "hooks" / "addness_session_start.py")], stdin=subprocess.DEVNULL)
    ok = r.returncode == 0 and "Addness" in r.stdout
    return ok, ("開始時の【Addness】の案内が出る" if ok else "開始時の案内が出ない：" + (r.stderr.strip().splitlines() or ["?"])[-1])


def install_hook():
    print("  フック（.claude/settings.json と .claude/hooks/）を確かめる。python3 が要る")


STEPS = [
    ("place", check_place, install_place),
    ("brew", check_brew, install_brew),
    ("env", check_env, install_env),
    ("fonts", check_fonts, install_fonts),
    ("panel", check_panel, install_panel),
    ("composer", check_composer, install_composer),
    ("memory", check_memory, install_memory),
    ("local", check_local, install_local),
    ("links", check_links, install_links),
    ("keys", check_keys, install_keys),
    ("git", check_git, install_git),
    ("hook", check_hook, install_hook),
]


def pack():
    """元の PC で、運ぶ前に 環境/ を最新にする"""
    src = HOME / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(ROOT)) / "memory"
    if src.is_dir():
        print(f"AI メモリ：{sync_memory(src, MEMORY_SRC)} 件を 環境/AIメモリ/ に写した")
    else:
        print(f"AI メモリが無い：{src}")
    if TASK_LOCAL.is_dir():
        shutil.copytree(TASK_LOCAL, TASK_SRC, dirs_exist_ok=True)
        print("予定タスク：環境/予定タスク/ に写した")
    FONTS_SRC.mkdir(parents=True, exist_ok=True)
    new = [p for p in sorted(FONTS_DST.iterdir()) if p.is_file() and p.name != ".DS_Store" and not (FONTS_SRC / p.name).exists()] if FONTS_DST.is_dir() else []
    for p in new:
        shutil.copy2(p, FONTS_SRC / p.name)
    print(f"フォント：新しいもの {len(new)} 個を 環境/フォント/ に写した")
    if COMPOSER_DST.is_dir():
        shutil.copytree(COMPOSER_DST, COMPOSER_SRC, dirs_exist_ok=True)
        print("Composer の Pan：環境/PremiereComposer/ に写した")
    boss = HOME / "Desktop" / "担当2"
    if boss.is_dir():
        for name in ["YT AI自動編集の方法 2", "03_編集ルール定義"]:
            if (boss / name).is_dir() and not same_tree(boss / name, ROOT / "上司の資料" / name):
                print(f"※ ~/Desktop/担当2/{name} が 上司の資料/ と違う。上司から新しい版が来たなら、小川さんに聞いて差し替える")
    r = run(["git", "-C", str(ROOT), "status", "--short"])
    if r.stdout.strip():
        print("※ Git にまだ送っていない変更がある（運ぶ前にコミットしておくと、別の PC と行き来しやすい）：")
        print("\n".join("   " + l for l in r.stdout.rstrip().splitlines()[:15]))


def main():
    ap = argparse.ArgumentParser(description="別のPCで今と同じ編集環境にする（別のPCの準備.md）")
    ap.add_argument("--install", action="store_true", help="足りないものを入れる（1つずつ聞く）")
    ap.add_argument("--yes", action="store_true", help="聞かずに入れる（AI が流す時。先にチャットで OK をもらう）")
    ap.add_argument("--only", help="入れるものを絞る（カンマ区切り：" + ",".join(s[0] for s in STEPS) + "）")
    ap.add_argument("--pack", action="store_true", help="運ぶ前に（元の PC で）環境/ を最新にする")
    a = ap.parse_args()
    if a.pack:
        pack()
        return
    only = set(a.only.split(",")) if a.only else None
    bad = 0
    for name, check, install in STEPS:
        if only and name not in only:
            continue
        ok, msg = check()
        print(f"[{'OK' if ok else '--'}] {name:8} {msg}")
        if ok or not a.install:
            bad += 0 if ok else 1
            continue
        if not a.yes and input(f"  {name} を入れますか？ [y/N] ").strip().lower() != "y":
            bad += 1
            continue
        install()
        ok, msg = check()
        print(f"  → [{'OK' if ok else '--'}] {msg}")
        bad += 0 if ok else 1
    print(f"\n足りないもの {bad} 件" + ("" if a.install or not bad else "（入れるには --install）"))


if __name__ == "__main__":
    main()
