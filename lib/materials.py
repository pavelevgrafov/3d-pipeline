"""Шаг 3: материалы. Процедурные — ничего не нужно скачивать.

Каждая функция возвращает готовый материал. Все параметры — числа, поэтому
правка «шершавее», «темнее», «убери анизотропию» превращается в правку одного
аргумента, а не в поход по нодовому редактору.

Процедурные материалы — не единственный источник. Порядок предпочтения:

| Источник                          | Когда                                    |
|-----------------------------------|------------------------------------------|
| Библиотеки PBR (Poly Haven, CC0)  | реальные поверхности: дерево, бетон, ткань |
| Процедурные (этот модуль)         | металл, стекло, пластик, кожа, лак       |
| Генерация текстуры по описанию    | нестандартный узор, специфичный принт     |

Набор материалов проекта описывается словарём слот → фабрика, а сами слоты
привязываются к именам объектов сцены (`apply_slots`).
"""
import bpy

_ALIAS = {"color": "Base Color", "rough": "Roughness", "metallic": "Metallic",
          "aniso": "Anisotropic", "aniso_rot": "Anisotropic Rotation",
          "sheen": "Sheen Weight", "sheen_tint": "Sheen Tint",
          "sheen_rough": "Sheen Roughness", "coat": "Coat Weight",
          "coat_rough": "Coat Roughness", "ior": "IOR",
          "transmission": "Transmission Weight", "emission": "Emission Strength"}


def _mk(name):
    """Свежий материал с нуля: пересоздаём, чтобы итерации не наслаивались."""
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes, nt.links, nt.nodes["Principled BSDF"]


def _set(bsdf, **kw):
    for k, v in kw.items():
        key = _ALIAS.get(k, k)
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = v


def _bump(nodes, links, bsdf, height_socket, strength, distance):
    b = nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    links.new(height_socket, b.inputs["Height"])
    links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return b


def leather(name, color, grain=170.0, bump=0.30, rough=0.50, sheen=0.35,
            pores=True, rough_var=0.10):
    """Кожа: клеточное зерно (Voronoi) плюс мелкий шум, оба в Bump.

    `rough_var` — неоднородность блеска. Это главный признак, по которому глаз
    отличает настоящую кожу от коричневого пластика: ровная roughness читается
    как штамповка.
    """
    m, _, n, l, b = _mk(name)
    _set(b, color=color, rough=rough, sheen=sheen, sheen_rough=0.4,
         sheen_tint=(1, 1, 1, 1), ior=1.45)

    vor = n.new("ShaderNodeTexVoronoi")
    vor.feature, vor.distance = "F1", "EUCLIDEAN"
    vor.inputs["Scale"].default_value = grain
    vor.inputs["Randomness"].default_value = 1.0

    fine = n.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = grain * 6.0
    fine.inputs["Detail"].default_value = 6.0
    fine.inputs["Roughness"].default_value = 0.7

    mix = n.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "OVERLAY"
    mix.inputs["Factor"].default_value = 0.35 if pores else 0.15
    l.new(vor.outputs["Distance"], mix.inputs[6])
    l.new(fine.outputs["Fac"], mix.inputs[7])
    _bump(n, l, b, mix.outputs[2], bump, 0.004)

    rmap = n.new("ShaderNodeMapRange")
    rmap.inputs["To Min"].default_value = rough - rough_var
    rmap.inputs["To Max"].default_value = rough + rough_var
    l.new(vor.outputs["Distance"], rmap.inputs["Value"])
    l.new(rmap.outputs["Result"], b.inputs["Roughness"])
    return m


def nubuck(name, color, rough=0.78):
    """Замша, нубук: без бликов, сильный sheen, ворсистая микрогеометрия."""
    m, _, n, l, b = _mk(name)
    _set(b, color=color, rough=rough, sheen=0.9, sheen_rough=0.65,
         sheen_tint=(1, 1, 1, 1))
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 900.0
    noise.inputs["Detail"].default_value = 8.0
    _bump(n, l, b, noise.outputs["Fac"], 0.45, 0.002)
    return m


def metal(name, color, rough=0.15, aniso=0.0, radial=False, axis="Z", brush_scale=0.0):
    """Металл. `radial=True` плюс `aniso` — круговая шлифовка, как на диске.

    `brush_scale` добавляет микроцарапины: они ловят свет полосами, и без них
    шлифованный металл выглядит крашеным.
    """
    m, _, n, l, b = _mk(name)
    _set(b, color=color, metallic=1.0, rough=rough, aniso=aniso)
    if radial:
        t = n.new("ShaderNodeTangent")
        t.direction_type, t.axis = "RADIAL", axis
        l.new(t.outputs["Tangent"], b.inputs["Tangent"])
    if brush_scale:
        w = n.new("ShaderNodeTexNoise")
        w.inputs["Scale"].default_value = brush_scale
        w.inputs["Detail"].default_value = 2.0
        _bump(n, l, b, w.outputs["Fac"], 0.08, 0.0004)
    return m


def plastic(name, color, rough=0.5, coat=0.0, micro=0.0):
    """От софт-тача до рояльного лака. `coat=1.0, rough=0.06` — лак, `micro` — шагрень."""
    m, _, n, l, b = _mk(name)
    _set(b, color=color, rough=rough, coat=coat, coat_rough=0.05)
    if micro:
        noise = n.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 600.0
        noise.inputs["Detail"].default_value = 5.0
        _bump(n, l, b, noise.outputs["Fac"], micro, 0.001)
    return m


