# Group Final Project: Agent系统设计与实现-v3

**TAs: Wang Wei& Sun Xiyu**

## 项目意义

**基于LLM的**Agent利用LLM推理能力，利用工具，长短记忆以及设计模式，实现具有自主能力的智能体。真实业务通常按照一定流程进行，对多智能体进行编排形成工作流已成为Agent落地最普及形式。以业务出发，设计和实现复杂智能体对技术挑战性要求有较大差异。编程Agent已成为典型落地场景，对LLM模型本身要求极高，另外对系统架构也提出新要求。实践表明，以上下文工程（context engineering）为代表的Agent Engineering技术话题日益精深。为执行编程以及机器人具身智能的长程任务，基于已有LLM模型必须设计新的系统架构（最新进展为DeepAgent以及Skills）。

面向本科生基础能力训练，从源代码级别理解多agent编排和执行过程对夯实基础大有裨益。Final Project 从Agent Engineering角度，涵盖Agent系统设计（多Agent编排）、长短期记忆（Workflow中Agent上下文及数据存储），人在环路（Human-in-the-Loop）交互以及系统行为观察和评估等。

**以OpenAI Agent 开源示范应用（customer service）出发，通过完善Demo系统，学习**和实践Agent系统构建涉及的诸多工程问题，提升同学工科完整思维和实践能力。此外，为开放话题留出空间，欢迎同学以OpenAI Agent SDK为开发工具，改造开源或自己实现其它多Agent系统，要求涵盖Agent系统设计（多Agent编排）、长短期记忆（Workflow中Agent上下文及数据存储），人在环路（Human-in-the-Loop）交互以及系统行为观察和评估等技术要点。

## 技术要点

### 技术要点1： 短期和长期存储 【参见代码注释】

Agent共享的上下文数据结构进行永久存储，构成系统的Agent涉及的函数、工具、mcp集成等相关操作，通过真实数据或者仿真数据执行（建立存储数据结构）。客服多agent系统功能更逼近真实业务场景，提升系统可用性。

技术说明：采用sqlite3轻量级数据库（可作为内存数据库），postgresql等关系数据库，可使用DBeaver等工具进行数据查看和管理，不建议vector数据库。

### 技术要点2：人在环路交互及用户反馈 【参见代码注释】

用户提供过前端界面对AI响应消息进行评分反馈，即对Agent回复消息进行喜好评价，并将trace id对应的响应消息的评分更新至langfuse平台。

基本思路：将langfuse的trace id绑定agent消息反馈，实现后端和前端共享trace id及用户反馈状态，调用langfuse打分函数将用户反馈的评分上传至langfuse平台。

实现策略：（a）前端和后端均运行langfuse，后端生成trace id和其他信息，前端根据trace id进行评分；（b）后端运行langfuse，通过trace id实现打分消息绑定通信，fastapi后端更新打分结果至langfuse平台。

技术说明：建议采用（b）策略，Fastapi后端生成trace id，与前端消息通信，处理用户消息反馈的具体逻辑（score评分等）；注意查看fastapi_qwen_gradio.py相关代码逻辑。

### 技术要点3：基于观测平台进行评估【Agent评估流程和langfuse技术文档】

专家利用观测平台提供的annotation工具修改trace评分（学生可自行模拟专家完成实验）。

LLM-as-a-Judge提供的evaluator机制，对agent响应消息进行评分。

Score分析。通过平台提供的score分析工具，观察评估指标提升，理解observation和evaluation在智能体构建中逐步优化提升的重要作用。

技术说明：

Langfuse平台提供的内置LLM-as-a-Judge evaluator主要来自ragas开源评估框架，访问ragas开源评估框架可获得Langfuse中大部分evaluator metrics指标的具体含义（https://github.com/vibrantlabsai/ragas/tree/main/src/ragas/metrics）。langfuse只集成了ragas开源框架的部分LLM和Agent评估指标，agent相关的指标仍未集成。Ragas开源框架提供了大量Final project未涉及的评估案例，供自行拓展。（https://github.com/vibrantlabsai/ragas/tree/main/examples/ragas_examples）。另外，Agent工程领域的开源项目Langchain针对Agent函数调用产生的轨迹评估，也给出值得参考的开源代码（https://github.com/langchain-ai/agentevals/）。

Langfuse针对Agent MCP函数调用轨迹给出一个评估教程，该教程使用pydantic ai SDK（https://langfuse.com/guides/cookbook/example_pydantic_ai_mcp_agent_evaluation），通过experiment完成agent多种评估方式。该教程可以方便迁移至openai agent sdk：可通过重载MCPServerStreamableHttp类call tool函数获取function调用行为https://openai.github.io/openai-agents-python/ref/mcp/server/） 。

利用上述思路，课程TA团队完成一个基于langfuse + openai agent sdk的，针对Agent MCP函数调用轨迹的评估（openai-agentmcp-evaluation.zip，zip包括README.mk介绍实现思路和实验方法），runtime录制的示范视频（openai-agentmcp-evaluation使用教程视频.zip）。

请每组**自行选择3（b）评估任务**的工作量，具体实现时，有如下3种策略可以选择：

