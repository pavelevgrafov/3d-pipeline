"""ШАГИ 2–4 — ракурс, кадр, свет. Здесь живут все утверждённые числа.

Числа записываются В КОД, а не остаются в `.blend`. Это принципиально: файл
сцены мог быть сохранён до того, как вы сказали «вот так», а числа воспроизводят
кадр всегда — в фоне, на другой машине, через полгода.

Как сюда попадают числа ракурса: вы крутите объект мышью в открытом Blender,
`camera.snap_to_viewport()` возвращает словарь, и его содержимое переносится
в константы ниже. Либо вы называете номер с контрольного листа, и тогда ракурс
задаётся через `camera.look_from(...)`.
"""
import sys
from os.path import abspath, dirname, join

sys.path.insert(0, join(dirname(dirname(abspath(__file__))), "lib"))
sys.path.insert(0, dirname(abspath(__file__)))

import bpy                     # noqa: E402
import camera as cam_lib       # noqa: E402
import frame                   # noqa: E402
import lighting                # noqa: E402
import render                  # noqa: E402

import build                   # noqa: E402
import sets                    # noqa: E402

# --- ШАГ 2: утверждённый ракурс ---------------------------------------------
# Вариант А — числа, снятые с вьюпорта (`camera.snap_to_viewport()`).
# Вариант Б — углы с контрольного листа; тогда USE_VIEWPORT = False.
#
# Числа ниже — не заглушка: это ровно тот ракурс, который даёт вариант Б
# на объекте из `build.py`, снятый с камеры и записанный сюда. Поэтому оба
# пути дают одинаковый кадр, и переключение флага ничего не ломает. Как
# только вы поставите свой объект и докрутите вьюпорт — замените их своими.
USE_VIEWPORT = False
CAM_QUAT = (0.6885, 0.5777, 0.2818, 0.3358)
CAM_EYE = (4.66, -3.64, 1.04)
VIEW_DISTANCE = 6.00
ORTHO = False                 # орто или перспектива — ваш выбор, см. LIMITS.md

AZIMUTH, ELEVATION, DISTANCE, LENS = 52.0, 10.0, 6.0, 85.0

# --- ШАГ 3: утверждённый набор материалов -----------------------------------
MATERIAL_SET = 2

# --- ШАГ 4 и композиция ------------------------------------------------------
RES = (1080, 1080)            # квадрат. Вертикаль 4:5 — (1080, 1350), горизонт — (1600, 900)
FILL = 0.78                   # доля кадра под объект: 0.9 — плотно, 0.6 — с воздухом
FIT_BY = "max"                # "max" — объект влезает целиком; "height"/"width" — с обрезом
OFFSET = (0.0, 0.04)          # увод от центра в долях охвата
FSTOP = 4.0                   # орто: рабочий диапазон 2.5…5.0. Перспектива: как в фото
GAIN = 1.0                    # общая яркость света одним числом

# Мусор с предыдущих шагов: студийный свет сравнения материалов и метка листа.
JUNK = ("KeyStudio", "FillStudio", "RimStudio", "SheetLabel", "CamTarget")


def restore():
    """Камера и материалы из утверждённых чисел. Живой Blender не нужен."""
    for n in JUNK:
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob)
    if USE_VIEWPORT:
        cam = cam_lib.restore(quat=CAM_QUAT, eye=CAM_EYE, ortho=ORTHO,
                              view_distance=VIEW_DISTANCE, view_lens=50.0,
                              lens=LENS)
    else:
        cam = cam_lib.look_from(AZIMUTH, ELEVATION, DISTANCE, lens=LENS)
        cam.data.type = "ORTHO" if ORTHO else "PERSP"
    print("SHOT материалы:", sets.apply(MATERIAL_SET))
    return cam


def apply(samples=256, res=RES, fill=FILL, offset=OFFSET, fstop=FSTOP,
          ortho_scale=None, gain=GAIN, look="AgX - High Contrast", exposure=0.0,
          by=FIT_BY):
    """Собрать кадр целиком. Возвращает числа кадра — они попадут в лог рендера.

    Порядок не переставлять: сначала кадр (он даёт `scale`), потом свет — все
    источники выражены в долях охвата кадра и без `scale` встанут не туда.
    """
    scale = frame.fit(res=res, fill=fill, offset=offset, ortho_scale=ortho_scale, by=by)

    focus = frame.aim_at(build.face_world())
    frame.depth_of_field(focus, fstop=fstop)

    # Тёмный рекламный набор. Для матового объекта или светлого фона замените
    # на lighting.world_hdri(...) / lighting.world_gradient() + three_point().
    lighting.editorial_dark(
        scale, aim=build.face_world(), gain=gain,
        mirror=dict(point=build.face_world(), normal=build.face_normal()))

    render.setup(samples=samples, look=look, exposure=exposure)
    return frame.report()
