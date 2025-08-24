from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)

DB_FILE = "chat.db"

# --- DB Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        message TEXT,
        timestamp TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        last_seen TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

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
    c.execute("SELECT sender, message, timestamp FROM messages WHERE sender=? OR receiver=? ORDER BY id ASC",
              (customer_name, customer_name))
    rows = c.fetchall()
    conn.close()
    return rows

def update_customer(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO customers (id, name, last_seen) VALUES ((SELECT id FROM customers WHERE name=?), ?, ?)",
              (name, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_customers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM customers")
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return rows


# --- Routes ---
@app.route("/customer/<name>")
def customer(name):
    messages = get_messages(name)
    return render_template("customer.html", customer_name=name, messages=messages)

@app.route("/admin")
def admin():
    customers = get_customers()
    return render_template("admin.html", customers=customers)


# --- Socket.IO ---
@socketio.on("join")
def handle_join(data):
    name = data["name"]
    join_room(name)
    update_customer(name)
    emit("active_customers", {"customers": get_customers()}, broadcast=True)


@socketio.on("send_message")
def handle_message(data):
    sender = data["sender"]
    receiver = data["receiver"]
    message = data["message"]

    save_message(sender, receiver, message)

    emit("receive_message", data, room=receiver)
    emit("receive_message", data, room=sender)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
