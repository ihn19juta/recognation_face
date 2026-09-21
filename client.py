# import websocket
# import numpy as np
# import cv2
# import requests

# ESP32_IP = "10.150.57.89"   # IP dari serial monitor
# WS_URL = f"ws://{ESP32_IP}:81/"

# API_URL = "http://localhost:5000/api/auto-detect"

# def on_message(ws, message):

#     print("Frame received")

#     # convert ke numpy
#     np_arr = np.frombuffer(message, np.uint8)

#     # decode JPEG
#     frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

#     if frame is None:
#         print("Decode error")
#         return

#     # encode base64 untuk kirim ke Flask
#     _, buffer = cv2.imencode(".jpg", frame)

#     import base64
#     img_base64 = base64.b64encode(buffer).decode()

#     payload = {
#         "image": img_base64
#     }

#     try:
#         r = requests.post(API_URL, json=payload, timeout=2)
#         print("API Response:", r.json())
#     except:
#         print("API connection error")

# def on_open(ws):
#     print("Connected to ESP32 WebSocket")

# def on_close(ws, close_status_code, close_msg):
#     print("WebSocket closed")

# ws = websocket.WebSocketApp(
#     WS_URL,
#     on_message=on_message,
#     on_open=on_open,
#     on_close=on_close
# )

# ws.run_forever()



# import websocket
# import numpy as np
# import cv2
# import requests
# import base64

# ESP32_IP = "10.210.196.81"
# # 10.210.196.81
# WS_URL = f"ws://{ESP32_IP}:81/"
# # http://10.210.196.85:5000/
# API_URL = "http://localhost:5000/api/auto-detect"

# def on_message(ws, message):

#     np_arr = np.frombuffer(message, np.uint8)
#     frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

#     if frame is None:
#         print("Decode error")
#         return

#     print("Frame received")

#     _, buffer = cv2.imencode(".jpg", frame)
#     img_base64 = base64.b64encode(buffer).decode()

#     payload = {"image": img_base64}

#     try:
#         r = requests.post(API_URL, json=payload, timeout=2)
#         print("API:", r.json())
#     except Exception as e:
#         print("API error:", e)

# def on_open(ws):
#     print("Connected to ESP32")

# def on_close(ws, close_status_code, close_msg):
#     print("WebSocket closed")

# def on_error(ws, error):
#     print("WebSocket error:", error)

# ws = websocket.WebSocketApp(
#     WS_URL,
#     on_message=on_message,
#     on_open=on_open,
#     on_close=on_close,
#     on_error=on_error
# )

# ws.run_forever()



import websocket
import numpy as np
import cv2
import requests
import base64
import threading
import time

ESP32_IP = "10.103.46.89"
WS_URL = f"ws://{ESP32_IP}:81/"
API_URL = "http://localhost:5000/api/auto-detect"

frame_count = 0

# ================= API THREAD =================
def send_to_api(img_base64):
    try:
        r = requests.post(API_URL, json={"image": img_base64}, timeout=2)
        print("API:", r.json())
    except Exception as e:
        print("API error:", e)

# ================= WEBSOCKET =================
def on_message(ws, message):
    global frame_count

    try:
        frame_count += 1

        # 🔥 skip frame biar ringan
        if frame_count % 5 != 0:
            return

        np_arr = np.frombuffer(message, np.uint8)

        # 🔥 validasi ukuran data
        if len(np_arr) < 1000:
            print("Frame terlalu kecil, skip")
            return

        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            print("Decode error")
            return

        print("Frame OK")

        _, buffer = cv2.imencode(".jpg", frame)
        img_base64 = base64.b64encode(buffer).decode()

        # 🔥 kirim ke API di thread (anti lag)
        threading.Thread(target=send_to_api, args=(img_base64,)).start()

    except Exception as e:
        print("Processing error:", e)

def on_open(ws):
    print("✅ Connected to ESP32")

def on_close(ws, close_status_code, close_msg):
    print("❌ WebSocket closed")

def on_error(ws, error):
    print("⚠️ WebSocket error:", error)

# ================= AUTO RECONNECT =================
def start_ws():
    while True:
        try:
            print("🔄 Connecting to ESP32...")

            ws = websocket.WebSocketApp(
                WS_URL,
                on_message=on_message,
                on_open=on_open,
                on_close=on_close,
                on_error=on_error
            )

            ws.run_forever(
                skip_utf8_validation=True,
                ping_interval=10,
                ping_timeout=5
            )

        except Exception as e:
            print("Reconnect error:", e)

        print("⏳ Retry 2 detik...")
        time.sleep(2)

# ================= MAIN =================
if __name__ == "__main__":
    start_ws()