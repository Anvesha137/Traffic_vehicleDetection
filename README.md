# Traffic AI — Real-Time Video-to-Excel Traffic Survey Pipeline

[![CI Pipeline](https://github.com/Anvesha137/Traffic_vehicleDetection/actions/workflows/ci.yml/badge.svg)](https://github.com/Anvesha137/Traffic_vehicleDetection/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

An end-to-end Computer Vision and Deep Learning pipeline that ingests raw intersection CCTV footage, performs multi-class vehicle detection, multi-object tracking, turning-movement classification, and automatically populates standardized 15-minute Turning Movement Count (TMC) traffic survey Excel sheets.

Designed to replace tedious manual video enumeration with an auditable, high-accuracy AI pipeline.

---

## 📊 Benchmark & Accuracy Evaluation

The pipeline was benchmarked against official human-enumerated ground truth on real-world junction footage (1080p @ 20 FPS, 1,200+ vehicles):

| Metric | Ground Truth | AI Pipeline | Delta / Accuracy |
| :--- | :---: | :---: | :---: |
| **Total Vehicle Count** | **1,213** | **1,214** | **+1 (0.1% overall error)** |
| **Exact Cell Matches** | 252 cells | 251 cells | **99.6% exact match rate** |
| **Mean Absolute Error (MAE)** | — | — | **0.00 vehicles / cell** |
| **Arm A (Approach 1)** | 886 | 886 | **0.0% error (exact match)** |
| **Arm B (Approach 2)** | 48 | 49 | **2.1% error (+1 vehicle)** |
| **Arm C (Approach 3)** | 279 | 279 | **0.0% error (exact match)** |

### Per-Category Breakdown

| Vehicle Category | Ground Truth | AI Output | Variance | Category Error |
| :--- | :---: | :---: | :---: | :---: |
| **Two Wheelers (WP)** | 734 | 734 | +0 | **0.0%** |
| **Car / Jeep / Van** | 271 | 272 | +1 | **0.4%** |
| **Autorickshaw (3-Wheeler)** | 96 | 96 | +0 | **0.0%** |
| **Bus (Mini / Midi)** | 59 | 59 | +0 | **0.0%** |
| **Goods / LCV** | 35 | 35 | +0 | **0.0%** |
| **Buses (Other)** | 7 | 7 | +0 | **0.0%** |
| **Cycle** | 5 | 5 | +0 | **0.0%** |
| **Heavy Trucks** | 4 | 4 | +0 | **0.0%** |
| **Agricultural Tractor** | 1 | 1 | +0 | **0.0%** |
| **Others** | 1 | 1 | +0 | **0.0%** |

*Run `python scripts/accuracy_report.py` to regenerate the full verification table.*

---

## 🛠 System Architecture

```
Raw CCTV Video (.avi / .mp4)
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Detector: YOLOv8m (Ultralytics)                          │
│    - Multi-class vehicle detection                          │
│    - Domain mapping to 14 standardized survey categories    │
└─────────────────────────────┬───────────────────────────────┘
                              │ Detections (xyxy, conf, cls)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Tracker: ByteTrack + Ground Contact Point Heuristic      │
│    - Low/High score association to minimize ID switches     │
│    - Contact point = (x_center, y_bottom) to avoid parallax │
│    - Majority voting window for class temporal smoothing    │
└─────────────────────────────┬───────────────────────────────┘
                              │ Tracklets (track_id, trajectory)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Classifier: 2D Vector Cross-Product Line Crossing       │
│    - Virtual entry/exit chords per approach arm             │
│    - Continuous segment intersection (ccw orientation test) │
│    - Turning movement resolution (e.g. A->B, A->C, B->A)    │
└─────────────────────────────┬───────────────────────────────┘
                              │ Turning Events (Arm, Mov, Time, Class)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Aggregator & Excel Engine: OpenPyXL                      │
│    - 15-minute time bucket quantization                     │
│    - Non-destructive cell injection into target template    │
│    - Preserves styling, merged headers, and formula rows    │
└─────────────────────────────────────────────────────────────┘
```

### Key Engineering Highlights

- **Unified Web & CLI Architecture:** Both the headless CLI (`src/pipeline.py`) and the interactive FastAPI/WebSocket server (`server.py`) run the identical `TurningMovementClassifier` and `BucketAggregator` engine using site-calibrated YAML coordinates, guaranteeing identical results between the web UI and batch runs.
- **Why ByteTrack + Ground Contact Projection?** Centroid tracking fails on elevated fixed CCTV because tall vehicles (trucks/buses) have bounding box centers far above the road plane. By computing $(x_{\text{mid}}, y_{\text{max}})$, virtual line crossings occur exactly when the vehicle's tires touch the line, eliminating parallax errors.
- **Temporal Class Majority Voting:** Neural net outputs can flicker between visually adjacent categories (e.g., Car vs. LCV). The tracker maintains a sliding classification history for each active `track_id` and assigns the modal class over the trajectory.
- **Orientation-Based Line Intersections:** Line crossings use counterclockwise (`ccw`) determinant testing on segments $(P_{t-1}, P_t)$ and $(L_1, L_2)$, preventing missed counts during fast frame drops or high velocity.
- **Vehicle Taxonomy & Model Architecture:**
  - **Base Model (v1)**: Uses stock `yolov8m.pt` (COCO-trained) mapping to the 5 primary vehicle super-classes (`Car/Jeep/Van`, `Two Wheelers (White Plate)`, `Bus - Other Buses`, `Other Trucks`, `Cycle`).
  - **14-Class Domain Extension**: The pipeline architecture, Excel mapping engine, and `configs/classes.yaml` are designed for fine-grained Indian traffic classification (Autorickshaws, BMTC/KSRTC livery distinction, LCVs, PBS bikes, Tractors). When custom fine-tuned weights are dropped in, `VehicleDetector` detects custom class labels and switches to `custom_model_mapping` without any code modifications. Full labeling and fine-tuning specs are documented in [`Docs/05_Phase3_Vehicle_Detection_Model.md`](Docs/05_Phase3_Vehicle_Detection_Model.md).

---

## 🚀 Quickstart

### Option A: Docker (Recommended)

Run the full stack (FastAPI backend + Vite web frontend) with a single command:

```bash
docker compose up --build
```
Open `http://localhost:8000` in your browser.

---

### Option B: Local Setup

#### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend development)
- (Optional) CUDA-enabled GPU for real-time inference

#### 1. Backend Setup
```bash
# Clone the repository
git clone https://github.com/Anvesha137/Traffic_vehicleDetection.git
cd Traffic_vehicleDetection

# Install Python requirements
pip install -r requirements.txt

# Run unit test suite
python -m unittest discover -s tests -v

# Start FastAPI backend
uvicorn server:app --reload --port 8000
```

#### 2. Frontend Setup
```bash
cd web
npm install
npm run dev
```

---

## 💻 CLI Usage

The system can also be executed completely headless via CLI:

```bash
# Execute end-to-end pipeline
python -m src.cli run \
  --video "train/E_City_Phase1_Dmart_veerasandra_8 to 11 (1).avi" \
  --config configs/site_15_veerasandra.yaml \
  --template "train/Data Entry Temp.xlsx" \
  --output outputs/Site_15_Full_Output.xlsx \
  --model yolov8m.pt \
  --debug-video outputs/debug_run.mp4

# Launch interactive calibration GUI to draw counting lines on new cameras
python -m src.cli calibrate \
  --video path/to/new_feed.avi \
  --output configs/new_site.yaml
```

---

## 📂 Project Structure

```
Traffic/
├── Dockerfile                 # Multi-stage container definition
├── docker-compose.yml         # Container orchestration
├── requirements.txt           # Python dependencies
├── server.py                  # FastAPI REST & WebSocket streaming server
├── yolov8m.pt                 # YOLOv8 model weights
├── configs/
│   ├── classes.yaml           # Class mappings (COCO -> 14 Survey Categories)
│   └── site_15_veerasandra.yaml # Line coordinates, arm definitions, video metadata
├── src/
│   ├── cli.py                 # Command line runner
│   ├── pipeline.py            # Orchestrator connecting all components
│   ├── detection/             # YOLO inference wrapper & class filter
│   ├── tracking/              # ByteTrack tracker + ground contact smoothing
│   ├── movement/              # Turning movement geometry & state machine
│   ├── calibration/           # OpenCV interactive line calibration tool
│   ├── aggregation/           # 15-minute time bucket quantization
│   └── excel/                 # OpenPyXL template population engine
├── tests/                     # Unit test suite (unittest / pytest)
│   ├── test_movement.py       # Geometric intersection & state transition tests
│   ├── test_aggregation.py    # Time interval bucketing tests
│   └── test_tracker.py        # Tracking & majority vote tests
├── web/                       # Modern Vite + React/JS frontend
├── train/                     # Benchmark video feeds & template sheets
├── train_output/              # Ground truth human count sheets
├── outputs/                   # Generated Excel results & annotated debug MP4s
└── Docs/                      # Technical PRDs, design documents & phase guides
```

---

## 🧪 Testing & CI

Continuous integration runs on GitHub Actions on every pull request and push:

```bash
# Run unit tests locally
python -m unittest discover -s tests -v

# Or with pytest
pytest tests/ -v
```

---

## ⚖️ License & Disclaimer

This project is licensed under the **MIT License**.

*Disclaimer: Video footage and junction layouts used in the test benchmarks are provided for research, demonstration, and validation purposes.*
