"""Пульт проекта: одна команда на каждую контрольную точку.

    blender -b --python make.py -- OUTDIR angles      # шаг 1: лист ракурсов
    blender -b --python make.py -- OUTDIR looks       # шаг 3: лист материалов
    blender -b --python make.py -- OUTDIR light       # шаг 4: варианты света
    blender -b --python make.py -- OUTDIR preview     # быстрый взгляд
    blender -b --python make.py -- OUTDIR final       # шаг 5: PNG + EXR с пассами

Шаг 6 — отдельной командой, по готовому EXR:

    blender -b --python ../lib/post.py -- OUTDIR/final.exr OUTDIR/graded.png

Называется `make.py`, а не `render.py`, намеренно: свой каталог стоит в sys.path
раньше библиотеки, и `render.py` рядом перекрыл бы `lib/render.py`.

Каждый запуск пишет время стадии в `OUTDIR/run_log.jsonl` (`lib/telemetry.py`);
`final` дополнительно печатает сводку по всем стадиям проекта. Если рядом
с `OUTDIR` лежит `<stage>.approved.png` (утверждённый на прошлой итерации
чекпоинт того же имени) — автоматически появляется `<stage>.compare.png`
("approved"/"new") и предупреждение, если разница заметна (`lib/mosaic.py`,
`lib/diff.py`).
"""
import os
import sys
from os.path import abspath, dirname, join

HERE = dirname(abspath(__file__))
sys.path.insert(0, join(dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import bpy               # noqa: E402
import camera            # noqa: E402
import diff              # noqa: E402
import frame             # noqa: E402
import lighting          # noqa: E402
import mosaic            # noqa: E402
import render as R       # noqa: E402
import scene             # noqa: E402
import telemetry         # noqa: E402
import variants          # noqa: E402

import build             # noqa: E402
import sets              # noqa: E402
import shot              # noqa: E402

# Грубый порог для diff.perceptual_diff() (0..1 по каналу) — выше него
# сравнение с <stage>.approved.png печатает предупреждение, а не просто число.
DIFF_ALERT = 0.15


def angles(outdir):
    """ШАГ 1. Серая глина с 12 сторон. Вы смотрите на форму и называете, что не так."""
    lighting.world_gradient()
    lighting.three_point(distance=DIST)
    got = camera.contact_sheet(join(outdir, "angles.png"), elevation=10,
                               distance=DIST, res=320, cols=4)
    print("ANGLES", got)
    return [join(outdir, "angles.png")]


def looks(outdir):
    """ШАГ 3. Наборы материалов на ВАШЕМ кадре, а не на шариках-превью."""
    shot.restore()
    frame.fit(res=(420, 520), fill=shot.FILL, offset=shot.OFFSET)
    lighting.world_gradient()
    lighting.three_point(distance=DIST)

    def apply(res, samples, index):
        title = sets.apply(index)
        R.setup(samples=samples, look="AgX - Base Contrast")
        return title

    cases = [dict(index=i + 1) for i in range(len(sets.SETS))]
    info = variants.grid(apply, cases, join(outdir, "looks.png"),
                         res=(420, 520), samples=96, cols=3, label=True)
    for n, title in info:
        print(f"LOOK {n}: {title}")
    return [join(outdir, "looks.png")]


def light(outdir):
    """ШАГ 4. Один параметр, четыре значения, одна картинка. Вы называете номер."""
    shot.restore()

    def apply(res, samples, **kw):
        shot.apply(samples=samples, res=res, **kw)
        return kw

    cases = [dict(gain=0.6), dict(gain=1.0), dict(gain=1.6), dict(gain=2.4)]
    info = variants.grid(apply, cases, join(outdir, "light.png"),
                         res=(360, 450), samples=64, cols=2)
    print("LIGHT", info)
    return [join(outdir, "light.png")]


def preview(outdir):
    """Дешёвый взгляд между правками: один PNG, без пассов."""
    shot.restore()
    print("PREVIEW", shot.apply(samples=64, res=(540, 675)))
    return [R.preview(join(outdir, "preview.png"), res=(540, 675), samples=64)]


def final(outdir):
    """ШАГ 5. Финальное разрешение, PNG плюс multilayer EXR со всеми пассами."""
    shot.restore()
    info = shot.apply(samples=320)
    passes = R.enable_passes()
    print("FINAL", info, passes)
    made = R.save(join(outdir, "final"))
    scene.save(join(outdir, "final.blend"))
    return made


STAGES = {"angles": angles, "looks": looks, "light": light,
          "preview": preview, "final": final}


def _compare_with_approved(outdir, stage, outputs):
    """F: сравнение с прошлым утверждённым; H: грубый дифф-гейт поверх него.

    Конвенция: утвердили чекпоинт — скопируйте его в `<stage>.approved.png`
    в этой же папке (например, `looks.approved.png`). При следующем запуске
    того же `stage` рядом с новым вариантом появится `<stage>.compare.png`
    ("approved"/"new"), и если разница выше `DIFF_ALERT` — предупреждение.
    Ничего не делает, если approved-файла ещё нет — это не обязательный шаг.
    """
    approved = join(outdir, f"{stage}.approved.png")
    current = next((f for f in outputs if f.endswith(".png")), None)
    if current is None or not os.path.exists(approved):
        return
    cmp_path = mosaic.side_by_side(approved, current,
                                   join(outdir, f"{stage}.compare.png"),
                                   labels=("approved", "new"))
    d = diff.perceptual_diff(approved, current)
    print(f"COMPARE {stage} vs approved -> {cmp_path} "
          f"(max={d['max']:.3f} mean={d['mean']:.3f})")
    if d["max"] > DIFF_ALERT:
        print(f"WARNING: {stage} заметно отличается от approved "
              f"(max={d['max']:.3f} > {DIFF_ALERT})")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2 or argv[1] not in STAGES:
        raise SystemExit(f"blender -b --python make.py -- OUTDIR [{'|'.join(STAGES)}]")
    outdir, stage = abspath(argv[0]), argv[1]
    os.makedirs(outdir, exist_ok=True)

    # Обязательно: `blender -b` без файла грузит СТАРТОВУЮ сцену — с кубом
    # и лампой. Оба честно попадут в кадр и в габариты объекта.
    scene.reset()
    with telemetry.timed(outdir, "build"):
        counts = build.build()
    print("BUILD polys:", sum(counts.values()))

    global DIST
    # Дистанция обзора для листа ракурсов — из габаритов объекта, чтобы шаг 1
    # работал на предмете любого размера без подбора.
    camera.look_from(0, 10, 10.0)
    (x0, x1), (y0, y1), _ = frame.extent()
    DIST = 2.6 * max(x1 - x0, y1 - y0)

    with telemetry.timed(outdir, stage):
        outputs = STAGES[stage](outdir)
    for f in outputs:
        print("OUT", f, os.path.getsize(f))

    _compare_with_approved(outdir, stage, outputs)

    if stage == "final":
        print("TIME", telemetry.summary(outdir))


main()
