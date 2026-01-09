import logging

from . import langfuse_client
from .task import run_agent

TEST_CASES = [
    {
        "input": {
            "question": "What meal options are available for flight FLT-238?",
            "flight_number": "FLT-238",
            "seat_number": "14C",
            "conversation_id": "food-eval-001",
        },
        "expected_output": {
            "trajectory": ["check_menu_options"],
        },
    },
    {
        "input": {
            "question": "Use account 38249175. I want Vegetarian Pasta Primavera. Please record and confirm.",
            "account_number": "38249175",
            "conversation_id": "food-eval-002",
        },
        "expected_output": {
            "trajectory": [
                "fetch_customer_profile",
                "record_meal_preference",
                "confirm_meal_selection",
            ],
        },
    },
    {
        "input": {
            "question": "I have a nut allergy. What meals are safe on flight FLT-238?",
            "flight_number": "FLT-238",
            "seat_number": "21F",
            "conversation_id": "food-eval-003",
        },
        "expected_output": {
            "trajectory": ["check_menu_options"],
        },
    },
]

DATASET_NAME = "food-mcp-agent-evaluation"


def create_dataset() -> None:
    dataset = langfuse_client.create_dataset(name=DATASET_NAME)
    for case in TEST_CASES:
        langfuse_client.create_dataset_item(
            dataset_name=DATASET_NAME,
            input=case["input"],
            expected_output=case["expected_output"],
        )
    logging.info("Created dataset %s", DATASET_NAME)


def run_test() -> None:
    dataset = langfuse_client.get_dataset(DATASET_NAME)
    result = dataset.run_experiment(
        name="Food MCP Evaluation",
        description="Food agent MCP tool-trajectory evaluation",
        task=run_agent,
        max_concurrency=1,
    )
    logging.info(result.format())
    langfuse_client.flush()


if __name__ == "__main__":
    run_test()
