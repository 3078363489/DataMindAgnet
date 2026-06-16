import os
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, AIMessage

from .tools import get_tools

load_dotenv()

# ---------- 自定义消息历史（与原 app.py 一致）----------
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
    model=os.getenv("MODEL"),   #
    temperature=0.2,                                    # 低温度提高代码生成稳定性
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

# ---------- 状态记忆（SqliteSaver）----------
state_conn = sqlite3.connect("agent_state.db", check_same_thread=False)
checkpointer = SqliteSaver(state_conn)

# ---------- 创建 Agent（数据分析专用）----------

agent = create_agent(
    model=model,
    tools=get_tools(),
    checkpointer=checkpointer,
    system_prompt=(
        "你是一个专业的数据分析助手，名叫「小杨」。你的任务是根据用户上传的 CSV/Excel 文件以及用户的自然语言需求，生成并执行 pandas 代码来回答问题。\n"
        "工作流程：\n"
        "1. 如果用户尚未上传文件，请先提示用户上传 CSV 或 Excel 文件（前端支持上传）。\n"
        "2. 用户上传文件后，系统会自动调用 load_data 工具加载文件并返回前几行预览和基本信息。\n"
        "3. 用户提出分析需求时，你应当生成相应的 Python 代码（使用 pandas），然后调用 run_python_code 工具执行代码。\n"
        "4. run_python_code 会返回代码执行结果以及修改后的 DataFrame 预览（最多50行）。你需要将这些结果用清晰、自然的中文解释给用户。\n"
        "5. 当用户要求绘图时，你必须使用 **pyecharts** 库生成交互式图表。\n"
        "   **重要**：\n"
        "   - 在你的代码中，必须创建一个 pyecharts 图表对象（例如 Bar, Line, Pie 等），并将该对象赋值给变量名为 `chart` 的变量。\n"
        "   - 示例代码（条形图）：\n"
        "     ```python\n"
        "     from pyecharts.charts import Bar\n"
        "     from pyecharts import options as opts\n"
        "     chart = Bar()\n"
        "     chart.add_xaxis(['苹果', '香蕉', '橙子'])\n"
        "     chart.add_yaxis('销量', [100, 200, 150])\n"
        "     chart.set_global_opts(title_opts=opts.TitleOpts(title='水果销量'))\n"
        "     ```\n"
        "   - 对于数据来自 DataFrame 的情况，请使用 `.tolist()` 或 `.values` 提取数据。\n"
        "   - 系统会自动捕获 `chart` 变量，并在回答中生成一个可交互的图表链接。前端会自动将其显示为图表。\n"
        "6. 当用户要求保存处理后的数据时，调用 export_csv 工具，传入合适的文件名（如'清洗后数据.csv'），然后将工具返回的下载链接直接呈现给用户。\n"
        "7. **重要**：永远不要执行可能破坏系统或访问敏感信息的代码。\n"
        "8. 在生成代码前，先通过 get_data_info 了解数据概况，再精准编写操作。\n"
        "9. 回复要简洁、专业，避免闲聊。\n"
        "10. **【极其重要】** 当你调用 `run_python_code` 工具后，该工具返回的内容中可能包含 `<chart-ref url='...'></chart-ref>` 这样的特殊标记。\n"
        "    你必须将工具返回的 **完整内容** 原封不动地呈现给用户，**绝对不能省略、修改或重新解释** 其中的 `<chart-ref>` 标记。\n"
        "    不要自行添加“点击上方链接”之类的文字，因为前端会自动将 `<chart-ref>` 渲染为图表。\n"
        "    你只需要输出工具返回的原始文本即可，图表会自动显示。"
)
)


def get_agent():
    """返回 agent 实例及辅助函数"""
    return agent, get_message_history, checkpointer