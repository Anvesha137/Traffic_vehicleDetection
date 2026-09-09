# Phase 1 — Data Audit & Site Calibration

**Goal of this phase:** fully understand the exact output format you need to produce, and
create a reusable "calibration" for each unique camera view — the counting lines and
zones that later phases will use. **This phase involves zero AI/model training** — it's
pure setup, and it's the foundation everything else stands on.

**Exit criteria:** for your sample video, you have a `site_config.yaml` file describing
the camera's counting lines/zones, and you have a written mapping from Excel columns to
vehicle classes and movements.

Budget: **1–2 days** for the first site (this includes learning the tools), then
**15–30 minutes per additional new camera angle** once you're used to it.

---

## 1.1 Step 1: Confirm the Excel → data-model mapping (do this on paper/spreadsheet first)

Before writing any code, write down — literally in a notes doc — the mapping between
"what the model will produce" and "what cell that goes into." I already did this for your
two sample files; **use this as your template** and repeat it for every new site's Excel:

### `Site_15_-_Veerasandra_Main_Road.xlsx` (3-arm Turning Movement Count)

- 3 sheets = 3 physical approach roads: `Arm A`, `Arm B`, `Arm C`.
- Inside sheet `Arm A`, there are 3 column-blocks, each representing a **movement**:
  - Block 1, columns B–O → movement **A→A** (u-turn back onto A)
  - Block 2, columns R–AE → movement **A→B**
  - Block 3, columns AH–AU → movement **A→C**
- Each block has these 15 vehicle-type sub-columns, in this exact order:

| # | Column offset in block | Category | Notes |
|---|---|---|---|
| 1 | +0 | Two Wheelers (White Plate) | private motorbike/scooter |
| 2 | +1 | Two Wheelers (Taxi) | commercial bike-taxi (e.g. Rapido) |
| 3 | +2 | Car/Jeep/Van | all private 4-wheelers, single bucket |
| 4 | +3 | Autorickshaw – 3 wheeler | |
| 5 | +4 | Bus – City Bus (BMTC) | |
| 6 | +5 | Bus – (KSRTC) Bus | |
| 7 | +6 | Bus – Other Buses | |
| 8 | +7 | Bus – Mini/Midi Bus | |
| 9 | +8 | Goods Auto/LCV | light commercial vehicle |
| 10 | +9 | Other Trucks | |
| 11 | +10 | Agricultural Tractor/Trailer | |
| 12 | +11 | Cycle | |
| 13 | +12 | PBS | public bike-share e.g. Yulu |
| 14 | +13 | Others | catch-all |

- Row 7 onward = one row per **15-minute time bucket**, values in column A/Q/AG are the
  bucket start time (`8:00`, `8:15`, …). Note the sheet **skips midday** (jumps from
  10:45 straight to 16:30) — meaning surveys only cover the AM peak (8–11) and PM peak
  (16:30–19:30). **This matches your video's "8 to 11" filename.**

### `Data_Entry_Temp.xlsx` (simple gate/entrance count)

- 1 sheet, 2 column-blocks: "Towards entrance" and "Towards exit" — i.e. just an in/out
  count, no turning-movement complexity.
- Same 15 vehicle-type sub-columns and same 15-minute row structure.

**Action for you:** for every new site's Excel template you get, spend 10 minutes opening
it and writing down: how many sheets, how many movement-blocks per sheet, and confirm the
vehicle-column order matches the table above (Vtrac's templates are probably consistent,
but don't assume — verify each new file, a single shifted column silently corrupts your
entire output).

> **Tip:** don't do this by eyeballing merged cells in Excel — it's error-prone. Use the
> small Python inspection script in Appendix A at the bottom of this file; run it on any
> new Excel template and it prints the structure for you automatically.

---

## 1.2 Step 2: Understand your video's relationship to the Excel rows

Key facts about your sample video:
- Burned-in timestamp: starts at **2026-05-13 08:01:33**, resolution 1920×1080, 20fps,
  duration ~28 minutes (ends ~08:29).
- The Excel's `Arm A` sheet has AM rows from 8:00 to 10:45 (that's 3 hours = the "8 to 11"
  in the filename) — meaning **this one video is only a slice of the full 8–11 window**;
  there must be more video files (maybe 6 files of ~28 min each) that together cover
  8:00–11:00. **Confirm this with whoever gave you the files** — ask specifically:
  1. "Is one site's 8–11AM count made from multiple video files? How many, and are they
     named consistently?"
  2. "Is there a video for the PM window (16:30–19:30) too, and for each of the 3 arms
     separately, or does one camera see all 3 arms at once?"

  This matters a lot for Phase 8 (batch processing) — you need the naming convention to
  auto-sort videos into the correct site + arm + time-window.

- **Read the timestamp overlay, don't trust "video start = Excel row 1"** — because
  recording start times can drift by a few seconds/minutes from the intended schedule.
  Phase 5 will literally read the burned-in clock digits from frame images (a small OCR
  step) to align video-time to wall-clock-time with certainty, rather than assuming.

---

## 1.3 Step 3: Draw the counting lines / zones on the camera view (the actual calibration)

This is the one manual step every new camera angle needs. The idea: pick a handful of
video frames, and manually draw:

1. **One "arm entry line"** per physical road that a vehicle can arrive from — a line
   segment across the road, near the edge of frame, that a vehicle crosses when entering
   the junction from that arm.
