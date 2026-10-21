"""Classify tracked passengers as sitting, standing, or walking.

Press Q while the video window is focused to stop the program.  The angle and
speed thresholds are starting values and should be calibrated for the camera's
placement in the vehicle.
"""

from collections import defaultdict, deque
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


MOVEMENT_HISTORY_SIZE = 8
WALKING_SPEED_THRESHOLD = 0.035
SITTING_KNEE_ANGLE_THRESHOLD = 145
STRAIGHT_KNEE_ANGLE_THRESHOLD = 155
KEYPOINT_CONFIDENCE_THRESHOLD = 0.35
UPPER_BODY_CONFIDENCE_THRESHOLD = 0.45
STANDING_FALLBACK_ASPECT_RATIO = 2.0
SITTING_FALLBACK_ASPECT_RATIO = 1.25
DEFAULT_CONFIRMATION_SECONDS = 1.0
DEFAULT_PERSON_CONFIDENCE = 0.55
DEFAULT_MIN_PERSON_HEIGHT = 0.10
DEFAULT_MIN_UPPER_BODY_KEYPOINTS = 2

movement_history = defaultdict(lambda: deque(maxlen=MOVEMENT_HISTORY_SIZE))
posture_states: dict[int, dict[str, str | float | None]] = {}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS_FILE = PROJECT_ROOT / "data" / "live_metrics.json"
FRAME_FILE = PROJECT_ROOT / "data" / "live_frame.jpg"


def parse_camera_source(source: str) -> int | str:
    """Use numeric camera indexes locally, or retain an RTSP/HTTP URL as text."""
    return int(source) if source.isdigit() else source


def save_live_metrics(
    source: str,
    total: int,
    sitting: int,
    standing: int,
    walking: int,
    unclear: int,
) -> None:
    """Write the newest counts for the local SafeRide-LK dashboard."""
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source,
        "updated_at": time.time(),
        "total_passengers": total,
        "sitting": sitting,
        "standing": standing,
        "walking": walking,
        "pose_unclear": unclear,
    }
    temporary_file = METRICS_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(payload), encoding="utf-8")
    temporary_file.replace(METRICS_FILE)


def save_live_frame(frame: np.ndarray) -> None:
    """Save the newest annotated frame for the local SafeRide-LK dashboard."""
    success, encoded_frame = cv2.imencode(".jpg", frame)
    if not success:
        return
    temporary_file = FRAME_FILE.with_suffix(".tmp")
    temporary_file.write_bytes(encoded_frame.tobytes())
    temporary_file.replace(FRAME_FILE)


