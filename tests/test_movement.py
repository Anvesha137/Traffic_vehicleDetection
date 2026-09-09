import unittest
import numpy as np
from src.movement.movement_classifier import ccw, intersect, TurningMovementClassifier

class TestMovementClassifier(unittest.TestCase):
    def setUp(self):
        self.site_config = {
            "site_id": "Test_Junction",
            "lines": {
                "Arm_A_Entry": {
                    "p1": [0, 50],
                    "p2": [100, 50],
                    "type": "entry",
                    "arm": "Arm A"
                },
                "Arm_B_Exit": {
                    "p1": [0, 150],
                    "p2": [100, 150],
                    "type": "exit",
                    "arm": "Arm B"
                }
            },
            "movement_mapping": {
                "Arm A -> Arm B": "A-B"
            }
        }
        self.classifier = TurningMovementClassifier(self.site_config)

    def test_ccw_and_intersect(self):
        # Intersecting segments
        p1 = (0, 0)
        p2 = (10, 10)
        p3 = (0, 10)
        p4 = (10, 0)
        self.assertTrue(intersect(p1, p2, p3, p4))

        # Parallel non-intersecting segments
        p5 = (0, 0)
        p6 = (10, 0)
        p7 = (0, 5)
        p8 = (10, 5)
        self.assertFalse(intersect(p5, p6, p7, p8))

    def test_turning_movement_completed(self):
        tid = 1
        cname = "Car/Jeep/Van"

        # Frame 1: Before entry line (y=40)
        history = {tid: [(50, 40)]}
        events = self.classifier.process_frame(
            track_ids=np.array([tid]),
            tracked_classes=[cname],
            tracker_history=history,
            current_time_str="08:05:00"
        )
        self.assertEqual(len(events), 0)

        # Frame 2: Crosses Arm_A_Entry line (y=50) moving down to y=60
        history[tid].append((50, 60))
        events = self.classifier.process_frame(
            track_ids=np.array([tid]),
            tracked_classes=[cname],
            tracker_history=history,
            current_time_str="08:05:01"
        )
        self.assertEqual(len(events), 0)
        self.assertEqual(self.classifier.vehicle_states[tid]["entry_arm"], "Arm A")

        # Frame 3: Before exit line
        history[tid].append((50, 140))
        events = self.classifier.process_frame(
            track_ids=np.array([tid]),
            tracked_classes=[cname],
            tracker_history=history,
            current_time_str="08:05:03"
        )
        self.assertEqual(len(events), 0)

        # Frame 4: Crosses Arm_B_Exit line (y=150) moving to y=160
        history[tid].append((50, 160))
        events = self.classifier.process_frame(
            track_ids=np.array([tid]),
            tracked_classes=[cname],
            tracker_history=history,
            current_time_str="08:05:04"
        )
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["track_id"], tid)
        self.assertEqual(ev["sheet_name"], "Arm A")
        self.assertEqual(ev["movement_code"], "A-B")
        self.assertEqual(ev["class_name"], "Car/Jeep/Van")
        self.assertTrue(self.classifier.vehicle_states[tid]["counted"])

        # Frame 5: Double counting prevention
        history[tid].append((50, 170))
        events_after = self.classifier.process_frame(
            track_ids=np.array([tid]),
            tracked_classes=[cname],
            tracker_history=history,
            current_time_str="08:05:05"
        )
        self.assertEqual(len(events_after), 0)

if __name__ == "__main__":
    unittest.main()
