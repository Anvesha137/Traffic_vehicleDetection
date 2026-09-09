"""
Traffic AI Pipeline — FastAPI Backend Server
Handles video uploads, pipeline processing with live WebSocket frame streaming,
real TurningMovementClassifier integration, and Excel download.
"""
import os
import sys
import json
import time
import uuid
import asyncio
import base64
import shutil
import logging
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import cv2
import numpy as np
import yaml
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.detection.detector import VehicleDetector
from src.tracking.tracker import VehicleTracker
from src.movement.movement_classifier import TurningMovementClassifier
from src.aggregation.bucket_aggregator import BucketAggregator
from src.excel.excel_writer import ExcelWriter

logger = logging.getLogger("traffic_server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Traffic AI Pipeline", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CONFIGS_DIR = PROJECT_ROOT / "configs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Mount web frontend dist if built
DIST_DIR = PROJECT_ROOT / "web" / "dist"
if DIST_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(DIST_DIR), html=True), name="static_frontend")

# Global job state
jobs = {}

# Cached detector instance (loaded once, shared across WebSocket sessions)
GLOBAL_DETECTOR = None


def get_detector() -> VehicleDetector:
    global GLOBAL_DETECTOR
    if GLOBAL_DETECTOR is None:
        classes_cfg = CONFIGS_DIR / "classes.yaml"
        logger.info("Initializing VehicleDetector model weights...")
        GLOBAL_DETECTOR = VehicleDetector(
            model_path="yolov8m.pt",
            config_path=str(classes_cfg) if classes_cfg.exists() else None
        )
    return GLOBAL_DETECTOR


def cleanup_old_jobs(max_jobs: int = 50, max_age_hours: float = 2.0):
    """Prunes old jobs to prevent unbound memory growth."""
    now = time.time()
    expired = []
    for jid, jinfo in jobs.items():
        created = jinfo.get("created_at", now)
        if (now - created) > (max_age_hours * 3600) and jinfo.get("status") in ("completed", "error", "disconnected"):
            expired.append(jid)

    for jid in expired:
        jobs.pop(jid, None)

    # If still exceeding capacity, drop oldest completed jobs
    if len(jobs) > max_jobs:
        sorted_jobs = sorted(jobs.items(), key=lambda x: x[1].get("created_at", 0))
        for jid, jinfo in sorted_jobs:
            if jinfo.get("status") in ("completed", "error", "disconnected"):
                jobs.pop(jid, None)
                if len(jobs) <= max_jobs:
                    break


