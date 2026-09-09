# Phase 2 — Training Data Collection & Labeling

**Goal of this phase:** produce a set of labeled images (frames with boxes drawn around
each vehicle, and a category assigned to each box) that we will use in Phase 3 to
teach/fine-tune the AI model. **This is the most time-consuming manual phase, but also the
one that most determines your final accuracy** — a great model with bad labels performs
worse than an OK model with great labels.

**Exit criteria:** you have 800–3,000+ labeled vehicle examples across a good variety of
frames, exported in a format YOLO can train on.

Budget: **1–3 weeks**, largely depending on how much you can parallelize labeling across
people, and whether you can reuse an existing labeled traffic dataset to cut this down
(see 2.4 — strongly recommended for a beginner).

---

## 2.1 Why you can't skip this even though "AI already knows what a car looks like"

Off-the-shelf object detectors (like YOLO pretrained on the COCO dataset) already know
generic categories: "car," "truck," "bus," "motorcycle," "bicycle," "person." That's
useful, but your Excel template needs **finer categories that COCO does not have**:
Autorickshaw, Goods Auto/LCV vs Other Trucks, Agricultural Tractor, PBS vs Cycle, and (as
covered in the PRD) plate-type/bus-operator splits. So we must **fine-tune** — take a
pretrained model and continue training it on examples labeled with YOUR categories.

---

## 2.2 Decide your class list (do this once, use everywhere downstream)

Based on the Excel template, here is the recommended **detector class list** — note we
deliberately do NOT try to detect "White Plate vs Taxi" or "BMTC vs KSRTC" at this stage
(per PRD §7, those go in Phase 9 as a separate, optional add-on):

```
0 two_wheeler
1 car_jeep_van
2 autorickshaw
3 bus
4 goods_auto_lcv
5 other_truck
6 agri_tractor_trailer
7 cycle_or_pbs
8 other_vehicle
```

That's **9 classes** — manageable for a first model, and every one of them maps directly
or near-directly to your Excel columns (with the plate/bus-subtype/PBS splits handled by
simple post-processing rules or optional Phase 9 models later, not by asking this one
detector to do everything).

> **Beginner tip:** resist the urge to make 15+ classes from day one. Fewer, more visually
> distinct classes → the model learns faster and more reliably with less data. You can
> always split a class later once you have more labeled examples for it.

---

## 2.3 Extract candidate frames from your videos

You don't need to label every frame (that would be 33,907 frames for just your one
sample video — way too many, and consecutive frames are nearly identical anyway).
Instead, **sample frames spread across time and traffic conditions**:

```python
import cv2, os

def extract_frames(video_path, out_dir, every_n_seconds=5):
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * every_n_seconds)
    idx, saved = 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % frame_interval == 0:
            fname = os.path.join(out_dir, f"frame_{idx:06d}.jpg")
            cv2.imwrite(fname, frame)
            saved += 1
        idx += 1
    cap.release()
    print(f"Saved {saved} frames to {out_dir}")

extract_frames("E_City_Phase1_Dmart_veerasandra_8_to_11__1_.avi", "data/frames/site15", every_n_seconds=5)
```

For your ~28-minute sample video, `every_n_seconds=5` gives ~336 candidate frames. Do
this across **several different videos/times of day** (morning light vs evening light,
light traffic vs heavy traffic) so the model sees variety, not just one lighting
condition.

**Rule of thumb target:** aim for enough frames that, after labeling, you have **at least
80–150 labeled examples of your rarest class** (probably Agricultural Tractor, PBS, or
Bus). Common classes (two-wheeler, car) will naturally rack up thousands of examples
because they appear constantly — that's fine and good.

---

## 2.4 Strongly consider bootstrapping with an existing dataset first

Before hand-labeling everything from scratch, check these public sources — using them can
cut your labeling time by 50%+ because you start from a model that already understands
"Indian road vehicle" shapes, and you only need to label enough of YOUR footage to adapt
it, not teach it from zero:

- **IDD (India Driving Dataset)** — indiandrivingdataset.org — real Indian road scenes,
  includes autorickshaw, truck, and other India-specific classes.
- **Roboflow Universe** (universe.roboflow.com) — search "Indian traffic," "autorickshaw
  detection," "vehicle classification India" — many public, pre-labeled datasets you can
  download in YOLO format directly, some specifically for CCTV-angle traffic counting.