(1)使用langfuse的相关功能/UI来做简单的端到端，对agent响应消息进行评分的观测。

(2)自行使用wrapper或者decorator的方式，对一个或者多个agent加入相关代码来实现对函数调用的观测。

(3)参考openai-agentmcp-evaluation.zip（脚手架代码）中对于mcp的观测方法，将一个或多个agent改造成mcp，实现相应的评估方法。

以（1）（2）两点为技术基础，可设计技术要点3（b）的实现方案（技术说明1为小组设计更新颖的评估实验，3（b）需要学习openai-agentmcp-evaluation.zip代码后，根据建议策略自行设计实验（experiment））。技术要点3（a）3（c）可利用平台UI完成。

### 技术要点4：业务优化及扩展【参考给定源代码及customer service demo最新代码】

优化客服系统中已有agent功能，增加新的agent提升系统业务处理能力。对于给定的航班客服系统（customer service），建议增加food agent来处理用户饮食需求。

技术说明：建立评估case，设计增加food agent的多agent框架；实现food agent（可结合数据库存储）后，对food agent的整体系统影响进行评估；最终的多agent系统不因food agnent增加，影响已有业务逻辑的正确性。

### 技术要点5：界面外观提升【前端编程】

提升前端界面的美观度，系统运行效率等。

技术说明：多种候选UI技术提升系统美观性。

Web前框框架：Next.js, Vue3等

Chatkit：OpenAI公司最新开源框架（https://openai.github.io/chatkit-js/, https://github.com/openai/openai-chatkit-advanced-samples）

AG-UI技术：开源框架 (https://github.com/ag-ui-protocol/ag-ui/)，已获行业普遍采用 (https://docs.ag-ui.com/introduction, https://dojo.ag-ui.com/)

A2UI技术：Google公司最新开源框架(https://github.com/google/A2UI)

## 基础系统选择

### 课程提供的customer service agent工具包

完善Agent系统，工作涵盖第二部分涵盖的5个要点。

### 其它基于OpenAI Agent SDK的Agent开源系统

*DeepResearch Agent, Coding Agent 等最新类型Agent系统， 它们的Agent编排架构，Agent系统能力，代码难度等不低于给定的customer service应用。小组选定后与任课教师联系。对原型系统起点难度高，工作涵盖所有技术要点，最终系统完成度好的小组，可有10%-30%的加分。*

## 评分方法

### 总体评分（20%）

系统外观，运行时以及系统能力。

### 技术要点打分 （60%）

通过文档阅读，运行时表现及源代码查看相结合。

### 文档打分（20%）

提交报告格式不限，包括：

系统技术栈，存储（数据库schema，db文件等）及运行环境等，要求提交的PJ项目科编译运行；

系统简介（含Agent Graph）：系统架构，功能说明等。

技术要点说明（五个技术要点的设计及实现，langfuse相关部分须有截图，自行设计test case等）

自评亮点（小组工作突出之处）。

### 加分项（10-30%）

任课教师和小组充分技术讨论后确定。

## 工作任务表

每个小组提供人员和任务分配表。

**附录A：**

**OpenAI Customer Service Agents 安装说明（含python前端）**

**1.项目简介**

**OpenAI Agent SDK是一款轻量级，开源且功能强大的Agent SDK, 配合OpenAI开发者平台的Agent Builder工具，可构建具有全部源代码的Agent工作流，超越Agent Builder(Langchain)/GoogleADK/ Coze/Dify/n8n等无法查看全部源代码的Agent可视编排框架。 OpenAI Customer Service Agents Demo示范企业级客服Agent系统设计与实现，是OpenAI Agent SDK若干开源项目中的明星项目( https://github.com/openai/openai-cs-agents-demo )**

**2.代码特点**

基于该开源项目最新Chatkit之前的2025年8月版本，该版本代码未采用openai最新的chatkit重构，代码结构清晰 简洁易懂，充分展示Agent编排实现的工作流原理和设计。

**教学团队通过适配Qwen模型，开发基于Gradio UI的python前端，方便同学进行代码阅读和实时运行时探究。Fastapi服务端口及Agent定义等关键代码部分增加注释及作业要求，方便代码阅读，实现编程任务。**

**3.编译运行**

解压openai-cs-agents-demo.zip

依赖包安装1：Fastapi后端安装需求见requirements.txt，位于python-backend目录下：

依赖包安装2：Next.js前端安装需求见package.json，位于ui目录下，该所需next.js相关版本虽不新，可正确运行。

Fastapi服务端：Fastapi endpoint服务（8000端口），VS Code打开项目目录， 设置虚拟环境后，进入python-backend目录，执行： `python -m uvicorn api:app --reload --port 8000`

Next.js前端：VS Code虚拟环境下，进入ui目录下，执行: `npx next dev`

基于gradio UI的python前端（user feedback）：VS Code虚拟环境下，进入python-backend目录，执行：`python .\fastapi_qwen_gradio.py`，运行画面见如下截图（显示具有一定容错能力，如服务器未启动显示Invalid request），喜好图标等用户反馈UI元素。
