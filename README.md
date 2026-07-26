# 3d-pipeline

**Version 1.0**

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
| `mosaic.py` | tiling stitched into one image |

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

## License

MIT — see [LICENSE](LICENSE).
