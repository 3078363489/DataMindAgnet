#!/usr/bin/env python3
import uuid
import sqlite3
import json
from flask import Flask, request, jsonify, render_template
from langchain_core.messages import HumanMessage

from agent.graph import get_agent, get_message_history

app = Flask(__name__)

agent, _, _ = get_agent()

# ==================== 辅助函数：直接查询自定义表结构 ====================
def get_raw_messages(session_id: str):
    """返回该会话的所有消息（role, content）"""
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT type, message FROM message_store WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    messages = []
    for typ, msg_json in rows:
        try:
            data = json.loads(msg_json)
            content = data.get('content', '')
        except:
            content = str(msg_json)
        messages.append({
            "role": "user" if typ == "human" else "assistant",
            "content": content
        })
    return messages

def get_all_sessions():
    """获取所有会话，预览第一条用户消息，按最后活跃时间排序"""
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    # 获取每个会话的最后一条消息的 created_at
    cursor.execute("""
        SELECT session_id, MAX(created_at) as last_time
        FROM message_store
        GROUP BY session_id
        ORDER BY last_time DESC
    """)
    rows = cursor.fetchall()
    sessions = []
    for session_id, last_time in rows:
        # 获取第一条用户消息作为预览
        cursor.execute("""
            SELECT message FROM message_store
            WHERE session_id = ? AND type = 'human'
            ORDER BY created_at ASC LIMIT 1
        """, (session_id,))
        first_msg = cursor.fetchone()
        preview = "新对话"
        if first_msg:
            try:
                data = json.loads(first_msg[0])
                preview = data.get('content', '新对话')[:30]
            except:
                preview = str(first_msg[0])[:30]
        sessions.append({
            "session_id": session_id,
            "preview": preview,
            "last_time": last_time
        })
    conn.close()
    return sessions

# ==================== 路由 ====================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Missing message"}), 400

    user_input = data["message"].strip()
    session_id = data.get("session_id", str(uuid.uuid4()))

    msg_history = get_message_history(session_id)
    messages_to_send = msg_history.messages + [HumanMessage(content=user_input)]

    config = {"configurable": {"thread_id": session_id}}
    response = agent.invoke({"messages": messages_to_send}, config=config)
    ai_reply = response["messages"][-1].content

    msg_history.add_user_message(user_input)
    msg_history.add_ai_message(ai_reply)

    return jsonify({"session_id": session_id, "response": ai_reply})

@app.route("/sessions", methods=["GET"])
def get_sessions():
    return jsonify(get_all_sessions())

@app.route("/session/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    return jsonify(get_raw_messages(session_id))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)