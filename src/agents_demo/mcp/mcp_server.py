"""
Agent Function Call Observation and Evaluation
Implements tool call tracking for agents using wrapper/decorator pattern
"""

from __future__ import annotations

import json
import logging
import time
import copy
import contextvars
from typing import Any, Optional, Dict, List, Callable, Union, cast
from functools import wraps

from agents import Agent, RunContextWrapper
from agents.tool import FunctionTool
from agents.tool_context import ToolContext

logger = logging.getLogger(__name__)

# Context variables for tracking trace ID and agent name in async execution
_current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_trace_id", default=None
)
_current_agent_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_agent_name", default=None
)


class FunctionCallTracker:
    """Track function/tool calls from agents for evaluation"""

    def __init__(self):
        self.call_history: List[Dict[str, Any]] = []

    def start_trace(self, trace_id: str, agent_name: str):
        """Start a new trace"""
        _current_trace_id.set(trace_id)
        _current_agent_name.set(agent_name)
        logger.info(f"Starting trace {trace_id} for agent {agent_name}")

    def end_trace(self):
        """End current trace"""
        trace_id = _current_trace_id.get()
        if trace_id:
            logger.info(f"Ending trace {trace_id}")
        _current_trace_id.set(None)
        _current_agent_name.set(None)

    def log_function_call(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        result: str,
        success: bool,
        execution_time: float,
    ):
        """Log a function call"""
        trace_id = _current_trace_id.get()
        agent_name = _current_agent_name.get()

        call_record = {
            "trace_id": trace_id,
            "agent_name": agent_name,
            "function_name": function_name,
            "arguments": arguments,
            "result": result,
            "success": success,
            "execution_time": execution_time,
            "timestamp": time.time(),
        }
        self.call_history.append(call_record)
        logger.info(f"Logged function call: {function_name}")

    def get_calls_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all calls for a specific trace"""
        return [call for call in self.call_history if call["trace_id"] == trace_id]

    def get_calls_by_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all calls for a specific agent"""
        return [call for call in self.call_history if call["agent_name"] == agent_name]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about function calls"""
        total_calls = len(self.call_history)
        successful_calls = sum(1 for call in self.call_history if call["success"])
        failed_calls = total_calls - successful_calls

        avg_execution_time = (
            sum(call["execution_time"] for call in self.call_history) / total_calls
            if total_calls > 0
            else 0
        )

        function_usage: Dict[str, int] = {}
        for call in self.call_history:
            func_name = call["function_name"]
            function_usage[func_name] = function_usage.get(func_name, 0) + 1

        agent_usage: Dict[str, int] = {}
        for call in self.call_history:
            agent_name = call["agent_name"]
            if agent_name:
                agent_usage[agent_name] = agent_usage.get(agent_name, 0) + 1

        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate": successful_calls / total_calls if total_calls > 0 else 0,
            "average_execution_time": avg_execution_time,
            "function_usage": function_usage,
            "agent_usage": agent_usage,
        }


def track_function_call(tracker: FunctionCallTracker):
    """Decorator to track function calls"""

    def decorator(func: Callable):
        # We need to access the underlying function if it's a FunctionTool
        original_func = func

        # Check if it's a FunctionTool instance
        is_function_tool = hasattr(func, "name") and hasattr(func, "description")

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            # Use getattr to safely handle objects that might not have __name__
            function_name = getattr(
                original_func,
                "name",
                getattr(original_func, "__name__", str(original_func)),
            )

            try:
                # If it's a FunctionTool, we call it directly as it's callable
                result = await original_func(*args, **kwargs)
                execution_time = time.time() - start_time
                tracker.log_function_call(
                    function_name=function_name,
                    arguments=kwargs,
                    result=str(result),
                    success=True,
                    execution_time=execution_time,
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                tracker.log_function_call(
                    function_name=function_name,
                    arguments=kwargs,
                    result=str(e),
                    success=False,
                    execution_time=execution_time,
                )
                raise

        return async_wrapper

    return decorator


# Helper to identify if an object is a tool
def is_tool(obj: Any) -> bool:
    return hasattr(obj, "name") and hasattr(obj, "description")


class TrackedTool:
    """Proxy class to wrap a tool and track its calls"""

    def __init__(self, tool: Any, tracker: FunctionCallTracker):
        self._tool = tool
        self._tracker = tracker

    def __getattr__(self, name):
        return getattr(self._tool, name)

    async def __call__(self, *args, **kwargs):
        start_time = time.time()
        function_name = getattr(self._tool, "name", str(self._tool))

        try:
            result = await self._tool(*args, **kwargs)
            execution_time = time.time() - start_time
            self._tracker.log_function_call(
                function_name=function_name,
                arguments=kwargs,
                result=str(result),
                success=True,
                execution_time=execution_time,
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            self._tracker.log_function_call(
                function_name=function_name,
                arguments=kwargs,
                result=str(e),
                success=False,
                execution_time=execution_time,
            )
            raise


class AgentFunctionWrapper:
    """Wrapper for agents to enable function call tracking"""

    def __init__(
        self,
        agent: Agent,
        tracker: Optional[FunctionCallTracker] = None,
        langfuse_client=None,
    ):
        self.agent = agent
        self.tracker = tracker or FunctionCallTracker()
        self.langfuse = langfuse_client
        self._wrapped_tools = {}

    def wrap_tools(self):
        """Wrap all tools of the agent with tracking"""
        if not hasattr(self.agent, "tools") or not self.agent.tools:
            logger.warning(f"Agent {self.agent.name} has no tools to wrap")
            return

        for tool in self.agent.tools:
            # Handle both FunctionTool objects and raw functions
            tool_name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))

            # Use different wrapping strategy based on tool type
            if isinstance(tool, FunctionTool):
                # For FunctionTool, we need to wrap the invoke callback
                original_invoke = tool.on_invoke_tool

                async def wrapped_invoke(ctx: ToolContext[Any], input_str: str) -> Any:
                    start_time = time.time()
                    try:
                        # Parse input for logging if possible
                        try:
                            args = json.loads(input_str) if input_str else {}
                        except:
                            args = {"raw_input": input_str}

                        result = await original_invoke(ctx, input_str)

                        execution_time = time.time() - start_time
                        self.tracker.log_function_call(
                            function_name=tool_name,
                            arguments=args,
                            result=str(result),
                            success=True,
                            execution_time=execution_time,
                        )
                        return result
                    except Exception as e:
                        execution_time = time.time() - start_time
                        try:
                            args = json.loads(input_str) if input_str else {}
                        except:
                            args = {"raw_input": input_str}

                        self.tracker.log_function_call(
                            function_name=tool_name,
                            arguments=args,
                            result=str(e),
                            success=False,
                            execution_time=execution_time,
                        )
                        raise

                # Replace the invoke method on the tool instance
                # This modifies the tool in place!
                tool.on_invoke_tool = wrapped_invoke

                # Register as processed
                self._wrapped_tools[tool_name] = tool

            elif is_tool(tool):
                # Other tool types that might not be FunctionTool but look like tools
                self._wrapped_tools[tool_name] = TrackedTool(tool, self.tracker)
            else:
                # Raw functions - use cast to avoid type errors
                self._wrapped_tools[tool_name] = track_function_call(self.tracker)(
                    cast(Callable, tool)
                )

    def get_wrapped_agent(self) -> Agent:
        """Get the agent with wrapped tools"""
        self.wrap_tools()

        if hasattr(self.agent, "tools") and self.agent.tools:
            # Check if we need to replace any tools (non-FunctionTool ones that were wrapped)
            new_tools = []
            for tool in self.agent.tools:
                if isinstance(tool, FunctionTool):
                    new_tools.append(tool)  # Already modified in place
                else:
                    # Logic to find the name
                    tool_name = getattr(
                        tool, "name", getattr(tool, "__name__", str(tool))
                    )

                    if tool_name in self._wrapped_tools:
                        new_tools.append(self._wrapped_tools[tool_name])
                    else:
                        new_tools.append(tool)

            self.agent.tools = new_tools

        return self.agent

    async def run_with_tracking(
        self,
        input: Union[str, List[Any]],
        trace_id: Optional[str] = None,
        run_config=None,
        context: Optional[Any] = None,
    ):
        """Run the agent with tracking enabled"""
        if trace_id is None:
            trace_id = f"trace_{int(time.time() * 1000)}"

        self.tracker.start_trace(trace_id, self.agent.name)

        try:
            from agents import Runner

            wrapped_agent = self.get_wrapped_agent()

            # Handle different input types and arguments compatible with Runner.run
            kwargs = {}
            if run_config:
                kwargs["run_config"] = run_config
            if context:
                kwargs["context"] = context

            result = await Runner.run(wrapped_agent, input, **kwargs)

            return result, trace_id
        finally:
            self.tracker.end_trace()
            if self.langfuse:
                await self._submit_to_langfuse(trace_id)

    async def _submit_to_langfuse(self, trace_id: str):
        """Submit tracking data to Langfuse"""
        # Type check to satisfy linter
        client = self.langfuse
        if not client:
            return

        try:
            stats = self.tracker.get_statistics()

            # Helper to safely create scores
            # Use getattr to bypass static type checking on optional self.langfuse
            if hasattr(client, "score"):
                score_func = getattr(client, "score")
            elif hasattr(client, "create_score"):
                score_func = getattr(client, "create_score")
            else:
                logger.warning("Langfuse client has no score/create_score method")
                return

            def safe_create_score(**kwargs):
                score_func(**kwargs)

            # Important: Use numeric values for numeric scores to ensure they appear in charts

            # 1. Success Rate (0-1)
            safe_create_score(
                trace_id=trace_id,
                name="mcp_function_call_success_rate",
                value=float(stats["success_rate"]),
                data_type="NUMERIC",
                comment=f"Function call success rate for agent {self.agent.name}",
            )

            # 2. Total Calls (Integer)
            safe_create_score(
                trace_id=trace_id,
                name="mcp_function_call_count",
                value=float(stats["total_calls"]),
                data_type="NUMERIC",
                comment=f"Total function calls for agent {self.agent.name}",
            )

            # 3. Average Execution Time (Seconds)
            safe_create_score(
                trace_id=trace_id,
                name="mcp_average_function_call_time",
                value=float(stats["average_execution_time"]),
                data_type="NUMERIC",
                comment=f"Average function call execution time for agent {self.agent.name}",
            )

            logger.info(
                f"Submitted function call metrics to Langfuse for trace {trace_id}"
            )
        except Exception as e:
            logger.error(f"Failed to submit to Langfuse: {e}")

    def get_evaluation_data(self) -> Dict[str, Any]:
        """Get data for evaluation"""
        return {
            "call_history": self.tracker.call_history,
            "statistics": self.tracker.get_statistics(),
        }


class MultiAgentObserver:
    """Observer for multiple agents"""

    def __init__(self, langfuse_client=None):
        self.wrappers: Dict[str, AgentFunctionWrapper] = {}
        self.langfuse = langfuse_client

    def wrap_agent(self, agent: Agent) -> Agent:
        """Wrap an agent for observation"""
        if agent.name in self.wrappers:
            return self.wrappers[agent.name].get_wrapped_agent()

        wrapper = AgentFunctionWrapper(agent, langfuse_client=self.langfuse)
        self.wrappers[agent.name] = wrapper
        return wrapper.get_wrapped_agent()

    def get_wrapper(self, agent: Agent) -> AgentFunctionWrapper:
        """Get or create a wrapper for the agent"""
        if agent.name not in self.wrappers:
            self.wrap_agent(agent)
        return self.wrappers[agent.name]

    async def run_agent(
        self,
        agent_name: str,
        input: str,
        trace_id: Optional[str] = None,
        run_config=None,
    ):
        """Run a specific agent with tracking"""
        if agent_name not in self.wrappers:
            raise ValueError(f"Agent {agent_name} not found in wrappers")

        return await self.wrappers[agent_name].run_with_tracking(
            input, trace_id=trace_id, run_config=run_config
        )

    def get_global_statistics(self) -> Dict[str, Any]:
        """Get statistics across all agents"""
        all_stats = {
            "total_agents": len(self.wrappers),
            "agent_statistics": {},
            "global_function_usage": {},
        }

        for agent_name, wrapper in self.wrappers.items():
            stats = wrapper.tracker.get_statistics()
            all_stats["agent_statistics"][agent_name] = stats

            for func_name, count in stats["function_usage"].items():
                all_stats["global_function_usage"][func_name] = (
                    all_stats["global_function_usage"].get(func_name, 0) + count
                )

        return all_stats

    def export_evaluation_report(self) -> str:
        """Export a formatted evaluation report"""
        report = []
        stats = self.get_global_statistics()

        report.append("=== Agent Function Call Evaluation Report ===\n")
        report.append(f"Total Agents: {stats['total_agents']}\n")
        report.append("\n")

        for agent_name, agent_stats in stats["agent_statistics"].items():
            report.append(f"--- Agent: {agent_name} ---")
            report.append(f"Total Calls: {agent_stats['total_calls']}")
            report.append(f"Success Rate: {agent_stats['success_rate']:.2%}")
            report.append(
                f"Avg Execution Time: {agent_stats['average_execution_time']:.4f}s"
            )
            report.append(
                f"Functions Used: {', '.join(agent_stats['function_usage'].keys())}"
            )
            report.append("\n")

        return "\n".join(report)


def create_agent_wrapper(agent: Agent, langfuse_client=None) -> Agent:
    """
    Convenience function to create a wrapped agent

    Args:
        agent: The agent to wrap
        langfuse_client: Optional Langfuse client for metrics submission

    Returns:
        The wrapped agent with tracking enabled
    """
    wrapper = AgentFunctionWrapper(agent, langfuse_client=langfuse_client)
    return wrapper.get_wrapped_agent()


def create_multi_agent_observer(langfuse_client=None) -> MultiAgentObserver:
    """
    Convenience function to create a multi-agent observer

    Args:
        langfuse_client: Optional Langfuse client for metrics submission

    Returns:
        MultiAgentObserver instance
    """
    return MultiAgentObserver(langfuse_client=langfuse_client)
