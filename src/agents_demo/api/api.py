from importlib.resources import files
from pathlib import Path
import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import uuid4
import time
import logging
import asyncio

from starlette.staticfiles import StaticFiles

# Load environment variables
load_dotenv()

# Import agents and context creation from main_qwen (SUPPORT QWEN MODEL)
from agents_demo.agents.main_qwen import (
    triage_agent,
    faq_agent,
    seat_booking_agent,
    flight_status_agent,
    cancellation_agent,
    create_initial_context,
    AirlineAgentContext,
    food_service_agent,
    USE_FOOD_MCP,
    FOOD_MCP_SERVER,
)
from agents_demo.agents.main_qwen import (
    OpenAIModel as bOpenAIModel,
)  # True: use OpenAI model; False: use Qwen model
from agents_demo.agents.main_qwen import myRunConfig
from agents_demo.services.storage import (
    CompositeConversationStore,
    JsonConversationStore,
    PostgresConversationStore,
)
from agents_demo.services.telemetry import Telemetry
from agents_demo.services.evaluators import evaluate_and_score_trace
from agents_demo.services.data_loader import get_seats_by_flight
from agents_demo.models.seat_assignments import seat_assignment_store
from agents_demo.mcp.mcp_integration import get_mcp_integration


"""
from main import (
    triage_agent,
    faq_agent,
    seat_booking_agent,
    flight_status_agent,
    cancellation_agent,
    create_initial_context,
)
"""

