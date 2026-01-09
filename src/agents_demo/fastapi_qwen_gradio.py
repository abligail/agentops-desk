#=========================================================================
#  fastapi_qwen_gradio.py
#  Agents demos using OpenAI Agent SDK, Qwen, langfuse and Gradio UI
#  HCI course project material by Tecching Group, Fudan University, 2025
#=========================================================================

import gradio as gr # Gradio for UI

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from typing import AsyncGenerator
from pydantic import BaseModel,ValidationError
from agents import Agent, Runner, TResponseInputItem

from uuid import uuid4 # for session id
import random
import time

import requests
import json
import logging

#    LLMs and oai agent sdk
from openai import OpenAI
from openai.types.responses import ResponseTextDeltaEvent # added for streaming
from openai import AsyncOpenAI
import asyncio

from dotenv import load_dotenv
import os

from agents import (
    Agent,
    Model,
    ModelSettings, # added for control thinking value of extra_body
    ModelProvider,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    function_tool,
    set_tracing_disabled,
)

# added for langfuse
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from langfuse import get_client,observe
import nest_asyncio


#=========================================
# Load environment variables for Langfuse
#=========================================
load_dotenv()

nest_asyncio.apply()

OpenAIAgentsInstrumentor().instrument()

# Initialize Langfuse client (optional - controlled by env vars)
class _NoopLangfuse:
    def auth_check(self) -> bool:
        return False

    def create_score(self, *args, **kwargs):
        return None

    def get_current_trace_id(self):
        return None

    def update_current_trace(self, *args, **kwargs):
        return None

    def flush(self):
        return None


langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")

if langfuse_public_key and langfuse_secret_key:
    try:
        langfuse = get_client()
        if langfuse.auth_check():  # Verify connection
            print("Langfuse client is authenticated and ready!")
        else:
            print("Langfuse authentication failed. Please check your credentials and host.")
    except Exception as exc:
        print(f"Langfuse initialization failed: {exc}. Running without remote tracing.")
        langfuse = _NoopLangfuse()
else:
    print("Langfuse not configured. Set LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY to enable tracing.")
    langfuse = _NoopLangfuse()
#==============end of langfuse ====================================================

"""  
https://bailian.console.aliyun.com/?tab=model#/model-market/detail/qwen3-next-80b-a3b-instruct
"""
OpenAIModel = os.getenv("USE_OPENAI_MODEL", "false").lower() == "true"
OutputSteaming = os.getenv("OUTPUT_STREAMING", "false").lower() == "true"

if OpenAIModel:
    BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    API_KEY = os.getenv("OPENAI_API_KEY", "")
    MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4.1")
else:
    BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    API_KEY = os.getenv("QWEN_API_KEY", "")
    MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen3-next-80b-a3b-instruct")

# qwen model settings (enable_thinking)
mt = ModelSettings(extra_body={"enable_thinking": True})

if not API_KEY:
    raise ValueError(
        "Missing API key. Please set OPENAI_API_KEY (USE_OPENAI_MODEL=true) or QWEN_API_KEY (USE_OPENAI_MODEL=false)."
    )

# setup OpenAI client for Qwen model or OpenAI model
client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
#======= enable tracing (observation)=========
#set_tracing_disabled(disabled=True) #enable tracing if needed
#=============================================

# setup custom model provider for Qwen model
# with openai model, it also works
class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(model=model_name or MODEL_NAME, openai_client=client)

CUSTOM_MODEL_PROVIDER = CustomModelProvider()


# logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#====================================================
#  endpoint for chat agent, usesless here
#
#url = "http://localhost:8012/v1/chat/completions"
#url = "http://127.0.0.1:8012/v1/chat/completions"  
#headers = {"Content-Type": "application/json"}
#stream_flag = False
#====================================================


