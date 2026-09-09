import cv2
import yaml
import os
import numpy as np

class SiteCalibrator:
    """
    Interactive Calibration GUI tool to draw Arm counting lines and zones on a video frame.
    Allows user to click points, label counting lines (e.g. Arm A Entry, Arm B Exit),
    and save directly to YAML.
    """
    def __init__(self, video_path: str, output_yaml: str):
        self.video_path = video_path
        self.output_yaml = output_yaml
        self.points = []
        self.lines = {}
        self.current_line_name = "Arm_A_Entry"
        self.colors = [(0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
        
        cap = cv2.VideoCapture(video_path)
        ret, self.frame = cap.read()
        cap.release()
        if not ret:
            raise ValueError(f"Could not read frame from {video_path}")
        self.display_frame = self.frame.copy()

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((x, y))
            print(f"Point selected: ({x}, {y})")
            if len(self.points) == 2:
                self.lines[self.current_line_name] = {
                    "p1": [self.points[0][0], self.points[0][1]],
                    "p2": [self.points[1][0], self.points[1][1]]
                }
                print(f"Saved line '{self.current_line_name}': {self.lines[self.current_line_name]}")
                self.points = []
            self._redraw()

    def _redraw(self):
        self.display_frame = self.frame.copy()
        # Draw saved lines
        for idx, (name, pts) in enumerate(self.lines.items()):
            p1 = tuple(pts["p1"])
            p2 = tuple(pts["p2"])
            color = self.colors[idx % len(self.colors)]
            cv2.line(self.display_frame, p1, p2, color, 3)
            mid_x, mid_y = (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2
            cv2.putText(self.display_frame, name, (mid_x, mid_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Draw pending point
        if len(self.points) == 1:
            cv2.circle(self.display_frame, self.points[0], 5, (0, 255, 255), -1)

        # Draw instructions HUD
        hud = f"Active Line: {self.current_line_name} | Press [1-6] to change line | [S] Save | [C] Clear | [Q] Quit"
        cv2.rectangle(self.display_frame, (0, 0), (self.display_frame.shape[1], 40), (0, 0, 0), -1)
        cv2.putText(self.display_frame, hud, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.imshow("Site Calibration Tool", self.display_frame)

    def run(self):
        cv2.namedWindow("Site Calibration Tool", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Site Calibration Tool", 1280, 720)
        cv2.setMouseCallback("Site Calibration Tool", self.mouse_callback)
        self._redraw()

        line_options = [
            "Arm_A_Entry", "Arm_A_Exit",
            "Arm_B_Entry", "Arm_B_Exit",
            "Arm_C_Entry", "Arm_C_Exit"
        ]

        while True:
            key = cv2.waitKey(20) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('s'):
                self.save_yaml()
                break
            elif key == ord('c'):
                self.lines.clear()
                self.points.clear()
                self._redraw()
            elif ord('1') <= key <= ord('6'):
                idx = key - ord('1')
                if idx < len(line_options):
                    self.current_line_name = line_options[idx]
                    self.points = []
                    self._redraw()

        cv2.destroyAllWindows()

    def save_yaml(self):
        config_data = {
            "site_id": "Site_15_Veerasandra",
            "video_resolution": [self.frame.shape[1], self.frame.shape[0]],
            "lines": self.lines
        }
        with open(self.output_yaml, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)
        print(f"Site configuration saved successfully to: {self.output_yaml}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=r"C:\Users\Admin\Desktop\Traffic\E_City_Phase1_Dmart_veerasandra_8 to 11 (1).avi")
    parser.add_argument("--output", default=r"C:\Users\Admin\Desktop\Traffic\configs\site_15_veerasandra.yaml")
    args = parser.parse_args()
    calibrator = SiteCalibrator(args.video, args.output)
    calibrator.run()
