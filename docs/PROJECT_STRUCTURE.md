# 项目文件结构说明

## 重组后的文件结构

```
agents_demo/
├── docs/                          # 文档目录
│   ├── README.md
│   ├── MCP_README.md
│   ├── MCP_IMPLEMENTATION_SUMMARY.md
│   ├── MCP_EVALUATION.md
│   ├── PROJECT_RUN_GUIDE.md
│   ├── OPERATIONS.md
│   ├── FINAL_PROJECT_REPORT.md
│   ├── finalproject-说明.md
│   ├── finalproject-说明.pdf
│   └── screenshot.jpg
│
├── src/agents_demo/              # 主项目目录
│   ├── __init__.py
│   ├── agents/                   # 代理核心逻辑
│   │   ├── __init__.py
│   │   ├── main.py               # 代理定义
│   │   ├── main_qwen.py          # Qwen模型支持
│   │   ├── fastapi_qwen_gradio.py # FastAPI + Gradio集成
│   │   └── serve.py              # 服务启动脚本
│   │
│   ├── api/                      # API接口层
│   │   ├── __init__.py
│   │   └── api.py                # FastAPI路由定义
│   │
│   ├── mcp/                      # MCP相关功能
│   │   ├── __init__.py
│   │   ├── mcp_server.py         # MCP服务器实现
│   │   ├── mcp_integration.py    # MCP集成
│   │   ├── mcp_evaluation.py     # MCP评估
│   │   └── mcp_demo.py           # MCP演示
│   │
│   ├── services/                 # 服务层
│   │   ├── __init__.py
│   │   ├── data_loader.py        # 数据加载服务
│   │   ├── storage.py            # 存储服务
│   │   ├── telemetry.py          # 遥测服务
│   │   └── evaluators.py         # 评估服务
│   │
│   ├── models/                   # 数据模型
│   │   ├── __init__.py
│   │   └── seat_assignments.py   # 座位分配模型
│   │
│   ├── tests/                    # 测试文件
│   │   ├── __init__.py
│   │   ├── test_mcp.py
│   │   └── test_mcp_unit.py
│   │
│   ├── utils/                    # 工具函数
│   │   ├── __init__.py
│   │   └── generate_evaluation_data.py
│   │
│   ├── data/                     # 数据文件
│   │   ├── conversations.json
│   │   ├── customer_profiles.json
│   │   ├── feedback.jsonl
│   │   ├── flights.json
│   │   ├── mcp_evaluation_data.json
│   │   ├── meals.json
│   │   ├── seats.json
│   │   └── traces.jsonl
│   │
│   └── ui/                       # Next.js前端UI
│       ├── app/
│       ├── components/
│       ├── lib/
│       ├── public/
│       └── [package.json配置文件]
│
├── .env.example
├── .gitignore
├── LICENSE
├── pyproject.toml
└── uv.lock
```

## 主要改进

1. **模块化分离**：将不同功能的代码分离到独立的子包中
   - `agents/` - 代理逻辑和核心业务
   - `api/` - HTTP API接口
   - `mcp/` - MCP相关功能
   - `services/` - 各种服务层
   - `models/` - 数据模型
   - `tests/` - 测试代码
   - `utils/` - 工具函数

2. **文档集中管理**：所有文档文件集中在`docs/`目录下

3. **清晰的职责划分**：每个目录有明确的职责

## 导入路径变化

重组后的导入路径已更新，主要变化如下：

```python
# API层
from agents_demo.agents.main_qwen import triage_agent
from agents_demo.services.storage import CompositeConversationStore
from agents_demo.services.telemetry import Telemetry
from agents_demo.services.evaluators import evaluate_response
from agents_demo.services.data_loader import get_seats_by_flight
from agents_demo.models.seat_assignments import seat_assignment_store

# MCP模块
from agents_demo.mcp.mcp_server import FunctionCallTracker
from agents_demo.mcp.mcp_evaluation import AgentMCPEvaluator
from agents_demo.services.telemetry import Telemetry

# 工具和测试
from agents_demo.agents.main import triage_agent
from agents_demo.agents.main_qwen import myRunConfig
from agents_demo.mcp.mcp_server import FunctionCallTracker
```

## 运行方式

```bash
# 安装依赖
uv sync

# 运行FastAPI服务
uv run demo_serve_fastapi

# 运行Gradio服务
uv run demo_serve_gradio

# 同时运行FastAPI和Gradio
uv run demo_serve_both

# 运行测试
uv run pytest src/agents_demo/tests/
```

## 注意事项

- 所有导入路径已更新为使用绝对导入
- pyproject.toml中的脚本路径已更新
- 保持了原有的功能完整性
- 前端UI目录结构未改变