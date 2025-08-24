from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from datetime import datetime

# --- App setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- DB file ---
DB_FILE = os.path.join(os.path.dirname(__file__), "chat.db")

# --- DB setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
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

# --- DB helper functions ---
def save_message(sender, receiver, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)",
        (sender, receiver, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_messages(customer_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT sender, message, timestamp FROM messages WHERE sender=? OR receiver=? ORDER BY id ASC",
        (customer_name, customer_name)
    )
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "message": r[1], "timestamp": r[2]} for r in rows]

def update_customer(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO customers (name, last_seen) VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen
    """, (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM customers ORDER BY last_seen DESC")
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return rows

# --- Routes ---
@app.route("/")
def index():
    return "Chatbox is running!"

@app.route("/customer/<name>")
def customer(name):
    messages = get_messages(name)
    return render_template("customer.html", customer_name=name, messages=messages)

@app.route("/admin")
def admin():
    customers = get_customers()
    return render_template("admin.html", customers=customers)

# --- Socket.IO events ---
@socketio.on("join")
def handle_join(data):
    """
    data: { name: <customer_name> }
    """
    name = data.get("name")
    if not name:
        return
    join_room(name)
    update_customer(name)

    # Send updated active customer list to all admins
    emit("active_customers", {"customers": get_customers()}, broadcast=True)

    # Send previous messages to the joining client
    history = get_messages(name)
    emit("chat_history", {"messages": history})

@socketio.on("send_message")
def handle_message(data):
    """
    data: { sender: <>, receiver: <>, message: <> }
    """
    sender = data.get("sender")
    receiver = data.get("receiver")
    message = data.get("message", "").strip()
    if not (sender and receiver and message):
        return

    save_message(sender, receiver, message)

    # Send message to both sender and receiver rooms
    emit("receive_message", {"sender": sender, "message": message}, room=receiver)
    emit("receive_message", {"sender": sender, "message": message}, room=sender)

    # Update active customers for admin
    if sender != "admin":
        emit("active_customers", {"customers": get_customers()}, room="admin")

@socketio.on("register_admin")
def handle_admin_join(data):
    join_room("admin")
    # Send current active customers on admin connect
    emit("active_customers", {"customers": get_customers()})

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
