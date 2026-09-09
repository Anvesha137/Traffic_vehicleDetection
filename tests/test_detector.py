import unittest
import numpy as np
from src.detection.detector import VehicleDetector

class TestDetectorMapping(unittest.TestCase):
    def test_detector_class_mapping(self):
        detector = VehicleDetector(model_path="yolov8m.pt")
        # Ensure classes.yaml was loaded and mapped
        self.assertIn("car", detector.class_map)
        self.assertEqual(detector.class_map["car"], "Car/Jeep/Van")
        self.assertEqual(detector.class_map["motorcycle"], "Two Wheelers (White Plate)")
        self.assertEqual(detector.class_map["bus"], "Bus - Other Buses")
        self.assertEqual(detector.class_map["truck"], "Other Trucks")
        self.assertEqual(detector.class_map["bicycle"], "Cycle")

if __name__ == "__main__":
    unittest.main()
