"""Шаг 3: шесть наборов материалов для наушников.

Набор — это словарь слот → фабрика. Слоты привязаны к именам объектов из
`build.py`. Всё процедурное: скачивать нечего, каждый параметр — число.

Пользователь выбирает набор по номеру с листа вариантов; выбран был третий.
"""
import sys
from os.path import abspath, dirname, join

sys.path.insert(0, join(dirname(dirname(dirname(abspath(__file__)))), "lib"))
import materials  # noqa: E402

# Какие объекты сцены попадают в какой слот.
OBJECTS = {
    "leather": ["BandLeather"],
    "pad": ["PadL", "PadR"],
    "metal": ["BandPlate", "ArmL", "ArmR", "DiscL", "DiscR", "LogoL", "LogoR"],
    "shell": ["CupL", "CupR"],
}

SETS = [
    dict(title="AMG Black — гладкая наппа, полированный алюминий",
         leather=lambda: materials.leather("L", (0.017, 0.017, 0.019, 1),
                                           grain=150, bump=0.22, rough=0.42),
         pad=lambda: materials.leather("P", (0.013, 0.013, 0.015, 1),
                                       grain=260, bump=0.35, rough=0.52),
         metal=lambda: materials.metal("M", (0.86, 0.86, 0.85, 1), rough=0.055),
         shell=lambda: materials.plastic("S", (0.014, 0.014, 0.016, 1),
                                         rough=0.48, micro=0.10)),

    dict(title="Brushed Alu — зернистая кожа, радиальная шлифовка, графит",
         leather=lambda: materials.leather("L", (0.022, 0.022, 0.024, 1),
                                           grain=110, bump=0.45, rough=0.55),
         pad=lambda: materials.leather("P", (0.015, 0.015, 0.017, 1),
                                       grain=220, bump=0.40, rough=0.58),
         metal=lambda: materials.metal("M", (0.66, 0.655, 0.64, 1), rough=0.26,
                                       aniso=0.92, radial=True, axis="Z",
                                       brush_scale=1400),
         shell=lambda: materials.plastic("S", (0.030, 0.031, 0.033, 1),
                                         rough=0.72, micro=0.22)),

    dict(title="Night Chrome — чёрная кожа, тёмный хром, рояльный лак",
         leather=lambda: materials.leather("L", (0.010, 0.010, 0.012, 1),
                                           grain=180, bump=0.26, rough=0.38),
         pad=lambda: materials.leather("P", (0.010, 0.010, 0.012, 1),
                                       grain=240, bump=0.34, rough=0.50),
         metal=lambda: materials.metal("M", (0.20, 0.205, 0.215, 1), rough=0.075),
         shell=lambda: materials.plastic("S", (0.008, 0.008, 0.010, 1),
                                         rough=0.06, coat=1.0)),

    dict(title="Cognac & Brass — коньячная кожа, латунь, шоколадный корпус",
         leather=lambda: materials.leather("L", (0.240, 0.086, 0.028, 1),
                                           grain=120, bump=0.40, rough=0.48),
         pad=lambda: materials.leather("P", (0.170, 0.062, 0.022, 1),
                                       grain=230, bump=0.38, rough=0.54),
         metal=lambda: materials.metal("M", (0.72, 0.53, 0.24, 1), rough=0.20,
                                       aniso=0.6, radial=True, brush_scale=900),
         shell=lambda: materials.plastic("S", (0.045, 0.024, 0.014, 1),
                                         rough=0.42, micro=0.12)),

    dict(title="Maybach White — белая наппа, полированный никель, перламутр",
         leather=lambda: materials.leather("L", (0.760, 0.740, 0.700, 1),
                                           grain=140, bump=0.28, rough=0.40),
         pad=lambda: materials.leather("P", (0.700, 0.680, 0.645, 1),
                                       grain=250, bump=0.34, rough=0.48),
         metal=lambda: materials.metal("M", (0.78, 0.775, 0.755, 1), rough=0.09),
         shell=lambda: materials.plastic("S", (0.560, 0.560, 0.555, 1),
                                         rough=0.22, coat=0.6)),

    dict(title="Carbon & Titanium — карбон, нубук, матовый титан",
         leather=lambda: materials.nubuck("L", (0.055, 0.056, 0.060, 1), rough=0.80),
         pad=lambda: materials.nubuck("P", (0.040, 0.041, 0.045, 1), rough=0.84),
         metal=lambda: materials.metal("M", (0.545, 0.540, 0.525, 1), rough=0.36,
                                       aniso=0.5, radial=True, brush_scale=1100),
         shell=lambda: materials.carbon("S", scale=110)),
]


def apply(index):
    """Применить набор по номеру, как его видит пользователь на листе (с единицы)."""
    return materials.apply_set(SETS, index, OBJECTS)
