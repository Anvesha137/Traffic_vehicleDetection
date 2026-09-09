# Phase 4 — Multi-Object Tracking

**Goal of this phase:** turn "a detector that finds vehicles in single frames" into
"a system that follows each individual vehicle across the whole video with one stable ID,"
so that we count each real vehicle **exactly once**, not once per frame it appears in.

**Exit criteria:** running your detector + tracker together on the sample video produces
a list of tracked vehicle "tracks," each with a unique ID, a class label, and the
sequence of positions/timestamps it moved through.

Budget: **2–4 days.**

---

## 4.1 Why detection alone isn't enough (the core problem)

Your video runs at 20 frames per second. A single car crossing the visible road area over
3 seconds appears in **60 separate frames**. If we just counted every detection, that one
car would be counted 60 times, not once. We need **tracking**: recognizing "the box in
frame 100 and the box in frame 101 are the same physical vehicle, just moved slightly."

---

## 4.2 The algorithm: ByteTrack

**ByteTrack** is the current standard choice — it's fast, doesn't need its own separate
training (it works directly on top of your Phase 3 detector's output), and is built into
the `supervision` library you installed in Phase 0. In plain English, it works like this,
frame by frame:

1. Take this frame's detected boxes (from your Phase 3 model).
2. Predict where each *existing* tracked vehicle should now be, based on its recent
   motion (a simple physics-style prediction — "it was moving right at this speed, so it's
   probably a bit further right now").
3. Match new detections to existing tracks based on position overlap (and appearance, in
   fancier variants) — a matched detection updates that track; an unmatched detection
   starts a brand-new track (a vehicle just entered frame); a track with no matching
   detection for several frames in a row is considered to have left frame (or is
   temporarily hidden — see occlusion note below) and is closed.
4. ByteTrack's specific improvement over older trackers: it also tries to match
   **low-confidence** detections (which older trackers would throw away) — this helps a
   lot with partially-occluded vehicles (like ones hidden behind your sample video's tree
   branch for a few frames), because a low-confidence-but-real detection can still keep a
   track alive instead of losing it.

---

## 4.3 Code: running detection + tracking together

```python
import cv2
from ultralytics import YOLO
import supervision as sv

model = YOLO("models/vehicle_detector_v1/weights/best.pt")
tracker = sv.ByteTrack()

video_path = "E_City_Phase1_Dmart_veerasandra_8_to_11__1_.avi"
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)

# We'll store every track's history here
track_history = {}   # track_id -> list of (frame_idx, x_center, y_center, class_name)

frame_idx = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break

    results = model.predict(frame, conf=0.35, verbose=False)[0]
    detections = sv.Detections.from_ultralytics(results)

    tracked = tracker.update_with_detections(detections)

    for i in range(len(tracked)):
        track_id = int(tracked.tracker_id[i])
        x1, y1, x2, y2 = tracked.xyxy[i]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        cls_id = int(tracked.class_id[i])
        cls_name = model.names[cls_id]

        track_history.setdefault(track_id, []).append(
            {"frame": frame_idx, "cx": float(cx), "cy": float(cy), "class": cls_name}
        )

    frame_idx += 1

cap.release()
print(f"Total unique tracked vehicles: {len(track_history)}")
```

This is the **core output** Phase 5 will consume: for every unique vehicle, a timeline of
where its center point was, frame by frame, plus its class.

---

## 4.4 Deciding a track's "final class"

A vehicle might get classified slightly differently frame-to-frame (e.g. `car_jeep_van`
in most frames but `other_vehicle` in 2 blurry frames). **Don't use the last frame's
class — use the majority vote across the whole track:**

```python
from collections import Counter

def final_class_for_track(track):
    classes = [step["class"] for step in track]
    return Counter(classes).most_common(1)[0][0]
```

This single trick meaningfully improves classification accuracy for free, since it
smooths out momentary misclassifications.

---

## 4.5 Tuning ByteTrack for your occlusion problem

Your sample video has a **tree branch partially blocking part of the road** — a real
occlusion source. ByteTrack has parameters worth tuning for this:

```python
tracker = sv.ByteTrack(
    track_activation_threshold=0.25,   # lower = more willing to start/keep tracks from lower-confidence detections
    lost_track_buffer=60,               # frames to keep a track "alive" while waiting for it to reappear (60 frames = 3 sec at 20fps)
    minimum_matching_threshold=0.8,
)
```

Increase `lost_track_buffer` if you see vehicles getting a NEW id after passing behind an
obstruction (that's "ID switching" — the same physical vehicle wrongly counted as two).
Decrease it if instead you see tracks lingering/duplicating.

---

## 4.6 Validate tracking quality by eye before moving on

Draw the boxes + IDs onto the video and watch it:

```python
box_annotator = sv.BoxAnnotator()
label_annotator = sv.LabelAnnotator()

# inside your frame loop, after tracking:
labels = [f"#{tid} {cls}" for tid, cls in zip(tracked.tracker_id, [model.names[c] for c in tracked.class_id])]
annotated = box_annotator.annotate(scene=frame.copy(), detections=tracked)
annotated = label_annotator.annotate(scene=annotated, detections=tracked, labels=labels)
cv2.imwrite(f"debug_frames/frame_{frame_idx:05d}.jpg", annotated)
# or write these frames to an output video with cv2.VideoWriter to watch as a clip
```

Watch a couple of minutes of this annotated output. Ask yourself:
- Does each real vehicle keep the **same number** the whole time it's visible?
- Does the number change (ID switch) when a vehicle passes behind the tree/another
  vehicle? If yes → increase `lost_track_buffer` and re-test.
- Are there "ghost" boxes/IDs on static objects (parked vehicles, shadows)? If a track
  never moves for a long time, you can filter it out in Phase 5 (static objects shouldn't
  be counted as "passing through").

---

## 4.7 Common beginner pitfalls

- **Every vehicle gets a new ID every single frame** — you probably created a new
  `sv.ByteTrack()` inside the frame loop instead of once outside it. The tracker needs to
  persist across frames to remember previous tracks.
- **IDs jump around wildly on parked/stationary vehicles** — that's expected, ByteTrack is
  designed for moving objects; filter near-zero-motion tracks in Phase 5's aggregation
  logic (they're not "passing through" traffic anyway, so we don't want to count them).
- **Processing is very slow** — this is normal, detection+tracking on every frame of a
  full video is compute-heavy. Options: process every 2nd frame (halves work, usually
  fine since vehicles don't move far in 1/20th second `→` 1/10th second), or reduce
  `imgsz`, or move to a stronger GPU (Phase 8 covers throughput/cost planning properly).

---

Next: open `07_Phase5_Turning_Movement_Classification.md`.
