"""Склейка нескольких рендеров в одну картинку.

Вся петля обратной связи в этом пайплайне держится на одном приёме: сравнивать
варианты не по очереди, а рядом, в одном изображении. Смотреть на четыре плитки
дешевле, чем открывать четыре файла и держать разницу в голове.

Читает и пишет через `bpy.data.images` — сторонних библиотек вроде PIL не нужно,
внутри Blender их обычно и нет.
"""
import math
import os

import bpy
import numpy as np


def load(path):
    """PNG → массив (высота, ширина, 4), строки сверху вниз.

    Blender хранит пиксели снизу вверх, поэтому массив переворачивается здесь
    один раз, а не в каждом вызывающем модуле.
    """
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    return px[::-1]


def save(array, path):
    """Массив (высота, ширина, 4) → PNG."""
    h, w, _ = array.shape
    out = bpy.data.images.new("mosaic", w, h, alpha=True)
    out.pixels = array[::-1].ravel().tolist()
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    return path


def tile(arrays, cols=3, gap=6, bg=0.09):
    """Разложить плитки в сетку слева направо, сверху вниз.

    Плитки должны быть одного размера — они и приходят из одного рендера
    с одним разрешением.
    """
    if not arrays:
        raise ValueError("нечего складывать: пустой список плиток")
    h, w, _ = arrays[0].shape
    rows = math.ceil(len(arrays) / cols)
    canvas = np.zeros((rows * h + (rows - 1) * gap, cols * w + (cols - 1) * gap, 4),
                      dtype=np.float32)
    canvas[..., :3] = bg
    canvas[..., 3] = 1.0
    for i, t in enumerate(arrays):
        if t.shape != arrays[0].shape:
            raise ValueError(f"плитка {i} другого размера: {t.shape} против {arrays[0].shape}")
        r, c = divmod(i, cols)
        y, x = r * (h + gap), c * (w + gap)
        canvas[y:y + h, x:x + w] = t
    return canvas


def from_files(paths, out_path, cols=3, gap=6, bg=0.09, cleanup=False):
    """Склеить готовые PNG-файлы в сетку."""
    sheet = tile([load(p) for p in paths], cols=cols, gap=gap, bg=bg)
    save(sheet, out_path)
    if cleanup:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
    return out_path
