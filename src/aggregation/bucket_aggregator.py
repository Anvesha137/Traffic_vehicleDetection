from collections import defaultdict

class BucketAggregator:
    """
    Aggregates vehicle count events into 15-minute time intervals per Sheet and Movement.
    """
    def __init__(self):
        # Structure: counts[sheet_name][movement_code][time_bucket][class_name] = count
        self.counts = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
        self.event_log = []

    def add_event(self, event: dict):
        """
        event: dict(track_id, sheet_name, movement_code, class_name, time_str)
        time_str format: "HH:MM:SS"
        """
        self.event_log.append(event)
        
        sheet = event["sheet_name"]
        movement = event["movement_code"]
        class_name = event["class_name"]
        time_str = event["time_str"]

        # Calculate 15-min bucket
        hh, mm, _ = [int(x) for x in time_str.split(":")]
        bucket_minute = (mm // 15) * 15
        bucket_str = f"{hh:02d}:{bucket_minute:02d}"

        self.counts[sheet][movement][bucket_str][class_name] += 1

    def get_matrix(self):
        """Returns the nested dictionary suitable for ExcelWriter."""
        # Convert defaultdict to regular dict for serialization/clean access
        result = {}
        for sheet, movements in self.counts.items():
            result[sheet] = {}
            for mov, buckets in movements.items():
                result[sheet][mov] = {}
                for bucket, ccounts in buckets.items():
                    result[sheet][mov][bucket] = dict(ccounts)
        return result

    def get_event_log(self):
        return self.event_log
