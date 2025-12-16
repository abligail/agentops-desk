"""
LLM-as-a-Judge Evaluator for Agent Responses
Provides automatic quality assessment of agent interactions
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from typing import Optional

from agents import Agent, Runner
from .main_qwen import qwen_model2, OpenAIModel, myRunConfig

logger = logging.getLogger(__name__)


# =========================
# Evaluation Schema
# =========================

class EvaluationScore(BaseModel):
    """Schema for evaluation scores from LLM judge."""
    helpfulness: float = Field(..., ge=0, le=1, description="How helpful is the response? (0-1)")
    accuracy: float = Field(..., ge=0, le=1, description="Is the information accurate? (0-1)")
    relevance: float = Field(..., ge=0, le=1, description="Is the response on-topic? (0-1)")
    overall_score: float = Field(..., ge=0, le=1, description="Overall quality score (0-1)")
    reasoning: str = Field(..., description="Brief explanation of the scores")
    improvement_suggestions: Optional[str] = Field(None, description="Optional suggestions for improvement")


# =========================
# Evaluator Agent
# =========================

evaluator_agent = Agent(
    name="Response Quality Evaluator",
    model=qwen_model2,  # Use the same model configuration as other agents
    instructions="""
You are an expert evaluator assessing the quality of airline customer service agent responses.

Evaluate the assistant's response based on these criteria:

1. **Helpfulness** (0-1): Does the response effectively address the customer's needs?
   - 1.0: Fully addresses the question with actionable information
   - 0.5: Partially helpful but missing key details
   - 0.0: Unhelpful or irrelevant

2. **Accuracy** (0-1): Is the information provided correct and reliable?
   - 1.0: All information is accurate
   - 0.5: Some inaccuracies or unverified claims
   - 0.0: Contains false or misleading information

3. **Relevance** (0-1): Is the response on-topic for airline customer service?
   - 1.0: Fully relevant to airline/flight topics
   - 0.5: Somewhat related but includes off-topic content
   - 0.0: Completely off-topic

4. **Overall Score** (0-1): Weighted average considering all factors
   - Formula: (helpfulness * 0.4) + (accuracy * 0.3) + (relevance * 0.3)

Provide:
- Scores for each criterion
- Brief reasoning (2-3 sentences)
- Optional improvement suggestions

Be objective and constructive in your evaluation.
""",
    output_type=EvaluationScore,
)


# =========================
# Evaluation Functions
# =========================

async def evaluate_response(
    user_message: str,
    assistant_message: str,
    agent_name: Optional[str] = None,
    context: Optional[dict] = None,
) -> EvaluationScore:
    """
    Evaluate a single agent response using LLM-as-a-Judge.

    Args:
        user_message: The customer's question/request
        assistant_message: The agent's response
        agent_name: Name of the agent that provided the response (optional)
        context: Additional context about the conversation (optional)

    Returns:
        EvaluationScore: Structured evaluation with scores and reasoning
    """
    # Build evaluation prompt
    eval_prompt = f"""
**Customer Question:**
{user_message}

**Agent Response:**
{assistant_message}
"""

    if agent_name:
        eval_prompt = f"**Agent:** {agent_name}\n\n" + eval_prompt

    if context:
        eval_prompt += f"\n\n**Context:** {context}"

    try:
        # Run evaluator agent
        if OpenAIModel:
            result = await Runner.run(evaluator_agent, eval_prompt)
        else:
            result = await Runner.run(evaluator_agent, eval_prompt, run_config=myRunConfig)

        score = result.final_output_as(EvaluationScore)
        logger.info(f"Evaluated response: overall={score.overall_score:.2f}")
        return score

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        # Return default scores on error
        return EvaluationScore(
            helpfulness=0.5,
            accuracy=0.5,
            relevance=0.5,
            overall_score=0.5,
            reasoning=f"Evaluation failed: {str(e)}",
            improvement_suggestions=None,
        )


async def evaluate_conversation(
    messages: list[dict],
    max_evaluations: int = 5,
) -> list[EvaluationScore]:
    """
    Evaluate multiple turns in a conversation.

    Args:
        messages: List of message dicts with 'role' and 'content'
        max_evaluations: Maximum number of assistant responses to evaluate

    Returns:
        List of EvaluationScore objects, one per assistant message
    """
    evaluations = []
    user_msg = None

    for msg in messages:
        if msg["role"] == "user":
            user_msg = msg["content"]
        elif msg["role"] == "assistant" and user_msg:
            if len(evaluations) >= max_evaluations:
                break

            score = await evaluate_response(
                user_message=user_msg,
                assistant_message=msg["content"],
                agent_name=msg.get("agent"),
            )
            evaluations.append(score)
            user_msg = None  # Reset for next pair

    return evaluations


# =========================
# Langfuse Integration
# =========================

async def evaluate_and_score_trace(
    trace_id: str,
    user_message: str,
    assistant_messages: list[str],
    agent_name: str,
    langfuse_client=None,
) -> Optional[EvaluationScore]:
    """
    Evaluate a response and submit scores to Langfuse.

    Args:
        trace_id: Langfuse trace ID
        user_message: User's input
        assistant_messages: List of assistant responses
        agent_name: Name of the agent
        langfuse_client: Langfuse client instance (optional)

    Returns:
        EvaluationScore if successful, None otherwise
    """
    if not assistant_messages:
        logger.warning("No assistant messages to evaluate")
        return None

    # Combine multiple messages if present
    combined_response = "\n".join(assistant_messages)

    # Evaluate
    score = await evaluate_response(
        user_message=user_message,
        assistant_message=combined_response,
        agent_name=agent_name,
    )

    # Submit to Langfuse if client is provided
    if langfuse_client:
        try:
            # Submit individual scores
            langfuse_client.score(
                trace_id=trace_id,
                name="llm_judge_helpfulness",
                value=score.helpfulness,
                comment=score.reasoning,
            )
            langfuse_client.score(
                trace_id=trace_id,
                name="llm_judge_accuracy",
                value=score.accuracy,
            )
            langfuse_client.score(
                trace_id=trace_id,
                name="llm_judge_relevance",
                value=score.relevance,
            )
            langfuse_client.score(
                trace_id=trace_id,
                name="llm_judge_overall",
                value=score.overall_score,
                comment=score.improvement_suggestions or score.reasoning,
            )

            logger.info(f"Submitted LLM judge scores to Langfuse for trace {trace_id}")
        except Exception as e:
            logger.error(f"Failed to submit scores to Langfuse: {e}")

    return score
