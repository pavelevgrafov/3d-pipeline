"""Шаги 2–4 одним файлом: утверждённый ракурс, набор материалов, свет и кадр.

Все числа здесь — то, что пользователь утвердил на контрольных точках. Они
записаны в КОД, а не взяты из `.blend`, и это принципиально: файл сцены на диске
мог быть сохранён до утверждения, а числа воспроизводят кадр всегда и без
открытого Blender.

Изменить кадр = изменить число здесь и перезапустить рендер.
"""
import sys
from os.path import abspath, dirname, join

sys.path.insert(0, join(dirname(dirname(dirname(abspath(__file__)))), "lib"))
sys.path.insert(0, dirname(abspath(__file__)))

import bpy                                        # noqa: E402
import frame                                      # noqa: E402
import lighting                                   # noqa: E402
import render                                     # noqa: E402

import build                                      # noqa: E402
import sets                                       # noqa: E402
import camera as cam_lib                          # noqa: E402

# --- утверждено пользователем -----------------------------------------------
# Ракурс снят прямо с вьюпорта: пользователь докрутил объект мышью и сказал
# «вот так». Орто — осознанный выбор, перспективу не навязываем.
CAM_QUAT = (0.27962, 0.416601, 0.718235, 0.482073)
CAM_EYE = (4.6535, 2.5828, -2.4749)
VIEW_DISTANCE = 5.6757          # опорный охват вьюпорта в момент снятия
MATERIAL_SET = 3                # Night Chrome

RES = (900, 1200)               # вертикальный кадр 3:4 — рекламный разворот
FILL = 0.86                     # доля высоты кадра под объект
OFFSET = (0.04, 0.05)           # увод от центра: объект стоит по диагонали
FSTOP = 4.0                     # см. LIMITS.md: в орто рабочий диапазон 2.5…5.0

# Мусор от предыдущих шагов: студийный свет сравнения материалов и метка листа.
JUNK = ("KeyStudio", "FillStudio", "RimStudio", "SheetLabel", "CamTarget")


def restore():
    """Камера и материалы из утверждённых чисел. Живой Blender не нужен."""
    for n in JUNK:
        ob = bpy.data.objects.get(n)
        if ob:
            bpy.data.objects.remove(ob)
    cam = cam_lib.restore(quat=CAM_QUAT, eye=CAM_EYE, ortho=True,
                          view_distance=VIEW_DISTANCE, view_lens=50.0)
    title = sets.apply(MATERIAL_SET)
    print("SHOT материалы:", title)
    return cam


def apply(samples=320, res=RES, fill=FILL, offset=OFFSET, fstop=FSTOP,
          ortho_scale=None, gain=1.0, look="AgX - High Contrast", exposure=0.0):
    """Собрать кадр целиком. Возвращает числа кадра — они печатаются в лог.

    Порядок важен и не переставляется: сначала кадр (он даёт `scale`), потом
    свет — все источники выражены в долях охвата кадра.
    """
    scale = frame.fit(res=res, fill=fill, offset=offset, ortho_scale=ortho_scale)

    # Фокус — на эмблеме, а не на центре габаритов: по референсу резкая должна
    # быть именно она, ближняя чашка и дальняя дужка уходят в размытие.
    focus = frame.aim_at(build.logo_world())
    frame.depth_of_field(focus, fstop=fstop)

    # Правый диск — плоская полированная деталь, смотрящая по +X. Без отражателя
    # по зеркальному лучу он остаётся чёрным пятном при любой яркости остального.
    lighting.editorial_dark(scale, aim=build.logo_world(), gain=gain,
                            mirror=dict(point=build.logo_world(), normal=(1, 0, 0)))

    render.setup(samples=samples, look=look, exposure=exposure)
    return frame.report()
