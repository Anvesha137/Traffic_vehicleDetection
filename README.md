# Traffic AI Pipeline

An AI-powered traffic video analysis pipeline that detects, tracks, and classifies vehicles from intersection camera footage — then auto-fills standardized Excel count sheets.

Built with **YOLOv8** for detection, custom tracking logic, and movement classification across configurable intersection arms.

## Features

- **Vehicle Detection** — YOLOv8-based detection supporting 14 vehicle categories (two-wheelers, cars, buses, trucks, auto-rickshaws, cycles, etc.)
- **Object Tracking** — Frame-to-frame tracking with unique vehicle IDs
- **Movement Classification** — Determines entry/exit arms and computes turning movements (e.g., A→B, B→C)
- **Excel Auto-Fill** — Populates standardized traffic survey Excel templates with aggregated counts
- **Interactive Calibration** — GUI tool to define virtual counting lines on video frames
- **Web Interface** — Vite-powered frontend with live WebSocket frame streaming during processing
- **FastAPI Backend** — REST + WebSocket API for video upload, pipeline execution, and result download

## Tech Stack

| Layer       | Technology                           |
| ----------- | ------------------------------------ |
| Detection   | YOLOv8 (Ultralytics)                |
| Tracking    | Custom tracker                       |
| Backend     | FastAPI, OpenCV, NumPy, openpyxl     |
| Frontend    | Vite + JavaScript                    |
| Config      | YAML (site configs + class mappings) |

## Project Structure

```
Traffic/
├── server.py                  # FastAPI backend (uploads, WebSocket, pipeline orchestration)
├── yolov8m.pt                 # YOLOv8 model weights
├── configs/
│   ├── classes.yaml           # Vehicle class mappings (COCO → Excel columns)
│   └── site_*.yaml            # Per-site configs (lines, arms, resolution, FPS)
├── src/
│   ├── cli.py                 # CLI entry point
│   ├── pipeline.py            # End-to-end pipeline orchestrator
│   ├── detection/             # YOLOv8 vehicle detector
│   ├── tracking/              # Frame-to-frame object tracker
│   ├── movement/              # Movement/turning classification
│   ├── calibration/           # Interactive line calibration GUI
│   ├── aggregation/           # Count aggregation logic
│   └── excel/                 # Excel template writer
├── web/                       # Vite frontend (live frame viewer)
├── train/                     # Training input data (videos, Excel templates)
├── train_output/              # Training output results
├── uploads/                   # Uploaded video files
├── outputs/                   # Generated Excel results & debug videos
├── data/                      # Reference data files
├── scripts/                   # Utility scripts
└── Docs/                      # Documentation
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the web frontend)

### Installation

```bash
# Clone the repo
git clone <repo-url>
cd Traffic

# Install Python dependencies
pip install fastapi uvicorn opencv-python-headless numpy ultralytics pyyaml openpyxl python-multipart websockets

# Install frontend dependencies
cd web
npm install
cd ..
```

### Running the Web App

```bash
# Terminal 1 — Start the backend
uvicorn server:app --reload --port 8000

# Terminal 2 — Start the frontend
cd web
npm run dev
```

### CLI Usage

```bash
# Run the full pipeline
python -m src.cli run \
  --video path/to/video.avi \
  --config configs/site_15_veerasandra.yaml \
  --template "Data Entry Temp.xlsx" \
  --output outputs/result.xlsx \
  --model yolov8m.pt

# Interactive calibration
python -m src.cli calibrate \
  --video path/to/video.avi \
  --output configs/my_site.yaml
```

## Configuration

### Site Config (`configs/site_*.yaml`)

Defines intersection-specific parameters:

- `video_resolution` — Frame dimensions
- `fps` — Video frame rate
- `lines` — Virtual counting line coordinates (entry/exit per arm)
- `movement_mapping` — Arm-to-arm turning movement labels

### Class Mapping (`configs/classes.yaml`)

Maps COCO/custom model class names to the 14 Excel template columns (Two Wheelers, Car/Jeep/Van, Bus subtypes, Trucks, Cycles, etc.)

## API Endpoints

| Method    | Endpoint              | Description                        |
| --------- | --------------------- | ---------------------------------- |
| `POST`    | `/upload`             | Upload a video file                |
| `GET`     | `/jobs/{id}/status`   | Check pipeline job status          |
| `GET`     | `/jobs/{id}/download` | Download the generated Excel file  |
| `WS`      | `/ws/{id}`            | Live frame stream during processing|

## License

This project is proprietary. All rights reserved.
