# 白地のキュウリ（img_cucumber_crop.jpg）を「傷んだキュウリ」の絵にする：緑を黄ばんだ緑に寄せ、茶色の傷みのまだらを足す。地（白）と影はそのまま
#   python3 make_cucumber_rotten.py img_cucumber_rotten.jpg（zukai/assets で実行）
import random, sys
from PIL import Image, ImageFilter, ImageChops
src = Image.open('img_cucumber_crop.jpg').convert('RGB')
W, H = src.size
hsv = src.convert('HSV')
Hc, Sc, Vc = hsv.split()
# キュウリの所＝色がある所（影・白地は色が無い）
mask = Sc.point(lambda s: 0 if s < 30 else (255 if s > 60 else int((s - 30) / 30 * 255))).filter(ImageFilter.GaussianBlur(2))
# 色：黄ばんだ緑（色相を黄へ少し・彩度を少し落とす・少し暗く）
Hn = Hc.point(lambda h: max(0, h - 8))
Sn = Sc.point(lambda s: int(s * 0.92))
Vn = Vc.point(lambda v: int(v * 0.9))
yel = Image.merge('HSV', (Hn, Sn, Vn)).convert('RGB')
img = Image.composite(yel, src, mask)
# 茶色の傷み（まだら）：低い解像度の乱数を広げてぼかす（決まった種で毎回同じ）
def noise(gw, gh, seed, blur):
    r = random.Random(seed)
    n = Image.new('L', (gw, gh))
    n.putdata([r.randint(0, 255) for _ in range(gw * gh)])
    return n.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
n1 = noise(16, 6, 7, 26)
n2 = noise(60, 24, 11, 7)
blot = n1.point(lambda v: 0 if v < 150 else min(175, int((v - 150) * 3)))
spots = n2.point(lambda v: 0 if v < 192 else min(165, int((v - 192) * 5)))
brown = Image.new('RGB', (W, H), (112, 76, 36))
dark = Image.new('RGB', (W, H), (74, 50, 24))
img = Image.composite(brown, img, ImageChops.multiply(blot, mask))
img = Image.composite(dark, img, ImageChops.multiply(spots, mask))
img.save(sys.argv[1], quality=92)
print(img.size)