from agents import (
    Runner,
    ItemHelpers,
    MessageOutputItem,
    HandoffOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    InputGuardrailTripwireTriggered,
    Handoff,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================================================================================
# Initialize Langfuse client for trace management (v3 API)
# ===================================================================================
try:
    from langfuse import get_client

    # Note: get_client() automatically reads from environment variables:
    # LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (or LANGFUSE_BASE_URL)
    langfuse_client = get_client()
    logger.info("Langfuse client initialized successfully (v3 SDK)")
    LANGFUSE_ENABLED = True
except Exception as e:
    logger.warning(f"Langfuse initialization failed: {e}. Tracing will be disabled.")
    langfuse_client = None
    LANGFUSE_ENABLED = False

# Initialize MCP integration
try:
    mcp_integration = get_mcp_integration()
    mcp_integration.initialize(langfuse_client=langfuse_client, telemetry=None)
    logger.info("MCP Integration initialized via API startup")
except Exception as e:
    logger.warning(f"MCP Integration initialization failed: {e}")

# fastapi app instance
app = FastAPI()

# CORS configuration (adjust as needed for deployment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dangous security setting for demo purpose only
    # allow_origins=["http://localhost:3000","http://localhost:3001","http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# Models
# =========================


# From frontend request
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


# agent message response
class MessageResponse(BaseModel):
    id: str
    content: str
    agent: str
    trace_id: Optional[str] = None
    timestamp: float
    feedback: Optional[float] = None
    rating: Optional[int] = None
    comment: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None  # Added evaluation info per message
    mcp_metrics: Optional[Dict[str, Any]] = None  # Added MCP metrics info per message


# agent event log of workflow
class AgentEvent(BaseModel):
    id: str
    type: str
    agent: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


# guardrail check input/output
class GuardrailCheck(BaseModel):
    id: str
    name: str
    input: str
    reasoning: str
    passed: bool
    timestamp: float


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    trace_id: str
    score: Optional[float] = None
    rating: Optional[int] = None
    comment: Optional[str] = None


class SeatMapSection(BaseModel):
    rows: List[int] = Field(default_factory=list)
    seats_per_row: List[str] = Field(default_factory=list)
    occupied: List[str] = Field(default_factory=list)
    exit_rows: List[int] = Field(default_factory=list)
    premium: List[str] = Field(default_factory=list)


class SeatMapResponse(BaseModel):
    conversation_id: str
    flight_number: str
    aircraft: Optional[str] = None
    sections: Dict[str, SeatMapSection]
    current_seat: Optional[str] = None


# ****************************************************************************************************
# ===================================================================================================
# Response Model： sending response back to frontend app
# Add fields, such as trace id for getting user feedback from frontend, fastapi app sending trace id
# generated by tracing agent run with langfuse， to frontend for display message with trace ID.
# Traces can be scored in frontend app if obersavation platform allows multiple accesses simultaneously.
# Otherwise，they can be sent back along with feedback values to backend for computing scores.
# ===================================================================================================
# ****************************************************************************************************
class ChatResponse(BaseModel):
    conversation_id: str
    current_agent: str
    messages: List[MessageResponse]
    events: List[AgentEvent]
    context: Dict[str, Any]
    agents: List[Dict[str, Any]]
    guardrails: List[GuardrailCheck] = Field(default_factory=list)
    trace_id: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None  # Added for evaluation details
    mcp_metrics: Optional[Dict[str, Any]] = None  # Added for MCP metrics


# ===================================================================================
# Persistent conversation store instance
# ===================================================================================
data_dir = Path(__file__).resolve().parent.parent / "data"
primary_store = None
try:
    primary_store = PostgresConversationStore(
        context_loader=lambda payload: AirlineAgentContext(**payload),
        seed_path=data_dir / "conversations.json",
    )
except Exception as exc:
    logger.warning("Postgres store unavailable, using JSON store only: %s", exc)

json_store = JsonConversationStore(
    data_dir / "conversations.json",
    context_loader=lambda payload: AirlineAgentContext(**payload),
)

if primary_store is None:
    conversation_store = json_store
else:
    conversation_store = CompositeConversationStore(
        primary_store,
        json_store,
        sync_secondary_from_primary=True,
    )

# ===================================================================================
# Telemetry for trace logging and feedback forwarding
# ===================================================================================
telemetry = Telemetry(
    trace_log=data_dir / "traces.jsonl",
    feedback_log=data_dir / "feedback.jsonl",
)


@app.on_event("startup")
async def _connect_food_mcp() -> None:
    """Ensure the Food MCP server is connected before handling requests."""
    if USE_FOOD_MCP and FOOD_MCP_SERVER is not None:
        try:
            await FOOD_MCP_SERVER.connect()
            logger.info("Food MCP server connected")
        except Exception as exc:
            logger.warning("Failed to connect Food MCP server: %s", exc)

# =========================
# Helpers
# =========================


def _get_agent_by_name(name: str):
    """Return the agent object by name."""
    agents = {
        triage_agent.name: triage_agent,
        faq_agent.name: faq_agent,
        seat_booking_agent.name: seat_booking_agent,
        flight_status_agent.name: flight_status_agent,
        cancellation_agent.name: cancellation_agent,
        food_service_agent.name: food_service_agent,
    }
    return agents.get(name, triage_agent)


def _get_guardrail_name(g) -> str:
    """Extract a friendly guardrail name."""
    name_attr = getattr(g, "name", None)
    if isinstance(name_attr, str) and name_attr:
        return name_attr
    guard_fn = getattr(g, "guardrail_function", None)
    if guard_fn is not None and hasattr(guard_fn, "__name__"):
        return guard_fn.__name__.replace("_", " ").title()
    fn_name = getattr(g, "__name__", None)
    if isinstance(fn_name, str) and fn_name:
        return fn_name.replace("_", " ").title()
    return str(g)


def _build_agents_list() -> List[Dict[str, Any]]:
    """Build a list of all available agents and their metadata."""

    def make_agent_dict(agent):
        return {
            "name": agent.name,
            "description": getattr(agent, "handoff_description", ""),
            "handoffs": [
                getattr(h, "agent_name", getattr(h, "name", ""))
                for h in getattr(agent, "handoffs", [])
            ],
            "tools": [
                getattr(t, "name", getattr(t, "__name__", ""))
                for t in getattr(agent, "tools", [])
            ],
            "input_guardrails": [
                _get_guardrail_name(g) for g in getattr(agent, "input_guardrails", [])
            ],
        }

    return [
        make_agent_dict(triage_agent),
        make_agent_dict(faq_agent),
        make_agent_dict(seat_booking_agent),
        make_agent_dict(flight_status_agent),
        make_agent_dict(cancellation_agent),
        make_agent_dict(food_service_agent),
    ]


# =========================
# Background Tasks
# =========================


async def run_llm_judge_evaluation(
    conversation_id: str,
    trace_id: str,
    user_message: str,
    assistant_messages: List[str],
    agent_name: str,
):
    """Background task to evaluate response quality using LLM-as-a-Judge."""
    if not LANGFUSE_ENABLED or not langfuse_client:
        logger.info("Langfuse not enabled, skipping LLM judge evaluation")
        return

    try:
        score = await evaluate_and_score_trace(
            trace_id=trace_id,
            user_message=user_message,
            assistant_messages=assistant_messages,
            agent_name=agent_name,
            langfuse_client=langfuse_client,
        )
        # Flush to ensure scores are sent
        langfuse_client.flush()
        logger.info(f"LLM judge evaluation completed and flushed for trace {trace_id}")

        if score:
            # Update conversation store with the evaluation result
            state = conversation_store.get(conversation_id)
            if state and "trace_history" in state:
                updated = False
                for trace in state["trace_history"]:
                    if trace.get("trace_id") == trace_id:
                        # Update the last message in this trace with evaluation
                        if trace.get("messages"):
                            trace["messages"][-1]["evaluation"] = score.model_dump()
                            updated = True
                        break

                if updated:
                    conversation_store.save(conversation_id, state)
                    logger.info(
                        f"Updated conversation store with evaluation for trace {trace_id}"
                    )

    except Exception as e:
        logger.error(f"LLM judge evaluation failed for trace {trace_id}: {e}")


# =========================
# Main Chat Endpoint
# =========================


@app.get("/api/history/{conversation_id}", response_model=ChatResponse)
async def history_endpoint(conversation_id: str):
    """Retrieve the full conversation history including updated evaluations."""
    state = conversation_store.get(conversation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Reconstruct the response format from state
    # We need to flatten trace_history to get all messages and events
    all_messages = []
    all_events = []
    all_guardrails = []

    # Iterate through trace history to build the full timeline
    if "trace_history" in state:
        for trace in state["trace_history"]:
            all_messages.extend(trace.get("messages", []))
            all_guardrails.extend(trace.get("guardrails", []))
            # Note: events are not currently stored in trace_history in the exact format needed
            # so we might miss historical events if we rely only on this.
            # However, for simply updating the chat view with messages and scores, this is sufficient.

    # Current context
    ctx = state.get("context", {})
    if hasattr(ctx, "model_dump"):
        ctx = ctx.model_dump()

    current_agent_name = state.get("current_agent", triage_agent.name)

    return ChatResponse(
        conversation_id=conversation_id,
        current_agent=current_agent_name,
        messages=all_messages,
        events=[],  # Events are transient in this simple store implementation
        context=ctx,
        agents=_build_agents_list(),
        guardrails=all_guardrails,
        trace_id=None,  # No active trace for history fetch
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, background_tasks: BackgroundTasks):
    print(
        f"Received chat request: conversation_id={req.conversation_id}, message={req.message} "
    )
    trace_id = uuid4().hex
    now_ms = time.time() * 1000

    # ===================================================================================
    # Create Langfuse trace for this interaction (v3 API)
    # ===================================================================================
    langfuse_span = None

    if LANGFUSE_ENABLED and langfuse_client:
        # Langfuse v3 SDK relies on OpenTelemetry or trace_id + observability
        # It does NOT have a .trace() method on the client instance anymore.
        # Instead, we should use `create_trace` if available (it's not),
        # or simply rely on `trace_id` being passed to scores/generations.

        # However, to ensure a trace "root" exists in the dashboard with metadata,
        # we might need to use `langfuse.trace()` if it was available (it's not).

        # Looking at the available methods:
        # 'create_score', 'create_event', 'start_span', 'start_generation', ...
        # There is no direct 'create_trace' or 'trace' method exposed on the client object itself
        # in the version installed.

        # BUT, standard Langfuse usage often involves `langfuse.trace(...)`.
        # If it's missing, it might be because we are using a specific client initialization
        # or version that favors OTEL.

        # Workaround:
        # Since we just need the ID to associate subsequent scores/events,
        # and we don't have a way to explicitly "start" a trace object via the client
        # (without using decorators or context managers which we aren't using here),
        # we will skip explicit trace object creation and just log the ID.
        # The 'create_score' calls later use this trace_id, which will create the trace
        # in Langfuse if it doesn't exist (lazy creation) or associate it correctly.

        # If we really want to set metadata (like user_id) on the trace, we might need
        # to send an event or generation that includes it, or use `update_current_trace`
        # if we were in a context.

        # logger.info(
        #    f"Using trace ID: {trace_id}. Skipping explicit trace object creation as .trace() is unavailable."
        # )

        try:
            # Try to force trace creation by starting a span with that trace_id
            # This ensures the trace appears in the dashboard even if empty
            # We use a very short dummy span as the "root" placeholder if needed,
            # but ideally we just want to establish the trace context.

            # Create a dummy span to initialize the trace in Langfuse
            # Using the trace_id we generated
            # trace_context = {"trace_id": trace_id}

            # Start a span and immediately end it just to register the trace
            # We call it "interaction_root" or similar

            # NOTE: start_span returns a LangfuseSpan, not a context manager.
            # We should use it directly or use start_as_current_span if we wanted a context manager.
            # Here we just want to fire and forget to register the trace.

            # Since the client has no .trace() method, we create a span to root the trace
            langfuse_span = langfuse_client.start_span(
                name="chat_interaction",
                # trace_context expects a TraceContext object or dict with specific shape
                # but passing trace_id via trace_context is how we link it
                trace_context={"trace_id": trace_id},
                metadata={"conversation_id": req.conversation_id},
                input=req.message,
            )
            # span.end() - Moved to end of request processing to capture output/usage

            logger.info(f"Initialized trace {trace_id} with root span")

        except Exception as e:
            logger.warning(f"Failed to create explicit trace object: {e}")

    # Fallback: Just log the ID we generated
    logger.info(f"Generated trace ID for this interaction: {trace_id}")

    """
	Main chat endpoint for agent orchestration.
	Handles conversation state, agent routing, and guardrail checks.
	"""
    # Initialize or retrieve conversation state
    existing_state = (
        conversation_store.get(req.conversation_id) if req.conversation_id else None
    )
    is_new = existing_state is None
    if is_new:
        conversation_id: str = uuid4().hex
        ctx = create_initial_context()  # flight booking context
        current_agent_name = triage_agent.name

        # ========================================
        #     state for first time conversation
        # ========================================
        state: Dict[str, Any] = {
            "input_items": [],  # list of TResponseInputItem for Runner.run
            "context": ctx,  # flight booking context
            "current_agent": current_agent_name,  # agent to start with
            "trace_history": [],
            "feedback": [],
        }
        if req.message.strip() == "":
            conversation_store.save(conversation_id, state)
            return ChatResponse(
                conversation_id=conversation_id,
                current_agent=current_agent_name,
                messages=[],
                events=[],
                context=ctx.model_dump(),
                agents=_build_agents_list(),
                guardrails=[],
                trace_id=trace_id,
            )
    else:
        conversation_id = str(req.conversation_id)
        # ===============================================
        #   retrieve state for conversation from store
        # ===============================================
        if existing_state is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        state = existing_state

    # =============================================
    # prepare parameters for Runner
    # =============================================
    current_agent = _get_agent_by_name(
        state["current_agent"]
    )  # pick this agent for running
    state["input_items"].append(
        {"content": req.message, "role": "user"}
    )  # input for runner.run
    old_context = (
        state["context"].model_dump().copy()
        if hasattr(state["context"], "model_dump")
        else dict(state["context"])
    )  # context for runner.run
    guardrail_checks: List[GuardrailCheck] = []

    try:
        result = None

        # ===========================================================================================
        # check: https://openai.github.io/openai-agents-python/ref/run/#agents.run.Runner.run
        # run with input(list[TResponseInputItem] ) and context (flight booking context)
        # ===========================================================================================

        # Initialize MCP tracking if available
        mcp_int = get_mcp_integration()
        should_track = mcp_int.is_initialized() and mcp_int.evaluator is not None

        if should_track and mcp_int.evaluator:
            # Wrap agent tools for tracking
            mcp_int.evaluator.wrap_agent(current_agent)
            # Start tracking context
            mcp_int.evaluator.tracker.start_trace(trace_id, current_agent.name)

        try:
            if bOpenAIModel:  # zdjiang added for qwen3
                result = await Runner.run(
                    current_agent, state["input_items"], context=state["context"]
                )
            else:
                result = await Runner.run(
                    current_agent,
                    state["input_items"],
                    context=state["context"],
                    run_config=myRunConfig,
                )
        finally:
            # Ensure we close the trace context
            if should_track and mcp_int.evaluator:
                mcp_int.evaluator.tracker.end_trace()

                # Submit metrics to Langfuse if enabled
                if LANGFUSE_ENABLED and langfuse_client:
                    try:
                        stats = mcp_int.evaluator.tracker.get_statistics()
                        stats["agent_name"] = current_agent.name
                        await mcp_int.evaluator._submit_evaluation_to_langfuse(
                            trace_id,
                            stats,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to submit MCP metrics: {e}")

    except InputGuardrailTripwireTriggered as e:  # gurdrail tripwire triggered
        failed = e.guardrail_result.guardrail
        gr_output = e.guardrail_result.output.output_info
        gr_reasoning = getattr(gr_output, "reasoning", "")
        gr_input = req.message
        gr_timestamp = time.time() * 1000
        for g in current_agent.input_guardrails:
            guardrail_checks.append(
                GuardrailCheck(
                    id=uuid4().hex,
                    name=_get_guardrail_name(g),
                    input=gr_input,
                    reasoning=(gr_reasoning if g == failed else ""),
                    passed=(g != failed),
                    timestamp=gr_timestamp,
                )
            )
        refusal = "Sorry, I can only answer questions related to airline travel."
        state["input_items"].append(
            {"role": "assistant", "content": refusal}
        )  # record refusal in conversation history
        refusal_message = MessageResponse(
            id=uuid4().hex,
            content=refusal,
            agent=current_agent.name,
            trace_id=trace_id,
            timestamp=gr_timestamp,
        )
        conversation_store.save(conversation_id, state)
        telemetry.record_trace(
            trace_id=trace_id,
            conversation_id=conversation_id,
            agent=current_agent.name,
            user_message=req.message,
            assistant_messages=[refusal_message.model_dump()],
            guardrails=[gc.model_dump() for gc in guardrail_checks],
        )
        return ChatResponse(
            conversation_id=conversation_id,
            current_agent=current_agent.name,
            messages=[refusal_message],
            events=[],
            context=state["context"].model_dump()
            if hasattr(state["context"], "model_dump")
            else state["context"],
            agents=_build_agents_list(),
            guardrails=guardrail_checks,
            trace_id=trace_id,
        )

    # ===============================
    #  Process result items
    # ================================
    messages: List[MessageResponse] = []  # agent messages to return
    events: List[AgentEvent] = []  # agent events to return

    # ================================================================================
    # Process new items from the run result
    # check: https://openai.github.io/openai-agents-python/ref/result/
    # check: https://openai.github.io/openai-agents-python/ref/items/
    # ================================================================================
    for item in result.new_items:
        if isinstance(item, MessageOutputItem):
            text = ItemHelpers.text_message_output(item)
            msg_ts = time.time() * 1000
            msg_id = uuid4().hex
            messages.append(
                MessageResponse(
                    id=msg_id,
                    content=text,
                    agent=item.agent.name,
                    trace_id=trace_id,
                    timestamp=msg_ts,
                )
            )
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="message",
                    agent=item.agent.name,
                    content=text,
                    timestamp=msg_ts,
                )
            )

        # Handle handoff output and agent switching
        elif isinstance(item, HandoffOutputItem):
            # Record the handoff event
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="handoff",
                    agent=item.source_agent.name,
                    content=f"{item.source_agent.name} -> {item.target_agent.name}",
                    metadata={
                        "source_agent": item.source_agent.name,
                        "target_agent": item.target_agent.name,
                    },
                    timestamp=time.time() * 1000,
                )
            )
            # If there is an on_handoff callback defined for this handoff, show it as a tool call
            from_agent = item.source_agent
            to_agent = item.target_agent
            # Find the Handoff object on the source agent matching the target
            ho = next(
                (
                    h
                    for h in getattr(from_agent, "handoffs", [])
                    if isinstance(h, Handoff)
                    and getattr(h, "agent_name", None) == to_agent.name
                ),
                None,
            )
            if ho:
                fn = ho.on_invoke_handoff
                fv = fn.__code__.co_freevars
                cl = fn.__closure__ or []
                if "on_handoff" in fv:
                    idx = fv.index("on_handoff")
                    if idx < len(cl) and cl[idx].cell_contents:
                        cb = cl[idx].cell_contents
                        cb_name = getattr(cb, "__name__", repr(cb))
                        events.append(
                            AgentEvent(
                                id=uuid4().hex,
                                type="tool_call",
                                agent=to_agent.name,
                                content=cb_name,
                                timestamp=time.time() * 1000,
                            )
                        )
            # ==========================================================
            # handoff target agent is the starting agent of next run
            current_agent = item.target_agent
            # ==========================================================

        elif isinstance(item, ToolCallItem):
            tool_name = getattr(item.raw_item, "name", None)
            raw_args = getattr(item.raw_item, "arguments", None)
            tool_args: Any = raw_args
            if isinstance(raw_args, str):
                try:
                    import json

                    tool_args = json.loads(raw_args)
                except Exception:
                    pass
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="tool_call",
                    agent=item.agent.name,
                    content=tool_name or "",
                    metadata={"tool_args": tool_args},
                    timestamp=time.time() * 1000,
                )
            )

            # ================== important trick for frontend interaction ===================================
            # If the tool is display_seat_map, send a special message so the UI can render the seat selector.
            # ===============================================================================================
            if tool_name == "display_seat_map":
                messages.append(
                    MessageResponse(
                        id=uuid4().hex,
                        content="DISPLAY_SEAT_MAP",
                        agent=item.agent.name,
                        trace_id=trace_id,
                        timestamp=time.time() * 1000,
                    )
                )
        elif isinstance(item, ToolCallOutputItem):
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="tool_output",
                    agent=item.agent.name,
                    content=str(item.output),
                    metadata={"tool_result": item.output},
                    timestamp=time.time() * 1000,
                )
            )

    # Check for context updates
    new_context = state["context"].model_dump()
    changes = {
        k: new_context[k] for k in new_context if old_context.get(k) != new_context[k]
    }
    if changes:
        events.append(
            AgentEvent(
                id=uuid4().hex,
                type="context_update",
                agent=current_agent.name,
                content="",
                metadata={"changes": changes},
                timestamp=time.time() * 1000,
            )
        )
    # ==================================================================================================
    # Save updated conversation state
    # https://openai.github.io/openai-agents-python/running_agents/#conversationschat-threads
    # https://openai.github.io/openai-agents-python/ref/result/#agents.result.RunResult.to_input_list
    state["input_items"] = (
        result.to_input_list()
    )  # check above links for to_input_list method details
    state["current_agent"] = current_agent.name
    # ==================================================================================================

    # Build guardrail results: mark failures (if any), and any others as passed
    final_guardrails: List[GuardrailCheck] = []
    for g in getattr(current_agent, "input_guardrails", []):
        name = _get_guardrail_name(g)
        failed = next((gc for gc in guardrail_checks if gc.name == name), None)
        if failed:
            final_guardrails.append(failed)
        else:
            final_guardrails.append(
                GuardrailCheck(
                    id=uuid4().hex,
                    name=name,
                    input=req.message,
                    reasoning="",
                    passed=True,
                    timestamp=time.time() * 1000,
                )
            )

    state.setdefault("trace_history", []).append(
        {
            "trace_id": trace_id,
            "timestamp": now_ms,
            "agent": current_agent.name,
            "messages": [m.model_dump() for m in messages],
            "guardrails": [g.model_dump() for g in final_guardrails],
        }
    )
    conversation_store.save(conversation_id, state)

    # ===================================================================================
    # Schedule LLM-as-a-Judge evaluation as background task (optional - can be disabled)
    # ===================================================================================
    evaluation_result = None
    if messages and os.getenv("ENABLE_LLM_JUDGE", "true").lower() == "true":
        # Run asynchronously for better user experience
        background_tasks.add_task(
            run_llm_judge_evaluation,
            conversation_id=conversation_id,
            trace_id=trace_id,
            user_message=req.message,
            assistant_messages=[m.content for m in messages],
            agent_name=current_agent.name,
        )
        logger.info(
            f"Scheduled LLM judge evaluation background task for trace {trace_id}"
        )

    # Collect MCP metrics if available
    mcp_metrics_data = None
    if should_track and mcp_int.evaluator:
        try:
            stats = mcp_int.evaluator.tracker.get_statistics()
            # Only include if there were actual calls
            if stats.get("total_calls", 0) > 0:
                mcp_metrics_data = {
                    "totalCalls": stats.get("total_calls", 0),
                    "successRate": stats.get("success_rate", 0),
                    "avgTime": stats.get("average_execution_time", 0),
                }
        except Exception as e:
            logger.warning(f"Failed to collect MCP metrics for response: {e}")

    # Pass evaluation and metrics to the LAST assistant message for display
    if messages:
        messages[-1].evaluation = evaluation_result
        messages[-1].mcp_metrics = mcp_metrics_data

    # Prepare metadata for telemetry
    trace_metadata: Dict[str, Any] = {}
    trace_metadata["events"] = [e.model_dump() for e in events]
    if evaluation_result:
        trace_metadata["evaluation"] = evaluation_result
    if mcp_metrics_data:
        trace_metadata["mcp_metrics"] = mcp_metrics_data

    telemetry.record_trace(
        trace_id=trace_id,
        conversation_id=conversation_id,
        agent=current_agent.name,
        user_message=req.message,
        assistant_messages=[m.model_dump() for m in messages],
        guardrails=[g.model_dump() for g in final_guardrails],
        metadata=trace_metadata,
        evaluation=evaluation_result,  # Explicitly pass evaluation
    )

    # ===================================================================================
    # Update and end Langfuse trace with agent response and metadata (v3 API)
    # ===================================================================================
    # Langfuse Trace Update (Lazy update for ID based traces)
    # ===================================================================================

    # Calculate token usage from Runner result
    total_input = 0
    total_output = 0
    total_count = 0

    if result and hasattr(result, "raw_responses"):
        for response in result.raw_responses:
            if hasattr(response, "usage"):
                usage = response.usage
                total_input += getattr(usage, "input_tokens", 0) or 0
                total_output += getattr(usage, "output_tokens", 0) or 0
                total_count += getattr(usage, "total_tokens", 0) or 0

    if LANGFUSE_ENABLED and langfuse_client:
        try:
            # Update and close the span if it exists
            if langfuse_span:
                # Update output if we have messages
                if messages:
                    langfuse_span.update(output=messages[-1].content)

                # Update usage stats
                langfuse_span.update(
                    usage={
                        "input": total_input,
                        "output": total_output,
                        "total": total_count,
                        "unit": "TOKENS",
                    }
                )

                # End the span to finish the trace duration
                langfuse_span.end()

            # Just flush the client to ensure any background events/scores are sent.
            langfuse_client.flush()
        except Exception as e:
            logger.warning(f"Failed to update/flush langfuse client: {e}")

    # return response for frontend
    return ChatResponse(
        conversation_id=conversation_id,
        current_agent=current_agent.name,
        messages=messages,
        events=events,
        context=state["context"].model_dump(),
        agents=_build_agents_list(),
        guardrails=final_guardrails,
        trace_id=trace_id,
        evaluation=evaluation_result,
        mcp_metrics=mcp_metrics_data,
    )


