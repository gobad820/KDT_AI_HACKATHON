"""첫 화면 영상: POS 감열 프린터가 영수증을 출력하고, 다시 출력할 때는 앞 영수증을 구겨 던진다.

실행 (Blender 5.x):
  /Applications/Blender.app/Contents/MacOS/Blender -b -P media/printer/render_hero.py -- <출력 폴더> [옵션]
    --stills 0,40,90      이 프레임만 렌더 (확인용)
    --samples 64          Cycles 샘플 수
    --res 1080x1200       해상도
    --fps 30
입력: media/printer/receipt.png, receipt.json  (receipt_texture.js 로 hero.json 숫자를 감열 인쇄한 텍스처)
출력: <출력 폴더>/f_0000.png ... 와 timeline.json (hero.js 가 멈출 시점·던지기 시작 시점)

hero.json 이 바뀌었을 때 다시 만드는 순서:
  1. uvicorn 으로 로컬 서버를 띄우고 첫 화면을 연다(Pretendard 글꼴과 hero.json 이 필요하다).
  2. 브라우저 콘솔에 receipt_texture.js 내용을 붙여 넣고 아래를 실행해 나온 문자열을 파일로 저장한다.
       JSON.stringify(makeReceiptTexture(await (await fetch('hero.json')).json(), { stamp: '2026-11-21 14:00', seq: 1, scale: 2 }))
  3. python3 media/printer/save_texture.py <저장한 파일>      → receipt.png, receipt.json
  4. Blender -b -P media/printer/render_hero.py -- media/printer/frames   (M2 Pro GPU 기준 약 35분)
  5. sh media/printer/make_video.sh                           → app/web/img/hero_print.mp4, _poster.webp, .json

치수는 실제 80mm POS 프린터 비율(가로 14cm, 깊이 17cm, 높이 10cm)을 1 = 10cm 로 줄였다.
종이 모양: 출구에서 뒤로 조금 기울어 나오고, 길어질수록 무게 때문에 뒤로 더 휜다(곡률이 남은 길이에 비례).
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector, noise

HERE = Path(__file__).resolve().parent
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["."]
OUT = Path(argv[0]).resolve()
OUT.mkdir(parents=True, exist_ok=True)


def opt(name, default):
    return argv[argv.index(name) + 1] if name in argv else default


STILLS = [int(x) for x in opt("--stills", "").split(",") if x != ""]
SAMPLES = int(opt("--samples", "64"))
RES = tuple(int(x) for x in opt("--res", "1080x1200").split("x"))
FPS = int(opt("--fps", "60"))

# ---------- 초기화 ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

W, D, H = 1.40, 1.70, 1.00          # 가로(x), 깊이(y, 앞이 -y), 높이(z)
Z0 = 0.03                           # 고무 발 높이
ZT = Z0 + H                         # 윗면 높이
SLOT_Y = -D / 2 + 0.30              # 종이 출구: 윗면 앞쪽
SLOT_W = 0.88                       # 80mm 용지보다 조금 넓게
PW = 0.80                           # 용지 폭 80mm


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mat(name, color, rough=0.5, spec=0.5, metal=0.0, emit=None, strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.25
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


M_BODY = mat("body", srgb("#18191c"), rough=0.42, spec=0.5)
M_COVER = mat("cover", srgb("#1d1e22"), rough=0.45, spec=0.45, coat=0.15)
M_DARK = mat("slot", srgb("#050506"), rough=0.9, spec=0.1)
M_BTN = mat("button", srgb("#3a3d43"), rough=0.4, spec=0.5)
M_LED = mat("led", srgb("#4fd187"), rough=0.2, emit=srgb("#4fd187"), strength=10)
M_BAR = mat("tear_bar", srgb("#55585e"), rough=0.32, metal=1.0)
M_STUDIO = mat("studio", srgb("#c4c5c9"), rough=0.92, spec=0.2)


def box(name, size, loc, bevel=0.0, seg=6, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bv = o.modifiers.new("bevel", "BEVEL")
        bv.width = bevel
        bv.segments = seg
        bv.limit_method = "NONE"
    if material:
        o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o


def cut(target, cutter):
    m = target.modifiers.new("cut_" + cutter.name, "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    cutter.hide_render = True
    cutter.display_type = "WIRE"


# ---------- 프린터 ----------
body = box("body", (W, D, H), (0, 0, Z0 + H / 2), bevel=0.16, seg=8, material=M_BODY)
plate_d = D / 2 - SLOT_Y - 0.12
box("plate", (W - 0.16, plate_d, 0.06), (0, D / 2 - 0.06 - plate_d / 2, ZT - 0.02), bevel=0.03, seg=4, material=M_COVER)
slot = box("slot_cut", (SLOT_W, 0.04, 0.5), (0, SLOT_Y, ZT), material=M_DARK)
cut(body, slot)
box("slot_inner", (SLOT_W, 0.04, 0.02), (0, SLOT_Y, ZT - 0.2), material=M_DARK)
box("tear_bar", (SLOT_W + 0.04, 0.018, 0.012), (0, SLOT_Y - 0.032, ZT + 0.004), bevel=0.004, seg=2, material=M_BAR)
bpy.ops.mesh.primitive_cylinder_add(radius=0.026, depth=0.03, location=(W * 0.34, -D / 2 - 0.004, Z0 + H * 0.70), rotation=(math.pi / 2, 0, 0))
bpy.context.active_object.data.materials.append(M_LED)
box("button", (0.18, 0.03, 0.065), (W * 0.18, -D / 2 - 0.004, Z0 + H * 0.70), bevel=0.028, material=M_BTN)
for sx in (-1, 1):
    for sy in (-1, 1):
        box("foot", (0.16, 0.16, Z0), (sx * (W / 2 - 0.18), sy * (D / 2 - 0.2), Z0 / 2), bevel=0.01, material=M_DARK)

# ---------- 스튜디오 배경: 바닥에서 벽으로 이어지는 곡면(사이클로라마) ----------
prof = [(-14.0, 0.0), (1.4, 0.0)]
R_CYC, CY, CZ = 3.0, 1.4, 3.0
for i in range(1, 17):
    a = -math.pi / 2 + (math.pi / 2) * i / 16
    prof.append((CY + R_CYC * math.cos(a), CZ + R_CYC * math.sin(a)))
prof.append((CY + R_CYC, 14.0))
verts, faces = [], []
for x in (-16.0, 16.0):
    for (y, z) in prof:
        verts.append((x, y, z))
n = len(prof)
for i in range(n - 1):
    faces.append((i, i + 1, n + i + 1, n + i))
me = bpy.data.meshes.new("studio")
me.from_pydata(verts, [], faces)
studio = bpy.data.objects.new("studio", me)
scene.collection.objects.link(studio)
studio.data.materials.append(M_STUDIO)
for p in studio.data.polygons:
    p.use_smooth = True


# ---------- 조명 ----------
def area(name, loc, target, size, power, color=(1, 1, 1)):
    bpy.ops.object.light_add(type="AREA", location=loc)
    lt = bpy.context.active_object
    lt.name = name
    lt.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    lt.data.size = size
    lt.data.energy = power
    lt.data.color = color
    return lt


area("key", (-3.6, -3.4, 5.4), (0, 0, 1.0), 3.6, 1500)
area("fill", (4.2, -3.2, 2.4), (0, 0, 1.0), 3.0, 420, (0.88, 0.92, 1.0))
area("rim", (1.0, 3.0, 3.8), (0, -0.3, 1.6), 2.2, 700, (1.0, 0.97, 0.92))
area("top", (0, -0.5, 6.5), (0, 0, 0), 4.0, 240)
world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.82, 0.86, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.25

# ---------- 카메라 ----------
# 오른쪽 앞 14도, 16도 위에서. 종이가 화면 폭의 45% 정도가 되게 당기고, 프린터 아래쪽은 잘라 낸다
CAM_T = Vector((0.0, 0.0, 1.30))
CAM_D, CAM_EL, CAM_AZ = 5.9, math.radians(16), math.radians(14)
bpy.ops.object.camera_add(location=CAM_T + CAM_D * Vector((math.cos(CAM_EL) * math.sin(CAM_AZ), -math.cos(CAM_EL) * math.cos(CAM_AZ), math.sin(CAM_EL))))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (CAM_T - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 96

# ---------- 종이 재질: 감열지(한쪽 면만 인쇄, 은은한 광택, 얇아서 뒤에서 빛이 비침) ----------
meta = json.loads((HERE / "receipt.json").read_text())
LR = PW * meta["H"] / meta["W"]                    # 영수증 길이
M_PAPER = bpy.data.materials.new("thermal_paper")
M_PAPER.use_nodes = True
nt = M_PAPER.node_tree
for nd in list(nt.nodes):
    nt.nodes.remove(nd)
N = nt.nodes.new
out = N("ShaderNodeOutputMaterial")
tex = N("ShaderNodeTexImage")
tex.image = bpy.data.images.load(str(HERE / "receipt.png"))
tex.extension = "EXTEND"
tex.interpolation = "Linear"
uvn = N("ShaderNodeUVMap")
geo = N("ShaderNodeNewGeometry")
mix = N("ShaderNodeMix")
mix.data_type = "RGBA"
mix.inputs[7].default_value = (*srgb("#f4f4f1"), 1)       # 뒷면: 인쇄 없는 종이
bsdf = N("ShaderNodeBsdfPrincipled")
bsdf.inputs["Roughness"].default_value = 0.4
bsdf.inputs["Specular IOR Level"].default_value = 0.45
bsdf.inputs["Coat Weight"].default_value = 0.12
bsdf.inputs["Coat Roughness"].default_value = 0.3
trans = N("ShaderNodeBsdfTranslucent")
mixs = N("ShaderNodeMixShader")
mixs.inputs[0].default_value = 0.16
nz = N("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 260.0
nz.inputs["Detail"].default_value = 6.0
bump = N("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.05
bump.inputs["Distance"].default_value = 0.002
L = nt.links.new
L(uvn.outputs["UV"], tex.inputs["Vector"])
L(geo.outputs["Backfacing"], mix.inputs[0])
L(tex.outputs["Color"], mix.inputs[6])
L(mix.outputs[2], bsdf.inputs["Base Color"])
L(mix.outputs[2], trans.inputs["Color"])
L(nz.outputs["Fac"], bump.inputs["Height"])
L(bump.outputs["Normal"], bsdf.inputs["Normal"])
L(bump.outputs["Normal"], trans.inputs["Normal"])
L(bsdf.outputs[0], mixs.inputs[1])
L(trans.outputs[0], mixs.inputs[2])
L(mixs.outputs[0], out.inputs["Surface"])

paper_me = bpy.data.meshes.new("paper")
paper = bpy.data.objects.new("paper", paper_me)
scene.collection.objects.link(paper)
paper_me.materials.append(M_PAPER)

# ---------- 타임라인(초) ----------
UNIT = PW / meta["W"]                               # 점 하나의 길이
steps = []                                          # (길이, 걸리는 시간)
prev = 0
for i, (y, h) in enumerate(meta["rows"]):
    end = y + h
    dur = 0.20 if i == 0 else (0.17 if h > 60 else 0.10)
    steps.append(((end - prev) * UNIT, dur))
    prev = end
steps.append(((meta["H"] - prev) * UNIT + 0.004, 0.16))
T_PRINT0 = 0.35
T_PRINT1 = T_PRINT0 + sum(d for _, d in steps)
T_CUT = T_PRINT1 + 0.14
T_PAUSE = T_CUT + 0.30                               # 웹에서 여기서 멈춘다(정지 구간 안)
T_TOSS = T_CUT + 1.10
TOSS_DUR = 1.30
T_END = T_TOSS + TOSS_DUR + 0.25
E_FINAL = sum(s for s, _ in steps)


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def extruded(t):
    """시각 t에 출구 밖으로 나온 길이. 줄마다 70% 시간에 밀고 30% 쉰다(덜컥거림)."""
    if t <= T_PRINT0:
        return 0.0
    e, t0 = 0.0, T_PRINT0
    for s, d in steps:
        if t >= t0 + d:
            e += s
            t0 += d
            continue
        return e + s * smooth(0, 0.7, (t - t0) / d)
    return E_FINAL


TH0, K0, K1 = 0.05, 0.10, 0.22


def strip(E, sway):
    """출구 기준 거리 s(0..E)에 대한 (y, z, 각도) 표. 각도는 수직에서 뒤로 기운 정도."""
    ds, pts, y, z = 0.004, [], SLOT_Y, ZT
    s = 0.0
    while True:
        th = TH0 + K0 * s + K1 * (E * s - s * s / 2) + sway * s
        pts.append((s, y, z, th))
        if s >= E:
            break
        st = min(ds, E - s)
        y += math.sin(th) * st
        z += math.cos(th) * st
        s += st
    return pts


def sample(pts, s):
    if s <= 0:
        return SLOT_Y, ZT + s, 0.0
    lo, hi = 0, len(pts) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pts[mid][0] <= s:
            lo = mid
        else:
            hi = mid
    a, b = pts[lo], pts[hi]
    f = 0.0 if b[0] == a[0] else (s - a[0]) / (b[0] - a[0])
    return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f


NX = 24


def sheet(E, sway, s_min):
    """s_min..E 구간의 종이 격자. 정점, 면, uv."""
    pts = strip(E, sway)
    ns = max(4, int((E - s_min) / 0.01))
    V, UV = [], []
    for j in range(ns + 1):
        s = s_min + (E - s_min) * j / ns
        y, z, th = sample(pts, s)
        d = E - s
        v = 1 - d / LR
        ny, nz_ = -math.cos(th), math.sin(th)               # 앞(카메라 쪽) 법선
        for i in range(NX + 1):
            u = i / NX
            x = (u - 0.5) * PW
            cup = 0.004 * (1 - (2 * u - 1) ** 2)              # 롤에서 풀린 종이의 가로 휨
            V.append(Vector((x, y + ny * cup, z + nz_ * cup)))
            UV.append((u, v))
    F = []
    for j in range(ns):
        for i in range(NX):
            a = j * (NX + 1) + i
            F.append((a, a + 1, a + NX + 2, a + NX + 1))
    return V, F, UV


def set_paper(V, F, UV):
    paper_me.clear_geometry()
    if not F:
        paper.hide_render = True
        return
    paper.hide_render = False
    paper_me.from_pydata([tuple(v) for v in V], [], F)
    uv = paper_me.uv_layers.new(name="UV")
    flat = []
    for poly in paper_me.polygons:
        for li in poly.loop_indices:
            flat.extend(UV[paper_me.loops[li].vertex_index])
    uv.data.foreach_set("uv", flat)
    for poly in paper_me.polygons:
        poly.use_smooth = False
    paper_me.update()


def sway_at(t):
    if t < T_PRINT0:
        return 0.0
    amp = 0.035 * (1 - smooth(T_CUT, T_CUT + 0.9, t))
    return amp * math.sin(2 * math.pi * 1.3 * (t - T_PRINT0))


def crumple(V, UV, tau):
    """뜯어서(들어 올림) → 구기고 → 오른쪽 위로 던져 화면 밖으로."""
    c0 = sum(V, Vector()) / len(V)
    lift = Vector((0.0, -0.06, 0.24)) * smooth(0.0, 0.22, tau)
    k = smooth(0.12, 0.55, tau)
    t2 = max(0.0, (tau - 0.42) / 0.58)
    throw = Vector((3.2 * t2, 0.2 * t2, 0.9 * t2 - 3.4 * t2 * t2))      # 오른쪽 아래로 포물선
    c = c0 + lift + throw
    ang = 6.0 * smooth(0.25, 1.0, tau) ** 1.3
    rot = Matrix.Rotation(ang, 3, Vector((0.35, 1.0, 0.25)).normalized())
    R_BALL = 0.21
    out = []
    for p, (u, v) in zip(V, UV):
        vv = min(1.0, max(0.0, v))
        base = Vector((math.cos(2 * math.pi * u) * math.sin(math.pi * vv), math.sin(2 * math.pi * u) * math.sin(math.pi * vv), math.cos(math.pi * vv)))
        d = (base + 0.9 * noise.noise_vector(Vector((u * 2.3, vv * 2.3, 7.1)))).normalized()
        rad = R_BALL * (0.8 + 0.35 * noise.noise(Vector((u * 5.0, vv * 5.0, 3.3))))
        flat_p = p - c0 + c
        q = flat_p.lerp(c + d * rad, k) + noise.noise_vector(p * 7.0 + Vector((0, 0, 11.0))) * 0.09 * math.sin(math.pi * k)
        out.append(c + rot @ (q - c) if ang > 0 else q)
    return out


def frame_state(t):
    if t < T_CUT:
        E = extruded(t)
        if E < 0.001:
            return [], [], []
        return sheet(E, sway_at(t), -0.25)
    if t < T_TOSS:
        jolt = 0.006 * math.exp(-((t - T_CUT) / 0.05) ** 2) if t >= T_CUT else 0.0   # 커터가 자르는 순간의 떨림
        V, F, UV = sheet(E_FINAL, sway_at(t), E_FINAL - LR)
        return [v + Vector((0, 0, jolt)) for v in V], F, UV
    tau = (t - T_TOSS) / TOSS_DUR
    if tau >= 1.0:
        return [], [], []
    V, F, UV = sheet(E_FINAL, sway_at(T_TOSS), E_FINAL - LR)
    return crumple(V, UV, tau), F, UV


# ---------- 렌더 설정 ----------
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for dv in prefs.devices:
        dv.use = dv.type != "CPU"
    scene.cycles.device = "GPU"
    print("DEVICES", [(dv.name, dv.type, dv.use) for dv in prefs.devices])
except Exception as e:  # GPU가 없으면 CPU로
    print("GPU unavailable:", e)
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPENIMAGEDENOISE"
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"

total = int(round(T_END * FPS))
timeline = {"fps": FPS, "frames": total, "duration": total / FPS, "pauseAt": round(T_PAUSE, 3), "tossAt": round(T_TOSS, 3),
            "printEnd": round(T_CUT, 3), "res": list(RES)}
(OUT / "timeline.json").write_text(json.dumps(timeline, indent=1))
print("TIMELINE", json.dumps(timeline))

frames = STILLS or list(range(total))
for f in frames:
    t = f / FPS
    set_paper(*frame_state(t))
    scene.render.filepath = str(OUT / f"f_{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("FRAME", f, flush=True)
print("RENDER_DONE")
