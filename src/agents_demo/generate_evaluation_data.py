import asyncio
import json
import random
import time
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

from agents import Runner

# Import agents from main.py as the source of truth
from agents_demo.main import (
    triage_agent,
    faq_agent,
    flight_status_agent,
    seat_booking_agent,
    cancellation_agent,
)

# Import MCP server components
from agents_demo.mcp_server import FunctionCallTracker, AgentFunctionWrapper

# Try to import Qwen config if available
try:
    from agents_demo.main_qwen import myRunConfig, OpenAIModel
except ImportError:
    myRunConfig = None
    OpenAIModel = True

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_data_gen")


class ScenarioGenerator:
    """Generates random user scenarios for evaluation"""

    def __init__(self):
        self.scenarios = {
            "faq_baggage": [
                "What is the baggage allowance for economy class?",
                "Can I bring a guitar on board?",
                "How much does extra baggage cost?",
                "What are the carry-on dimensions?",
                "Do you charge for checked bags?",
            ],
            "faq_wifi": [
                "Is there wifi on the plane?",
                "How do I connect to wifi?",
                "Is the wifi free?",
                "What is the wifi password?",
            ],
            "flight_status": [
                "What is the status of flight FLT-123?",
                "Is flight FLT-456 on time?",
                "Check status for flight FLT-789",
                "Which gate is FLT-238 departing from?",
                "Has flight FLT-999 landed?",
            ],
            "seat_booking": [
                "I want to change my seat",
                "Can I get a window seat?",
                "Show me the seat map",
                "I'd like to sit in row 5",
                "Move me to an aisle seat please",
            ],
            "cancellation": [
                "I need to cancel my flight",
                "Cancel flight FLT-202",
                "Refund policy for cancelled flights",
                "I can't make my flight tomorrow, cancel it",
            ],
            "meal_preference": [
                "I want to order a vegetarian meal",
                "What food do you serve?",
                "I have a nut allergy",
                "Order the chicken for me",
            ],
            "triage_general": [
                "Hello",
                "I need help",
                "Who are you?",
                "Connect me to an agent",
            ],
        }

    def get_random_input(self) -> str:
        """Get a random input string"""
        category = random.choice(list(self.scenarios.keys()))
        return random.choice(self.scenarios[category])

    def get_batch(self, size: int) -> List[str]:
        """Get a batch of random inputs"""
        return [self.get_random_input() for _ in range(size)]


async def generate_evaluation_data(
    num_samples: int = 10, output_file: str = "mcp_evaluation_data.json"
):
    """
    Generate evaluation data by running agents with random inputs
    and capturing execution traces via MCP tracking.
    """
    logger.info(f"Starting data generation for {num_samples} samples...")

    # 1. Initialize a shared tracker for all agents
    shared_tracker = FunctionCallTracker()

    # 2. Wrap all agents with the shared tracker
    # This ensures that even if agents delegate to each other,
    # all tool calls are logged to the same tracker.
    agents_to_wrap = [
        triage_agent,
        faq_agent,
        flight_status_agent,
        seat_booking_agent,
        cancellation_agent,
    ]

    wrappers = {}
    for agent in agents_to_wrap:
        logger.info(f"Wrapping agent: {agent.name}")
        wrapper = AgentFunctionWrapper(agent, tracker=shared_tracker)
        wrapper.get_wrapped_agent()  # This modifies the agent in-place
        wrappers[agent.name] = wrapper

    # 3. Generate random inputs
    generator = ScenarioGenerator()
    inputs = generator.get_batch(num_samples)

    results = []

    # 4. Run loop
    for i, user_input in enumerate(inputs):
        trace_id = f"gen_trace_{int(time.time())}_{i}"
        logger.info(f"Processing sample {i + 1}/{num_samples}: {user_input}")

        # Start trace on the shared tracker
        shared_tracker.start_trace(trace_id, "System")

        start_time = time.time()
        try:
            # We run the triage agent as the entry point
            # The agents are already modified in-place with tracking tools

            # Select config based on environment
            if OpenAIModel:
                result = await Runner.run(triage_agent, user_input)
            else:
                result = await Runner.run(
                    triage_agent, user_input, run_config=myRunConfig
                )

            execution_time = time.time() - start_time

            # Retrieve calls for this trace
            calls = shared_tracker.get_calls_by_trace(trace_id)

            # Construct trace data object
            trace_record = {
                "trace_id": trace_id,
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input,
                "agent_response": result.final_output,
                "total_execution_time": execution_time,
                "function_calls": calls,
                "call_count": len(calls),
                "success": True,
            }

            results.append(trace_record)
            logger.info(
                f"Sample {i + 1} complete. Recorded {len(calls)} function calls."
            )

        except Exception as e:
            logger.error(f"Error processing sample {i + 1}: {e}")
            # Log failed trace
            results.append(
                {
                    "trace_id": trace_id,
                    "timestamp": datetime.now().isoformat(),
                    "user_input": user_input,
                    "error": str(e),
                    "success": False,
                }
            )
        finally:
            shared_tracker.end_trace()

    # 5. Save to file
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Data generation complete. Saved {len(results)} traces to {output_file}"
    )

    # 6. Output Summary Stats
    stats = shared_tracker.get_statistics()
    logger.info("=== Generation Statistics ===")
    logger.info(f"Total Traces: {num_samples}")
    logger.info(f"Total Function Calls: {stats['total_calls']}")
    logger.info(f"Success Rate: {stats['success_rate']:.2%}")
    logger.info("Function Usage:")
    for func, count in stats["function_usage"].items():
        logger.info(f"  - {func}: {count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate MCP evaluation data")
    parser.add_argument(
        "--samples", type=int, default=5, help="Number of samples to generate"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="src/agents_demo/data/mcp_evaluation_data.json",
        help="Output file path",
    )

    args = parser.parse_args()

    # Resolve path relative to current working directory if not absolute
    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.abspath(output_path)

    asyncio.run(generate_evaluation_data(args.samples, output_path))
