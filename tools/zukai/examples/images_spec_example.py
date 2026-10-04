# 画像を出す所の書き方の例（tools/zukai/gen_images.py が読む。案件では <図解のフォルダ>/images_spec.py に書く）。
# 環境設定 v004 の I01・I03・I07 から（字幕ID と画像の名前はその案件のもの。全部は tools/case_template/環境設定_v004/v004/zukai/gen_images.py）。
# 使える名前：S(字幕ID)・E(字幕ID)・spec・photo・card・text・arrow・cross・tl・ZUKAI・OUT・json
# 置き方の決まり：顔・右上のタイトル・強調の黒い帯・問いの札にかけない。比べる2枚は上端・下端をそろえる。言葉の頭に出す

# I01 スパイク：横の写真 → 裏の写真 → 平らな底と見比べ（2枚目以降は言葉の頭に前倒し）
s0 = S("161"); r = lambda c: S(c) - s0
spec("I01", "スパイク（横 → 裏のポイント → 平らな底と見比べ）", "161", S("172"), [
    photo("p1", "img_spike_side.jpg", 510, 110, 900, 600, 0, r("162")),
    photo("p2", "img_spike_sole.jpg", 735, 80, 450, 600, r("162"), r("168"), label="スパイクの裏"),
    photo("p3", "img_flat_sole.jpg", 150, 150, 780, 520, r("168"), label="ポイントなし"),
    photo("p4", "img_spike_sole.jpg", 1190, 150, 330, 520, r("170"), label="ポイント付き", objpos="15% 50%"),   # 顔の右半分を避けた細い枠
], [(0, "ピコンッ"), (r("162"), "ピコンッ"), (r("168"), "ピコンッ"), (r("170"), "ピコンッ")],
    "161「スパイクってさ」横 → 162「ポイントあるやん」裏 → 168「みんなポイントなしで」平らな底 → 170「俺だけポイント付き」右に裏。172 の頭で消す")

# I03 ロゴの札を縦に並べ、VS を叩きつける。途中で左の札を替え、同じコマで右下を消す
s0 = S("1179"); r = lambda c: S(c) - s0
spec("I03", "Cursor VS OpenAI・Anthropic → Addness VS OpenAI", "1179", S("1188"), [
    card("c1", "logo_cursor.svg", "", 60, 170, 0, r("1187"), logo_h=100),
    card("c4", "logo_addness_clear.png", "", 60, 170, r("1187"), logo_h=80),   # 背景を抜いた公式ロゴ
    text("vs", "VS", 330, 420, r("1185"), size=150),
    card("c2", "logo_openai_wordmark.svg", "", 60, 510, r("1184"), logo_h=90),
    card("c3", "logo_anthropic.svg", "", 60, 680, r("1184") + 8, r("1187"), logo_h=60),
], [(0, "cursor"), (r("1184"), "cursor"), (r("1185"), "ドン"), (r("1187"), "cursor")],
    "1179 Cursor → 1184 OpenAI と Anthropic → 1185 VS → 1187 左が Addness に替わり ANTHROPIC を消す")

# I07 写真に「捨てよ」で赤い×（×は写真の真ん中。右上のタイトルにかけない）
spec("I07", "このキュウリはやばいから捨てよ", "1389", S("1391"), [
    photo("p1", "img_cucumber_rotten.jpg", 500, 150, 920, 357, 0),
    cross("x1", 835, 203, 250, 42),
], [(0, "ピコンッ"), (42, "ドスッ")], "1389「このキュウリはやばいから捨てよ」→「捨てよ」で×。1391 の頭で消す")
