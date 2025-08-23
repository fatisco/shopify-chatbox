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
    return """
    <h2>Chatbox is running!</h2>
    <p>Use /admin?room=customer_id for admin</p>
    <p>Use /customer/&lt;customer_id&gt; for customer</p>
    """

@app.route("/customer/<customer_id>")
def customer(customer_id):
    return render_template("customer.html", customer_id=customer_id)

# ----------------------------
# Socket.IO events
# ----------------------------
@socketio.on("join")
def on_join(data):
    room = data["room"]
    join_room(room)
    emit("message", {"sender": "System", "message": f"{room} joined the chat"}, room=room)

@app.route("/")
def index():
    return render_template("landing.html")

@socketio.on("leave")
def on_leave(data):
    room = data["room"]
    leave_room(room)
    emit("message", {"sender": "System", "message": f"{room} left the chat"}, room=room)

@socketio.on("message")
def handle_message(data):
    room = data.get("room", "general")
    sender = data.get("sender", "Unknown")
    message = data.get("message", "")
    emit("message", {"sender": sender, "message": message}, room=room)

@socketio.on("typing")
def handle_typing(data):
    room = data.get("room", "general")
    message = data.get("message", "")
    emit("typing", {"message": message}, room=room)

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
