import pytest
import asyncio
import logging
from typing import Any, Dict

# Configure logging to show info
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Mock classes to simulate Agent and Tool
class MockTool:
    def __init__(self, name: str):
        self.name = name
        self.description = f"Description for {name}"

    async def __call__(self, **kwargs):
        return f"Result from {self.name} with {kwargs}"


class MockAgent:
    def __init__(self, name: str):
        self.name = name
        self.tools = [MockTool("test_tool_1"), MockTool("test_tool_2")]


@pytest.mark.asyncio
async def test_mcp_evaluation():
    print("Starting MCP Verification...")

    try:
        from agents_demo.mcp.mcp_evaluation import (
            AgentMCPEvaluator,
            MCPEvaluationServer,
        )

        print("Successfully imported MCPEvaluationServer and AgentMCPEvaluator")
    except ImportError as e:
        print(f"Failed to import: {e}")
        return

    # 1. Initialize Evaluator
    evaluator = AgentMCPEvaluator()
    print("Initialized AgentMCPEvaluator")

    # 2. Create Mock Agent
    agent = MockAgent("mock_agent")

    # 3. Create MCP Server for Agent
    server = evaluator.create_mcp_server_for_agent(agent.name, agent.tools)
    print(f"Created MCP Server for {agent.name}")

    # 4. Verify Tools Registered
    if "test_tool_1" in server.tools_mapping:
        print("Tool 'test_tool_1' registered successfully")
    else:
        print("FAILED: Tool 'test_tool_1' not registered")
        return

    # 5. Simulate Tool Call Tracking
    print("Simulating tool call...")
    result = await server.call_tool_with_tracking(
        "test_tool_1", {"param": "value"}, trace_id="test_trace_123"
    )
    print(f"Tool call result: {result}")

    # 6. Evaluate Trace
    print("Evaluating trace...")
    evaluation = await evaluator.evaluate_agent_trace("test_trace_123", agent.name)

    print("\n--- Evaluation Result ---")
    print(f"Success Rate: {evaluation['success_rate']}")
    print(f"Total Calls: {evaluation['total_calls']}")

    if evaluation["total_calls"] == 1 and evaluation["success_rate"] == 1.0:
        print("\nSUCCESS: MCP Evaluation logic verified!")
    else:
        print("\nFAILED: Metrics do not match expected values.")


if __name__ == "__main__":
    asyncio.run(test_mcp_evaluation())
