import uuid
from flask import Flask, request, jsonify, render_template
from agent.graph import get_agent, get_message_history
import sqlite3
import json
from datetime import datetime
app = Flask(__name__)

# 获取全局 agent 实例及辅助函数
agent, get_msg_history, _ = get_agent()

@app.route("/")
def index():
    """提供前端聊天页面"""
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """聊天 API 端点"""
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message'"}), 400

    user_input = data["message"].strip()
    if not user_input:
        return jsonify({"error": "Message empty"}), 400

    session_id = data.get("session_id", str(uuid.uuid4()))

    # 获取消息历史对象
    msg_history = get_msg_history(session_id)

    # 构建消息列表：历史消息 + 当前用户消息
    messages_to_send = list(msg_history.messages)  # 已经是 HumanMessage/AIMessage 对象
    from langchain_core.messages import HumanMessage
    messages_to_send.append(HumanMessage(content=user_input))

    # 调用 Agent（config 中的 thread_id 用于恢复状态记忆）
    response = agent.invoke(
        {"messages": messages_to_send},
        config={"configurable": {"thread_id": session_id}}
    )

    # 提取 AI 回复
    ai_reply = response["messages"][-1].content

    # 保存本次对话到消息历史
    msg_history.add_user_message(user_input)
    msg_history.add_ai_message(ai_reply)

    return jsonify({
        "session_id": session_id,
        "response": ai_reply
    })

@app.route("/sessions", methods=["GET"])
def get_sessions():
    """获取所有历史会话列表（从 chat_history.db 中查询）"""
    try:
        # 连接消息历史数据库
        conn = sqlite3.connect("chat_history.db")
        cursor = conn.cursor()
        # 查询所有 session_id，以及每个会话的最新消息时间
        cursor.execute("""
            SELECT session_id, MAX(created_at) as last_time 
            FROM message_store 
            GROUP BY session_id 
            ORDER BY last_time DESC
        """)
        rows = cursor.fetchall()
        sessions = []
        for row in rows:
            session_id = row[0]
            # 获取该会话的第一条用户消息作为预览
            cursor.execute("""
                SELECT data FROM message_store 
                WHERE session_id = ? AND type = 'human'
                ORDER BY created_at ASC LIMIT 1
            """, (session_id,))
            first_msg_row = cursor.fetchone()
            preview = first_msg_row[0] if first_msg_row else "新会话"
            # 解析 JSON 获取文本
            try:
                msg_data = json.loads(preview)
                preview = msg_data.get('content', preview)[:30]
            except:
                preview = preview[:30]
            sessions.append({
                "session_id": session_id,
                "preview": preview,
                "last_time": row[1]
            })
        conn.close()
        return jsonify(sessions)
    except Exception as e:
        # 如果表不存在，返回空列表
        return jsonify([])

@app.route("/session/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    """获取某个会话的完整聊天记录"""
    try:
        conn = sqlite3.connect("chat_history.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT type, data, created_at FROM message_store 
            WHERE session_id = ? 
            ORDER BY created_at ASC
        """, (session_id,))
        rows = cursor.fetchall()
        messages = []
        for row in rows:
            msg_type = row[0]  # 'human' 或 'ai'
            data = row[1]
            created_at = row[2]
            try:
                msg_data = json.loads(data)
                content = msg_data.get('content', '')
            except:
                content = data
            messages.append({
                "role": "user" if msg_type == "human" else "assistant",
                "content": content,
                "time": created_at
            })
        conn.close()
        return jsonify(messages)
    except Exception as e:
        return jsonify([])
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)