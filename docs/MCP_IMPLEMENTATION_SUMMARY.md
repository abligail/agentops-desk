# 技术要点3：基于观测平台进行评估 - 实施报告

## 1. 概述

本项目严格遵循Final Project说明文档中关于“技术要点3”的要求，设计并实现了一套完整的Agent观测与评估体系。该体系整合了**在线实时评估**（LLM-as-a-Judge）与**离线过程评估**（MCP Tool Tracking），全面覆盖了对Agent输出质量（Response Quality）和执行逻辑（Execution Process）的量化分析。

## 2. 核心实现策略

根据项目要求，我们采用了**混合评估策略**，具体对应技术文档中的以下要求：

*   **实时质量评估**: 对应技术文档中 "LLM-as-a-Judge提供的evaluator机制"。
*   **过程轨迹评估**: 对应技术文档中 "策略(3)：参考mcp的观测方法...将agent改造成mcp"。

### 2.1 LLM-as-a-Judge (在线实时评估)

我们实现了一个专用的评估Agent，能够在每次对话结束后自动对回复质量进行多维度打分。

*   **实现位置**: `src/agents_demo/services/evaluators.py`
*   **评估模型**: 使用与业务Agent相同的Qwen模型配置。
*   **评分维度**:
    *   **Helpfulness (有用性)**: 是否解决了用户的问题？(0-1分)
    *   **Accuracy (准确性)**: 提供的信息是否准确？(0-1分)
    *   **Relevance (相关性)**: 回复是否切题？(0-1分)
    *   **Overall Score (综合得分)**: 加权平均分。
*   **集成方式**:
    *   在FastAPI后端 (`src/agents_demo/api/api.py`) 中集成。
    *   利用 `BackgroundTasks` 机制异步触发评估，不阻塞用户主线程。
    *   评估结果直接上传至 **Langfuse** 平台，与对应的Trace绑定。

### 2.2 MCP Tool Tracking (离线过程评估)

为了更深入地分析Agent的工具使用能力，我们实现了一套基于 **MCP (Model Context Protocol)** 理念的函数调用追踪系统。

*   **实现位置**: `src/agents_demo/mcp/` 目录
    *   `mcp_server.py`: 核心追踪逻辑。
    *   `mcp_evaluation.py`: 评估指标计算与Langfuse对接。
*   **技术原理**:
    *   **AgentFunctionWrapper**: 使用Python装饰器和Monkey Patching技术，无侵入地拦截Agent的工具调用。
    *   **FunctionCallTracker**: 实时记录每次调用的函数名、参数、返回值、执行耗时和成功状态。
    *   **Metrics**: 自动计算 **工具调用成功率 (Success Rate)**、**平均耗时 (Avg Latency)** 和 **工具使用分布 (Usage Distribution)**。
*   **验证脚本**:
    *   提供了 `src/agents_demo/mcp/mcp_demo.py` 脚本。
    *   通过命令 `uv run demo_mcp_eval` 即可运行包含单Agent问答和多Agent协作（如改签机票、查询行李）的标准测试集，生成详细的评估报告。

## 3. 评估流程与效果

### 3.1 评估流程图
1.  **用户交互**: 用户发送消息 -> 触发Agent执行。
2.  **过程追踪**: `mcp_server` 自动捕获所有工具调用 -> 记录至内存/日志。
3.  **结果生成**: Agent生成最终回复。
4.  **异步评估**: 
    *   后台触发 `evaluator_agent` 对回复内容打分。
    *   计算工具调用统计指标。
5.  **数据上报**: 所有Trace数据、评分（Scores）、元数据（Metadata）统一上传至Langfuse。

### 3.2 评估结果示例 (基于Demo运行)
运行 `demo_mcp_eval` 后，系统会输出如下格式的报告：

```text
=== MCP Agent Function Call Evaluation Report ===

Total Calls: 5
Successful Calls: 5
Failed Calls: 0
Success Rate: 100.00%
Average Execution Time: 0.12s

Function Usage:
  - faq_lookup_tool: 2 calls
  - update_seat: 1 calls
  - display_seat_map: 1 calls
  - flight_status_tool: 1 calls

Agent Usage:
  - FAQ Agent: 2 calls
  - Seat Booking Agent: 2 calls
  - Flight Status Agent: 1 calls
```

## 4. 结论

本项目通过结合 **LLM-as-a-Judge** 和 **MCP Tool Tracking**，成功构建了一个闭环的Agent评估体系。既能量化Agent“说得好不好”（回复质量），也能监控Agent“做得对不对”（工具调用逻辑），完全满足了Final Project对于系统行为观察和评估的高级要求。
