"""Шаг 1: геометрия наушников целиком кодом. Ни одной текстуры, только форма.

    blender -b --python build.py -- headphones.blend

Ничего не импортирует из `lib/`: шаг 1 к библиотеке не привязан — это просто
`bpy`. Камеру, свет и материалы не трогает, их выбирает пользователь дальше.

Имена объектов важны: по ним `sets.py` раскладывает материалы, а `shot.py`
целится светом. Переименуете объект — поправьте и там.
"""
import math
import os
import sys
from os.path import abspath, dirname, join

import bmesh
import bpy
from mathutils import Vector

# --- параметры, которые имеет смысл крутить ---------------------------------
BAND_R = 1.05                # радиус дуги оголовья
PLATE_T = 0.016              # толщина металлической пластины
PLATE_HW = (0.106, 0.072)    # полуширина пластины: середина → концы
PLATE_ARC = (-7.0, 187.0)    # градусы дуги

# Кожа — именно оболочка: в сечении обхватывает пластину со всех сторон, поэтому
# толще и шире её. Металл выходит наружу только у концов дуги. Если сделать кожу
# накладкой поверх, при камере снизу видно изнанку — металл там, где ждёшь кожу.
LEATHER_T = 0.058
LEATHER_HW = (0.130, 0.094)
LEATHER_ARC = (14.0, 166.0)

CUP_X, CUP_R, CUP_D = 1.02, 0.48, 0.30      # чашка: центр по X, радиус, глубина
CUP_Z = -0.62                               # чашки сидят НЕ на нуле — см. lathe()
DISC_X, DISC_R, DISC_T = 1.19, 0.42, 0.045  # накладка-диск

LOGO_TIP = 0.215        # радиус лучей звезды
LOGO_RING = 0.248       # внешний радиус кольца
LOGO_H = 0.0085         # высота выдавливания
LOGO_INNER = 0.155      # где сходятся основания лучей: меньше — острее

OBJECTS = ("BandPlate", "BandLeather", "ArmL", "ArmR", "CupL", "CupR",
           "DiscL", "DiscR", "PadL", "PadR", "LogoL", "LogoR")


