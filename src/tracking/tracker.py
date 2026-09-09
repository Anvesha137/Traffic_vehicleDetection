import supervision as sv
import numpy as np

class VehicleTracker:
    """
    Multi-Object Tracker using ByteTrack to assign persistent IDs and track vehicle trajectories.
    """
    def __init__(self, track_activation_threshold: float = 0.35, lost_track_buffer: int = 40):
        self.tracker = sv.ByteTrack(
            track_activation_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
            minimum_matching_threshold=0.8,
            frame_rate=20
        )
        self.history = {} # track_id -> list of bottom-center points (x, y)
        self.class_history = {} # track_id -> list of class names (for majority voting)

    def update(self, boxes: np.ndarray, confidences: np.ndarray, class_names: list):
        """
        Updates tracks with detections.
        Returns:
            tracked_boxes: np.ndarray [M, 4]
            track_ids: np.ndarray [M]
            tracked_classes: list of str
        """
        if len(boxes) == 0:
            return np.empty((0, 4)), np.empty((0,), dtype=int), []

        # Create supervision Detections object
        detections = sv.Detections(
            xyxy=boxes,
            confidence=confidences,
            class_id=np.arange(len(class_names))
        )

        tracked_detections = self.tracker.update_with_detections(detections)

        tracked_boxes = []
        track_ids = []
        tracked_classes = []

        if tracked_detections.tracker_id is not None and len(tracked_detections.tracker_id) > 0:
            for i, tid in enumerate(tracked_detections.tracker_id):
                box = tracked_detections.xyxy[i]
                orig_idx = tracked_detections.class_id[i]
                cname = class_names[orig_idx] if orig_idx < len(class_names) else "Others"

                # Calculate bottom-center contact point
                cx = int((box[0] + box[2]) / 2)
                cy = int(box[3])  # bottom edge for ground contact

                if tid not in self.history:
                    self.history[tid] = []
                    self.class_history[tid] = []

                self.history[tid].append((cx, cy))
                self.class_history[tid].append(cname)

                # Keep history bounded
                if len(self.history[tid]) > 100:
                    self.history[tid].pop(0)
                    self.class_history[tid].pop(0)

                # Classify via majority vote
                majority_class = max(set(self.class_history[tid]), key=self.class_history[tid].count)

                tracked_boxes.append(box)
                track_ids.append(tid)
                tracked_classes.append(majority_class)

        return np.array(tracked_boxes), np.array(track_ids, dtype=int), tracked_classes

    def get_trajectory(self, track_id: int):
        return self.history.get(track_id, [])
