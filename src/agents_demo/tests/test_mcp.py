#!/usr/bin/env python
"""
Simple test script for MCP evaluation functionality
"""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def test_basic_functionality():
    """Test basic MCP evaluation functionality"""
    logger.info("Testing basic MCP evaluation functionality...")

    from agents_demo.mcp_server import (
        FunctionCallTracker,
        track_function_call,
    )

    # Test FunctionCallTracker
    tracker = FunctionCallTracker()
    tracker.start_trace("test_trace_1", "TestAgent")

    # Simulate function calls
    tracker.log_function_call(
        function_name="test_function_1",
        arguments={"arg1": "value1"},
        result="success",
        success=True,
        execution_time=0.123,
    )

    tracker.log_function_call(
        function_name="test_function_2",
        arguments={"arg2": "value2"},
        result="error",
        success=False,
        execution_time=0.456,
    )

    tracker.end_trace()

    # Get statistics
    stats = tracker.get_statistics()

    logger.info(f"Total calls: {stats['total_calls']}")
    logger.info(f"Success rate: {stats['success_rate']:.2%}")
    logger.info(f"Avg execution time: {stats['average_execution_time']:.4f}s")
    logger.info(f"Function usage: {stats['function_usage']}")

    # Test getting calls by trace
    calls = tracker.get_calls_by_trace("test_trace_1")
    logger.info(f"Calls for trace_1: {len(calls)}")

    assert stats["total_calls"] == 2, "Expected 2 total calls"
    assert stats["successful_calls"] == 1, "Expected 1 successful call"
    assert stats["failed_calls"] == 1, "Expected 1 failed call"

    logger.info("✓ Basic functionality test passed!")


async def test_mcp_evaluator():
    """Test MCP evaluator"""
    logger.info("\nTesting MCP evaluator...")

    from agents_demo.mcp_evaluation import create_mcp_evaluator

    evaluator = create_mcp_evaluator()

    # Create mock tools
    async def mock_tool1(param1: str) -> str:
        return f"Mock tool 1 result: {param1}"

    async def mock_tool2(param2: int) -> str:
        return f"Mock tool 2 result: {param2 * 2}"

    # Register tools
    mcp_server = evaluator.create_mcp_server_for_agent(
        agent_name="MockAgent",
        tools=[
            type(
                "Tool",
                (),
                {
                    "name": "mock_tool1",
                    "description_override": "A mock tool for testing",
                },
            )(),
        ],
    )

    logger.info("Created MCP server for MockAgent")

    # Test evaluation
    evaluation = await evaluator.evaluate_agent_trace(
        trace_id="test_trace_2",
        agent_name="MockAgent",
    )

    logger.info(f"Evaluation: {evaluation}")

    # Get global statistics
    stats = evaluator.get_global_statistics()
    logger.info(f"Global stats: {stats}")

    # Export report
    report = evaluator.export_evaluation_report()
    logger.info(f"\nReport:\n{report}")

    logger.info("✓ MCP evaluator test passed!")


async def test_integration():
    """Test MCP integration"""
    logger.info("\nTesting MCP integration...")

    from agents_demo.mcp_integration import get_mcp_integration

    # Get singleton instance
    integration1 = get_mcp_integration()
    integration2 = get_mcp_integration()

    assert integration1 is integration2, "Expected same instance"

    logger.info("Singleton pattern working correctly")

    # Test initialization
    integration1.initialize()

    assert integration1.is_initialized(), "Expected initialized"

    logger.info("✓ Integration test passed!")


async def run_all_tests():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("Starting MCP Evaluation Tests")
    logger.info("=" * 60)

    try:
        await test_basic_functionality()
        await test_mcp_evaluator()
        await test_integration()

        logger.info("\n" + "=" * 60)
        logger.info("✓ All tests passed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n✗ Test failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    exit(exit_code)
