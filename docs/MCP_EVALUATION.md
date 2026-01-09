# MCP Evaluation Implementation

## 概述

本项目实现了基于MCP（Model Context Protocol）的Agent函数调用观测和评估方法。通过将一个或多个Agent改造成MCP服务器，实现了对Agent函数调用行为的追踪和评估。

## 实现内容

### 1. 核心文件

#### `mcp_server.py`
- `FunctionCallTracker`: 函数调用追踪器，记录所有函数调用详情
- `AgentFunctionWrapper`: Agent包装器，启用函数调用追踪
- `MultiAgentObserver`: 多Agent观察器，支持同时追踪多个Agent

#### `mcp_evaluation.py`
- `MCPEvaluationServer`: MCP服务器实现，用于Agent评估
- `AgentMCPEvaluator`: Agent评估器，基于函数调用数据生成评估指标
- 提供与Langfuse集成的评估指标提交功能

#### `mcp_integration.py`
- `MCPIntegration`: 单例集成层，连接MCP评估和现有API
- 提供便捷的评估接口

#### `mcp_demo.py`
- 完整的演示代码，展示如何使用MCP评估功能
- 包含单Agent、多Agent、Langfuse集成等示例

### 2. 评估指标

MCP评估提供以下关键指标：

- **函数调用成功率**: 成功的函数调用比例
- **总函数调用数**: Agent执行的函数调用总数
- **平均执行时间**: 函数调用的平均执行时间
- **函数使用频率**: 每个函数的调用次数
- **Agent使用统计**: 每个Agent的函数调用分布

### 3. 使用方法

#### 3.1 单Agent评估

```python
from agents_demo.mcp_evaluation import create_mcp_evaluator
from agents import Runner

# 创建评估器
evaluator = create_mcp_evaluator(langfuse_client=langfuse)

# 为Agent创建MCP服务器
evaluator.create_mcp_server_for_agent(
    agent_name="FAQ Agent",
    tools=faq_agent.tools,
)

# 运行Agent
result = await Runner.run(faq_agent, "What is the baggage allowance?")

# 评估
evaluation = await evaluator.evaluate_agent_trace(
    trace_id="trace_123",
    agent_name="FAQ Agent",
)
```

#### 3.2 多Agent评估

```python
from agents_demo.mcp_server import MultiAgentObserver

# 创建多Agent观察器
observer = MultiAgentObserver(langfuse_client=langfuse)

# 包装所有Agent
wrapped_triage = observer.wrap_agent(triage_agent)
wrapped_faq = observer.wrap_agent(faq_agent)

# 运行Agent
result, trace_id = await observer.run_agent(
    agent_name="FAQ Agent",
    input="What is the baggage allowance?",
)

# 获取全局统计
stats = observer.get_global_statistics()
```

#### 3.3 集成到API

```python
from agents_demo.mcp_integration import get_mcp_integration, evaluate_with_mcp

# 初始化集成
integration = get_mcp_integration()
integration.initialize(langfuse_client=langfuse)

# 评估Agent执行
evaluation = await evaluate_with_mcp(
    trace_id="trace_123",
    agent_name="FAQ Agent",
    user_message="What is the baggage allowance?",
    assistant_message="One carry-on and one checked bag...",
    langfuse_client=langfuse,
)
```

### 4. 运行演示

```bash
# 在虚拟环境中运行完整演示
uv run python -m agents_demo.mcp_demo
```

演示包括：
1. 单Agent MCP评估
2. 多Agent MCP评估
3. Langfuse集成评估
4. 综合评估（MCP + LLM-as-a-Judge）

### 5. Langfuse集成

评估指标会自动提交到Langfuse平台，包括：

- `mcp_function_call_success_rate`: 函数调用成功率
- `mcp_total_function_calls`: 总函数调用数
- `mcp_avg_execution_time`: 平均执行时间

这些指标可以在Langfuse Dashboard中查看和分析。

### 6. 技术要点

#### 实现策略
根据项目说明，采用**策略(3)**：
- 参考openai-agentmcp-evaluation.zip中的MCP观测方法
- 将Agent改造成MCP服务器
- 实现函数调用的观测和评估

#### 设计模式
- **包装器模式**: `AgentFunctionWrapper`包装Agent以启用追踪
- **装饰器模式**: `track_function_call`装饰器追踪函数调用
- **观察者模式**: `FunctionCallTracker`记录和追踪函数调用
- **单例模式**: `MCPIntegration`确保全局只有一个集成实例

#### 与现有代码集成
- 与`evaluators.py`中的LLM-as-a-Judge评估配合使用
- 与`telemetry.py`中的遥测系统集成
- 支持FastAPI和Gradio前端

### 7. 评估报告示例

```
=== MCP Agent Function Call Evaluation Report ===

Total Calls: 15
Successful Calls: 14
Failed Calls: 1
Success Rate: 93.33%
Average Execution Time: 0.0234s

Function Usage:
  - faq_lookup_tool: 5 calls
  - flight_status_tool: 4 calls
  - update_seat: 3 calls
  - display_seat_map: 3 calls

Agent Usage:
  - FAQ Agent: 5 calls
  - Flight Status Agent: 4 calls
  - Seat Booking Agent: 6 calls
```

### 8. 扩展建议

- 添加更多评估指标（如函数调用深度、错误分析）
- 支持自定义评估规则和权重
- 实现评估结果的可视化
- 添加异常检测和告警功能

## 技术要点对应

本实现覆盖了**技术要点3(b)**：基于观测平台进行评估

- ✅ 使用wrapper/decorator方式对Agent加入观测代码
- ✅ 实现函数调用追踪
- ✅ 实现评估方法
- ✅ 与Langfuse集成提交评估指标
- ✅ 提供完整的演示和文档

## 参考资料

- [OpenAI Agent SDK](https://github.com/openai/openai-agents-python)
- [Langfuse Documentation](https://langfuse.com/docs)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Ragas Evaluation Framework](https://github.com/vibrantlabsai/ragas)
