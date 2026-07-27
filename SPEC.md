# Spec — version 1.2

Implementation of the critical and important hypotheses from
[BACKLOG.md](BACKLOG.md). The items chosen are ones that either (a) are
cheap relative to their payoff, or (b) directly close a risk that's
already materialized (inconsistent "Tyan" references, money spent on a
paid API before checking). The backlog's big bets (characters, animation,
multi-object scenes, a render farm) are **not** part of this spec — see
"Out of scope" at the end.

The number in brackets is a reference to the matching [BACKLOG.md](BACKLOG.md)
item.

---

## Release summary

| Feature | Backlog | Layer | Cost | Depends on |
|---|---|---|---|---|
| A. Task-applicability checklist | #25 | documentation | S | — |
| B. Tolerance and verdict in silhouette comparison | #2 | `lib/silhouette.py` | S | — |
| C. Reference-consistency audit | #5 | `lib/silhouette.py` | M | B |
| D. Multi-view silhouette | #12 | `lib/silhouette.py` | M | B |
| E. Stop-gate before a paid API | #6 | template/project + `lib/silhouette.py` | S | B |
| F. Compare with the last approved | #4 | `lib/mosaic.py` | S/M | — |
| G. Time and iteration log | #3 | new `lib/telemetry.py` | S | — |
| H. Perceptual-diff gate | #14 | new module (`lib/diff.py`) | M | F |

Whole-release readiness criterion: `python3 check.py` → **PASS 5/5**,
`README.md` version and changelog updated to 1.2, `GUIDE.md`/`LIMITS.md`
reflect the new steps and their honest limitations (project principle: a
limitation gets documented, not hidden).

---

## A. Task-applicability checklist (step 0)

**Problem.** `LIMITS.md` exhaustively lists what the pipeline can't do
(organics, animation, interiors, cloth/liquids), but it's applied by a
human manually and from memory. A typical time sink is starting `build.py`
and only realizing partway through that the task is the wrong class
entirely.

**Solution.** Not code — documentation. In `GUIDE.md`, section "Step 0. The
task", add a short five-question checklist, one per row of the "Task
class" table in `LIMITS.md`: character/organic? cloth/liquid/smoke? needs
animation? multiple objects where arrangement relative to each other
matters? needs drafting precision? A "yes" to any of them is a signal to
stop before `build.py` and handle it separately (model import, a separate
tool, manual work), not inside the pipeline.

**Acceptance criteria.** The checklist is visible in `GUIDE.md` before the
"Step 1" section, links to specific `LIMITS.md` rows work.

**Payoff.** Fail-fast at the task-framing level — the cheapest point of
failure in the whole pipeline, cheaper even than a cheap preview.

---

## B. Tolerance and verdict in silhouette comparison

**Problem.** `silhouette.compare()` returns a percent discrepancy per
label, but the "is this within normal range or not" decision is made fresh
by a human every time. Without a threshold, the number can't be used as an
automatic gate (in particular — for feature **E** below).

**Solution.** Add an optional `tolerance` parameter (a fraction, e.g.
`0.15`) to `compare()` in `lib/silhouette.py`. When present, a verdict is
added next to the number:

```python
def compare(reference, render, tolerance=None):
    ...
    # without tolerance — behavior unchanged, numbers only
    # with tolerance — additionally out[label] = {"diff": -3.2, "ok": True}
```

Backward compatibility is mandatory: without `tolerance`, the return value
is exactly what it is today (a bare number). The threshold isn't subject-
specific — it's a call parameter, not a library constant (same principle
as `fractions`).

**Acceptance criteria.** A new smoke check in `tests/smoke.py`:
`compare(x, x, tolerance=0.1)` gives `ok=True` on every label; a
deliberately distorted profile with a discrepancy above the threshold
gives `ok=False`.

**Payoff.** Turns a measurement into a decision without a human in the
loop on every iteration — the necessary base for the stop-gate (E) and for
future autonomous acceptance.

---

## C. Reference-consistency audit (step 0.5, before geometry)

**Problem.** Diagnosed on the "Tyan" case: discrepancies blamed on
imprecise sculpting were partly explained by inconsistent distance/focal
length across six on-screen shots of the same object. This is visible in
the references themselves, before any time is spent on shape — but right
now there's nothing that checks it automatically.

