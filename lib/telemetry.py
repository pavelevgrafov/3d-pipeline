"""Журнал времени и повторов по стадиям — сколько реально стоил проект.

`GUIDE.md` документирует стоимость шагов один раз, вручную, на одной машине.
По конкретному проекту такой видимости нет: нельзя ответить «сколько мы
потратили» и «сколько раз возвращались на шаг 3» без пересмотра истории чата.

Модуль не решает, что медленно, и не объясняет, почему стадия вызвана
повторно — только пишет факт в `run_log.jsonl` внутри папки проекта. Без
внешних зависимостей: обычный JSON построчно, дописывается, не переписывается.
"""
import contextlib
import json
import os
import time


def _log_path(project_dir):
    return os.path.join(project_dir, "run_log.jsonl")


def record(project_dir, stage, seconds, extra=None):
    """Добавить строку `{ts, stage, seconds, extra}` в `run_log.jsonl`."""
    row = {"ts": time.time(), "stage": stage,
           "seconds": round(seconds, 3), "extra": extra or {}}
    with open(_log_path(project_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


@contextlib.contextmanager
def timed(project_dir, stage, extra=None):
    """`with telemetry.timed(outdir, "final"): ...` — засечь и записать за один вызов.

    Ровно тот же паттерн, который описан в SPEC.md: `time.time()` до/после,
    один вызов `record()` — просто без дублирования в каждом `make.py`.
    """
    t0 = time.time()
    try:
        yield
    finally:
        record(project_dir, stage, time.time() - t0, extra)


def summary(project_dir):
    """Суммарное время и число вызовов по каждой стадии из `run_log.jsonl`.

    Возвращает `{stage: {"seconds": float, "count": int}}`. Число повторов
    стадии — это и есть счётчик возвратов на шаг 3/4: если "looks" вызвана
    трижды, `count` равен трём, и это видно без пересмотра истории чата.

    Отсутствующий или пустой журнал (новый проект ничего ещё не записал)
    даёт пустой словарь, а не падение.
    """
    path = _log_path(project_dir)
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            s = out.setdefault(row["stage"], {"seconds": 0.0, "count": 0})
            s["seconds"] += row["seconds"]
            s["count"] += 1
    for s in out.values():
        s["seconds"] = round(s["seconds"], 3)
    return out