#===================================================================================
# Global reference for the current trace_id which is used to later add user feedback
current_trace_id = None
session_id = None   #agent runns in this gradio app, not remotely in fastapi endpoint 
chat_history_sibling = []  #sibling chat history to store meta data for each message
score_experiment_name = "OAI Agent SDK + Qwen + Gradio"
score_name = "user-feedback"
score_rating_name = "user-rating"
FASTAPI_WORKFLOW_BASE_URL = os.getenv("FASTAPI_WORKFLOW_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
FASTAPI_WORKFLOW_CHAT_URL = f"{FASTAPI_WORKFLOW_BASE_URL}/api/chat"
FASTAPI_WORKFLOW_FEEDBACK_URL = f"{FASTAPI_WORKFLOW_BASE_URL}/api/feedback"

def set_new_session_id(): #initialize session id and other global vars
    print("...Setting new session id...")
    global session_id
    global chat_history_sibling
    import uuid
    session_id = str(uuid.uuid4())
    chat_history_sibling.clear()  #clear sibling chat history
set_new_session_id()

#===================================================================================
# Like/Dislike icon event handler for feedback to Langfuse using scores
#===================================================================================
def _submit_feedback_to_backend(
    *,
    conversation_id: Optional[str],
    message_id: Optional[str],
    trace_id: Optional[str],
    liked: bool,
) -> bool:
    if not conversation_id or not message_id or not trace_id:
        return False
    payload = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "trace_id": trace_id,
        "score": 1.0 if liked else 0.0,
        "comment": "Like" if liked else "Dislike",
    }
    try:
        response = requests.post(
            FASTAPI_WORKFLOW_FEEDBACK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        logger.warning(f"Feedback request failed: {exc}")
        return False

def handle_feedback(data: gr.LikeData):
    #Invoked when Like/Dislike icons of assistant message of chatbot is clicked
    # gr.LikeData contains feedback info: index, liked(bool), value (str)
    global current_trace_id
    global chat_history_sibling

    if data.index is None or data.index >= len(chat_history_sibling):
        logger.warning("Feedback index out of range: %s", data.index)
        return

    #current_trace_id is fetched from chat_history_sibling, it can be generated by frontend or backend
    feedback_meta = chat_history_sibling[data.index]
    current_trace_id = feedback_meta.get("current_trace_id")
    message_id = feedback_meta.get("message_id")
    source = feedback_meta.get("source")
    
    if data.liked:
        print(f"User Liked: {data.index}: {current_trace_id}  {data.value}")
        if source == "fastapi_workflow":
            if _submit_feedback_to_backend(
                conversation_id=session_id_workflow,
                message_id=message_id,
                trace_id=current_trace_id,
                liked=True,
            ):
                return
        if current_trace_id:
            langfuse.create_score(
                    name=score_name,
                    value=1.0,
                    trace_id=current_trace_id,
                    data_type="NUMERIC",  # optional, inferred if not provided
                    comment="Like",  # optional
                )

    else:
        print(f"User Disliked: {data.index}: {current_trace_id}  {data.value}")
        if source == "fastapi_workflow":
            if _submit_feedback_to_backend(
                conversation_id=session_id_workflow,
                message_id=message_id,
                trace_id=current_trace_id,
                liked=False,
            ):
                return
        if current_trace_id:
            langfuse.create_score(
                    name=score_name,
                    value=0.0,
                    trace_id=current_trace_id,
                    data_type="NUMERIC",  # inferred if not provided
                    comment="Dislike",  # optional
                )

def _summarize_feedback_content(content: Optional[str]) -> str:
    text = " ".join((content or "").split())
    if len(text) > 60:
        text = text[:60].rstrip() + "..."
    return text or "(empty response)"

def _build_feedback_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in chat_history_sibling:
        if entry.get("role") != "assistant":
            continue
        trace_id = entry.get("current_trace_id")
        if not trace_id:
            continue
        items.append(
            {
                "label": _summarize_feedback_content(entry.get("content")),
                "message_id": entry.get("message_id"),
                "trace_id": trace_id,
                "source": entry.get("source"),
            }
        )
    return items

def _feedback_dropdown_update(items: list[dict[str, Any]]):
    choices = [(f"{idx + 1}. {item['label']}", idx) for idx, item in enumerate(items)]
    value = choices[-1][1] if choices else None
    return gr.update(choices=choices, value=value)

def _parse_rating_choice(choice: Any) -> Optional[int]:
    if choice in (None, "", 0):
        return None
    try:
        rating = int(choice)
    except (TypeError, ValueError):
        return None
    if rating < 1 or rating > 5:
        return None
    return rating

def _submit_rating_to_backend(
    *,
    conversation_id: Optional[str],
    message_id: Optional[str],
    trace_id: Optional[str],
    rating: Optional[int],
    comment: Optional[str],
) -> bool:
    if not conversation_id or not message_id or not trace_id:
        return False
    if rating is None and not comment:
        return False
    payload: dict[str, Any] = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "trace_id": trace_id,
    }
    if rating is not None:
        payload["rating"] = rating
    if comment:
        payload["comment"] = comment
    try:
        response = requests.post(
            FASTAPI_WORKFLOW_FEEDBACK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        logger.warning(f"Rating request failed: {exc}")
        return False

def submit_rating(
    target_index: Optional[int],
    rating_choice: Optional[str],
    comment: Optional[str],
    feedback_items: list[dict[str, Any]],
):
    if target_index is None:
        return "Select an assistant reply first.", gr.update(), gr.update()
    try:
        idx = int(target_index)
    except (TypeError, ValueError):
        return "Invalid feedback target.", gr.update(), gr.update()
    if idx < 0 or idx >= len(feedback_items):
        return "Feedback target not found.", gr.update(), gr.update()

    entry = feedback_items[idx]
    rating = _parse_rating_choice(rating_choice)
    trimmed_comment = (comment or "").strip() or None
    if rating is None and not trimmed_comment:
        return "Provide a rating or a comment.", gr.update(), gr.update()

    if entry.get("source") == "fastapi_workflow":
        ok = _submit_rating_to_backend(
            conversation_id=session_id_workflow,
            message_id=entry.get("message_id"),
            trace_id=entry.get("trace_id"),
            rating=rating,
            comment=trimmed_comment,
        )
        if ok:
            return "Feedback submitted.", gr.update(value=""), gr.update(value="")
        return "Feedback failed to submit.", gr.update(), gr.update()

    trace_id = entry.get("trace_id")
    if not trace_id:
        return "Missing trace id for this reply.", gr.update(), gr.update()
    if rating is None:
        return "Comment-only feedback needs FastAPI workflow.", gr.update(), gr.update()

    langfuse.create_score(
        name=score_rating_name,
        value=float(rating),
        trace_id=trace_id,
        data_type="NUMERIC",
        comment=trimmed_comment or "",
    )
    return "Rating submitted.", gr.update(value=""), gr.update(value="")

def reset_feedback_state():
    chat_history_sibling.clear()
    return [], gr.update(choices=[], value=None)

#============================================================================================
# Main function to create response from Agent runns in gradio app, with langfuse observation
#============================================================================================

# # @observe() for langfuse observation, your can remove it if not needed  
@observe()
async def create_response(message, chat_history):
    
    #======================================================
    # Save trace id in global var to add feedback later
    #======================================================
    global chat_history_sibling
    global current_trace_id
    current_trace_id = langfuse.get_current_trace_id()
    
    # Add session_id to Langfuse Trace to enable session tracking
    global session_id
    langfuse.update_current_trace(name= score_experiment_name,
                                  session_id=session_id,
                                  input= message,)

    #LLM response
    prompt = message

    agent = Agent(name="Assistant", instructions="You are a helpful Assistant.")
    # Must use steaming mode when thinking=true
    # RunConfig=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER, model_settings= mt)
    print(f"LLModel= {MODEL_NAME}") # display model
    if OpenAIModel:
        myRunConfig=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER,)
    else:
        myRunConfig=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER, model_settings=mt)  # qwen model

    result = ""  #initialize

    # we use non-streaming for simplicity
    if OutputSteaming:
        agentResponse = Runner.run_streamed(
            agent,
            #"What's the weather in Tokyo?",
            prompt,
            #run_config=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER, model_settings= mt),
            run_config=myRunConfig,
            )

        # print(f"LLModel= {MODEL_NAME}") # display model
        async for event in agentResponse.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)
                result += event.data.delta
            #collect data for final output
            # to do for streaming usage
    else:
        agentResponse = await Runner.run(
                agent,
                #"What's the weather in Tokyo?",
                input=prompt,
                run_config=myRunConfig,
        )
        print(agentResponse.final_output)
        result = agentResponse.final_output
    
    #===============================================================
    #for data that shoud be cleared after the clear button is clicked
    if len( chat_history_sibling) > len(chat_history):
        chat_history_sibling.clear()
    # ==============================================================

    chat_history.append({"role": "user", "content": message})
    chat_history_sibling.append(
        {
            "role": "user",
            "content": message,
            "current_trace_id": current_trace_id,
            "message_id": None,
            "source": "local",
        }
    )
    chat_history.append({"role": "assistant", "content": result})
    chat_history_sibling.append(
        {
            "role": "assistant",
            "content": result,
            "current_trace_id": current_trace_id,
            "message_id": None,
            "source": "local",
        }
    )
    
    langfuse.flush()

    #==========================================================
    time.sleep(1)
    feedback_items = _build_feedback_items()
    feedback_update = _feedback_dropdown_update(feedback_items)
    return "", chat_history, feedback_items, feedback_update
        