# --- утилиты ----------------------------------------------------------------
def _new(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return ob


def _smooth(ob, angle=35.0):
    for p in ob.data.polygons:
        p.use_smooth = True
    bpy.context.view_layer.objects.active = ob
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
    except Exception:
        pass          # в фоне оператор иногда без контекста — сглаживание по граням уже стоит


def _bevel(ob, width, segments=3, angle=30.0):
    b = ob.modifiers.new("Bevel", "BEVEL")
    b.width, b.segments, b.limit_method = width, segments, "ANGLE"
    b.angle_limit = math.radians(angle)
    return b


def _kill(*names):
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob:
            data = ob.data
            bpy.data.objects.remove(ob)
            if isinstance(data, bpy.types.Mesh) and data.users == 0:
                bpy.data.meshes.remove(data)


def _chaikin(pts, iterations=2):
    """Сглаживание замкнутой ломаной. Скругляет углы профиля — это «мягкая кожа»."""
    for _ in range(iterations):
        out = []
        n = len(pts)
        for i in range(n):
            a, b = Vector(pts[i]), Vector(pts[(i + 1) % n])
            out.append(tuple(a * 0.75 + b * 0.25))
            out.append(tuple(a * 0.25 + b * 0.75))
        pts = out
    return pts


# --- построители ------------------------------------------------------------
def sweep_rect_arc(name, a0, a1, radius, thick, hw, segments=128):
    """Дуга в плоскости XZ с прямоугольным сечением, сужающимся к концам."""
    verts, faces = [], []
    for i in range(segments + 1):
        t = i / segments
        ang = math.radians(a0 + (a1 - a0) * t)
        u = Vector((math.cos(ang), 0.0, math.sin(ang)))
        c = u * radius
        k = 1.0 - (2.0 * t - 1.0) ** 2            # парабола: середина шире концов
        w = hw[1] + (hw[0] - hw[1]) * k
        y = Vector((0.0, 1.0, 0.0))
        verts += [tuple(c - u * (thick / 2) - y * w),
                  tuple(c - u * (thick / 2) + y * w),
                  tuple(c + u * (thick / 2) + y * w),
                  tuple(c + u * (thick / 2) - y * w)]
    for i in range(segments):
        for j in range(4):
            a, b = 4 * i + j, 4 * i + (j + 1) % 4
            faces.append((a, b, b + 4, a + 4))
    faces.append((3, 2, 1, 0))
    n = 4 * segments
    faces.append((n, n + 1, n + 2, n + 3))
    return _new(name, verts, faces)


def lathe(name, profile, axis_x, direction, center=(0.0, 0.0), segments=192,
          folds=0, fold_amp=0.0, fold_phase=0.0):
    """Точение замкнутого профиля вокруг оси X. profile = [(глубина, радиус), ...].

    `center` = (y, z) — где проходит ось. Это не формальность: чашки сидят на
    z = −0.62, и точение вокруг оси через ноль вешает амбушюр выше чашки.

    folds/fold_amp дают радиальные складки — то, чем мягкая кожа отличается
    от гладкого бублика. Амплитуда гаснет у грани чашки, где кожа притянута.
    """
    verts, faces = [], []
    m = len(profile)
    y0, z0 = center
    dmax = max(d for d, _ in profile) or 1.0
    for k in range(segments):
        phi = 2 * math.pi * k / segments
        cy, sz = math.cos(phi), math.sin(phi)
        # две гармоники, иначе складки выглядят штампованной гофрой
        ripple = (0.72 * math.sin(folds * phi + fold_phase)
                  + 0.28 * math.sin(2 * folds * phi + 1.7 * fold_phase)) if folds else 0.0
        for d, r in profile:
            w = math.sin(math.pi * min(d / dmax, 1.0))     # 0 у чашки, максимум в середине
            verts.append((axis_x + direction * d,
                          y0 + r * (1.0 + fold_amp * w * ripple) * cy,
                          z0 + r * (1.0 + fold_amp * w * ripple) * sz))
    for k in range(segments):
        k2 = (k + 1) % segments
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((k * m + j, k * m + j2, k2 * m + j2, k2 * m + j))
    return _new(name, verts, faces)


def emblem(name, face_x, direction, z):
    """Трёхлучевая звезда в кольце, выдавленная из плоскости диска."""
    verts, faces = [], []
    h = LOGO_H * direction
    base_x, top_x = face_x - 0.0008 * direction, face_x + h

    star = []
    for i in range(6):
        a = math.radians(60 * i)               # 0° = вверх
        r = LOGO_TIP if i % 2 == 0 else LOGO_TIP * LOGO_INNER
        star.append((r * math.sin(a), z + r * math.cos(a)))
    verts += [(base_x, y, zz) for y, zz in star]
    verts += [(top_x, y, zz) for y, zz in star]
    c_base, c_top = len(verts), len(verts) + 1
    verts += [(base_x, 0.0, z), (top_x, 0.0, z)]
    for i in range(6):
        j = (i + 1) % 6
        faces.append((c_base, j, i))                 # донце, внутри диска
        faces.append((c_top, 6 + i, 6 + j))          # лицевая грань
        faces.append((i, j, 6 + j, 6 + i))           # боковина
    off = len(verts)

    seg = 96
    for k in range(seg):
        a = 2 * math.pi * k / seg
        cy, sz = math.sin(a), math.cos(a)
        for x in (base_x, top_x):
            verts.append((x, LOGO_TIP * cy, z + LOGO_TIP * sz))
            verts.append((x, LOGO_RING * cy, z + LOGO_RING * sz))
    for k in range(seg):
        k2 = (k + 1) % seg
        a, b = off + 4 * k, off + 4 * k2
        faces.append((a + 2, a + 3, b + 3, b + 2))   # лицевая
        faces.append((a + 1, a + 0, b + 0, b + 1))   # донце
        faces.append((a + 0, a + 2, b + 2, b + 0))   # внутренняя стенка
        faces.append((a + 3, a + 1, b + 1, b + 3))   # внешняя стенка
    return _new(name, verts, faces)


def cylinder_x(name, radius, depth, x, z, vertices=96):
    """Цилиндр вдоль оси X — чашка или диск-накладка."""
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, vertices=vertices,
                                        location=(x, 0.0, z),
                                        rotation=(0.0, math.radians(90), 0.0))
    ob = bpy.context.object
    ob.name = name
    return ob


