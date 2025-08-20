import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, join_room, emit
from datetime import datetime
import os
import random
import string
import socket

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# -------------------------
# In-memory store
# -------------------------
customers = {}
messages = {}

# Tiny notification "ding" sound (base64)
BEEP_WAV_BASE64 = (
    "UklGRgYAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQcAAAAA////AP///wD///8A"
    "////AP///wD///8A////AP///wD///8A////AP///wD///8A"
)

# -------------------------
# Helpers
# -------------------------
def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def new_customer_id(n=6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))

def ensure_customer(cid, name=None):
    if cid not in customers:
        customers[cid] = {"name": name or f"Customer-{cid}", "created": now_iso(), "last": now_iso()}
        messages[cid] = []
    return customers[cid]

# -------------------------
# Templates
# -------------------------
# Admin layout with sidebar + main chat
ADMIN_HTML = r"""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shopify Live Chat - Admin</title>
<style>
:root { --bg:#f4f4f4; --white:#fff; --black:#111; --gray:#d1d1d1; }
* { box-sizing:border-box; }
body { margin:0; font-family:Arial,sans-serif; height:100vh; display:flex; background:var(--bg); }
.wrap { display:flex; width:100%; height:100vh; }
.sidebar { width:300px; max-width:40vw; background:#fff; border-right:1px solid #ddd; display:flex; flex-direction:column; transition:left 0.3s; position:relative; z-index:1; }
.title { padding:14px 16px; font-weight:bold; text-align:center; border-bottom:1px solid #eee; }
.search { padding:10px; border-bottom:1px solid #eee; }
.search input { width:100%; padding:9px 12px; border:1px solid #ccc; border-radius:16px; outline:none; }
.list { overflow:auto; flex:1; }
.customer { padding:12px 14px; border-bottom:1px solid #f0f0f0; cursor:pointer; display:flex; align-items:center; justify-content:space-between; }
.customer:hover { background:#fafafa; }
.customer .name { font-weight:600; }
.customer .meta { font-size:12px; color:#666; }
.main { flex:1; display:flex; flex-direction:column; background:#fff; position:relative; }
.header { height:56px; display:flex; align-items:center; justify-content:center; border-bottom:1px solid #eee; font-weight:700; }
.messages { flex:1; overflow:auto; padding:14px; display:flex; flex-direction:column; background:#f9f9f9; }
.message { max-width:75%; padding:10px 14px; margin:6px 0; border-radius:20px; word-wrap:break-word; }
.admin { background:var(--black); color:#fff; align-self:flex-end; border-bottom-right-radius:6px; }
.customerMsg { background:var(--gray); color:#000; align-self:flex-start; border-bottom-left-radius:6px; }
.inputBar { display:flex; padding:10px; background:#fff; border-top:1px solid #eee; }
.inputBar input { flex:1; padding:10px; border:1px solid #ccc; border-radius:20px; outline:none; }
.inputBar button { margin-left:10px; padding:10px 14px; border:none; border-radius:20px; background:#111; color:#fff; cursor:pointer; }
.empty { flex:1; display:flex; align-items:center; justify-content:center; color:#777; }

/* Mobile responsiveness */
@media (max-width: 800px){
  .sidebar{ position:absolute; left:-300px; width:250px; height:100%; z-index:1000; }
  .sidebar.active{ left:0; }
  .toggle-sidebar{ display:block; position:absolute; top:10px; left:10px; background:#000; color:#fff; padding:8px 12px; border-radius:5px; cursor:pointer; z-index:1100; }
  .main{ margin-left:0; flex:1; }
}
</style>
</head>
<body>
<div class="wrap">
  <div class="toggle-sidebar" onclick="document.querySelector('.sidebar').classList.toggle('active')">☰</div>
  <div class="sidebar">
    <div class="title">Shopify Live Chat</div>
    <div class="search"><input id="search" placeholder="Search customers..." oninput="filterList()"></div>
    <div class="list" id="list"></div>
  </div>
  <div class="main">
    <div class="header" id="chatHeader">Shopify Live Chat</div>
    <div class="messages" id="messages"><div class="empty" id="empty">Select a customer</div></div>
    <div class="inputBar">
      <input id="msg" placeholder="Type a message..." onkeypress="if(event.key==='Enter') sendMsg()">
      <button onclick="sendMsg()">Send</button>
    </div>
  </div>
</div>

<audio id="ding" preload="auto"></audio>

<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script>
const beep = "{{ beep }}";
document.getElementById('ding').src = URL.createObjectURL(new Blob([Uint8Array.from(atob(beep), c=>c.charCodeAt(0))], {type:'audio/wav'}));

const socket = io({transports:['websocket','polling']});
let current = null; 
let allCustomers = [];

fetch("/api/customers").then(r=>r.json()).then(data=>{ allCustomers = data; renderList(allCustomers); });

function filterList(){ 
    const q=document.getElementById('search').value.toLowerCase(); 
    renderList(allCustomers.filter(c=>(c.name||'').toLowerCase().includes(q) || (c.id||'').toLowerCase().includes(q))); 
}

function renderList(list){
  const wrap = document.getElementById('list'); 
  wrap.innerHTML="";
  list.forEach(c=>{
    const d=document.createElement('div'); 
    d.className='customer'; 
    d.onclick=()=>openChat(c.id,c.name);
    const left=document.createElement('div'); 
    left.innerHTML='<div class="name">'+(c.name||c.id)+'</div><div class="meta">'+(c.last||'')+'</div>';
    const right=document.createElement('div'); 
    right.className='meta'; 
    right.textContent=c.id;
    d.appendChild(left); 
    d.appendChild(right); 
    wrap.appendChild(d);
  });
}

function openChat(cid,name){
  current=cid; 
  document.getElementById('chatHeader').textContent="Shopify Live Chat"; 
  document.getElementById('messages').innerHTML="";
  fetch('/api/history/'+cid).then(r=>r.json()).then(rows=>{
    if(!rows.length){ 
      const e=document.createElement('div'); 
      e.className='empty'; 
      e.textContent='No messages yet'; 
      document.getElementById('messages').appendChild(e); 
    } else rows.forEach(addBubble);
    socket.emit('join_room', {room: cid}); 
    scrollDown();
  });
}

function addBubble(m){ 
    const msg=document.createElement('div'); 
    msg.className='message '+(m.role==='admin'?'admin':'customerMsg'); 
    msg.textContent=m.text; 
    document.getElementById('messages').appendChild(msg); 
}

function scrollDown(){ const box=document.getElementById('messages'); box.scrollTop=box.scrollHeight; }

function sendMsg(){ 
    if(!current) return; 
    const inp=document.getElementById('msg'); 
    const txt=inp.value.trim(); 
    if(!txt) return; 
    socket.emit('chat_message',{room:current, role:'admin', text:txt}); 
    inp.value=''; 
}

socket.on('chat_message',function(data){
  if(data.room===current){ 
    addBubble(data); 
    scrollDown(); 
    if(data.role==='customer'){   // admin only hears
        document.getElementById('ding').play().catch(()=>{}); 
    } 
  }
  refreshCustomers();
});

function refreshCustomers(){ fetch("/api/customers").then(r=>r.json()).then(data=>{ allCustomers=data; filterList(); }); }
setInterval(refreshCustomers,4000);
</script>
</body>
</html>
"""

