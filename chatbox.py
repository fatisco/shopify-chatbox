from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")  # safe default
socketio = SocketIO(app, cors_allowed_origins="*")

# ----------------------------
# Routes
# ----------------------------

@app.route("/customer/<customer_id>")
def customer(customer_id):
    return render_template("customer.html", customer_id=customer_id)

@app.route("/admin")
def admin():
    return render_template("admin.html")

# ----------------------------
# Socket.IO Events
# ----------------------------

@socketio.on("join")
def on_join(data):
    room = data["room"]
    join_room(room)
    emit("message", {"sender": "System", "message": f"{room} joined"}, room=room)

@socketio.on("leave")
def on_leave(data):
    room = data["room"]
    leave_room(room)
    emit("message", {"sender": "System", "message": f"{room} left"}, room=room)

@socketio.on("message")
def handle_message(data):
    room = data["room"]
    sender = data["sender"]
    message = data["message"]
    emit("message", {"sender": sender, "message": message}, room=room)

# ----------------------------
# Main (for local dev only)
# ----------------------------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
