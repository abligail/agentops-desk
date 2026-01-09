# 演示运行手册

## 常用命令
- `demo_serve_fastapi`：启动 FastAPI 后端（端口 8000），同时提供 `src/agents_demo/ui/out` 静态界面。
- `demo_serve_gradio`：启动基于 Qwen/OpenAI Agent SDK 的 Gradio 界面。
- `demo_serve_both`：同时启动 FastAPI 和 Gradio（多进程）。


mcp：
终端A
# 可选，明确指定端口
$env:FOOD_MCP_PORT="8007"
python -m agents_demo.mcp_food_server



$env:USE_FOOD_MCP="true"
$env:FOOD_MCP_URL="http://127.0.0.1:8000/mcp"
uvicorn agents_demo.api:app --host 127.0.0.1 --port 8000

打开 http://localhost:8001
输入示例：
“餐食服务”
“我的账号是 38249175，想要 Vegetarian Pasta Primavera”
“FLT-238 有哪些餐食？”
你应看到 Food agent 走 MCP 工具正常响应。

评估
food_mcp_create_dataset
$env:FOOD_MCP_URL="http://127.0.0.1:8000/mcp"
food_mcp_run_test


## 环境准备
1) 安装 Python 依赖：`pip install -e .`
2) 可选，重建 Next.js 静态 UI（Next.js 15 已内置静态导出，直接 build 即可）：
   ```
   cd src/agents_demo/ui
   npm install
   npm run build   # 会在 out/ 生成静态资源
   ```
   会刷新 FastAPI 使用的 `src/agents_demo/ui/out`。

## 运行与访问
- 仅后端：`demo_serve_fastapi` → 打开 `http://localhost:8000`（UI）或 `http://localhost:8000/docs`（API）。
- 仅 Gradio：`demo_serve_gradio` → 控制台查看访问地址（通常 `http://127.0.0.1:7860`）。
- 同时运行：`demo_serve_both` → FastAPI 端口 8000 + 控制台中的 Gradio 地址。

## 额外提示
- 如需自定义主机/端口，可用 `uvicorn agents_demo.api:app --host 0.0.0.0 --port 8000`。
- 运行产生的会话和反馈数据保存在 `src/agents_demo/data/`。

## MCP Food Server
- 启动独立 MCP Server：`python -m agents_demo.mcp_food_server`
- 默认地址：`http://127.0.0.1:8007/mcp`（可用 `FOOD_MCP_HOST`/`FOOD_MCP_PORT` 覆盖）
- 若要让 Food agent 走 MCP：设置 `USE_FOOD_MCP=true`，并确保 `FOOD_MCP_URL` 指向实际服务地址

## MCP 评估（技术要点3b）
- 创建数据集：`food_mcp_create_dataset`
- 运行实验：`food_mcp_run_test`
- 需配置 Langfuse 环境变量（`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_BASE_URL`）并保持 MCP Server 运行
- 评估脚本会读取根目录 `.env`，确保 `USE_OPENAI_MODEL` 与 `FOOD_MCP_URL` 设置正确
