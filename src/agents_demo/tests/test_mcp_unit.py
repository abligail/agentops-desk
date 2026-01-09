import asyncio
import logging
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from agents_demo.mcp.mcp_server import (
    FunctionCallTracker,
    track_function_call,
    AgentFunctionWrapper,
    MultiAgentObserver,
)
from agents_demo.mcp.mcp_evaluation import (
    MCPEvaluationServer,
    AgentMCPEvaluator,
    create_mcp_evaluator,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Test Data & Mocks ---


class MockAgent:
    def __init__(self, name="MockAgent"):
        self.name = name
        self.tools = []


class MockTool:
    def __init__(self, name="mock_tool"):
        self.name = name
        self.__name__ = name
        self.description = "A mock tool"

    async def __call__(self, *args, **kwargs):
        return "mock_result"


# --- Tests for FunctionCallTracker ---


def test_tracker_initialization():
    tracker = FunctionCallTracker()
    assert tracker.call_history == []
    assert tracker.current_trace_id is None
    assert tracker.current_agent_name is None


def test_tracker_logging():
    tracker = FunctionCallTracker()
    tracker.start_trace("trace_123", "TestAgent")

    tracker.log_function_call(
        function_name="test_func",
        arguments={"arg": 1},
        result="success",
        success=True,
        execution_time=0.5,
    )

    assert len(tracker.call_history) == 1
    call = tracker.call_history[0]
    assert call["trace_id"] == "trace_123"
    assert call["agent_name"] == "TestAgent"
    assert call["function_name"] == "test_func"
    assert call["success"] is True
    assert call["execution_time"] == 0.5


def test_tracker_statistics():
    tracker = FunctionCallTracker()
    tracker.start_trace("trace_1", "Agent1")

    # Log 2 successful calls and 1 failed call
    tracker.log_function_call("func1", {}, "ok", True, 0.1)
    tracker.log_function_call("func1", {}, "ok", True, 0.2)
    tracker.log_function_call("func2", {}, "error", False, 0.3)

    stats = tracker.get_statistics()

    assert stats["total_calls"] == 3
    assert stats["successful_calls"] == 2
    assert stats["failed_calls"] == 1
    assert stats["success_rate"] == 2 / 3
    assert stats["average_execution_time"] == pytest.approx((0.1 + 0.2 + 0.3) / 3)
    assert stats["function_usage"] == {"func1": 2, "func2": 1}


# --- Tests for Decorator ---


@pytest.mark.asyncio
async def test_track_function_call_decorator():
    tracker = FunctionCallTracker()
    tracker.start_trace("trace_dec", "DecAgent")

    @track_function_call(tracker)
    async def sample_tool(x: int):
        return x * 2

    result = await sample_tool(5)
    assert result == 10

    assert len(tracker.call_history) == 1
    assert tracker.call_history[0]["function_name"] == "sample_tool"
    assert tracker.call_history[0]["result"] == "10"
    assert tracker.call_history[0]["success"] is True


@pytest.mark.asyncio
async def test_track_function_call_error():
    tracker = FunctionCallTracker()
    tracker.start_trace("trace_err", "ErrAgent")

    @track_function_call(tracker)
    async def failing_tool():
        raise ValueError("Oops")

    with pytest.raises(ValueError):
        await failing_tool()

    assert len(tracker.call_history) == 1
    assert tracker.call_history[0]["success"] is False
    assert "Oops" in tracker.call_history[0]["result"]


# --- Tests for AgentWrapper ---


def test_agent_wrapper_wrap_tools():
    agent = MockAgent()
    tool = MockTool("my_tool")
    agent.tools = [tool]

    wrapper = AgentFunctionWrapper(agent)
    wrapped_agent = wrapper.get_wrapped_agent()

    # Check if tools are wrapped (different objects now)
    assert len(wrapped_agent.tools) == 1
    assert wrapped_agent.tools[0] != tool

    # Check if we can still access wrapper map
    assert "my_tool" in wrapper._wrapped_tools


@pytest.mark.asyncio
async def test_agent_wrapper_execution():
    agent = MockAgent()
    tool = MockTool("my_tool")
    agent.tools = [tool]

    wrapper = AgentFunctionWrapper(agent)
    wrapped_agent = wrapper.get_wrapped_agent()

    # Manually trigger trace start
    wrapper.tracker.start_trace("wrapper_trace", "MockAgent")

    # Execute the wrapped tool
    await wrapped_agent.tools[0]()

    assert len(wrapper.tracker.call_history) == 1
    assert wrapper.tracker.call_history[0]["function_name"] == "my_tool"


# --- Tests for MCPEvaluationServer ---


@pytest.mark.asyncio
async def test_mcp_server_tool_tracking():
    tracker = FunctionCallTracker()
    server = MCPEvaluationServer("TestServer", tracker=tracker)

    async def sample_func(arg):
        return f"processed {arg}"

    server.register_tool("sample_func", sample_func)

    result = await server.call_tool_with_tracking("sample_func", {"arg": "data"})

    assert result == "processed data"
    assert len(tracker.call_history) == 1
    assert tracker.call_history[0]["function_name"] == "sample_func"


# --- Tests for Evaluator ---


@pytest.mark.asyncio
async def test_evaluator_workflow():
    evaluator = create_mcp_evaluator()

    # Simulate data
    evaluator.tracker.start_trace("eval_trace", "EvalAgent")
    evaluator.tracker.log_function_call("tool1", {}, "ok", True, 0.1)
    evaluator.tracker.end_trace()

    report = await evaluator.evaluate_agent_trace("eval_trace", "EvalAgent")

    assert report["total_calls"] == 1
    assert report["success_rate"] == 1.0
    assert report["agent_name"] == "EvalAgent"


def test_evaluator_export():
    evaluator = create_mcp_evaluator()
    evaluator.tracker.log_function_call("tool_a", {}, "ok", True, 0.1)

    report_text = evaluator.export_evaluation_report()

    assert "MCP Agent Function Call Evaluation Report" in report_text
    assert "Total Calls: 1" in report_text
    assert "tool_a" in report_text


if __name__ == "__main__":
    # If run directly, run pytest
    import sys

    sys.exit(pytest.main(["-v", __file__]))
