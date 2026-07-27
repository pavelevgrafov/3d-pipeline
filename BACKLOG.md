# Hypothesis backlog — version 1.2+

The view of a product manager with experience running large 3D production
pipelines, looking at the current version (1.1). Not an implementation
plan — a list of hypotheses with problem/effect/cost estimates, for
prioritizing ahead of future versions.

---

## How to read this document

The current pipeline already solves its original task well: one solid
object, an advertising frame, every feedback loop measured in seconds.
Render speed itself is **not the main lever** here — `check.py` end to end
takes ~2 minutes, the final render — 30 seconds. The real leverage is
elsewhere: (1) how many iterations get spent BEFORE rendering — on shape
and references that turned out to be wrong; (2) how applicable the
pipeline even is to harder-than-one-object tasks — characters, animation,
a catalog of fifty items; (3) how cheaply the person directing the shoot
can take part in the loop once there's more than one object's worth of
decisions.

Cost estimates (`S`/`M`/`L`) are rough: `S` — a day or two, `M` — one to
two weeks of equivalent work, `L` — a separate sub-project on the scale of
a new module or a new pipeline branch.

---

## Quick wins (P0 — cheap, clear payoff)

| # | Hypothesis | Problem | Effect | Cost |
|---|---|---|---|---|
| 1 | Auto-detect the render device (CPU/GPU) with an explicit warning if only CPU is configured | Right now "it uses whatever's configured in Blender" (LIMITS.md) — the user finds out about a slow CPU render only after the fact, after the first final render | Saves one "wasted" iteration in a new environment | S |
| 2 | A tolerance threshold in `silhouette.compare()` — not just a number, but an "in tolerance / take a look" verdict at a configurable threshold | The discrepancy number exists, but the "is this fine or not" decision still lives in a human's head, redone every time | Less mental load, a step toward an autonomous QA gate | S |
| 3 | An aggregated time/iteration report at the end of `make.py final` — how many steps, how many seconds total, how many returns to 3/4 | GUIDE.md documents step cost manually, once; there's no such visibility per real project | Data for systemic PM analysis instead of one-off estimates | S |
| 4 | "Compare with the last approved" by default at every checkpoint, not just the final | Every step shows only the current variant; seeing what changed requires holding the previous frame in memory | Fewer "fixed one thing, broke another" mistakes, faster decisions | S/M |

---

## Cutting cost

| # | Hypothesis | Problem | Effect | Cost |
|---|---|---|---|---|
| 5 | Extend the reference audit (step 0/1.5) to check **consistency between frames** of the same object — not just silhouette vs. model, but reference vs. reference, before any geometry work | Already demonstrated on the "Tyan" case: inconsistent distance/focal length across 6 frames devalues precise modeling before it even starts. Currently only caught after the fact | Saves exactly the most expensive scenario — sculpting or a paid API call on bad references | M |
| 6 | An explicit "stop-gate" before any paid external call (Meshy and similar): don't allow the call until the `silhouette` reference audit has passed a basic check | Right now a paid API can be called on references of any quality — money is spent before the check, not after | Direct $ savings on failed calls | S/M |
| 7 | A "lighting/material recipe" library from past approved projects (local database, not cloud) — reusing `sets.py`/`shot.py` combinations across similar objects | Every new product in the same product line goes through steps 3–4 from scratch, even though the answer is often similar to a past one | For repeat clients/lines — steps 3–4 become nearly free | M |
| 8 | Presets by object category (jewelry, electronics, footwear, packaging) as starting `shot.py`/`sets.py` files, not an empty template | Cold start is always from scratch from `template/`, even though categories repeat | Fewer iterations to the first acceptable variant | M |

---

## Speeding up

| # | Hypothesis | Problem | Effect | Cost |
|---|---|---|---|---|
| 9 | A long-lived Blender process (add-on/RPC), instead of relaunching `blender -b` for every command | Every call is a cold Blender start plus scene load; on a large project (many objects/materials) that's fixed overhead on every one of dozens of iterations | Noticeably faster during the active-editing phase (steps 1, 3, 4), where most iterations happen | M/L |
| 10 | Parallel rendering of independent checkpoints (angle sheet, material sheet, light grid) instead of sequential | Numbers in `shot.py` are fixed by the time each sheet renders — the builds are independent, but run one after another | Multiplied speedup with a large number of variants (e.g. 12 material sets instead of 6) | M |
| 11 | Targeted re-render via a Cryptomatte mask: re-render/re-composite only one object/material instead of the whole scene, on a step-5→3 return for a spot fix | Passes (Cryptomatte) are already written into the EXR, but only used in post, never for partial recompute | A "fix one rim" return stops costing as much as a full final render | L |

---

## Accuracy

| # | Hypothesis | Problem | Effect | Cost |
|---|---|---|---|---|
| 12 | `silhouette` across several angles (front + side + 3/4), not just frontal | LIMITS.md names this limitation directly: a flat silhouette misses depth/volume errors | Catches a class of shape error the current module can't | M |
| 13 | Numeric target dimensions instead of eyeballing: the user states real dimensions of key points (mm/cm), code checks `build.py` constants against them before rendering | Step 1 currently is "look at the grey clay and describe it in words"; for objects with precisely known dimensions (packaging, a part built to spec) that's a wasted iteration round | Correct shape on the first try wherever dimensions are already known | M |
| 14 | An automatic perceptual diff between the current and last-approved frame (SSIM/perceptual hash) as a gate when returning to step 3/4 | "Went back to step 4, fixed the light" can silently shift something already approved at step 3 | Fewer hidden regressions during iterative editing | M |