# Customer HTML remains the same as before, full-width mobile-friendly
CUSTOMER_HTML = r"""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shopify Live Chat</title>
<style>
:root { --bg:#f4f4f4; --white:#fff; --black:#111; --gray:#d1d1d1; }
* { box-sizing:border-box; }
body { margin:0; font-family:Arial,sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; background:var(--bg); }
.chat { width:100%; max-width:400px; height:100vh; background:#fff; display:flex; flex-direction:column; }
.header { height:56px; display:flex; align-items:center; justify-content:center; border-bottom:1px solid #eee; font-weight:700; }
.messages { flex:1; overflow:auto; padding:14px; display:flex; flex-direction:column; background:#f9f9f9; }
.message { max-width:75%; padding:10px 14px; margin:6px 0; border-radius:20px; word-wrap:break-word; }
.admin { background:var(--black); color:#fff; align-self:flex-end; border-bottom-right-radius:6px; }
.customerMsg { background:var(--gray); color:#000; align-self:flex-start; border-bottom-left-radius:6px; }
.inputBar { display:flex; padding:10px; background:#fff; border-top:1px solid #eee; }
.inputBar input { flex:1; padding:10px; border:1px solid #ccc; border-radius:20px; outline:none; }
.inputBar button { margin-left:10px; padding:10px 14px; border:none; border-radius:20px; background:#111; color:#fff; cursor:pointer; }

/* Mobile adjustments */
@media (max-width:500px){
  .chat { max-width:100%; height:100%; }
  .header, .inputBar input, .inputBar button { font-size:14px; }
}
</style>
</head>
<body>
<div class="chat">
  <div class="header">Shopify Live Chat</div>
  <div class="messages" id="messages"></div>
  <div class="inputBar">
    <input id="msg" placeholder="Type a message..." onkeypress="if(event.key==='Enter') sendMsg()">
    <button onclick="sendMsg()">Send</button>
  </div>
</div>

<audio id="ding" preload="auto"></audio>

<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script>
const beep = "{{ beep }}";
document.getElementById('ding').src = URL.createObjectURL(new Blob([Uint8Array.from(atob(beep), c=>c.charCodeAt(0))], {type:'audio/wav'}));

const socket = io({transports:['websocket','polling']});
const room = "{{ room }}";
const role = "customer";

// Join room and load history
socket.emit('join_room', {room});
fetch('/api/history/'+room).then(r=>r.json()).then(rows=>{ rows.forEach(addBubble); scrollDown(); });

function addBubble(m){
  const d = document.createElement('div');
  d.className = 'message ' + (m.role==='admin' ? 'admin':'customerMsg');
  d.textContent = m.text;
  document.getElementById('messages').appendChild(d);
  scrollDown();
}

function scrollDown(){ 
  const box = document.getElementById('messages'); 
  box.scrollTop = box.scrollHeight; 
}

function sendMsg(){
  const input = document.getElementById('msg');
  const text = input.value.trim();
  if(!text) return;

  // Immediately display customer's message
  addBubble({role:'customer', text:text});

  socket.emit('chat_message',{room, role, text});
  input.value='';
}

// Listen to messages from admin only
socket.on('chat_message', function(data){
  if(data.room===room && data.role==='admin'){
    addBubble(data);
    document.getElementById('ding')?.play().catch(()=>{});
  }
});
</script>
</body>
</html>
"""

