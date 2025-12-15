from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ConversationStore:
    """Persistence layer for conversation state."""

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def save(self, conversation_id: str, state: Dict[str, Any]) -> None:
        raise NotImplementedError


class JsonConversationStore(ConversationStore):
    """
    Lightweight JSON store for conversation state.

    Designed for demo use: thread-safe, survives process restarts, and
    keeps data in-memory for quick reads.
    """

    def __init__(
        self,
        path: Path,
        *,
        context_loader: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._context_loader = context_loader
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.path.exists():
            self._cache = {}
            return
        try:
            self._cache = json.loads(self.path.read_text())
        except Exception as exc:  # pragma: no cover - best-effort load
            logger.warning("Failed to load conversation store: %s", exc)
            self._cache = {}

    def _write_to_disk(self) -> None:
        def _json_fallback(obj: Any):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        try:
            self.path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2, default=_json_fallback)
            )
        except Exception as exc:  # pragma: no cover - best-effort persistence
            logger.error("Failed to persist conversation store: %s", exc)

    def _restore_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rehydrate context using the provided loader to keep runtime types intact.
        """
        context_data = state.get("context")
        if context_data and self._context_loader:
            try:
                state["context"] = self._context_loader(context_data)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Unable to restore context, keeping raw data: %s", exc)
        return state

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            raw = self._cache.get(conversation_id)
            if raw is None:
                return None
            return self._restore_context(dict(raw))

    def save(self, conversation_id: str, state: Dict[str, Any]) -> None:
        payload = dict(state)
        ctx = payload.get("context")
        if hasattr(ctx, "model_dump"):
            payload["context"] = ctx.model_dump()
        payload["updated_at"] = time.time()
        payload.setdefault("created_at", payload["updated_at"])

        with self._lock:
            self._cache[conversation_id] = payload
            self._write_to_disk()
