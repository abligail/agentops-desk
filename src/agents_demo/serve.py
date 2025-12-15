import uvicorn

from .fastapi_qwen_gradio import run_gradio
import multiprocessing as mp


def serve_fastapi():
	uvicorn.run("agents_demo.api:app", host="127.0.0.1", port=8000)
 
def serve_gradio():
	run_gradio()

def serve_both():
	mp.set_start_method("spawn", force=True)  # macOS 推荐
	p1 = mp.Process(target=serve_fastapi, daemon=True)
	p2 = mp.Process(target=serve_gradio, daemon=True)
	p1.start(); p2.start()
	p1.join(); p2.join()