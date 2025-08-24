from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

DB_FILE = os.path.join(os.path.dirname(__file__), "chatbox.db")

# --- Database setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
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

def save_message(sender, receiver, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)",
              (sender, receiver, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_messages(customer_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT sender, receiver, message, timestamp
        FROM messages
        WHERE sender=? OR receiver=?
        ORDER BY id ASC
    """, (customer_name, customer_name))
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "receiver": r[1], "message": r[2], "timestamp": r[3]} for r in rows]

def update_customer(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO customers (id, name, last_seen)
        VALUES ((SELECT id FROM customers WHERE name=?), ?, ?)
        ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen
    """, (name, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM customers ORDER BY last_seen DESC")
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return rows

# --- Initialize DB ---
init_db()

# --- Routes ---
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/customer/<customer_name>")
def customer(customer_name):
    messages = get_messages(customer_name)
    return render_template("customer.html", customer_name=customer_name, messages=messages)

@app.route("/admin")
def admin():
    customers = get_customers()
    return render_template("admin.html", customers=customers)

# --- SocketIO events ---
@socketio.on("join")
def handle_join(data):
    name = data.get("name")
    if not name:
        return
    join_room(name)
    update_customer(name)
    emit("active_customers", {"customers": get_customers()}, broadcast=True)

@socketio.on("send_message")
def handle_send_message(data):
    sender = data.get("sender")
    receiver = data.get("receiver")
    message = data.get("message")
    if not sender or not receiver or not message:
        return
    save_message(sender, receiver, message)
    # Send message to both sender and receiver rooms
    emit("receive_message", {"sender": sender, "receiver": receiver, "message": message}, room=receiver)
    emit("receive_message", {"sender": sender, "receiver": receiver, "message": message}, room=sender)
    update_customer(receiver)
    emit("active_customers", {"customers": get_customers()}, broadcast=True)

# --- Run app ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
