# Phase 5 — Turning Movement & Time-Bucket Classification

**Goal of this phase:** for every tracked vehicle from Phase 4, decide (a) which
"movement" it made (e.g. arrived from Arm A, exited toward Arm C → movement "A→C"), and
(b) which exact 15-minute Excel row it belongs in. This is where Phase 1's calibration
lines finally get used.

**Exit criteria:** a per-video results table: one row per tracked vehicle, with columns
`track_id, vehicle_class, movement (e.g. "A-C"), bucket_time (e.g. "08:15")`.

Budget: **3–5 days** (mostly logic + testing, some light OCR work for timestamps).

---

## 5.1 Step 1: line-crossing logic (which movement did this vehicle make?)

Recall from Phase 1 you defined an `entry_line` and `exit_line` per arm, as two pixel
points each. The geometry idea: as a tracked vehicle's center point moves frame to frame,
check whether its path **crosses** each line. Whichever entry line it crosses first, and
whichever exit line it crosses last, defines its movement.

```python
def ccw(A, B, C):
    return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

def segments_intersect(A, B, C, D):
    """Standard geometry check: does segment AB cross segment CD?"""
    return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

def find_crossed_line(prev_point, curr_point, lines_dict):
    """lines_dict: {"A": [[x1,y1],[x2,y2]], "B": [...], "C": [...]}"""
    for arm_name, (p1, p2) in lines_dict.items():
        if segments_intersect(prev_point, curr_point, tuple(p1), tuple(p2)):
            return arm_name
    return None
```

Then, for each track's frame-by-frame path:

```python
def classify_movement(track, entry_lines, exit_lines):
    entered_arm = None
    exited_arm = None
    for i in range(1, len(track)):
        prev_pt = (track[i-1]["cx"], track[i-1]["cy"])
        curr_pt = (track[i]["cx"], track[i]["cy"])

        if entered_arm is None:
            arm = find_crossed_line(prev_pt, curr_pt, entry_lines)
            if arm:
                entered_arm = arm

        arm = find_crossed_line(prev_pt, curr_pt, exit_lines)
        if arm:
            exited_arm = arm   # keep updating, we want the LAST exit crossing

    if entered_arm and exited_arm:
        return f"{entered_arm}-{exited_arm}"
    return None   # couldn't determine movement — flag for QA, don't guess
```

**Important: it's OK to return `None`/unknown for some tracks.** A track that never
clearly crosses a defined entry+exit line (e.g., a vehicle that only briefly clips the
edge of frame, or a pedestrian/stationary object that got misdetected) should be excluded
from the count rather than force-assigned to a guessed movement. Log these to a QA file
(Phase 7) so a human can glance at how many were excluded and why.

---

## 5.2 Step 2: getting the exact wall-clock time (reading the burned-in timestamp)

You have two options, in order of preference:

### Option A (preferred, if timestamp overlay is present, like your sample video)
Read the actual burned-in clock digits from the frame using OCR. This is more reliable
than trusting the file's metadata, because recordings can start a little later/earlier
than scheduled, or the file's internal clock can drift.

```python
import easyocr   # pip install easyocr
reader = easyocr.Reader(['en'], gpu=True)

def read_timestamp(frame, region_px):
    x1, y1, x2, y2 = region_px   # from your site_config.yaml, e.g. [10, 5, 260, 35]
    crop = frame[y1:y2, x1:x2]
    result = reader.readtext(crop, detail=0)
    return " ".join(result)   # e.g. "2026-05-13 08:01:33"
```

You don't need to run OCR on every single frame (slow) — run it once every ~5 seconds
(100 frames at 20fps) and interpolate the timestamp for frames in between using the known
fps, since the clock advances in a perfectly predictable way once anchored:

