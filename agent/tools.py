import uuid
from langchain.tools import tool

# 模拟知识库检索（实际可接入向量数据库）
FAQ_DICT = {}
try:
    with open("knowledge_base/faq.txt", "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                key, val = line.strip().split(":", 1)
                FAQ_DICT[key.strip()] = val.strip()
except FileNotFoundError:
    FAQ_DICT = {
        "退货政策": "您可以在签收后7天内无理由退货。",
        "退款时效": "3-5个工作日内原路退回。"
    }

@tool
def query_order(order_id: str = "") -> str:
    """查询订单状态，需要用户提供订单号。"""
    if not order_id or order_id.strip() == "":
        return "请提供订单号，例如：查询订单号 1234567890"
    return f"订单 {order_id} 当前状态：已发货，预计3天内送达。物流单号：SF{order_id[-6:]}"

@tool
def create_refund_request(order_id: str = "", reason: str = "") -> str:
    """创建退货/退款工单，需要订单号和原因。"""
    if not order_id:
        return "请提供需要退款的订单号。"
    ticket = str(uuid.uuid4())[:8]
    return f"已为您创建退货工单 {ticket}，订单号 {order_id}，原因：{reason or '未说明'}。客服将在24小时内联系您。"

@tool
def search_knowledge_base(query: str) -> str:
    """搜索客服知识库，回答政策类问题。"""
    for key, value in FAQ_DICT.items():
        if key in query or query in key:
            return f"【知识库】{key}: {value}"
    return "未找到完全匹配的答案，建议您转人工客服（400-123-4567）。"

def get_tools():
    """返回工具列表供 Agent 使用"""
    return [query_order, create_refund_request, search_knowledge_base]