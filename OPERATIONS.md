# 演示运行手册

## 常用命令
- `demo_serve_fastapi`：启动 FastAPI 后端（端口 8000），同时提供 `src/agents_demo/ui/out` 静态界面。
- `demo_serve_gradio`：启动基于 Qwen/OpenAI Agent SDK 的 Gradio 界面。
- `demo_serve_both`：同时启动 FastAPI 和 Gradio（多进程）。

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