@app.post("/api/feedback")
async def feedback_endpoint(req: FeedbackRequest):
    """Collect user feedback from the UI and optionally forward to Langfuse."""
    if (
        req.score is None
        and req.rating is None
        and not (req.comment and req.comment.strip())
    ):
        raise HTTPException(
            status_code=400, detail="Feedback must include a score, rating, or comment"
        )
    if req.score is not None and (req.score < 0 or req.score > 1):
        raise HTTPException(status_code=400, detail="Score must be between 0 and 1")
    if req.rating is not None and req.rating not in range(1, 6):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    comment = req.comment.strip() if req.comment else None

    state = conversation_store.get(req.conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    entry = {
        "message_id": req.message_id,
        "trace_id": req.trace_id,
        "score": req.score,
        "rating": req.rating,
        "comment": comment,
        "timestamp": time.time() * 1000,
    }
    state.setdefault("feedback", []).append(entry)
    conversation_store.save(req.conversation_id, state)

    sent_results = []
    if req.score is not None:
        sent_results.append(
            telemetry.submit_feedback(
                trace_id=req.trace_id,
                score=req.score,
                comment=comment,
                metadata={
                    "conversation_id": req.conversation_id,
                    "message_id": req.message_id,
                    "feedback_type": "binary",
                },
                score_name="user-feedback",
            )
        )
    if req.rating is not None:
        sent_results.append(
            telemetry.submit_feedback(
                trace_id=req.trace_id,
                score=float(req.rating),
                comment=comment,
                metadata={
                    "conversation_id": req.conversation_id,
                    "message_id": req.message_id,
                    "feedback_type": "rating",
                    "rating": req.rating,
                },
                score_name="user-rating",
            )
        )
    if req.score is None and req.rating is None and comment:
        sent_results.append(
            telemetry.submit_feedback(
                trace_id=req.trace_id,
                score=None,
                comment=comment,
                metadata={
                    "conversation_id": req.conversation_id,
                    "message_id": req.message_id,
                    "feedback_type": "comment",
                },
                score_name="user-comment",
            )
        )

    return {"status": "ok", "sent_to_langfuse": any(sent_results)}


@app.get("/api/seatmap", response_model=SeatMapResponse)
async def seatmap_endpoint(conversation_id: str):
    """Return a data-driven seat map for the current conversation's flight."""
    state = conversation_store.get(conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    ctx = state.get("context")
    flight_number = getattr(ctx, "flight_number", None) if ctx is not None else None
    if not flight_number and isinstance(ctx, dict):
        flight_number = ctx.get("flight_number")
    if not flight_number:
        raise HTTPException(
            status_code=400, detail="No flight number available in conversation context"
        )

    seat_layout = get_seats_by_flight(str(flight_number))
    if not seat_layout:
        raise HTTPException(
            status_code=404, detail=f"Seat map not available for flight {flight_number}"
        )

    reserved = seat_assignment_store.occupied_seats(flight_number=str(flight_number))

    def _seat_sort_key(seat: str):
        row_str = "".join(ch for ch in seat if ch.isdigit())
        letter = "".join(ch for ch in seat if ch.isalpha())
        try:
            row = int(row_str) if row_str else 0
        except Exception:
            row = 0
        return (row, letter)

    sections: Dict[str, SeatMapSection] = {}
    for cabin in ("business", "economy"):
        cabin_data = seat_layout.get(cabin, {}) if isinstance(seat_layout, dict) else {}
        base_occupied = set(cabin_data.get("occupied", []) or [])
        all_occupied = sorted(base_occupied | reserved, key=_seat_sort_key)
        sections[cabin] = SeatMapSection(
            rows=cabin_data.get("rows", []) or [],
            seats_per_row=cabin_data.get("seats_per_row", []) or [],
            occupied=all_occupied,
            exit_rows=cabin_data.get("exit_rows", []) or [],
            premium=cabin_data.get("premium", []) or [],
        )

    current_seat = getattr(ctx, "seat_number", None) if ctx is not None else None
    if not current_seat and isinstance(ctx, dict):
        current_seat = ctx.get("seat_number")

    return SeatMapResponse(
        conversation_id=conversation_id,
        flight_number=str(flight_number),
        aircraft=seat_layout.get("aircraft") if isinstance(seat_layout, dict) else None,
        sections=sections,
        current_seat=current_seat,
    )


dist = files("agents_demo").joinpath("ui").joinpath("out")

app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
