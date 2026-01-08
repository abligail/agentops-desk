"""
Agent Function Call Observation and Evaluation
Implements tool call tracking for agents using wrapper/decorator pattern
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Dict, List, Callable
from functools import wraps

from agents import Agent, RunContextWrapper

logger = logging.getLogger(__name__)


class FunctionCallTracker:
    """Track function/tool calls from agents for evaluation"""

    def __init__(self):
        self.call_history: List[Dict[str, Any]] = []
        self.current_trace_id: Optional[str] = None
        self.current_agent_name: Optional[str] = None

    def start_trace(self, trace_id: str, agent_name: str):
        """Start a new trace"""
        self.current_trace_id = trace_id
        self.current_agent_name = agent_name
        logger.info(f"Starting trace {trace_id} for agent {agent_name}")

    def end_trace(self):
        """End current trace"""
        logger.info(f"Ending trace {self.current_trace_id}")
        self.current_trace_id = None
        self.current_agent_name = None

    def log_function_call(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        result: str,
        success: bool,
        execution_time: float,
    ):
        """Log a function call"""
        call_record = {
            "trace_id": self.current_trace_id,
            "agent_name": self.current_agent_name,
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
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = getattr(func, "name", func.__name__)

            try:
                result = await func(*args, **kwargs)
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
            tool_name = getattr(tool, "name", tool.__name__)
            self._wrapped_tools[tool_name] = track_function_call(self.tracker)(tool)

    def get_wrapped_agent(self) -> Agent:
        """Get the agent with wrapped tools"""
        self.wrap_tools()

        if hasattr(self.agent, "tools") and self.agent.tools:
            tool_list = list(self.agent.tools)
            self.agent.tools.clear()

            for tool in tool_list:
                tool_name = getattr(tool, "name", tool.__name__)
                if tool_name in self._wrapped_tools:
                    self.agent.tools.append(self._wrapped_tools[tool_name])

        return self.agent

    async def run_with_tracking(
        self,
        input: str,
        trace_id: Optional[str] = None,
        run_config=None,
    ):
        """Run the agent with tracking enabled"""
        if trace_id is None:
            trace_id = f"trace_{int(time.time() * 1000)}"

        self.tracker.start_trace(trace_id, self.agent.name)

        try:
            from agents import Runner

            wrapped_agent = self.get_wrapped_agent()

            if run_config:
                result = await Runner.run(wrapped_agent, input, run_config=run_config)
            else:
                result = await Runner.run(wrapped_agent, input)

            return result, trace_id
        finally:
            self.tracker.end_trace()
            if self.langfuse:
                await self._submit_to_langfuse(trace_id)

    async def _submit_to_langfuse(self, trace_id: str):
        """Submit tracking data to Langfuse"""
        if not self.langfuse:
            return

        try:
            stats = self.tracker.get_statistics()

            self.langfuse.create_score(
                trace_id=trace_id,
                name="function_call_success_rate",
                value=stats["success_rate"],
                data_type="NUMERIC",
                comment=f"Function call success rate for agent {self.agent.name}",
            )

            self.langfuse.create_score(
                trace_id=trace_id,
                name="function_call_count",
                value=stats["total_calls"],
                data_type="NUMERIC",
                comment=f"Total function calls for agent {self.agent.name}",
            )

            self.langfuse.create_score(
                trace_id=trace_id,
                name="average_function_call_time",
                value=stats["average_execution_time"],
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
        wrapper = AgentFunctionWrapper(agent, langfuse_client=self.langfuse)
        self.wrappers[agent.name] = wrapper
        return wrapper.get_wrapped_agent()

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
