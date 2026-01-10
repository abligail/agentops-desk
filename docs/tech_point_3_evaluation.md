# 技术要点3：基于观测平台进行评估 - 实现技术文档

## 1. 概述

本项目严格遵循《Agent系统设计与实现》Final Project说明文档中关于“技术要点3：基于观测平台进行评估”的要求。我们采用**混合评估策略**，结合了**MCP (Model Context Protocol) 过程追踪**与**LLM-as-a-Judge 结果评估**，构建了一套完整的Agent观测与评估体系。

该体系对应说明文档中的 **策略(3)**（参考MCP的观测方法）与 **策略(2)**（使用wrapper/decorator），并集成了Langfuse观测平台，实现了对Agent“执行逻辑”与“输出质量”的双重评估。

## 2. 核心技术架构

系统采用双层评估架构：

1.  **底层：基于MCP的执行轨迹追踪 (Process Evaluation)**
    *   **目标**：评估Agent工具使用的正确性、效率和稳定性。
    *   **核心技术**：Model Context Protocol (MCP), Python Decorators, Monkey Patching。
2.  **上层：基于LLM-as-a-Judge的质量评估 (Quality Evaluation)**
    *   **目标**：评估Agent回复内容的语义质量（有用性、准确性、相关性）。
    *   **核心技术**：LLM Prompt Engineering, Pydantic Structured Output, Ragas Metrics思想。
3.  **数据层：Langfuse观测平台**
    *   **目标**：统一存储Trace、Span、Scores和Evaluation Report。

## 3. 实现方式与具体技术

### 3.1 基于MCP的函数调用追踪 (MCP Tool Tracking)

这是本项目对**技术要点3(b)**的核心实现，参考了MCP的设计理念，将Agent的工具调用标准化为MCP Server行为进行观测。

*   **实现原理**：
    *   **无侵入式埋点**：开发了 `AgentFunctionWrapper` 类，利用Python的动态特性（Monkey Patching），在Agent初始化时自动包裹其所有Tools。
    *   **装饰器模式**：使用 `track_function_call` 装饰器拦截每一次工具调用。
    *   **上下文追踪**：利用 `contextvars` 维护 `trace_id`，确保在异步并发环境下，工具调用能正确关联到对应的对话Trace。

*   **关键代码模块** (`src/agents_demo/mcp/`)：
    *   `mcp_server.py`:
        *   `FunctionCallTracker`: 内存级追踪器，实时记录函数名、参数、返回值、耗时、异常信息。
        *   `AgentFunctionWrapper`: 自动将普通Agent转换为具备追踪能力的“可观测Agent”。
    *   `mcp_evaluation.py`:
        *   负责计算统计指标：**Success Rate** (成功率)、**Average Latency** (平均耗时)、**Tool Usage Distribution** (工具使用分布)。
        *   负责将这些结构化指标转换为Langfuse的Score对象并上传。

### 3.2 LLM-as-a-Judge 在线评估

对应技术要点中关于“LLM-as-a-Judge提供的evaluator机制”。

*   **实现原理**：
    *   在FastAPI后端引入异步评估机制。每当Agent生成回复后，后台触发一个独立的Evaluator Agent。
    *   使用与业务相同的Qwen模型，但配置专门的System Prompt作为裁判。
*   **评估指标** (`src/agents_demo/services/evaluators.py`)：
    *   **Helpfulness (有用性)**: 是否解决了用户问题 (0-1分)。
    *   **Accuracy (准确性)**: 信息是否准确无误 (0-1分)。
    *   **Relevance (相关性)**: 是否未偏离航司客服主题 (0-1分)。
    *   **Overall Score**: 加权综合得分。
*   **技术亮点**：
    *   使用 `Pydantic` 定义 `EvaluationScore` Schema，确保LLM输出绝对结构化的JSON数据，便于后续统计分析。

### 3.3 Langfuse 平台深度集成

*   **Trace ID 绑定**：
    *   前端(Gradio/Next.js)与后端(FastAPI)共享 `trace_id`。
    *   MCP追踪到的工具调用作为 `Span` 挂载在主 `Trace` 下。
    *   LLM-as-a-Judge的评分作为 `Score` 关联到同一 `Trace`。
*   **用户反馈 (Human-in-the-Loop)**：
    *   实现了用户界面端的 👍/👎 评分，该评分同样作为Score上传Langfuse，形成了“机器评估”与“人工评估”的对照数据集。

## 4. 评估指标体系概览

| 评估维度 | 指标名称 | 数据来源 | 实现技术 |
| :--- | :--- | :--- | :--- |
| **执行质量** | Tool Call Success Rate | MCP Tracker | Python Wrapper / Decorator |
| **执行效率** | Avg Execution Time | MCP Tracker | `time` module delta |
| **工作流** | Function Usage Count | MCP Tracker | In-memory Dict Aggregation |
| **回复质量** | Helpfulness / Accuracy | LLM Evaluator | Qwen Model + Prompt Engineering |
| **用户体验** | User Feedback Score | Web UI | Langfuse Client SDK |

## 5. 总结

本项目通过自主实现 `src/agents_demo/mcp` 模块，不仅完成了Final Project中要求的“参考MCP观测方法”的挑战性策略，还进一步整合了在线LLM评估，形成了一个闭环的Agent DevOps监控体系。该实现允许开发者在开发阶段快速定位工具调用故障，在生产阶段持续监控回复质量。