---

## Scaling: bigger projects, characters, animation

This is the biggest structural gap between what the pipeline can do now
(one solid object, one frame) and what you've mentioned as a growth goal.
LIMITS.md already names this honestly ("Characters, faces, organic forms —
no sculpting... Animation, video — still frames only"). Below aren't
"add it all at once", but concrete, bounded steps in that direction.

| # | Hypothesis | Problem | Effect | Cost |
|---|---|---|---|---|
| 15 | Multi-object framing mode: "hero + environment", where `frame.fit()` computes coverage from one main object, not the group's combined bounding box | Right now multiple objects only work as "overall coverage around the whole group" (LIMITS.md) — for a catalog scene with props, that's a compromise, not composition | Opens up scenes with props/backdrop without manually nudging the camera | M |
| 16 | "Light" parametric organics: not sculpting, but a base with 5–10 shape-key sliders (height, build, limb length), where `silhouette.profile()` of a reference serves as the objective function for fitting the sliders | Full sculpting is a separate profession, but an approximate proxy figure (a blockout for materials/light) can close the gap for far less | Gives an organic blockout without retopology/rigging — not a replacement for a character, but a bridge to one | L |
| 17 | Animation as approved numbers at two or three points, not curves: key `shot.py` states (start/end of a turn) get approved as ordinary checkpoints, code interpolates between them | Right now "still frames only" is a hard rule; for a simple product turntable or camera push-in, that doesn't need a full animator | A simple product turntable video without stepping outside "look and say a number" | L |
| 18 | A project/version registry (local SQLite/JSON database): which `build.py`/`sets.py`/`shot.py` were approved, for which client, when, why | As the number of projects grows, "why is azimuth=127 here" and "did we have something similar before" isn't stored anywhere but human memory and one project's `PROGRESS.md` | Manageable catalog of dozens/hundreds of objects, not just one | M |
| 19 | A "photogrammetry/LiDAR scan instead of photo references" adapter — phone scans feeding directly into the silhouette audit and (where applicable) geometry import | LIMITS.md already notes that importing a finished model "is possible but not wrapped"; scanning is cheap now and gives far more consistent references than manual photos | Removes the root cause of the "Tyan" reference problem (inconsistent angle/distance) instead of just measuring the symptom | M/L |

---

## Interaction with the person directing the shoot

| # | Hypothesis | Problem | Effect | Cost |
|---|---|---|---|---|
| 20 | A mini-DSL for edits instead of free text: `rim -15%`, `gain +0.2`, parsed without an LLM in the loop for unambiguous cases, LLM only for ambiguous wording | Right now every verbal edit ("darker rim") requires interpretation by the assistant; for frequent, predictable edits that's an unnecessary layer | Faster, cheaper loop on type-in edits, LLM stays for genuinely ambiguous cases | M |
| 21 | A mobile/web review page: numbered previews plus one text reply, no terminal or code on the director's side | The person directing the shoot currently implicitly depends on someone (you or the assistant) opening a terminal and showing a picture | Removes the last dependency on a technical environment for the person making the call | L |
| 22 | An automatic per-project decision log (an extension of the `PROGRESS.md` idea, but at frame level): at every approved checkpoint, auto-record "what was chosen and why" | Numbers in `shot.py` are reproducible, but the **reason** for a choice (why angle 7, not 3) lives nowhere but the conversation | An answer to "why like this" six months later, without digging through chat history | S/M |

---

## Other hypotheses that look promising

| # | Hypothesis | Problem | Effect | Cost |
|---|---|---|---|---|
| 23 | Catalog visual-consistency check: auto-compare lighting histogram/energy between different objects in the same series (`editorial_dark` etc.) | When shooting a series of dozens of products, "each frame looks good on its own" doesn't guarantee the whole series reads as one hand | Catalog consistency as a metric, not a feeling | M |
| 24 | A quality budget per stage: `preview`/`final` are currently fixed sample counts; instead, an adaptive budget tied to how many iterations have already happened at this checkpoint (early runs cheaper, the last one before approval pricier and cleaner) | Resolution/samples are constants with no awareness of iteration context | Less time wasted on early, deliberately rough passes | S/M |
| 25 | An explicit "task doesn't fit this pipeline" class already at step 0 — an auto-checklist from `LIMITS.md` (organic? animation? several objects mixed together?) before `build.py` is even opened | LIMITS.md is exhaustive, but applied by a human manually and from memory — a common cause of lost time is "started, then realized it was the wrong tool" | Fail-fast at the task-framing level, not just on references | S |

---

## How to prioritize

Recommendation (not a decision): start with the **P0** block (items 1–4) —
they're cheap and cut friction immediately. Then item 6 (stop-gate before
a paid API) and item 5 (reference-consistency audit), because they hit
directly at a concrete case that already happened ("Tyan"). Items 15–19
(scaling to characters/animation) are a separate development branch with
its own risk: before investing, it's worth explicitly deciding whether
organics and animation actually belong as part of **this** pipeline, or
whether that's a case for a separate tool that reuses `lib/` as a library
rather than extending it.
