"""Сетка вариантов одним изображением — петля обратной связи всего пайплайна.

На каждой контрольной точке вопрос к вам один и тот же: «какой из этих?».
Поэтому варианты рендерятся не по очереди, а сразу в одну картинку с номерами.
Четыре кадра 360×480 при 64 сэмплах — около девяти секунд, так что смотреть
картинку дешевле, чем рассуждать о ней.

    def apply(res, samples, **kw):
        ...настроить сцену по kw, вернуть подпись...

    variants.grid(apply, [dict(fstop=2.5), dict(fstop=4.0)], "out.png")
"""
import os

import bpy

import mosaic

LABEL = "SheetLabel"


def label_on(text, size=0.05, margin=(0.86, 0.86), depth=2.0):
    """Пришпилить номер к камере — левый верхний угол кадра.

    Номер печатается текстовым объектом внутри сцены, поэтому попадает в тот же
    рендер и не требует ни PIL, ни шрифтов снаружи.

    `margin` и `size` — в долях охвата кадра, а не в метрах: раньше были
    зашиты как метры (0.60, 0.56), и при 85-мм объективе кадр на рабочей
    дистанции оказывался вдвое уже этих чисел — надпись рендерилась ЗА кадром,
    молча, лист вариантов выходил без номеров. Кадр берётся из
    `cam.data.view_frame()` — это то же самое, что использует сам Blender,
    и оно уже учитывает объектив, сдвиг и соотношение сторон. В перспективе
    охват растёт с глубиной линейно, поэтому корни масштабируются на
    `depth / |z камеры кадра|`; в орто от глубины не зависит вовсе.
    """
    cam = bpy.context.scene.camera
    corners = cam.data.view_frame(scene=bpy.context.scene)
    xs, ys = [c.x for c in corners], [c.y for c in corners]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    hw, hh = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
    k = 1.0 if cam.data.type == "ORTHO" else depth / abs(corners[0].z)

    ob = bpy.data.objects.get(LABEL)
    if ob is None:
        cu = bpy.data.curves.new(LABEL, type="FONT")
        ob = bpy.data.objects.new(LABEL, cu)
        bpy.context.collection.objects.link(ob)
        m = bpy.data.materials.new("SheetLabelMat")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (1, 1, 1, 1)
        em.inputs["Strength"].default_value = 2.0
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        ob.data.materials.append(m)
        ob.visible_shadow = ob.visible_diffuse = ob.visible_glossy = False
    ob.data.body = text
    ob.data.size = size * 2 * hh * k
    ob.parent = cam
    ob.parent_type = "OBJECT"
    # Identity, а НЕ cam.matrix_world.inverted(): привычная идиома гасит трансформ
    # родителя, и надпись остаётся в мировых координатах — то есть вне кадра.
    ob.matrix_parent_inverse.identity()
    ob.location = ((cx - margin[0] * hw) * k, (cy + margin[1] * hh) * k, -depth)
    ob.rotation_euler = (0, 0, 0)
    ob.hide_render = False
    return ob


def label_off():
    ob = bpy.data.objects.get(LABEL)
    if ob:
        ob.hide_render = True


def _render_np(path, res, samples):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = samples
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    px = mosaic.load(path)
    os.remove(path)
    return px


def grid(apply_fn, cases, out_path, res=(360, 480), samples=48, cols=2, gap=6,
         label=False):
    """Отрендерить `cases` (список kwargs для apply_fn) и сложить в одну картинку.

    `label=True` печатает номер прямо в кадре — удобно на листе материалов.
    На выверенной композиции надпись мешает, поэтому по умолчанию выключена:
    порядок плиток слева направо, сверху вниз и есть нумерация.

    Возвращает [(номер, что вернул apply_fn)] — по этому списку вы называете номер.
    """
    tmp = os.path.join(os.path.dirname(out_path) or ".", "_var_tmp")
    os.makedirs(tmp, exist_ok=True)
    tiles, info = [], []
    try:
        for i, kw in enumerate(cases):
            info.append((i + 1, apply_fn(res=res, samples=samples, **kw)))
            if label:
                label_on(str(i + 1))
            tiles.append(_render_np(os.path.join(tmp, f"{i:02d}.png"), res, samples))
        if label:
            label_off()
        mosaic.save(mosaic.tile(tiles, cols=cols, gap=gap), out_path)
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    return info