def calculate_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Return the angle (degrees) at point b for the points a-b-c."""
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(
        a[1] - b[1], a[0] - b[0]
    )
    angle = abs(radians * 180.0 / np.pi)
    return 360 - angle if angle > 180 else angle


def angle_from_vertical(a: np.ndarray, b: np.ndarray) -> float:
    """Return how far a body segment is from vertical, in degrees."""
    dx = abs(float(b[0] - a[0]))
    dy = abs(float(b[1] - a[1]))
    return math.degrees(math.atan2(dx, max(dy, 0.0001)))


def angle_from_horizontal(a: np.ndarray, b: np.ndarray) -> float:
    """Return how far a body segment is from horizontal, in degrees."""
    return 90 - angle_from_vertical(a, b)


def classify_visible_legs(
    points: np.ndarray,
    confidences: np.ndarray,
    sitting_knee_angle_threshold: float,
) -> tuple[str | None, float | None]:
    """Recognise a straight standing leg and an L-shaped sitting leg.

    A straight standing leg has a large knee angle and both leg segments close
    to vertical. Sitting has a bent knee; the knee-angle rule is retained for
    frontal cameras where the horizontal thigh may be partly foreshortened.
    """
    # COCO keypoint 0 is the nose. It is used as an approximate head point
    # when visible, but does not invalidate a pose when cropped/occluded.
    head_is_visible = confidences[0] >= KEYPOINT_CONFIDENCE_THRESHOLD
    head = points[0]
    knee_angles: list[float] = []
    straight_leg_count = 0
    l_shaped_sitting_count = 0

    for hip_index, knee_index, ankle_index in ((11, 13, 15), (12, 14, 16)):
        leg_confidence = confidences[[hip_index, knee_index, ankle_index]]
        if not np.all(leg_confidence >= KEYPOINT_CONFIDENCE_THRESHOLD):
            continue

        hip, knee, ankle = points[hip_index], points[knee_index], points[ankle_index]
        knee_angle = calculate_angle(hip, knee, ankle)
        knee_angles.append(knee_angle)

        thigh_vertical_error = angle_from_vertical(hip, knee)
        shin_vertical_error = angle_from_vertical(knee, ankle)
        head_to_hip_error = angle_from_vertical(head, hip) if head_is_visible else 0

        # Standing straight: head → hip → knee → ankle are mostly vertical.
        if (
            knee_angle >= STRAIGHT_KNEE_ANGLE_THRESHOLD
            and thigh_vertical_error <= 35
            and shin_vertical_error <= 35
            and (not head_is_visible or head_to_hip_error <= 40)
        ):
            straight_leg_count += 1

        # Sitting L-shape: torso/head remains above the hip, thigh tends
        # toward horizontal, and shin tends toward vertical. Perspective can
        # hide the horizontal thigh, so the bent-knee fallback remains below.
        if (
            knee_angle < sitting_knee_angle_threshold
            and angle_from_horizontal(hip, knee) <= 45
            and shin_vertical_error <= 45
            and (not head_is_visible or head_to_hip_error <= 50)
        ):
            l_shaped_sitting_count += 1

    if not knee_angles:
        return None, None

    mean_knee_angle = float(np.mean(knee_angles))
    # When seated, one knee is frequently hidden by a uniform, bag, seat, or
    # another passenger. A clearly bent visible knee is enough evidence of
    # sitting; averaging it with an incorrectly estimated straight knee can
    # otherwise incorrectly produce STANDING/POSE NOT CLEAR.
    if l_shaped_sitting_count or min(knee_angles) < sitting_knee_angle_threshold:
        return "SITTING", min(knee_angles)
    if straight_leg_count:
        return "STANDING", mean_knee_angle

    # A partly bent, crossed, crouched, or badly occluded leg should not be
    # reported as confidently standing.
    return "POSE NOT CLEAR", mean_knee_angle


def calculate_speed(person_id: int, center: tuple[int, int], frame_width: int) -> float:
    """Return recent centre-point speed normalised by image width."""
    movement_history[person_id].append((time.time(), center[0], center[1]))
    history = movement_history[person_id]

    if len(history) < 4:
        return 0.0

    old_time, old_x, old_y = history[0]
    new_time, new_x, new_y = history[-1]
    elapsed = new_time - old_time
    if elapsed <= 0 or frame_width <= 0:
        return 0.0

    distance = math.hypot(new_x - old_x, new_y - old_y)
    return (distance / elapsed) / frame_width


def parse_seat_roi(value: str) -> tuple[float, float, float, float]:
    """Parse a normalised seat zone: x1,y1,x2,y2, where each value is 0..1."""
    try:
        roi = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Seat ROI must be x1,y1,x2,y2") from error
    if len(roi) != 4 or any(point < 0 or point > 1 for point in roi):
        raise argparse.ArgumentTypeError("Seat ROI values must be between 0 and 1")
    x1, y1, x2, y2 = roi
    if x1 >= x2 or y1 >= y2:
        raise argparse.ArgumentTypeError("Seat ROI must have x1 < x2 and y1 < y2")
    return roi


def point_in_seat_zone(
    center: tuple[int, int],
    seat_rois: list[tuple[float, float, float, float]],
    frame_width: int,
    frame_height: int,
) -> bool:
    """Return True when a passenger's box centre is inside a configured seat zone."""
    if frame_width <= 0 or frame_height <= 0:
        return False
    x, y = center[0] / frame_width, center[1] / frame_height
    return any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in seat_rois)


