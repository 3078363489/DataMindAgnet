from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """Agent 状态（LangGraph 兼容，实际 create_agent 内部使用）"""
    messages: Annotated[List, add_messages]
    session_id: Optional[str]