"""
#maybe userful in someday for streaming response
#streaming response (we use non-streaming for simplicity)
async def respond(prompt: str, history):
    async for message in create_response(prompt, history):
            yield message             
"""
#=============================================================
# fastapi - simple agent demo
#=============================================================
class AgentRequest(BaseModel):
    """Standard request model for agent interactions."""
    input: str | list[TResponseInputItem]
    context: Optional[dict[str, Any]] = None
    session_id: Optional[str] = None


class AgentResponse(BaseModel):
    """Standard response model for agent interactions."""
    final_output: Any
    success: bool = True
    error: Optional[str] = None
    usage: Optional[dict[str, Any]] = None
    response_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None

# @observe() for langfuse observation, your can remove it if not needed
@observe()
async def create_response_fastapi(message, chat_history):
    request_data = AgentRequest(input=message) #input text to AgentRequest model
    json_data = request_data.model_dump_json()
    
    """
    curl -X POST "http://127.0.0.1:8080/chat/run" ^
    -H "Content-Type: application/json" ^
    -d "{\"input\": \"Hello, how can you help me?\"}"
    """
    url_fastapi = "http://127.0.0.1:8080/chat/run"  #endpoint for chat agent
    headers_fastapi = {"Content-Type": "application/json"}

    #response = requests.post(url, headers=headers, data=json.dumps(data,ensure_ascii=False))
    try:
        response = requests.post(url_fastapi, headers=headers_fastapi, data=json_data)
        response.raise_for_status()

        agent_response = AgentResponse(**response.json())  #parse response json to AgentResponse model
        bot_message = agent_response.final_output

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        bot_message = "Error: Invalid request."
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        bot_message = "Error: Invalid response format from the server."
    except Exception as e:
        logger.error(f"Other Error: {e}")
        bot_message = "Error: Unable to get response from the server."
    
    #chat_history.append({"role": "user", "content": message})
    #chat_history.append({"role": "assistant", "content": bot_message})

    #===============================================================
    #for data that shoud be cleared after the clear button is clicked
    if len( chat_history_sibling) > len(chat_history):
        chat_history_sibling.clear()
    # ==============================================================

    #=================================================================================================
    # Extract real trace_id from backend response (if available)
    #=================================================================================================
    current_trace_id = getattr(agent_response, 'trace_id', None) or "unknown_trace"
    if current_trace_id == "unknown_trace":
        logger.warning("No trace_id in simple agent response")
    #=================================================================================================

    chat_history.append({"role": "user", "content": message})
    chat_history_sibling.append(
        {
            "role": "user",
            "content": message,
            "current_trace_id": current_trace_id,
            "message_id": None,
            "source": "fastapi_simple",
        }
    )
    chat_history.append({"role": "assistant", "content": bot_message})
    chat_history_sibling.append(
        {
            "role": "assistant",
            "content": bot_message,
            "current_trace_id": current_trace_id,
            "message_id": None,
            "source": "fastapi_simple",
        }
    )
    
    """
    if response.status_code == 200:
        res_json = response.json()
        logger.info(f"Response JSON: {res_json}")
        bot_message = res_json['choices'][0]['message']['content']
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": bot_message})
    """
    feedback_items = _build_feedback_items()
    feedback_update = _feedback_dropdown_update(feedback_items)
    return "", chat_history, feedback_items, feedback_update
        