- **UA-DETRAC / BDD100K / COCO vehicles subset** — good for generic car/bus/truck/bike
  classes to pretrain on before fine-tuning on your specific footage.

**Recommended approach for a beginner:** download 1–2 relevant Roboflow datasets, fine-
tune a first model on that public data (Phase 3), then use that model to **pre-label your
own frames automatically** (it will get many boxes right, some wrong), and your labeling
job becomes "correcting the AI's guesses" instead of "drawing every box from scratch" —
much faster. This technique is called **model-assisted labeling** and is standard
practice.

---

## 2.5 Labeling tool: use Roboflow or CVAT (don't build your own)

Two good free options for a beginner, both let multiple people label collaboratively in
a browser:

### Option A — Roboflow (easiest to start, has a generous free tier)
1. Go to https://roboflow.com, create a free account, create a new project (type:
   Object Detection).
2. Upload your extracted frames (from 2.3).
3. Define your 9 classes (from 2.2) in the project settings.
4. Use the built-in annotation tool — click-drag a box around each vehicle, pick its
   class from a dropdown. Roboflow also has an "Auto Label" / model-assisted feature
   (once you have a first trained model) — huge time saver, see 2.4.
5. When done, click **Export Dataset → YOLOv8 format** — Roboflow generates the exact
   folder structure and `data.yaml` file Phase 3 needs, automatically.

### Option B — CVAT (self-hosted, more control, steeper setup)
1. https://www.cvat.ai — free hosted version available, or self-host via Docker if you
   want full data privacy (recommended if your videos are sensitive/client-confidential).
2. Create a task, upload frames, define labels, annotate the same way.
3. Export in "YOLO 1.1" format.

> **Privacy note:** if these traffic videos are under client confidentiality, prefer
> **self-hosted CVAT** (Docker, runs on your own machine/server) over any cloud tool, or
> check Roboflow's private-workspace/enterprise data terms before uploading client video
> frames.

---

## 2.6 Labeling guidelines (write these down and share with anyone else labeling)

Consistency between labelers matters more than perfection by any one labeler. Agree on
rules like:

- **Box tightness:** box should hug the visible vehicle body, not include shadow.
- **Partially visible vehicles** (cut off by frame edge or occluded by the tree branch in
  your sample video): label them anyway if more than ~40% of the vehicle is visible;
  otherwise skip.
- **Class-confusion rules** (write your own, but examples):
  - A pickup truck carrying goods with an open flatbed, under ~2 tons → `goods_auto_lcv`.
  - Anything clearly bigger / multi-axle truck → `other_truck`.
  - A three-wheeled cargo vehicle → still `autorickshaw` if passenger-style, or
    `goods_auto_lcv` if clearly a cargo mini-truck (Tata Ace-style small trucks look
    similar to LCVs and are commonly confused with goods autos — pick one convention and
    be consistent).
  - E-bikes/mopeds with pedals → `cycle_or_pbs`; anything with only a motor and no pedals
    → `two_wheeler`.
- Keep a shared doc/spreadsheet of "edge case → decision" as you encounter them, so
  labeling stays consistent across days/people.

---

## 2.7 Split your labeled data

Once labeling is done, split into:
- **Train set (70%)** — what the model learns from.
- **Validation set (20%)** — used during training to check progress without cheating.
- **Test set (10%)** — touched only once, at the very end, for an honest final accuracy
  number (Phase 7).

Roboflow/CVAT can do this split for you automatically on export — just make sure the
split is **randomized across different source videos/times of day**, not all from one
5-minute clip (otherwise your validation score will look great but not reflect reality).

---

## 2.8 Deliverables checklist for Phase 2

- [ ] Final class list decided and documented (§2.2)
- [ ] Frames extracted from a representative variety of videos/lighting/traffic density
- [ ] Labeling tool set up (Roboflow or CVAT)
- [ ] At least 800–3,000 labeled vehicle boxes, with rarer classes deliberately
      oversampled
- [ ] Written labeling guideline doc for consistency
- [ ] Data exported in YOLO format, split into train/val/test

---

Next: open `05_Phase3_Vehicle_Detection_Model.md`.