2. **One "arm exit line"** per physical road that a vehicle can leave toward.
3. When a tracked vehicle crosses an entry line and later crosses an exit line, that
   defines its movement (e.g. entered from Arm-A-line, exited via Arm-C-line → count as
   A→C).

### How to do this practically

1. Extract a clean, representative frame from the video (no vehicles blocking the road):
   ```python
   import cv2
   cap = cv2.VideoCapture("your_video.avi")
   cap.set(cv2.CAP_PROP_POS_FRAMES, 500)   # pick a frame a few seconds in
   ok, frame = cap.read()
   cv2.imwrite("calibration_frame.jpg", frame)
   ```
2. Open `calibration_frame.jpg` in any image tool (even MS Paint / Preview) that shows
   pixel coordinates when you hover, OR use the small interactive helper script in
   Appendix B below (click-to-place points, then it prints coordinates for you — much
   easier than guessing pixels by hand).
3. For each arm, note two pixel points `(x1,y1)` and `(x2,y2)` that define the line
   across that road.
4. Save all of this into a **site config file** — this is the reusable artifact this
   whole phase produces:

```yaml
# configs/sites/site_15_veerasandra.yaml
site_name: "Site 15 - Veerasandra Main Road"
camera_id: "veerasandra_cam1"
video_resolution: [1920, 1080]
fps: 20
timestamp_overlay:
  present: true
  region_px: [10, 5, 260, 35]     # x1,y1,x2,y2 box around the burned-in clock, for OCR (Phase 5)

arms:
  A:
    entry_line: [[300, 800], [900, 950]]   # example pixel coords, replace with real ones
    exit_line:  [[300, 780], [900, 930]]
  B:
    entry_line: [[1200, 200], [1500, 400]]
    exit_line:  [[1220, 220], [1520, 420]]
  C:
    entry_line: [[50, 300], [50, 600]]
    exit_line:  [[80, 300], [80, 600]]

excel_template: "Site_15_-_Veerasandra_Main_Road.xlsx"
sheet_mapping:
  A: "Arm A"
  B: "Arm B"
  C: "Arm C"
```

> **Important honest caveat about your sample video specifically:** looking at the frame
> you gave me, the camera appears to be positioned to see mainly **one road with a
> junction visible in the distance**, plus a tree branch partly blocking the view. It is
> **not obviously showing all 3 arms of the junction from one camera.** You likely have
> *one camera per arm* (3 cameras/videos needed to fill the 3 sheets), OR this camera
> genuinely can see traffic going all 3 directions if you look at the far junction — you
> (or whoever manages the CCTV) need to confirm this before calibration, because it
> changes whether one video fills one sheet or all three. **This is the single most
> important question to resolve before writing more code — ask it now.**

---

## 1.4 Step 4: Repeat Step 3 for every unique camera angle you have

You don't need to recalibrate for every video file — only for every **unique camera
position**. If the same camera records many 28-minute segments across many days, one
calibration file covers all of them (unless the camera physically moves/gets reinstalled).

Keep a running list:
```
configs/sites/site_15_veerasandra_camA.yaml
configs/sites/site_15_veerasandra_camB.yaml
configs/sites/phase1_hp_entrance.yaml
...
```

---

## 1.5 Deliverables checklist for Phase 1

- [ ] Written column/category mapping confirmed for every distinct Excel template you have
- [ ] Answered: does one video = one arm, or one video = all arms of a junction?
- [ ] Answered: how many video files make up one full 8–11AM (or 16:30–19:30) window, and
      what's the file-naming pattern?
- [ ] One `site_config.yaml` per unique camera, with entry/exit lines drawn
- [ ] Confirmed whether the burned-in timestamp is present/readable on every camera (not
      just this one sample)

---

## Appendix A — Excel structure inspector script

Run this on any new Excel template to auto-print its structure (sheets, merged headers,
row/column layout) instead of eyeballing it:

```python
import openpyxl

def inspect(path):
    wb = openpyxl.load_workbook(path, data_only=False)
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        print(f"\n=== Sheet: {sheet} | range: {ws.dimensions} ===")
        print("Merged header cells:")
        for mc in sorted(ws.merged_cells.ranges, key=lambda r: (r.min_row, r.min_col)):
            top_left = ws.cell(mc.min_row, mc.min_col).value
            if top_left:
                print(f"  {mc}  ->  {top_left!r}")

inspect("Site_15_-_Veerasandra_Main_Road.xlsx")
```

## Appendix B — simple click-to-calibrate helper

```python
import cv2

points = []

def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        print(f"Point added: ({x}, {y})  -- total so far: {len(points)}")

img = cv2.imread("calibration_frame.jpg")
cv2.namedWindow("Click 2 points per line, press q when done", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Click 2 points per line, press q when done", on_click)

while True:
    disp = img.copy()
    for p in points:
        cv2.circle(disp, p, 6, (0, 0, 255), -1)
    cv2.imshow("Click 2 points per line, press q when done", disp)
    if cv2.waitKey(20) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
print("Final points:", points)
```

Run it, click two points for each line you need (entry/exit per arm), read the printed
coordinates, and paste them into your `site_config.yaml`.

---

Next: open `04_Phase2_Data_Collection_and_Labeling.md`.
