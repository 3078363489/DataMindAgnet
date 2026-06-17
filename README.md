# 📊 智能数据分析助手 · 小杨

> 基于 LangGraph + Flask + Pyecharts 的自然语言数据分析平台，让数据对话像聊天一样简单。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.0+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 项目简介

“小杨”是一个智能数据分析助手，专为数据探索和快速洞察设计。用户只需上传 CSV 或 Excel 文件，然后用自然语言描述分析需求（例如“计算销售额总和”“按地区分组统计”“绘制趋势折线图”），系统便会自动生成并执行 Pandas 代码，并以交互式图表（基于 Pyecharts / ECharts）呈现结果。

> 无需编写代码，即可完成数据清洗、聚合、可视化全流程。

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 📁 **文件上传** | 支持 `.csv`、`.xlsx`、`.xls` 格式，自动读取并预览数据 |
| 💬 **自然语言交互** | 用中文提问，Agent 自动生成 Pandas 代码并执行 |
| 📊 **交互式图表** | 使用 Pyecharts 生成柱状图、折线图、饼图、散点图等，支持缩放、保存、数据视图 |
| 🔍 **数据洞察** | 自动提供描述统计、缺失值检测、数据预览 |
| 💾 **数据导出** | 处理后的 DataFrame 可一键导出为 CSV 文件 |
| 🗂️ **会话管理** | 支持多会话切换，历史消息持久化存储（SQLite） |
| 🧠 **智能 Agent** | 基于 LangGraph 构建，具备工具调用、状态记忆、代码安全执行能力 |

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | Flask 3.0 |
| **AI 框架** | LangChain, LangGraph |
| **大模型** | OpenAI API（兼容接口） |
| **数据处理** | Pandas 2.2 |
| **可视化** | Pyecharts 2.0（ECharts 5） |
| **数据持久化** | SQLite（消息历史 + Agent 状态） |
| **前端** | 原生 HTML + CSS + JS，轻量级 Markdown 渲染（Showdown） |

---

## 🚀 快速开始

### 环境要求
- Python 3.10 或更高版本
- 一个有效的 OpenAI API Key（或兼容的 API 端点）

### 1. 克隆仓库
```bash
git clone https://github.com/your-username/data-assistant-xiaoyang.git
cd data-assistant-xiaoyang
```
### 2. 安装依赖
```bash
pip install -r requirements.txt
```
### 3. 配置环境变量
创建 .env 文件（参考 .env.example）：

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1   # 若使用代理或中转，请修改
MODEL=gpt-4o                                # 或其他支持函数调用的模型
```
4. 初始化数据库
首次运行会自动创建 chat_history.db 和 agent_state.db，无需手动操作。

5. 启动服务
```bash
python app.py
访问 http://127.0.0.1:5000 即可开始使用。
```
