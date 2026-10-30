import os

# ── Video Paths ──────────────────────────────────────────────────────────────
IN_VIDEO_PATH  = "./data/vehicle-counting.mp4"
OUT_VIDEO_PATH = "./data/vehicles_output.mp4"

# ── YOLO Model Path ───────────────────────────────────────────────────────────
# Auto-select: use VisDrone model if available, else fallback to yolov8n
_visdrone = "./models/VisDrone_YOLO_x2.pt"
_yolov8n  = "./models/yolov8n.pt"

if os.path.exists(_visdrone):
    YOLO_MODEL_PATH = _visdrone
elif os.path.exists(_yolov8n):
    YOLO_MODEL_PATH = _yolov8n
else:
    # Use whichever .pt file exists in models/
    _candidates = [f for f in os.listdir("./models") if f.endswith(".pt")] if os.path.exists("./models") else []
    YOLO_MODEL_PATH = os.path.join("./models", _candidates[0]) if _candidates else _yolov8n

print(f"[config] YOLO model: {YOLO_MODEL_PATH}")

# ── Line Zone ─────────────────────────────────────────────────────────────────
LINE_Y = 480

# ── Perspective Transform Points ─────────────────────────────────────────────
SOURCE_POINTS = [[450, 300], [860, 300], [1900, 720], [-660, 720]]
WIDTH, HEIGHT  = 25, 100
TARGET_POINTS  = [[0, 0], [WIDTH, 0], [WIDTH, HEIGHT], [0, HEIGHT]]

# ── Display (unused by Flask) ─────────────────────────────────────────────────
WINDOW_NAME = "SmartCity Traffic"
