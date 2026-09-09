# Product Requirements Document (PRD)
## Automated Traffic Classified-Volume Counting System (Video → Excel)

**Doc owner:** You (Project Lead) · **Prepared by:** Claude (planning assistant)
**Status:** Draft v1 · **Last updated:** 2026-09-08

---

## 1. Problem Statement

Your team (or a vendor, "Vtrac Worldwide", per the Excel metadata) currently produces
traffic volume/classified turning-movement counts by having a human **enumerator watch
CCTV video and manually tally vehicles** into a 15-minute-interval Excel template, split
by vehicle type (15 categories) and by direction/turning-movement (up to 3 per site).

This is:
- **Slow** — a 3-hour video takes roughly 3–6 hours of a trained person's time to tally
  accurately (rewinding to double-check is common).
- **Expensive at scale** — you say "there will be multiple videos," implying many sites ×
  many time-of-day windows × multiple days. This multiplies linearly with human labor.
- **Error-prone** — fatigue, missed vehicles during dense traffic, inconsistent judgment
  calls between enumerators (e.g., is that a Goods Auto/LCV or an Other Truck?).

**Goal:** Build an ML/DL pipeline that ingests a raw traffic video and a target Excel
template, and outputs the **same Excel file, auto-filled** with vehicle counts per
15-minute bucket, per vehicle category, per direction/movement — matching (within an
agreed error tolerance) what a careful human enumerator would have written.

---

## 2. Objectives & Success Metrics

| # | Objective | Metric | Target for v1 (MVP) | Target for v2 (Production) |
|---|---|---|---|---|
| 1 | Correct total vehicle count per 15-min bucket (all classes combined) | % error vs. manual ground truth count | ≤ 15% mean absolute error | ≤ 8% |
| 2 | Correct **coarse** vehicle classification (Two-Wheeler / Car / Bus / Truck / Auto / Cycle) | Per-class F1 score | ≥ 0.80 | ≥ 0.90 |
| 3 | Correct **fine-grained** classification (all 15 template columns) | Per-class F1 score | ≥ 0.55 (some classes intentionally deferred, see §7) | ≥ 0.75 |
| 4 | Correct turning-movement assignment (A→A/A→B/A→C) | % of tracked vehicles assigned to correct movement | ≥ 80% | ≥ 92% |
| 5 | No double counting / missed counting due to tracking failure | ID-switch rate | ≤ 10% of vehicles | ≤ 5% |
| 6 | Time to process 1 hour of video | Wall-clock processing time | ≤ 30 min on 1 GPU | ≤ 10 min on 1 GPU (batch) |
| 7 | Excel output matches template exactly (cell positions, formatting untouched) | Manual spot check | 100% | 100% |
| 8 | System scales to N videos/sites without manual re-work per video | Config-only onboarding of a new site | New site onboarded in ≤ 1 hour of human setup | ≤ 15 min |

We are optimizing for **directional accuracy trusted enough to replace a first-pass human
count, with a human doing spot-check QA**, not "perfect, zero-touch automation" in v1.
That is a realistic, honest bar for a first ML system on this kind of task — even
commercial products in this space (traffic AI vendors) report similar accuracy bands.

---

## 3. Users & Use Cases

- **Primary user:** You / your data-entry or traffic-survey team. Instead of watching
  video and typing numbers, they will: (a) drop new videos into a folder, (b) run the
  pipeline, (c) review a QA report, (d) spot-check a few low-confidence intervals, (e)
  accept the auto-filled Excel.
- **Secondary user:** whoever consumes the final Excel reports (client, government body,
  planning team) — they should not be able to tell the difference from a hand-filled sheet.

---

## 4. Scope

### In scope (v1)
- Processing videos with a **static, non-moving CCTV/dashcam-style camera** covering one
  approach/arm, similar in style to the sample video (elevated angle, burned-in timestamp
  helpful but not required).
- Detecting and classifying vehicles into the 15 template categories (with graceful
  fallback to "Others" or a coarser category when confidence is low — see §7).
- Assigning each vehicle to the correct 15-minute time bucket using either the burned-in
  video timestamp (preferred) or file-start-time + frame count (fallback).
- Assigning turning movement (which arm the vehicle exits toward) for junction-style
  sheets, and simple in/out direction for gate-style sheets (`Data_Entry_Temp.xlsx`).
- Writing results into a **copy** of the existing `.xlsx` template, preserving all
  existing formatting, merged cells, and headers — only the numeric cells change.
- Batch processing many videos across many sites via a config file (no code changes
  needed to add a new site/video).

### Out of scope (v1) — explicitly deferred
- Real-time/live-stream processing (we assume recorded video files, processed after the
  fact — this matches your use case).
- Automatic detection of the **number plate color/type** for the Two-Wheeler
  "White Plate" vs "Taxi" split, and the **bus operator livery** for
  BMTC/KSRTC/Other/Mini-Midi — these require plate OCR / logo recognition which is a
  meaningfully harder sub-problem. v1 will output a best-effort default and flag these
  cells for manual review (full detail in Phase 9 / §7 below).
- Camera auto-calibration (v1 requires ~10–20 minutes of one-time manual setup per unique
  camera view — drawing the counting lines. This is a very common, accepted trade-off in
  this industry).
- Mobile app / non-technical UI (v1 is a command-line / script-driven pipeline; a simple
  UI can be a v2 nice-to-have).

---

## 5. Non-Functional Requirements

- **Reproducibility:** Same video in → same Excel out, every run (deterministic given a
  fixed model + fixed calibration).
