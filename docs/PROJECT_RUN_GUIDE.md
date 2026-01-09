# Agent系统运行指南

## 项目状态

✅ **系统运行正常**

### 已启动的服务

1. **Gradio Web UI** - http://127.0.0.1:7860
   - 状态: ✅ 运行中
   - 功能: 聊天界面、Agent交互、用户反馈

2. **MCP评估功能** - 已集成
   - 状态: ✅ 工作正常
   - 功能: 函数调用追踪、评估指标生成

## 快速开始

### 1. 激活虚拟环境

```bash
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

### 2. 启动服务

#### 方式1: 启动Gradio界面（推荐）

```bash
uv run demo_serve_gradio
```

访问: http://127.0.0.1:7860

#### 方式2: 启动FastAPI后端

```bash
uv run uvicorn agents_demo.api:app --host 127.0.0.1 --port 8000 --reload
```

访问: http://127.0.0.1:8000/docs

#### 方式3: 同时启动两者

```bash
uv run demo_serve_both
```

### 3. 测试MCP评估功能

```bash
# 运行单元测试
python test_mcp.py

# 运行完整演示
python -m agents_demo.mcp_demo

# 运行数据生成
python -m agents_demo.generate_evaluation_data
```

## 系统功能

### Agent系统

- **Triage Agent** - 分发用户请求到合适的Agent
- **FAQ Agent** - 回答常见问题
- **Flight Status Agent** - 查询航班状态
- **Seat Booking Agent** - 管理座位预订
- **Cancellation Agent** - 处理航班取消
- **Food Service Agent** - 处理餐饮需求

### MCP评估功能

- **函数调用追踪** - 自动记录所有函数调用
- **评估指标** - 成功率、执行时间、使用频率
- **Langfuse集成** - 自动提交评估指标
- **多Agent观察** - 同时追踪多个Agent的行为

### 评估指标

| 指标 | 说明 |
|------|------|
| 函数调用成功率 | 成功调用的比例 |
| 总函数调用数 | Agent执行的函数调用总数 |
| 平均执行时间 | 函数调用的平均执行时间 |
| 函数使用频率 | 每个函数的调用次数 |
| Agent使用统计 | 每个Agent的函数调用分布 |

## 使用示例

### 1. 通过Gradio界面交互

1. 访问 http://127.0.0.1:7860
2. 在聊天框中输入问题，例如：
   - "What is the baggage allowance?"
   - "Check my flight status for FL123"
   - "I want to change my seat to 1A"
3. 系统会自动路由到合适的Agent
4. 可以对回复进行评分反馈

### 2. 通过API使用

```bash
# 启动FastAPI后端后，使用curl测试
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the baggage allowance?"}'
```

### 3. 运行评估

```python
import asyncio
from agents_demo.mcp_integration import get_mcp_integration

async def run_evaluation():
    # 初始化集成
    integration = get_mcp_integration()
    integration.initialize()

    # 评估Agent执行
    evaluation = await integration.evaluate_agent_execution(
        trace_id="your_trace_id",
        agent_name="FAQ Agent",
        user_message="What is the baggage allowance?",
        assistant_message="One carry-on and one checked bag...",
    )

    # 获取评估报告
    report = integration.get_evaluation_report()
    print(report)

asyncio.run(run_evaluation())
```

## 文件结构

```
agents_demo/
├── src/agents_demo/
│   ├── main.py              # Agent定义（原始OpenAI版本）
│   ├── main_qwen.py         # Agent定义（Qwen适配版本）
│   ├── api.py               # FastAPI后端
│   ├── fastapi_qwen_gradio.py  # Gradio前端
│   ├── serve.py             # 服务启动脚本
│   ├── mcp_server.py        # MCP追踪器核心
│   ├── mcp_evaluation.py    # MCP评估器
│   ├── mcp_integration.py   # API集成层
│   ├── mcp_demo.py         # 演示代码
│   ├── evaluators.py        # LLM-as-a-Judge评估
│   ├── telemetry.py         # 遥测记录
│   ├── storage.py           # 数据存储
│   └── data/               # 数据文件
├── test_mcp.py             # MCP测试
├── MCP_EVALUATION.md       # MCP技术文档
├── MCP_README.md          # MCP使用指南
└── MCP_IMPLEMENTATION_SUMMARY.md  # 实现总结
```

## 环境配置

确保`.env`文件包含以下配置：

```bash
# Langfuse配置
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com

# Qwen模型配置
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=sk-...
QWEN_MODEL_NAME=qwen3-next-80b-a3b-instruct

# OpenAI模型配置（可选）
OPENAI_API_KEY=sk-proj-...
OPENAI_BASE_URL=https://api.openai.com/v1

# 应用配置
USE_OPENAI_MODEL=true  # true使用OpenAI，false使用Qwen
```

## 依赖安装

```bash
# 使用uv安装依赖
uv sync

# 或使用pip安装
pip install -r requirements.txt  # 如果有requirements.txt
```

## 故障排除

### 1. Gradio无法启动

```bash
# 检查端口是否被占用
lsof -i :7860

# 或者使用其他端口
uv run gradio src/agents_demo/fastapi_qwen_gradio.py:run_gradio --port 7861
```

### 2. Langfuse连接失败

- 检查`.env`中的密钥是否正确
- 确保网络可以访问Langfuse服务器
- 查看日志中的错误信息

### 3. MCP评估未工作

- 确保已安装mcp包：`uv add mcp`
- 运行测试：`python test_mcp.py`
- 检查初始化是否正确调用

## 性能监控

### 查看实时日志

```bash
# Gradio日志
tail -f /tmp/gradio.log

# FastAPI日志
tail -f /tmp/fastapi.log
```

### 查看MCP评估报告

```python
from agents_demo.mcp_integration import get_mcp_integration

integration = get_mcp_integration()
report = integration.get_evaluation_report()
print(report)
```

## 扩展功能

1. **添加新的Agent** - 在`main_qwen.py`中定义
2. **自定义评估指标** - 修改`evaluators.py`或`mcp_evaluation.py`
3. **集成数据库** - 使用`storage.py`中的存储接口
4. **添加UI组件** - 修改`fastapi_qwen_gradio.py`

## 相关文档

- [MCP_EVALUATION.md](MCP_EVALUATION.md) - MCP技术文档
- [MCP_README.md](MCP_README.md) - MCP使用指南
- [MCP_IMPLEMENTATION_SUMMARY.md](MCP_IMPLEMENTATION_SUMMARY.md) - 实现总结
- [finalproject-说明.md](finalproject-说明.md) - 项目需求说明

## 技术支持

遇到问题时，请查看：
1. 日志文件输出
2. 测试脚本运行结果
3. 相关技术文档

---

**当前分支**: feat/mcp-evaluation
**最新提交**: 添加MCP评估功能实现总结文档
**项目状态**: ✅ 运行正常
