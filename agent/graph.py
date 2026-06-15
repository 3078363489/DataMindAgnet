import os
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent       # 修正导入
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, AIMessage

from .tools import get_tools

load_dotenv()

# ---------- 自定义消息历史（与 app.py 中原版一致）----------
class CustomSQLiteMessageHistory:
    def __init__(self, session_id: str, db_path: str = "chat_history.db"):
        self.session_id = session_id
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    @property
    def messages(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT type, message FROM message_store WHERE session_id = ? ORDER BY created_at ASC",
            (self.session_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        result = []
        for typ, msg_json in rows:
            try:
                data = json.loads(msg_json)
                content = data.get('content', '')
            except:
                content = str(msg_json)
            if typ == 'human':
                result.append(HumanMessage(content=content))
            else:
                result.append(AIMessage(content=content))
        return result

    def add_user_message(self, content: str):
        self._add_message('human', content)

    def add_ai_message(self, content: str):
        self._add_message('ai', content)

    def _add_message(self, msg_type: str, content: str):
        msg_data = json.dumps({"content": content})
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO message_store (session_id, type, message, created_at) VALUES (?, ?, ?, ?)",
            (self.session_id, msg_type, msg_data, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def clear(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM message_store WHERE session_id = ?", (self.session_id,))
        conn.commit()
        conn.close()

def get_message_history(session_id: str):
    """返回自定义消息历史实例"""
    return CustomSQLiteMessageHistory(session_id)

# ---------- 初始化模型 ----------
model = ChatOpenAI(
    model=os.getenv("MODEL"),          # 根据你的实际模型修改
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

# ---------- 状态记忆（SqliteSaver）----------
state_conn = sqlite3.connect("agent_state.db", check_same_thread=False)
checkpointer = SqliteSaver(state_conn)

# ---------- 创建 Agent（使用 create_react_agent）----------
agent = create_agent(
    model=model,
    tools=get_tools(),
    checkpointer=checkpointer,
    system_prompt=(
        "你是智能客服助手「小智」。请用中文、礼貌、简洁地回答问题。\n"
        "当用户询问订单时，调用 query_order 工具（如果没提供订单号则询问）。\n"
        "当用户要求退款时，调用 create_refund_request。\n"
        "当用户问政策、规则时，调用 search_knowledge_base。\n"
        "用户情绪激动时，先道歉并主动建议转人工。"
    )
)
def get_agent():
    """返回 agent 实例及辅助函数"""
    return agent, get_message_history, checkpointer