# ============================================================================
def build():
    _kill(*OBJECTS)

    # --- оголовье: металлическая пластина, поверх кожаный ремень ------------
    plate = sweep_rect_arc("BandPlate", *PLATE_ARC, BAND_R, PLATE_T, PLATE_HW)
    _bevel(plate, 0.0035, segments=2)
    _smooth(plate, 40)

    leather = sweep_rect_arc("BandLeather", *LEATHER_ARC, BAND_R,
                             LEATHER_T, LEATHER_HW)
    _bevel(leather, 0.016, segments=4)
    _smooth(leather, 45)

    # --- дужки: плоские полосы, продолжение пластины ------------------------
    for side, sign in (("L", -1), ("R", 1)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(sign * BAND_R, 0, -0.325))
        arm = bpy.context.object
        arm.name = f"Arm{side}"
        arm.scale = (PLATE_T, PLATE_HW[1] * 2 * 0.92, 0.58)
        bpy.ops.object.transform_apply(scale=True)
        _bevel(arm, 0.006)
        _smooth(arm, 35)

    # --- чашки и диски-накладки ---------------------------------------------
    for side, sign in (("L", -1), ("R", 1)):
        cup = cylinder_x(f"Cup{side}", CUP_R, CUP_D, sign * CUP_X, CUP_Z)
        _bevel(cup, 0.03, segments=4)
        _smooth(cup, 40)
        disc = cylinder_x(f"Disc{side}", DISC_R, DISC_T, sign * DISC_X, CUP_Z)
        _bevel(disc, 0.008, segments=3)
        _smooth(disc, 35)

    # --- амбушюры: точёный профиль ------------------------------------------
    # (глубина внутрь от грани чашки, радиус). Тонкая мягкая кожа: невысокий
    # валик, широкое ушное отверстие, подвёрнутый край. Максимальный радиус
    # держим под радиусом чашки, иначе кожа торчит оборкой.
    prof = _chaikin([
        (0.000, 0.462), (0.038, 0.472), (0.092, 0.464), (0.132, 0.432),
        (0.158, 0.390), (0.170, 0.348), (0.158, 0.320), (0.108, 0.309),
        (0.044, 0.306), (0.000, 0.314),
    ], iterations=2)

    noise = bpy.data.textures.get("PadNoise") or bpy.data.textures.new("PadNoise", "CLOUDS")
    noise.noise_scale, noise.noise_depth = 0.055, 4

    for side, sign in (("L", -1), ("R", 1)):
        face = sign * (CUP_X - CUP_D / 2)                # внутренняя грань чашки
        pad = lathe(f"Pad{side}", prof, face, -sign, center=(0.0, CUP_Z),
                    folds=19, fold_amp=0.011, fold_phase=0.7 * sign)
        d = pad.modifiers.new("Soft", "DISPLACE")
        d.texture, d.strength, d.mid_level = noise, 0.0065, 0.5
        d.texture_coords = "LOCAL"
        _smooth(pad, 50)

    # --- эмблема на дисках ---------------------------------------------------
    for side, sign in (("L", -1), ("R", 1)):
        logo = emblem(f"Logo{side}", sign * (DISC_X + DISC_T / 2), sign, CUP_Z)
        _bevel(logo, 0.0012, segments=2)
        _smooth(logo, 25)

    return {o.name: len(o.data.polygons)
            for o in bpy.context.scene.objects if o.type == "MESH"}


def logo_world(side=1):
    """Центр эмблемы в мире — точка фокуса и цель для отражателя в `shot.py`."""
    return (side * (DISC_X + DISC_T / 2 + LOGO_H), 0.0, CUP_Z)


if __name__ == "__main__":
    # При самостоятельном запуске сцену чистим: `blender -b` грузит стартовую,
    # с кубом и лампой. Внутри make.py это уже сделано раньше.
    sys.path.insert(0, join(dirname(dirname(dirname(abspath(__file__)))), "lib"))
    import scene
    scene.reset()
    counts = build()
    print("BUILD", counts, "polys:", sum(counts.values()))
    print("BUILD logo_world", logo_world())
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv:
        path = os.path.abspath(argv[0])
        bpy.ops.wm.save_as_mainfile(filepath=path)
        print("BUILD saved", path)