def fallback_posture(
    confidences: np.ndarray,
    box_width: int,
    box_height: int,
    in_seat_zone: bool,
) -> str | None:
    """Estimate posture only when clothing/crowding hides the lower-body points.

    This fallback is deliberately conservative. A configured seat zone is the
    most reliable fallback for long skirts, sarees, coats, and bags.
    """
    upper_body_indexes = (5, 6, 11, 12)  # shoulders and hips
    if not np.all(confidences[list(upper_body_indexes)] >= UPPER_BODY_CONFIDENCE_THRESHOLD):
        return None

    if in_seat_zone:
        return "SITTING (EST.)"

    aspect_ratio = box_height / max(box_width, 1)
    if aspect_ratio >= STANDING_FALLBACK_ASPECT_RATIO:
        return "STANDING (EST.)"
    if aspect_ratio <= SITTING_FALLBACK_ASPECT_RATIO:
        return "SITTING (EST.)"
    return None


def is_confirmed_person(
    box_confidence: float,
    confidences: np.ndarray,
    box_height: int,
    frame_height: int,
    minimum_confidence: float,
    minimum_height_ratio: float,
    minimum_upper_body_keypoints: int,
) -> bool:
    """Reject likely bags or other false person detections.

    YOLO Pose is trained for people, but a bag can occasionally receive a
    low-quality person box. A real passenger should have a sufficiently large
    box and at least a few visible shoulder/hip landmarks.
    """
    upper_body_indexes = (5, 6, 11, 12)  # shoulders and hips
    visible_upper_body_points = int(
        np.count_nonzero(confidences[list(upper_body_indexes)] >= KEYPOINT_CONFIDENCE_THRESHOLD)
    )
    return (
        box_confidence >= minimum_confidence
        and box_height / max(frame_height, 1) >= minimum_height_ratio
        and visible_upper_body_points >= minimum_upper_body_keypoints
    )


def smooth_posture(person_id: int, raw_posture: str, confirmation_seconds: float) -> str:
    """Only change a passenger's displayed posture after it remains stable.

    A brief missing limb, blur, or tracking wobble should not instantly turn a
    seated passenger into standing/walking. The first second is labelled as a
    check; after that, the last confirmed result remains on screen until a new
    result has also been stable for the same period.
    """
    now = time.time()
    state = posture_states.setdefault(
        person_id,
        {"candidate": None, "candidate_since": now, "confirmed": None, "last_seen": now},
    )
    state["last_seen"] = now

    if raw_posture != state["candidate"]:
        state["candidate"] = raw_posture
        state["candidate_since"] = now

    if now - float(state["candidate_since"]) >= confirmation_seconds:
        state["confirmed"] = raw_posture

    return str(state["confirmed"] or "POSTURE CHECKING")


def remove_stale_tracking_states(active_person_ids: set[int]) -> None:
    """Release state for people no longer in the camera view."""
    now = time.time()
    for person_id, state in list(posture_states.items()):
        last_seen = float(state["last_seen"])
        if person_id not in active_person_ids and now - last_seen > 5:
            posture_states.pop(person_id, None)
            movement_history.pop(person_id, None)


