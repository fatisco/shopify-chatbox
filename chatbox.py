from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Track active customer rooms
active_rooms = {}  # room_id: {'customers': [sid,...]}

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
        if user_type == "customer":
            if room not in active_rooms:
                active_rooms[room] = {'customers': []}
            if request.sid not in active_rooms[room]['customers']:
                active_rooms[room]['customers'].append(request.sid)
            # Notify all admins about new active customer
            emit("new_customer", {"room": room}, broadcast=True)
        elif user_type == "admin":
            emit("receive_message", {"message": f"✅ Admin joined room {room}", "sender": "admin"}, room=room)

@socketio.on("leave")
def on_leave(data):
    room = data.get("room")
    if room:
        leave_room(room)
        # Remove customer from active_rooms
        for r in active_rooms:
            if request.sid in active_rooms[r]['customers']:
                active_rooms[r]['customers'].remove(request.sid)

@socketio.on("send_message")
def handle_send_message(data):
    room = data.get("room")
    message = data.get("message", "").strip()
    sender = data.get("sender", "Unknown")
    if room and message:
        emit("receive_message", {"message": message, "sender": sender}, room=room)

@socketio.on("typing")
def handle_typing(data):
    room = data.get("room")
    sender = data.get("sender")
    if room:
        emit("typing", {"sender": sender}, room=room)

@socketio.on("request_active_customers")
def send_active_customers():
    # Send list of all active rooms
    rooms = list(active_rooms.keys())
    emit("active_customers", {"rooms": rooms})

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
