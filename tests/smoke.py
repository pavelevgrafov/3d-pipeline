"""Сквозная проверка пайплайна на тестовой сцене. Запускается внутри Blender.

Проходит все шесть шагов на объекте, которого никто не проектировал: набор
примитивов размером около восьми единиц — намеренно НЕ такой, как заготовка.
Если библиотека действительно универсальна, ни одно число подкручивать не нужно.

Не для красоты: разрешения крошечные, сэмплов мало. Задача — поймать поломку
API и неверные допущения, а не сделать картинку.

    blender -b --python tests/smoke.py -- OUTDIR

Печатает строки `CHECK <имя> ok|FAIL <подробности>` и в конце `SMOKE PASS|FAIL`.
Запускать удобнее через `python3 check.py`, который ещё и разбирает вывод.
"""
import math
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import camera      # noqa: E402
import diff        # noqa: E402
import exr_info    # noqa: E402
import frame       # noqa: E402
import lighting    # noqa: E402
import materials   # noqa: E402
import mosaic      # noqa: E402
import post        # noqa: E402
import render      # noqa: E402
import silhouette  # noqa: E402
import telemetry   # noqa: E402
import variants    # noqa: E402

RESULTS = []


def check(name):
    """Контекстный менеджер не нужен — обычный декоратор проще читается в логе."""
    def wrap(fn):
        try:
            detail = fn()
            RESULTS.append((name, True, detail))
            print(f"CHECK {name} ok {detail}")
            return detail
        except Exception as exc:                     # noqa: BLE001 — это и есть отчёт
            import traceback
            RESULTS.append((name, False, repr(exc)))
            print(f"CHECK {name} FAIL {exc!r}")
            traceback.print_exc()
            return None
    return wrap


def out(*parts):
    return os.path.join(OUTDIR, *parts)


