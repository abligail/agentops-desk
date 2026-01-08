"""
MCP Server implementation for Agent Evaluation
Creates MCP servers from agents for tool call observation and evaluation
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Dict, List

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning(
        "MCP package not available. MCP server functionality will be limited."
    )

from .mcp_server import (
    FunctionCallTracker,
    AgentFunctionWrapper,
    MultiAgentObserver,
)

logger = logging.getLogger(__name__)


class MCPEvaluationServer:
    """MCP Server for evaluating agent function calls"""

    def __init__(
        self,
        agent_name: str,
        tracker: Optional[FunctionCallTracker] = None,
        langfuse_client=None,
    ):
        if not MCP_AVAILABLE:
            logger.warning("MCP package not available, creating mock server")
            self.server = None
        else:
            self.server = Server(f"{agent_name}_mcp_evaluation")

        self.agent_name = agent_name
        self.tracker = tracker or FunctionCallTracker()
        self.langfuse = langfuse_client
        self.tools_mapping: Dict[str, Any] = {}

    def register_tool(self, tool_name: str, tool_func: Any, description: str = ""):
        """Register a tool for MCP server"""
        self.tools_mapping[tool_name] = {
            "function": tool_func,
            "description": description,
        }
        logger.info(f"Registered tool: {tool_name}")

    async def call_tool_with_tracking(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> str:
        """Call a tool and track the invocation"""
        if tool_name not in self.tools_mapping:
            error_msg = f"Tool {tool_name} not found"
            logger.error(error_msg)
            return error_msg

        import time

        start_time = time.time()

        try:
            tool_func = self.tools_mapping[tool_name]["function"]
            result = await tool_func(**arguments)
            execution_time = time.time() - start_time

            self.tracker.log_function_call(
                function_name=tool_name,
                arguments=arguments,
                result=str(result),
                success=True,
                execution_time=execution_time,
            )

            logger.info(
                f"Tool {tool_name} called successfully in {execution_time:.4f}s"
            )
            return str(result)

        except Exception as e:
            execution_time = time.time() - start_time
            self.tracker.log_function_call(
                function_name=tool_name,
                arguments=arguments,
                result=str(e),
                success=False,
                execution_time=execution_time,
            )
            logger.error(f"Tool {tool_name} failed: {e}")
            return f"Error: {str(e)}"

    def setup_mcp_handlers(self):
        """Setup MCP server handlers"""
        if not self.server:
            return

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools"""
            tools = []
            for tool_name, tool_info in self.tools_mapping.items():
                tools.append(
                    Tool(
                        name=tool_name,
                        description=tool_info["description"],
                    )
                )
            return tools

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[TextContent]:
            """Handle tool calls"""
            result = await self.call_tool_with_tracking(name, arguments)
            return [TextContent(type="text", text=result)]

    async def run_server(self):
        """Run the MCP server"""
        if not self.server:
            logger.warning("MCP server not available, running in mock mode")
            return

        self.setup_mcp_handlers()

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


