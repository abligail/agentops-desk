from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    """Best-effort append to a JSONL file for offline analysis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to append to %s: %s", path, exc)


class Telemetry:
    """
    Small helper to log traces locally and optionally forward feedback to Langfuse.
    """

    def __init__(self, trace_log: Path, feedback_log: Path) -> None:
        self.trace_log = trace_log
        self.feedback_log = feedback_log
        self._langfuse = self._init_langfuse()

    def _init_langfuse(self):
        try:
            from langfuse import get_client  # type: ignore
        except Exception as exc:
            logger.info("Langfuse SDK unavailable, skipping remote tracing: %s", exc)
            return None

        try:
            client = get_client()
            client.auth_check()
            logger.info("Langfuse client initialised for feedback upload")
            return client
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.info("Langfuse client not configured: %s", exc)
            return None

    def record_trace(
        self,
        *,
        trace_id: str,
        conversation_id: str,
        agent: str,
        user_message: str,
        assistant_messages: list[Dict[str, Any]],
        guardrails: list[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist the trace locally for later analysis/evaluation."""
        payload = {
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "agent": agent,
            "user_message": user_message,
            "assistant_messages": assistant_messages,
            "guardrails": guardrails,
            "metadata": metadata or {},
            "ts": time.time(),
        }
        _append_jsonl(self.trace_log, payload)

    def submit_feedback(
        self,
        *,
        trace_id: str,
        score: Optional[float],
        comment: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
        score_name: str = "user-feedback",
    ) -> bool:
        """Submit user feedback to Langfuse if available and log locally."""
        feedback_payload = {
            "trace_id": trace_id,
            "score": score,
            "score_name": score_name,
            "comment": comment,
            "metadata": metadata or {},
            "ts": time.time(),
        }
        _append_jsonl(self.feedback_log, feedback_payload)

        if score is None or not self._langfuse:
            return False

        try:
            # Align with langfuse scoring API used in the Gradio example
            self._langfuse.create_score(
                name=score_name,
                value=score,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=comment or "",
                metadata=metadata or {},
            )
            return True
        except Exception as exc:  # pragma: no cover - network/env dependent
            logger.info("Failed to forward feedback to Langfuse: %s", exc)
            return False
