from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app)

# ----------------------------
# Routes
# ----------------------------

@app.route("/")
def index():
    return """
    <h2>Shopify Chatbox</h2>
    <p><a href='/admin'>Admin Dashboard</a></p>
    <p><a href='/new'>Start New Customer Chat</a></p>
    """

@app.route("/new")
def new_chat():
    user_id = str(uuid.uuid4())
    return redirect(url_for("chat", user_id=user_id))

@app.route("/chat/<user_id>")
def chat(user_id):
    return render_template("chat.html", user_id=user_id)

@app.route("/admin")
def admin():
    return render_template("admin.html")

# ----------------------------
# Socket.IO Events
# ----------------------------

@socketio.on("join")
def on_join(data):
    user_id = data["user_id"]
    join_room(user_id)
    emit("status", {"msg": f"{user_id} has entered the chat"}, room=user_id)

@socketio.on("leave")
def on_leave(data):
    user_id = data["user_id"]
    leave_room(user_id)
    emit("status", {"msg": f"{user_id} has left the chat"}, room=user_id)

@socketio.on("message")
def handle_message(data):
    user_id = data["user_id"]
    msg = data["msg"]
    emit("message", {"user_id": user_id, "msg": msg}, room=user_id)

# ----------------------------
# Main
# ----------------------------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
