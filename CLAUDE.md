# 3d-pipeline

Pipeline for advertising images of a product in Blender, built from a
description and references. The user doesn't work in the GUI: they look at
a picture with variants and name a number. Everything else is code.

Documentation: [GUIDE.md](GUIDE.md) — steps and checkpoints,
[LIMITS.md](LIMITS.md) — what the pipeline can't do.

## Structure

| Path | Purpose |
|---|---|
| `lib/` | library, **subject-agnostic** — nothing about a specific object |
| `template/` | new project scaffold: `build`, `sets`, `shot`, `make` |
| `tests/smoke.py` | end-to-end run on a test scene |
| `check.py` | one command that verifies the whole repository |

## Rules

**Verify by rendering, not by reasoning.** A preview takes 5 seconds, a
variant grid — 9. Looking is always faster than arguing. No claim about
light, material, or frame reaches the user without a picture.

**Approved numbers go into code.** Angle, set number, frame coverage live
as constants in `shot.py`, not in the `.blend` file: the file could have
been saved before approval.

**After editing `lib/` — `python3 check.py`.** Mandatory, not optional. The
library is shared, and a break in it silently breaks every project.

**Nothing subject-specific goes into `lib/`.** Object names, material
slots, specific sets — belong in the project, not the library. Check: the
test scene in `smoke.py` is deliberately unlike the scaffold in both shape
and scale.

**Numbers are fractions of frame coverage.** Light and composition are
scale-invariant; absolute sizes in the library are a bug.

## Lessons learned the expensive way (re-renders)

| | |
|---|---|
| `blender -b` without a file | loads the STARTUP scene with a cube and a lamp → `scene.reset()` as the first line |
| `snap_to_viewport()` in the background | fails on purpose; used to silently return the startup angle |
| light sources that are meshes | only excluded from bounds by `visible_camera` |
| your own `render.py` next to the script | shadows `lib/render.py` → hence the control panel is named `make.py` |
| ortho + DOF | aperture = `lens/(2·fstop)/1000`, independent of distance; working range 2.5…5.0 |
| Blender 5 API | multilayer EXR — via `media_type`; compositor — `scene.compositing_node_group`, no `Composite` node; engine is `BLENDER_EEVEE` again |

## Commands

```bash
python3 check.py                                        # verify the repository
blender -b --python template/make.py -- /tmp/t preview
blender -b --python template/make.py -- /tmp/t final
blender -b --python lib/post.py -- in.exr out.png vignette=0.3
```