class AgentMCPEvaluator:
    """Evaluator for agent function calls using MCP pattern"""

    def __init__(self, langfuse_client=None):
        self.tracker = FunctionCallTracker()
        self.langfuse = langfuse_client
        self.mcp_servers: Dict[str, MCPEvaluationServer] = {}

    def create_mcp_server_for_agent(
        self,
        agent_name: str,
        tools: List[Any],
    ) -> MCPEvaluationServer:
        """Create an MCP server for an agent's tools"""
        mcp_server = MCPEvaluationServer(
            agent_name=agent_name,
            tracker=self.tracker,
            langfuse_client=self.langfuse,
        )

        for tool in tools:
            tool_name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))
            tool_description = getattr(
                tool,
                "description_override",
                getattr(tool, "__doc__", ""),
            )
            mcp_server.register_tool(tool_name, tool, tool_description)

        self.mcp_servers[agent_name] = mcp_server
        return mcp_server

    async def evaluate_agent_trace(
        self,
        trace_id: str,
        agent_name: str,
        evaluation_criteria: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate an agent trace based on function calls"""
        evaluation_criteria = evaluation_criteria or {}

        calls = self.tracker.get_calls_by_trace(trace_id)

        if not calls:
            return {
                "trace_id": trace_id,
                "agent_name": agent_name,
                "total_calls": 0,
                "success_rate": 0.0,
                "evaluation": "No function calls found",
            }

        total_calls = len(calls)
        successful_calls = sum(1 for call in calls if call["success"])
        success_rate = successful_calls / total_calls if total_calls > 0 else 0

        avg_execution_time = sum(call["execution_time"] for call in calls) / total_calls

        evaluation = {
            "trace_id": trace_id,
            "agent_name": agent_name,
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": total_calls - successful_calls,
            "success_rate": success_rate,
            "average_execution_time": avg_execution_time,
            "function_usage": {},
        }

        for call in calls:
            func_name = call["function_name"]
            if func_name not in evaluation["function_usage"]:
                evaluation["function_usage"][func_name] = {
                    "count": 0,
                    "success_rate": 0.0,
                    "avg_time": 0.0,
                }

            stats = evaluation["function_usage"][func_name]
            stats["count"] += 1

        for func_name in evaluation["function_usage"]:
            func_calls = [c for c in calls if c["function_name"] == func_name]
            stats = evaluation["function_usage"][func_name]
            stats["success_rate"] = sum(1 for c in func_calls if c["success"]) / len(
                func_calls
            )
            stats["avg_time"] = sum(c["execution_time"] for c in func_calls) / len(
                func_calls
            )

        if self.langfuse:
            await self._submit_evaluation_to_langfuse(trace_id, evaluation)

        return evaluation

    async def _submit_evaluation_to_langfuse(
        self,
        trace_id: str,
        evaluation: Dict[str, Any],
    ):
        """Submit evaluation results to Langfuse"""
        try:
            self.langfuse.create_score(
                trace_id=trace_id,
                name="mcp_function_call_success_rate",
                value=evaluation["success_rate"],
                data_type="NUMERIC",
                comment=f"Function call success rate for agent {evaluation['agent_name']}",
            )

            self.langfuse.create_score(
                trace_id=trace_id,
                name="mcp_total_function_calls",
                value=evaluation["total_calls"],
                data_type="NUMERIC",
                comment=f"Total function calls for agent {evaluation['agent_name']}",
            )

            self.langfuse.create_score(
                trace_id=trace_id,
                name="mcp_avg_execution_time",
                value=evaluation["average_execution_time"],
                data_type="NUMERIC",
                comment=f"Average function call execution time for agent {evaluation['agent_name']}",
            )

            logger.info(f"Submitted MCP evaluation to Langfuse for trace {trace_id}")
        except Exception as e:
            logger.error(f"Failed to submit MCP evaluation to Langfuse: {e}")

    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global statistics across all traces"""
        return self.tracker.get_statistics()

    def export_evaluation_report(self) -> str:
        """Export a formatted evaluation report"""
        stats = self.get_global_statistics()

        report_lines = [
            "=== MCP Agent Function Call Evaluation Report ===\n",
            f"Total Calls: {stats['total_calls']}",
            f"Successful Calls: {stats['successful_calls']}",
            f"Failed Calls: {stats['failed_calls']}",
            f"Success Rate: {stats['success_rate']:.2%}",
            f"Average Execution Time: {stats['average_execution_time']:.4f}s\n",
            "Function Usage:",
        ]

        for func_name, count in sorted(stats["function_usage"].items()):
            report_lines.append(f"  - {func_name}: {count} calls")

        report_lines.append("\nAgent Usage:")
        for agent_name, count in sorted(stats["agent_usage"].items()):
            report_lines.append(f"  - {agent_name}: {count} calls")

        return "\n".join(report_lines)


def create_mcp_evaluator(langfuse_client=None) -> AgentMCPEvaluator:
    """
    Convenience function to create an MCP evaluator

    Args:
        langfuse_client: Optional Langfuse client for metrics submission

    Returns:
        AgentMCPEvaluator instance
    """
    return AgentMCPEvaluator(langfuse_client=langfuse_client)


async def run_mcp_evaluation_example():
    """
    Example demonstrating how to use MCP evaluation with agents
    """
    from .main_qwen import qwen_model2, myRunConfig, OpenAIModel
    from .main import (
        seat_booking_agent,
        flight_status_agent,
        faq_agent,
    )

    logger.info("Starting MCP Evaluation Example")

    evaluator = create_mcp_evaluator()

    for agent in [seat_booking_agent, flight_status_agent, faq_agent]:
        if hasattr(agent, "tools") and agent.tools:
            evaluator.create_mcp_server_for_agent(agent.name, agent.tools)
            logger.info(f"Created MCP server for agent: {agent.name}")

    logger.info("MCP servers created successfully")
    logger.info(f"Evaluation Report:\n{evaluator.export_evaluation_report()}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_mcp_evaluation_example())
