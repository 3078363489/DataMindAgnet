import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib.font_manager")
import pandas as pd
import io
import os
import sys
import base64
import uuid
from typing import Dict
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pyecharts.charts import Bar, Line, Pie, Scatter, HeatMap, Boxplot, Map, Funnel, Gauge
from pyecharts import options as opts
from pyecharts.globals import CurrentConfig

# 设置 CDN 为可访问的地址（解决白屏问题）
CurrentConfig.ONLINE_HOST = "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/"
# 存储每个会话的 DataFrame
_session_dataframes: Dict[str, pd.DataFrame] = {}

# 图表存储目录（相对于项目根目录）
CHART_STORAGE_DIR = "pyecharts_charts"
os.makedirs(CHART_STORAGE_DIR, exist_ok=True)

def _get_dataframe(session_id: str) -> pd.DataFrame:
    if session_id not in _session_dataframes:
        raise ValueError("尚未加载任何数据文件，请先上传 CSV/Excel。")
    return _session_dataframes[session_id]

def _save_dataframe(session_id: str, df: pd.DataFrame):
    _session_dataframes[session_id] = df

def _clean_old_charts(max_age_seconds: int = 3600):
    """清理超过指定时间的图表文件（避免磁盘占满）"""
    try:
        now = os.path.getmtime(__file__)  # 用一个基准时间，实际应该用time.time()
        # 更准确的方法：
        import time
        now = time.time()
        for filename in os.listdir(CHART_STORAGE_DIR):
            filepath = os.path.join(CHART_STORAGE_DIR, filename)
            if os.path.isfile(filepath):
                if now - os.path.getmtime(filepath) > max_age_seconds:
                    os.remove(filepath)
    except Exception:
        pass

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
    """执行 pandas + pyecharts 代码，返回输出、数据预览及交互式图表引用"""
    session_id = config.get("configurable", {}).get("thread_id")
    if not session_id:
        return "错误：无法获取会话ID。"

    old_stdout = sys.stdout
    try:
        df = _get_dataframe(session_id)

        # 准备命名空间，导入常用库
        namespace = {
            'df': df,
            'pd': pd,
            'Bar': Bar,
            'Line': Line,
            'Pie': Pie,
            'Scatter': Scatter,
            'HeatMap': HeatMap,
            'Boxplot': Boxplot,
            'Map': Map,
            'Funnel': Funnel,
            'Gauge': Gauge,
            'opts': opts,
            '__builtins__': __builtins__
        }

        sys.stdout = io.StringIO()
        exec(code, namespace)

        output = sys.stdout.getvalue()

        # 检查是否有 pyecharts 图表对象（变量名为 chart）
        chart_obj = namespace.get('chart')
        chart_markdown = ""
        if chart_obj is not None and hasattr(chart_obj, 'render'):
            try:
                # 生成唯一文件名
                chart_filename = f"{uuid.uuid4().hex}.html"
                chart_filepath = os.path.join(CHART_STORAGE_DIR, chart_filename)
                # 渲染为完整 HTML 文件
                chart_obj.render(chart_filepath)
                # 构造前端可访问的 URL
                chart_url = f"/chart/{chart_filename}"
                chart_markdown = (
                    f"\n\n<chart-ref url='{chart_url}'></chart-ref>\n\n"
                    f"📊 **[点击这里查看交互式图表]({chart_url})** （如果图表未自动加载）"
                )
                # 可选：清理旧图表文件（例如每次生成新图表时触发）
                _clean_old_charts()
            except Exception as e:
                chart_markdown = f"\n\n⚠️ 图表生成失败: {e}"

        # 更新 DataFrame（如果用户修改了 df 变量）
        updated_df = namespace.get('df')
        if isinstance(updated_df, pd.DataFrame):
            _save_dataframe(session_id, updated_df)
            preview = updated_df.head(50).to_string()
            result_text = f"✅ 执行成功！\n输出：\n{output}\n\n预览（最多50行）：\n{preview}"
        else:
            result_text = f"✅ 执行成功！\n输出：\n{output}\n（DataFrame 未修改）"

        result_text += chart_markdown
        return result_text

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

@tool
def export_csv(filename: str, config: RunnableConfig) -> str:
    """导出当前 DataFrame 为 CSV 文件，返回下载链接"""
    session_id = config.get("configurable", {}).get("thread_id")
    if not session_id:
        return "错误：无法获取会话ID。"
    try:
        df = _get_dataframe(session_id)
    except ValueError as e:
        return f"错误：{e}"

    if not filename.endswith('.csv'):
        filename += '.csv'

    download_url = f"/download/{session_id}?filename={filename}"
    return f"✅ 数据已导出，请点击链接下载：{download_url}"

def get_tools():
    return [load_data, run_python_code, get_data_info, export_csv]

def get_session_dataframe(session_id: str):
    return _session_dataframes.get(session_id)

def delete_session_dataframe(session_id: str):
    if session_id in _session_dataframes:
        del _session_dataframes[session_id]