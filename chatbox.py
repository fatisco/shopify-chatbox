from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os

# ----------------------------
# Monkey patching for eventlet
# ----------------------------
import eventlet
eventlet.monkey_patch()  # must run before importing other modules that use sockets

# ----------------------------
# App setup
# ----------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def index():
    # Single landing route
    return render_template("landing.html")

# ----------------------------
# Socket.IO events
# ----------------------------
@socketio.on("join")
def on_join(data):
    room = data["room"]
    join_room(room)
    emit("message", {"sender": "System", "message": f"{room} joined the chat"}, room=room)

@socketio.on("leave")
def on_leave(data):
    room = data["room"]
    leave_room(room)
    emit("message", {"sender": "System", "message": f"{room} left the chat"}, room=room)

@socketio.on("message")
def handle_message(data):
    room = data.get("room")
    sender = data.get("sender", "Unknown")
    message = data.get("message", "")
    if room:
        emit("message", {"sender": sender, "message": message}, room=room)

@socketio.on("typing")
def handle_typing(data):
    room = data.get("room")
    message = data.get("message", "")
    if room:
        emit("typing", {"message": message}, room=room)

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
