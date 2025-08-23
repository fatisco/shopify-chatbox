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
    return render_template("admin.html")

@app.route("/customer/<room_id>")
def customer(room_id):
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

@socketio.on("leave")
def on_leave(data):
    """Leave a specific chat room"""
    room = data.get("room")
    if room:
        leave_room(room)

@socketio.on("send_message")
def handle_send_message(data):
    """Send message to a specific room"""
    room = data.get("room")
    message = data.get("message", "").strip()
    if room and message:
        emit("receive_message", {"message": message}, room=room)

@socketio.on("typing")
def handle_typing(data):
    """Notify typing status"""
    room = data.get("room")
    if room:
        emit("typing", data, room=room)

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
