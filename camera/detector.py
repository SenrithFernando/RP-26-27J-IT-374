import argparse

import cv2
from ultralytics import YOLO

def parse_camera_source(source: str) -> int | str:
    """Use numeric camera indexes locally, or retain an RTSP/HTTP URL as text."""
    return int(source) if source.isdigit() else source


parser = argparse.ArgumentParser(description="SafeRide live passenger detection")
parser.add_argument(
    "--source",
    default="0",
    help="Camera index (0, 1, ...) or an RTSP/HTTP stream URL. Default: 0",
)
args = parser.parse_args()
camera_source = parse_camera_source(args.source)

print("Loading YOLOv8 model...")
model = YOLO("yolov8n.pt")

print("Model loaded")
print(f"Opening camera source: {args.source}")
print("Press Q to exit")

cap = (
    cv2.VideoCapture(camera_source, cv2.CAP_AVFOUNDATION)
    if isinstance(camera_source, int)
    else cv2.VideoCapture(camera_source)
)

if not cap.isOpened():
    print("ERROR: Camera could not be opened")
    raise SystemExit(1)

while True:
    ret, frame = cap.read()

    if not ret:
        print("ERROR: Could not read frame")
        break

    # COCO class 0 is person, so other detected objects are excluded.
    results = model(frame, classes=[0], verbose=False)
    person_count = 0

    for result in results:
        for box in result.boxes:
            person_count += 1
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"Person {confidence:.2f}",
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

    cv2.putText(
        frame,
        f"Passengers: {person_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2,
    )
    cv2.imshow("SafeRide Passenger Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
