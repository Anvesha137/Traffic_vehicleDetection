"""
Traffic AI Pipeline — FastAPI Backend Server
Handles video uploads, pipeline processing with live WebSocket frame streaming,
and Excel download.
"""
import os
import sys
import json
import time
import uuid
import asyncio
import base64
import shutil
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

# Global job state
jobs = {}


# ========== Simple line-crossing counter ==========
def ccw(A, B, C):
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

def segments_intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


class SimpleLineCounter:
    """
    Counts unique vehicles crossing counting lines.
    Each vehicle (track_id) is counted ONCE per line it crosses.
    No need for entry+exit pairs.
    """
    def __init__(self, counting_lines):
        """
        counting_lines: list of dicts with keys: name, p1, p2, color
        """
        self.lines = counting_lines
        self.counted_ids = {}  # line_name -> set of track_ids already counted
        self.category_counts = defaultdict(int)  # class_name -> count
        self.total_count = 0
        self.events = []  # list of (track_id, class_name, line_name, time_str)

        for line in self.lines:
            self.counted_ids[line["name"]] = set()

    def update(self, track_ids, tracked_classes, tracker_history, time_str):
        """Check all active tracks for line crossings."""
        new_events = []
        for tid, cname in zip(track_ids, tracked_classes):
            pts = tracker_history.get(int(tid), [])
            if len(pts) < 2:
                continue
            p_prev = pts[-2]
            p_curr = pts[-1]

            for line in self.lines:
                lname = line["name"]
                if int(tid) in self.counted_ids[lname]:
                    continue  # already counted on this line

                lp1 = tuple(line["p1"])
                lp2 = tuple(line["p2"])

                if segments_intersect(p_prev, p_curr, lp1, lp2):
                    self.counted_ids[lname].add(int(tid))
                    self.category_counts[cname] += 1
                    self.total_count += 1
                    ev = {"track_id": int(tid), "class": cname, "line": lname, "time": time_str}
                    self.events.append(ev)
                    new_events.append(ev)

        return new_events


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file (supports up to 5 hours / multi-GB)."""
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
    return FileResponse(path=str(excel_path),
        filename=f"Traffic_Count_{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


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
        # Get config from client
        try:
            init_msg = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
            start_time = init_msg.get("start_time", "08:00:00")
            frame_stride = int(init_msg.get("frame_stride", 3))
        except asyncio.TimeoutError:
            start_time = "08:00:00"
            frame_stride = 3

        # Initialize detector and tracker
        detector = VehicleDetector(model_path="yolov8m.pt")
        tracker = VehicleTracker()

        # Open video
        cap = cv2.VideoCapture(job["video_path"])
        fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # ===== AUTO-GENERATE COUNTING LINES across the road =====
        # Place 3 horizontal counting lines at different vertical positions
        # These cut across where vehicles actually drive
        counting_lines = [
            {
                "name": "Line Top",
                "p1": [int(width * 0.10), int(height * 0.40)],
                "p2": [int(width * 0.90), int(height * 0.40)],
                "color": (0, 255, 200),
            },
            {
                "name": "Line Mid",
                "p1": [int(width * 0.05), int(height * 0.60)],
                "p2": [int(width * 0.95), int(height * 0.60)],
                "color": (0, 200, 255),
            },
            {
                "name": "Line Bot",
                "p1": [int(width * 0.02), int(height * 0.82)],
                "p2": [int(width * 0.98), int(height * 0.82)],
                "color": (100, 255, 100),
            },
        ]

        counter = SimpleLineCounter(counting_lines)

        # Debug video writer
        debug_path = str(OUTPUT_DIR / f"{job_id}_debug.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(debug_path, fourcc, fps / frame_stride, (width, height))

        base_dt = datetime.strptime(start_time, "%H:%M:%S")
        frame_idx = 0
        last_ws_send = 0
        ws_interval = 0.10

        await websocket.send_json({
            "type": "init",
            "total_frames": total_frames,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "duration_min": round(total_frames / fps / 60, 2),
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

            # 1. Detect
            boxes, confs, class_names, _ = detector.detect(frame)

            # 2. Track
            tracked_boxes, track_ids, tracked_classes = tracker.update(boxes, confs, class_names)

            # 3. Count line crossings
            new_events = counter.update(track_ids, tracked_classes, tracker.history, curr_time_str)

            # 4. Draw visualization
            vis_frame = frame.copy()

            # Draw counting lines
            for line in counting_lines:
                p1 = tuple(line["p1"])
                p2 = tuple(line["p2"])
                cv2.line(vis_frame, p1, p2, line["color"], 2)
                cv2.putText(vis_frame, line["name"], (p1[0] + 10, p1[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, line["color"], 2)

            # Draw bounding boxes and trails
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
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 170), 2)
            cv2.putText(vis_frame, f"Tracks: {len(track_ids)}", (320, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 220, 80), 2)
            cv2.putText(vis_frame, f"Counted: {counter.total_count}", (580, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 200, 255), 2)
            cv2.putText(vis_frame, f"{progress_pct}%", (width - 130, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 255), 2)

            # Progress bar at bottom
            bar_w = int((width - 40) * progress_pct / 100)
            cv2.rectangle(vis_frame, (20, height - 12), (width - 20, height - 4), (40, 40, 60), -1)
            cv2.rectangle(vis_frame, (20, height - 12), (20 + bar_w, height - 4), (0, 255, 170), -1)

            # Flash new crossing events
            for ev in new_events:
                cv2.putText(vis_frame, f"+1 {ev['class']}", (width // 2 - 80, height // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

            out_writer.write(vis_frame)

            # 5. Stream to WebSocket
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
                        "total_counted": counter.total_count,
                        "category_counts": dict(counter.category_counts),
                    })
                except WebSocketDisconnect:
                    break

            job["progress"] = progress_pct

        cap.release()
        out_writer.release()

        # Generate Excel if template exists
        template_path = PROJECT_ROOT / "Site 15 - Veerasandra_Main_Road.xlsx"
        if template_path.exists():
            from src.excel.excel_writer import ExcelWriter
            from src.aggregation.bucket_aggregator import BucketAggregator
            aggregator = BucketAggregator()
            for ev in counter.events:
                aggregator.add_event({
                    "track_id": ev["track_id"],
                    "sheet_name": "Arm A",
                    "movement_code": "A-C",
                    "class_name": ev["class"],
                    "time_str": ev["time"],
                })
            writer = ExcelWriter(str(template_path))
            excel_out = str(OUTPUT_DIR / f"{job_id}_output.xlsx")
            writer.populate_counts(aggregator.get_matrix(), excel_out)

        job["status"] = "completed"
        job["progress"] = 100

        await websocket.send_json({
            "type": "complete",
            "total_counted": counter.total_count,
            "category_counts": dict(counter.category_counts),
            "excel_ready": template_path.exists(),
            "debug_video_ready": True,
        })

    except WebSocketDisconnect:
        job["status"] = "disconnected"
    except Exception as e:
        job["status"] = "error"
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
