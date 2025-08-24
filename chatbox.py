from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ----------------------------
# Active customers and chat history
# ----------------------------
active_customers = {}  # room_id: unread_count
chat_history = {}      # room_id: list of {sender, message}

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

        # Initialize chat history
        if room not in chat_history:
            chat_history[room] = []

        # Send existing messages to the user who just joined
        for msg in chat_history[room]:
            emit("receive_message", msg, room=request.sid)

        # Track active customers
        if user_type == "customer":
            if room not in active_customers:
                active_customers[room] = 0
            emit("update_customers", active_customers, broadcast=True)
        elif user_type == "admin":
            emit("receive_message", {"message": f"✅ Admin joined room {room}", "sender": "admin"}, room=room)

@socketio.on("leave")
def on_leave(data):
    room = data.get("room")
    if room:
        leave_room(room)

@socketio.on("send_message")
def handle_send_message(data):
    room = data.get("room")
    message = data.get("message", "").strip()
    sender = data.get("sender", "customer")
    if room and message:
        msg_data = {"message": message, "sender": sender, "room": room}
        chat_history.setdefault(room, []).append(msg_data)  # Save message
        emit("receive_message", msg_data, room=room)

        # Increment unread count if customer sends
        if sender == "customer":
            if room in active_customers:
                active_customers[room] += 1
                emit("update_customers", active_customers, broadcast=True)

@socketio.on("typing")
def handle_typing(data):
    room = data.get("room")
    if room:
        emit("typing", data, room=room)

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
