#!/usr/bin/env python3
# google_listener.py -- robust final: verbose serial read, CANCEL+resend, foreground follower
# Usage:
#   source ~/gsr-env2/bin/activate
#   python3 /home/miniproj/Desktop/google_listener.py

import speech_recognition as sr
import subprocess
import time
import serial
import os
import sys

# ---------- CONFIG ----------
ARECORD_DEVICE = "plughw:2,0"     # change if your mic device differs
RECORD_SECONDS = 3
WAV_FILE = "voice.wav"

SERIAL_PORT = "/dev/ttyACM0"      # hard-coded Arduino port (no guessing)
BAUD = 115200

# Python interpreter (venv) to run qrFollower so cv2/pyzbar are available
VENV_PYTHON = "/home/miniproj/gsr-env2/bin/python3"
QR_SCRIPT_PATH = "/home/miniproj/Desktop/qrFollower_with_ack.py"

PHRASE_TO_BYTE = {
    "go to milk":  b'1', "goto milk": b'1', "milk": b'1',
    "go to bread": b'2', "goto bread": b'2', "bread": b'2',
    "go to pen":   b'3', "goto pen":  b'3', "pen": b'3'
}

# ---------- Utilities ----------
def record_chunk():
    cmd = [
        "arecord", "-D", ARECORD_DEVICE,
        "-f", "S16_LE", "-r", "16000", "-c", "1",
        "-d", str(RECORD_SECONDS),
        WAV_FILE
    ]
    try:
        subprocess.check_call(cmd)
        return True
    except KeyboardInterrupt:
        return False
    except Exception as e:
        print("arecord failed:", e)
        return False

def recognize_with_google():
    r = sr.Recognizer()
    try:
        with sr.AudioFile(WAV_FILE) as src:
            audio = r.record(src)
        return r.recognize_google(audio).lower()
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        print("Recognition error:", e)
        return ""

def port_exists():
    return os.path.exists(SERIAL_PORT)

# ---------- Robust serial send/read ----------
def send_trigger_to_arduino(byte_cmd):
    """
    Send byte_cmd (b'1', b'2', b'3'), read raw reply bytes (0.6s window),
    print raw repr + decoded text. If reply contains "Already executing" -> cancel + resend.
    Returns True if send+(optional resend) succeeded.
    """
    if not port_exists():
        print(f"DEBUG: Serial port {SERIAL_PORT} not found.")
        return False

    try:
        s = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
    except Exception as e:
        print("DEBUG: could not open serial:", e)
        return False

    try:
        # small settle to avoid reset/noise interleaving
        time.sleep(0.12)
        print(f"DEBUG: opened {SERIAL_PORT} - sending {byte_cmd!r}")
        s.write(byte_cmd)
        s.flush()

        # read raw bytes for a short window
        t0 = time.time()
        raw = b''
        while time.time() - t0 < 0.6:
            chunk = s.read(256)
            if chunk:
                raw += chunk
            else:
                time.sleep(0.02)

        if raw:
            print("DEBUG: raw reply bytes:", repr(raw))
            try:
                text = raw.decode('utf-8', errors='replace').strip()
            except Exception:
                text = str(raw)
            print("DEBUG: decoded reply:", text)
        else:
            text = ""
            print("DEBUG: no reply received (raw len 0)")

        s.close()

        # if Arduino indicates busy, attempt cancel+resend
        if ("Already executing" in text) or (b"Already executing" in raw):
            print("DEBUG: Arduino busy -> attempting CANCEL + resend")
            ok = force_cancel_and_resend(byte_cmd)
            return ok

        return True

    except Exception as e:
        print("DEBUG: runtime error during send/read:", e)
        try:
            s.close()
        except:
            pass
        return False

def force_cancel_and_resend(byte_cmd):
    """Send CANCEL\n then resend byte_cmd; read replies similarly and print them."""
    if not port_exists():
        print("DEBUG: serial port missing for CANCEL")
        return False

    try:
        s = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
    except Exception as e:
        print("DEBUG: cancel: could not open serial:", e)
        return False

    try:
        time.sleep(0.08)
        s.write(b"CANCEL\n")
        s.flush()
        print("DEBUG: Sent CANCEL\\n")
        # read immediate reply from CANCEL
        t0 = time.time()
        raw = b''
        while time.time() - t0 < 0.4:
            chunk = s.read(256)
            if chunk:
                raw += chunk
            else:
                time.sleep(0.02)
        if raw:
            print("DEBUG: raw after CANCEL:", repr(raw))
            try:
                print("DEBUG: decoded after CANCEL:", raw.decode('utf-8', errors='replace').strip())
            except:
                pass
        s.close()
    except Exception as e:
        print("DEBUG: cancel write/read error:", e)
        try:
            s.close()
        except:
            pass
        return False

    # brief pause then resend trigger
    time.sleep(0.25)
    return send_trigger_to_arduino(byte_cmd)

# ---------- Follow mode launcher ----------
def notify_follow_text():
    if not port_exists():
        print("DEBUG: cannot notify Arduino about FOLLOW - no port")
        return False
    try:
        s = serial.Serial(SERIAL_PORT, BAUD, timeout=0.2)
        time.sleep(0.08)
        s.write(b"FOLLOW\n")
        s.flush()
        # quick read
        t0 = time.time()
        raw = b''
        while time.time() - t0 < 0.4:
            chunk = s.read(256)
            if chunk:
                raw += chunk
            else:
                time.sleep(0.02)
        if raw:
            print("DEBUG: notify_follow raw:", repr(raw))
            try:
                print("DEBUG: notify_follow decoded:", raw.decode('utf-8', errors='replace').strip())
            except:
                pass
        s.close()
        return True
    except Exception as e:
        print("DEBUG: notify_follow failed:", e)
        return False

def launch_qr_follower_foreground():
    if not os.path.isfile(QR_SCRIPT_PATH):
        print("ERROR: qrFollower script not found at", QR_SCRIPT_PATH)
        return 1
    print("\n=== Launching qrFollower_with_ack.py in FOREGROUND (you will see its output) ===\n")
    try:
        ret = subprocess.call([VENV_PYTHON, QR_SCRIPT_PATH])
        print("\n=== qrFollower exited with code", ret, "===\n")
        return ret
    except Exception as e:
        print("ERROR launching qrFollower:", e)
        return 2

# ---------- Main ----------
def main():
    print("Google listener (one-shot). Say: 'Follow me' OR 'Go to milk' / 'Go to bread' / 'Go to pen'\n")
    try:
        while True:
            ok = record_chunk()
            if not ok:
                continue

            text = recognize_with_google()
            if not text:
                print("No speech recognized.\n")
                continue

            print("Heard:", text)

            # FOLLOW ME -> notify Arduino and launch follower in foreground
            if "follow me" in text:
                print("Heard 'follow me' -> notifying Arduino and launching follower (foreground).")
                notify_follow_text()
                launch_qr_follower_foreground()
                print("Listener: follower ended. Exiting.")
                return

            # LFR triggers (milk/bread/pen)
            matched = False
            for phrase, byte_cmd in PHRASE_TO_BYTE.items():
                if phrase in text:
                    matched = True
                    print(f"Matched phrase '{phrase}' -> sending {byte_cmd!r}")
                    ok = send_trigger_to_arduino(byte_cmd)
                    print("DEBUG: send_trigger_to_arduino returned", ok)
                    print("Listener exiting.\n")
                    break

            if matched:
                return

            print("No matching command. Listening again...\n")

    except KeyboardInterrupt:
        print("\nListener interrupted by user.")
    finally:
        print("Listener exiting.")

if __name__ == "__main__":
    main()