parser = argparse.ArgumentParser(description="SafeRide live posture analysis")
parser.add_argument(
    "--model",
    default="yolov8n-pose.pt",
    help="YOLO Pose model file. Use yolov8s-pose.pt for higher accuracy. Default: yolov8n-pose.pt",
)
parser.add_argument(
    "--sitting-knee-angle",
    type=float,
    default=SITTING_KNEE_ANGLE_THRESHOLD,
    help="Maximum bent-knee angle counted as sitting. Default: 145",
)
parser.add_argument(
    "--imgsz",
    type=int,
    default=640,
    help="Inference image size. Use 960 for small/distant passengers. Default: 640",
)
parser.add_argument(
    "--source",
    default="0",
    help="Camera index (0, 1, ...) or an RTSP/HTTP stream URL. Default: 0",
)
parser.add_argument(
    "--seat-roi",
    action="append",
    type=parse_seat_roi,
    default=[],
    metavar="X1,Y1,X2,Y2",
    help=(
        "Optional normalised seat area; repeat for multiple seat zones. "
        "Example: --seat-roi 0.05,0.35,0.45,0.95"
    ),
)
parser.add_argument(
    "--confirm-seconds",
    type=float,
    default=DEFAULT_CONFIRMATION_SECONDS,
    help="Seconds a new posture must remain consistent before it is shown. Default: 1.0",
)
parser.add_argument(
    "--person-confidence",
    type=float,
    default=DEFAULT_PERSON_CONFIDENCE,
    help="Minimum YOLO person confidence. Higher removes more false bags. Default: 0.55",
)
parser.add_argument(
    "--min-person-height",
    type=float,
    default=DEFAULT_MIN_PERSON_HEIGHT,
    help="Minimum person-box height as a fraction of the frame. Default: 0.10",
)
parser.add_argument(
    "--min-upper-body-keypoints",
    type=int,
    default=DEFAULT_MIN_UPPER_BODY_KEYPOINTS,
    help="Required visible shoulder/hip landmarks before counting a person. Default: 2",
)
args = parser.parse_args()
if args.confirm_seconds < 0:
    parser.error("--confirm-seconds must be zero or greater")
if not 0 <= args.person_confidence <= 1:
    parser.error("--person-confidence must be between 0 and 1")
if not 0 < args.min_person_height <= 1:
    parser.error("--min-person-height must be greater than 0 and at most 1")
if not 1 <= args.min_upper_body_keypoints <= 4:
    parser.error("--min-upper-body-keypoints must be between 1 and 4")
if not 60 <= args.sitting_knee_angle <= 170:
    parser.error("--sitting-knee-angle must be between 60 and 170")
if args.imgsz < 320:
    parser.error("--imgsz must be at least 320")
camera_source = parse_camera_source(args.source)

print("Loading YOLOv8 Pose model...")
model = YOLO(args.model)
print("Pose model loaded")
print(f"Opening camera source: {args.source}")
print(f"Accuracy mode: model {args.model}, inference size {args.imgsz}")
print(
    "Person filter: "
    f"confidence >= {args.person_confidence:.2f}, "
    f"height >= {args.min_person_height:.0%}, "
    f"upper-body keypoints >= {args.min_upper_body_keypoints}"
)
print(f"Sitting knee threshold: {args.sitting_knee_angle:.0f}°")
if args.seat_roi:
    print(f"Using {len(args.seat_roi)} seat-zone fallback area(s)")
else:
    print("No seat zones set: lower-body occlusion will remain POSE NOT CLEAR unless shape is clear")
print("Press Q to exit")

