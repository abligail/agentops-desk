"""
Integration of MCP Evaluation with existing API
Integrates function call tracking with FastAPI endpoints
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from .mcp_evaluation import AgentMCPEvaluator
from .telemetry import Telemetry

logger = logging.getLogger(__name__)


class MCPIntegration:
    """Integration layer for MCP evaluation with the API"""

    _instance: Optional["MCPIntegration"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.evaluator: Optional[AgentMCPEvaluator] = None
        self.telemetry: Optional[Telemetry] = None
        self._initialized = True
        logger.info("MCP Integration initialized")

    def initialize(
        self,
        langfuse_client=None,
        telemetry: Optional[Telemetry] = None,
    ):
        """Initialize the MCP integration with Langfuse and Telemetry"""
        self.evaluator = AgentMCPEvaluator(langfuse_client=langfuse_client)
        self.telemetry = telemetry
        logger.info("MCP Integration configured with Langfuse and Telemetry")

    def is_initialized(self) -> bool:
        """Check if the integration is initialized"""
        return self.evaluator is not None

    def get_evaluator(self) -> Optional[AgentMCPEvaluator]:
        """Get the MCP evaluator instance"""
        return self.evaluator

    async def evaluate_agent_execution(
        self,
        trace_id: str,
        agent_name: str,
        user_message: str,
        assistant_message: str,
    ):
        """Evaluate an agent execution using MCP"""
        if not self.is_initialized():
            logger.warning("MCP Integration not initialized, skipping evaluation")
            return None

        try:
            evaluation = await self.evaluator.evaluate_agent_trace(
                trace_id=trace_id,
                agent_name=agent_name,
            )

            logger.info(f"Completed MCP evaluation for trace {trace_id}")
            return evaluation

        except Exception as e:
            logger.error(f"MCP evaluation failed: {e}")
            return None

    def get_evaluation_report(self) -> str:
        """Get the evaluation report"""
        if not self.is_initialized():
            return "MCP Integration not initialized"

        return self.evaluator.export_evaluation_report()

    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global statistics"""
        if not self.is_initialized():
            return {}

        return self.evaluator.get_global_statistics()


def get_mcp_integration() -> MCPIntegration:
    """
    Get the singleton MCP integration instance

    Returns:
        MCPIntegration instance
    """
    return MCPIntegration()


async def evaluate_with_mcp(
    trace_id: str,
    agent_name: str,
    user_message: str,
    assistant_message: str,
    langfuse_client=None,
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to evaluate an agent execution with MCP

    Args:
        trace_id: Langfuse trace ID
        agent_name: Name of the agent
        user_message: User's input message
        assistant_message: Agent's response message
        langfuse_client: Optional Langfuse client

    Returns:
        Evaluation results if successful, None otherwise
    """
    integration = get_mcp_integration()

    if not integration.is_initialized():
        integration.initialize(langfuse_client=langfuse_client)

    return await integration.evaluate_agent_execution(
        trace_id=trace_id,
        agent_name=agent_name,
        user_message=user_message,
        assistant_message=assistant_message,
    )
