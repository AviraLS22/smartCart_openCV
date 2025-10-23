sudo apt install python3-opencv python3-picamera2 python3-serial
from picamera2 import Picamera2
import cv2
import time
import serial

# ---- Serial connection to Arduino ----
# Adjust '/dev/ttyUSB0' or '/dev/ttyACM0' depending on your Arduino port
arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
time.sleep(2)

# ---- Initialize Camera ----
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480)}))
picam2.start()
time.sleep(1)

detector = cv2.QRCodeDetector()
frame_center_x = 320  # half of 640px width

print("Starting QR-follow system. Press 'q' to quit.")

while True:
    frame = picam2.capture_array()
    data, bbox, _ = detector.detectAndDecode(frame)

    if bbox is not None:
        # Draw box around QR
        for i in range(len(bbox)):
            p1 = tuple(map(int, bbox[i][0]))
            p2 = tuple(map(int, bbox[(i+1) % len(bbox)][0]))
            cv2.line(frame, p1, p2, (255, 0, 0), 2)

        # Find QR center
        x_center = int(sum([p[0][0] for p in bbox]) / len(bbox))
        y_center = int(sum([p[0][1] for p in bbox]) / len(bbox))
        cv2.circle(frame, (x_center, y_center), 5, (0, 255, 0), -1)

        # Control logic
        if x_center < frame_center_x - 50:
            cmd = 'L'
        elif x_center > frame_center_x + 50:
            cmd = 'R'
        else:
            cmd = 'F'

        arduino.write(cmd.encode())
        print(f"QR detected ({data}), sending command: {cmd}")

    else:
        arduino.write(b'S')
        print("No QR detected → STOP")

    cv2.imshow("QR Follow", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

picam2.stop()
arduino.close()
cv2.destroyAllWindows()
