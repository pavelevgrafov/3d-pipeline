"""Проверочный этап: пропорции референса и модели — числом, а не взглядом.

Идея та же, что у `frame.py` («сначала измерить, потом решать»), только для
самого частого источника ошибки на органических/непростых формах: «модель
непропорциональна референсу» — субъективная жалоба, которую нечем проверить
до тех пор, пока кто-то не сравнит их числами. Порог + чёрный фон дают
силуэт, силуэт даёт ширину на любой доле высоты, а дальше это просто два
профиля одних и тех же единиц — сравнимые независимо от разрешения картинки
и масштаба сцены.

Дешёвый гейт: `profile()` на референсе — секунды, без Blender-рендера самой
модели. Есть смысл прогнать его на референсах СРАЗУ при получении, до того,
как потрачено время на геометрию: несогласованные ракурсы (разный масштаб
или дистанция камеры между кадрами одного объекта) видны уже здесь — если
силуэт по двум видам одного и того же предмета не сходится по высоте на
разумную величину, дальше сравнивать не с чем.

Ничего предметного здесь нет: подписи долей высоты задаёт вызывающий код
(проект), библиотека передаёт только доли числами по умолчанию.
"""
import bpy

import camera
import frame
import lighting

# Десять точек по высоте, поровну — нейтральный набор для случая, когда
# вызывающий код не задал свой (частями тела, ярусами предмета и т.п.).
DEFAULT_FRACTIONS = {f"{int(round(f * 100))}%": f
                     for f in (0.05, 0.15, 0.25, 0.35, 0.45,
                               0.55, 0.65, 0.75, 0.85, 0.95)}


