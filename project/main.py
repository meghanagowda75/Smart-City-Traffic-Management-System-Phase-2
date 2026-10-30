# main.py
import numpy as np
import supervision as sv
from ultralytics import YOLO

from src.annotator import Annotator
from src.view_transformer import ViewTransformer
from src.speed_estimator import SpeedEstimator
from config import (
    IN_VIDEO_PATH,
    OUT_VIDEO_PATH,
    YOLO_MODEL_PATH,
    LINE_Y,
    SOURCE_POINTS,
    TARGET_POINTS,
    WINDOW_NAME,
)

# 1. Load YOLO model
model = YOLO(YOLO_MODEL_PATH)

# 2. Get video info
video_info = sv.VideoInfo.from_video_path(IN_VIDEO_PATH)
print("Video info:", video_info)

# 3. Initialize ByteTrack tracker
tracker = sv.ByteTrack(frame_rate=video_info.fps)

# 4. Define Line Zone for counting
offset = 55
start, end = sv.Point(offset, LINE_Y), sv.Point(video_info.width - offset, LINE_Y)
line_zone = sv.LineZone(start, end, minimum_crossing_threshold=1)

# 5. Perspective Transform source & target points
SOURCE = np.array(SOURCE_POINTS)
TARGET = np.array(TARGET_POINTS)

# 6. Initialize ViewTransformer
view_transformer = ViewTransformer(SOURCE, TARGET)

# 7. Initialize SpeedEstimator
speed_estimator = SpeedEstimator(fps=video_info.fps, view_transformer=view_transformer)

# 8. Initialize Annotator
annotator = Annotator(
    resolution_wh=video_info.resolution_wh,
    box_annotator=True,
    label_annotator=True,
    line_annotator=True,
    multi_class_line_annotator=True,
    trace_annotator=True,
    polygon_zone=SOURCE,
)

# Export important names for app.py
__all__ = [
    "model",
    "video_info",
    "tracker",
    "line_zone",
    "speed_estimator",
    "annotator",
    "IN_VIDEO_PATH",
]
