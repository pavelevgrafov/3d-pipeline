# Step-by-step guide

For someone opening this repository for the first time who has never worked
in Blender. Here's what happens at each step, what the code does, and —
most importantly — **where you're needed and what exactly you decide**.

---

## How it works

The pipeline is a loop of three actions, repeated seven times:

```
code builds a variant  →  you're shown one picture  →  you say a word
```

You **never move the mouse in Blender** and never dial in numbers. You look
at a picture and say: "the second one", "too dim", "rotate a quarter turn
left". That turns into a code edit, and the loop repeats.

Three principles everything else follows from:

**Look, don't reason.** No decision about light, material, or frame is made
"from the description". Every one is checked by rendering. A cheap preview
takes 5–10 seconds, so looking is always faster than reasoning.

**Numbers live in code.** The approved angle is four numbers in `shot.py`,
not the state of a `.blend` file. The scene file could have been saved
before you said "like this". Numbers reproduce the shot every time: headless,
on another machine, six months later.

**Composition is computed, not eyeballed.** The object's bounding box is
measured in camera coordinates, and from it the code computes frame
coverage, offset, focus, fog range, and the position of every light source.
That's why one set of settings works on an object of any size.

---

## Checkpoint map

The "your word" column is literally all that's required of you. Everything
else at that step is done by the code.

| Step | What you see | Your word | Time |
|---|---|---|---|
| 0. The task | — | description of the object and references | yours |
| 0.5. Reference audit (optional) | a table of numbers, not a picture | nothing — auto-check, stops on an outlier | ~1 s |
| 1. Shape | grey clay from 12 sides | "proportions are off", "wider", "good" | ~40 s |
| 1.5. Proportions (optional) | a table of numbers, not a picture | nothing — auto-check | ~1 s |
| 2. Angle | a contact sheet of angles, or your own viewport | angle number **or** rotate it yourself | ~40 s |
| 3. Materials | 4–6 sets on your frame | set number | ~60 s |
| 4. Light and frame | 4 variants of one parameter | variant number, "tighter", "darker" | ~10 s |
| 5. Final render | the finished frame at full size | "approved" or back to 3–4 | ~30 s/frame |
| 6. Color grade | the same frame with different grading | "more contrast", "remove the vignette" | ~1 s |

**Mandatory checkpoints are 2 and 3.** Angle and materials can't be chosen
for you: that's the substantive decision about how the object looks. Steps
1 and 4 can be skipped on the defaults and revisited later if the result
doesn't land. Step 6 is optional.

---

## Step 0. The task

**You do this.** Describe the object in words and attach references.

Worth naming: what the object is, what it's made of (material of each
visible part separately), the mood of the shot (dark advertising, bright
catalog, technical cutaway), the frame's aspect ratio (square, vertical
4:5, landscape).

References work as a **sample of mood and light**, not as a blueprint: you
can't recover exact dimensions from a picture. If dimensions matter, state
them as numbers.

The result of this step is a `spec.md` file next to the project: a short
description that's easy to check against the finished frame later.

### Task-applicability checklist

