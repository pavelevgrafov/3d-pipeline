"""Шаг 2: ракурс. Снять камеру с вьюпорта, поставить по углам, собрать лист ракурсов.

Три способа выбрать кадр, все три рабочие:

* `snap_to_viewport()` — вы крутите объект мышью в открытом Blender, я забираю
  ровно это положение. Требует живого Blender (GUI или MCP-соединение).
* `look_from(azimuth, elevation, distance)` — сферические координаты числами.
  Работает в фоне.
* `contact_sheet()` — лист из N ракурсов одной картинкой, вы называете номер.

Импортируется внутри Blender:
    import sys; sys.path.append(".../lib"); import camera
"""
import math
import os

import bpy
from mathutils import Vector

import mosaic

# Вьюпорт Blender считает орто-охват как перспективу с сенсором 72 мм на
# расстоянии view_distance. Число зашито в Blender, не подбиралось.
_VIEWPORT_SENSOR = 72.0


def ensure_camera(name="Cam", lens=60.0, target=(0, 0, 0)):
    """Камера + пустышка-таргет с Track To. Двигаем только позицию — наведение само."""
    tgt = bpy.data.objects.get("CamTarget")
    if tgt is None:
        tgt = bpy.data.objects.new("CamTarget", None)
        bpy.context.collection.objects.link(tgt)
    tgt.location = target

    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        bpy.context.collection.objects.link(cam)
    cam.data.lens = lens
    # Цель переустанавливается КАЖДЫЙ раз, а не только при создании констрейнта.
    # Проект вправе удалить "CamTarget" между шагами (в заготовке он в JUNK):
    # тогда у существующего констрейнта target становится None, Track To молча
    # перестаёт работать, и камера остаётся с нулевым поворотом — смотрит
    # вертикально вниз. Ошибка не падает: получается аккуратный кадр сверху
    # вместо утверждённого ракурса.
    trk = next((c for c in cam.constraints if c.type == "TRACK_TO"), None)
    if trk is None:
        trk = cam.constraints.new("TRACK_TO")
        trk.track_axis, trk.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    trk.target = tgt
    bpy.context.scene.camera = cam
    return cam, tgt


def look_from(azimuth, elevation, distance, target=(0, 0, 0), lens=60.0):
    """Сферические координаты вокруг таргета. Азимут и возвышение — в градусах.

    azimuth 0 = вид спереди (-Y), растёт против часовой стрелки, если смотреть сверху.
    """
    cam, _ = ensure_camera(lens=lens, target=target)
    a, e = math.radians(azimuth), math.radians(elevation)
    cam.location = Vector(target) + Vector((
        distance * math.cos(e) * math.sin(a),
        -distance * math.cos(e) * math.cos(a),
        distance * math.sin(e),
    ))
    bpy.context.view_layer.update()
    return cam


def preview_engine():
    """Имя движка для быстрых превью. EEVEE переименовывали между версиями.

    В Blender 4.2–4.5 он назывался `BLENDER_EEVEE_NEXT`, в 5.x снова
    `BLENDER_EEVEE`. Зашитое имя падает с «enum not found» на половине версий,
    поэтому спрашиваем у самого Blender, что у него есть.
    """
    items = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    for name in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        if name in items:
            return name
    return "CYCLES"


def read_viewport():
    """Куда сейчас смотрит пользователь в окне Blender. В фоне возвращает None.

    Проверка на `bpy.app.background` тут обязательна, и это не перестраховка:
    при запуске `blender -b` окно всё равно существует в данных, у него есть
    область VIEW_3D со СТАРТОВЫМ ракурсом. Без этой проверки «снять камеру
    с вьюпорта» в фоне молча отдаёт ракурс сцены по умолчанию — то есть кадр,
    который никто не выбирал, и ошибку видно только на финальном рендере.
    """
    if bpy.app.background:
        return None
    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return None
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        r3d = area.spaces[0].region_3d
        eye = r3d.view_rotation @ Vector((0, 0, r3d.view_distance)) + r3d.view_location
        return {
            "eye": tuple(eye),
            "target": tuple(r3d.view_location),
            "distance": r3d.view_distance,
            "lens": area.spaces[0].lens,
            "quat": tuple(r3d.view_rotation),
            "ortho": r3d.view_perspective == "ORTHO",
        }
    return None


