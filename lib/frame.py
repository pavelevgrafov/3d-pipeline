"""Кадрирование из измеренных габаритов, а не подбором на глаз.

Главный приём всего пайплайна: сначала померить объект в системе координат
камеры, потом посчитать охват и сдвиг кадра из этих чисел. «Объект занимает
86% высоты кадра» — это `fill=0.86`, а не двадцать перерендеров с подбором
дистанции.

Система координат камеры: x — вправо по кадру, y — вверх, камера смотрит
вдоль −z. Отсюда же ставится свет (`lighting.py`), поэтому «источник справа
от кадра» означает буквально положительный x при любом ракурсе.
"""
import math

import bpy
from mathutils import Vector

# Служебные объекты, которые не должны влиять на кадрирование. Фон в кадр
# попадает, поэтому по признаку видимости не отсеивается — только по имени.
SERVICE = {"Backdrop", "SheetLabel", "CamTarget", "FocusPoint"}


def subjects(exclude=()):
    """Меши, которые считаются объектом съёмки.

    Источники света в этом пайплайне — тоже меши (светящиеся плоскости), и они
    заведомо больше объекта и стоят вокруг него. Отсеиваем их по `visible_camera`:
    то, чего камера не видит, не может быть частью кадрируемого объекта. Признак
    надёжнее списка имён — он работает и для источников, которые вы завели сами.

    Без этого фильтра габариты раздувались втрое, и всё, что считается от них —
    охват кадра, сдвиг, диапазон Mist — уезжало вместе с ними.
    """
    skip = SERVICE | set(exclude)
    return [ob for ob in bpy.context.scene.objects
            if ob.type == "MESH" and ob.name not in skip
            and not ob.hide_render and ob.visible_camera]


def extent(exclude=()):
    """Габариты объекта в системе координат камеры: (x0,x1), (y0,y1), (z0,z1).

    z отрицательный и растёт по модулю вглубь: z1 — ближняя точка, z0 — дальняя.
    Из этого же диапазона потом считается Mist в `render.py`.
    """
    cam = bpy.context.scene.camera
    if cam is None:
        raise RuntimeError("В сцене нет активной камеры")
    obs = subjects(exclude)
    if not obs:
        raise RuntimeError("В сцене нет ни одного видимого меша — нечего кадрировать")
    inv = cam.matrix_world.inverted()
    xs, ys, zs = [], [], []
    for ob in obs:
        for c in ob.bound_box:
            v = inv @ (ob.matrix_world @ Vector(c))
            xs.append(v.x)
            ys.append(v.y)
            zs.append(v.z)
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def center(exclude=()):
    """Центр габаритов в мировых координатах — куда наводить свет и фокус."""
    cam = bpy.context.scene.camera
    (x0, x1), (y0, y1), (z0, z1) = extent(exclude)
    return cam.matrix_world @ Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def _needed_scale(res, spans, fill, by):
    """Охват по БОЛЬШЕЙ стороне кадра, при котором объект в него влезает.

    Blender меряет и `ortho_scale`, и `shift_x/shift_y` в единицах большей
    стороны кадра, поэтому и здесь всё считается в них. Охват вдоль оси i равен
    `scale · res_i / max(res)`, отсюда требование `span_i ≤ fill · охват_i`.

    Без пересчёта на пропорции кадра «вписать по ширине» врёт всегда, когда кадр
    не квадратный, а «вписать по высоте» молча срезает широкий объект по бокам —
    на вертикальном кадре это и происходит.
    """
    long_side = max(res)
    need = {"width": spans[0] * long_side / (fill * res[0]),
            "height": spans[1] * long_side / (fill * res[1])}
    if by == "max":
        return max(need.values())
    if by not in need:
        raise ValueError(f'by должно быть "width", "height" или "max", а не {by!r}')
    return need[by]


