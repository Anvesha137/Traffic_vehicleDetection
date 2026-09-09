import cv2
import yaml
import os
import time
from datetime import datetime, timedelta
from tqdm import tqdm

from src.detection.detector import VehicleDetector
from src.tracking.tracker import VehicleTracker
from src.movement.movement_classifier import TurningMovementClassifier
from src.aggregation.bucket_aggregator import BucketAggregator
from src.excel.excel_writer import ExcelWriter

class TrafficPipeline:
    def __init__(self, config_path: str, model_path: str = "yolov8m.pt"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        self.detector = VehicleDetector(model_path=model_path)
        self.tracker = VehicleTracker()
        self.classifier = TurningMovementClassifier(self.config)
        self.aggregator = BucketAggregator()

    def run(self, video_path: str, template_path: str, output_excel_path: str,
            debug_video_path: str = None, max_frames: int = None, frame_stride: int = 1):
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Unable to open video: {video_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if max_frames:
            total_frames = min(total_frames, max_frames)

        # Parse base time from config (e.g. 08:01:33)
        base_time_str = self.config.get("start_time_overlay", "08:00:00")
        base_dt = datetime.strptime(base_time_str, "%H:%M:%S")

        out_writer = None
        if debug_video_path:
            os.makedirs(os.path.dirname(os.path.abspath(debug_video_path)), exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_writer = cv2.VideoWriter(debug_video_path, fourcc, fps / frame_stride, (width, height))

        print(f"Starting processing: {os.path.basename(video_path)} ({total_frames} frames)...")
        pbar = tqdm(total=total_frames, desc="Processing Frames")

        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or (max_frames and frame_idx >= max_frames):
                break

            frame_idx += 1
            if frame_idx % frame_stride != 0:
                pbar.update(1)
                continue

            # Calculate current simulated timestamp
            elapsed_sec = frame_idx / fps
            curr_dt = base_dt + timedelta(seconds=elapsed_sec)
            curr_time_str = curr_dt.strftime("%H:%M:%S")

            # 1. Detection
            boxes, confs, class_names, _ = self.detector.detect(frame)

            # 2. Tracking
            tracked_boxes, track_ids, tracked_classes = self.tracker.update(boxes, confs, class_names)

            # 3. Turning Movement Classification
            events = self.classifier.process_frame(
                track_ids=track_ids,
                tracked_classes=tracked_classes,
                tracker_history=self.tracker.history,
                current_time_str=curr_time_str
            )

            # 4. Aggregation
            for ev in events:
                self.aggregator.add_event(ev)

            # 5. Debug Visualization
            if out_writer:
                vis_frame = frame.copy()
                
                # Draw counting lines
                for lname, linfo in self.config.get("lines", {}).items():
                    p1 = tuple(linfo["p1"])
                    p2 = tuple(linfo["p2"])
                    color = (0, 255, 0) if linfo.get("type") == "entry" else (0, 0, 255)
                    cv2.line(vis_frame, p1, p2, color, 3)
                    cv2.putText(vis_frame, lname, (p1[0], p1[1] - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                # Draw bounding boxes and tracks
                for box, tid, cname in zip(tracked_boxes, track_ids, tracked_classes):
                    x1, y1, x2, y2 = [int(v) for v in box]
                    cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
                    label = f"#{tid} {cname[:12]}"
                    cv2.putText(vis_frame, label, (x1, max(20, y1 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

                    # Draw bottom point trajectory
                    pts = self.tracker.get_trajectory(tid)
                    for k in range(1, len(pts)):
                        cv2.line(vis_frame, pts[k-1], pts[k], (0, 255, 255), 2)

                # Draw live counter HUD
                total_counted = len(self.aggregator.get_event_log())
                hud_text = f"Time: {curr_time_str} | Active Tracks: {len(track_ids)} | Total Vehicles Counted: {total_counted}"
                cv2.rectangle(vis_frame, (10, 10), (950, 55), (0, 0, 0), -1)
                cv2.putText(vis_frame, hud_text, (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)

                out_writer.write(vis_frame)

            pbar.update(1)

        pbar.close()
        cap.release()
        if out_writer:
            out_writer.release()
            print(f"Debug video saved to: {debug_video_path}")

        # 6. Write Excel
        print("Populating Excel template...")
        writer = ExcelWriter(template_path)
        matrix = self.aggregator.get_matrix()
        writer.populate_counts(matrix, output_excel_path)
        print("Pipeline execution finished successfully.")
        return matrix
