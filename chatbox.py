from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*")

DB_FILE = "chat.db"

# --- DB Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room TEXT,
        sender TEXT,
        message TEXT,
        ts TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

def save_message(room, sender, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (room, sender, message, ts) VALUES (?, ?, ?, ?)",
              (room, sender, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def load_history(room):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sender, message FROM messages WHERE room=? ORDER BY id ASC", (room,))
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "message": r[1]} for r in rows]

active_customers = set()

# --- Routes ---
@app.route("/")
def index():
    return render_template("landing.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/customer/<customer_id>")
def customer(customer_id):
    return render_template("customer.html", customer_id=customer_id)

# --- Socket.IO Events ---
@socketio.on("join")
def handle_join(data):
    room = data.get("room")
    user_type = data.get("user_type")
    if not room: return

    join_room(room)
    if user_type=="customer":
        active_customers.add(room)
        emit("active_customers", {"customers": list(active_customers)}, broadcast=True)
    
    # send message history to this socket only
    history = load_history(room)
    emit("load_history", history, room=request.sid)

@socketio.on("send_message")
def handle_message(data):
    room = data.get("room")
    sender = data.get("sender")
    message = data.get("message")
    if not (room and message): return

    save_message(room, sender, message)

    # broadcast to the room including sender
    emit("receive_message", {"room": room, "sender": sender, "message": message}, room=room)

    # update admin active customer list
    emit("active_customers", {"customers": list(active_customers)}, room="admin")

# --- Run ---
if __name__=="__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