- **Auditability:** For every filled cell, we can show *which* video frames / tracked
  vehicle IDs contributed to that count, so a human can verify disagreements.
- **Portability:** Should run on a single machine with one consumer/prosumer GPU
  (e.g., an RTX 3060/4060 or a cloud GPU instance) — no need for a data-center cluster.
- **Cost-awareness:** Processing cost per hour of video should be estimated and tracked
  (Phase 8 covers this in detail — cloud GPU rental vs. one-time GPU purchase).

---

## 6. Assumptions

1. You have access to (or can obtain) **more example videos with matching manually-filled
   Excel sheets** — these are your "ground truth" / labeled data, essential for training
   and validating the model. (If Vtrac Worldwide has historical filled sheets + matching
   videos, that is gold — reuse them; see Phase 2.)
2. Each unique camera position needs to be "calibrated" once (Phase 1) — a video from a
   brand-new camera angle at a brand-new site cannot be processed with zero setup.
3. Videos have reasonably consistent daytime lighting (traffic-survey convention is to
   record during daylight hours, matching your 8:00–19:15 rows). Night-time/low-light
   video is out of scope for v1 unless you tell me otherwise.
4. The burned-in timestamp overlay (seen in your sample video) is either present, or the
   video's recording start time is otherwise known/derivable from the filename or
   metadata (your filename `..._8_to_11...` suggests a naming convention we can parse).

## 7. Known Hard Constraints (read this — sets honest expectations)

These template requirements are **materially harder than "detect a vehicle"** and deserve
explicit callouts so nobody is surprised later:

| Requirement | Why it's hard | v1 handling |
|---|---|---|
| Two Wheelers: White Plate vs Taxi | Needs number-plate color/text OCR at long range, tiny objects, motion blur | Default all two-wheelers to "White Plate"; log a confidence flag; optional Phase 9 add-on model later |
| Bus: BMTC vs KSRTC vs Other vs Mini/Midi | Needs livery/logo/color recognition, buses are infrequent so little training data | Classify generically as "Bus", route to "Other Buses" column by default, flag for QA; optional Phase 9 add-on |
| Distinguishing Goods Auto/LCV vs Other Trucks vs Agricultural Tractor/Trailer | All are visually similar mid-size vehicles from an elevated CCTV angle, low sample counts | Train a dedicated fine-tuned classifier with as many real examples as we can label (Phase 2); accept lower F1 target here (§2) |
| Occlusion by trees/poles/other vehicles (visible in your sample frame) | Vehicles can be hidden for several frames, confusing the tracker | Use a robust tracker (ByteTrack) tuned for short occlusions (Phase 4); accept it as a source of count error, quantify it in QA (Phase 7) |
| PBS (bike share, e.g. Yulu) vs Cycle | Visually near-identical (both are pedal/e-bikes) unless branding is visible | Merge into a single detector class initially, only split if you can supply labeled examples |

None of these block starting the project — they just mean v1 will be **"very good, not
perfect,"** with a clear upgrade path (Phase 9) once the core pipeline works and you
decide it's worth the extra investment.

---

## 8. High-Level Architecture

```
                 ┌────────────────────────┐
  Raw video ───▶ │ Phase 1: Calibration    │  (one-time per camera)
  file(s)        │  (counting lines/zones) │
                 └───────────┬─────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ Phase 3: Detector       │  finds + classifies every
                 │  (YOLOv8, fine-tuned)   │  vehicle in every frame
                 └───────────┬─────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ Phase 4: Tracker        │  gives each vehicle one
                 │  (ByteTrack)            │  persistent ID over time
                 └───────────┬─────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ Phase 5: Movement logic │  line-crossing → which
                 │  (geometry + timestamp) │  arm, which 15-min bucket
                 └───────────┬─────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ Phase 6: Excel writer   │  fills the .xlsx template
                 └───────────┬─────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ Phase 7: QA report      │  confidence + accuracy
                 └────────────────────────┘
```

Phase 8 wraps all of this into a **batch pipeline** that runs it automatically across
every video for every site, and Phase 9 is the optional accuracy-boosting add-on layer.

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Not enough labeled training data for rare classes (tractor, PBS) | High | Medium | Use pretrained models + data augmentation + active learning (label the cases the model is least sure about first — Phase 2/7) |
| Camera angle differs a lot site-to-site, hurting generalization | High | Medium | Fine-tune per-camera-family if needed; keep calibration modular (Phase 1) |
| Occlusion/tree branches cause tracker to lose vehicles | Medium | Medium | Tune tracker patience, validate against manual counts, accept documented error margin |
| Team member(s) new to ML get stuck on setup | Medium | Low | Phase 0 is deliberately over-explained with copy-paste commands |
| Vendor (Vtrac) sheet format changes between sites | Medium | Medium | Phase 6 Excel writer is template-driven (reads column headers, not hardcoded positions) |

---

## 10. Deliverables Checklist (what "done" looks like)

- [ ] A working Python pipeline: `video.mp4/.avi` + `site_config.yaml` → filled `.xlsx`
- [ ] A trained, versioned detection/classification model (`.pt` weights file)
- [ ] A calibration tool/format so any new camera can be onboarded quickly
- [ ] A QA/validation report generator comparing model output vs. manual ground truth
- [ ] Documentation (this plan) + a runbook for adding a new site
- [ ] A batch runner that can process a folder of many videos unattended

---

Next: open `02_Phase0_Environment_Setup.md`.
