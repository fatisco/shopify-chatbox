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
    room = data.get("room")
    user_type = data.get("user_type")  # "admin" or "customer"
    if room:
        join_room(room)
        # Only show join message to the user themselves
        if user_type == "admin":
            emit("receive_message", {"message": f"✅ You joined room {room}"}, room=request.sid)
        elif user_type == "customer":
            emit("receive_message", {"message": f"✅ You joined the chat"}, room=request.sid)

@socketio.on("leave")
def on_leave(data):
    room = data.get("room")
    if room:
        leave_room(room)

@socketio.on("join")
def on_join(data):
    room = data.get("room")
    user_type = data.get("user_type")
    join_room(room)
    if user_type == "customer":
        emit("customer_joined", {"room": room}, room="admin-global")

@socketio.on("send_message")
def handle_send_message(data):
    room = data.get("room")
    message = data.get("message", "").strip()
    sender = data.get("sender", "Unknown")
    if room and message:
        # Send to everyone except the sender to prevent duplicates
        emit("receive_message", {"message": message, "sender": sender}, room=room, include_self=False)

@socketio.on("typing")
def handle_typing(data):
    room = data.get("room")
    if room:
        # Just show "Typing" for the other user
        emit("typing", {"message": "Typing"}, room=room, include_self=False)

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
