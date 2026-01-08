"""
Demonstration of MCP Evaluation for Agents
Shows how to convert agents to MCP servers and evaluate function calls
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

from agents import Agent, Runner

from .mcp_evaluation import AgentMCPEvaluator, create_mcp_evaluator
from .telemetry import Telemetry

logger = logging.getLogger(__name__)


async def demo_mcp_evaluation_single_agent():
    """
    Demo: Evaluate a single agent using MCP observation
    Demonstrates function call tracking and evaluation
    """
    from .main_qwen import qwen_model2, myRunConfig, OpenAIModel
    from .main import faq_agent, faq_lookup_tool

    logger.info("=== Demo: Single Agent MCP Evaluation ===")

    evaluator = create_mcp_evaluator()

    if hasattr(faq_agent, "tools") and faq_agent.tools:
        mcp_server = evaluator.create_mcp_server_for_agent(
            agent_name=faq_agent.name,
            tools=faq_agent.tools,
        )
        logger.info(f"Created MCP server for {faq_agent.name}")

    import time

    trace_id = f"demo_trace_{int(time.time() * 1000)}"

    logger.info(f"Running agent with trace ID: {trace_id}")

    try:
        if OpenAIModel:
            result = await Runner.run(faq_agent, "What is the baggage allowance?")
        else:
            result = await Runner.run(
                faq_agent, "What is the baggage allowance?", run_config=myRunConfig
            )

        logger.info(f"Agent response: {result.final_output}")

        calls = evaluator.tracker.get_calls_by_trace(trace_id)
        logger.info(f"Function calls made: {len(calls)}")

        for call in calls:
            logger.info(
                f"  - {call['function_name']}: success={call['success']}, "
                f"time={call['execution_time']:.4f}s"
            )

        evaluation = await evaluator.evaluate_agent_trace(
            trace_id=trace_id,
            agent_name=faq_agent.name,
        )

        logger.info("\n=== Evaluation Results ===")
        logger.info(f"Total calls: {evaluation['total_calls']}")
        logger.info(f"Success rate: {evaluation['success_rate']:.2%}")
        logger.info(f"Avg execution time: {evaluation['average_execution_time']:.4f}s")
        logger.info(f"\nFunction usage: {evaluation['function_usage']}")

    except Exception as e:
        logger.error(f"Demo failed: {e}")

    return evaluator


async def demo_mcp_evaluation_multiple_agents():
    """
    Demo: Evaluate multiple agents using MCP observation
    Demonstrates comprehensive evaluation across agent workflow
    """
    from .main_qwen import qwen_model2, myRunConfig, OpenAIModel
    from .main import (
        triage_agent,
        faq_agent,
        flight_status_agent,
        seat_booking_agent,
    )

    logger.info("=== Demo: Multiple Agents MCP Evaluation ===")

    evaluator = create_mcp_evaluator()

    agents_to_wrap = [
        triage_agent,
        faq_agent,
        flight_status_agent,
        seat_booking_agent,
    ]

    for agent in agents_to_wrap:
        if hasattr(agent, "tools") and agent.tools:
            evaluator.create_mcp_server_for_agent(
                agent_name=agent.name,
                tools=agent.tools,
            )
            logger.info(f"Created MCP server for {agent.name}")

    test_cases = [
        "What is the baggage allowance?",
        "I need to check the status of my flight",
        "I want to change my seat",
    ]

    for i, test_input in enumerate(test_cases):
        import time

        trace_id = f"multi_agent_trace_{i}_{int(time.time() * 1000)}"
        logger.info(f"\n--- Test Case {i + 1}: {test_input} ---")
        logger.info(f"Trace ID: {trace_id}")

        try:
            if OpenAIModel:
                result = await Runner.run(triage_agent, test_input)
            else:
                result = await Runner.run(
                    triage_agent, test_input, run_config=myRunConfig
                )

            logger.info(f"Response: {result.final_output[:200]}...")

            calls = evaluator.tracker.get_calls_by_trace(trace_id)
            logger.info(f"Function calls in this trace: {len(calls)}")

        except Exception as e:
            logger.error(f"Test case {i + 1} failed: {e}")

    logger.info("\n=== Global Statistics ===")
    stats = evaluator.get_global_statistics()
    logger.info(f"Total calls across all agents: {stats['total_calls']}")
    logger.info(f"Overall success rate: {stats['success_rate']:.2%}")
    logger.info(f"Avg execution time: {stats['average_execution_time']:.4f}s")
    logger.info("\nFunction usage:")
    for func_name, count in sorted(stats["function_usage"].items()):
        logger.info(f"  - {func_name}: {count} calls")
    logger.info("\nAgent usage:")
    for agent_name, count in sorted(stats["agent_usage"].items()):
        logger.info(f"  - {agent_name}: {count} calls")

    return evaluator


async def demo_mcp_with_langfuse():
    """
    Demo: MCP evaluation with Langfuse integration
    Demonstrates how evaluation metrics are submitted to Langfuse
    """
    from .main_qwen import qwen_model2, myRunConfig, OpenAIModel
    from .main import faq_agent

    logger.info("=== Demo: MCP Evaluation with Langfuse ===")

    try:
        from langfuse import get_client

        langfuse = get_client()

        if langfuse.auth_check():
            logger.info("Connected to Langfuse")
        else:
            logger.warning("Langfuse authentication failed, using without Langfuse")
            langfuse = None
    except Exception as e:
        logger.warning(f"Langfuse not available: {e}")
        langfuse = None

    evaluator = create_mcp_evaluator(langfuse_client=langfuse)

    if hasattr(faq_agent, "tools") and faq_agent.tools:
        evaluator.create_mcp_server_for_agent(
            agent_name=faq_agent.name,
            tools=faq_agent.tools,
        )

    import time

    trace_id = f"langfuse_demo_{int(time.time() * 1000)}"
    logger.info(f"Running agent with Langfuse trace ID: {trace_id}")

    try:
        if OpenAIModel:
            result = await Runner.run(faq_agent, "What is the baggage allowance?")
        else:
            result = await Runner.run(
                faq_agent, "What is the baggage allowance?", run_config=myRunConfig
            )

        logger.info(f"Agent response: {result.final_output}")

        evaluation = await evaluator.evaluate_agent_trace(
            trace_id=trace_id,
            agent_name=faq_agent.name,
        )

        logger.info("\n=== Evaluation Submitted to Langfuse ===")
        logger.info(f"Success Rate Score: {evaluation['success_rate']:.2%}")
        logger.info(f"Total Calls Score: {evaluation['total_calls']}")
        logger.info(f"Avg Time Score: {evaluation['average_execution_time']:.4f}s")

        if langfuse:
            langfuse.flush()
            logger.info("Metrics flushed to Langfuse")

    except Exception as e:
        logger.error(f"Demo failed: {e}")

    return evaluator


async def demo_comprehensive_evaluation():
    """
    Demo: Comprehensive evaluation using MCP pattern
    Combines function call tracking, LLM-as-a-Judge, and user feedback
    """
    from .evaluators import evaluate_response
    from .main_qwen import qwen_model2, myRunConfig, OpenAIModel
    from .main import triage_agent

    logger.info("=== Demo: Comprehensive Evaluation ===")

    try:
        from langfuse import get_client

        langfuse = get_client()
        if langfuse.auth_check():
            logger.info("Connected to Langfuse")
        else:
            langfuse = None
    except:
        langfuse = None

    mcp_evaluator = create_mcp_evaluator(langfuse_client=langfuse)

    if hasattr(triage_agent, "tools") and triage_agent.tools:
        mcp_evaluator.create_mcp_server_for_agent(
            agent_name=triage_agent.name,
            tools=triage_agent.tools,
        )

    test_queries = [
        ("What is the baggage allowance?", "User asking about baggage policy"),
        ("I want to change my seat", "User wants seat change"),
    ]

    for i, (query, context) in enumerate(test_queries):
        import time

        trace_id = f"comprehensive_{i}_{int(time.time() * 1000)}"
        logger.info(f"\n--- Query {i + 1}: {query} ---")
        logger.info(f"Trace ID: {trace_id}")

        try:
            if OpenAIModel:
                result = await Runner.run(triage_agent, query)
            else:
                result = await Runner.run(triage_agent, query, run_config=myRunConfig)

            agent_response = result.final_output

            logger.info(f"\n1. Agent Response:")
            logger.info(f"   {agent_response[:200]}...")

            mcp_eval = await mcp_evaluator.evaluate_agent_trace(
                trace_id=trace_id,
                agent_name=triage_agent.name,
            )
            logger.info(f"\n2. MCP Function Call Evaluation:")
            logger.info(f"   Success Rate: {mcp_eval['success_rate']:.2%}")
            logger.info(f"   Total Calls: {mcp_eval['total_calls']}")

            if langfuse:
                llm_eval = await evaluate_response(
                    user_message=query,
                    assistant_message=agent_response,
                    agent_name=triage_agent.name,
                    langfuse_client=langfuse,
                )
                logger.info(f"\n3. LLM-as-a-Judge Evaluation:")
                logger.info(f"   Helpfulness: {llm_eval.helpfulness:.2f}")
                logger.info(f"   Accuracy: {llm_eval.accuracy:.2f}")
                logger.info(f"   Relevance: {llm_eval.relevance:.2f}")
                logger.info(f"   Overall Score: {llm_eval.overall_score:.2f}")
                logger.info(f"   Reasoning: {llm_eval.reasoning}")

                langfuse.flush()

        except Exception as e:
            logger.error(f"Query {i + 1} failed: {e}")

    logger.info("\n=== Comprehensive Report ===")
    logger.info(mcp_evaluator.export_evaluation_report())

    return mcp_evaluator


async def run_all_demos():
    """Run all MCP evaluation demonstrations"""
    logger.info("Starting MCP Evaluation Demonstrations")
    logger.info("=" * 60)

    await demo_mcp_evaluation_single_agent()
    logger.info("\n" + "=" * 60)

    await demo_mcp_evaluation_multiple_agents()
    logger.info("\n" + "=" * 60)

    await demo_mcp_with_langfuse()
    logger.info("\n" + "=" * 60)

    await demo_comprehensive_evaluation()
    logger.info("\n" + "=" * 60)

    logger.info("All demonstrations completed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_all_demos())
