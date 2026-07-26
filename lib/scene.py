"""Состояние сцены: начать с нуля, сохранить, прибрать.

Мелочь, которая стоит целого перерендера. `blender -b --python скрипт.py`
загружает НЕ пустую сцену, а стартовую: в ней уже лежат куб, лампа и камера.
Куб послушно попадёт в кадр и в габариты, лампа подсветит фон — и вы будете
искать ошибку в свете, которого не ставили.

Поэтому шаг 1 всегда начинается с `scene.reset()`.
"""
import os

import bpy


def reset():
    """Пустая сцена: ни куба, ни лампы, ни камеры из стартового файла."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def save(path):
    """Сохранить .blend. Он не источник истины, а слепок: истина — код."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    return path


def purge():
    """Убрать данные без пользователей: меши и материалы от прошлых итераций.

    Итеративная сборка пересоздаёт объекты, и без уборки файл пухнет от мусора,
    который ни на что не влияет и ни во что не входит.
    """
    removed = 0
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                 bpy.data.curves, bpy.data.lights):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)
                removed += 1
    return removed
