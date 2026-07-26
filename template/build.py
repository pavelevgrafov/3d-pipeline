"""ШАГ 1 — форма. Здесь вы описываете геометрию, и больше ничего.

Ни материалов, ни света, ни камеры: на этом шаге смотрят на силуэт и пропорции,
и всё остальное только мешает. Материалы придут на шаге 3.

Имена объектов — это интерфейс между файлами. По ним `sets.py` раскладывает
материалы, а `shot.py` целится светом. Переименовали здесь — поправьте и там.

    blender -b --python build.py -- out.blend

Заготовка собирает корпус с полированной лицевой накладкой — типовой продуктовый
предмет. Замените содержимое `build()` на свой объект.
"""
import math
import os
import sys
from os.path import abspath, dirname, join

import bpy

sys.path.insert(0, join(dirname(dirname(abspath(__file__))), "lib"))
import scene  # noqa: E402

# --- параметры формы: то, что вы крутите словами «шире», «глубже» ------------
BODY = (1.6, 1.0, 0.42)      # полугабариты корпуса: ширина, глубина, высота
BEVEL = 0.08                 # скругление рёбер: 0 — рубленый, 0.15 — обмылок
FACE_R = 0.62                # радиус лицевой накладки
FACE_T = 0.04                # её толщина

# Объекты, которые строит этот файл. Список нужен, чтобы пересборка не плодила
# копии: итерация начинается с удаления предыдущей.
OBJECTS = ("Body", "Face", "Ring")


def _kill(*names):
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob:
            data = ob.data
            bpy.data.objects.remove(ob)
            if isinstance(data, bpy.types.Mesh) and data.users == 0:
                bpy.data.meshes.remove(data)


def _bevel(ob, width, segments=4, angle=40.0):
    b = ob.modifiers.new("Bevel", "BEVEL")
    b.width, b.segments, b.limit_method = width, segments, "ANGLE"
    b.angle_limit = math.radians(angle)
    return b


def _smooth(ob, angle=35.0):
    for p in ob.data.polygons:
        p.use_smooth = True
    bpy.context.view_layer.objects.active = ob
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
    except Exception:
        pass


def build():
    """Соберите здесь свой объект. Возвращает {имя: число полигонов}."""
    _kill(*OBJECTS)

    # Корпус.
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    body = bpy.context.object
    body.name = "Body"
    body.scale = BODY
    bpy.ops.object.transform_apply(scale=True)
    _bevel(body, BEVEL, segments=6)
    _smooth(body, 45)

    # Полированная лицевая накладка, смотрящая по −Y. Плоская глянцевая деталь —
    # ровно тот случай, ради которого в `shot.py` стоит отражатель `mirror`.
    bpy.ops.mesh.primitive_cylinder_add(radius=FACE_R, depth=FACE_T, vertices=96,
                                        location=(0, -BODY[1] - FACE_T / 2, 0),
                                        rotation=(math.radians(90), 0, 0))
    face = bpy.context.object
    face.name = "Face"
    _bevel(face, 0.008, segments=3)
    _smooth(face, 30)

    # Ободок вокруг накладки — контрастный слот, чтобы на листе материалов было
    # видно разницу между двумя металлами.
    bpy.ops.mesh.primitive_torus_add(major_radius=FACE_R + 0.05, minor_radius=0.035,
                                     major_segments=96, minor_segments=16,
                                     location=(0, -BODY[1] - FACE_T / 2, 0),
                                     rotation=(math.radians(90), 0, 0))
    ring = bpy.context.object
    ring.name = "Ring"
    _smooth(ring, 30)

    return {o.name: len(o.data.polygons)
            for o in bpy.context.scene.objects if o.type == "MESH"}


def face_world():
    """Ключевая точка объекта: куда наводить фокус и целить свет.

    Здесь это центр лицевой накладки. Возвращайте отсюда то, что в вашем кадре
    обязано быть резким и подсвеченным: шильдик, кнопка, горлышко, циферблат.
    """
    return (0.0, -BODY[1] - FACE_T, 0.0)


def face_normal():
    """Нормаль лицевой плоскости — по ней ставится отражатель `mirror_board`."""
    return (0.0, -1.0, 0.0)


if __name__ == "__main__":
    scene.reset()
    counts = build()
    print("BUILD", counts, "polys:", sum(counts.values()))
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv:
        print("BUILD saved", scene.save(os.path.abspath(argv[0])))
