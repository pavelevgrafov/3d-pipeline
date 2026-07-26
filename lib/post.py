"""Шаг 6: пост в компоузере Blender — блум по бликам, кривая, виньетка.

Работает по готовому EXR, а не по сцене, поэтому перерендер не нужен: правка
грейда стоит секунду, а не минуту, и крутить её можно сколько угодно раз.

    blender -b --python lib/post.py -- in.exr out.png vignette=0.3 strength=0.7

Про API Blender 5: компоузер переехал со `scene.node_tree` на отдельную
node-группу `scene.compositing_node_group`, выходной ноды `Composite` больше
нет — результат уходит в `NodeGroupOutput`, а параметры `Glare` из свойств ноды
стали входными сокетами.
"""
import os
import sys

import bpy

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import exr_info  # noqa: E402


def build(exr_path, strength=0.5, threshold=0.75, size=7, vignette=0.22,
          contrast=0.02):
    """Собрать дерево компоузера. Грейд намеренно слабый.

    Кадр, построенный по этому пайплайну, уже держится на естественном спаде
    света. Сильная виньетка (0.55) вместе с контрастом 0.04 съедала дальний край
    объекта целиком: туда, где свет и так падает к нулю, пост добавить нечего.
    Финальные значения втрое слабее первой попытки.
    """
    sc = bpy.context.scene
    ng = bpy.data.node_groups.new("Post", "CompositorNodeTree")
    sc.compositing_node_group = ng
    n, l = ng.nodes, ng.links

    img = n.new("CompositorNodeImage")
    img.image = bpy.data.images.load(exr_path)
    # У multilayer-EXR нода раскрывается в сокеты по числу пассов, и обычного
    # выхода "Image" у неё уже нет — собранный кадр лежит в "Combined".
    src = img.outputs.get("Combined") or img.outputs["Image"]

    glare = n.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Streaks"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = threshold
    glare.inputs["Strength"].default_value = strength
    glare.inputs["Size"].default_value = size
    glare.inputs["Streaks"].default_value = 4
    glare.inputs["Fade"].default_value = 0.86
    l.new(src, glare.inputs["Image"])

    curve = n.new("CompositorNodeCurveRGB")
    c = curve.mapping.curves[3]          # композитная кривая RGB
    c.points[0].location = (0.0 + contrast, 0.0)
    c.points[1].location = (1.0 - contrast * 0.5, 1.0)
    curve.mapping.update()
    l.new(glare.outputs["Image"], curve.inputs["Image"])

    last = curve.outputs["Image"]
    if vignette:
        # Маска-эллипс шире кадра и сильно размытая: края уходят в чёрный мягко,
        # без видимого овала.
        mask = n.new("CompositorNodeEllipseMask")
        mask.inputs["Size"].default_value = (0.78, 0.78)
        mask.inputs["Position"].default_value = (0.5, 0.5)
        blur = n.new("CompositorNodeBlur")
        blur.inputs["Size"].default_value = (220, 220)   # сокет двумерный, в пикселях
        l.new(mask.outputs["Mask"], blur.inputs["Image"])

        # Factor=1 внутри маски отдаёт исходник, снаружи — чёрный. Глубину
        # виньетки задаём подмешиванием исходника обратно.
        dark = n.new("ShaderNodeMix")
        dark.data_type = "RGBA"
        black = n.new("CompositorNodeRGB")
        black.outputs["Color"].default_value = (0, 0, 0, 1)
        l.new(blur.outputs["Image"], dark.inputs["Factor"])
        l.new(black.outputs["Color"], dark.inputs[6])
        l.new(last, dark.inputs[7])

        blend = n.new("ShaderNodeMix")
        blend.data_type = "RGBA"
        blend.inputs["Factor"].default_value = vignette
        l.new(last, blend.inputs[6])
        l.new(dark.outputs[2], blend.inputs[7])
        last = blend.outputs[2]

    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    out = n.new("NodeGroupOutput")
    l.new(last, out.inputs[0])
    return img.image


def run(src, dst, look="AgX - High Contrast", **kw):
    """Пустая сцена + компоузер: считать нечего, вся работа по готовому EXR."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    cam = bpy.data.objects.new("C", bpy.data.cameras.new("C"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.render.use_compositing = True
    sc.render.use_sequencer = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = look

    build(src, **kw)
    # Размер берём из заголовка EXR: bpy грузит файл лениво, и до первого
    # обращения к пикселям image.size равен (0, 0) — кадр вышел бы 0×0.
    sc.render.resolution_x, sc.render.resolution_y = exr_info.size(src)
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "16"
    sc.render.filepath = dst
    bpy.ops.render.render(write_still=True)
    return dst


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        raise SystemExit("blender -b --python lib/post.py -- in.exr out.png [ключ=число]")
    # Остальные аргументы — «ключ=значение», чтобы крутить грейд без правки файла.
    kwargs = {k: float(v) for k, v in (a.split("=", 1) for a in argv[2:])}
    path = run(argv[0], argv[1], **kwargs)
    print("POST", path, os.path.getsize(path), exr_info.size(argv[0]))
