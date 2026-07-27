# Limits

Read **before** taking on a task. Here's an honest list of what this
pipeline can't do, where it needs manual work, and where it's easy to
mistake for something it isn't.

---

## Task class

The pipeline is built for **one solid object in frame**: a product shot,
an advertising or catalog frame. Anything beyond that isn't supported:

| Not supported | Why |
|---|---|
| Characters, faces, organic forms | no sculpting, retopology, rigging, skinning |
| Cloth, liquids, smoke, destruction | no simulations or caching |
| Animation, video | still frames only; the timeline is never touched |
| Interiors, scenes, environments | framing and light are built around **one** object |
| Vegetation, terrain | no particle or scatter systems |
| Architecture, drafting precision | no CAD import, dimension chains, tolerances |

Multiple objects in frame technically work — the bounds are measured
across every visible mesh at once — but the composition will read as
"overall coverage around the whole group". The pipeline won't help you
arrange objects relative to each other nicely: that's your call, in
`build.py`.

---

## Geometry

Shape is built from **primitives and modifiers**: cubes, cylinders, tori,
profile revolves, arc arrays, edge bevels. That's enough for a technical
object with a clear construction, and not enough for anything where shape
is an artistic choice.

* Sculpting, retopology, manual mesh editing — **no**.
* UV unwrapping — **no**. Materials are procedural, coordinates are
  generated or object-based. A texture that needs precise unwrap alignment
  won't fit here.
* Importing a finished model (`.obj`, `.fbx`, `.gltf`) is possible in code
  but isn't wrapped or tested. Everything downstream — frame, light,
  render, passes — will work on an imported model.
* Text and logos are made as **geometry**. A decal wrapped onto a curved
  surface is manual work, not covered here.

Practical takeaway: if the object can't be described with a handful of
primitives and a couple of modifiers, build the shape outside the pipeline
and import it.

---

## Proportion check (silhouette)

`lib/silhouette.py` compares the object's silhouette to a reference as a
number instead of "doesn't look right" — but this is a **cheap early
signal**, not a substitute for reviewing angles:

* Only the **flat frontal silhouette** is compared — one projection, not
  the full 3D shape. A matching profile doesn't guarantee matching volume
  or how the object looks from the side.
* The reference must be on a **uniform dark background**: it's a
  brightness threshold, not segmentation. A light background, a
  semi-transparent edge, or compression noise near the threshold silently
  ruins the result — a number still comes out, just the wrong one.
* The module doesn't check that the reference was shot at the same
  distance and focal length as the compared render, and doesn't undo
  perspective distortion from pose or angle — a bent figure gives a
  different profile than the same body in a neutral stance, and the
  difference will land in the numbers as "shape error" even though shape
  has nothing to do with it. Inconsistency between the references
  themselves is a finding for a human, not for a pixel threshold.
* Height-fraction labels (`fractions`, e.g. `{"waist": 0.30}`) are
  subject-specific and live in the project; the library only knows
  fraction numbers (`silhouette.DEFAULT_FRACTIONS`).
* `compare(..., tolerance=...)` gives an `ok`/not-`ok` verdict by
  threshold — that's a decision about tolerance, not about correctness. A
  threshold that fits one label/object pair may be too strict or too loose
  for another: the number doesn't pick a sensible `tolerance` for you.
* `audit_references()` compares shots **only within a single angle** —
  intended as the same pose/frontal view. References of different angles
  aren't compared to each other, and the function doesn't judge which
  frame is "correct": it only shows who deviates from the group's median.
  An outlier from one could well be the one correct frame, if the other
  five were all shot the same wrong way.
* `flat_render(azimuth=..., elevation=...)` gives a profile at another
  projection, but this is still **not a volume check**: several flat
  slices don't add up to a 3D shape, they just give more separate numbers.

---

## Materials

The library is procedural and **finite**: leather, nubuck, metal (with
anisotropy and a radial brush pattern), plastic (micro-relief, lacquer),
glass, carbon. Plus `pbr_library()` — picking up a folder of ready-made PBR
maps.

What's missing:

* wear, scratches, dust, and grime via wear masks;
* complex layered coatings like automotive paint with metal flakes, or
  pearlescent finishes;
* subsurface scattering as a dedicated recipe (skin, wax, jade);
* woven-thread fabric structure;
* emission as an object's own material — glowing planes here are light
  sources only.

Each of these can be built by hand in the node editor. The pipeline
doesn't prevent adding it, but doesn't hand you a ready recipe either.

---

## Light

There's exactly one ready-made rig: `editorial_dark` — dark advertising
style. It's **tuned for a dark glossy object** and calibrated numerically
on one. On a matte light-colored object it produces a flat grey image: the
narrow edge highlights it exists for simply won't appear.

For other jobs there are building blocks — `world_hdri`, `world_gradient`,
`three_point`, `emitter`, `backdrop`, `mirror_board` — but assembling a new
rig from them is on you, with a variant sweep to check the result.

Separately: the **`mirror_board` reflector only works for a flat part**.
It's placed by the mirror-reflection formula relative to a single point
and a single normal. On a convex polished surface the reflection smears,
and finding the point becomes trial and error.

