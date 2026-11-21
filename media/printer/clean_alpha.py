"""렌더(pos_printer.png)를 화면용으로 자르고 바닥 그림자의 투명도를 정리한다.

실행: /Applications/Blender.app/Contents/MacOS/Blender -b -P media/printer/clean_alpha.py -- <입력 png> <출력 png>
- 그림자만 받는 바닥이 화면 전체에 남기는 옅은 알파(약 1~4%)를 걷어 낸다.
- 본체가 아닌 픽셀은 자른 영역의 가장자리에 가까울수록 알파를 0으로 줄인다(사각형 경계가 보이지 않게).
자르는 영역(가로 308~1092, 세로 108~774)은 style.css 의 .pos3d 비율·출구 위치와 맞춰 두었다.
"""
import sys

import bpy
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]
src, dst = args[0], args[1]
X0, Y0, CW, CH = 308, 108, 784, 666
HAZE = 0.045        # 이보다 옅은 알파는 바닥 잡음으로 보고 지운다
MARGIN = 70         # 가장자리에서 이 거리(px) 안쪽으로 그림자를 서서히 지운다

img = bpy.data.images.load(src)
w, h = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]   # 위가 0행
crop = px[Y0:Y0 + CH, X0:X0 + CW].copy()
a = crop[..., 3]
body = a > 0.985

yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
edge = np.minimum.reduce([xx, CW - 1 - xx, yy, CH - 1 - yy])
t = np.clip(edge / MARGIN, 0, 1)
fade = t * t * (3 - 2 * t)

soft = np.clip((a - HAZE) / (1 - HAZE), 0, 1) * fade
crop[..., 3] = np.where(body, a, soft)

out = bpy.data.images.new("clean", CW, CH, alpha=True)
out.pixels[:] = crop[::-1].reshape(-1)
out.filepath_raw = dst
out.file_format = "PNG"
out.save()
print("CLEAN_DONE", dst, "body px", int(body.sum()))
