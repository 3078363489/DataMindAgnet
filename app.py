#!/usr/bin/env python3
import uuid
import sqlite3
import json
import base64
import os
import time
import threading
from io import BytesIO
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from langchain_core.messages import HumanMessage
from agent.graph import get_agent, get_message_history
from agent.tools import get_session_dataframe, delete_session_dataframe, CHART_STORAGE_DIR

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
    cursor.execute("""
        SELECT session_id, MAX(created_at) as last_time
        FROM message_store
        GROUP BY session_id
        ORDER BY last_time DESC
    """)
    rows = cursor.fetchall()
    sessions = []
    for session_id, last_time in rows:
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

# ==================== 图表文件清理（定时任务，可选） ====================
def clean_old_charts_periodically():
    """每隔1小时清理超过1小时的图表文件"""
    while True:
        time.sleep(3600)
        try:
            now = time.time()
            for filename in os.listdir(CHART_STORAGE_DIR):
                filepath = os.path.join(CHART_STORAGE_DIR, filename)
                if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 3600:
                    os.remove(filepath)
        except Exception:
            pass

# 启动后台清理线程（如果不想使用，可以注释掉）
cleaner_thread = threading.Thread(target=clean_old_charts_periodically, daemon=True)
cleaner_thread.start()

# ==================== 路由 ====================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "没有文件部分"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    session_id = request.form.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    file_bytes = file.read()
    file_b64 = base64.b64encode(file_bytes).decode('utf-8')

    config = {"configurable": {"thread_id": session_id}}

    from agent.tools import load_data
    result = load_data.invoke({
        "file_content_b64": file_b64,
        "file_name": file.filename
    }, config=config)

    msg_history = get_message_history(session_id)
    msg_history.add_user_message(f"上传文件：{file.filename}")
    msg_history.add_ai_message(result)

    return jsonify({"session_id": session_id, "message": result})

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

@app.route("/download/<session_id>", methods=["GET"])
def download_data(session_id):
    """下载当前会话处理后的数据为 CSV"""
    df = get_session_dataframe(session_id)
    if df is None:
        return jsonify({"error": "没有已加载的数据，请先上传文件并执行分析"}), 404

    filename = request.args.get("filename", f"data_{session_id}.csv")
    if not filename.endswith(".csv"):
        filename += ".csv"

    try:
        csv_data = df.to_csv(index=False, encoding='utf-8-sig')
        return send_file(
            BytesIO(csv_data.encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/session/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """删除指定会话的所有消息及缓存数据"""
    try:
        msg_history = get_message_history(session_id)
        msg_history.clear()
        delete_session_dataframe(session_id)
        # 注意：图表文件不按会话存储，这里不删除，由定时清理统一处理
        return jsonify({"success": True, "message": "会话已删除"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 新增：提供 pyecharts 生成的图表 HTML 文件 ====================
@app.route('/chart/<filename>')
def serve_chart(filename):
    """返回 Pyecharts 生成的图表 HTML 文件"""
    # 安全检查
    if '..' in filename or not filename.endswith('.html'):
        return "Invalid file name", 400
    try:
        return send_from_directory(CHART_STORAGE_DIR, filename)
    except FileNotFoundError:
        return "Chart not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)