---

## Camera and frame

* Framing is computed from the **bounding box**, not the silhouette. An
  object with large gaps (a ring, a frame, a handle) has bounds noticeably
  bigger than its visible mass, and the frame ends up with extra air.
  Fixable by adjusting `fill`, but by one number, not automatically.
* Bounds are taken from the object's `bound_box` — this is **not the same
  thing** as the actual geometry after modifiers, if a modifier changes
  size substantially.
* Framing excludes what the camera can't see (`visible_camera`) and
  internal names. Your own mesh prop that's visible in frame but shouldn't
  affect composition needs to be listed in `exclude` by hand.
* Depth of field in ortho behaves **unlike photography**: aperture radius
  equals `lens/(2·fstop)/1000` and doesn't depend on distance. The working
  range is 2.5…5.0 for a wide shot, 8…10 for a close-up. Familiar f/1.2
  values turn into mush.

---

## Render and output

* Only **Cycles** for the final render and EEVEE for previews. No external
  engines supported.
* The render device (CPU/GPU) **isn't chosen by code** — it uses whatever
  your Blender is configured with. On CPU, the final frame takes several
  times longer than the stated 30 seconds.
* Resolution and sample count are constants. There's no adaptive
  "keep going until it converges".
* The EXR is written with all passes, including Cryptomatte — but **working
  with those masks isn't automated**. The passes exist; compositing on top
  of them is on you.
* Color grading (`post.py`) is a fixed set: bloom, vignette, contrast, tone
  curve via AgX. A custom node-based comp is something you write yourself.

---

## Comparison with the previous shot and time log

* `mosaic.side_by_side()` prints labels with a minimal built-in pixel font
  — **Latin letters, digits, `-`, `.` only**. A character not in that
  alphabet (Cyrillic included) is silently dropped — the label just gets
  shorter, it doesn't fail. For readable labels, pass `labels` in Latin
  script (`("prev", "curr")`, not `("было", "стало")`).
* `diff.perceptual_diff()` is **not a strict perceptual-loss metric** —
  there's no perception model, just averaging over a coarse grid of cells.
  A small but eye-catching defect (a chip, a stain) can get lost when
  averaged over a large cell; an overall exposure or white-balance shift
  can, conversely, produce a noticeable number even though it wouldn't
  bother a human. The alert threshold (`DIFF_ALERT` in `make.py`) is a
  rough heuristic, not a calibrated value.
* Both functions only work when `<stage>.approved.png` exists — that's a
  manual naming convention (copy the approved frame yourself), not
  automatic version tracking. Nothing stops you from accidentally
  overwriting or forgetting to update the `approved` file — then the
  comparison runs against a stale frame.
* `lib/telemetry.py` only logs what's wrapped in a `record()`/`timed()`
  call. Time spent between `make.py` runs — talking, looking at a frame,
  thinking — doesn't go into the log and shouldn't: it's not a user timer,
  it's a counter for code stages.

---

## Blender version

Tested on **Blender 5.2.0 LTS**. On 4.x the code will break: the API
changed in version 5.

| What changed | Consequence |
|---|---|
| `image_settings.media_type = 'MULTI_LAYER_IMAGE'` | without it, multilayer EXR is silently written as a regular one |
| the compositor moved to `scene.compositing_node_group` | the old `scene.node_tree` doesn't work |
| the `Composite` node no longer exists | output goes through `NodeGroupOutput` |
| `Glare` parameters became input sockets | old code fails accessing properties |
| the engine is `BLENDER_EEVEE` again (was `BLENDER_EEVEE_NEXT` in 4.2–4.5) | the engine name is queried from Blender, not hardcoded as a string |

There is **no** backward compatibility with 4.x, and none is planned.

---

## What's left to the human

The pipeline removes the craft, not the decision. Your involvement is
required wherever taste is needed, and no default setting can replace it:

**Angle.** Which point we're looking from is the main decision about how
the object looks. The pipeline shows twelve variants; which one is correct
is something only you know.

**Materials.** Choosing a set is choosing what the object claims to be.
"Leather and brass" and "carbon and titanium" are different statements
about the same body.

**Matching the reference.** Silhouette proportions are now compared by
`lib/silhouette.py` with a number (see above), but mood, materials, and
fitting the style aren't understood by the code — you still check those
yourself.

**When to stop.** There's no formal "done" criterion. Iterations are
cheap, and that's a trap: you can compare variants forever.

---

## What this is not

This is **not a text-to-image generator**. There's no model that "invents"
the object. Everything that appears in frame was explicitly described by
someone — primitives in `build.py`, materials in `sets.py`.

This is **not a replacement for a designer**. Materials and light come from
a finite set of recipes; the pipeline won't invent a fundamentally new
visual language.

This is **not "press a button and get it"**. Without your decisions at
steps 2 and 3, you'll get a technically correct but indifferent frame.

What it does do, it does **reproducibly**: the same numbers give the same
frame on another machine six months later, and any edit can be undone,
because the scene is code.
