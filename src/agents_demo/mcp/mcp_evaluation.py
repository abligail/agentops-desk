"""
MCP Server implementation for Agent Evaluation
Creates MCP servers from agents for tool call observation and evaluation
"""

from __future__ import annotations

import logging
import asyncio
import time
import json
from typing import Any, Optional, Dict, List

# Standard MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from agents.tool import FunctionTool
from agents.tool_context import ToolContext

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

        logger.info(f"Processing tool call: {tool_name} with trace_id={trace_id}")

        if trace_id:
            self.tracker.start_trace(trace_id, self.agent_name)

        start_time = time.time()

        try:
            tool_obj = self.tools_mapping[tool_name]["function"]
            args = arguments or {}

            # Handle FunctionTool instances (which require ToolContext and JSON string input)
            if isinstance(tool_obj, FunctionTool):
                # Import context classes dynamically to avoid circular imports
                try:
                    from agents_demo.agents.main import create_initial_context
                except ImportError:
                    logger.warning(
                        "Could not import agents context classes, using placeholders"
                    )
                    create_initial_context = lambda: None  # type: ignore

                # Create a valid context for the tools
                # Real agents use AirlineAgentContext, so we create a mock one here
                # to prevent tools from crashing when accessing context properties
                agent_context = create_initial_context()

                # Mock the RunContextWrapper structure that tools expect
                # Tools often access context.context.some_field, so we need a structure
                # that has a 'context' attribute which holds the actual data
                class MockRunContextWrapper:
                    def __init__(self, context_data):
                        self.context = context_data

                mock_context_wrapper = MockRunContextWrapper(agent_context)

                # FunctionTool expects input as a JSON string
                # We need to ensure args are serializable
                try:
                    input_str = json.dumps(args)
                except Exception:
                    input_str = str(args)

                # Create the ToolContext with our mock wrapper
                # We do not pass llm/agent as they are not part of the constructor
                # We need to provide tool_name, tool_call_id and tool_arguments as required by ToolContext
                ctx = ToolContext(
                    context=mock_context_wrapper,
                    tool_name=tool_name,
                    tool_call_id=f"call_{trace_id or 'unknown'}",
                    tool_arguments=input_str,
                )

                # Invoke the tool
                # on_invoke_tool signature: (ctx: ToolContext[Context], input: str) -> str
                result = await tool_obj.on_invoke_tool(ctx, input_str)

            else:
                # Assume standard callable (function/method)
                result = await tool_obj(**args)

            execution_time = time.time() - start_time

            self.tracker.log_function_call(
                function_name=tool_name,
                arguments=args,
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
                arguments=arguments or {},
                result=str(e),
                success=False,
                execution_time=execution_time,
            )
            logger.error(f"Tool {tool_name} failed: {e}")
            return f"Error: {str(e)}"
        finally:
            if trace_id:
                self.tracker.end_trace()

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
                        inputSchema={
                            "type": "object",
                            "properties": {},  # Simplified schema for now
                        },
                    )
                )
            return tools

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[TextContent]:
            """Handle tool calls"""
            trace_id = f"mcp_trace_{int(time.time() * 1000)}"
            result = await self.call_tool_with_tracking(
                name, arguments, trace_id=trace_id
            )
            return [TextContent(type="text", text=result)]

    async def run_server(self):
        """Run the MCP server"""
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

    def wrap_agent(self, agent: Any) -> Any:
        """
        Wrap an agent to track its function calls using this evaluator's tracker.
        Modifies the agent's tools in-place.
        """
        wrapper = AgentFunctionWrapper(
            agent, tracker=self.tracker, langfuse_client=self.langfuse
        )
        return wrapper.get_wrapped_agent()

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
                "average_execution_time": 0.0,
                "evaluation": "No function calls found",
                "function_usage": {},
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
        # Type check to satisfy linter
        client = self.langfuse
        if not client:
            return

        try:
            # Helper to safely create scores
            if hasattr(client, "score"):
                score_func = getattr(client, "score")
            elif hasattr(client, "create_score"):
                score_func = getattr(client, "create_score")
            else:
                logger.warning("Langfuse client has no score/create_score method")
                return

            def safe_create_score(**kwargs):
                score_func(**kwargs)

            safe_create_score(
                trace_id=trace_id,
                name="mcp_function_call_success_rate",
                value=float(evaluation["success_rate"]),
                data_type="NUMERIC",
                comment=f"Function call success rate for agent {evaluation['agent_name']}",
            )

            safe_create_score(
                trace_id=trace_id,
                name="mcp_total_function_calls",
                value=float(evaluation["total_calls"]),
                data_type="NUMERIC",
                comment=f"Total function calls for agent {evaluation['agent_name']}",
            )

            safe_create_score(
                trace_id=trace_id,
                name="mcp_avg_execution_time",
                value=float(evaluation["average_execution_time"]),
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
    try:
        from agents_demo.agents.main import (
            seat_booking_agent,
            flight_status_agent,
            faq_agent,
            AirlineAgentContext,
        )
    except ImportError:
        logger.error("Could not import agents for example")
        return

    logger.info("Starting MCP Evaluation Example")

    evaluator = create_mcp_evaluator()

    for agent in [seat_booking_agent, flight_status_agent, faq_agent]:
        if hasattr(agent, "tools") and agent.tools:
            evaluator.create_mcp_server_for_agent(agent.name, agent.tools)
            logger.info(f"Created MCP server for agent: {agent.name}")

    # Explicitly simulate a tool call to verify the loop
    if "Flight Status Agent" in evaluator.mcp_servers:
        server = evaluator.mcp_servers["Flight Status Agent"]

        tool_name = "flight_status_tool"
        if tool_name in server.tools_mapping:
            logger.info(f"Simulating call to {tool_name} for verification...")

            trace_id = "example_run_trace_002"

            # Use valid args for this tool
            args = {"flight_number": "UA123"}

            await server.call_tool_with_tracking(tool_name, args, trace_id=trace_id)

            # Now evaluate
            report = await evaluator.evaluate_agent_trace(
                trace_id, "Flight Status Agent"
            )
            logger.info(f"Verification Trace Report: {report}")

    logger.info("MCP servers created successfully")
    logger.info(f"Evaluation Report:\n{evaluator.export_evaluation_report()}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_mcp_evaluation_example())
