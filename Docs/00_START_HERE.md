# START HERE — Traffic Video → Excel Auto-Fill ML Project

Welcome. This folder contains a **complete, beginner-friendly implementation plan** for
building a Machine Learning / Deep Learning system that watches traffic-survey videos
(like the one you uploaded) and automatically fills in the Excel count sheets (like the
ones you uploaded), instead of a human enumerator counting vehicles by hand.

You said you are new to ML/DL — so this plan is written so that **someone who has never
trained a model before can still follow it end‑to‑end**, phase by phase, without getting lost.

---

## What you gave me (and what I found)

I actually opened your files. Here's what they contain, in plain English:

### 1. The video — `E_City_Phase1_Dmart_veerasandra_8_to_11__1_.avi`
- Fixed CCTV camera, **1920×1080**, **20 frames/second**, **~28 minutes long**
- Has a **burned-in timestamp** in the top-left corner (e.g. `2026-05-13 08:01:33`) — this
  is extremely useful, it means we can align every second of footage with an exact clock
  time, which is exactly what the Excel sheet needs (15-minute time buckets).
- It shows a road/junction from an elevated angle — two-wheelers, cars, autos, a truck,
  pedestrians, and a tree branch that partially blocks part of the view.
- The filename says "8 to 11" (8AM–11AM) but the actual file is only ~28 minutes. That
  strongly suggests: **the full survey is recorded as many short video segments**, and
  you will feed the model dozens/hundreds of clips like this one, not just one.

### 2. `Site_15_-_Veerasandra_Main_Road.xlsx`
This is a **Turning Movement Count (TMC) sheet** for a 3-legged road junction:
- 3 sheets: `Arm A`, `Arm B`, `Arm C` — one per approach road into the junction.
- Inside **each** sheet, there are **3 sub-blocks**: e.g. inside "Arm A" you have
  `A-A`, `A-B`, `A-C` — meaning "vehicles that came from Arm A and went towards Arm A
  (U-turn), towards Arm B, or towards Arm C." This is called a **turning movement**.
- Each sub-block has **15 vehicle-type columns**:
  `Two Wheelers (White Plate)`, `Two Wheelers (Taxi)`, `Car/Jeep/Van`,
  `Autorickshaw-3wh`, `Bus – City Bus (BMTC)`, `Bus – KSRTC`, `Bus – Other Buses`,
  `Bus – Mini/Midi Bus`, `Goods Auto/LCV`, `Other Trucks`,
  `Agricultural Tractor/Trailer`, `Cycle`, `PBS` (public bike share, e.g. Yulu),
  `Others`.
- Each row is a **15-minute time bucket** (8:00, 8:15, 8:30 … skips midday … 16:30 … 19:15).
- So one sheet = 3 movements × 15 vehicle types × ~26 time rows = **~1,170 numbers to fill in**,
  and you have 3 sheets (Arm A/B/C) per site.

### 3. `Data_Entry_Temp.xlsx`
A simpler version of the same idea — a single entrance/exit gate count (e.g. a mall/HP
office driveway), 2 directions (in/out), same 15 vehicle-type columns, same 15-min buckets.
No turning movements here — simpler.

**Bottom line:** this is a genuinely well-known, real-world problem called **automated
traffic counting & classification from CCTV**. It is solvable with today's ML/DL tools,
but it is not a "run one script" job — it has real engineering steps. This plan breaks it
into phases so nothing feels overwhelming.

---

## How the whole system will work (one-paragraph summary)

1. A **detector** model looks at every video frame and draws a box around every vehicle
   and says what type it roughly is (two-wheeler, car, bus, truck, etc.).
2. A **tracker** follows each box across frames so the same physical vehicle keeps one ID
   as it moves through the video (so we don't count it 30 times as it crosses 30 frames).
3. We draw **virtual lines** on the video (once, per camera) that mark "this is Arm A
   entrance", "this is Arm B exit", etc. When a tracked vehicle's path crosses a line, we
   know which movement it made (A→B, A→C, etc.) and at what exact timestamp.
4. We bucket that timestamp into the correct 15-minute row and vehicle-type column, and
   **increment a counter**.
5. At the end of a video, we **write the counters into the Excel file**, in the exact same
   cells your enumerators currently fill in by hand.
6. We repeat this for every video, for every site, automatically.

---

## The phases (read/do them in this order)

| File | Phase | What you'll build |
|---|---|---|
| `01_PRD.md` | — | The full Product Requirements Document — read this first |
| `02_Phase0_Environment_Setup.md` | Phase 0 | Your computer/cloud setup, installing Python & tools |
| `03_Phase1_Data_Audit_and_Site_Calibration.md` | Phase 1 | Understand your data fully + draw counting lines on each camera |
| `04_Phase2_Data_Collection_and_Labeling.md` | Phase 2 | Turn video frames into labeled training examples |
| `05_Phase3_Vehicle_Detection_Model.md` | Phase 3 | Train the AI model that finds & classifies vehicles |
| `06_Phase4_Multi_Object_Tracking.md` | Phase 4 | Make the model track vehicles instead of just spotting them |
| `07_Phase5_Turning_Movement_Classification.md` | Phase 5 | Decide which "arm" each vehicle went to |
| `08_Phase6_Excel_Auto_Fill_Engine.md` | Phase 6 | Auto-write results into your exact Excel template |
| `09_Phase7_Validation_and_QA.md` | Phase 7 | Prove the model is accurate enough to trust |
| `10_Phase8_Scaling_Multi_Site_Pipeline.md` | Phase 8 | Run this on hundreds of videos/sites automatically |
| `11_Phase9_Advanced_Optional.md` | Phase 9 (optional) | Hard extras: bus-company sub-type, number-plate-taxi detection |

**Do not skip Phase 1.** Everything downstream depends on it, and it's the one phase that
is NOT really "ML" — it's just careful setup, so it's a good confidence-building start.

---

## Time & difficulty, honestly

- If you are doing this **solo, self-taught, evenings/weekends**: expect **2.5–4 months**
  to get a working, reasonably accurate v1.
- If you have **1 ML engineer full-time**: expect **4–6 weeks** to a working v1, plus
  ongoing tuning per new site.
- The hardest parts (be mentally prepared) are: (a) getting the fine-grained vehicle
  categories right — some are visually very similar (Goods Auto/LCV vs Other Trucks vs
  Tractor), and (b) the turning-movement line-crossing logic when the camera angle is bad
  or vehicles are occluded by the tree/other vehicles.
- The **plate-type split** (Two Wheelers "White Plate" vs "Taxi") is the single hardest
  requirement in your template — I flag exactly how to handle it in Phase 9.

Open `01_PRD.md` next.
