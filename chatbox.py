from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import os

# --- App setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- DB setup ---
DB_FILE = os.path.join(os.path.dirname(__file__), "chatbox.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

def save_message(room, sender, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (room, sender, message) VALUES (?, ?, ?)", (room, sender, message))
    conn.commit()
    conn.close()

def load_messages(room, limit=500):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sender, message FROM messages WHERE room = ? ORDER BY id ASC LIMIT ?", (room, limit))
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "message": r[1]} for r in rows]

init_db()

# --- Routes ---
@app.route("/")
def index():
    return render_template("landing.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/customer/<room_id>")
def customer(room_id):
    return render_template("customer.html", room_id=room_id)

# --- Socket events ---
@socketio.on("join")
def on_join(data):
    """
    data: { room: <room_id>, user_type: "admin"|"customer" (optional) }
    When a socket joins a room, we send the persisted history to that socket only.
    """
    room = data.get("room")
    if not room:
        return
    join_room(room)

    # load historical messages for that room and send *only to this socket*
    history = load_messages(room)
    # send history to the joining socket only
    emit("load_history", history, room=request.sid)

    # If admin wants a global admin room for notifications, they can join 'admin'
    user_type = data.get("user_type")
    if user_type == "admin":
        join_room("admin")  # optional: admin global room

@socketio.on("leave")
def on_leave(data):
    room = data.get("room")
    if room:
        leave_room(room)

@socketio.on("send_message")
def handle_send_message(data):
    """
    data: { room: <room_id>, sender: "Admin"|"Customer" or username, message: <text> }
    Clients are expected to append their own outgoing message locally.
    Server saves and broadcasts to other participants (include_self=False) to avoid duplicates.
    """
    room = data.get("room")
    sender = data.get("sender", "Unknown")
    message = data.get("message", "").strip()
    if not (room and message):
        return

    # persist
    save_message(room, sender, message)

    # broadcast to room but exclude the sender socket (so the sender doesn't get duplicate)
    emit("receive_message", {"sender": sender, "message": message}, room=room, include_self=False)

    # Also notify admin global room so admin UI (sidebar) can track active customers
    emit("customer_message_event", {"room": room, "sender": sender, "message": message}, room="admin")

@socketio.on("typing")
def handle_typing(data):
    """
    data: { room: <room_id> }
    Server emits 'typing' to the room but excludes the typing sender.
    """
    room = data.get("room")
    if not room:
        return
    emit("typing", {"message": "Typing"}, room=room, include_self=False)

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
