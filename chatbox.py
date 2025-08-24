from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from datetime import datetime

# --- App setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret!")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- DB setup ---
DB_FILE = os.path.join(os.path.dirname(__file__), "chat.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Messages table
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)
    # Customers table
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

# --- DB functions ---
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
        SELECT sender, message, timestamp 
        FROM messages 
        WHERE sender=? OR receiver=? 
        ORDER BY id ASC
    """, (customer_name, customer_name))
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "message": r[1], "timestamp": r[2]} for r in rows]

def update_customer(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM customers WHERE name=?", (name,))
    row = c.fetchone()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if row:
        c.execute("UPDATE customers SET last_seen=? WHERE id=?", (now, row[0]))
    else:
        c.execute("INSERT INTO customers (name, last_seen) VALUES (?, ?)", (name, now))
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
def landing():
    return render_template("landing.html")

@app.route("/customer/<name>")
def customer(name):
    try:
        messages = get_messages(name)
        update_customer(name)  # mark last seen
        return render_template("customer.html", customer_name=name, messages=messages)
    except Exception as e:
        return f"Error loading customer page: {e}"

@app.route("/admin")
def admin():
    try:
        customers = get_customers()
        return render_template("admin.html", customers=customers)
    except Exception as e:
        return f"Error loading admin page: {e}"

# --- Socket.IO events ---
@socketio.on("join")
def handle_join(data):
    name = data.get("name")
    if not name:
        return
    join_room(name)
    update_customer(name)
    emit("active_customers", {"customers": get_customers()}, broadcast=True)

@socketio.on("send_message")
def handle_message(data):
    sender = data.get("sender")
    receiver = data.get("receiver")
    message = data.get("message")
    if not sender or not receiver or not message:
        return
    save_message(sender, receiver, message)
    # Broadcast message to both sender and receiver rooms
    emit("receive_message", {"sender": sender, "message": message}, room=receiver)
    emit("receive_message", {"sender": sender, "message": message}, room=sender)
    # Update admin sidebar
    emit("active_customers", {"customers": get_customers()}, room="admin")

@socketio.on("register_admin")
def handle_admin(data):
    join_room("admin")
    emit("active_customers", {"customers": get_customers()}, room=request.sid)

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
