"""Шаг 5: финальный рендер — PNG плюс multilayer EXR с пассами.

PNG — это картинка «как есть», уже через AgX. EXR — 32 бита, линейный, со всеми
пассами: глубина, нормали, cryptomatte. Он и есть ответ на вопрос «можно ли
отдать это в другую программу»: EXR с пассами читают DaVinci, Fusion, Nuke,
Affinity, Krita.

Один рендер — два файла: PNG собирается из уже посчитанного результата,
второй раз считать не нужно.
"""
import os

import bpy

import frame

# Пассы, из которых потом собирается пост без перерендера.
PASSES = ("use_pass_z", "use_pass_normal", "use_pass_mist",
          "use_pass_ambient_occlusion", "use_pass_diffuse_color",
          "use_pass_glossy_direct")


def setup(samples=320, look="AgX - High Contrast", exposure=0.0,
          denoise=True, engine="CYCLES", transparent=False):
    """Движок и цвет. Отскоки подняты под стекло и многослойный глянец."""
    sc = bpy.context.scene
    sc.render.engine = engine
    if engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.use_denoising = denoise
        sc.cycles.max_bounces = 16
        sc.cycles.glossy_bounces = 8
        sc.cycles.transparent_max_bounces = 12
    sc.view_settings.view_transform = "AgX"
    # Имена строгие: есть "AgX - Base Contrast" и "AgX - High Contrast",
    # а "AgX - Medium Contrast" не существует и падает с enum not found.
    sc.view_settings.look = look
    sc.view_settings.exposure = exposure
    sc.render.film_transparent = transparent
    return {"engine": engine, "samples": samples, "look": look}


def enable_passes(cryptomatte=True, mist=True, exclude=()):
    """Включить пассы и настроить диапазон Mist по реальной глубине объекта.

    Mist меряется от камеры, и диапазон по умолчанию почти всегда мимо: пасс
    выходит либо весь белый, либо весь чёрный. Здесь границы берутся из
    габаритов сцены, так что пасс осмысленный без ручной настройки.
    """
    vl = bpy.context.view_layer
    for p in PASSES:
        setattr(vl, p, True)
    if cryptomatte:
        vl.use_pass_cryptomatte_object = True
        vl.use_pass_cryptomatte_material = True
        vl.pass_cryptomatte_depth = 6

    info = {}
    if mist:
        _, _, (z0, z1) = frame.extent(exclude)
        ms = bpy.context.scene.world.mist_settings
        ms.start = max(abs(z1) - 0.3, 0.0)
        ms.depth = (abs(z0) - abs(z1)) + 1.2
        ms.falloff = "LINEAR"
        info = {"mist_start": round(ms.start, 3), "mist_depth": round(ms.depth, 3)}
    return info


def save(stem):
    """Один рендер — два файла: `stem.exr` (все пассы) и `stem.png`.

    Две грабли Blender 5, обе проверены по содержимому файла:

    * EXR пишется штатной записью рендера (`write_still=True`), а НЕ
      `save_render`: последний отдаёт только собранный кадр, и файл выходит
      однослойным RGBA — без пассов, ради которых он и нужен.
    * У формата появился `media_type`, и `OPEN_EXR_MULTILAYER` виден только при
      `MULTI_LAYER_IMAGE`. Пока он `IMAGE`, присваивание падает с «enum not
      found», а обычный `OPEN_EXR` молча пишет один слой.
    """
    sc = bpy.context.scene
    os.makedirs(os.path.dirname(os.path.abspath(stem)), exist_ok=True)
    ims = sc.render.image_settings
    ims.media_type = "MULTI_LAYER_IMAGE"
    ims.file_format = "OPEN_EXR_MULTILAYER"
    ims.color_depth = "32"
    ims.exr_codec = "ZIP"
    sc.render.filepath = stem              # расширение Blender добавит сам
    sc.render.use_file_extension = True
    bpy.ops.render.render(write_still=True)

    rr = bpy.data.images["Render Result"]
    ims.media_type = "IMAGE"
    ims.file_format = "PNG"
    ims.color_mode = "RGB"
    ims.color_depth = "16"
    rr.save_render(stem + ".png", scene=sc)
    return [stem + ".exr", stem + ".png"]


def preview(path, res=(540, 720), samples=64, engine="CYCLES"):
    """Быстрый одиночный кадр для промежуточного взгляда. Только PNG."""
    sc = bpy.context.scene
    prev = (sc.render.engine, sc.render.resolution_x, sc.render.resolution_y)
    sc.render.engine = engine
    sc.render.resolution_x, sc.render.resolution_y = res
    if engine == "CYCLES":
        sc.cycles.samples = samples
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    sc.render.engine, sc.render.resolution_x, sc.render.resolution_y = prev
    return path
