"""ШАГ 3 — материалы. Наборы, между которыми вы выбираете по номеру.

Набор — это словарь слот → фабрика материала. Слот привязан к именам объектов
из `build.py` через `OBJECTS`.

Правило про количество: делайте 4–6 наборов, не два и не двадцать. Меньше
четырёх — не из чего выбирать, больше шести — лист перестаёт читаться, и выбор
превращается в лотерею.
"""
import sys
from os.path import abspath, dirname, join

sys.path.insert(0, join(dirname(dirname(abspath(__file__))), "lib"))
import materials  # noqa: E402

# Какие объекты сцены попадают в какой слот. Имена — из build.py.
OBJECTS = {
    "shell": ["Body"],
    "face": ["Face"],
    "trim": ["Ring"],
}

SETS = [
    dict(title="Графит и сталь — матовый корпус, полированная сталь",
         shell=lambda: materials.plastic("shell", (0.030, 0.031, 0.033, 1),
                                         rough=0.62, micro=0.18),
         face=lambda: materials.metal("face", (0.82, 0.82, 0.81, 1), rough=0.06),
         trim=lambda: materials.metal("trim", (0.60, 0.60, 0.59, 1), rough=0.28,
                                      aniso=0.8, radial=True, brush_scale=1200)),

    dict(title="Рояльный лак и никель — глянец, холодный металл",
         shell=lambda: materials.plastic("shell", (0.008, 0.008, 0.010, 1),
                                         rough=0.06, coat=1.0),
         face=lambda: materials.metal("face", (0.78, 0.775, 0.755, 1), rough=0.09),
         trim=lambda: materials.metal("trim", (0.22, 0.225, 0.235, 1), rough=0.10)),

    dict(title="Кожа и латунь — тёплый, дорогой, ретро",
         shell=lambda: materials.leather("shell", (0.240, 0.086, 0.028, 1),
                                         grain=120, bump=0.40, rough=0.48),
         face=lambda: materials.metal("face", (0.72, 0.53, 0.24, 1), rough=0.18,
                                      aniso=0.6, radial=True, brush_scale=900),
         trim=lambda: materials.metal("trim", (0.62, 0.45, 0.20, 1), rough=0.30)),

    dict(title="Карбон и титан — техничный, матовый, тёмный",
         shell=lambda: materials.carbon("shell", scale=110),
         face=lambda: materials.metal("face", (0.545, 0.540, 0.525, 1), rough=0.34,
                                      aniso=0.5, radial=True, brush_scale=1100),
         trim=lambda: materials.nubuck("trim", (0.045, 0.046, 0.050, 1), rough=0.82)),
]


def apply(index):
    """Применить набор по номеру, как вы видите его на листе (нумерация с единицы)."""
    return materials.apply_set(SETS, index, OBJECTS)
