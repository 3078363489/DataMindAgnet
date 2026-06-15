import os
import sqlite3
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_community.chat_message_histories import SQLChatMessageHistory

from .tools import get_tools

load_dotenv()

# ---------- 初始化模型 ----------
model = ChatOpenAI(

    model="deepseek-ai/DeepSeek-V4-Flash",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

# ---------- 状态记忆（SqliteSaver）----------
state_conn = sqlite3.connect("agent_state.db", check_same_thread=False)
checkpointer = SqliteSaver(state_conn)

# ---------- 消息历史工厂函数 ----------
def get_message_history(session_id: str):
    """返回一个 SQLChatMessageHistory 实例，用于存储原始对话消息"""
    return SQLChatMessageHistory(
        session_id=session_id,
        connection="sqlite:///chat_history.db"
    )

# ---------- 创建 Agent ----------
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