def resolve_excel_template(template_name: str) -> Path:
    """Finds the Excel template across standard project folders."""
    candidates = [
        PROJECT_ROOT / "train_output" / template_name,
        PROJECT_ROOT / "train" / template_name,
        PROJECT_ROOT / template_name,
        PROJECT_ROOT / "train_output" / "Site 15 - Veerasandra_Main_Road.xlsx",
        PROJECT_ROOT / "train" / "Data Entry Temp.xlsx",
        PROJECT_ROOT / "Site 15 - Veerasandra_Main_Road.xlsx",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


@app.on_event("startup")
async def startup_event():
    # Pre-warm detector model on startup
    try:
        get_detector()
        logger.info("Detector initialized successfully at startup.")
    except Exception as e:
        logger.warning(f"Deferred detector initialization: {e}")


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file (supports multi-GB videos)."""
    cleanup_old_jobs()

    job_id = str(uuid.uuid4())[:8]
    ext = Path(file.filename).suffix or ".avi"
    save_path = UPLOAD_DIR / f"{job_id}{ext}"

    total_bytes = 0
    with open(save_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024 * 8)
            if not chunk:
                break
            f.write(chunk)
            total_bytes += len(chunk)

    cap = cv2.VideoCapture(str(save_path))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0
    cap.release()

    jobs[job_id] = {
        "status": "uploaded",
        "video_path": str(save_path),
        "filename": file.filename,
        "width": width,
        "height": height,
        "fps": fps,
        "total_frames": total_frames,
        "duration_sec": duration_sec,
        "progress": 0,
        "created_at": time.time(),
    }

    return {
        "job_id": job_id,
        "filename": file.filename,
        "size_mb": round(total_bytes / (1024 * 1024), 2),
        "resolution": f"{width}x{height}",
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration_min": round(duration_sec / 60, 2),
    }


@app.get("/api/jobs")
async def list_jobs():
    return {jid: {k: v for k, v in j.items() if k != "video_path"} for jid, j in jobs.items()}


@app.get("/api/download/{job_id}")
async def download_excel(job_id: str):
    excel_path = OUTPUT_DIR / f"{job_id}_output.xlsx"
    if not excel_path.exists():
        raise HTTPException(status_code=404, detail="Excel output not found.")
    return FileResponse(
        path=str(excel_path),
        filename=f"Traffic_Count_{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/api/download-video/{job_id}")
async def download_debug_video(job_id: str):
    video_path = OUTPUT_DIR / f"{job_id}_debug.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Debug video not found.")
    return FileResponse(path=str(video_path), filename=f"Debug_{job_id}.mp4", media_type="video/mp4")


@app.websocket("/ws/process/{job_id}")
async def websocket_process(websocket: WebSocket, job_id: str):
    await websocket.accept()

    if job_id not in jobs:
        await websocket.send_json({"type": "error", "message": "Job not found"})
        await websocket.close()
        return

    job = jobs[job_id]
    if job["status"] == "processing":
        await websocket.send_json({"type": "error", "message": "Job already processing"})
        await websocket.close()
        return

    job["status"] = "processing"

    try:
        # 1. Parse client configuration
        try:
            init_msg = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
            start_time = init_msg.get("start_time", "08:00:00")
            frame_stride = max(1, int(init_msg.get("frame_stride", 3)))
            config_name = init_msg.get("config", "site_15_veerasandra.yaml")
            template_name = init_msg.get("template", "Site 15 - Veerasandra_Main_Road.xlsx")
        except (asyncio.TimeoutError, json.JSONDecodeError):
            start_time = "08:00:00"
            frame_stride = 3
            config_name = "site_15_veerasandra.yaml"
            template_name = "Site 15 - Veerasandra_Main_Road.xlsx"

        # 2. Load site configuration YAML
        site_cfg_path = CONFIGS_DIR / config_name
        if not site_cfg_path.exists():
            site_cfg_path = CONFIGS_DIR / "site_15_veerasandra.yaml"

        with open(site_cfg_path, "r") as f:
            site_config = yaml.safe_load(f)

        # 3. Initialize components
        detector = get_detector()
        tracker = VehicleTracker()
        classifier = TurningMovementClassifier(site_config)
        aggregator = BucketAggregator()

        # 4. Open video
        cap = cv2.VideoCapture(job["video_path"])
        fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        lines_cfg = site_config.get("lines", {})

        # Debug video writer
        debug_path = str(OUTPUT_DIR / f"{job_id}_debug.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(debug_path, fourcc, fps / frame_stride, (width, height))

        base_dt = datetime.strptime(start_time, "%H:%M:%S")
        frame_idx = 0
        last_ws_send = 0
        ws_interval = 0.10

        category_counts = defaultdict(int)
        movement_counts = defaultdict(int)
        total_counted = 0

        await websocket.send_json({
            "type": "init",
            "total_frames": total_frames,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "duration_min": round(total_frames / fps / 60, 2),
            "site_id": site_config.get("site_id", "Traffic Site"),
        })

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if frame_idx % frame_stride != 0:
                continue

            elapsed_sec = frame_idx / fps
            curr_dt = base_dt + timedelta(seconds=elapsed_sec)
            curr_time_str = curr_dt.strftime("%H:%M:%S")

            # Step 1: Detect
            boxes, confs, class_names, _ = detector.detect(frame)

            # Step 2: Track
            tracked_boxes, track_ids, tracked_classes = tracker.update(boxes, confs, class_names)

            # Step 3: Turning movement classification
            completed_events = classifier.process_frame(
                track_ids=track_ids,
                tracked_classes=tracked_classes,
                tracker_history=tracker.history,
                current_time_str=curr_time_str
            )

            # Step 4: Aggregate counts
            for ev in completed_events:
                aggregator.add_event(ev)
                category_counts[ev["class_name"]] += 1
                movement_counts[f"{ev['sheet_name']} {ev['movement_code']}"] += 1
                total_counted += 1

            # Step 5: Draw visualization overlay
            vis_frame = frame.copy()

            # Draw site counting lines (green for entry, red for exit)
            for lname, linfo in lines_cfg.items():
                p1 = tuple(linfo["p1"])
                p2 = tuple(linfo["p2"])
                ltype = linfo.get("type", "entry")
                color = (0, 255, 100) if ltype == "entry" else (0, 80, 255)
                cv2.line(vis_frame, p1, p2, color, 2)
                cv2.putText(
                    vis_frame,
                    f"{lname} ({linfo.get('arm', '')})",
                    (p1[0] + 5, p1[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    color,
                    2
                )

            # Draw bounding boxes and bottom-center trajectory trails
            for box, tid, cname in zip(tracked_boxes, track_ids, tracked_classes):
                x1, y1, x2, y2 = [int(v) for v in box]
                cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
                label = f"#{tid} {cname[:15]}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(vis_frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 4, y1), (255, 180, 0), -1)
                cv2.putText(vis_frame, label, (x1 + 2, max(th + 4, y1 - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

                pts = tracker.get_trajectory(int(tid))
                for k in range(1, len(pts)):
                    cv2.line(vis_frame, pts[k - 1], pts[k], (0, 255, 255), 2)

            # HUD
            progress_pct = round(frame_idx / total_frames * 100, 1)
            overlay = vis_frame.copy()
            cv2.rectangle(overlay, (0, 0), (width, 60), (15, 15, 25), -1)
            vis_frame = cv2.addWeighted(overlay, 0.85, vis_frame, 0.15, 0)

            cv2.putText(vis_frame, f"Time: {curr_time_str}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 170), 2)
            cv2.putText(vis_frame, f"Active Tracks: {len(track_ids)}", (300, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 220, 80), 2)
            cv2.putText(vis_frame, f"Counted: {total_counted}", (580, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (100, 200, 255), 2)
            cv2.putText(vis_frame, f"{progress_pct}%", (width - 120, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (180, 180, 255), 2)

            # Bottom progress bar
            bar_w = int((width - 40) * progress_pct / 100)
            cv2.rectangle(vis_frame, (20, height - 12), (width - 20, height - 4), (40, 40, 60), -1)
            cv2.rectangle(vis_frame, (20, height - 12), (20 + bar_w, height - 4), (0, 255, 170), -1)

            # Display active crossing events
            for ev in completed_events:
                cv2.putText(
                    vis_frame,
                    f"+1 {ev['class_name']} ({ev['movement_code']})",
                    (width // 2 - 120, height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.1,
                    (0, 255, 0),
                    3
                )

            out_writer.write(vis_frame)

            # Step 6: Stream to WebSocket client
            now = time.time()
            if now - last_ws_send >= ws_interval:
                last_ws_send = now
                stream_h = 480
                stream_w = int(width * stream_h / height)
                small = cv2.resize(vis_frame, (stream_w, stream_h))
                _, jpeg_buf = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_b64 = base64.b64encode(jpeg_buf.tobytes()).decode('ascii')

                try:
                    await websocket.send_json({
                        "type": "frame",
                        "frame": frame_b64,
                        "progress": progress_pct,
                        "frame_idx": frame_idx,
                        "total_frames": total_frames,
                        "time": curr_time_str,
                        "active_tracks": int(len(track_ids)),
                        "total_counted": total_counted,
                        "category_counts": dict(category_counts),
                        "movement_counts": dict(movement_counts),
                    })
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected by client for job {job_id}")
                    break

            job["progress"] = progress_pct

        cap.release()
        out_writer.release()

        # Step 7: Populate Excel template with aggregated matrix
        template_file = resolve_excel_template(template_name)
        excel_generated = False
        if template_file:
            try:
                writer = ExcelWriter(str(template_file))
                excel_out = str(OUTPUT_DIR / f"{job_id}_output.xlsx")
                writer.populate_counts(aggregator.get_matrix(), excel_out)
                excel_generated = True
                logger.info(f"Generated output Excel for job {job_id} at {excel_out}")
            except Exception as e:
                logger.error(f"Failed to populate Excel: {e}")

        job["status"] = "completed"
        job["progress"] = 100

        await websocket.send_json({
            "type": "complete",
            "total_counted": total_counted,
            "category_counts": dict(category_counts),
            "movement_counts": dict(movement_counts),
            "excel_ready": excel_generated,
            "debug_video_ready": True,
        })

    except WebSocketDisconnect:
        job["status"] = "disconnected"
        logger.info(f"Job {job_id} WebSocket session ended.")
    except Exception as e:
        job["status"] = "error"
        logger.error(f"Job {job_id} error: {traceback.format_exc()}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except (WebSocketDisconnect, RuntimeError):
            pass
    finally:
        try:
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
