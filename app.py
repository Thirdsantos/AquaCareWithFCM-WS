import os
import json
import asyncio
import websockets
from flask import Flask
import threading
import firebase_admin
from firebase_admin import credentials, db, messaging
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Firebase setup
firebase_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

if firebase_credentials:
    creds = json.loads(firebase_credentials)
    if not firebase_admin._apps:
        cred = credentials.Certificate(creds)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://aquamans-47d16-default-rtdb.asia-southeast1.firebasedatabase.app/"
        })
        print("✅ Firebase Connected Successfully")
else:
    print("❌ Error: GOOGLE_APPLICATION_CREDENTIALS_JSON not found.")
    exit()

refPh = db.reference("Notification/PH")
refTemp = db.reference("Notification/Temperature")
refTurb = db.reference("Notification/Notification/Turbidity")
ref = db.reference("Sensors")
refNotif = db.reference("Notifications")

FCM_TOPIC = "aquacare-notifs"

@app.route("/")
def index():
    return "✅ AQUACARE THE BRIDGE BETWEEN THE GAPS"

# -------------------- WebSocket Logic --------------------

async def handle_websocket(websocket, path):
    await websocket.send(json.dumps({"message": "✅ You're now connected to the WebSocket server"}))

    try:
        async for message in websocket:
            print(f"📨 Received message: {message}")
            try:
                data = json.loads(message)

                if isinstance(data, dict) and "PH" in data and "Temperature" in data and "Turbidity" in data:
                    sensor_data = {
                        "PH": data["PH"],
                        "Temperature": data["Temperature"],
                        "Turbidity": data["Turbidity"]
                    }

                    updateToDb(sensor_data)
                    await checkThreshold(sensor_data, websocket)

                    await websocket.send(json.dumps(sensor_data))
                else:
                    await websocket.send(json.dumps({"error": "Invalid data format"}))
            except Exception as e:
                print(f"⚠️ Error handling message: {e}")
                await websocket.send(json.dumps({"error": "Error processing data"}))
    except Exception as e:
        print(f"❌ Connection error: {e}")
    finally:
        print("🔌 A client disconnected.")

def updateToDb(data):
    ref.update(data)
    print("✅ Successfully updated Firebase")

def send_fcm_notification(title, body):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            topic=FCM_TOPIC
        )
        response = messaging.send(message)
        print(f"📲 FCM Notification sent: {response}")
    except Exception as e:
        print(f"⚠️ Error sending FCM notification: {e}")

async def checkThreshold(data, websocket):
    ph_value = refPh.get()
    temp_value = refTemp.get()
    turb_value = refTurb.get()

    ph = data["PH"]
    temp = data["Temperature"]
    turb = data["Turbidity"]

    if ph_value and ph_value["Min"] != 0 and ph_value["Max"] != 0:
        if ph < ph_value["Min"] or ph > ph_value["Max"]:
            await websocket.send(json.dumps({"alertForPH": "PH value is out of range"}))
            send_fcm_notification("PH Alert", f"PH value {ph} is out of range")

    if temp_value and temp_value["Min"] != 0 and temp_value["Max"] != 0:
        if temp < temp_value["Min"] or temp > temp_value["Max"]:
            await websocket.send(json.dumps({"alertForTemp": "Temperature value is out of range"}))
            send_fcm_notification("Temperature Alert", f"Temperature value {temp} is out of range")

    if turb_value and turb_value["Min"] != 0 and turb_value["Max"] != 0:
        if turb < turb_value["Min"] or turb > turb_value["Max"]:
            await websocket.send(json.dumps({"alertForTurb": "Turbidity value is out of range"}))
            send_fcm_notification("Turbidity Alert", f"Turbidity value {turb} is out of range")

# -------------------- Run Flask + WebSocket --------------------

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

async def run_websocket():
    port = int(os.environ.get("WS_PORT", 8765))
    server = await websockets.serve(handle_websocket, "0.0.0.0", port)
    print(f"🧩 WebSocket server is running on port {port}...")
    await server.wait_closed()

if __name__ == "__main__":
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Run WebSocket server in the main event loop
    asyncio.run(run_websocket())
