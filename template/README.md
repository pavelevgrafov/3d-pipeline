# New project scaffold

Copy this folder next to yourself and edit four files. The scaffold works
out of the box: it builds a body with a polished plate and a rim — a
generic product object — so you can run every step before changing
anything and see what it looks like.

```bash
cp -r template ~/my-object
cd ~/my-object
blender -b --python make.py -- /tmp/my preview
```

## The four files

| File | Step | What to edit |
|---|---|---|
| `build.py` | 1 | shape: parameters at the top of the file, then the contents of `build()` |
| `sets.py` | 3 | material sets, 4–6 of them |
| `shot.py` | 2, 4 | approved numbers: angle, set number, frame, light |
| `make.py` | control panel | usually left alone |

## Workflow

```bash
blender -b --python make.py -- /tmp/my angles     # step 1: angle sheet
blender -b --python make.py -- /tmp/my looks      # step 3: material sheet
blender -b --python make.py -- /tmp/my light      # step 4: light variants
blender -b --python make.py -- /tmp/my preview    # quick look between edits
blender -b --python make.py -- /tmp/my final      # step 5: PNG + EXR + .blend

blender -b --python ../lib/post.py -- /tmp/my/final.exr /tmp/my/graded.png
```

What happens at each step and what's required of you —
[GUIDE.md](../GUIDE.md).

Every run appends the stage's time to `run_log.jsonl` (`lib/telemetry.py`);
`final` prints a summary for the whole project. If `OUTDIR` has a
`<stage>.approved.png` (the frame approved in a previous pass of the same
step — just copy `looks.png` to `looks.approved.png` once you've settled
on a material set) — a `<stage>.compare.png` will appear next to it, along
with a warning if the difference is noticeable. Details — [GUIDE.md,
"Comparison with the previous shot and time log"](../GUIDE.md#comparison-with-the-previous-shot-and-time-log).

## Before calling a paid external API

If your project calls a paid geometry-generation service (image-to-3D and
similar) in addition to this pipeline — run the reference audit **before**
the call, not after:

```python
import silhouette

audit = silhouette.audit_references(ref_paths, tolerance=0.15)
if any(v["outlier"] for v in audit.values()):
    raise RuntimeError("references are inconsistent — see audit; API not called")
# only after this check — call the paid service
```

Inconsistent references (different distance or focal length between shots
of the same angle) are visible right here, in seconds and for free —
cheaper to catch this before spending money on an external service than
after. `lib/` knows nothing about any specific API or keys — this is a
pattern in the project's own code, not library-level protection.

## What to know before editing

**Object names are an interface.** `build.py` names objects `Body`,
`Face`, `Ring`; `sets.py` assigns materials to them via `OBJECTS`. Rename
in one place — edit the other too, or the material silently won't apply.

**`face_world()` and `face_normal()` are the object's key point.** The
first returns a point that must stay sharp and lit (a badge, a button, a
neck, a dial — in the scaffold this is the plate's center); the second is
the normal of a flat glossy part, used to place the reflector. Return your
own from these.

**Don't name your files the same as library modules.** The script's own
directory sits in `sys.path` before `lib/`, so a `render.py` next to it
would shadow `lib/render.py`. Hence the name `make.py`.

**Start with `scene.reset()`.** `blender -b` without a file loads the
startup scene — with a cube and a lamp, and both will end up in frame
honestly. `make.py` already does this.

## Defaults

`shot.py` ships with a perspective camera, a square 1080×1080 frame, and
`FILL = 0.78` — the object with some air, catalog-style. Lighting is the
dark advertising rig `editorial_dark`. For a matte or light-colored
object, swap it for `world_gradient()` + `three_point()`: `editorial_dark`
is tuned for dark gloss and gives a flat grey image on matte (see
[LIMITS.md](../LIMITS.md)).

The default angle is set by angles (`USE_VIEWPORT = False`). If you want
to rotate it with the mouse, build the scene in an open Blender, call
`camera.snap_to_viewport()`, copy the returned numbers into `CAM_QUAT`,
`CAM_EYE`, `VIEW_DISTANCE`, and set `USE_VIEWPORT = True`.
