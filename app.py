import os
from flask import Flask, render_template, request, jsonify, session, send_file
import sqlite3
import wikipedia
import json
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")  # required for sessions
wikipedia.set_lang("bn")

DB_PATH = "super_ai.db"

# =========================
# Database setup
# =========================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE
    )
    """)
    # Knowledge table
    c.execute("""
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT UNIQUE,
        answer TEXT
    )
    """)
    # Chat history table
    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sender TEXT,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()
init_db()

# =========================
# DB Functions
# =========================
def get_answer_from_db(question):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT answer FROM knowledge WHERE question=?", (question,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def save_answer_to_db(question, answer):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO knowledge (question, answer) VALUES (?, ?)", (question, answer))
    conn.commit()
    conn.close()

def save_chat_history(user, sender, message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # get user_id
    c.execute("SELECT id FROM users WHERE username=?", (user,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT OR IGNORE INTO users(username) VALUES (?)", (user,))
        c.execute("SELECT id FROM users WHERE username=?", (user,))
        row = c.fetchone()
    user_id = row[0]
    # save message
    c.execute("INSERT INTO chat_history(user_id, sender, message) VALUES (?, ?, ?)", (user_id, sender, message))
    conn.commit()
    conn.close()

def get_user_chat_history(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (user,))
    row = c.fetchone()
    if not row:
        return []
    user_id = row[0]
    c.execute("SELECT sender, message, timestamp FROM chat_history WHERE user_id=? ORDER BY timestamp ASC", (user_id,))
    history = c.fetchall()
    conn.close()
    return [{"sender": s, "message": m, "timestamp": t} for s,m,t in history]

# =========================
# Wikipedia
# =========================
def get_answer_from_wikipedia(question):
    try:
        summary = wikipedia.summary(question, sentences=2)
        return summary + "\n\nSource: Wikipedia 📚"
    except:
        return None

# =========================
# Routes
# =========================
@app.route("/")
def index():
    # Assign a session username if not exists
    if "username" not in session:
        session["username"] = f"user_{os.urandom(4).hex()}"
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()
    user = session.get("username")
    if not question:
        return jsonify({"answer": "প্রশ্ন দিতে হবে।"})

    # 1️⃣ Check Teach DB
    answer = get_answer_from_db(question)
    if answer:
        save_chat_history(user, "ai", answer)
        return jsonify({"answer": answer})

    # 2️⃣ Wikipedia fallback
    wiki_answer = get_answer_from_wikipedia(question)
    if wiki_answer:
        save_chat_history(user, "ai", wiki_answer)
        return jsonify({"answer": wiki_answer})

    # 3️⃣ Unknown question
    unknown_msg = "আমি এখনো জানি না। তুমি কি আমাকে শিখাবে?"
    save_chat_history(user, "ai", unknown_msg)
    return jsonify({"answer": unknown_msg})

@app.route("/teach", methods=["POST"])
def teach():
    data = request.get_json()
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()
    user = session.get("username")
    if not question or not answer:
        return jsonify({"status": "error", "message": "প্রশ্ন ও উত্তর উভয়ই দিতে হবে।"})
    save_answer_to_db(question, answer)
    save_chat_history(user, "ai", "✅ নতুন তথ্য সংরক্ষিত হয়েছে।")
    return jsonify({"status": "success"})

@app.route("/history")
def history():
    user = session.get("username")
    return jsonify(get_user_chat_history(user))

@app.route("/export")
def export_chat():
    user = session.get("username")
    history = get_user_chat_history(user)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Smart AI Chat History", ln=True, align="C")
    pdf.ln(5)
    for msg in history:
        pdf.multi_cell(0, 8, f"[{msg['timestamp']}] {msg['sender'].upper()}: {msg['message']}")
    export_file = "chat_history.pdf"
    pdf.output(export_file)
    return send_file(export_file, as_attachment=True)

# =========================
# Admin Panel Routes
# =========================
@app.route("/admin/knowledge")
def admin_knowledge():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, question, answer FROM knowledge")
    data = c.fetchall()
    conn.close()
    return jsonify([{"id":i, "question":q, "answer":a} for i,q,a in data])

@app.route("/admin/delete/<int:id>", methods=["POST"])
def admin_delete(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM knowledge WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status":"success"})

# =========================
# Run app
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
