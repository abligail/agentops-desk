# MCP Evaluation Implementation - 使用指南

## 快速开始

### 1. 环境准备

```bash
# 确保已使用uv创建虚拟环境
uv sync

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 设置环境变量（从.env.example复制）
cp .env.example .env
```

### 2. 运行测试

```bash
# 运行MCP评估测试
python test_mcp.py

# 运行完整演示
python -m agents_demo.mcp_demo
```

### 3. 集成到现有代码

在API中使用MCP评估：

```python
from agents_demo.mcp_integration import get_mcp_integration
from langfuse import get_client

# 初始化Langfuse
langfuse = get_client()

# 初始化MCP集成
integration = get_mcp_integration()
integration.initialize(langfuse_client=langfuse)

# 评估Agent执行
evaluation = await integration.evaluate_agent_execution(
    trace_id="your_trace_id",
    agent_name="Triage Agent",
    user_message="What is the baggage allowance?",
    assistant_message="One carry-on and one checked bag...",
)

# 获取评估报告
report = integration.get_evaluation_report()
print(report)
```

## 功能特性

### 1. 函数调用追踪
- 自动记录所有Agent的函数调用
- 追踪调用成功/失败状态
- 记录执行时间

### 2. 评估指标
- 函数调用成功率
- 总调用次数
- 平均执行时间
- 函数使用频率
- Agent使用统计

### 3. Langfuse集成
- 自动提交评估指标到Langfuse
- 与LLM-as-a-Judge配合使用
- 支持多维度评估分析

## 文件说明

| 文件 | 说明 |
|------|------|
| `mcp_server.py` | 核心追踪和包装器实现 |
| `mcp_evaluation.py` | MCP服务器和评估器 |
| `mcp_integration.py` | API集成层 |
| `mcp_demo.py` | 完整演示代码 |
| `test_mcp.py` | 单元测试 |
| `MCP_EVALUATION.md` | 详细技术文档 |

## 下一步

1. 根据需要调整评估指标
2. 自定义评估规则和权重
3. 集成到FastAPI端点
4. 在Gradio界面中显示评估结果

## 相关文档

- [MCP_EVALUATION.md](MCP_EVALUATION.md) - 详细技术文档
- [finalproject-说明.md](finalproject-说明.md) - 项目需求说明