Before opening `build.py` — five questions, one per row of the "[Task
class](LIMITS.md#task-class)" table. A "yes" to any of them is a signal to
stop here, not partway through the geometry: it's either a separate tool,
manual work, or importing a finished model, but not what this pipeline is
built for.

1. Is it a character, a face, or other organic form?
2. Does it need cloth, liquid, smoke, or destruction?
3. Does it need animation or video, not a still frame?
4. Are there multiple objects in the frame where their arrangement
   **relative to each other** matters — not just overall coverage around
   the group?
5. Does it need drafting/CAD precision (tolerances, dimension chains)?

The cheapest point of failure in the whole pipeline: stopping here costs
seconds, stopping partway through `build.py` costs hours.

---

## Step 0.5. Reference audit (optional)

**The code does this.** Needed when there are several references intended
to be the same angle — for example, six front-on photos of the object at
different distances or focal lengths. Discrepancies between such shots are
easy to blame on imprecise geometry at step 1, when the real cause is the
references themselves: a different distance or focal length between frames
already produces a different silhouette, regardless of what gets sculpted
afterward.

```python
import silhouette

audit = silhouette.audit_references(
    ["references/front_01.png", "references/front_02.png", "references/front_03.png"],
    tolerance=0.15)
for path, v in audit.items():
    print(path, "outlier" if v["outlier"] else "ok", v["diff"])
```

`audit_references` doesn't decide which shot is "correct" — it only shows
which one deviates from the group's median. Run it before `build.py`: it's
cheaper to discard a bad reference now than to reshape geometry to fit
distorted numbers.

**Your word:** nothing, this is an auto-check. But on `outlier=True` — go
back to the references, not the geometry.

> **Limitation.** Only comparable **within a single angle** — the shots
> must be the same pose/frontal view. References of different angles are
> not compared to each other here — see [Step 1.5](#step-15-proportions-optional)
> for a multi-view silhouette.

### Stop-gate before a paid external API

If a project calls a paid geometry-generation service (e.g. an
image-to-3D API) — call it **after** the reference audit, and only if
there are no outliers. Money gets spent before the check, not after, if
there's no gate:

```python
audit = silhouette.audit_references(ref_paths, tolerance=0.15)
if any(v["outlier"] for v in audit.values()):
    raise RuntimeError("references are inconsistent — see audit; API not called")
# only after this check — call the paid service
```

This isn't library-level protection — `lib/` knows nothing about external
services or keys — but a mandatory pattern in the project's own code. Full
example — [template/README.md](template/README.md#before-calling-a-paid-external-api).

---

## Step 1. Shape

**The code does this.** Geometry is described in `build.py` with primitives
and modifiers: cubes, cylinders, tori, profile revolves, edge bevels. No
materials, no light — shape only.

Object names (`Body`, `Face`, `Ring`) are the **interface between files**:
`sets.py` assigns materials by them, and `shot.py` aims light and focus by
them. Rename in one place — edit the other too.

```bash
blender -b --python make.py -- /tmp/out angles
```

**You see** `angles.png` — the object as grey clay from 12 sides, 30° apart.
Materials are deliberately off at this step: color and highlights would
hide a crooked silhouette.

**Your word.** Look at proportions and silhouette: "the body's too deep",
"the bevel looks melted", "the rim doesn't read". Shape parameters live at
the top of `build.py` as separate constants precisely so edits like these
are a one-number change.

> **Easy to lose time here.** Don't polish the shape to perfection at this
> step. A lot of what looks wrong on grey clay disappears under materials
> and light — and vice versa. Getting the proportions right is enough.

---

## Step 1.5. Proportions (optional)

**The code does this.** Needed when "proportions are off" from step 1 is
a subjective complaint with nothing to check it against except redoing the
shape and looking again. `lib/silhouette.py` turns that into a number: a
threshold against a black background turns the reference and the render
into a silhouette, and the silhouette into a table of "width at such-and-
such a fraction of height".

```python
import silhouette

# height fractions are subject-specific — your project, not the library
FRACTIONS = {"shoulder": 0.13, "waist": 0.30, "hip": 0.45, "ankle": 0.88}

ref = silhouette.profile("references/front.png", FRACTIONS)
silhouette.flat_render("/tmp/render.png")
mine = silhouette.profile("/tmp/render.png", FRACTIONS)
print(silhouette.compare(ref, mine))   # {"shoulder": -3.2, "waist": 22.4, ...} — percent
```

`flat_render()` sets up a frontal view, an ortho camera, and a flat white
material on the current scene itself (`build.py` is already assembled),
and returns everything to how it was after the render — you can call it
straight from your own `make.py`, no separate script needed.

**Your word:** nothing, this is an auto-check. A large percentage on a
single label is a signal to go back to step 1 before the eye gets used to
it, not after materials and light have settled on top of the shape.

> **This is not a 3D-shape check**, only a flat frontal silhouette — a
> cheap early signal, not a replacement for step 2 or the final review.
> Nor is it license to pair the reference with just anything: a bent pose
> or a reference shot from a different distance will give a different
> profile regardless of how accurate the geometry is — see
> [LIMITS.md](LIMITS.md#proportion-check-silhouette).

### Several angles instead of one frontal view

For organic and non-trivial shapes, one frontal view is often not enough:
arms held against the body in one reference and spread in another — a
volume difference invisible in a single projection. `flat_render` accepts
`azimuth`/`elevation` (like `camera.look_from`) — you can take a profile
at a 3/4 view too, if a matching-angle shot exists for the reference:

```python
front = silhouette.flat_render("/tmp/front.png")                       # frontal, as before
side = silhouette.flat_render("/tmp/3q.png", azimuth=45, elevation=0)   # same trick, different angle
```

This is still **not a full 3D-shape check**: several flat projections
don't add up to volume, they just add another slice. The library doesn't
decide which angles matter for a given object — the same kind of decision
as the `fractions` labels.

---

## Step 2. Angle

The most substantive decision in the whole pipeline: which point we're
looking from. Two paths, pick either.

### Path A — from the sheet (no need to open Blender)

**You see** the same `angles.png` from step 1. Tiles are numbered left to
right, top to bottom.

**Your word:** "seventh" or "seventh, but a bit higher". The number and
height get written into `shot.py` as `AZIMUTH`, `ELEVATION`, `DISTANCE`,
`LENS`.

### Path B — rotate it yourself (needs Blender open)

The one place where a live Blender gives you something the background
mode doesn't.

1. Open Blender, load the assembled scene.
2. Rotate the view with the mouse until you like it. This is exactly what
   you already know how to do without training — rotate an object.
3. `camera.snap_to_viewport()` puts the render camera exactly where you
   ended up, and **returns the numbers**.
4. The numbers get copied into `shot.py` as the constants `CAM_QUAT`,
   `CAM_EYE`, `VIEW_DISTANCE`, and `USE_VIEWPORT = True`.

The angle is copied from the viewport exactly, including ortho mode: if
you were rotating in orthographic view, the camera becomes orthographic
too. Perspective isn't forced on you — working in ortho wasn't an accident.

> In headless Blender (`-b`), `snap_to_viewport()` **fails with an error**,
> on purpose. It used to silently return the startup angle — producing a
> frame nobody had actually chosen.

**End of step:** numbers in code. From this point on, a live Blender is
never needed again — `camera.restore()` rebuilds the same camera from the
recorded numbers.

---

## Step 3. Materials

**The code does this.** `sets.py` describes 4–6 material **sets**. A set
is a dictionary of "slot → material": for example, "body — matte
graphite, plate — polished steel, rim — circular brushed metal".

Materials are procedural: grained leather, nubuck, metal with anisotropy
and a radial brush pattern, plastic with micro-relief and lacquer, glass,
carbon. Texture files aren't needed, but if you have them —
`materials.pbr_library()` will pick up a folder of PBR maps.

```bash
blender -b --python make.py -- /tmp/out looks
```

**You see** `looks.png` — every set in one image, numbered in frame.
Important: the sets are shown **on your object, at your angle**, not on
preview spheres. Metal on a sphere and metal on a flat plate look different.

**Your word:** the set number. Or "the third one, but darker rim".

> **Why 4–6 sets, not two, not twenty.** Fewer than four — nothing to
> choose from, nothing for the eye to compare against. More than six — the
> sheet stops reading, and the choice turns into a lottery.

The chosen number goes into `shot.py` as `MATERIAL_SET`.

---

## Step 4. Light and frame

This is where the pipeline differs most from manual work.

### Frame is computed

`frame.fit()` measures the object's bounding box in camera coordinates and
adjusts coverage so the object fills a given fraction of the frame:

* `FILL` — the frame fraction taken by the object. `0.9` — tight, "the
  object fills the frame". `0.6` — with air, catalog-style.
* `OFFSET` — shift away from center. The object doesn't have to sit on the
  axis.
* `FIT_BY` — which side to fit by. `"max"` — the object fits entirely
  (default). `"height"`/`"width"` — the other side may run off-frame, which
  makes sense when a crop is intentional.

In an orthographic camera, coverage changes while the camera stays put —
**the approved angle isn't disturbed**. In a perspective camera, the camera
pulls back along its own line of sight: the field of view is set by the
lens, nothing to change there except distance; the direction of view
doesn't change either.

### Light is placed in camera coordinates

Each light source is defined relative to the camera: x is right across the
frame, y is up, the camera looks along −z. "A source to the right of frame"
literally means positive x — **at any angle**. Change the angle, and the
light travels with it, staying put within the frame.

Source sizes and distances are expressed as fractions of frame coverage.
This isn't decoration, it's physics: scale both a source's size and its
distance by the same factor, and the solid angle doesn't change — so
neither does the illumination. That's why a finished rig works on an
object of any size.

The ready-made rig `lighting.editorial_dark()` is dark advertising style:
narrow highlight strips along edges, a light patch on the background, a
separate reflector for a flat glossy part. For a matte object or a bright
background, use `world_gradient()` + `three_point()`.

```bash
blender -b --python make.py -- /tmp/out light
```

**You see** `light.png` — one parameter in four values, as a single image.
By default this is overall brightness (`gain`), but anything can be swept
this way: hardness, the patch's position on the background, the fraction
of fill light.

**Your word:** the variant number. Or in words: "tighter", "darker on the
left", "the top-edge highlight is too wide".

> The variant grid is the cheapest loop in the whole pipeline: four frames
> at 360×480, 64 samples, render in about 9 seconds. Trying variants is
> **faster than arguing** about which one is correct.

---

## Step 5. Final render

```bash
blender -b --python make.py -- /tmp/out final
```

**The code does this.** Full resolution, 320 samples, Cycles, and three
output files:

| File | What it is |
|---|---|
| `final.png` | 16-bit, through AgX — the finished picture |
| `final.exr` | 32-bit, linear, multilayer: 14 passes |
| `final.blend` | the scene in exactly the state that produced the picture |

The passes in the EXR aren't a formality. They hold Depth, Normal, Mist,
Ambient Occlusion, separate Diffuse/Glossy, and Cryptomatte by object and
material. Cryptomatte gives **exact per-object masks** — you can select one
rim and edit only it, without re-rendering the whole scene. Depth and
Normal are needed if the frame is headed into compositing or another app.

**You see** the finished frame at full size.

**Your word:** "approved" — or go back to step 3 or 4. Going back is
cheap: the numbers are recorded, rebuilding is one command.

---

## Step 6. Color grading

**The code does this** from the finished EXR — **the scene isn't
re-rendered**:

```bash
blender -b --python ../lib/post.py -- /tmp/out/final.exr /tmp/out/graded.png
```

Bloom from highlights, vignette, contrast, tone curve. Parameters are
passed right on the command line:

```bash
blender -b --python ../lib/post.py -- in.exr out.png vignette=0.3 strength=0.7
```

**You see** the same frame with different processing.

**Your word:** "more contrast", "remove the vignette", "too much bloom".

> **This is the cheapest edit in the pipeline — about a second.** So the
> grade gets revised as many times as needed, and for the same reason it
> shouldn't be finalized at step 5 by baking it into the render: anything
> that can be deferred to the EXR should be deferred to the EXR.

---

## Comparison with the previous shot and time log

Two things the scaffold's `make.py` does automatically, with no separate
command.

**Comparison with the last approved version.** Each step shows only the
current variant — seeing what changed after going back to step 3 or 4 used
to mean holding the previous frame in memory. The convention is simple:
once you approve a checkpoint, save it alongside as `<stage>.approved.png`
(e.g. `looks.approved.png` for step 3). On the next run of the same step,
`make.py` will drop a `<stage>.compare.png` next to it ("approved"/"new",
`lib/mosaic.py:side_by_side`) and compute a rough difference
(`lib/diff.py:perceptual_diff`) — if it's above the threshold, you'll get
a `WARNING` in the console. This isn't a strict perceptual loss, just a
rough averaging grid: a small local defect can get lost, while an overall
exposure shift can produce a number even though the eye isn't bothered.
The number is a signal to look, not an automatic verdict.

**Time log.** Every `make.py` run appends a line to `OUTDIR/run_log.jsonl`
(`lib/telemetry.py`) — how long the stage took. On `final`, the console
prints a summary for the whole project: total time and call count per
stage, so returns to step 3/4 show up as a counter, not as a memory of
"how many times we redid the light".

---

## If something went wrong

| Symptom | Cause |
|---|---|
| A white cube in frame | `blender -b` without a file loads the **startup** scene — with a cube and a lamp. Start `make.py` with `scene.reset()` |
| The object is tiny in a corner of the frame | An extra object got into the bounds. `frame.subjects()` excludes what the camera can't see, but your own mesh prop may slip through the filter — add it to `exclude` |
| The frame doesn't match what was approved | The numbers came from the `.blend` file, not from code. Every approved value must live in `shot.py` |
| Blur ate the detail | In ortho, aperture radius equals `lens/(2·fstop)/1000` and **doesn't depend on distance**. Familiar photographic f/1.2 values turn into mush; the working range is 2.5…5.0 for a wide shot and 8…10 for a close-up |
| The script imports itself | The script's own directory sits in `sys.path` before `lib/`. Don't name your files `render.py`, `scene.py`, `camera.py` — hence `make.py` |
| `silhouette.compare` gives large discrepancies on a model that looks correct | The reference isn't on a black background, was shot from a different distance/focal length, or the pose isn't frontal — the profile is lying, not the geometry. See [LIMITS.md](LIMITS.md#proportion-check-silhouette) |
| Everything broke after a library edit | `python3 check.py` — it runs every step on the test scene and tells you exactly what broke |

---

## Repository check

```bash
python3 check.py
```

Five stages: compiling every `.py` file, an end-to-end run of every step
inside Blender on the test scene, checking artifacts on disk, and
separately — **reading the resulting EXR in plain Python, without bpy** —
and building the scaffold at the cheap `preview` stage. Reading the EXR
without Blender isn't a formality — it's the only way to see that the file
holds real passes, not a single RGBA layer, which Blender can write out
silently.

The test scene is deliberately **unlike** the scaffold in both shape and
scale (around 8 units vs. 3.2, and ring-shaped instead of solid). If the
library quietly picked up assumptions about a specific object, this run
will show it.

---

## How much time this costs

| | |
|---|---|
| Proportion check (`silhouette.profile`+`compare`) | ~1 s per reference |
| Contact sheet of angles, 12 tiles | ~40 s |
| Material sheet, 6 sets | ~60 s |
| Light grid, 4 variants | ~9 s |
| Preview between edits | ~5 s |
| Final frame, 320 samples | ~30 s |
| Color grade from EXR | ~1 s |
| `check.py` end to end | ~2 min |

Measured on a MacBook, Blender 5.2.0 LTS. The order of magnitude matters
more than exact numbers: **every feedback loop is seconds to tens of
seconds**, so looking is cheaper than reasoning.

---

Next: [LIMITS.md](LIMITS.md) — what this pipeline can't do.
