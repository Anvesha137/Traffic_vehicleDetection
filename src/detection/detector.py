from ultralytics import YOLO
import numpy as np
import yaml
import os

class VehicleDetector:
    """
    Wraps YOLO model (YOLOv8/v11) and maps detected classes to target traffic survey classes.
    """
    def __init__(self, model_path: str = "yolov8m.pt", config_path: str = None, conf_threshold: float = 0.35):
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        
        # Resolve config_path default if not specified
        if not config_path:
            default_cfg = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "classes.yaml")
            if os.path.exists(default_cfg):
                config_path = os.path.abspath(default_cfg)

        # Load class mappings
        self.class_map = {}
        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}

            # Detect whether loaded model contains custom fine-tuned classes or standard COCO classes
            custom_map = cfg.get("custom_model_mapping", {})
            coco_map = cfg.get("coco_mapping", {})
            model_class_names = set(self.model.names.values()) if hasattr(self.model, "names") else set()

            # Domain-specific classes that only exist in custom traffic models (not in standard COCO 80-classes)
            custom_exclusive_classes = {
                "two_wheeler_private", "two_wheeler_taxi", "auto_rickshaw",
                "bus_bmtc", "bus_ksrtc", "bus_minibus", "lcv_goods_auto",
                "tractor", "pbs_bike"
            }

            if model_class_names and any(c in custom_exclusive_classes for c in model_class_names):
                self.class_map = custom_map
            else:
                self.class_map = coco_map
        
        # Fallback if config is missing or empty
        if not self.class_map:
            self.class_map = {
                "bicycle": "Cycle",
                "motorcycle": "Two Wheelers (White Plate)",
                "car": "Car/Jeep/Van",
                "bus": "Bus - Other Buses",
                "truck": "Other Trucks"
            }

    def detect(self, frame: np.ndarray):
        """
        Runs detection on a single frame.
        Returns:
            boxes: np.ndarray [N, 4] (x1, y1, x2, y2)
            confidences: np.ndarray [N]
            class_names: list of str (mapped target class names)
            raw_class_ids: np.ndarray [N]
        """
        results = self.model.predict(
            source=frame,
            conf=self.conf_threshold,
            verbose=False,
            device='cuda' if self.model.device.type == 'cuda' else 'cpu'
        )[0]

        boxes = []
        confs = []
        class_names = []
        raw_ids = []

        if results.boxes is not None and len(results.boxes) > 0:
            xyxy = results.boxes.xyxy.cpu().numpy()
            conf = results.boxes.conf.cpu().numpy()
            cls_ids = results.boxes.cls.cpu().numpy().astype(int)

            for i in range(len(cls_ids)):
                raw_name = results.names.get(cls_ids[i], "")
                mapped_name = self.class_map.get(raw_name)
                
                # If mapped_name is valid (not None and not ignored)
                if mapped_name:
                    boxes.append(xyxy[i])
                    confs.append(conf[i])
                    class_names.append(mapped_name)
                    raw_ids.append(cls_ids[i])

        if len(boxes) == 0:
            return np.empty((0, 4)), np.empty((0,)), [], np.empty((0,))

        return np.array(boxes), np.array(confs), class_names, np.array(raw_ids)