# ---------------------------------------------------------------------------
def build_scene():
    """Тестовый объект: заведомо не заготовка и заведомо другого масштаба.

    Габарит около 7.6 единиц против 3.2 у заготовки, и форма кольцевая вместо
    сплошной — этим и проверяется, что свет и кадр считаются от объекта,
    а не от зашитых констант.
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.mesh.primitive_torus_add(major_radius=3.0, minor_radius=0.8,
                                     major_segments=48, minor_segments=16)
    bpy.context.object.name = "Body"

    # Плоский полированный диск, смотрящий по +X: ради него существует mirror_board.
    bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=0.25, vertices=64,
                                        location=(3.0, 0, 0),
                                        rotation=(0, math.radians(90), 0))
    bpy.context.object.name = "Face"

    bpy.ops.mesh.primitive_cube_add(size=1.4, location=(-3.0, 0, 0.6))
    bpy.context.object.name = "Trim"

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.9, segments=24, ring_count=12,
                                         location=(0, 0, 2.4))
    bpy.context.object.name = "Cap"

    bpy.ops.mesh.primitive_plane_add(size=1.6, location=(0, 0, -2.2))
    bpy.context.object.name = "Pane"

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 2.6, 0))
    bpy.context.object.name = "Weave"

    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.25,
                                     major_segments=24, minor_segments=10,
                                     location=(0, -2.8, 0))
    bpy.context.object.name = "Pad"

    return [ob.name for ob in bpy.context.scene.objects if ob.type == "MESH"]


SLOTS = {
    "metal": lambda: materials.metal("metal", (0.72, 0.71, 0.69, 1), rough=0.18,
                                     aniso=0.6, radial=True, brush_scale=900),
    "leather": lambda: materials.leather("leather", (0.10, 0.06, 0.04, 1), grain=90),
    "plastic": lambda: materials.plastic("plastic", (0.02, 0.02, 0.03, 1),
                                         rough=0.08, coat=1.0),
    "glass": lambda: materials.glass("glass", rough=0.03),
    "carbon": lambda: materials.carbon("carbon", scale=40),
    "nubuck": lambda: materials.nubuck("nubuck", (0.06, 0.06, 0.07, 1)),
}
OBJECTS = {
    "metal": ["Body", "Face"],
    "leather": ["Trim"],
    "plastic": ["Cap"],
    "glass": ["Pane"],
    "carbon": ["Weave"],
    "nubuck": ["Pad"],
}


def main():
    names = build_scene()
    print("SMOKE scene", names)

    # --- шаг 2: ракурс ------------------------------------------------------
    @check("camera.look_from")
    def _():
        cam = camera.look_from(azimuth=52, elevation=14, distance=14.0, lens=60)
        return {"loc": tuple(round(v, 3) for v in cam.location)}

    @check("camera.read_viewport_in_background")
    def _():
        # В фоне вьюпорта нет: функция обязана вернуть None, а snap — внятно упасть.
        assert camera.read_viewport() is None, "в фоне вьюпорта быть не должно"
        try:
            camera.snap_to_viewport()
        except RuntimeError as exc:
            return {"raised": type(exc).__name__}
        raise AssertionError("snap_to_viewport в фоне обязан бросить RuntimeError")

    @check("camera.restore_from_numbers")
    def _():
        cam = camera.restore(quat=(0.2796, 0.4166, 0.7182, 0.4821),
                             eye=(9.0, 5.0, -4.5), ortho=True,
                             view_distance=14.0, view_lens=50.0)
        assert cam.data.type == "ORTHO"
        return {"ortho_scale": round(cam.data.ortho_scale, 4)}

    @check("camera.contact_sheet")
    def _():
        # Контрольный лист рендерится в EEVEE — это шаг «посмотреть форму», не финал.
        camera.look_from(0, 12, 14.0)
        got = camera.contact_sheet(out("sheet.png"), angles=[0, 90, 180, 270],
                                   elevation=12, distance=14.0, res=160, cols=2)
        assert os.path.exists(out("sheet.png")), "лист ракурсов не создан"
        assert not os.path.isdir(out("_sheet_tmp")), "временная папка не убрана"
        return {"tiles": len(got), "engine": camera.preview_engine(),
                "bytes": os.path.getsize(out("sheet.png"))}

    # --- шаг 3: материалы ---------------------------------------------------
    @check("materials.apply_slots")
    def _():
        hits = materials.apply_slots(SLOTS, OBJECTS)
        assert all(v > 0 for v in hits.values()), f"слоты без объектов: {hits}"
        return hits

    @check("materials.apply_set")
    def _():
        sets = [dict(title="набор 1", metal=SLOTS["metal"]),
                dict(title="набор 2", metal=lambda: materials.metal("m2", (0.2, 0.2, 0.22, 1)))]
        title = materials.apply_set(sets, 2, {"metal": ["Body", "Face"]})
        try:
            materials.apply_set(sets, 5, {"metal": ["Body"]})
        except IndexError:
            pass
        else:
            raise AssertionError("выход за диапазон наборов обязан падать")
        materials.apply_slots(SLOTS, OBJECTS)          # вернуть как было
        return {"title": title}

    @check("materials.pbr_library")
    def _():
        # Настоящих карт в репозитории нет, поэтому кладём две пустышки: проверяется
        # разбор имён файлов и сборка нод, а не содержимое текстур.
        folder = out("_pbr")
        os.makedirs(folder, exist_ok=True)
        for stem in ("test_diff_2k.png", "test_rough_2k.png"):
            img = bpy.data.images.new(stem, 16, 16)
            img.filepath_raw = os.path.join(folder, stem)
            img.file_format = "PNG"
            img.save()
            bpy.data.images.remove(img)
        m = materials.pbr_library("pbr_test", folder, scale=2.0)
        n_tex = sum(1 for nd in m.node_tree.nodes if nd.type == "TEX_IMAGE")
        assert n_tex == 2, f"ожидались две карты, собрано {n_tex}"

        empty = out("_pbr_empty")
        os.makedirs(empty, exist_ok=True)
        try:
            materials.pbr_library("pbr_empty", empty)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("пустая папка карт обязана падать явно")
        return {"textures": n_tex}

    # --- шаг 4: свет и окружение -------------------------------------------
    @check("lighting.world_gradient+three_point")
    def _():
        lighting.world_gradient()
        made = lighting.three_point(target=(0, 0, 0), distance=14.0)
        assert len(made) == 3
        return {"lights": made}

    @check("lighting.world_hdri")
    def _():
        # Настоящего HDRI в репозитории нет — генерируем крошечный,
        # чтобы проверить загрузку, ноды и поворот окружения.
        path = out("_env.hdr")
        img = bpy.data.images.new("env_test", 32, 16, float_buffer=True)
        img.pixels = [0.4, 0.5, 0.7, 1.0] * (32 * 16)
        img.filepath_raw = path
        img.file_format = "HDR"
        img.save()
        bpy.data.images.remove(img)
        lighting.world_hdri(path, strength=0.8, rotation=35)
        try:
            lighting.world_hdri(out("нет-такого.hdr"))
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("отсутствующий HDRI обязан падать явно")
        return {"hdri": os.path.getsize(path)}

    # --- шаг 2 (продолжение): кадрирование ----------------------------------
    def _fills(res, scale):
        """Какую долю кадра занял объект по ширине и по высоте.

        `scale` — охват по БОЛЬШЕЙ стороне кадра; вдоль оси i охват равен
        `scale · res_i / max(res)`. Кадр здесь неквадратный именно поэтому:
        на квадрате обе доли совпадают, и ошибка в пропорциях не видна.
        """
        (x0, x1), (y0, y1), _ = frame.extent()
        long_side = max(res)
        return ((x1 - x0) / (scale * res[0] / long_side),
                (y1 - y0) / (scale * res[1] / long_side))

    @check("frame.fit_perspective")
    def _():
        camera.look_from(52, 14, 14.0, lens=60)
        res, fill = (240, 320), 0.8
        scale = frame.fit(res=res, fill=fill)
        w, h = _fills(res, scale)
        # Контракт by="max": по узкой стороне объект занимает ровно fill,
        # по другой — не больше, то есть в кадр он влезает целиком.
        assert abs(max(w, h) - fill) < 0.02, f"занял {max(w, h):.3f} вместо {fill}"
        assert w <= fill + 0.02 and h <= fill + 0.02, f"вылез за кадр: {w:.3f}×{h:.3f}"
        return {"scale": round(scale, 3), "fill_wh": (round(w, 3), round(h, 3))}

    @check("frame.fit_ortho")
    def _():
        cam = bpy.context.scene.camera
        cam.data.type = "ORTHO"
        res, fill = (240, 320), 0.86
        scale = frame.fit(res=res, fill=fill, offset=(0.02, 0.03))
        w, h = _fills(res, scale)
        assert abs(max(w, h) - fill) < 0.001, f"занял {max(w, h):.3f} вместо {fill}"
        assert w <= fill + 0.001 and h <= fill + 0.001, f"вылез за кадр: {w:.3f}×{h:.3f}"
        return {"scale": round(scale, 3), "fill_wh": (round(w, 3), round(h, 3))}

    @check("frame.fit_by_height_crops")
    def _():
        """`by="height"` заполняет высоту ровно и РАЗРЕШАЕТ обрез по ширине.

        Тестовый объект широкий, кадр вертикальный — то самое сочетание, на
        котором прежний код молча срезал бока, считая это нормой.
        """
        res, fill = (240, 320), 0.86
        scale = frame.fit(res=res, fill=fill, by="height")
        w, h = _fills(res, scale)
        assert abs(h - fill) < 0.001, f"по высоте занял {h:.3f} вместо {fill}"
        assert w > fill, "обрез по ширине не наступил — проверять нечего"
        return {"fill_wh": (round(w, 3), round(h, 3))}

    @check("frame.extent_excludes_service")
    def _():
        # И фон, и источники света — меши, и оба заведомо больше объекта.
        # Если они попадут в габариты, поедет всё, что от габаритов считается:
        # охват кадра, сдвиг, диапазон Mist.
        cam = bpy.context.scene.camera
        before = frame.extent()
        lighting.backdrop(cam.data.ortho_scale, span=1.6)
        assert frame.extent() == before, "фон просочился в габариты объекта"
        lighting.emitter("KeyStrip", 30.0, 40.0, 10.0, local=(9, 0, -12), aim=(0, 0, 0))
        assert frame.extent() == before, "источник света просочился в габариты объекта"
        lighting.clear()
        return {"extent_y": tuple(round(v, 3) for v in before[1])}

    @check("frame.depth_of_field")
    def _():
        f = frame.aim_at(None)                  # центр габаритов
        info = frame.depth_of_field(f, fstop=4.0)
        assert bpy.context.scene.camera.data.dof.use_dof
        return info

    SCALE = bpy.context.scene.camera.data.ortho_scale

    @check("lighting.editorial_dark")
    def _():
        aim = frame.center()
        made = lighting.editorial_dark(
            SCALE, aim, gain=1.0,
            mirror=dict(point=tuple(bpy.data.objects["Face"].location) ,
                        normal=(1, 0, 0)))
        assert len(made) == 6, f"ожидались пять источников и отражатель, вышло {made}"
        # Ключевое свойство набора: подсвечивать диффузно разрешено только заливке.
        diffuse = [n for n in made
                   if bpy.data.objects[n].visible_diffuse]
        assert diffuse == ["FillLeft"], f"диффузно светят лишние источники: {diffuse}"
        return {"rig": made}

    @check("lighting.clear")
    def _():
        lighting.clear()
        left = [n for n in lighting.RIG if bpy.data.objects.get(n)]
        assert not left, f"после clear() остались объекты: {left}"
        # Собрать заново — дальше рендерим именно с этим светом.
        lighting.editorial_dark(SCALE, frame.center(),
                                mirror=dict(point=tuple(bpy.data.objects["Face"].location),
                                            normal=(1, 0, 0)))
        return {"cleared": True}

    # --- петля обратной связи ----------------------------------------------
    @check("variants.grid")
    def _():
        def apply(res, samples, fstop):
            render.setup(samples=samples)
            frame.depth_of_field(bpy.data.objects["FocusPoint"], fstop=fstop)
            return f"f/{fstop}"
        info = variants.grid(apply, [dict(fstop=3.0), dict(fstop=8.0)],
                             out("variants.png"), res=(120, 160), samples=8,
                             cols=2, label=True)
        assert os.path.exists(out("variants.png"))
        assert not os.path.isdir(out("_var_tmp")), "временная папка не убрана"
        return {"cases": info, "bytes": os.path.getsize(out("variants.png"))}

    @check("mosaic.tile_size_guard")
    def _():
        import numpy as np
        a = np.zeros((4, 4, 4), dtype=np.float32)
        b = np.zeros((5, 4, 4), dtype=np.float32)
        try:
            mosaic.tile([a, b])
        except ValueError:
            pass
        else:
            raise AssertionError("плитки разного размера обязаны падать явно")
        try:
            mosaic.tile([])
        except ValueError:
            pass
        else:
            raise AssertionError("пустой список плиток обязан падать явно")
        return {"guards": 2}

    # --- шаг 5: рендер ------------------------------------------------------
    @check("render.setup+passes+save")
    def _():
        render.setup(samples=24, look="AgX - Base Contrast")
        frame.fit(res=(240, 320), fill=0.86)
        info = render.enable_passes()
        made = render.save(out("hero"))
        for f in made:
            assert os.path.exists(f) and os.path.getsize(f) > 0, f"пусто: {f}"
        return {"mist": info, "files": [os.path.basename(f) for f in made]}

    @check("exr_info.passes")
    def _():
        ps = exr_info.passes(out("hero.exr"))
        got = {n for n, _ in ps}
        # Пассы лежат с префиксом слоя: "ViewLayer.Depth", а AO записывается
        # полным именем "Ambient Occlusion" — сокращения в файле нет.
        need = {"Combined", "Depth", "Normal", "Mist", "Ambient Occlusion",
                "Diffuse Color", "Glossy Direct"}
        missing = [n for n in need
                   if not any(n.lower() in g.lower() for g in got)]
        assert not missing, f"в EXR нет пассов: {missing}; есть {sorted(got)}"
        crypto = [g for g in got if "crypto" in g.lower()]
        assert crypto, f"нет cryptomatte; есть {sorted(got)}"
        assert exr_info.size(out("hero.exr")) == (240, 320), "размер EXR не тот"
        return {"passes": len(ps), "crypto": len(crypto)}

    @check("render.preview")
    def _():
        p = render.preview(out("preview.png"), res=(120, 160), samples=8)
        assert os.path.exists(p)
        return {"bytes": os.path.getsize(p)}

    # --- проверка пропорций: силуэт референса и модели, числом -------------
    @check("silhouette.profile+ui_bar_filter")
    def _():
        def wedge(path, ui_bar):
            """Клин на чёрном фоне: ширина растёт сверху вниз — известный,
            монотонный профиль, по которому видно, испортил ли UI-бар число.
            """
            w, h = 40, 60
            img = bpy.data.images.new("test_sil", w, h, alpha=False)
            # Alpha=1 обязателен по всей картинке: PNG пишется с премультипликацией
            # альфы, и нулевая альфа молча топит белый цвет в чёрный при сохранении.
            px = [0.0, 0.0, 0.0, 1.0] * (w * h)
            for disp_row in range(5, 55):
                t = (disp_row - 5) / 49
                half = 3 + round(12 * t)
                y = h - 1 - disp_row              # хранение пикселей снизу вверх
                for x in range(w // 2 - half, w // 2 + half):
                    base = y * w * 4 + x * 4
                    px[base:base + 3] = [1.0, 1.0, 1.0]
            if ui_bar:
                # Нижняя строка картинки во всю ширину — скраббер поверх скриншота.
                for x in range(w):
                    base = x * 4
                    px[base:base + 3] = [1.0, 1.0, 1.0]
            img.pixels = px
            img.filepath_raw = path
            img.file_format = "PNG"
            img.save()
            bpy.data.images.remove(img)

        clean, dirty = out("_sil_clean.png"), out("_sil_dirty.png")
        wedge(clean, ui_bar=False)
        wedge(dirty, ui_bar=True)

        p_clean, p_dirty = silhouette.profile(clean), silhouette.profile(dirty)
        # Без фильтра нижние доли "dirty" читались бы как полная ширина
        # картинки вместо края клина — расхождение было бы огромным.
        worst = max(abs(p_dirty[k] - p_clean[k]) for k in p_clean if p_clean[k] is not None)
        assert worst < 0.05, f"UI-бар просочился в профиль: расхождение {worst:.3f}"
        vals = [p_clean[f"{f}%"] for f in (5, 25, 45, 65, 85)]
        assert vals == sorted(vals), f"профиль клина не монотонен: {vals}"
        return {"worst_diff": round(worst, 4), "vals": [round(v, 3) for v in vals]}

    @check("silhouette.flat_render+compare")
    def _():
        path = silhouette.flat_render(out("_sil_render.png"), res=(80, 140))
        assert os.path.exists(path) and os.path.getsize(path) > 0
        prof = silhouette.profile(path)
        assert any(v is not None for v in prof.values()), "пустой профиль рендера"
        same = silhouette.compare(prof, prof)
        assert all(v == 0 for v in same.values() if v is not None), \
            f"compare(x, x) обязан давать нули: {same}"
        # Материалы и мир — временная подмена ради силуэта, а не побочный эффект.
        mats = [m.name for m in bpy.data.objects["Body"].data.materials]
        assert mats and mats[0] != "_SilhouetteFlat", f"материал не восстановлен: {mats}"
        return {"labels": len(prof), "45%": prof.get("45%")}

    # --- v1.2: допуск/вердикт, аудит референсов, многоракурсный силуэт -----
    @check("silhouette.compare_tolerance")
    def _():
        ref = {"a": 10.0, "b": 20.0}
        good = {"a": 10.5, "b": 19.0}       # ~5% и ~5% — в пределах 10%
        bad = {"a": 10.5, "b": 30.0}        # b — 50% мимо
        same = silhouette.compare(ref, ref, tolerance=0.1)
        assert all(v["ok"] for v in same.values()), f"compare(x,x) обязан быть ok: {same}"
        mixed = silhouette.compare(ref, bad, tolerance=0.1)
        assert mixed["a"]["ok"] and not mixed["b"]["ok"], f"вердикт неверный: {mixed}"
        bare = silhouette.compare(ref, good)
        assert isinstance(bare["a"], float), "без tolerance обязано быть голое число"
        return {"same": same, "mixed": mixed}

    @check("silhouette.audit_references")
    def _():
        def wedge2(path, scale):
            """Тот же клин, что и выше, но с управляемым масштабом ширины —
            ровно то расхождение между референсами одного ракурса, которое
            audit_references должен ловить (несогласованная дистанция/фокусное).
            """
            w, h = 40, 60
            img = bpy.data.images.new("test_sil_audit", w, h, alpha=False)
            px = [0.0, 0.0, 0.0, 1.0] * (w * h)
            for disp_row in range(5, 55):
                t = (disp_row - 5) / 49
                half = max(1, min(w // 2 - 1, int(round((3 + 12 * t) * scale))))
                y = h - 1 - disp_row
                for x in range(w // 2 - half, w // 2 + half):
                    base = y * w * 4 + x * 4
                    px[base:base + 3] = [1.0, 1.0, 1.0]
            img.pixels = px
            img.filepath_raw = path
            img.file_format = "PNG"
            img.save()
            bpy.data.images.remove(img)

        paths = [out(f"_audit_{i}.png") for i in range(4)]
        for p in paths[:3]:
            wedge2(p, scale=1.0)          # три согласованных снимка
        wedge2(paths[3], scale=1.8)       # один явно шире — «другая дистанция»

        audit = silhouette.audit_references(paths, tolerance=0.15)
        outliers = [p for p, v in audit.items() if v["outlier"]]
        assert outliers == [paths[3]], f"неверно определён выброс: {outliers}"
        return {"outliers": outliers}

    @check("silhouette.flat_render_multiview")
    def _():
        front = silhouette.flat_render(out("_sil_front.png"), res=(80, 140), azimuth=0.0)
        side = silhouette.flat_render(out("_sil_45.png"), res=(80, 140), azimuth=45.0)
        p_front, p_side = silhouette.profile(front), silhouette.profile(side)
        diffs = [abs(p_front[k] - p_side[k]) for k in p_front
                 if p_front[k] is not None and p_side[k] is not None]
        assert diffs and max(diffs) > 0.05, f"azimuth=45 не изменил силуэт: {diffs}"
        return {"max_diff": round(max(diffs), 3)}

    # --- v1.2: сравнение с прошлым утверждённым, журнал времени, дифф-гейт -
    @check("mosaic.side_by_side")
    def _():
        import numpy as np
        a = np.zeros((30, 40, 4), dtype=np.float32)
        a[..., 0], a[..., 3] = 0.8, 1.0
        b = np.zeros((30, 50, 4), dtype=np.float32)
        b[..., 1], b[..., 3] = 0.8, 1.0
        pa, pb = out("_sbs_a.png"), out("_sbs_b.png")
        mosaic.save(a, pa)
        mosaic.save(b, pb)
        result = out("_sbs_out.png")
        mosaic.side_by_side(pa, pb, result, labels=("prev", "curr"), gap=6)
        got = mosaic.load(result)
        assert got.shape[1] == 40 + 6 + 50, f"ширина не сумма исходных плюс отступ: {got.shape}"
        left_mean = float(got[:30, :40, :3].mean())
        right_mean = float(got[:30, 46:96, :3].mean())
        assert left_mean > 0.1 and right_mean > 0.1, f"половины пустые: {left_mean}, {right_mean}"
        return {"shape": got.shape, "left_mean": round(left_mean, 3), "right_mean": round(right_mean, 3)}

    @check("telemetry.record_summary")
    def _():
        tdir = out("_telemetry")
        os.makedirs(tdir, exist_ok=True)
        telemetry.record(tdir, "looks", 2.0)
        telemetry.record(tdir, "looks", 3.0)
        telemetry.record(tdir, "light", 1.5)
        s = telemetry.summary(tdir)
        assert s["looks"]["count"] == 2 and abs(s["looks"]["seconds"] - 5.0) < 1e-6, s
        assert s["light"]["count"] == 1, s
        with telemetry.timed(tdir, "final"):
            pass
        s2 = telemetry.summary(tdir)
        assert s2["final"]["count"] == 1, s2
        return {"looks": s["looks"], "final": s2["final"]}

    @check("diff.perceptual_diff")
    def _():
        import numpy as np
        a = np.zeros((32, 32, 4), dtype=np.float32)
        a[..., :3], a[..., 3] = 0.2, 1.0
        pa, pb = out("_diff_a.png"), out("_diff_b.png")
        mosaic.save(a, pa)
        mosaic.save(a.copy(), pb)
        same = diff.perceptual_diff(pa, pb, grid=(4, 4))
        assert same["max"] == 0 and same["mean"] == 0, same

        c = a.copy()
        c[16:, 16:, :3] = 0.9
        pc = out("_diff_c.png")
        mosaic.save(c, pc)
        changed = diff.perceptual_diff(pa, pc, grid=(4, 4))
        assert changed["max"] > 0.3, changed
        return {"same": same, "changed": changed}

    # --- шаг 6: пост --------------------------------------------------------
    @check("post.run")
    def _():
        # Внимание: post.run сбрасывает сцену — всё, что нужно от неё, уже сделано.
        dst = post.run(out("hero.exr"), out("hero_graded.png"),
                       vignette=0.2, strength=0.4)
        assert os.path.exists(dst) and os.path.getsize(dst) > 0
        assert exr_info.size(out("hero.exr")) == (240, 320)
        return {"bytes": os.path.getsize(dst)}

    ok = sum(1 for _, good, _ in RESULTS if good)
    bad = [n for n, good, _ in RESULTS if not good]
    print(f"SMOKE {'PASS' if not bad else 'FAIL'} {ok}/{len(RESULTS)}"
          + (f" провалено: {bad}" if bad else ""))
    return 0 if not bad else 1


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    OUTDIR = os.path.abspath(argv[0] if argv else "./_smoke")
    os.makedirs(OUTDIR, exist_ok=True)
    sys.exit(main())