def fit(res=(1080, 1080), fill=0.86, offset=(0.0, 0.0), ortho_scale=None,
        exclude=(), by="max"):
    """Подогнать кадр под объект. Работает и в орто, и в перспективе.

    * `fill` — какую долю кадра занимает объект (0.86 = плотно, 0.6 = с воздухом).
    * `offset` — увод от центра в долях охвата: объект не обязан стоять по оси.
    * `by` — по какой стороне вписывать: "max" (объект влезает целиком, по
      умолчанию), "height" или "width" (вторая сторона может уйти за кадр —
      это осмысленно, когда обрез задуман).

    В ОРТО меняется `ortho_scale` — камера остаётся на месте, ракурс не портится.
    В ПЕРСПЕКТИВЕ камера отъезжает вдоль своей оси взгляда: угол зрения фиксирован
    объективом, менять там нечего, кроме дистанции. Направление взгляда при этом
    не меняется, то есть утверждённый ракурс сохраняется.

    Возвращает фактический охват кадра в единицах сцены.
    """
    sc = bpy.context.scene
    cam = sc.camera
    sc.render.resolution_x, sc.render.resolution_y = res

    (x0, x1), (y0, y1), (z0, z1) = extent(exclude)
    size = _needed_scale(res, (x1 - x0, y1 - y0), fill, by) * fill

    if cam.data.type == "ORTHO":
        scale = ortho_scale or size / fill
        cam.data.ortho_scale = scale
    else:
        # Требуемая дистанция до центра объекта, чтобы он занял долю fill кадра.
        # Половина угла зрения по меньшей стороне сенсора: Blender кадрирует
        # по большей стороне разрешения, поэтому берём её же.
        half_fov = math.atan(cam.data.sensor_width / 2 / cam.data.lens)
        need = (size / fill / 2) / math.tan(half_fov)
        view = (cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))).normalized()
        mid = cam.matrix_world @ Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        cam.location = mid - view * need
        bpy.context.view_layer.update()
        # После переезда габариты в системе камеры сдвинулись — меряем заново,
        # иначе сдвиг кадра посчитается по старому положению.
        (x0, x1), (y0, y1), _ = extent(exclude)
        scale = 2 * need * math.tan(half_fov)

    # shift_x/shift_y Blender меряет в долях БОЛЬШЕЙ стороны кадра.
    cam.data.shift_x = (x0 + x1) / 2 / scale + offset[0]
    cam.data.shift_y = (y0 + y1) / 2 / scale + offset[1]
    bpy.context.view_layer.update()
    return scale


def aim_at(point, exclude=(), name="FocusPoint"):
    """Пустышка в заданной точке — цель для глубины резкости и наведения света."""
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(ob)
        ob.empty_display_size = 0.08
    ob.location = Vector(point) if point is not None else center(exclude)
    bpy.context.view_layer.update()
    return ob


def depth_of_field(focus, fstop=4.0, blades=0):
    """Глубина резкости с фокусом на пустышке или объекте.

    Внимание, это стоило перерендеров: в ОРТО радиус апертуры равен
    `lens/(2·fstop)/1000` в единицах сцены и от дистанции НЕ зависит.
    Привычные фотографические f/1.2 дают кашу; рабочий диапазон — 2.5…5.0
    для общего плана и 8…10 для крупного.
    """
    cam = bpy.context.scene.camera
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus
    cam.data.dof.aperture_fstop = fstop
    cam.data.dof.aperture_blades = blades
    return {"fstop": fstop, "ortho": cam.data.type == "ORTHO"}


def report(exclude=()):
    """Числа кадра для протокола — их видно в логе фонового рендера."""
    cam = bpy.context.scene.camera
    (x0, x1), (y0, y1), (z0, z1) = extent(exclude)
    return {
        "type": cam.data.type,
        "ortho_scale": round(cam.data.ortho_scale, 4) if cam.data.type == "ORTHO" else None,
        "lens": round(cam.data.lens, 2) if cam.data.type == "PERSP" else None,
        "shift": (round(cam.data.shift_x, 4), round(cam.data.shift_y, 4)),
        "extent_x": (round(x0, 3), round(x1, 3)),
        "extent_y": (round(y0, 3), round(y1, 3)),
        "depth_z": (round(z0, 3), round(z1, 3)),
    }
