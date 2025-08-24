from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

DB_FILE = "chatbox.db"

# --- Database setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            sender TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            last_seen TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_message(room, sender, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (room, sender, message, timestamp) VALUES (?, ?, ?, ?)",
              (room, sender, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_messages(room):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sender, message, timestamp FROM messages WHERE room=? ORDER BY id ASC", (room,))
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "message": r[1], "timestamp": r[2]} for r in rows]

def update_customer(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO customers (name, last_seen)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen
    """, (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM customers ORDER BY last_seen DESC")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

# --- Routes ---
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/customer/<room_id>")
def customer(room_id):
    return render_template("customer.html", room_id=room_id)

# --- Socket.IO events ---
@socketio.on("join")
def handle_join(data):
    room = data.get("room")
    user_type = data.get("user_type")
    if not room:
        return
    join_room(room)
    if user_type == "customer":
        update_customer(room)
    # Send chat history to the joining socket
    emit("load_history", get_messages(room), room=request.sid)
    # Update active customers to all admins
    emit("active_customers", {"customers": get_customers()}, room="admin")

@socketio.on("send_message")
def handle_message(data):
    room = data.get("room")
    sender = data.get("sender")
    message = data.get("message")
    if not (room and message):
        return
    save_message(room, sender, message)
    # Broadcast message to room
    emit("receive_message", {"sender": sender, "message": message}, room=room)
    # Notify admin of customer activity
    emit("active_customers", {"customers": get_customers()}, room="admin")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
