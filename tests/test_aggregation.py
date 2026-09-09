import unittest
from src.aggregation.bucket_aggregator import BucketAggregator

class TestBucketAggregator(unittest.TestCase):
    def setUp(self):
        self.aggregator = BucketAggregator()

    def test_bucket_rounding(self):
        # 08:04:12 should be bucketed to 08:00
        event1 = {
            "track_id": 1,
            "sheet_name": "Arm A",
            "movement_code": "A-C",
            "class_name": "Car/Jeep/Van",
            "time_str": "08:04:12"
        }
        # 08:14:59 should be bucketed to 08:00
        event2 = {
            "track_id": 2,
            "sheet_name": "Arm A",
            "movement_code": "A-C",
            "class_name": "Car/Jeep/Van",
            "time_str": "08:14:59"
        }
        # 08:15:00 should be bucketed to 08:15
        event3 = {
            "track_id": 3,
            "sheet_name": "Arm A",
            "movement_code": "A-C",
            "class_name": "Two Wheelers (White Plate)",
            "time_str": "08:15:00"
        }

        self.aggregator.add_event(event1)
        self.aggregator.add_event(event2)
        self.aggregator.add_event(event3)

        matrix = self.aggregator.get_matrix()
        self.assertEqual(matrix["Arm A"]["A-C"]["08:00"]["Car/Jeep/Van"], 2)
        self.assertEqual(matrix["Arm A"]["A-C"]["08:15"]["Two Wheelers (White Plate)"], 1)
        self.assertEqual(len(self.aggregator.get_event_log()), 3)

if __name__ == "__main__":
    unittest.main()
