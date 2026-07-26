"""Шаг 4: свет. Примитивы, окружение и проверенные наборы.

Весь свет ставится в системе координат КАМЕРЫ и в долях охвата кадра. Из этого
следуют два свойства, ради которых так и сделано:

* «источник справа от кадра» означает буквально положительный x — при любом
  ракурсе, и световой рисунок не разваливается, когда камеру двигают;
* набор переносится на объект другого размера без перенастройки. Если увеличить
  и размер источника, и дистанцию в одно и то же число раз, телесный угол не
  меняется — а значит, не меняется и освещённость. Поэтому все константы здесь
  выражены в долях `scale` (охват кадра из `frame.fit()`), и яркость трогать
  не нужно.
"""
import math
import os

import bpy
from mathutils import Vector

# Имена служебных объектов: чтобы `clear()` знал, что убирать между итерациями.
RIG = ("KeyStudio", "FillStudio", "RimStudio",
       "KeyStrip", "EdgeStrip", "RimBack", "FillLeft", "TopKick",
       "SoftTop", "SoftLeft", "SoftRight", "Separator",
       "MirrorBoard", "Backdrop")


def clear(names=RIG):
    """Снести предыдущий свет. Без этого итерации накапливают источники."""
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is None:
            continue
        data = ob.data
        bpy.data.objects.remove(ob)
        if isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)


