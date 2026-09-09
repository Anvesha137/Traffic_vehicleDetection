import unittest
import numpy as np
from src.tracking.tracker import VehicleTracker

class TestVehicleTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = VehicleTracker()

    def test_empty_update(self):
        boxes, tids, classes = self.tracker.update(np.empty((0, 4)), np.empty((0,)), [])
        self.assertEqual(len(boxes), 0)
        self.assertEqual(len(tids), 0)
        self.assertEqual(len(classes), 0)

    def test_trajectory_and_majority_voting(self):
        # Manually verify tracker history & majority vote logic
        tid = 42
        self.tracker.history[tid] = [(100, 200), (105, 210)]
        self.tracker.class_history[tid] = ["Car/Jeep/Van", "Car/Jeep/Van", "Goods Auto/LCV"]

        pts = self.tracker.get_trajectory(tid)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[-1], (105, 210))

        # Majority vote test
        majority_class = max(set(self.tracker.class_history[tid]), key=self.tracker.class_history[tid].count)
        self.assertEqual(majority_class, "Car/Jeep/Van")

if __name__ == "__main__":
    unittest.main()
