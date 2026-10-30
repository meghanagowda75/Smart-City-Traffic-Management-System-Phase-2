# app.py — SmartCity Traffic | Flask App with Auth + YOLO + OSM Simulation
from flask import (
    Flask, Response, render_template, jsonify,
    request, redirect, url_for, session, flash
)
import cv2
import numpy as np
import os, time, json, hashlib, traceback
from functools import wraps

# ── Try importing YOLO/supervision libraries ──────────────────────────────────
# We only check if the LIBRARIES exist here — model loads lazily on first video upload
try:
    import supervision as sv
    from ultralytics import YOLO
    from src.speed_estimator import SpeedEstimator
    from src.view_transformer import ViewTransformer
    from src.annotator import Annotator
    from config import LINE_Y, SOURCE_POINTS, TARGET_POINTS
    LIBS_AVAILABLE = True
    print("[app] YOLO/supervision libraries loaded OK")
except Exception as e:
    LIBS_AVAILABLE = False
    print(f"[app] YOLO libraries not available: {e}")

# ── Flask setup ───────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "smartcity-secret-2025-change-in-production"

# ── User store ────────────────────────────────────────────────────────────────
USERS_FILE = "./data/users.json"
os.makedirs("./data", exist_ok=True)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── YOLO Pipeline State (initialized lazily on video upload) ──────────────────
SPEED_LIMIT    = 80
pipeline       = None   # dict with model, tracker, line_zone, speed_estimator, annotator
current_video  = None   # path to currently loaded video
latest_stats   = {"in_count": 0, "out_count": 0, "current_vehicles": [], "overspeed": []}

def init_pipeline(video_path):
    """Initialize YOLO pipeline for a given video. Returns (pipeline_dict, error_str)."""
    if not LIBS_AVAILABLE:
        return None, "YOLO libraries not installed"
    try:
        # Auto-select model
        candidates = ["./models/VisDrone_YOLO_x2.pt", "./models/yolov8n.pt"]
        model_path = next((p for p in candidates if os.path.exists(p)), None)
        if not model_path:
            # Find any .pt file in models/
            if os.path.exists("./models"):
                pts = [f for f in os.listdir("./models") if f.endswith(".pt")]
                if pts:
                    model_path = os.path.join("./models", pts[0])
        if not model_path:
            return None, "No YOLO model (.pt) found in ./models/ folder"

        print(f"[app] Loading model: {model_path}")
        model      = YOLO(model_path)
        video_info = sv.VideoInfo.from_video_path(video_path)
        print(f"[app] Video info: {video_info}")

        tracker    = sv.ByteTrack(frame_rate=video_info.fps)
        offset     = 55
        start      = sv.Point(offset, LINE_Y)
        end        = sv.Point(video_info.width - offset, LINE_Y)
        line_zone  = sv.LineZone(start, end, minimum_crossing_threshold=1)

        SOURCE = np.array(SOURCE_POINTS)
        TARGET = np.array(TARGET_POINTS)
        vt     = ViewTransformer(SOURCE, TARGET)
        se     = SpeedEstimator(fps=video_info.fps, view_transformer=vt)
        ann    = Annotator(
            resolution_wh=video_info.resolution_wh,
            box_annotator=True,
            label_annotator=True,
            line_annotator=True,
            multi_class_line_annotator=True,
            trace_annotator=True,
            polygon_zone=SOURCE,
        )
        return {
            "model": model, "tracker": tracker,
            "line_zone": line_zone, "speed_estimator": se,
            "annotator": ann, "video_info": video_info,
        }, None
    except Exception as e:
        traceback.print_exc()
        return None, str(e)

