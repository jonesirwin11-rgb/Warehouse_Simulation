import datetime
import math
import time
import requests
import uuid
import hashlib

# ==========================================
# Hysteresis constants (Task 1)
# ==========================================
BAND_PX = 15

# ==========================================
# ID-switch dedup constants (Task 2)
# ==========================================
REASSOC_WINDOW_S = 2.0
REASSOC_DIST_PX = 60
SIZE_RATIO_TOLERANCE = 0.25  # 25% width/height difference allowed

# ==========================================
# Confirm-eligibility guard (age + displacement)
# ==========================================
MIN_CONFIRM_AGE_FRAMES = 5          # a real crossing spans multiple frames; tune against footage
MIN_CONFIRM_DISPLACEMENT_PX = 150    # calibrate relative to observed box width (~150-200px in this footage)


# ==========================================
# Geometry helpers
# ==========================================

def signed_distance(point, line_start, line_end):
    """Signed perpendicular distance from a point to a line.
    Positive = dock side, negative = truck side."""
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end
    denom = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if denom == 0:
        return 0.0
    return ((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) / denom


def get_side(dist, band=BAND_PX):
    """Classify a signed distance into truck / neutral / dock."""
    if dist < -band:
        return "truck"
    elif dist > band:
        return "dock"
    return "neutral"


def update_crossing(track_state, foot_point, line_start, line_end):
    """Returns True on a complete transition across the neutral band
    in ANY direction, making tripwire placement robust against rotation."""
    dist = signed_distance(foot_point, line_start, line_end)
    side = get_side(dist)
    prev_side = track_state.get("last_side")

    crossed = False
    if prev_side in ("truck", "dock") and side in ("truck", "dock") and prev_side != side:
        crossed = True
        
    # Only overwrite last_side when OUT of the neutral band — this is what
    # stops dithering inside the band from resetting/losing state.
    if side != "neutral":
        track_state["last_side"] = side

    return crossed


def euclidean(p1, p2):
    """Euclidean distance between two (x, y) tuples."""
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

def iou(box_a, box_b):
    """Standard intersection-over-union between two (x1,y1,x2,y2) boxes."""
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b
    ix1, iy1 = max(xa1, xb1), max(ya1, yb1)
    ix2, iy2 = min(xa2, xb2), min(ya2, yb2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = (xa2 - xa1) * (ya2 - ya1)
    area_b = (xb2 - xb1) * (yb2 - yb1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def is_likely_id_switch(new_track, recent_completed_tracks, now):
    """Returns True if a new track looks like the same physical box
    that was just counted under a different tracker ID (ByteTrack
    re-assignment after occlusion).

    Discriminates on time + location + size — time+location alone
    would falsely merge two genuinely different boxes crossing the
    same line in quick succession."""
    for rt in recent_completed_tracks:
        if now - rt["timestamp"] > REASSOC_WINDOW_S:
            continue
        dist = euclidean(new_track["foot_point"], rt["end_location"])
        if dist > REASSOC_DIST_PX:
            continue

        # Size/aspect discriminator — crucial to avoid undercounting
        if rt["width"] == 0 or rt["height"] == 0:
            continue
        w_ratio = abs(new_track["width"] - rt["width"]) / rt["width"]
        h_ratio = abs(new_track["height"] - rt["height"]) / rt["height"]
        if w_ratio > SIZE_RATIO_TOLERANCE or h_ratio > SIZE_RATIO_TOLERANCE:
            continue  # different-sized box → real new box, not a switch

        return True  # same window, same spot, same size → ID-switch
    return False

def is_eligible_to_confirm(track, current_frame_idx):
    """A track must be old enough AND have moved enough to be a plausible real
    crossing. Rejects tracks that spawn inside/near the hysteresis band and
    jitter across it from detection noise with no real motion behind them."""
    age = current_frame_idx - track["first_frame_idx"]
    if age < MIN_CONFIRM_AGE_FRAMES:
        return False, f"too young ({age} frames)"

    dx = track["foot_point"][0] - track["first_foot_point"][0]
    dy = track["foot_point"][1] - track["first_foot_point"][1]
    dist = (dx ** 2 + dy ** 2) ** 0.5
    if dist < MIN_CONFIRM_DISPLACEMENT_PX:
        return False, f"insufficient displacement ({dist:.0f}px)"

    return True, None


def _foot_point_from_detection(xyxy):
    """Bottom-center of a bounding box = the 'foot' used for line crossing."""
    x1, y1, x2, y2 = xyxy
    return ((x1 + x2) / 2.0, y2)


def _bbox_size(xyxy):
    """Returns (width, height) of a bounding box."""
    x1, y1, x2, y2 = xyxy
    return (abs(x2 - x1), abs(y2 - y1))


def publish_events(states, confirmed_ids, session_id, camera_id, target_event_type, api_url):
    """
    Takes a list of newly confirmed IDs and fires events to the backend.
    """
    if not confirmed_ids:
        return

    valid_ids = [tid for tid in confirmed_ids if not states[tid].get("event_sent")]

    if not valid_ids:
        return

    avg_conf = sum(
        states[tid].get("confidence", 0.0) * (1.0 if states.get(tid, {}).get("entry_confirmed", False) else 0.9)
        for tid in valid_ids
    ) / len(valid_ids)

    # Task 3: structural idempotency key (now session-scoped)
    sorted_tids = '-'.join(str(t) for t in sorted(valid_ids))
    event_id = f"{session_id}-{camera_id}-{target_event_type}-{sorted_tids}"

    event = {
        "event_id": event_id,
        "camera_id": camera_id,
        "event_type": target_event_type,
        "quantity": len(valid_ids),
        "tracker_ids": [int(tid) for tid in valid_ids],
        "video_t_sec": [states[tid].get("video_t_sec", 0.0) for tid in valid_ids],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "confidence": float(avg_conf),
    }

    print(f"\n[EVENT GENERATED] {target_event_type} | ID: {event_id} | QTY: {len(valid_ids)}")

    try:
        res = requests.post(api_url, json=event, timeout=2.0)
        if res.status_code == 200:
            for tid in valid_ids:
                states[tid]["event_sent"] = True
    except Exception as e:
        print(f"NETWORK ERROR: Failed to send to backend -> {e}")

class BoxStateMachine:
    def __init__(self, entry_coords, exit_coords, camera_id, api_url, target_event_type, video_source="default"):
        """
        entry_coords: tuple of two sv.Point (start, end)
        exit_coords: tuple of two sv.Point (start, end)
        """
        import supervision as sv  # lazy load

        self.camera_id = camera_id
        self.api_url = api_url
        self.target_event_type = target_event_type
        self.session_id = hashlib.sha1(video_source.encode('utf-8')).hexdigest()[:8]

        self.line_entry = sv.LineZone(start=entry_coords[0], end=entry_coords[1])
        self.line_exit = sv.LineZone(start=exit_coords[0], end=exit_coords[1])

        # Raw line endpoints for signed-distance math (Task 1)
        self._entry_start = (entry_coords[0].x, entry_coords[0].y)
        self._entry_end = (entry_coords[1].x, entry_coords[1].y)
        self._exit_start = (exit_coords[0].x, exit_coords[0].y)
        self._exit_end = (exit_coords[1].x, exit_coords[1].y)

        # Per-track FSM state
        # { tracker_id: {"state": str, "event_sent": bool, "confidence": float,
        #                 "entry_side": str|None, "exit_side": str|None,
        #                 "foot_point": tuple, "width": float, "height": float} }
        self.states = {}
        self.completed_ids = set()  # HARD LOCK to prevent duplicates

        # Task 2: recently completed tracks for ID-switch detection
        self.recent_completed_tracks = []

    def update(self, detections, frame_idx: int, fps: float):
        """
        Receives Supervision detections (post-tracker).
        Returns a list of newly confirmed tracker IDs in this tick.
        """
        # Still trigger sv.LineZone for its built-in annotations / counters
        self.line_entry.trigger(detections)
        self.line_exit.trigger(detections)

        confirmed_this_tick = []
        now = time.monotonic()

        if detections.tracker_id is None:
            return confirmed_this_tick

        for i, tracker_id in enumerate(detections.tracker_id):
            # Skip if this ID has ALREADY been counted
            if tracker_id in self.completed_ids:
                continue

            xyxy = detections.xyxy[i]
            foot = _foot_point_from_detection(xyxy)
            w, h = _bbox_size(xyxy)

            if tracker_id not in self.states:
                self.states[tracker_id] = {
                    "state": "NEW",
                    "event_sent": False,
                    "confidence": 0.0,
                    "entry_side": None,   # Task 1: hysteresis state for entry line
                    "exit_side": None,    # Task 1: hysteresis state for exit line
                    "foot_point": foot,
                    "first_foot_point": foot,
                    "width": w,
                    "height": h,
                    "frame_idx": frame_idx,
                    "first_frame_idx": frame_idx,
                    "last_frame_idx": frame_idx,
                    "video_t_sec": round(frame_idx / fps, 2) if fps else 0.0,
                }

            track = self.states[tracker_id]

            # Keep latest geometry and timing
            track["foot_point"] = foot
            track["width"] = w
            track["height"] = h
            track["frame_idx"] = frame_idx
            track["last_frame_idx"] = frame_idx
            track["video_t_sec"] = round(frame_idx / fps, 2) if fps else 0.0

            if detections.confidence is not None:
                track["confidence"] = float(detections.confidence[i])

            current_state = track["state"]

            # ---- Task 1: directional hysteresis crossing check ----
            # Build per-line sub-dicts for update_crossing
            entry_sub = {"last_side": track["entry_side"]}
            crossed_entry = update_crossing(entry_sub, foot,
                                            self._entry_start, self._entry_end)
            track["entry_side"] = entry_sub["last_side"]

            exit_sub = {"last_side": track["exit_side"]}
            crossed_exit = update_crossing(exit_sub, foot,
                                           self._exit_start, self._exit_end)
            track["exit_side"] = exit_sub["last_side"]

            # FSM transitions
            if crossed_entry and current_state in ("NEW", "ABORTED"):
                track["state"] = "LINE_1_CROSSED"

            if crossed_exit and track["state"] in ("NEW", "LINE_1_CROSSED"):
                eligible, reason = is_eligible_to_confirm(track, frame_idx)
                if not eligible:
                    track["state"] = "REJECTED_INELIGIBLE"
                    self.completed_ids.add(tracker_id)
                    print(f"[REJECTED] track {tracker_id} not eligible to confirm: {reason}")
                    continue

                # ---- Task 2: check for ID-switch before confirming ----
                candidate = {
                    "foot_point": foot,
                    "width": w,
                    "height": h,
                }
                if is_likely_id_switch(candidate, self.recent_completed_tracks, now):
                    track["state"] = "SUPPRESSED_ID_SWITCH"
                    self.completed_ids.add(tracker_id)  # lock so we don't revisit
                    print(f"[SUPPRESSED] track {tracker_id} flagged as ID-switch "
                          f"(near a recent confirm, within {REASSOC_DIST_PX}px / "
                          f"{REASSOC_WINDOW_S}s / {SIZE_RATIO_TOLERANCE*100:.0f}% size)")
                    continue

                entry_confirmed = (current_state == "LINE_1_CROSSED")
                track["state"] = "CONFIRMED"
                track["entry_confirmed"] = entry_confirmed
                self.completed_ids.add(tracker_id)
                confirmed_this_tick.append(tracker_id)

                # Record for future ID-switch checks
                self.recent_completed_tracks.append({
                    "id": tracker_id,
                    "timestamp": now,
                    "end_location": foot,
                    "width": w,
                    "height": h,
                    "frame_idx": frame_idx,
                    "video_t_sec": round(frame_idx / fps, 2) if fps else 0.0,
                })

        # Prune expired entries from the recent list
        self.recent_completed_tracks = [
            rt for rt in self.recent_completed_tracks
            if now - rt["timestamp"] <= REASSOC_WINDOW_S * 2
        ]

        return confirmed_this_tick

    # NOTE: event_id = f"{session_id}-{camera_id}-{event_type}-{sorted(tracker_ids)}"
    # This deduplicates NETWORK-LEVEL replay (same event POSTed twice) WITHIN a session.
    # It does NOT deduplicate ID-switches -- a genuine ByteTrack ID switch
    # produces a structurally different tracker_id and therefore a different
    # event_id. That dedup happens upstream in is_likely_id_switch() (Task 2),
    # before this function is ever called.
    def confirm_and_publish(self, confirmed_ids):
        publish_events(self.states, confirmed_ids, self.session_id, self.camera_id, self.target_event_type, self.api_url)

    def print_diagnostics(self):
        stuck_new = sum(1 for t in self.states.values() if t["state"] == "NEW")
        stuck_line1 = sum(1 for t in self.states.values() if t["state"] == "LINE_1_CROSSED")
        suppressed = sum(1 for t in self.states.values() if t["state"] == "SUPPRESSED_ID_SWITCH")
        rejected_ineligible = sum(1 for t in self.states.values() if t["state"] == "REJECTED_INELIGIBLE")
        confirmed = sum(1 for t in self.states.values() if t["state"] == "CONFIRMED")
        print(f"\n[DIAGNOSTICS] confirmed={confirmed} suppressed_id_switch={suppressed} "
              f"rejected_ineligible={rejected_ineligible} stuck_at_NEW={stuck_new} "
              f"stuck_at_LINE_1_CROSSED={stuck_line1} total_unique_tracker_ids={len(self.states)}")

        lifetimes = [t["last_frame_idx"] - t["first_frame_idx"] for t in self.states.values() if "last_frame_idx" in t and "first_frame_idx" in t]
        if lifetimes:
            print(f"[DIAGNOSTICS] track lifetime (frames): "
                  f"min={min(lifetimes)} max={max(lifetimes)} "
                  f"median={sorted(lifetimes)[len(lifetimes)//2]} "
                  f"pct_single_frame={sum(1 for l in lifetimes if l==0)/len(lifetimes)*100:.0f}%")

        STATIC_MOVEMENT_PX = 10  # a track that moved less than this over its whole life is "static"

        static_but_churned = 0
        for tid, t in self.states.items():
            if "first_foot_point" not in t:
                continue
            dx = t["foot_point"][0] - t["first_foot_point"][0]
            dy = t["foot_point"][1] - t["first_foot_point"][1]
            dist_moved = (dx**2 + dy**2) ** 0.5
            lifetime = t["last_frame_idx"] - t["first_frame_idx"]
            if dist_moved < STATIC_MOVEMENT_PX and lifetime < 5:
                static_but_churned += 1

        print(f"[DIAGNOSTICS] short-lived tracks with near-zero movement "
              f"(likely churn on static boxes): {static_but_churned}")

        print("[DIAGNOSTICS] Per-confirmed-track displacement:")
        for tid, t in self.states.items():
            if t["state"] != "CONFIRMED" or "first_foot_point" not in t:
                continue
            dx = t["foot_point"][0] - t["first_foot_point"][0]
            dy = t["foot_point"][1] - t["first_foot_point"][1]
            dist = (dx**2 + dy**2) ** 0.5
            flag = " <-- SUSPICIOUSLY SMALL" if dist < 50 else ""
            print(f"  track {tid}: displaced {dist:.0f}px over {t['last_frame_idx']-t['first_frame_idx']} frames{flag}")


class StagingSnapshotEngine:
    def __init__(self, roi_polygon, camera_id, api_url, target_event_type, video_source="default"):
        import hashlib
        self.roi_polygon = roi_polygon
        self.camera_id = camera_id
        self.api_url = api_url
        self.target_event_type = target_event_type
        self.session_id = hashlib.sha1(video_source.encode('utf-8')).hexdigest()[:8]
        self.line_entry = None
        self.line_exit = None

        self.state = "IDLE"
        self.last_gray_roi = None
        self.settle_start_time = None
        self.timer_val = 0.0
        self.SETTLE_REQUIRED_SEC = 3.0
        self.total_events_fired = 0

    def update(self, frame, video_t_sec, model, box_class_id):
        import cv2
        import numpy as np

        pts = np.array(self.roi_polygon, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)
        roi_frame = frame[y:y+h, x:x+w]
        
        gray_roi = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)

        if self.last_gray_roi is None:
            self.last_gray_roi = gray_roi
            return None

        frame_delta = cv2.absdiff(self.last_gray_roi, gray_roi)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        motion_amount = np.sum(thresh)
        
        self.last_gray_roi = gray_roi

        # Threshold required triggering "movement": ~2% of ROI pixels changing intensity heavily
        motion_threshold = w * h * 0.02 * 255

        if motion_amount > motion_threshold:
            self.state = "MOTION"
            self.settle_start_time = None
            self.timer_val = 0.0
        elif self.state == "MOTION":
            self.state = "SETTLING"
            self.settle_start_time = video_t_sec
            self.timer_val = 0.0
        elif self.state == "SETTLING":
            self.timer_val = video_t_sec - self.settle_start_time
            if self.timer_val >= self.SETTLE_REQUIRED_SEC:
                self.state = "IDLE"
                self.timer_val = 0.0
                return self.take_snapshot(frame, model, video_t_sec, box_class_id)
        
        return None

    def take_snapshot(self, frame, model, video_t_sec, box_class_id):
        import datetime
        import requests
        import cv2
        import numpy as np
        import supervision as sv

        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [np.array(self.roi_polygon, dtype=np.int32)], 255)
        masked = cv2.bitwise_and(frame, frame, mask=mask)

        # High confidence one-shot pass across masked frame, tuned NMS to avoid merging
        results = model(masked, imgsz=1280, conf=0.10, iou=0.82, verbose=False)[0]
        st_detections = sv.Detections.from_ultralytics(results)
        st_detections = st_detections[st_detections.class_id == box_class_id]

        count = len(st_detections)

        if count == 0:
            return st_detections

        # Assign dummy tracker IDs to trigger bounding box annotation 
        st_detections.tracker_id = np.arange(count)

        event_id = f"{self.session_id}-{self.camera_id}-{self.target_event_type}-SNAPSHOT-{self.total_events_fired}"
        self.total_events_fired += 1

        avg_conf = float(st_detections.confidence.mean()) if count > 0 else 0.0

        event = {
            "event_id": event_id,
            "camera_id": self.camera_id,
            "event_type": self.target_event_type,
            "quantity": count,
            "tracker_ids": st_detections.tracker_id.tolist(),
            "video_t_sec": [video_t_sec] * count,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "confidence": avg_conf,
        }

        print(f"\n[SNAPSHOT GENERATED] {self.target_event_type} | ID: {event_id} | QTY: {count}")

        try:
            res = requests.post(self.api_url, json=event, timeout=2.0)
            if res.status_code != 200:
                print(f"NETWORK ERROR: Failed to send to backend -> Status code {res.status_code}")
        except Exception as e:
            print(f"NETWORK ERROR: Failed to send to backend -> {e}")

        return st_detections

    def print_diagnostics(self):
        print(f"\n[DIAGNOSTICS] Snapshot events fired: {self.total_events_fired}")

