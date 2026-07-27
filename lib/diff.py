"""Грубый перцептивный дифф двух PNG — гейт «что-то заметно сдвинулось».

Возврат на шаг 3 или 4 может незаметно сдвинуть то, что уже было утверждено
раньше (материал, кадр) — без этого модуля такое ловится только глазом,
если вообще ловится. Это не perceptual-loss в строгом смысле — никакой модели
восприятия здесь нет, — а дешёвая, грубая мера «картинка примерно та же» или
«что-то заметно изменилось», достаточная как сигнал вернуться и посмотреть.

Используется вместе с `lib/mosaic.py:side_by_side` и конвенцией именования
`<stage>.approved.png`: см. `GUIDE.md` и `template/README.md`.
"""
import numpy as np

import mosaic


def _downsample(arr, grid):
    """Усреднить RGB (без альфы) по ячейкам сетки `grid` = (строки, столбцы).

    `np.array_split` допускает неровное деление — картинка любого разрешения
    сжимается к одной и той же сетке, поэтому `path_a`/`path_b` не обязаны
    быть одного размера.
    """
    gh, gw = grid
    out = np.empty((gh, gw, 3), dtype=np.float32)
    for i, row in enumerate(np.array_split(arr, gh, axis=0)):
        for j, cell in enumerate(np.array_split(row, gw, axis=1)):
            out[i, j] = cell[..., :3].reshape(-1, 3).mean(axis=0)
    return out


def perceptual_diff(path_a, path_b, grid=(16, 16)):
    """Даунсемплинг обоих PNG до `grid` усреднением по ячейке, затем разница.

    Возвращает `{"max": ..., "mean": ...}` — обе величины в диапазоне 0..1
    (разница компонент цвета, не проценты). `perceptual_diff(x, x)` всегда
    даёт нули. Дешёвый и грубый: локальный, но мелкий дефект (скол, пятно)
    может утонуть в усреднении по крупной ячейке, а общий сдвиг экспозиции —
    наоборот, дать заметное число, хотя глаз его не считает регрессией.
    """
    a = _downsample(mosaic.load(path_a), grid)
    b = _downsample(mosaic.load(path_b), grid)
    delta = np.abs(a - b)
    return {"max": float(delta.max()), "mean": float(delta.mean())}