**Solution.** A new function in `lib/silhouette.py`:

```python
def audit_references(paths, fractions=None, thresh=0.06, tolerance=0.15):
    """profile() of each path, then the group's median profile and each
    frame's deviation from it. Returns {path: {..., "outlier": bool}} — it
    doesn't judge what's correct, only shows which frame deviates from
    the group."""
```

An important limitation that needs to be documented explicitly (in the
spirit of the current `LIMITS.md`): this function is only comparable
**within a single angle** — several shots intended as "the same pose, the
same frontal view". Comparing references of *different* angles to each
other isn't part of this — that's feature D's job.

**Where it's called.** Not in `lib/`, but as a recommended pattern in
`GUIDE.md`/`template/README.md`: run at step 0, right after getting the
references, before `build.py`.

**Acceptance criteria.** Smoke test: a set of three consistent synthetic
silhouettes plus one deliberately rescaled one — `audit_references` flags
only the fourth as an `outlier`.

**Payoff.** Catches exactly the class of error that was previously
misattributed to geometry in a past case — before time or money is spent
on the wrong geometry.

---

## D. Multi-view silhouette

**Problem.** `silhouette.flat_render()` hard-locks a frontal view
(`azimuth=elevation=0`) — a documented limitation: "only the flat frontal
silhouette is compared… a bent figure gives a different profile". Depth/
volume errors (arms held against the body in one reference, spread in
another) are invisible in a single projection in principle, not by
oversight.

