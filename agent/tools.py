import pandas as pd
import io
import os
import sys
import base64
from typing import Dict
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

# 存储每个会话的 DataFrame
_session_dataframes: Dict[str, pd.DataFrame] = {}


def _get_dataframe(session_id: str) -> pd.DataFrame:
    if session_id not in _session_dataframes:
        raise ValueError("尚未加载任何数据文件，请先上传 CSV/Excel。")
    return _session_dataframes[session_id]


def _save_dataframe(session_id: str, df: pd.DataFrame):
    _session_dataframes[session_id] = df


@tool
def load_data(file_content_b64: str, file_name: str, config: RunnableConfig) -> str:
    """加载 CSV/Excel 文件（Base64 编码）"""
    session_id = config.get("configurable", {}).get("thread_id")
    if not session_id:
        return "错误：无法获取会话ID。"
    try:
        raw_data = base64.b64decode(file_content_b64)
        ext = os.path.splitext(file_name)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(io.BytesIO(raw_data))
        elif ext in ('.xlsx', '.xls'):
            df = pd.read_excel(io.BytesIO(raw_data))
        else:
            return f"不支持的文件类型: {ext}，请上传 CSV 或 Excel。"

        _save_dataframe(session_id, df)
        info = f"✅ 加载成功！{df.shape[0]}行 x {df.shape[1]}列\n列名：{list(df.columns)}\n\n前5行预览：\n{df.head(5).to_string()}"
        return info
    except Exception as e:
        return f"加载失败: {e}"


@tool
def run_python_code(code: str, config: RunnableConfig) -> str:
    """执行 pandas 代码，返回输出及数据预览"""
    session_id = config.get("configurable", {}).get("thread_id")
    if not session_id:
        return "错误：无法获取会话ID。"

    old_stdout = sys.stdout  # 移到 try 之前，确保 finally 中可用
    try:
        df = _get_dataframe(session_id)
        namespace = {'df': df, 'pd': pd}
        sys.stdout = io.StringIO()
        exec(code, namespace)
        output = sys.stdout.getvalue()

        updated_df = namespace.get('df')
        if isinstance(updated_df, pd.DataFrame):
            _save_dataframe(session_id, updated_df)
            preview = updated_df.head(50).to_string()
            return f"✅ 执行成功！\n输出：\n{output}\n\n预览（最多50行）：\n{preview}"
        else:
            return f"✅ 执行成功！\n输出：\n{output}\n（DataFrame 未修改）"
    except Exception as e:
        return f"❌ 执行出错: {e}"
    finally:
        sys.stdout = old_stdout


@tool
def get_data_info(config: RunnableConfig) -> str:
    """获取数据统计信息"""
    session_id = config.get("configurable", {}).get("thread_id")
    if not session_id:
        return "错误：无法获取会话ID。"
    try:
        df = _get_dataframe(session_id)
        desc = df.describe(include='all').to_string()
        missing = df.isnull().sum().to_string()
        return f"📊 描述统计：\n{desc}\n\n🔍 缺失值：\n{missing}"
    except Exception as e:
        return f"获取信息失败: {e}"


# 在 tools.py 末尾（get_tools 之前）添加

@tool
def export_csv(filename: str, config: RunnableConfig) -> str:
    """
    导出当前 DataFrame 为 CSV 文件，返回下载链接。
    参数 filename: 下载的文件名（不含 .csv 后缀时自动添加）
    """
    session_id = config.get("configurable", {}).get("thread_id")
    if not session_id:
        return "错误：无法获取会话ID。"
    try:
        df = _get_dataframe(session_id)
    except ValueError as e:
        return f"错误：{e}"

    if not filename.endswith('.csv'):
        filename += '.csv'

    # 生成前端可访问的下载链接（相对路径）
    download_url = f"/download/{session_id}?filename={filename}"
    return f"✅ 数据已导出，请点击链接下载：{download_url}"


# 修改 get_tools 函数，增加 export_csv
def get_tools():
    return [load_data, run_python_code, get_data_info, export_csv]

# 在 tools.py 末尾添加以下函数

def get_session_dataframe(session_id: str):
    """获取会话的 DataFrame，若无则返回 None"""
    return _session_dataframes.get(session_id)

def delete_session_dataframe(session_id: str):
    """删除会话的 DataFrame 缓存"""
    if session_id in _session_dataframes:
        del _session_dataframes[session_id]