# CAP_AVFOUNDATION is the native macOS backend for connected USB cameras.
cap = (
    cv2.VideoCapture(camera_source, cv2.CAP_AVFOUNDATION)
    if isinstance(camera_source, int)
    else cv2.VideoCapture(camera_source)
)
if not cap.isOpened():
    print("ERROR: Camera could not be opened")
    raise SystemExit(1)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Could not read frame")
            break

        frame_height, frame_width = frame.shape[:2]
        for seat_x1, seat_y1, seat_x2, seat_y2 in args.seat_roi:
            cv2.rectangle(
                frame,
                (int(seat_x1 * frame_width), int(seat_y1 * frame_height)),
                (int(seat_x2 * frame_width), int(seat_y2 * frame_height)),
                (180, 80, 180),
                1,
            )
            cv2.putText(
                frame,
                "SEAT ZONE",
                (int(seat_x1 * frame_width) + 4, int(seat_y1 * frame_height) + 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (180, 80, 180),
                1,
            )
        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=args.person_confidence,
            imgsz=args.imgsz,
            verbose=False,
        )

        sitting_count = 0
        standing_count = 0
        walking_count = 0
        unclear_pose_count = 0
        total_passenger_count = 0
        active_person_ids: set[int] = set()

        if results:
            result = results[0]
            boxes = result.boxes
            keypoints = result.keypoints

            if boxes is not None and keypoints is not None:
                points_by_person = keypoints.xy.cpu().numpy()
                confidence_by_person = keypoints.conf.cpu().numpy()

                for index, box in enumerate(boxes):
                    # A pose model returns only people. A temporary index is used
                    # until ByteTrack has assigned a persistent ID.
                    person_id = int(box.id[0]) if box.id is not None else index
                    active_person_ids.add(person_id)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    points = points_by_person[index]
                    confidences = confidence_by_person[index]
                    box_confidence = float(box.conf[0])

                    if not is_confirmed_person(
                        box_confidence,
                        confidences,
                        y2 - y1,
                        frame_height,
                        args.person_confidence,
                        args.min_person_height,
                        args.min_upper_body_keypoints,
                    ):
                        continue

                    total_passenger_count += 1

                    # COCO: hips 11/12, knees 13/14, ankles 15/16.
                    # Do not treat invisible legs (reported as zero coordinates)
                    # as a bent knee. At least one whole leg must be visible.
                    visible_leg_posture, knee_angle = classify_visible_legs(
                        points, confidences, args.sitting_knee_angle
                    )
                    speed = calculate_speed(person_id, (center_x, center_y), frame_width)
                    inside_seat_zone = point_in_seat_zone(
                        (center_x, center_y), args.seat_roi, frame_width, frame_height
                    )

                    if speed > WALKING_SPEED_THRESHOLD:
                        raw_posture = "WALKING"
                    elif visible_leg_posture is None:
                        raw_posture = fallback_posture(
                            confidences,
                            x2 - x1,
                            y2 - y1,
                            inside_seat_zone,
                        )
                        raw_posture = raw_posture or "POSE NOT CLEAR"
                    elif visible_leg_posture == "POSE NOT CLEAR" and inside_seat_zone:
                        # A static passenger inside a manually marked seat area
                        # is more reliably seated than a partial, ambiguous leg.
                        raw_posture = "SITTING (EST.)"
                    else:
                        raw_posture = visible_leg_posture

                    posture = smooth_posture(
                        person_id, raw_posture, args.confirm_seconds
                    )

                    if posture.startswith("WALKING"):
                        walking_count += 1
                        color = (255, 170, 0)
                    elif posture.startswith("SITTING"):
                        sitting_count += 1
                        color = (0, 255, 0)
                    elif posture.startswith("STANDING"):
                        standing_count += 1
                        color = (0, 0, 255)
                    else:
                        unclear_pose_count += 1
                        color = (0, 255, 255)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        frame,
                        f"ID {person_id} | {posture} | "
                        f"Knee {knee_angle:.0f}" if knee_angle is not None
                        else f"ID {person_id} | {posture}",
                        (x1, max(20, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        color,
                        2,
                    )

        remove_stale_tracking_states(active_person_ids)

        cv2.putText(frame, f"Total passengers: {total_passenger_count}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, f"Sitting: {sitting_count}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, f"Standing: {standing_count}", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, f"Walking: {walking_count}", (20, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 170, 0), 2)
        cv2.putText(frame, f"Pose unclear: {unclear_pose_count}", (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        save_live_metrics(
            args.source,
            total_passenger_count,
            sitting_count,
            standing_count,
            walking_count,
            unclear_pose_count,
        )
        save_live_frame(frame)
        cv2.imshow("SafeRide Behaviour Analysis", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    cap.release()
    cv2.destroyAllWindows()