**Solution.** Add optional `azimuth`/`elevation` parameters to
`flat_render()` (default `0, 0` — backward compatible, existing calls
don't change):

```python
def flat_render(path, res=(700, 1150), lens=60.0, fill=1.06,
                 azimuth=0.0, elevation=0.0):
```

Usage — run `profile()`+`compare()` for several angles (e.g. front + 3/4),
each time with a separate reference of that same angle. The library
doesn't decide which angles matter for a given object — that's still a
project-level decision, same as the `fractions` labels.

**Acceptance criteria.** Smoke check: `flat_render` with `azimuth=45`
gives a non-empty profile, distinct from `azimuth=0` on an asymmetric test
geometry.

**Payoff.** Closes a limitation named directly in `LIMITS.md` ("not a
check of the full 3D shape") — not entirely, but moves it from "not at
all" to "yes, across several projections", which for organic shapes is the
main source of errors.

---

## E. Stop-gate before a paid external API

**Problem.** Nothing currently stops a paid external geometry-generation
service (Meshy and similar) from being called on references of any
quality. Money is spent before the check, not after — even though a cheap
check (silhouette of the references) already exists and takes seconds.

**Solution.** Not a new function in `lib/`, but a mandatory pattern,
documented and placed in `template/`: before calling an external API, the
project code must call `audit_references(...)` (C) and **explicitly check**
for no `outlier`. Example in `template/README.md`:

```python
audit = silhouette.audit_references(ref_paths, tolerance=0.15)
if any(v["outlier"] for v in audit.values()):
    raise RuntimeError("references are inconsistent — see audit; API not called")
# only after this check — call the paid service
```

The library can't "forbid" a project from calling an API — the call lives
in project code, not in `lib/` (external services, keys, network are
already outside `lib/`). The gate is a mandatory pattern and an explicit
check, not a runtime lock.

**Acceptance criteria.** `template/README.md` contains this pattern as the
recommended first step before any paid-API integration; the example in the
documentation passes as part of the template's smoke check (already
covered by the existing `check.py` stage that builds `template/`).

**Payoff.** Direct savings on an already-observed class of error — a cheap
check before an expensive, irreversible call.

---

## F. Compare with the last approved (at every checkpoint)

**Problem.** Every step shows only the current variant. Seeing what
changed after going back to step 3 or 4 requires holding the previous
frame in memory — a source of silent regressions ("fixed the light, but
the materials shifted").

**Solution.** Extend `lib/mosaic.py` with a `side_by_side(prev_path,
curr_path, out_path, labels=("prev", "curr"))` function that simply places
two PNGs side by side with labels. Usage — in each project's `make.py`: if
a previous approved checkpoint file exists in the working folder (a simple
naming convention, e.g. `<stage>.approved.png`), automatically build a
comparison next to the new variant.

**Acceptance criteria.** Smoke check: `mosaic.side_by_side()` on two test
PNGs gives a file of the right width (sum of widths plus a gap) with both
source images visibly present pixel-wise (not a black/empty result).

**Payoff.** Fewer "fixed one thing — broke another" mistakes; the decision
is made from the difference, not from the absolute state.

---

## G. Time and iteration log

**Problem.** `GUIDE.md` documents step cost once, manually, on one
machine. There's no such visibility per real project — you can't answer
"how much did we spend" without digging through chat history.

**Solution.** A new dependency-free module, `lib/telemetry.py`:

```python
def record(project_dir, stage, seconds, extra=None):
    """Appends a line to <project_dir>/run_log.jsonl: {ts, stage,
    seconds, extra}. Doesn't decide what's slow — just records the fact."""

def summary(project_dir):
    """Reads run_log.jsonl, returns total time per stage and the repeat
    count per stage (returns to 3/4 show up as a counter)."""
```

Called from `make.py` around each stage (`time.time()` before/after, one
`record()` call). Requires no changes to existing `lib/` modules.

**Acceptance criteria.** Smoke check: several `record()` calls plus
`summary()` give the correct sum and the correct repeat count per stage.

**Payoff.** Data for real prioritization of future versions instead of
one-off guesses — in particular, will show whether render-speed features
(out of scope for this spec) are actually worth investing in on real
projects.

---

## H. Perceptual-diff gate

**Problem.** Going back to step 3/4 can silently shift something already
approved earlier (material, frame) — right now this is only caught by
eye, if at all.

**Solution.** A new module (working name `lib/diff.py`), without PIL/numpy
(a project constraint, confirmed by experience with `silhouette.py`),
built the same way as `silhouette._rows()`, via
`bpy.data.images.load()` + `.pixels`:

```python
def perceptual_diff(path_a, path_b, grid=(16, 16)):
    """Downsamples both PNGs to grid by cell-averaging (no external
    libraries), then reports max and mean difference across cells.
    Cheap, coarse, but good enough as a 'something visibly shifted'
    gate."""
```

Used together with F: when `<stage>.approved.png` exists — not just show
the side-by-side comparison, but also compute `perceptual_diff` and
explicitly warn if the difference is above a rough threshold, at a step
that wasn't supposed to change it.

**Acceptance criteria.** Smoke check: `perceptual_diff(x, x) == 0`;
`perceptual_diff` on substantially different synthetic images is above a
given threshold.

**Payoff.** Regressions show up as a number on the spot, not after the
fact at the final review — cheapest to catch at the moment they happen.

---

## Implementation order

1. **A** — blocks nothing, pure documentation, do it first.
2. **B** — the base for **C** and **E**; without a verdict, the audit and
   the gate are pointless.
3. **C** and **D** — independent of each other, both depend only on **B**.
4. **E** — depends on **C** (uses `audit_references`) and **B**.
5. **F** — independent, can be done in parallel with B/C/D.
6. **G** — fully independent, lowest risk, can be done at any point.
7. **H** — depends on **F** (reuses the `<stage>.approved.png` convention).

## Overall release acceptance criteria

- `python3 check.py` → `PASS 5/5`, including new smoke checks for each
  feature.
- Every new function in `lib/` is subject-agnostic: no object names,
  material slots, or subject-specific labels (checked by the same
  principle as the rest of `lib/` — the `smoke.py` test scene is
  deliberately unlike a real project).
- `GUIDE.md` and `LIMITS.md` are updated: new capabilities are described
  alongside their honest boundaries (in particular — D is not presented as
  a "full 3D-shape check", H is not presented as a true perceptual-loss
  metric).
- `README.md`: version → 1.2, a changelog entry, the library module table
  extended (`telemetry.py`, and `diff.py` once it exists).

## Out of scope for this spec

Explicitly not included (the backlog's big bets, each its own spec if the
decision is made to invest): multi-object composition (#15), parametric
organics (#16), animation (#17), a project registry (#18), a
photogrammetry/LiDAR adapter (#19), a long-lived Blender process (#9),
parallel checkpoint rendering (#10), targeted Cryptomatte re-render (#11),
a cross-project light/material recipe library (#7), category presets (#8),
a mini edit DSL (#20), a mobile review page (#21).
