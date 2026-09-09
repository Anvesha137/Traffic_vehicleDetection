# Phase 8 — Scaling to Multiple Videos & Sites

**Goal of this phase:** turn your working single-video pipeline (Phases 1–7) into an
unattended batch system that can process **many videos across many sites** automatically,
since you told me "there will be like multiple videos." This is where the project goes
from "a script I run by hand" to "a system my team relies on."

**Exit criteria:** you can drop a folder of new videos + a config file into the system,
walk away, and come back to filled Excel files + QA reports for every one of them.

Budget: **1–2 weeks**, plus ongoing small effort (~15–30 min) per brand-new camera site.

---

## 8.1 Standardize your inputs

Two things every batch run needs, decided once and enforced going forward:

1. **A consistent video file naming/foldering convention.** Based on your sample filename
   (`E_City_Phase1_Dmart_veerasandra_8_to_11__1_.avi`), propose something like:
   ```
   data/raw_videos/
     <site_id>/
       <camera_id>/
         <YYYY-MM-DD>/
           <window_start>-<window_end>_<segment_number>.avi
   ```
   e.g. `data/raw_videos/site15/camA/2026-05-13/0800-1100_1.avi`. Agree this with
   whoever supplies the videos (matches the open question flagged in Phase 1 §1.2).

2. **A site registry file** — one place listing every site and which calibration config
   (Phase 1) and Excel template it maps to:

```yaml
# configs/site_registry.yaml
site15:
  name: "Site 15 - Veerasandra Main Road"
  cameras:
    camA:
      config: configs/sites/site_15_veerasandra_camA.yaml
      arm: A
    camB:
      config: configs/sites/site_15_veerasandra_camB.yaml
      arm: B
    camC:
      config: configs/sites/site_15_veerasandra_camC.yaml
      arm: C
  excel_template: data/raw_excels/Site_15_-_Veerasandra_Main_Road.xlsx

phase1_hp_entrance:
  name: "Phase 1 HP Entrance"
  cameras:
    gate1:
      config: configs/sites/phase1_hp_entrance.yaml
      arm: gate
  excel_template: data/raw_excels/Data_Entry_Temp.xlsx
```

---

## 8.2 The batch runner

```python
import os, glob, yaml
from pathlib import Path

def run_pipeline_on_video(video_path, site_config, model, tracker_factory):
    """Wraps everything from Phases 3-6 into one function call."""
    # 1. Load calibration (Phase 1)
    # 2. Detect + track (Phase 3 + 4)
    # 3. Classify movement + time bucket (Phase 5)
    # 4. Write/accumulate into Excel (Phase 6)
    # 5. Generate QA flags (Phase 7)
    # Returns: (output_excel_path, qa_flags)
    ...

def batch_run(site_registry_path, raw_videos_dir, output_dir):
    with open(site_registry_path) as f:
        registry = yaml.safe_load(f)

    all_reports = []
    for site_id, site in registry.items():
        for cam_id, cam in site["cameras"].items():
            with open(cam["config"]) as f:
                site_config = yaml.safe_load(f)

            video_files = sorted(glob.glob(f"{raw_videos_dir}/{site_id}/{cam_id}/**/*.avi", recursive=True))
            print(f"[{site_id}/{cam_id}] found {len(video_files)} video segments")

            output_excel = f"{output_dir}/{site_id}_filled.xlsx"
            # First run for this site copies the template; subsequent segment runs
            # accumulate into the same output file (Phase 6 §6.4's "add" behavior)
            if not os.path.exists(output_excel):
                import shutil
                shutil.copy(site["excel_template"], output_excel)

            for video_path in video_files:
                qa_flags = run_pipeline_on_video(video_path, site_config, model=..., tracker_factory=...)
                all_reports.append({"video": video_path, "site": site_id, "flags": qa_flags})
                print(f"  processed {Path(video_path).name} -> flags: {qa_flags or 'none'}")

    return all_reports

if __name__ == "__main__":
    reports = batch_run("configs/site_registry.yaml", "data/raw_videos", "outputs/filled_excels")
    # Save a combined QA summary for human review
    import json
    with open("outputs/qa_summary.json", "w") as f:
        json.dump(reports, f, indent=2, default=str)
```

Run the whole thing with a single command:
```bash
python src/batch_runner.py
```

---

## 8.3 Onboarding a brand-new site (the repeatable "add a site" checklist)

Once the batch system exists, adding a new site should be fast and code-free:
1. Get the new site's blank Excel template → save into `data/raw_excels/`.
2. Get one representative video from the new camera → run the Phase 1 calibration steps
   (extract a frame, draw entry/exit lines, note the timestamp overlay region) → save the
   new `site_config.yaml`.
3. Add an entry to `site_registry.yaml`.
4. Drop the videos into the standard folder structure.
5. Run `batch_runner.py`.

No changes to detection/tracking/writer code needed — this is exactly why Phases 1 and 6
were built to be **config-driven and template-reading**, not hardcoded to your one sample
site.

---

## 8.4 Performance & cost planning

Rough throughput math to set expectations (adjust once you've measured your actual GPU):
- A mid-range GPU (e.g. RTX 3060 / cloud T4) typically processes YOLO detection at
  roughly 30–60 frames/second at 960px input size, before tracking overhead.
- At 20fps source video, that's **1.5x–3x real-time** — a 28-minute video segment might
  take roughly **10–20 minutes** to fully process (detection+tracking+classification).
  Measure this yourself early and update your planning — don't assume, verify on your
  actual hardware with a stopwatch on a full sample video.
- If you have **hundreds of video segments across many sites**, consider:
  - Processing every 2nd frame instead of every frame (near-halves time, usually
    acceptable — vehicles don't move far between two 1/20-sec frames).
  - Running multiple videos in parallel on one GPU (batch multiple frames together) or
    across multiple cloud GPU instances if you're on a deadline.
  - Cloud GPU rental cost example: a $0.40–$0.80/hour GPU instance processing ~3 hours of
    footage per GPU-hour → a rough back-of-envelope cost per hour of source video of well
    under $1, dramatically cheaper than the equivalent hours of manual counting labor —
    make this comparison explicitly to justify the project's ROI to stakeholders.

---

## 8.5 Monitoring over time

Once running regularly, track (in a simple spreadsheet or dashboard):
- Number of videos processed per week/site.
- QA flag rate over time (should trend down as calibration/model improves, or up if
  something breaks — e.g. a camera got physically bumped/repositioned, invalidating its
  calibration lines — this is a real, common failure mode, watch for it).
- Spot-check accuracy sampled regularly (Phase 7 process, repeated periodically, not just
  once at the start).

---

## 8.6 Deliverables checklist for Phase 8

- [ ] Standardized video folder/naming convention agreed with your video source
- [ ] `site_registry.yaml` covering all current sites
- [ ] Working `batch_runner.py` that processes a whole folder unattended
- [ ] Documented "add a new site" checklist (non-engineers should be able to follow it)
- [ ] Measured real throughput + cost-per-video-hour on your actual hardware
- [ ] A recurring QA/monitoring habit in place

---

At this point you have a complete, working, scalable v1 system. `11_Phase9_Advanced_Optional.md`
covers the harder accuracy upgrades (bus subtype, plate-type) if/when you decide they're
worth the extra investment.
