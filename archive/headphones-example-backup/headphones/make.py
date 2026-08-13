"""Шаг 5: от чистого файла до готовых кадров одной командой.

    blender -b --python make.py -- OUTDIR [hero|detail|both|preview]

Геометрию строит сам, поэтому `.blend` в репозитории не нужен: сцена — это код.
Кладёт PNG (16 бит, через AgX) и multilayer EXR (32 бита, линейный, 14 пассов),
плюс `hero.blend` — сцену ровно в том состоянии, что дало картинку.

Файл называется `make.py`, а не `render.py`, намеренно: свой каталог стоит
в `sys.path` раньше библиотеки, и `render.py` рядом со скриптом перекрыл бы
`lib/render.py` — скрипт импортировал бы сам себя.
"""
import os
import sys
from os.path import abspath, dirname, join

HERE = dirname(abspath(__file__))
sys.path.insert(0, join(dirname(dirname(HERE)), "lib"))
sys.path.insert(0, HERE)

import bpy            # noqa: E402
from mathutils import Vector  # noqa: E402

import render as R    # noqa: E402
import scene          # noqa: E402
import build          # noqa: E402
import shot           # noqa: E402

SAMPLES = 320


def hero(outdir):
    info = shot.apply(samples=SAMPLES)
    passes = R.enable_passes()
    print("HERO", info, passes)
    made = R.save(join(outdir, "hero_night_chrome"))
    bpy.ops.wm.save_as_mainfile(filepath=join(outdir, "hero.blend"))
    return made


def detail(outdir):
    """Крупный план эмблемы: тот же свет и ракурс, уже кадр.

    Диафрагму зажимаем до f/9: на таком масштабе прежнее размытие съело бы
    саму деталь, ради которой кадр и снимается.
    """
    info = shot.apply(samples=SAMPLES, res=(1100, 1100), ortho_scale=1.05,
                      fstop=9.0, offset=(0.0, 0.0))
    cam = bpy.context.scene.camera
    # Кадрируем на эмблему: сдвиг считаем из её положения в системе камеры.
    p = cam.matrix_world.inverted() @ Vector(build.logo_world())
    cam.data.shift_x = p.x / cam.data.ortho_scale
    cam.data.shift_y = p.y / cam.data.ortho_scale
    passes = R.enable_passes()
    print("DETAIL", info, passes)
    return R.save(join(outdir, "detail_emblem"))


def preview(outdir):
    """Дешёвый взгляд: один PNG, без пассов. Для итераций между правками."""
    print("PREVIEW", shot.apply(samples=64, res=(450, 600)))
    return [R.preview(join(outdir, "preview.png"), res=(450, 600), samples=64)]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("blender -b --python make.py -- OUTDIR [hero|detail|both|preview]")
    outdir = abspath(argv[0])
    which = argv[1] if len(argv) > 1 else "both"
    os.makedirs(outdir, exist_ok=True)

    # Обязательно: `blender -b` без файла грузит СТАРТОВУЮ сцену с кубом и лампой,
    # и оба честно попадают в кадр. Стоило одного перерендера.
    scene.reset()
    counts = build.build()
    print("BUILD polys:", sum(counts.values()))
    shot.restore()

    made = []
    if which in ("hero", "both"):
        made += hero(outdir)
    if which in ("detail", "both"):
        made += detail(outdir)
    if which == "preview":
        made += preview(outdir)

    for f in made:
        print("OUT", f, os.path.getsize(f))


main()
