import os
import socket
import time
import cv2                
import subprocess
import difflib

# === Configuration ===
ESP32_IP = "192.168.4.1"
ESP32_PORT = 80
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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

def run_ocr(frame):
    """Run OCR using Tesseract on a frame in memory"""
    try:
        # Save frame to temporary file
        temp_img = "temp_ocr.jpg"
        cv2.imwrite(temp_img, frame)
        
        output_path = "temp_result"
        subprocess.run(
            [TESSERACT_PATH, temp_img, output_path, "-l", "eng"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Read the output file
        txt_path = output_path + ".txt"
        if os.path.exists(txt_path):
            with open(txt_path, 'r') as f:
                text = f.read().strip()
                if text:
                    print("OCR:", text)
                    return text
        
        # Clean up temporary files
        if os.path.exists(temp_img):
            os.remove(temp_img)
        if os.path.exists(txt_path):
            os.remove(txt_path)
            
        return None
        
    except Exception as e:
        print("OCR error:", e)
        return None

def find_similar_word(med, known_meds, threshold=60):
    if not med:
        return None
    med = med.lower()
    words = med.split()

    for word in words:
        for known in known_meds:
            similarity = difflib.SequenceMatcher(None, word, known.lower()).ratio() * 100
            if similarity >= threshold:
                return known  
    return None

if __name__ == "__main__":
    cam_idx, cam_backend = find_camera()
    if cam_idx is None:
        raise RuntimeError("No working camera found.")
    print(f"Using camera index {cam_idx} (backend={cam_backend})")

    # Open camera
    cam = cv2.VideoCapture(cam_idx, cam_backend) if cam_backend is not None else cv2.VideoCapture(cam_idx)
    
    # Set a reasonable frame size
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    known_meds = ["rosulip", "ultrafen", "clovix", "naproxan"]
    last_match_time = 0
    match_cooldown = 30  # seconds
    
    try:
        while True:
            ret, frame = cam.read()
            if not ret:
                print("Failed to capture frame")
                time.sleep(1)
                continue
            
            # Display live feed
            cv2.imshow('Medicine Scanner', frame)
            
            # Only process OCR periodically to reduce CPU load
            current_time = time.time()
            if current_time - last_match_time > 5:  # Process every 5 seconds
                med = run_ocr(frame)
                if med:
                    match = find_similar_word(med, known_meds)
                    
                    if match and current_time - last_match_time > match_cooldown:
                        last_match_time = current_time
                        print(f"Match found: {match}")
                        
                        if match == "rosulip":
                            send_command("MOTOR1:5:1500")
                            time.sleep(20)
                            
                        elif match == "ultrafen":
                            send_command("MOTOR2:90:1500:CW")
                            time.sleep(2)
                            send_command("MOTOR1:5:1500")
                            time.sleep(30)  
                            send_command("MOTOR2:270:1500:CW")
                            time.sleep(2)

                        elif match == "clovix":
                            send_command("MOTOR2:180:1500:CW")
                            time.sleep(2)
                            send_command("MOTOR1:5:1500")
                            time.sleep(30)  
                            send_command("MOTOR2:180:1500:CW")
                            time.sleep(2)

                        elif match == "naproxan":
                            send_command("MOTOR2:270:1500:CW")
                            time.sleep(2)
                            send_command("MOTOR1:5:1500")
                            time.sleep(30) 
                            send_command("MOTOR2:90:1500:CW")
                            time.sleep(2)
            
            # Exit on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print("Camera released and windows closed")