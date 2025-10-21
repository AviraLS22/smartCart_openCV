from picamera2 import Picamera2
import cv2
import time

# Initialize the camera
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()
time.sleep(1)  # allow camera to warm up

# QR Code detector
detector = cv2.QRCodeDetector()

print("Starting QR Scanner. Press 'q' to quit.")

while True:
    # Capture the latest frame (Picamera2 auto-updates the array)
    frame = picam2.capture_array()

    if frame is None:
        print("⚠️ No frame captured, retrying...")
        time.sleep(0.05)
        continue

    # Detect QR code
    data, bbox, _ = detector.detectAndDecode(frame)

    if bbox is not None:
        for i in range(len(bbox)):
            p1 = tuple(map(int, bbox[i][0]))
            p2 = tuple(map(int, bbox[(i+1) % len(bbox)][0]))
            cv2.line(frame, p1, p2, (255, 0, 0), 2)

        if data:
            x, y = int(bbox[0][0][0]), int(bbox[0][0][1]) - 10
            cv2.putText(frame, data, (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 250, 120), 2)
            print("Data found:", data)

    # Show the live preview
    cv2.imshow("QR Scanner", frame)

    # Exit on pressing 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean up
cv2.destroyAllWindows()
picam2.stop()
print("Stopped.")