# ── Auth decorator ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def launch():
    return render_template("launch.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if "username" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        users    = load_users()
        user     = users.get(username)
        if not user:
            user = next((u for u in users.values() if u.get("email")==username), None)
            if user: username = user["username"]
        if user and user.get("password") == hash_pw(password):
            session["username"]   = username
            session["first_name"] = user.get("first_name", username)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if "username" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        first = request.form.get("first_name","").strip()
        last  = request.form.get("last_name","").strip()
        uname = request.form.get("username","").strip().lower()
        email = request.form.get("email","").strip().lower()
        pw    = request.form.get("password","")
        pw2   = request.form.get("confirm_password","")
        if not all([first, uname, email, pw]):
            flash("All fields are required.", "error"); return render_template("signup.html")
        if len(pw) < 8:
            flash("Password must be at least 8 characters.", "error"); return render_template("signup.html")
        if pw != pw2:
            flash("Passwords do not match.", "error"); return render_template("signup.html")
        users = load_users()
        if uname in users:
            flash("Username already taken.", "error"); return render_template("signup.html")
        if any(u.get("email")==email for u in users.values()):
            flash("Email already registered.", "error"); return render_template("signup.html")
        users[uname] = {
            "username": uname, "first_name": first, "last_name": last,
            "email": email, "password": hash_pw(pw),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
        session["username"]   = uname
        session["first_name"] = first
        return redirect(url_for("dashboard"))
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("launch"))

# ══════════════════════════════════════════════════════════════════════════════
#  PROTECTED ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/simulation")
@login_required
def simulation():
    return render_template("simulation.html")

# ══════════════════════════════════════════════════════════════════════════════
#  VIDEO PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
def placeholder_frame(msg="Upload a video to begin"):
    """Generate a single placeholder MJPEG frame."""
    frame = np.zeros((480, 854, 3), dtype=np.uint8)
    # Dark gradient background
    for y in range(480):
        val = int(6 + y * 0.04)
        frame[y, :] = [val, val+2, val+8]
    # Text
    font  = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.9
    thick = 2
    color = (0, 245, 212)  # neon cyan
    (tw, th), _ = cv2.getTextSize(msg, font, scale, thick)
    x = (854 - tw) // 2
    y = (480 + th) // 2
    cv2.putText(frame, msg, (x, y), font, scale, color, thick, cv2.LINE_AA)
    ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes() if ret else b""

def generate_frames():
    global pipeline, current_video, latest_stats, SPEED_LIMIT

    if pipeline is None or current_video is None:
        # Show placeholder, keep trying every 0.5s in case pipeline initialises
        fb = placeholder_frame("Upload a video to begin YOLO detection")
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while pipeline is None:
            yield boundary + fb + b"\r\n"
            time.sleep(0.5)

    p = pipeline
    try:
        frame_gen = sv.get_video_frames_generator(current_video)
    except Exception as e:
        fb = placeholder_frame(f"Video error: {e}")
        while True:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + fb + b"\r\n"
            time.sleep(1)
        return

    for frame in frame_gen:
        try:
            results    = p["model"](frame, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = p["tracker"].update_with_detections(detections)
            p["line_zone"].trigger(detections)
            detections = p["speed_estimator"].update(detections)

            labels, current_vehicles, overspeed_list = [], [], []
            class_names = detections.data.get("class_name", [])
            speeds      = detections.data.get("speed", [])
            tids        = detections.tracker_id if detections.tracker_id is not None else []

            for i, tid in enumerate(tids):
                cls = class_names[i] if i < len(class_names) else "vehicle"
                spd = int(speeds[i]) if i < len(speeds) and speeds[i] else 0
                labels.append(f"{cls} {spd}km/h")
                vd = {"id": int(tid), "class_name": str(cls), "speed": spd,
                      "overspeed": spd > SPEED_LIMIT}
                current_vehicles.append(vd)
                if spd > SPEED_LIMIT:
                    overspeed_list.append(vd)

            try:
                latest_stats["in_count"]  = int(p["line_zone"].in_count)
                latest_stats["out_count"] = int(p["line_zone"].out_count)
            except Exception:
                pass
            latest_stats["current_vehicles"] = current_vehicles
            latest_stats["overspeed"]        = overspeed_list

            annotated = p["annotator"].annotate(
                frame, detections, labels=labels,
                line_zones=[p["line_zone"]],
                multi_class_zones=[p["line_zone"]],
            )
            ret, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        except Exception:
            traceback.print_exc()
            time.sleep(0.03)

@app.route("/video_feed")
@login_required
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/data")
@login_required
def data():
    return jsonify(latest_stats)

@app.route("/set_speed_limit", methods=["POST"])
@login_required
def set_speed_limit():
    global SPEED_LIMIT
    body = request.get_json(silent=True) or {}
    SPEED_LIMIT = int(body.get("limit", SPEED_LIMIT))
    print(f"[app] Speed limit -> {SPEED_LIMIT} km/h")
    return jsonify({"ok": True, "limit": SPEED_LIMIT})

@app.route("/upload_video", methods=["POST"])
@login_required
def upload_video():
    global pipeline, current_video, latest_stats
    if "video" not in request.files:
        return jsonify({"error": "No video file"}), 400
    uploaded  = request.files["video"]
    save_path = "./data/uploaded_video.mp4"
    os.makedirs("./data", exist_ok=True)
    try:
        uploaded.save(save_path)
        print(f"[app] Video saved: {save_path} ({os.path.getsize(save_path)//1024} KB)")
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Save failed: {e}"}), 500

    current_video = save_path
    latest_stats  = {"in_count": 0, "out_count": 0, "current_vehicles": [], "overspeed": []}

    p, err = init_pipeline(save_path)
    if err:
        print(f"[app] Pipeline init failed: {err}")
        # Still return OK so video shows placeholder with error text
        pipeline = None
        return jsonify({"ok": True, "warning": err})

    pipeline = p
    print(f"[app] Pipeline ready for: {save_path}")
    return jsonify({"ok": True})

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("[app] Starting SmartCity Traffic on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
