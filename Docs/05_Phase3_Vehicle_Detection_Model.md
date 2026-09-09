# Phase 3 — Vehicle Detection & Classification Model

**Goal of this phase:** train (fine-tune) an AI model that, given one video frame, draws a
box around every vehicle and labels it with one of your 9 classes from Phase 2.

**Exit criteria:** a trained model file (`best.pt`) that reaches acceptable accuracy on
your validation set (see targets below), and you understand how to run it on a new image.

Budget: **3–7 days**, mostly waiting for training runs + iterating.

---

## 3.1 The model we'll use: YOLOv8 (or YOLO11) via Ultralytics

**Why YOLO:** it's the industry-standard, well-documented, actively maintained, easy-to-
use object detector family. It detects *and* classifies in one pass, runs fast enough for
practical video processing, and the `ultralytics` Python package (installed in Phase 0)
makes training a fine-tune literally a few lines of code — perfect for a beginner.

**What "fine-tuning" means, in plain English:** YOLO ships with weights already trained
on millions of general images (COCO dataset — 80 everyday object classes). Those weights
already "know" what edges, wheels, windows, and vehicle shapes generally look like. We
don't start from zero — we take those weights and keep training, but now showing it only
your images with your 9 specific classes, so it *adapts* its existing vehicle-shape
knowledge to your finer categories. This needs far less data and time than training from
scratch.

---

## 3.2 Prepare the `data.yaml` config

If you used Roboflow's export (Phase 2), this file is generated for you automatically.
If building manually, it looks like:

```yaml
# data.yaml
path: /full/path/to/data
train: images/train
val: images/val
test: images/test

names:
  0: two_wheeler
  1: car_jeep_van
  2: autorickshaw
  3: bus
  4: goods_auto_lcv
  5: other_truck
  6: agri_tractor_trailer
  7: cycle_or_pbs
  8: other_vehicle
```

Folder structure expected:
```
data/
├── images/
│   ├── train/   (your .jpg frames)
│   ├── val/
│   └── test/
└── labels/
    ├── train/   (matching .txt files, one per image, YOLO format)
    ├── val/
    └── test/
```
Each label `.txt` file has one line per box:
`class_id  x_center  y_center  width  height`  (all values normalized 0–1 relative to
image size — Roboflow/CVAT export this automatically, you never write it by hand).

---

## 3.3 Train the model

```python
from ultralytics import YOLO

# Start from a pretrained small model (fast to train, good for a first pass)
model = YOLO("yolov8s.pt")   # 's' = small. Options: n (nano, fastest) / s / m / l / x (biggest, most accurate)

results = model.train(
    data="data.yaml",
    epochs=100,          # how many full passes over the training data
    imgsz=960,            # input image size — CCTV vehicles are often small/far, so use a larger size than the 640 default
    batch=16,              # lower this (e.g. 8 or 4) if you get "out of memory" errors
    patience=20,           # stop early if no improvement for 20 epochs (saves time)
    project="models",
    name="vehicle_detector_v1",
)
```

Run this with:
```bash
python train.py
```

**What happens:** Ultralytics prints a live-updating table each epoch showing loss values
going down and accuracy metrics (mAP) going up. This can take **anywhere from 30 minutes
to several hours** depending on dataset size and your GPU. Let it run — go do Phase 4
reading while you wait.

### Which size model to pick, as a beginner
- Start with **`yolov8s.pt`** (small) — good balance of speed/accuracy, trains fast
  enough to iterate.
- If accuracy isn't good enough after your first full loop through Phases 3→7, and you
  have GPU time to spare, try `yolov8m.pt` (medium) for a bump in accuracy at the cost of
  slower training/inference.

---

## 3.4 Read your results

After training, Ultralytics saves everything to `models/vehicle_detector_v1/`, including:
- `weights/best.pt` — the actual trained model file, your main deliverable.
- `results.png` — graphs of loss and accuracy over training — loss lines should trend
  downward and flatten out; if they're still dropping fast at epoch 100, train longer.
- A confusion matrix image — shows which classes get mixed up with which (this is exactly
  where you'll SEE things like "goods_auto_lcv often confused with other_truck," matching
  the PRD's honest expectation in §7).

**Key metric to look at:** `mAP50-95` (mean Average Precision) — a combined
detection+classification accuracy score from 0 to 1. As a rough beginner benchmark:
- Below 0.3 → something is likely wrong (bad labels, too little data, wrong classes) —
  debug before continuing.
- 0.3–0.5 → workable first version, expect real errors in production, good enough to
  move forward and improve iteratively.
- 0.5–0.7 → solid, matches PRD v1 targets.
- 0.7+ → excellent, matches PRD v2 targets.

---

## 3.5 Test it on a real frame from your sample video

```python
from ultralytics import YOLO

model = YOLO("models/vehicle_detector_v1/weights/best.pt")

results = model.predict(
    source="calibration_frame.jpg",
    conf=0.35,     # confidence threshold — lower catches more vehicles but more false positives
    save=True       # saves an annotated image with boxes drawn, so you can eyeball it
)

for box in results[0].boxes:
    cls_id = int(box.cls[0])
    conf = float(box.conf[0])
    print(model.names[cls_id], f"{conf:.2f}")
```

Open the saved annotated image and **look at it yourself** — this "eyeball test" catches
obvious problems (e.g. every two-wheeler mislabeled as a bicycle) far faster than staring
at metric numbers.

---

## 3.6 Iterate

Your first training run will not be perfect. Standard iteration loop:
1. Run the model on frames it hasn't seen (from a different video/time of day).
2. Find & note mistakes (missed vehicles, wrong class, false detections on shadows/trees).
3. Add 50–150 more labeled examples specifically covering those mistake types (this is
   the "model-assisted labeling" workflow from Phase 2 §2.4 — use the current model to
   pre-label, then you just fix its mistakes, much faster than labeling from scratch).
4. Re-train (you can continue from your last checkpoint instead of starting over —
   `model = YOLO("models/vehicle_detector_v1/weights/best.pt")` then call `.train()`
   again with the expanded dataset).
5. Repeat until validation metrics meet the PRD targets (§2 in the PRD doc).

---

## 3.7 Common beginner pitfalls

- **Training accuracy looks great, but real-world video performance is bad** — classic
  sign that your train/val frames were too similar (e.g. all from one 5-minute clip).
  Go back to Phase 2 and get more variety.
- **Every prediction says "car"** — check your label files aren't all secretly the same
  class ID (an export/mapping bug), and check your `data.yaml` class order matches your
  label files' class order exactly.
- **Small/far-away vehicles never get detected** — increase `imgsz` (image size) during
  training and inference, e.g. from 640 to 960 or even 1280 (costs more GPU
  memory/time, but CCTV footage often has genuinely small objects far from camera).
- **Out of memory error during training** — lower `batch` size (try 8, then 4).

---

Next: open `06_Phase4_Multi_Object_Tracking.md`.
