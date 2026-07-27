# 3d-pipeline

**Version 1.2**

A Blender pipeline for advertising product renders **from a description and
references** — no manual work in the editor UI.

You describe the object in words and show references. At every step you're
shown **one image with several variants**, and you just name a number or say
what's wrong. Everything else — geometry, materials, lighting, composition,
rendering, color grading — is done by the code.

The library is subject-agnostic: composition and lighting are computed from
the object's measured bounding box, not eyeballed to fit a specific shape.

## Requirements

| | |
|---|---|
| Blender | 5.x (tested on 5.2.0 LTS). On `PATH` or in `$BLENDER` |
| Python | 3.11+ for `check.py`; everything else runs inside Blender |
| GPU | not required, but the final render is much slower on CPU |

A live, open Blender is needed in exactly one place — grabbing an angle from
the viewport with the mouse (step 2), and even that is optional. Everything
else runs headless.

## Quick start

Verify that everything works — a full run of every step on a test scene,
about 2 minutes:

```bash
python3 check.py
```

See what the template produces out of the box:

```bash
blender -b --python template/make.py -- /tmp/t preview
```

Start your own object: copy `template/` into your own folder and edit four
files — `build.py` (shape), `sets.py` (materials), `shot.py` (approved
numbers), `make.py` (control panel). Details in
[template/README.md](template/README.md).

## Documentation

| File | About |
|---|---|
| [GUIDE.md](GUIDE.md) | **Start here.** Steps 0–6 in order: what the code does, where you're needed, and what exactly you decide |
| [LIMITS.md](LIMITS.md) | What this pipeline can't do and where it lies. Read before taking on a task |
| [template/README.md](template/README.md) | New project scaffold |
| [BACKLOG.md](BACKLOG.md) | Improvement hypotheses for future versions — cost, speed, accuracy, scaling to larger/animated/character work |
| [SPEC.md](SPEC.md) | The spec this version (1.2) was implemented from |

## Structure

```
lib/          library — shared across all projects, subject-agnostic
template/     new project scaffold: copy and edit
tests/        end-to-end run on a test scene
check.py      one command that verifies the whole repository
```

Library:

| Module | Responsible for |
|---|---|
| `scene.py` | empty scene, saving, cleanup |
| `camera.py` | angles, grabbing an angle from the viewport, contact sheet |
| `frame.py` | **core**: composition from measured bounding box — fill, offset, focus |
| `materials.py` | procedural materials: leather, nubuck, metal, plastic, glass, carbon, PBR from textures |
| `lighting.py` | lighting in camera-relative coordinates, backdrop, reflectors, a ready advertising rig |
| `variants.py` | a variant grid as a single image |
| `render.py` | render setup, passes, saving PNG + EXR |
| `post.py` | color grading from a finished EXR |
| `exr_info.py` | reading passes from EXR in plain Python, without Blender |
| `mosaic.py` | tiling stitched into one image; `side_by_side()` compares a checkpoint against the last approved one |
| `silhouette.py` | proportions vs. a reference, measured — a flat silhouette profile compared by the number, not by eye; multi-view, tolerance/verdict, and reference-consistency audit |
| `telemetry.py` | append-only run log per project (`run_log.jsonl`) — time and repeat count per stage, no judgment attached |
| `diff.py` | a rough perceptual diff between two renders — a downsampled-grid gate for "something visibly shifted" |

## Core idea

Composition and lighting are **computed from the object's measured bounding
box in camera coordinates**, not eyeballed. "The object fills 86% of the
frame" is a single number, `fill=0.86`, not twenty re-renders spent nudging
the distance. Light sources are defined as fractions of frame coverage, so
the same rig works on an object 2 units across and one 8 units across.

The practical consequence: **approved numbers live in code, not in the
`.blend` file**. The scene file may have been saved before you approved a
look; the numbers reproduce the shot every time — headless, on another
machine, six months later.

## Changelog

**1.2** — systems-engineering pass targeting iteration waste and an
already-realized risk (inconsistent references before a paid geometry API
call), from a backlog collected as a product-management review of the whole
pipeline (see [BACKLOG.md](BACKLOG.md) / [SPEC.md](SPEC.md)):

* `silhouette.compare(..., tolerance=)` — an optional pass/fail verdict next
  to the percent diff, backward-compatible (omit it, get the bare number as
  before).
* `silhouette.audit_references()` — checks a group of same-angle references
  for internal consistency (median profile, per-frame deviation) *before*
  any geometry work starts.
* `silhouette.flat_render(azimuth=, elevation=)` — an optional non-frontal
  silhouette projection, still not a full 3D-shape check (see `LIMITS.md`).
* A documented stop-gate pattern (`template/README.md`): a paid external API
  (image-to-3D and similar) should only be called after `audit_references()`
  passes — spend the free check before the paid one.
* `mosaic.side_by_side()` — a labeled "before/after" comparison image.
* `lib/telemetry.py` — an append-only per-project run log
  (`run_log.jsonl`): time and repeat count per stage, no external
  dependencies.
* `lib/diff.py` — a rough perceptual diff (downsampled-grid, no PIL/heavy
  deps) between two renders, as a "did this change more than expected" gate.
* `template/make.py` now times every stage automatically and, when a
  `<stage>.approved.png` is present, generates a comparison and a diff
  warning against it.
* A five-question applicability checklist added to `GUIDE.md`, step 0 —
  fail fast at the task-framing stage, the cheapest point of failure in
  the whole pipeline.

**1.1** — added `lib/silhouette.py`: an optional early checkpoint that
measures an object's silhouette against a reference numerically (percent
diff per height fraction) instead of relying on "looks off" — see
[GUIDE.md, step 1.5](GUIDE.md#шаг-15-пропорции-по-желанию).

**1.0** — first public release: `lib/`, `template/`, `check.py`.

## License

MIT — see [LICENSE](LICENSE).