```python
from datetime import datetime, timedelta

def interpolate_timestamp(anchor_time: datetime, anchor_frame_idx: int, frame_idx: int, fps: float) -> datetime:
    seconds_elapsed = (frame_idx - anchor_frame_idx) / fps
    return anchor_time + timedelta(seconds=seconds_elapsed)
```

### Option B (fallback, if no burned-in timestamp)
Parse the recording start time from the filename/folder convention (this is why
confirming the naming pattern in Phase 1 §1.2 matters), then compute:
`row_time = file_start_time + (frame_idx / fps)` seconds.

Either way, once you have the actual timestamp for the frame where a vehicle's exit-line
crossing happened, **round it down to its 15-minute bucket**:

```python
def bucket_15min(dt: datetime) -> str:
    minute_bucket = (dt.minute // 15) * 15
    return dt.replace(minute=minute_bucket, second=0, microsecond=0).strftime("%H:%M")
```

---

## 5.3 Putting it together: the per-video results table

```python
import pandas as pd

rows = []
for track_id, track in track_history.items():
    movement = classify_movement(track, entry_lines, exit_lines)
    if movement is None:
        continue   # unresolved movement, excluded — logged separately for QA

    cls = final_class_for_track(track)   # from Phase 4 §4.4

    exit_frame_idx = track[-1]["frame"]   # approx — refine to the actual crossing frame if you tracked it in 5.1
    exit_time = interpolate_timestamp(anchor_time, anchor_frame_idx, exit_frame_idx, fps)
    bucket = bucket_15min(exit_time)

    rows.append({
        "track_id": track_id,
        "vehicle_class": cls,
        "movement": movement,
        "bucket_time": bucket,
    })

results_df = pd.DataFrame(rows)
results_df.to_csv("outputs/site15_video1_results.csv", index=False)
print(results_df.groupby(["movement", "bucket_time", "vehicle_class"]).size())
```

That last `groupby` line is essentially the exact shape of numbers your Excel template
needs — Phase 6 just needs to route each count into the right cell.

---

## 5.4 Mapping your 9 detector classes to the Excel's 15 columns

Since Phase 3's detector uses simplified classes (Phase 2 §2.2), apply this mapping when
producing final counts (documenting the honest simplifications from PRD §7 directly in
code, so it's explicit, not hidden):

```python
DETECTOR_TO_EXCEL_COLUMN = {
    "two_wheeler":         "Two Wheelers (White Plate)",   # default; Taxi split needs Phase 9
    "car_jeep_van":        "Car/Jeep/Van",
    "autorickshaw":        "Autorickshaw - 3wh",
    "bus":                 "Bus - Other Buses",             # default; operator split needs Phase 9
    "goods_auto_lcv":      "Goods Auto/LCV",
    "other_truck":         "Other Trucks",
    "agri_tractor_trailer":"Agricultural Tractor/Trailer",
    "cycle_or_pbs":        "Cycle",                          # default; PBS split needs labeled data
    "other_vehicle":       "Others",
}
```

---

## 5.5 Common beginner pitfalls

- **Movement always comes out `None`** — double check your entry/exit line pixel
  coordinates are in the same coordinate space as the video frame you're processing
  (e.g., if you calibrated on a resized/cropped frame but run inference on the original
  resolution, your lines will be in the wrong place — always calibrate on a frame at the
  exact resolution the pipeline actually processes).
- **OCR misreads digits occasionally** (e.g., reads "08" as "03")— add a sanity check: if
  a newly-read timestamp jumps backwards in time or jumps by an implausible amount versus
  the previous anchor, discard it and keep using the previous anchor + interpolation
  instead of trusting a clearly-wrong OCR read.
- **Vehicles double-counted because they cross the exit line, leave frame, then a NEW
  detection of a totally different vehicle re-uses a nearby ID** — this points back to
  Phase 4 tracker tuning; if it's frequent, tighten `lost_track_buffer` or add a max-track
  lifetime cutoff.

---

Next: open `08_Phase6_Excel_Auto_Fill_Engine.md`.
