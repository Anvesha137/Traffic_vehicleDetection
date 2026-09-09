# Phase 7 — Validation & QA

**Goal of this phase:** prove — with numbers, not vibes — that the system is accurate
enough to trust, find exactly where it's weak, and build a repeatable process for
checking every new site before you rely on it.

**Exit criteria:** a QA report comparing model output to at least one full manually-
counted video, with per-class and per-movement error broken down, plus a documented
process for spot-checking future runs.

Budget: **3–5 days** for the first full validation, then it becomes a lightweight,
repeatable step per new batch of videos (Phase 8).

---

## 7.1 Get (or create) ground truth to compare against

You need at least one video where you know the *true* counts, to measure against. Options,
best to worst:
1. **Best:** Vtrac (or your team) already has a manually-counted Excel for a video you
   also have — use that directly as ground truth.
2. **Good:** you manually count one 15–30 minute clip yourself (tedious but only needs to
   happen once or twice, not for every video).
3. **Minimum viable:** manually count just a handful of 15-minute buckets across a couple
   of different videos/sites, rather than a whole video — enough to get a directional
   sense of error, faster to produce.

Do this for **at least one AM (busy) and one PM (busy) segment**, and ideally one
lower-traffic segment too, since error rates often differ between light and heavy traffic
(more occlusion when traffic is dense).

---

## 7.2 Compute the accuracy metrics from PRD §2

```python
import pandas as pd

def compare(ground_truth_path, model_output_path, sheet_name):
    gt = pd.read_excel(ground_truth_path, sheet_name=sheet_name, header=None)
    pred = pd.read_excel(model_output_path, sheet_name=sheet_name, header=None)

    # Use the same column_map / row_map helpers from Phase 6 to pull out
    # every (movement, category, bucket_time) -> value from BOTH files, then compare.
    # (Pseudocode below — reuse build_column_map/build_row_map from Phase 6.)

    rows = []
    for key, gt_val in ground_truth_values.items():
        pred_val = predicted_values.get(key, 0)
        rows.append({
            "movement": key[0], "category": key[1], "bucket_time": key[2],
            "ground_truth": gt_val, "predicted": pred_val,
            "abs_error": abs(gt_val - pred_val),
        })

    df = pd.DataFrame(rows)
    df["pct_error"] = df["abs_error"] / df["ground_truth"].replace(0, pd.NA)
    return df

results = compare("ground_truth_arm_a.xlsx", "model_output_arm_a.xlsx", "Arm A")

print("Overall mean absolute error:", results["abs_error"].mean())
print("\nPer-category error:")
print(results.groupby("category")["abs_error"].mean().sort_values(ascending=False))
print("\nPer-movement error:")
print(results.groupby("movement")["abs_error"].mean().sort_values(ascending=False))
```

Compare these numbers directly against the PRD §2 target table. If a specific category
(e.g. Agricultural Tractor/Trailer) is far off target, that tells you exactly where to
add more labeled training data in Phase 2 and retrain in Phase 3 — this is a **loop back**,
not a one-and-done phase.

---

## 7.3 Track tracking-specific quality separately

Beyond count accuracy, check the tracking layer itself (Phase 4), since tracking errors
are a common root cause of count errors:
- **ID switches:** manually watch 2–3 minutes of the annotated debug video (Phase 4 §4.6)
  and count how many times a real vehicle's ID number changes mid-crossing. Divide by
  total real vehicles in that clip → your ID-switch rate (compare to PRD §2 target).
- **Missed vehicles:** count how many real vehicles never got any track at all (usually
  small/fast/heavily-occluded vehicles) in that same clip.
- **Phantom tracks:** count how many tracks correspond to nothing real (shadows,
  reflections, tree movement).

---

## 7.4 Build a lightweight QA report generator (reusable for every future video)

Even once accuracy is good, you should never blindly trust every new run forever. Build
a small automatic report that flags videos likely to need a human look:

```python
def generate_qa_flags(results_df, unmatched_from_phase6, track_history):
    flags = []

    if len(unmatched_from_phase6) > 0:
        flags.append(f"{len(unmatched_from_phase6)} unmatched result rows (see Phase 6 log)")

    unresolved_movements = sum(1 for t in track_history.values() if classify_movement(t, entry_lines, exit_lines) is None)
    total_tracks = len(track_history)
    if total_tracks and unresolved_movements / total_tracks > 0.15:
        flags.append(f"{unresolved_movements}/{total_tracks} tracks had unresolved movement (>15%) — check calibration lines")

    low_conf_tracks = sum(1 for t in track_history.values() if avg_confidence(t) < 0.4)
    if low_conf_tracks / max(total_tracks, 1) > 0.2:
        flags.append(f"{low_conf_tracks} tracks had low average detection confidence — check lighting/occlusion")

    return flags
```

Have every pipeline run (Phase 8) automatically produce this flags list alongside the
filled Excel, so a human reviewer knows in seconds whether to trust a given output or
spend 10 minutes spot-checking it.

---

## 7.5 Decide your QA policy for production use

A realistic, honest policy for v1 (update as accuracy improves):
- **Auto-accept** any 15-minute bucket/category where the model's own confidence signals
  are high and no QA flags fired.
- **Human spot-check** any bucket with QA flags, or a random 10% sample of all buckets
  even without flags, as an ongoing accuracy audit.
- **Always human-review** the "White Plate vs Taxi" and "Bus subtype" columns until Phase
  9 is built and separately validated (per PRD §7, these aren't reliably automatic yet).

---

## 7.6 Deliverables checklist for Phase 7

- [ ] At least one full ground-truth-compared validation run, with per-category and
      per-movement error tables
- [ ] Tracking-specific quality check (ID switches, missed vehicles, phantom tracks)
      done on a sample clip
- [ ] Automatic QA-flag generator wired into the pipeline
- [ ] A written, agreed QA policy (what gets auto-accepted vs human-reviewed)
- [ ] Results compared against PRD §2 targets — decide whether v1 is "good enough to
      start using with human spot-checks" or needs another Phase 2→3 iteration loop first

---

Next: open `10_Phase8_Scaling_Multi_Site_Pipeline.md`.
