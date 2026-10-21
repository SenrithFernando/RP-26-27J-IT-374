import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Camera could not be opened")
    raise SystemExit(1)

print("Camera started successfully")
print("Press Q to close")

while True:
    ret, frame = cap.read()

    if not ret:
        print("ERROR: Could not read camera frame")
        break

    cv2.imshow("SafeRide Camera Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