def glass(name, color=(1, 1, 1, 1), rough=0.02, ior=1.45):
    """Стекло: пропускание плюс лёгкая шероховатость.

    Требует Cycles и достаточного числа `transparent_max_bounces` —
    в `render.setup()` он уже поднят до 12.
    """
    m, _, n, l, b = _mk(name)
    _set(b, color=color, rough=rough, ior=ior, transmission=1.0, metallic=0.0)
    return m


def carbon(name, scale=90.0):
    """Плетение карбона: две волновые текстуры крест-накрест через шахматку."""
    m, _, n, l, b = _mk(name)
    _set(b, color=(0.02, 0.02, 0.022, 1), rough=0.22, coat=1.0, coat_rough=0.03)

    tex = n.new("ShaderNodeTexCoord")
    chk = n.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = scale
    chk.inputs["Color1"].default_value = (1, 1, 1, 1)
    chk.inputs["Color2"].default_value = (0, 0, 0, 1)
    l.new(tex.outputs["Object"], chk.inputs["Vector"])

    w1 = n.new("ShaderNodeTexWave")
    w1.bands_direction = "X"
    w2 = n.new("ShaderNodeTexWave")
    w2.bands_direction = "Y"
    for w in (w1, w2):
        w.inputs["Scale"].default_value = scale / 2.0
        w.inputs["Distortion"].default_value = 0.0
        l.new(tex.outputs["Object"], w.inputs["Vector"])

    mix = n.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MIX"
    l.new(chk.outputs["Fac"], mix.inputs["Factor"])
    l.new(w1.outputs["Color"], mix.inputs[6])
    l.new(w2.outputs["Color"], mix.inputs[7])
    _bump(n, l, b, mix.outputs[2], 0.35, 0.0015)

    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.012, 0.012, 0.014, 1)
    ramp.color_ramp.elements[1].color = (0.055, 0.056, 0.060, 1)
    l.new(mix.outputs[2], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def pbr_library(name, folder, mapping=None, scale=1.0):
    """Материал из скачанного PBR-набора (Poly Haven, ambientCG): папка с картами.

    Ищет файлы по подстрокам в имени. Так устроены оба каталога, поэтому
    распаковали архив — и всё подхватилось.
    """
    import os
    mapping = mapping or {"diff": "Base Color", "albedo": "Base Color",
                          "col": "Base Color", "rough": "Roughness",
                          "metal": "Metallic", "nor_gl": "Normal", "normal": "Normal"}
    m, _, n, l, b = _mk(name)
    texco = n.new("ShaderNodeTexCoord")
    mapn = n.new("ShaderNodeMapping")
    mapn.inputs["Scale"].default_value = (scale, scale, scale)
    l.new(texco.outputs["UV"], mapn.inputs["Vector"])

    found = {}
    for f in sorted(os.listdir(folder)):
        low = f.lower()
        for key, socket in mapping.items():
            if key in low and socket not in found:
                tex = n.new("ShaderNodeTexImage")
                tex.image = bpy.data.images.load(os.path.join(folder, f), check_existing=True)
                if socket != "Base Color":
                    tex.image.colorspace_settings.name = "Non-Color"
                l.new(mapn.outputs["Vector"], tex.inputs["Vector"])
                if socket == "Normal":
                    nm = n.new("ShaderNodeNormalMap")
                    l.new(tex.outputs["Color"], nm.inputs["Color"])
                    l.new(nm.outputs["Normal"], b.inputs["Normal"])
                else:
                    l.new(tex.outputs["Color"], b.inputs[socket])
                found[socket] = f
                break
    if not found:
        raise FileNotFoundError(f"в {folder} не нашлось ни одной карты по маскам {list(mapping)}")
    return m


# --- применение -------------------------------------------------------------
def apply_slots(slots, objects, suffix=""):
    """Разложить материалы по объектам сцены.

    * `slots` — {имя слота: функция без аргументов, возвращающая материал};
    * `objects` — {имя слота: [имена объектов]}.

    Возвращает {слот: сколько объектов получили материал} — по этому числу сразу
    видно опечатку в имени: ноль означает, что объект не нашёлся.
    """
    hits = {}
    for slot, factory in slots.items():
        mat = factory()
        mat.name = f"{slot}{suffix}"
        names = objects.get(slot, [])
        count = 0
        for n in names:
            ob = bpy.data.objects.get(n)
            if ob is None or ob.type != "MESH":
                continue
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            for p in ob.data.polygons:
                p.material_index = 0
            count += 1
        hits[slot] = count
    missing = [s for s, c in hits.items() if c == 0]
    if missing:
        print(f"MATERIALS предупреждение: слоты без объектов — {missing}")
    return hits


def apply_set(sets, index, objects):
    """Применить набор №index (1-based, как его видит пользователь на листе).

    `sets` — список словарей: {"title": ..., слот: фабрика, ...}.
    """
    if not 1 <= index <= len(sets):
        raise IndexError(f"набор {index} вне диапазона 1…{len(sets)}")
    spec = sets[index - 1]
    slots = {k: v for k, v in spec.items() if k != "title"}
    apply_slots(slots, objects, suffix=f"_{index}")
    return spec["title"]