# --- окружение --------------------------------------------------------------
def world_hdri(path, strength=1.0, rotation=0.0):
    """HDRI-окружение: одна картинка даёт и свет, и то, что отражается в металле.

    Основной способ осветить продуктовый кадр. Бесплатные HDRI — Poly Haven
    (CC0). `rotation` в градусах вокруг вертикали: поворот окружения меняет,
    где именно лягут блики, не трогая ничего больше.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"HDRI не найден: {path}")
    w = bpy.data.worlds.get("Env") or bpy.data.worlds.new("Env")
    bpy.context.scene.world = w
    w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputWorld")
    bg = n.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    env = n.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path, check_existing=True)
    texco = n.new("ShaderNodeTexCoord")
    mapn = n.new("ShaderNodeMapping")
    mapn.inputs["Rotation"].default_value = (0, 0, math.radians(rotation))
    l.new(texco.outputs["Generated"], mapn.inputs["Vector"])
    l.new(mapn.outputs["Vector"], env.inputs["Vector"])
    l.new(env.outputs["Color"], bg.inputs["Color"])
    l.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


def world_flat(color=(0.003, 0.003, 0.004), strength=1.0, name="Flat"):
    """Ровный мир. Почти чёрный — когда всё, что отражается, должно быть геометрией."""
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    bpy.context.scene.world = w
    w.use_nodes = True
    n = w.node_tree.nodes
    bg = n.get("Background") or n.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (*color, 1)
    bg.inputs["Strength"].default_value = strength
    return w


def world_gradient(top=(0.58, 0.59, 0.60), bottom=(0.055, 0.055, 0.058),
                   band_color=(3.4, 3.4, 3.45), band_center=0.34, band_width=0.11,
                   strength=1.0):
    """Градиент от тёмного низа к светлому верху плюс яркая полоса-софтбокс.

    Заменяет HDRI, когда качать ничего не хочется. Полоса — это то, что
    отражается в металле продолговатым бликом; без неё металл выглядит мёртвым.
    Отражение считается по вертикальной компоненте луча, поэтому полоса работает
    одинаково с любого ракурса.
    """
    w = bpy.data.worlds.get("Studio") or bpy.data.worlds.new("Studio")
    bpy.context.scene.world = w
    w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    n.clear()

    out = n.new("ShaderNodeOutputWorld")
    bg = n.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    ramp = n.new("ShaderNodeValToRGB")
    texco = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.55
    mr.inputs["From Max"].default_value = 0.55

    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (*bottom, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (*top, 1)
    cr.elements.new(band_center - band_width).color = (*top, 1)
    cr.elements.new(band_center).color = (*band_color, 1)
    cr.elements.new(band_center + band_width).color = (*top, 1)

    l.new(texco.outputs["Generated"], sep.inputs["Vector"])
    l.new(sep.outputs["Z"], mr.inputs["Value"])
    l.new(mr.outputs["Result"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], bg.inputs["Color"])
    l.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


# --- примитивы --------------------------------------------------------------
def _place_in_camera(ob, local, aim=None):
    cam = bpy.context.scene.camera
    ob.location = cam.matrix_world @ Vector(local)
    if aim is not None:
        d = Vector(aim) - ob.location
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = d.to_track_quat("-Z", "Y")


def emitter(name, width, height, strength, color=(1.0, 0.99, 0.97),
            local=None, world=None, aim=None, diffuse=False, visible=False):
    """Светящаяся плоскость: то, что отражается в глянце протяжённым бликом.

    `local` — координаты в системе камеры, `world` — в мировых. Одно из двух.

    `diffuse=False` (по умолчанию) — источник виден только зеркальным лучам.
    Тогда он рисует блик на металле и вообще не подсвечивает фон и матовые
    поверхности. Именно так получается «свет только на кромках, остальное
    в чёрном». Это главный переключатель во всём модуле: с diffuse=True тот же
    набор уводит фон в серый.
    """
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-width / 2, -height / 2, 0), (width / 2, -height / 2, 0),
                    (width / 2, height / 2, 0), (-width / 2, height / 2, 0)],
                   [], [(0, 1, 2, 3)])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)

    if world is not None:
        ob.location = Vector(world)
        if aim is not None:
            d = Vector(aim) - ob.location
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = d.to_track_quat("-Z", "Y")
    elif local is not None:
        _place_in_camera(ob, local, aim)
    else:
        raise ValueError("нужны координаты: local= (система камеры) или world=")

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    ob.data.materials.append(m)

    ob.visible_camera = visible      # сам источник в кадр не попадает
    ob.visible_shadow = False
    ob.visible_diffuse = diffuse
    return ob


def mirror_board(point, normal, size, strength=4.0, distance=1.0, lift=0.0,
                 color=(1.0, 0.99, 0.97), name="MirrorBoard"):
    """Отражатель для плоской полированной детали, стоящий по зеркальному лучу.

    Стоило одного полного цикла отладки, поэтому объясняю. Плоская полированная
    поверхность показывает не источники сбоку, а то, что лежит вдоль ОТРАЖЁННОГО
    луча. При взгляде почти в лоб это пространство ЗА камерой. Пока отражатель
    ставился с обратным знаком (за объект), деталь оставалась чёрным пятном при
    любой яркости боковых источников.

    `point` — центр детали в мире, `normal` — нормаль её лицевой плоскости.
    `lift` уводит отражатель по вертикали: тогда по детали идёт градиент,
    а не ровная серая заливка.
    """
    cam = bpy.context.scene.camera
    p = Vector(point)
    n = Vector(normal).normalized()
    view = (cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))).normalized()
    reflected = (view - 2 * view.dot(n) * n).normalized()
    pos = p + reflected * distance + Vector((0, 0, 1)) * lift
    return emitter(name, size, size * 1.5, strength, color=color, world=pos, aim=p)


def backdrop(scale, shift=(0.0, 0.0), local_z=-2.7071, span=1.6,
             hotspot=(0.80, 0.0), falloff=0.75, peak=1.2,
             base=(0.008, 0.009, 0.011), tint=(0.94, 0.96, 1.0),
             rough=0.34, specular=0.35, name="Backdrop"):
    """Фон: тёмная полуглянцевая плоскость со световым пятном.

    Пятно — эмиссия по сферическому градиенту, а не отдельная лампа: положение
    и спад задаются числами, а не подбором угла.

    Всё привязано к КАДРУ, а не к метрам: `span` — сколько высот кадра занимает
    фон, `hotspot`/`falloff` — доли высоты кадра, так что hotspot=(±0.8, ±0.8)
    это примерно углы кадра. Пока фон был фиксированных 26 единиц при кадре
    в 3.25, «пятно на 0.62» означало восемь единиц вбок — далеко за кадром,
    и в кадр попадал ровный хвост градиента, который принимали за пятно.
    """
    cam = bpy.context.scene.camera
    size = scale * span
    me = bpy.data.meshes.new(name)
    # Плоскость единичная, размер задаётся масштабом объекта: тогда Object-координаты
    # нормированы в ±1, и hotspot/falloff можно задавать в долях кадра.
    me.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.scale = (size / 2, size / 2, 1.0)
    ob.location = cam.matrix_world @ Vector((shift[0] * scale, shift[1] * scale,
                                             local_z * scale))
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = cam.matrix_world.to_quaternion()

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputMaterial")
    mix = n.new("ShaderNodeMixShader")
    bsdf = n.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    # Тёмный фон полуглянцевый — на нём видно отражение пятна. Светлому нужен
    # матовый: на глянцевом светлом фоне источники отражаются вторым набором
    # пятен, и «чистый разворот» превращается в кашу из блёсток.
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = specular
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*tint, 1)
    em.inputs["Strength"].default_value = peak

    texco = n.new("ShaderNodeTexCoord")
    mapn = n.new("ShaderNodeMapping")
    # Mapping считает location + scale·vector, то есть Location применяется ПОСЛЕ
    # Scale. Чтобы центр пятна встал ровно в hotspot, сдвиг делим на falloff —
    # иначе пятно уезжает к центру тем сильнее, чем уже спад.
    mapn.inputs["Location"].default_value = (-hotspot[0] / falloff, -hotspot[1] / falloff, 0)
    mapn.inputs["Scale"].default_value = (1 / falloff, 1 / falloff, 1.0)
    grad = n.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    ramp = n.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    cr.elements[0].position, cr.elements[0].color = 0.02, (0, 0, 0, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (1, 1, 1, 1)

    l.new(texco.outputs["Object"], mapn.inputs["Vector"])
    l.new(mapn.outputs["Vector"], grad.inputs["Vector"])
    l.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], mix.inputs["Fac"])
    l.new(bsdf.outputs["BSDF"], mix.inputs[1])
    l.new(em.outputs["Emission"], mix.inputs[2])
    l.new(mix.outputs["Shader"], out.inputs["Surface"])
    ob.data.materials.append(m)
    return ob


# --- готовые наборы ---------------------------------------------------------
def three_point(target=(0, 0, 0), distance=6.0, warm=(1.0, 0.93, 0.85),
                cool=(0.85, 0.90, 1.0), key=320.0, fill=70.0, rim=420.0):
    """Нейтральные три точки для СРАВНЕНИЯ материалов, а не для финального кадра.

    Ставится относительно текущей камеры, поэтому рисунок сохраняется при смене
    ракурса. Используется на шаге 3: без окружения металлу нечего отражать,
    и любой набор материалов выглядит одинаково мёртвым.
    """
    cam = bpy.context.scene.camera
    d = cam.location - Vector(target)
    az = math.degrees(math.atan2(d.x, -d.y))
    clear(("KeyStudio", "FillStudio", "RimStudio"))
    spec = (("KeyStudio", az + 42, 34, key, warm, 4.5),
            ("FillStudio", az - 68, 6, fill, cool, 6.0),
            ("RimStudio", az + 168, 22, rim, (1, 1, 1), 3.0))
    made = []
    for name, a, e, energy, color, size in spec:
        li = bpy.data.lights.new(name, "AREA")
        li.energy, li.size, li.color = energy, size, color
        ob = bpy.data.objects.new(name, li)
        bpy.context.collection.objects.link(ob)
        ar, er = math.radians(a), math.radians(e)
        ob.location = Vector(target) + Vector((
            distance * math.cos(er) * math.sin(ar),
            -distance * math.cos(er) * math.cos(ar),
            distance * math.sin(er),
        ))
        c = ob.constraints.new("TRACK_TO")
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        c.target = bpy.data.objects.get("CamTarget") or bpy.data.objects.get("FocusPoint")
        made.append(name)
    return made


# Константы набора `editorial_dark`. Это не «набор вообще», а числа снятые
# с доведённого до конца кадра и поделённые на его охват — поэтому набор,
# выверенный на предмете в пару единиц, работает и на восьми. Формат:
# (ширина, высота, x, y, z, сила, цвет, виден ли диффузному лучу).
# Длины — в долях `scale`.
_EDITORIAL = (
    # Длинная узкая полоса справа: протяжённый блик вдоль всей боковой кромки.
    ("KeyStrip",  0.1654, 2.5567,  0.8272,  0.1654, -1.6241, 16.0, (1.00, 0.99, 0.97), False),
    # Короче и ближе: подсвечивает кромки и фаски.
    ("EdgeStrip", 0.0782, 0.9024,  0.4662,  0.4061, -1.2934, 34.0, (0.92, 0.95, 1.00), False),
    # Контровой из-за объекта: отделяет силуэт от фона.
    ("RimBack",   0.7820, 1.2032,  0.9324,  0.2707, -2.5868,  9.0, (0.88, 0.92, 1.00), False),
    # Верхний штрих. Самый склонный к пережогу, поэтому слабый: при силе 40
    # верхняя кромка выжигалась в сплошную белую дугу и забирала весь кадр.
    ("TopKick",   0.1023, 1.2032,  0.1053,  0.7369, -1.7745,  8.0, (1.00, 0.98, 0.95), False),
    # Слева почти ничего — ровно чтобы левый край не исчез в ноль. Единственный,
    # кому разрешено светить по-настоящему; именно он раньше подсвечивал фон,
    # ломая «тёмное слева, свет справа».
    ("FillLeft",  0.5414, 0.9024, -0.9024, -0.1053, -1.4438,  0.4, (0.72, 0.80, 1.00), True),
)


def editorial_dark(scale, aim, gain=1.0, fill_left=0.4, backdrop_peak=1.2,
                   hotspot=(0.80, 0.0), falloff=0.75, span=1.6,
                   mirror=None, shift=None):
    """Рекламный тёмный набор: чёрный фон, световое пятно, узкие жёсткие блики.

    Это проверенный набор из готового кадра, а не «набор вообще»: он рассчитан
    на глянцевый предмет на тёмном фоне (техника, часы, флакон, бутылка).
    Для матового предмета или светлого фона берите `editorial_light` — здесь
    просто нечему бликовать.

    * `scale` — охват кадра, который вернул `frame.fit()`;
    * `aim` — точка, в которую целятся источники (обычно `frame.center()`);
    * `gain` — общая яркость набора одним числом;
    * `mirror` — `dict(point=..., normal=..., size=..., distance=..., lift=...)`
      в долях scale, если в кадре есть плоская полированная деталь.
    """
    cam = bpy.context.scene.camera
    clear()
    world_flat()
    # Фон центрируется по КАДРУ, а не по камере: после `frame.fit()` кадр сдвинут
    # относительно оси камеры, и без учёта сдвига световое пятно уезжает.
    if shift is None:
        shift = (cam.data.shift_x, cam.data.shift_y)
    backdrop(scale, shift=shift, span=span, peak=backdrop_peak,
             hotspot=hotspot, falloff=falloff)

    made = []
    for name, w, h, x, y, z, strength, color, diffuse in _EDITORIAL:
        s = fill_left if name == "FillLeft" else strength
        made.append(emitter(name, w * scale, h * scale, s * gain, color=color,
                            local=(x * scale, y * scale, z * scale), aim=aim,
                            diffuse=diffuse).name)

    if mirror:
        made.append(mirror_board(
            mirror["point"], mirror.get("normal", (0, 0, 1)),
            size=mirror.get("size", 0.6617) * scale,
            strength=mirror.get("strength", 4.0) * gain,
            distance=mirror.get("distance", 0.9625) * scale,
            lift=mirror.get("lift", 0.3309) * scale).name)
    return made


# Константы набора `editorial_light`. Формат тот же, что у `_EDITORIAL`, и длины
# так же в долях `scale` — но `diffuse` почти везде True, и это не деталь,
# а весь смысл набора: матовая поверхность НЕ отражает источник, она им
# освещается. Набор из зеркально-видимых полос на матовом предмете даёт ровно
# ничего, поэтому `editorial_dark` там и проваливается.
_EDITORIAL_LIGHT = (
    # Ключевой: большой софтбокс сверху и чуть слева. Широкий намеренно —
    # мягкая растянутая тень под предметом и плавный переход по объёму.
    ("SoftTop",   1.8000, 1.2000, -0.2500,  1.1500, -1.0500,  2.10, (1.00, 0.99, 0.97), True),
    # Справа — вторая по силе панель: она и есть «сторона, с которой светят».
    ("SoftRight", 1.5000, 1.5000,  1.1500,  0.1000, -1.3500,  1.05, (0.98, 0.99, 1.00), True),
    # Слева впятеро слабее ключевого, и это не «почти выключено», а весь объём:
    # на светлом предмете форму держит ТОЛЬКО разница между гранями. Сравняете
    # с правой — получите ровную заливку без формы, главный способ испортить
    # светлый кадр (проверено сеткой: при равных панелях грани неразличимы).
    ("SoftLeft",  1.5000, 1.5000, -1.2000, -0.1000, -1.3500,  0.42, (0.97, 0.98, 1.00), True),
    # Узкая полоса только для зеркальных лучей: на светлом предмете с глянцевыми
    # деталями (шильдик, кольцо, стекло) без неё блики пропадают совсем.
    ("EdgeStrip", 0.0800, 1.0000,  0.5000,  0.4200, -1.2500,  9.00, (1.00, 0.99, 0.97), False),
    # Отделение силуэта от светлого фона. На тёмном фоне это делает яркий
    # контровой, здесь наоборот: фон и так светлее предмета, и хватает лёгкого
    # подсвета сзади, чтобы кромка не слилась в одно пятно с фоном.
    ("Separator", 0.9000, 0.9000, -0.7000,  0.5500, -2.3000,  1.00, (1.00, 0.98, 0.95), True),
)


def editorial_light(scale, aim, gain=1.0, backdrop_peak=0.70,
                    hotspot=(0.0, 0.05), falloff=1.00, span=2.2,
                    backdrop_base=(0.38, 0.38, 0.39), backdrop_rough=0.62,
                    ambient=(0.09, 0.09, 0.10), ambient_strength=1.0,
                    mirror=None, shift=None):
    """Светлый рекламный набор: чистый светлый разворот, мягкий объём, тени.

    Второй проверенный набор и прямая противоположность `editorial_dark`.
    Тот показывает предмет узкими бликами по кромкам — и работает только
    на тёмном глянце. Этот показывает предмет ТОНОМ: светлый фон, широкие
    источники, видимые полутени. Для матового и/или светлого предмета —
    кожа, нубук, светлый пластик, керамика, бумага, ткань.

    Ключевое отличие в коде — `diffuse=True` у больших источников
    и `world_flat` со светлой заливкой вместо почти чёрной.

    * `scale` — охват кадра, который вернул `frame.fit()`;
    * `aim` — точка, в которую целятся источники (обычно `frame.center()`);
    * `gain` — общая яркость набора одним числом;
    * `backdrop_base` — светлота фона. 0.55 — светло-серый; выше 0.75 фон
      уходит в белое и силуэт начинает исчезать по кромкам;
    * `ambient` — заливка мира. Она поднимает донья теней; в ноль
      не ставить, иначе низ предмета провалится в чёрный на светлом фоне;
    * `mirror` — как в `editorial_dark`, если в кадре плоская полировка.
    """
    cam = bpy.context.scene.camera
    clear()
    world_flat(color=ambient, strength=ambient_strength, name="Soft")
    if shift is None:
        shift = (cam.data.shift_x, cam.data.shift_y)
    backdrop(scale, shift=shift, span=span, peak=backdrop_peak,
             hotspot=hotspot, falloff=falloff, base=backdrop_base,
             tint=(1.0, 1.0, 1.0), rough=backdrop_rough, specular=0.20)

    made = []
    for name, w, h, x, y, z, strength, color, diffuse in _EDITORIAL_LIGHT:
        made.append(emitter(name, w * scale, h * scale, strength * gain, color=color,
                            local=(x * scale, y * scale, z * scale), aim=aim,
                            diffuse=diffuse).name)

    if mirror:
        made.append(mirror_board(
            mirror["point"], mirror.get("normal", (0, 0, 1)),
            size=mirror.get("size", 0.6617) * scale,
            strength=mirror.get("strength", 2.0) * gain,
            distance=mirror.get("distance", 0.9625) * scale,
            lift=mirror.get("lift", 0.3309) * scale).name)
    return made