#================================================================================
# fastapi - workflow agent demo
# check api.py for more details about traces and feedback to obersvation platform
#================================================================================
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str

class MessageResponse(BaseModel):
    id: Optional[str] = None
    content: str
    agent: str
    trace_id: Optional[str] = None
    feedback: Optional[float] = None
    rating: Optional[int] = None
    comment: Optional[str] = None

class AgentEvent(BaseModel):
    id: str
    type: str
    agent: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

class GuardrailCheck(BaseModel):
    id: str
    name: str
    input: str
    reasoning: str
    passed: bool
    timestamp: float

class ChatResponse(BaseModel):
    conversation_id: str
    current_agent: str
    messages: List[MessageResponse]
    events: List[AgentEvent]
    context: Dict[str, Any]
    agents: List[Dict[str, Any]]
    guardrails: List[GuardrailCheck] = []
    trace_id: Optional[str] = None

session_id_workflow:Optional[str] = None

def display_seat_map():
    # Function to display seat map
    return "Seats Available[1A,1B,2C,3D][FrontInfo]"

# @observe() for langfuse observation, your can remove it if not needed
@observe()
async def create_response_fastapi_workflow(message, chat_history):
    global session_id_workflow
    
    print(f"session_id_workflow before request: {session_id_workflow}")
    request_data = ChatRequest(conversation_id=session_id_workflow, message=message)
    json_data = request_data.model_dump_json()
    #print(f"Request JSON data: {json_data}")
    
    #fastapi endpoint for chat client
    url_fastapi = FASTAPI_WORKFLOW_CHAT_URL
    headers_fastapi = {"Content-Type": "application/json"}

    error_occurred = False
    try:
        #response = requests.post(url, headers=headers, data=json.dumps(data,ensure_ascii=False)) #old function
        response = requests.post(url_fastapi, headers=headers_fastapi, data=json_data)
        response.raise_for_status()

        agent_response = ChatResponse(**response.json())  #parse response json to AgentResponse model
        #bot_message = agent_response.final_output

        if(agent_response.conversation_id is not None):
            if(session_id_workflow != agent_response.conversation_id):
                session_id_workflow = agent_response.conversation_id
                #print(f"Updated session_id_workflow: {session_id_workflow}")

        #for data that shoud be cleared after the clear button is clicked
        if len( chat_history_sibling) > len(chat_history):
            chat_history_sibling.clear()

        chat_history.append({"role": "user", "content": message})

        #=================================================================================================
        # Extract trace_id from backend response
        #=================================================================================================
        default_trace_id = agent_response.trace_id or "unknown_trace"
        if default_trace_id == "unknown_trace":
            logger.warning("No trace_id received from backend")
        #=================================================================================================

        chat_history_sibling.append(
            {
                "role": "user",
                "content": message,
                "current_trace_id": default_trace_id,
                "message_id": None,
                "source": "fastapi_workflow",
            }
        )
            
        for msg in agent_response.messages:
            if(msg.content =="DISPLAY_SEAT_MAP"):  #content="DISPLAY_SEAT_MAP",
                bot_message = display_seat_map() # + session_id_workflow
            else:
                bot_message = msg.content + "[" + msg.agent + "]" #+session_id_workflow
            
            #print(f"bot_message: {bot_message}")
            chat_history.append({"role": "assistant", "content": bot_message})
            message_trace_id = msg.trace_id or default_trace_id
            chat_history_sibling.append(
                {
                    "role": "assistant",
                    "content": bot_message,
                    "current_trace_id": message_trace_id,
                    "message_id": msg.id,
                    "source": "fastapi_workflow",
                }
            )
        

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        error_occurred = True
        bot_message = "Error: Invalid request."
    except ValidationError as e:
        error_occurred = True
        logger.error(f"Validation failed: {e}")
        bot_message = "Error: Invalid response format from the server."
    except Exception as e:
        error_occurred = True
        logger.error(f"Other Error: {e}")
        bot_message = "Error: Unable to get response from the server."
    
    if error_occurred:
        
        #for chat_history_sibling that shoud be cleared after the clear button is clicked
        if len( chat_history_sibling) > len(chat_history):
            chat_history_sibling.clear()
        
        fallback_trace_id = "0000000000000"  #placeholder only, add real trace id from response if possible
        chat_history.append({"role": "user", "content": message})
        chat_history_sibling.append(
            {
                "role": "user",
                "content": message,
                "current_trace_id": fallback_trace_id,
                "message_id": None,
                "source": "fastapi_workflow",
            }
        )
        chat_history.append({"role": "assistant", "content": bot_message})
        chat_history_sibling.append(
            {
                "role": "assistant",
                "content": bot_message,
                "current_trace_id": fallback_trace_id,
                "message_id": None,
                "source": "fastapi_workflow",
            }
        )
    
    """
    if response.status_code == 200:
        res_json = response.json()
        logger.info(f"Response JSON: {res_json}")
        bot_message = res_json['choices'][0]['message']['content']
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": bot_message})
    """

    feedback_items = _build_feedback_items()
    feedback_update = _feedback_dropdown_update(feedback_items)
    return "", chat_history, feedback_items, feedback_update

