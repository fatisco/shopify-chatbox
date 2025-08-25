from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

DB_FILE = os.path.join(os.path.dirname(__file__), "chatbox.db")

# --- DB Setup ---
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            last_seen DATETIME
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- DB helpers ---
def save_message(room, sender, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (room, sender, message) VALUES (?, ?, ?)", (room, sender, message))
    conn.commit()
    conn.close()

def get_messages(room):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sender, message FROM messages WHERE room=? ORDER BY id ASC", (room,))
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "message": r[1]} for r in rows]

def update_customer(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO customers (id, name, last_seen) VALUES ((SELECT id FROM customers WHERE name=?), ?, ?)",
              (name, name, datetime.now()))
    conn.commit()
    conn.close()

def get_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM customers ORDER BY last_seen DESC")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

def get_unread_count(room, admin_joined_time=None):
    """Get count of messages since admin last joined (optional enhancement)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if admin_joined_time:
        c.execute("SELECT COUNT(*) FROM messages WHERE room=? AND ts > ? AND sender != 'admin'", 
                 (room, admin_joined_time))
    else:
        c.execute("SELECT COUNT(*) FROM messages WHERE room=? AND sender != 'admin'", (room,))
    count = c.fetchone()[0]
    conn.close()
    return count

# --- Routes ---
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/customer/<customer_id>")
def customer(customer_id):
    return render_template("customer.html", customer_id=customer_id)

@app.route("/admin")
def admin():
    return render_template("admin.html")

# --- Socket.IO ---
@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on("join")
def handle_join(data):
    room = data.get("room")
    if not room:
        return
    
    join_room(room)
    update_customer(room)
    print(f"Client {request.sid} joined room: {room}")

    # send chat history to this socket only
    history = get_messages(room)
    emit("load_history", {"room": room, "messages": history})

    # update active customers for all clients (so admin sees updated list)
    socketio.emit("active_customers", {"customers": get_customers()})

@socketio.on("send_message")
def handle_message(data):
    room = data.get("room")
    sender = data.get("sender")
    message = data.get("message")
    
    if not (room and sender and message):
        print(f"Invalid message data: {data}")
        return

    # Validate message content
    message = message.strip()
    if not message:
        return

    print(f"Message from {sender} in room {room}: {message}")
    
    # save to DB first
    save_message(room, sender, message)
    update_customer(room)

    # send to everyone in the room (including sender)
    socketio.emit("receive_message", {
        "room": room, 
        "sender": sender, 
        "message": message
    }, room=room)

    # Clear typing indicator when message is sent
    socketio.emit("user_stopped_typing", {
        "room": room,
        "sender": sender
    }, room=room)

    # If this is a customer message, notify all admins (even if they're not in the room)
    if sender != "admin":
        socketio.emit("new_customer_message", {
            "customer": room,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    # update admin active customers list
    socketio.emit("active_customers", {"customers": get_customers()})

@socketio.on("typing")
def handle_typing(data):
    room = data.get("room")
    sender = data.get("sender")
    
    if not (room and sender):
        return
    
    # Broadcast typing indicator to others in the room
    socketio.emit("user_typing", {
        "room": room,
        "sender": sender
    }, room=room)

@socketio.on("stop_typing")
def handle_stop_typing(data):
    room = data.get("room")
    sender = data.get("sender")
    
    if not (room and sender):
        return
    
    # Broadcast stop typing to others in the room
    socketio.emit("user_stopped_typing", {
        "room": room,
        "sender": sender
    }, room=room)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
