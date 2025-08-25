from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

DB_FILE = os.path.join(os.path.dirname(__file__), "chatbox.db")

# --- DB setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_message(room, sender, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (room, sender, message) VALUES (?, ?, ?)", (room, sender, message))
    conn.commit()
    conn.close()

def load_messages(room):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sender, message FROM messages WHERE room = ? ORDER BY id ASC", (room,))
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
    room = data.get("room")
    if not room:
        return
    join_room(room)

    # load all history for this room
    history = load_messages(room)
    emit("load_history", history, room=request.sid)

@socketio.on("send_message")
def handle_send_message(data):
    room = data.get("room")
    sender = data.get("sender", "Unknown")
    message = data.get("message", "").strip()
    if not (room and message):
        return

    save_message(room, sender, message)

    # broadcast to all participants (including admin if connected)
    emit("receive_message", {"sender": sender, "message": message, "room": room}, room=room)

    # notify admin dashboard of active customer
    emit("active_customers", {"room": room}, broadcast=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