def run_gradio():
    #================================================================
    #  Gradio UI for agent demos
    # ===============================================================
    with gr.Blocks() as oaiagent_front:
        
        chatbot = gr.Chatbot(label="Workflow-OAI Agent SDK - Chat History")
        msg = gr.Textbox(label = "Input your query")  #input text box
        feedback_items = gr.State([])
        gr.Markdown("### Feedback")
        feedback_target = gr.Dropdown(
            label="Feedback target",
            choices=[],
            value=None,
        )
        rating_choice = gr.Dropdown(
            label="Star rating (optional)",
            choices=[
                ("No rating", ""),
                ("1 star", "1"),
                ("2 stars", "2"),
                ("3 stars", "3"),
                ("4 stars", "4"),
                ("5 stars", "5"),
            ],
            value="",
        )
        comment_box = gr.Textbox(
            label="Text feedback (optional)",
            lines=2,
            placeholder="Add a short note if needed.",
        )
        submit_feedback_btn = gr.Button("Submit feedback")
        feedback_status = gr.Markdown()
       
        clear_btn = gr.ClearButton(
            [msg, chatbot, feedback_target, rating_choice, comment_box, feedback_status]
        )  #clear button for chat history
    
        #============= three functions for msg.submit ===========================
        # non-fastapi version with langfuse feedback
        #msg.submit(create_response, [msg, chatbot], [msg, chatbot])
        
        # fastapi version without langfuse
        #msg.submit(create_response_fastapi, [msg, chatbot], [msg, chatbot])
        
        #fastapi workflow version without langfuse
        msg.submit(
            create_response_fastapi_workflow,
            [msg, chatbot],
            [msg, chatbot, feedback_items, feedback_target],
        )
        
        # like/dislike button handler
        chatbot.like(handle_feedback, None, None)
        
        submit_feedback_btn.click(
            submit_rating,
            [feedback_target, rating_choice, comment_box, feedback_items],
            [feedback_status, rating_choice, comment_box],
        )
        clear_btn.click(reset_feedback_state, None, [feedback_items, feedback_target])
        #clear_btn.click(lambda: [], None, chat_history_sibling)  # clear chat history sibling, not tested
    
    oaiagent_front.launch()
