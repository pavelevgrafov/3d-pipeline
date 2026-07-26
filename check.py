#!/usr/bin/env python3
"""Проверка репозитория целиком: синтаксис, сквозной прогон в Blender, артефакты.

Запускать после любой правки библиотеки — и обязательно перед тем, как считать
пайплайн рабочим:

    python3 check.py

Что делает:

1. компилирует все .py — ловит опечатки, не запуская Blender;
2. гоняет `tests/smoke.py` внутри Blender: все шесть шагов на тестовой сцене,
   которая намеренно не похожа на заготовку ни формой, ни масштабом;
3. проверяет, что артефакты действительно на диске и не пустые;
4. отдельно читает получившийся EXR ЧИСТЫМ python — без bpy. Это не формальность:
   именно так видно, что в файле настоящие пассы, а не один слой RGBA, который
   Blender умеет записать молча;
5. гоняет заготовку на дешёвой стадии. Библиотеку она использует иначе,
   чем тест: перспективная камера против орто, свои имена объектов.
   Без этого шага заготовка ломается молча — а именно её копирует новый человек.

Код возврата 0 — всё прошло.
"""
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "lib"))

# Минимальный набор пассов, ради которых EXR вообще нужен: без них шаг 6
# и передача в другую программу теряют смысл. Имена — как они лежат в файле:
# с префиксом слоя и без сокращений ("Ambient Occlusion", не "AO").
NEED_PASSES = ("Combined", "Depth", "Normal", "Mist", "Ambient Occlusion",
               "CryptoObject", "CryptoMaterial")


# Проекты, которые обязаны собираться. Стадия `preview` выбрана намеренно:
# она проходит все шаги (форма, ракурс, материалы, кадр, свет, рендер), но
# в дешёвом разрешении и без пассов — секунды вместо минуты.
PROJECTS = (("заготовка", os.path.join("template", "make.py")),)


def blender_bin():
    return os.environ.get("BLENDER") or shutil.which("blender") or "blender"


def step(title):
    print(f"\n=== {title} " + "=" * max(0, 62 - len(title)))


def compile_all():
    step("1/5 синтаксис")
    bad = []
    # Байт-код складываем во временную папку: репозиторий должен оставаться чистым.
    with tempfile.TemporaryDirectory(prefix="3dp-pyc-") as cache:
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "_smoke"}]
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                path = os.path.join(base, f)
                rel = os.path.relpath(path, ROOT)
                cfile = os.path.join(cache, rel.replace(os.sep, "_") + "c")
                try:
                    py_compile.compile(path, doraise=True, cfile=cfile)
                    print(f"  ok   {rel}")
                except py_compile.PyCompileError as exc:
                    bad.append((path, exc))
                    print(f"  FAIL {rel}: {exc}")
    return not bad


def run_smoke(outdir):
    step("2/5 сквозной прогон в Blender")
    cmd = [blender_bin(), "-b", "--factory-startup",
           "--python", os.path.join(ROOT, "tests", "smoke.py"), "--", outdir]
    print("  " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    lines = [ln for ln in proc.stdout.splitlines()
             if ln.startswith(("CHECK ", "SMOKE ", "MATERIALS "))]
    for ln in lines:
        print("  " + ln)
    # Именно "SMOKE PASS"/"SMOKE FAIL": строк с префиксом SMOKE в выводе несколько,
    # и первая из них — просто список объектов сцены.
    verdict = next((ln for ln in lines
                    if ln.startswith(("SMOKE PASS", "SMOKE FAIL"))), "")
    if not verdict.startswith("SMOKE PASS"):
        print("\n--- stderr (последние 40 строк) ---")
        print("\n".join(proc.stderr.splitlines()[-40:]))
        if not verdict:
            print("\n--- stdout (последние 40 строк) ---")
            print("\n".join(proc.stdout.splitlines()[-40:]))
        return False
    return True


def check_artifacts(outdir):
    step("3/5 артефакты на диске")
    expect = ["sheet.png", "variants.png", "preview.png",
              "hero.png", "hero.exr", "hero_graded.png"]
    ok = True
    for name in expect:
        path = os.path.join(outdir, name)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        good = size > 0
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} {name:20s} {size:>10,} байт")
    return ok


def check_exr(outdir):
    step("4/5 пассы в EXR, прочитанные без Blender")
    import exr_info
    path = os.path.join(outdir, "hero.exr")
    if not os.path.exists(path):
        print("  FAIL EXR не создан")
        return False
    print("  " + exr_info.report(path).replace("\n", "\n  "))
    names = " ".join(n for n, _ in exr_info.passes(path)).lower()
    missing = [p for p in NEED_PASSES if p.lower() not in names]
    if missing:
        print(f"  FAIL не хватает пассов: {missing}")
        return False
    print(f"  ok   все обязательные пассы на месте: {', '.join(NEED_PASSES)}")
    return True


def check_projects(outdir):
    step("5/5 заготовка собирается")
    ok = True
    for title, rel in PROJECTS:
        script = os.path.join(ROOT, rel)
        dest = os.path.join(outdir, os.path.basename(os.path.dirname(rel)))
        cmd = [blender_bin(), "-b", "--factory-startup",
               "--python", script, "--", dest, "preview"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        png = os.path.join(dest, "preview.png")
        size = os.path.getsize(png) if os.path.exists(png) else 0
        good = proc.returncode == 0 and size > 0
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} {title:12s} {rel:34s} {size:>10,} байт")
        if not good:
            for ln in proc.stdout.splitlines()[-15:]:
                print("      " + ln)
            print("\n".join("      " + ln for ln in proc.stderr.splitlines()[-15:]))
    return ok


def main():
    keep = "--keep" in sys.argv
    outdir = os.path.join(ROOT, "_smoke") if keep else tempfile.mkdtemp(prefix="3dp-check-")
    os.makedirs(outdir, exist_ok=True)
    try:
        results = [("синтаксис", compile_all())]
        if results[-1][1]:
            results.append(("прогон", run_smoke(outdir)))
            if results[-1][1]:
                results.append(("артефакты", check_artifacts(outdir)))
                results.append(("EXR", check_exr(outdir)))
                results.append(("проекты", check_projects(outdir)))

        step("итог")
        for name, good in results:
            print(f"  {'PASS' if good else 'FAIL'}  {name}")
        failed = [n for n, good in results if not good]
        done = len(results) == 5
        if failed or not done:
            print(f"\nПРОВЕРКА НЕ ПРОЙДЕНА: {failed or 'прогон оборвался'}")
            return 1
        print(f"\nВСЁ ПРОЙДЕНО. Артефакты: {outdir}")
        return 0
    finally:
        if not keep and os.path.isdir(outdir):
            shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
