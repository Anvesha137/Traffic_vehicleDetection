import argparse
import os
import sys

from src.pipeline import TrafficPipeline

def main():
    parser = argparse.ArgumentParser(description="Traffic Video to Excel Auto-Fill AI Pipeline")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Process video and populate Excel count sheet")
    run_parser.add_argument("--video", required=True, help="Path to input video file (.avi / .mp4)")
    run_parser.add_argument("--config", required=True, help="Path to site configuration YAML")
    run_parser.add_argument("--template", required=True, help="Path to target Excel template (.xlsx)")
    run_parser.add_argument("--output", required=True, help="Path to save populated Excel file (.xlsx)")
    run_parser.add_argument("--model", default="yolov8m.pt", help="YOLO model path or name (default: yolov8m.pt)")
    run_parser.add_argument("--debug-video", default=None, help="Optional output path for rendered debug video (.mp4)")
    run_parser.add_argument("--max-frames", type=int, default=None, help="Optional frame limit for testing")
    run_parser.add_argument("--frame-stride", type=int, default=1, help="Process every Nth frame (e.g. 2 to speed up inference)")

    # Command: calibrate
    calib_parser = subparsers.add_parser("calibrate", help="Open interactive calibration GUI tool")
    calib_parser.add_argument("--video", required=True, help="Path to sample video")
    calib_parser.add_argument("--output", default="configs/site_calibrated.yaml", help="Output YAML path")

    args = parser.parse_args()

    if args.command == "run":
        pipeline = TrafficPipeline(config_path=args.config, model_path=args.model)
        pipeline.run(
            video_path=args.video,
            template_path=args.template,
            output_excel_path=args.output,
            debug_video_path=args.debug_video,
            max_frames=args.max_frames,
            frame_stride=args.frame_stride
        )
    elif args.command == "calibrate":
        from src.calibration.calibrator_gui import SiteCalibrator
        calibrator = SiteCalibrator(args.video, args.output)
        calibrator.run()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