# -------------------------
# Routes
# -------------------------
@app.route("/admin")
def admin_dashboard():
    return render_template_string(ADMIN_HTML, beep=BEEP_WAV_BASE64)

@app.route("/new")
def new_chat():
    cid = new_customer_id()
    ensure_customer(cid)
    return redirect(url_for("customer_chat", customer_id=cid))

@app.route("/chat/<customer_id>")
def customer_chat(customer_id):
    ensure_customer(customer_id)
    return render_template_string(CUSTOMER_HTML, room=customer_id)

@app.route("/api/customers")
def api_customers():
    result = []
    for cid, c in customers.items():
        result.append({
            "id": cid,
            "name": c.get("name"),
            "last": c.get("last")
        })
    return jsonify(result)

@app.route("/api/history/<customer_id>")
def api_history(customer_id):
    ensure_customer(customer_id)
    return jsonify(messages[customer_id])

# -------------------------
# SocketIO
# -------------------------
@socketio.on("join_room")
def on_join(data):
    room = data.get("room")
    join_room(room)

@socketio.on("chat_message")
def handle_message(data):
    room = data.get("room")
    role = data.get("role")
    text = data.get("text")
    ensure_customer(room)
    messages[room].append({"role": role, "text": text})
    emit("chat_message", {"room": room, "role": role, "text": text}, to=room)

# -------------------------
# Run server
# -------------------------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
