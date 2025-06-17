import os
import socket
import time
import cv2
from ultralytics import YOLO
import random
import string
from datetime import datetime

def random_txt_timestamp():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")

# === Configuration ===
ESP32_IP = "192.168.4.1"
ESP32_PORT = 80

def send_command(cmd: str):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ESP32_IP, ESP32_PORT))
            s.sendall((cmd + "\n").encode())
    except Exception as e:
        print("Connection failed:", e)

def find_camera(max_idx=5):
    """Try MSMF, DSHOW, then default backend on indices 0..max_idx-1."""
    backends = [cv2.CAP_MSMF, cv2.CAP_DSHOW, None]
    for idx in range(max_idx):
        for b in backends:
            cap = cv2.VideoCapture(idx, b) if b is not None else cv2.VideoCapture(idx)
            if not cap.isOpened():
                cap.release()
                continue
            ret, _ = cap.read()
            cap.release()
            if ret:
                return idx, b
    return None, None

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.dirname(__file__))

    cam_idx, cam_backend = find_camera()
    if cam_idx is None:
        raise RuntimeError("No working camera found.")
    print(f"Using camera index {cam_idx} (backend={cam_backend})")

    # Open camera
    cam = cv2.VideoCapture(cam_idx, cam_backend) if cam_backend is not None else cv2.VideoCapture(cam_idx)
    
    # Set a reasonable frame size
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Load YOLO model
    model = YOLO(os.path.join(base_dir, "runs", "detect", "train", "weights", "best.pt"))
    
    # Variables for controlling detection frequency
    last_detection_time = 0
    detection_interval = 2  # seconds
    
    try:
        while True:
            current_time = time.time()
            
            # Grab frame
            ret, frame = cam.read()
            if not ret:
                print("Failed to capture frame")
                time.sleep(1)
                continue
            
            # Display live feed
            cv2.imshow('Medicine Detection', frame)
            
            # Only process detection periodically
            if current_time - last_detection_time > detection_interval:
                last_detection_time = current_time
                
                # Run YOLO detection directly on the frame
                results = model.predict(
                    source=frame,
                    conf=0.55,
                    stream=True  # More efficient for video
                )

                has_fault = False
                has_ok = False
                max_confidence = 0
                
                for res in results:
                    for box in res.boxes:
                        confidence = float(box.conf[0])
                        name = model.names[int(box.cls[0])]
                        print("Detected:", name, "with confidence:", confidence)
                        
                        if (name == "lost_pills_back" or  name == "lost_pills_front"):
                            has_fault = True
                        elif (name == "full_pills_back" or  name == "full_pills_front")  and (confidence >= 0.50):
                            has_ok = True
                            max_confidence = max(max_confidence, confidence)
                
                if has_fault:
                    send_command("MOTOR2:90:1500:CW")
                    time.sleep(2)
                    send_command("MOTOR1:5:1500")
                    time.sleep(26)
                    send_command("MOTOR2:270:1500:CW")
                    time.sleep(2)
                elif has_ok:
                    print("High confidence OK detected:", max_confidence)
                    send_command("MOTOR1:5:1500")
                    time.sleep(26)
                
                print("-" * 60)
            
            # Exit on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print("Camera released and windows closed")