import os
import json
import asyncio
import websockets
from flask import Flask
from flask_cors import CORS  # Enable CORS for the frontend
import firebase_admin
from firebase_admin import credentials, db, messaging
from dotenv import load_dotenv

load_dotenv()

# Flask setup
app = Flask(__name__)
CORS(app)  # Allow CORS for all domains

# Firebase setup
firebase_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

if firebase_credentials:
    creds = json.loads(firebase_credentials)
    if not firebase_admin._apps:
        cred = credentials.Certificate(creds)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://aquamans-47d16-default-rtdb.asia-southeast1.firebasedatabase.app/"
        })
        print("✅ Firebase Connected Successfully!")
else:
    print("❌ Error: GOOGLE_APPLICATION_CREDENTIALS_JSON not found.")
    exit()

# Firebase references
refPh = db.reference("Notification/PH")
refTemp = db.reference("Notification/Temperature")
refTurb = db.reference("Notification/Turbidity")
ref = db.reference("Sensors")

@app.route("/", methods=["GET"])
def index():
    return "🌊 AQUACARE: THE BRIDGE BETWEEN THE GAPS"

# WebSocket Handler
async def handle_websocket(websocket, path):
    if path != "/ws":
        await websocket.close()
        return

    await websocket.send(json.dumps({"message": "✅ You're now connected to the WebSocket server"}))

    try:
        async for message in websocket:
            print(f"📩 Received message: {message}")
            try:
                data = json.loads(message)

                if isinstance(data, dict) and all(k in data for k in ["PH", "Temperature", "Turbidity"]):
                    sensor_data = {
                        "PH": data["PH"],
                        "Temperature": data["Temperature"],
                        "Turbidity": data["Turbidity"]
                    }

                    updateToDb(sensor_data)
                    await checkThreshold(sensor_data, websocket)

                    await websocket.send(json.dumps({"PH": sensor_data["PH"]}))
                    await websocket.send(json.dumps({"Temperature": sensor_data["Temperature"]}))
                    await websocket.send(json.dumps({"Turbidity": sensor_data["Turbidity"]}))
                else:
                    await websocket.send(json.dumps({"error": "Invalid data format"}))
            except Exception as e:
                print(f"❌ Error handling message: {e}")
                await websocket.send(json.dumps({"error": "Error processing data"}))
    except Exception as e:
        print(f"❌ Connection error: {e}")
    finally:
        print("🔌 A client disconnected.")

# Firebase update function
def updateToDb(data):
    ref.update(data)
    print("✅ Successfully updated Firebase")
    print("✅ Firebase updated with:", data)

# FCM function
def send_fcm_notification(title, body):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        topic="aquacare"
    )

    try:
        response = messaging.send(message)
        print(f"✅ FCM sent successfully: {response}")
        print(f"✅ FCM notification sent: {response}")
    except Exception as e:
        print(f"❌ FCM sending failed: {e}")
        print(f"❌ Failed to send FCM notification: {e}")

# Check thresholds and send alerts if needed
async def checkThreshold(data, websocket):
    ph_value = refPh.get()
    temp_value = refTemp.get()
    turb_value = refTurb.get()

    ph = data["PH"]
    temp = data["Temperature"]
    turb = data["Turbidity"]

    if ph_value and ph_value["Min"] and ph_value["Max"]:
        if ph < ph_value["Min"] or ph > ph_value["Max"]:
            await websocket.send(json.dumps({"alertForPH": "⚠️ PH value is out of range!"}))
            send_fcm_notification("PH Alert", f"PH value {ph} is out of range!")

    if temp_value and temp_value["Min"] and temp_value["Max"]:
        if temp < temp_value["Min"] or temp > temp_value["Max"]:
            await websocket.send(json.dumps({"alertForTemp": "⚠️ Temperature value is out of range!"}))
            send_fcm_notification("Temperature Alert", f"Temperature value {temp} is out of range!")

    if turb_value and turb_value["Min"] and turb_value["Max"]:
        if turb < turb_value["Min"] or turb > turb_value["Max"]:
            await websocket.send(json.dumps({"alertForTurb": "⚠️ Turbidity value is out of range!"}))
            send_fcm_notification("Turbidity Alert", f"Turbidity value {turb} is out of range!")

# WebSocket server
async def run_websocket():
    port = int(os.environ.get("PORT", 10000))
    server = await websockets.serve(handle_websocket, "0.0.0.0", port, path="/ws")  # Add the path here
    print(f"🚀 WebSocket server is running on port {port}...")
    await server.wait_closed()

# Flask runner (async mode)
def run_flask():
    app.run(host="0.0.0.0", port=5000)

# Main
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_flask())
    loop.create_task(run_websocket())
    loop.run_forever()
