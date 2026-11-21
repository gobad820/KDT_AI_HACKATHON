"""POS 감열 프린터 3D 모델 → 투명 배경 렌더 + 종이 출구 위치(JSON).

실행: /Applications/Blender.app/Contents/MacOS/Blender -b -P media/printer/build_printer.py -- <출력 폴더>
치수는 실제 80mm POS 프린터 비율(가로 14cm, 깊이 19cm, 높이 12cm)을 1 = 10cm 로 줄였다.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

OUT = Path(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else ".").resolve()
OUT.mkdir(parents=True, exist_ok=True)

# ---------- 초기화 ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

W, D, H = 1.40, 1.70, 1.00          # 가로(x), 깊이(y, 앞이 -y), 높이(z)
SLOT_Y = -D / 2 + 0.30              # 종이 출구: 윗면 앞쪽
SLOT_W = 1.02


def mat(name, color, rough=0.5, spec=0.5, emit=None, strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    for key in ("Specular IOR Level", "Specular"):
        if key in b.inputs:
            b.inputs[key].default_value = spec
            break
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.25
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


M_BODY = mat("body", srgb("#141518"), rough=0.42, spec=0.5)
M_COVER = mat("cover", srgb("#1b1c20"), rough=0.28, spec=0.55, coat=0.6)
M_DARK = mat("slot", srgb("#050506"), rough=0.9, spec=0.1)
M_PANEL = mat("panel", srgb("#17181b"), rough=0.7, spec=0.3)
M_BTN = mat("button", srgb("#3a3d43"), rough=0.4, spec=0.5)
M_LED = mat("led", srgb("#4fd187"), rough=0.2, emit=srgb("#4fd187"), strength=12)


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


# ---------- 본체 ----------
body = box("body", (W, D, H), (0, 0, H / 2), bevel=0.16, seg=8, material=M_BODY)
# 윗면 덮개판: 출구 뒤쪽을 살짝 올린 반광 판
plate_d = D / 2 - SLOT_Y - 0.12
plate = box("plate", (W - 0.16, plate_d, 0.06), (0, D / 2 - 0.06 - plate_d / 2, H + 0.005), bevel=0.03, seg=4, material=M_COVER)
# 종이 출구: 윗면 앞쪽을 가로로 길게 판다
slot = box("slot_cut", (SLOT_W, 0.045, 0.5), (0, SLOT_Y, H), material=M_DARK)
cut(body, slot)
inner = box("slot_inner", (SLOT_W, 0.045, 0.02), (0, SLOT_Y, H - 0.2), material=M_DARK)
# 앞면: 급지 버튼과 LED
bpy.ops.mesh.primitive_cylinder_add(radius=0.026, depth=0.03, location=(W * 0.34, -D / 2 - 0.004, H * 0.70), rotation=(math.pi / 2, 0, 0))
led = bpy.context.active_object
led.data.materials.append(M_LED)
btn = box("button", (0.18, 0.03, 0.065), (W * 0.18, -D / 2 - 0.004, H * 0.70), bevel=0.028, material=M_BTN)
for sx in (-1, 1):
    for sy in (-1, 1):
        box("foot", (0.16, 0.16, 0.03), (sx * (W / 2 - 0.18), sy * (D / 2 - 0.2), 0.015), bevel=0.02, material=M_DARK)
body.location.z += 0.03

# ---------- 바닥: 그림자만 받는 면 ----------
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
ground = bpy.context.active_object
ground.is_shadow_catcher = True

# ---------- 조명 ----------
def area(name, loc, rot, size, power, color=(1, 1, 1)):
    bpy.ops.object.light_add(type="AREA", location=loc, rotation=rot)
    l = bpy.context.active_object
    l.name = name
    l.data.size = size
    l.data.energy = power
    l.data.color = color
    return l


area("key", (-2.6, -3.0, 4.2), (math.radians(48), 0, math.radians(-38)), 2.4, 900)
area("fill", (3.2, -2.4, 1.6), (math.radians(70), 0, math.radians(52)), 3.0, 260, (0.86, 0.9, 1.0))
area("rim", (0.4, 3.4, 3.2), (math.radians(-55), 0, math.radians(175)), 2.0, 700)
area("top", (0, 0, 5.0), (0, 0, 0), 3.0, 260)
world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.64, 0.68, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.12

# ---------- 카메라: 정면에서 조금 위 ----------
bpy.ops.object.camera_add(location=(0, -6.2, 5.0))
cam = bpy.context.active_object
scene.camera = cam
target = Vector((0, -0.1, H * 0.45))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 68

# ---------- 렌더 ----------
scene.render.engine = "CYCLES"
scene.cycles.samples = 160
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = 1400
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"
scene.render.filepath = str(OUT / "pos_printer.png")
bpy.ops.render.render(write_still=True)

# ---------- 종이 출구 위치를 이미지 좌표(0~1, 위가 0)로 ----------
def to_img(p):
    v = world_to_camera_view(scene, cam, Vector(p))
    return {"x": round(v.x, 5), "y": round(1 - v.y, 5)}


z_top = H + 0.03
info = {
    "image": "pos_printer.png", "width": scene.render.resolution_x, "height": scene.render.resolution_y,
    "slotLeft": to_img((-SLOT_W / 2, SLOT_Y, z_top)), "slotRight": to_img((SLOT_W / 2, SLOT_Y, z_top)),
    "slotCenter": to_img((0, SLOT_Y, z_top)), "slotFrontEdge": to_img((0, SLOT_Y - 0.0225, z_top)),
    "bodyLeft": to_img((-W / 2, -D / 2, 0.03)), "bodyRight": to_img((W / 2, -D / 2, 0.03)), "bodyBottom": to_img((0, -D / 2, 0.03)),
}
(OUT / "slot.json").write_text(json.dumps(info, indent=1))
print("PRINTER_DONE", json.dumps(info))
