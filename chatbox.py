from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def index():
    return render_template("landing.html")

@app.route("/admin")
def admin():
    """Admin interface expects ?room=ROOMID in query string"""
    return render_template("admin.html")

@app.route("/customer/<room_id>")
def customer(room_id):
    """Customer interface with a unique room ID"""
    return render_template("customer.html", room_id=room_id)

# ----------------------------
# Socket.IO events
# ----------------------------
@socketio.on("join")
def on_join(data):
    """Join a specific chat room"""
    room = data.get("room")
    if room:
        join_room(room)
        print(f"User joined room: {room}")

@socketio.on("leave")
def on_leave(data):
    """Leave a specific chat room"""
    room = data.get("room")
    if room:
        leave_room(room)
        print(f"User left room: {room}")

@socketio.on("send_message")
def handle_send_message(data):
    """
    Send message to a specific room
    `data` must include:
      - room: room id
      - message: message text
      - from: "customer" or "admin"
    """
    room = data.get("room")
    message = data.get("message", "").strip()
    sender = data.get("from", "customer")
    if room and message:
        emit(
            "receive_message",
            {"message": message, "from": sender},
            room=room
        )
        print(f"Message from {sender} in room {room}: {message}")

@socketio.on("send_message")
def handle_send_message(data):
    """Send message to a specific room"""
    room = data.get("room")
    message = data.get("message", "").strip()
    sender = data.get("from", "customer")  # default to customer if not specified
    if room and message:
        emit("receive_message", {"message": message, "from": sender}, room=room)


# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
