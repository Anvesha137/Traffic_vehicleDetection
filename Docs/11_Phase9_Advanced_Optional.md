# Phase 9 (Optional) — Advanced Fine-Grained Sub-Classification

**When to do this phase:** only after Phases 0–8 are working and validated (Phase 7), and
only if the business truly needs the two hardest template splits automated:
1. Two Wheelers: **White Plate vs Taxi**
2. Bus: **BMTC vs KSRTC vs Other Buses vs Mini/Midi Bus**

Until then, per the PRD (§7) and Phase 5 (§5.4), these default to a best-guess bucket and
get flagged for human review — which is a perfectly reasonable place to stop for a long
time. Only invest in this phase if the manual-review burden on these two columns
specifically becomes a real bottleneck.

Budget: **2–4 weeks per sub-problem**, and meaningfully more labeled data than Phases 2–3
needed, because these are genuinely harder visual problems.

---

## 9.1 Two-Wheeler White Plate vs Taxi — the plate-based approach

### The core difficulty
From an elevated CCTV angle, a motorbike's number plate is a small object (often under
50×20 pixels), frequently blurred by motion, and partially obscured by the rider's leg or
the bike body. This needs a **two-stage** approach:

1. **Plate detector:** a small, separate object detector trained just to find "number
   plate" regions on two-wheelers (much narrower/easier task than general vehicle
   detection — you can bootstrap from public Indian license plate datasets on Roboflow
   Universe, searching "license plate detection India").
2. **Plate color/type classifier:** once you have a cropped plate image, run either:
   - A simple color classifier (white background = private, yellow/black = commercial
     taxi plate) — this is the easiest signal and often "good enough" if the crop is
     usable — even basic average-pixel-color heuristics can work reasonably before
     reaching for a trained classifier.
   - OR train a small CNN classifier (e.g., fine-tune a tiny ResNet) on cropped plate
     images labeled white/yellow/black if color heuristics prove unreliable.

### Realistic expectations
Given CCTV image quality, expect this sub-system to have real error, and to fail
gracefully (i.e., fall back to "White Plate" default, PRD's stated default) whenever plate
region confidence is too low, rather than guessing.

---

## 9.2 Bus Subtype — livery/branding approach

### The core difficulty
Distinguishing BMTC (Bangalore city bus, generally a distinct red/orange livery) from
KSRTC (state transport, generally a different livery) from generic "Other Buses" from
Mini/Midi buses is a **fine-grained visual classification** problem, similar in spirit to
distinguishing car brands from a photo — doable, but needs dedicated labeled examples
per subtype, and buses are relatively rare in your footage (meaning collecting balanced
training data takes patience/time — you may need to actively seek out video segments/times
known to have more bus traffic to get enough examples).

### Approach
1. Crop every "bus" detection (from your Phase 3 detector) out of your video frames.
2. Manually sort a growing collection of these crops into the 4 subtype folders
   (BMTC / KSRTC / Other / Mini-Midi) — this is a classic **image classification**
   labeling task (much simpler UI-wise than object detection — Roboflow/CVAT both support
   "classification only" projects, or even just organizing crops into folders and using a
   simple `ImageFolder`-based training script).
3. Fine-tune a small image classifier (e.g., `timm` library's pretrained EfficientNet or
   ResNet, fine-tuned on your bus crops) — this is a separate, smaller model from your
   main YOLO detector, run only on crops the detector already found.
4. Chain it into Phase 5's mapping: instead of always mapping `bus` → "Bus - Other Buses",
   run this classifier on the crop and route to the correct column based on its output
   (with a confidence threshold below which you still fall back to "Other Buses" +
   a QA flag).

---

## 9.3 PBS vs Cycle split

If Yulu (or other PBS brand) bikes are visually distinguishable by a consistent color/
branding decal in your footage, this can follow the exact same "crop + small classifier"
pattern as §9.2, trained on far fewer examples since it's a simpler 2-way split. If not
visually distinguishable at your camera's resolution, this split may not be reliably
automatable at all — be honest with stakeholders about that possibility rather than
forcing a low-confidence guess.

---

## 9.4 Should you actually build this phase?

Before investing 2–4 weeks per sub-problem, weigh it against simply **keeping these two
columns as a lightweight manual step**: your QA process (Phase 7) already flags every
bus/two-wheeler count for review — an enumerator could feasibly review just those flagged
totals per 15-min bucket (a much smaller task than full manual counting) in a fraction of
the time full manual counting takes. For many teams, this "hybrid human+AI" split is the
pragmatic long-term answer rather than chasing full automation on the hardest 2 of 15
categories. Make this a conscious, documented decision rather than a default.

---

## Final note

This completes the full plan — Phases 0 through 9. Revisit `01_PRD.md`'s deliverables
checklist periodically as you complete each phase, and don't hesitate to loop back
(Phase 2 → 3 → 7 is a normal, expected cycle, not a sign something went wrong) as real
accuracy numbers reveal where the model needs more/better labeled examples.