def _rows(path, thresh):
    """Не-чёрные пиксели каждой строки: (min_x, max_x) или None, сверху вниз."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = img.pixels[:]
    bpy.data.images.remove(img)

    rows = []
    for row in range(h):
        y = h - 1 - row               # пиксели Blender лежат снизу вверх
        base = y * w * 4
        xs = [x for x in range(w)
              if max(px[base + x * 4], px[base + x * 4 + 1], px[base + x * 4 + 2]) > thresh]
        rows.append((min(xs), max(xs)) if xs else None)
    return w, rows


def _is_ui_bar(row, width):
    """Строка шире 90% картинки — это сплошная полоса интерфейса поверх
    скриншота (плеер, скраббер), не край объекта. Без этого фильтра такая
    строка становится ложным «низом» силуэта и роняет всю высоту объекта.
    """
    return row is not None and (row[1] - row[0] + 1) > 0.90 * width


def profile(path, fractions=None, thresh=0.06):
    """Ширина силуэта на заданных долях высоты — в долях ЖЕ высоты силуэта.

    Нормировка на высоту, а не пиксели, — то, что делает результат сравнимым
    между референсом и рендером любого разрешения. `fractions` — словарь
    {подпись: доля от 0 до 1}, счёт от верхней точки силуэта; по умолчанию
    `DEFAULT_FRACTIONS`.

    `thresh` — порог яркости канала, при котором пиксель считается объектом,
    а не чёрным фоном. Референсы этого пайплайна ожидаются на чёрном фоне;
    для светлого фона нужен другой признак, здесь не реализовано.
    """
    fractions = fractions or DEFAULT_FRACTIONS
    width, rows = _rows(path, thresh)

    subject = [i for i, r in enumerate(rows) if r is not None and not _is_ui_bar(r, width)]
    if not subject:
        raise RuntimeError(f"{path}: ни один пиксель не прошёл порог thresh={thresh}")
    top, bottom = min(subject), max(subject)
    height = bottom - top
    if height == 0:
        raise RuntimeError(f"{path}: силуэт высотой в одну строку — порог не подходит")

    def width_at(frac):
        target = max(top, min(bottom, top + int(round(frac * height))))
        # Ближайшая строка с данными: доля может указать на промежуток между
        # частями фигуры (просвет между руками и телом), где строка пуста.
        for d in range(21):
            for cand in (target - d, target + d):
                if top <= cand <= bottom and rows[cand] is not None \
                        and not _is_ui_bar(rows[cand], width):
                    lo, hi = rows[cand]
                    return (hi - lo + 1) / height
        return None

    return {label: width_at(f) for label, f in fractions.items()}


def flat_render(path, res=(700, 1150), lens=60.0, fill=1.06,
                azimuth=0.0, elevation=0.0):
    """Плоский орто-силуэт текущей сцены: белые меши на чёрном фоне.

    Ставит свою камеру и материалы, потом возвращает исходные — вызывающий
    код может продолжать со сценой как ни в чём не бывало. По умолчанию
    ракурс — анфас (`azimuth=elevation=0`), как и раньше: силуэт сравнивается
    с референсом того же ракурса, а не с утверждённым кадром `shot.py`.

    `azimuth`/`elevation` (градусы, та же система, что у `camera.look_from`)
    позволяют снять силуэт с другой стороны — например, 3/4 в дополнение
    к анфасу, если для референса есть снимок этого же ракурса. Библиотека
    не решает, какие ракурсы значимы для конкретного предмета — это
    по-прежнему решение проекта, ровно как и подписи `fractions`. Это
    по-прежнему не проверка 3D-формы целиком: несколько плоских проекций —
    не то же самое, что объём, см. LIMITS.md.
    """
    subjects = frame.subjects()
    if not subjects:
        raise RuntimeError("нет видимых мешей — нечего рендерить силуэтом")

    zs = [(ob.matrix_world @ v.co).z for ob in subjects for v in ob.data.vertices]
    target = (0, 0, (min(zs) + max(zs)) / 2)

    saved_world = bpy.context.scene.world
    saved_mats = [(ob, list(ob.data.materials)) for ob in subjects]
    saved_cam = (bpy.context.scene.camera.data.type
                 if bpy.context.scene.camera else None)

    flat = bpy.data.materials.get("_SilhouetteFlat")
    if flat is None:
        flat = bpy.data.materials.new("_SilhouetteFlat")
        flat.use_nodes = True
        nt = flat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        emit = nt.nodes.new("ShaderNodeEmission")
        emit.inputs["Color"].default_value = (1, 1, 1, 1)
        nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    for ob in subjects:
        ob.data.materials.clear()
        ob.data.materials.append(flat)
    lighting.world_flat(color=(0, 0, 0), strength=1.0)

    camera.look_from(azimuth, elevation, 10.0, target=target, lens=lens)
    cam = bpy.context.scene.camera
    cam.data.type = "ORTHO"
    _, (y0, y1), _ = frame.extent()
    cam.data.ortho_scale = (y1 - y0) * fill

    sc = bpy.context.scene
    sc.render.engine = camera.preview_engine()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = 16
    else:
        sc.eevee.taa_render_samples = 16
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

    for ob, mats in saved_mats:
        ob.data.materials.clear()
        for m in mats:
            ob.data.materials.append(m)
    bpy.context.scene.world = saved_world
    if saved_cam:
        cam.data.type = saved_cam
    return path


def compare(reference, render, tolerance=None):
    """Расхождение двух профилей в процентах — таблица вместо «не похоже».

    Оба аргумента — результат `profile()`. Метка, которой нет в одном из двух
    (пустая строка силуэта на одном из снимков), даёт `None`, а не падение:
    отсутствие одной точки не должно ронять всё сравнение.

    Без `tolerance` поведение прежнее — голое число расхождения в процентах.
    С `tolerance` (доля, например `0.15`) каждая метка вместо числа даёт
    словарь `{"diff": -3.2, "ok": True}` — решение «в пределах нормы или нет»
    посчитано, а не остаётся каждый раз на человеке. Порог — не предметный,
    живёт как параметр вызова, а не константа библиотеки, ровно как `fractions`.
    """
    out = {}
    for label, ref_v in reference.items():
        got_v = render.get(label)
        if ref_v is None or got_v is None:
            out[label] = None
            continue
        diff = round((got_v - ref_v) / ref_v * 100, 1)
        out[label] = diff if tolerance is None \
            else {"diff": diff, "ok": abs(diff) <= tolerance * 100}
    return out


def audit_references(paths, fractions=None, thresh=0.06, tolerance=0.15):
    """Согласованность нескольких референсов ОДНОГО ракурса между собой.

    Диагностированный на практике случай: расхождения, приписанные неточной
    геометрии, на деле объяснялись несогласованной дистанцией/фокусным между
    снимками одного объекта — и это видно уже по самим референсам, до того,
    как потрачено время на форму. Прогонять на шаге 0, сразу после получения
    референсов, до `build.py`.

    Считает `profile()` каждого пути, затем медианный профиль по группе
    (медиана, а не среднее — один выброс не должен сдвигать эталон, который
    с ним же и сравнивается) и отклонение каждого кадра от медианы через
    `compare(median, profile, tolerance=tolerance)`.

    Возвращает `{path: {"profile": {...}, "diff": {...}, "outlier": bool}}`.
    `outlier=True` — хотя бы одна метка вышла за `tolerance` относительно
    медианы. Функция не судит, какой из кадров правильный, только показывает,
    какой выбивается из группы.

    Ограничение: сравнимо только внутри одного ракурса — снимки задуманы как
    одна и та же поза/анфас. Референсы разных ракурсов между собой не
    сравниваются здесь — для этого несколько вызовов `flat_render(azimuth=…)`
    по отдельности, каждый со своим референсом того же ракурса.
    """
    if len(paths) < 2:
        raise ValueError("нужно минимум два референса, чтобы сравнивать согласованность")

    profiles = {p: profile(p, fractions=fractions, thresh=thresh) for p in paths}
    labels = next(iter(profiles.values())).keys()

    median = {}
    for label in labels:
        vals = sorted(v[label] for v in profiles.values() if v[label] is not None)
        if not vals:
            median[label] = None
            continue
        n = len(vals)
        median[label] = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2

    out = {}
    for p, prof in profiles.items():
        diff = compare(median, prof, tolerance=tolerance)
        outlier = any(v is not None and not v["ok"] for v in diff.values())
        out[p] = {"profile": prof, "diff": diff, "outlier": outlier}
    return out
