import numpy as np

def ccw(A, B, C):
    """Checks if three points are listed in counterclockwise order."""
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

def intersect(A, B, C, D):
    """Returns True if line segment AB and line segment CD intersect."""
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

class TurningMovementClassifier:
    """
    Classifies vehicle turning movements (e.g. A->B, A->C, B->A, etc.)
    by monitoring line crossings on entrance/exit virtual gates.
    """
    def __init__(self, site_config: dict):
        self.site_config = site_config
        self.lines = site_config.get("lines", {})
        self.movement_map = site_config.get("movement_mapping", {})
        
        # State: track_id -> dict(entry_arm=str, entry_time=str, exit_arm=str, exit_time=str, counted=bool)
        self.vehicle_states = {}

    def process_frame(self, track_ids: np.ndarray, tracked_classes: list, tracker_history: dict, current_time_str: str):
        """
        Evaluates current positions and trajectories of all active tracks against virtual counting lines.
        Returns:
            completed_events: list of dict(track_id, sheet_name, movement_code, class_name, time_str)
        """
        completed_events = []

        for tid, cname in zip(track_ids, tracked_classes):
            pts = tracker_history.get(tid, [])
            if len(pts) < 2:
                continue

            p_prev = pts[-2]
            p_curr = pts[-1]

            if tid not in self.vehicle_states:
                self.vehicle_states[tid] = {
                    "entry_arm": None,
                    "entry_time": None,
                    "exit_arm": None,
                    "exit_time": None,
                    "counted": False,
                    "class_name": cname
                }

            state = self.vehicle_states[tid]
            state["class_name"] = cname  # update with latest majority class

            if state["counted"]:
                continue

            # Check all configured lines for crossings
            for line_name, line_info in self.lines.items():
                lp1 = tuple(line_info["p1"])
                lp2 = tuple(line_info["p2"])
                ltype = line_info.get("type", "entry")
                arm = line_info.get("arm", "Arm A")

                if intersect(p_prev, p_curr, lp1, lp2):
                    if ltype == "entry" and not state["entry_arm"]:
                        state["entry_arm"] = arm
                        state["entry_time"] = current_time_str
                    elif ltype == "exit" and not state["exit_arm"]:
                        state["exit_arm"] = arm
                        state["exit_time"] = current_time_str

            # Check if movement is completed (both entry and exit recorded)
            if state["entry_arm"] and state["exit_arm"] and not state["counted"]:
                key = f"{state['entry_arm']} -> {state['exit_arm']}"
                movement_code = self.movement_map.get(key, f"{state['entry_arm'][-1]}-{state['exit_arm'][-1]}")
                sheet_name = state["entry_arm"]

                event = {
                    "track_id": tid,
                    "sheet_name": sheet_name,
                    "movement_code": movement_code,
                    "class_name": state["class_name"],
                    "time_str": state["exit_time"] or current_time_str
                }
                completed_events.append(event)
                state["counted"] = True

        return completed_events
