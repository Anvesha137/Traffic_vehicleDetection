# Phase 0 — Environment Setup & Project Scaffolding

**Goal of this phase:** get a working computer environment where you can run Python, AI
libraries, and video-processing tools — before touching any ML. This is 100% mechanical,
no ML knowledge needed. Budget **half a day**.

**Exit criteria (you're done with Phase 0 when):** you can run one test command and it
successfully opens your sample video and prints its length, with no errors.

---

## 0.1 Decide where you'll run this

You have three realistic options. Pick one:

| Option | Good if... | Cost |
|---|---|---|
| **A. Your own PC with an NVIDIA GPU** (even a modest gaming GPU, e.g. RTX 3060) | You already own one | Free (just electricity) |
| **B. Cloud GPU rental** (e.g. RunPod, Lambda Labs, Google Colab Pro, AWS/GCP) | You don't own a GPU | ~$0.30–$1.50/hour depending on GPU |
| **C. CPU only, no GPU** | Just to learn/prototype on tiny clips | Free, but 10–30x slower — fine for Phase 0–2 learning, NOT fine for real training in Phase 3 |

Recommendation for a beginner: **start on Google Colab (free tier) or a cheap cloud GPU**
for Phases 0–3 while you learn, then move to a proper GPU machine once you're doing real
training runs (Phase 3 onward), since those take hours.

---

## 0.2 Install core tools

### If using your own machine (Windows/Mac/Linux):

1. **Install Python 3.10 or 3.11** (not 3.13 yet — some ML libraries lag behind).
   Download from https://www.python.org/downloads/ — during install on Windows, tick
   "Add Python to PATH".

2. **Install a code editor** — VS Code (https://code.visualstudio.com/) is the standard
   choice, free, with a good Python extension.

3. **Install Git** (https://git-scm.com/downloads) — lets you save your project's history
   and download open-source model code.

4. **(If you have an NVIDIA GPU) Install CUDA drivers** — go to
   https://www.nvidia.com/Download/index.aspx, download the driver for your GPU model.
   Verify afterwards by opening a terminal and running:
   ```bash
   nvidia-smi
   ```
   You should see a table with your GPU name and driver version. If this command fails,
   your GPU isn't visible yet — fix this before continuing (search your GPU model +
   "CUDA driver install" for a guide specific to your OS).

### If using Google Colab (easiest for absolute beginners):

1. Go to https://colab.research.google.com, sign in with a Google account.
2. New notebook → Runtime → Change runtime type → select **GPU** (T4 is fine to start).
3. That's it — Python, and most libraries, are already installed for you.

---

## 0.3 Create the project folder & virtual environment

A "virtual environment" keeps this project's Python packages separate from everything
else on your computer, so nothing conflicts. Open a terminal and run:

```bash
mkdir traffic-count-ai
cd traffic-count-ai

python -m venv venv

# Activate it:
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

You'll know it worked because your terminal prompt now shows `(venv)` at the start.
**Every time you open a new terminal to work on this project, re-run the activate line.**

---

## 0.4 Install the Python libraries you'll need across all phases

```bash
pip install --upgrade pip

# Core deep learning + computer vision
pip install ultralytics          # YOLOv8/YOLOv11 — our detector/classifier (Phase 3)
pip install opencv-python        # video reading/writing, drawing lines (Phase 1, 4, 5)
pip install torch torchvision    # deep learning engine underneath ultralytics

# Tracking
pip install supervision          # helper library with ByteTrack built in (Phase 4)

# Excel handling
pip install openpyxl             # reading/writing .xlsx files, preserves formatting

# Data & utility
pip install pandas numpy tqdm pyyaml matplotlib
```

> **Note on `torch` (PyTorch):** if you have an NVIDIA GPU, go to
> https://pytorch.org/get-started/locally/ , select your OS + CUDA version, and copy the
> exact install command shown there instead of the plain `pip install torch` line above —
> this ensures you get the GPU-enabled version, not the CPU-only one.

---

## 0.5 Verify everything works (the actual exit test)

Create a file called `test_setup.py` in your project folder with this content:

```python
import cv2
import torch
from ultralytics import YOLO

print("OpenCV version:", cv2.__version__)
print("PyTorch version:", torch.__version__)
print("GPU available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU name:", torch.cuda.get_device_name(0))

# Try opening your sample video — update this path to wherever you saved it
video_path = "E_City_Phase1_Dmart_veerasandra_8_to_11__1_.avi"
cap = cv2.VideoCapture(video_path)
print("Video opened OK:", cap.isOpened())
print("Frame count:", int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
print("FPS:", cap.get(cv2.CAP_PROP_FPS))
print("Resolution:", int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "x", int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
cap.release()

# Quick sanity check that a pretrained model downloads and runs
model = YOLO("yolov8n.pt")   # this auto-downloads a small pretrained model (~6MB)
print("YOLO model loaded OK. Classes it knows:", len(model.names))
```

Run it:
```bash
python test_setup.py
```

**Expected output** looks roughly like:
```
OpenCV version: 4.x.x
PyTorch version: 2.x.x
GPU available: True
GPU name: NVIDIA GeForce RTX ...
Video opened OK: True
Frame count: 33907
FPS: 20.0
Resolution: 1920 x 1080
YOLO model loaded OK. Classes it knows: 80
```

If `Frame count`, `FPS`, and `Resolution` match your real video (they should look like
the numbers above, since that's what your sample video actually is), **Phase 0 is done.**

If `GPU available: False` — that's OK for now, everything in Phases 0–2 still works on
CPU, just slower. Fix GPU access before Phase 3 (real training).

---

## 0.6 Project folder structure (set this up now, we'll fill it in over the next phases)

```
traffic-count-ai/
├── venv/                       # your virtual environment (never commit this to git)
├── data/
│   ├── raw_videos/             # drop new site videos here
│   ├── raw_excels/             # the matching blank/target Excel templates
│   ├── frames/                 # extracted training frames (Phase 2)
│   └── labels/                 # annotation files (Phase 2)
├── configs/
│   └── sites/                  # one YAML file per camera/site (Phase 1)
├── models/
│   └── weights/                # trained model files (Phase 3)
├── src/
│   ├── calibration_tool.py     # Phase 1
│   ├── detect_and_track.py     # Phase 3 + 4
│   ├── movement_logic.py       # Phase 5
│   ├── excel_writer.py         # Phase 6
│   └── batch_runner.py         # Phase 8
├── outputs/
│   └── filled_excels/          # final results land here
└── test_setup.py
```

You don't need to create every folder by hand right now — each later phase tells you
exactly when to create what.

---

## 0.7 Common beginner pitfalls in this phase

- **"pip install" fails with permission errors** → you probably forgot to activate the
  virtual environment (`venv\Scripts\activate` / `source venv/bin/activate`). Check for
  `(venv)` in your prompt.
- **PyTorch says `GPU available: False` even though you have an NVIDIA card** → you
  installed the CPU-only version. Uninstall (`pip uninstall torch torchvision`) and
  reinstall using the exact command from pytorch.org for your CUDA version.
- **`.avi` file won't open with OpenCV** → install the `opencv-python` package (already
  in the list above) — the plain `opencv-python-headless` sometimes lacks certain codecs.
  If it still fails, install `ffmpeg` on your system (https://ffmpeg.org/download.html)
  and re-try; OpenCV often delegates to system ffmpeg for unusual codecs.

---

Next: open `03_Phase1_Data_Audit_and_Site_Calibration.md`.