def snap_to_viewport(keep_lens=False, exact=True):
    """Поставить рендер-камеру ровно туда, куда пользователь докрутил вьюпорт.

    exact=True — воспроизводим ракурс буквально: снимаем Track To (он перебил бы
    поворот), копируем кватернион вьюпорта и переносим орто-режим на камеру.
    Пользователь крутит вьюпорт в орто именно ради отсутствия перспективы,
    поэтому перспективную камеру по умолчанию не навязываем.

    Возвращает словарь чисел — их надо записать в `approved.py`: сцена на диске
    может быть сохранена ДО утверждения, а числа воспроизводят кадр всегда.
    """
    v = read_viewport()
    if v is None:
        raise RuntimeError("Нет живого 3D-вьюпорта (Blender в фоне или окно без 3D-области). "
                           "Ракурс задавайте через look_from() / contact_sheet(), "
                           "а утверждённый — через restore() из записанных чисел.")
    cam, _ = ensure_camera(target=v["target"])
    if exact:
        for c in list(cam.constraints):
            cam.constraints.remove(c)
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = v["quat"]
        cam.data.type = "ORTHO" if v["ortho"] else "PERSP"
        if v["ortho"]:
            cam.data.ortho_scale = v["distance"] * _VIEWPORT_SENSOR / v["lens"]
    cam.location = v["eye"]
    if keep_lens:
        cam.data.lens = v["lens"]
    bpy.context.view_layer.update()
    return v


def restore(quat=None, eye=None, ortho=False, view_distance=None, view_lens=50.0,
            lens=None, ortho_scale=None, name="Cam"):
    """Обратная операция к snap_to_viewport: собрать камеру из записанных чисел.

    Живой Blender не нужен — это и есть смысл записывать числа в `approved.py`.
    `view_distance`/`view_lens` — то, что вернул snap_to_viewport; из них
    считается ortho_scale ровно так же, как это делает вьюпорт.
    """
    from mathutils import Quaternion
    cam, _ = ensure_camera(name=name)
    for c in list(cam.constraints):
        cam.constraints.remove(c)
    if quat is not None:
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = Quaternion(quat)
    if eye is not None:
        cam.location = Vector(eye)
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        if ortho_scale is None:
            if view_distance is None:
                raise ValueError("для орто нужен ortho_scale или view_distance")
            ortho_scale = view_distance * _VIEWPORT_SENSOR / view_lens
        cam.data.ortho_scale = ortho_scale
    elif lens is not None:
        cam.data.lens = lens
    bpy.context.view_layer.update()
    return cam


def _render_to(path, res=384, samples=32, engine=None):
    engine = engine or preview_engine()
    sc = bpy.context.scene
    prev = (sc.render.engine, sc.render.resolution_x, sc.render.resolution_y,
            sc.render.filepath, sc.render.image_settings.file_format)
    sc.render.engine = engine
    sc.render.resolution_x = sc.render.resolution_y = res
    if engine == "CYCLES":
        sc.cycles.samples = samples
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    (sc.render.engine, sc.render.resolution_x, sc.render.resolution_y,
     sc.render.filepath, sc.render.image_settings.file_format) = prev


def contact_sheet(out_path, angles=None, elevation=8.0, distance=6.0,
                  target=(0, 0, 0), lens=60.0, res=384, cols=4,
                  engine=None, samples=32):
    """Лист ракурсов одним изображением — чтобы выбрать номер, а не описывать словами.

    Возвращает [(номер, азимут)]. Номера идут слева направо, сверху вниз;
    подписи в кадр не наносятся, порядок и есть нумерация.
    """
    if angles is None:
        angles = list(range(0, 360, 30))
    tmp = os.path.join(os.path.dirname(out_path) or ".", "_sheet_tmp")
    os.makedirs(tmp, exist_ok=True)

    tiles, paths = [], []
    try:
        for i, az in enumerate(angles):
            look_from(az, elevation, distance, target, lens)
            p = os.path.join(tmp, f"{i:02d}.png")
            _render_to(p, res=res, samples=samples, engine=engine)
            paths.append(p)
            tiles.append(mosaic.load(p))
        mosaic.save(mosaic.tile(tiles, cols=cols), out_path)
    finally:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        if os.path.isdir(tmp):
            os.rmdir(tmp)
    return [(i + 1, az) for i, az in enumerate(angles)]
