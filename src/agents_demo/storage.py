from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import psycopg
from psycopg.types.json import Json

logger = logging.getLogger(__name__)

def _read_json_payload(path: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except Exception as exc:  # pragma: no cover - best-effort load
        logger.warning("Failed to read JSON payload: %s", exc)
        return None
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return json.loads(raw.decode(encoding))
        except Exception:
            continue
    logger.warning("Failed to decode JSON payload with fallback encodings")
    return None


class ConversationStore:
    """Persistence layer for conversation state."""

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def save(self, conversation_id: str, state: Dict[str, Any]) -> None:
        raise NotImplementedError


class CompositeConversationStore(ConversationStore):
    """Fan-out adapter that keeps multiple stores in sync."""

    def __init__(
        self,
        primary: ConversationStore,
        secondary: ConversationStore,
        *,
        sync_secondary_from_primary: bool = False,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        if sync_secondary_from_primary:
            self._sync_secondary_from_primary()

    def _sync_secondary_from_primary(self) -> None:
        dump_all = getattr(self._primary, "dump_all", None)
        merge = getattr(self._secondary, "merge", None)
        if not callable(dump_all) or not callable(merge):
            return
        try:
            payload = dump_all()
        except Exception as exc:  # pragma: no cover - best-effort sync
            logger.warning("Failed to dump primary store: %s", exc)
            return
        if not isinstance(payload, dict):
            return
        try:
            merge(payload)
        except Exception as exc:  # pragma: no cover - best-effort sync
            logger.warning("Failed to merge into secondary store: %s", exc)

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        state = self._primary.get(conversation_id)
        if state is None:
            state = self._secondary.get(conversation_id)
            if state is not None:
                self._primary.save(conversation_id, state)
        return state

    def save(self, conversation_id: str, state: Dict[str, Any]) -> None:
        self._primary.save(conversation_id, state)
        self._secondary.save(conversation_id, state)


PG_HOST = "123.57.128.178"
PG_PORT = 5432
PG_DB = "evaluation"
PG_USER = "postgres"
PG_PASSWORD = "Postgres123!"
PG_DSN = (
    f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} "
    f"user={PG_USER} password={PG_PASSWORD}"
)


class PostgresConversationStore(ConversationStore):
    """
    Adapter for storing conversation state in PostgreSQL.

    Implements the ConversationStore interface so callers remain unchanged.
    """

    def __init__(
        self,
        dsn: str = PG_DSN,
        *,
        context_loader: Optional[Callable[[Dict[str, Any]], Any]] = None,
        seed_path: Optional[Path] = None,
    ) -> None:
        self._dsn = dsn
        self._context_loader = context_loader
        self._lock = threading.Lock()
        self._init_schema()
        if seed_path is not None:
            self._seed_from_json(seed_path)

    def _connect(self):
        return psycopg.connect(self._dsn)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_state (
                        conversation_id TEXT PRIMARY KEY,
                        state JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )

    def _seed_from_json(self, path: Path) -> None:
        if not path.exists():
            return
        payload = _read_json_payload(path)
        if payload is None:
            return
        if not isinstance(payload, dict):
            logger.warning("Seed conversations file is not a dict; skipping")
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                now = time.time()
                for conversation_id, state in payload.items():
                    if not isinstance(state, dict):
                        continue
                    created_at = state.get("created_at", now)
                    updated_at = state.get("updated_at", created_at)
                    cur.execute(
                        """
                        INSERT INTO conversation_state (conversation_id, state, created_at, updated_at)
                        VALUES (%s, %s, to_timestamp(%s), to_timestamp(%s))
                        ON CONFLICT (conversation_id) DO UPDATE SET
                            state = EXCLUDED.state,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            conversation_id,
                            Json(state),
                            created_at,
                            updated_at,
                        ),
                    )

    def dump_all(self) -> Dict[str, Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT conversation_id, state FROM conversation_state")
                rows = cur.fetchall()
        payload: Dict[str, Dict[str, Any]] = {}
        for conversation_id, state in rows:
            if isinstance(state, str):
                try:
                    state = json.loads(state)
                except json.JSONDecodeError:
                    continue
            if isinstance(state, dict):
                payload[conversation_id] = state
        return payload
    def _restore_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        context_data = state.get("context")
        if context_data and self._context_loader:
            try:
                state["context"] = self._context_loader(context_data)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Unable to restore context, keeping raw data: %s", exc)
        return state

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT state FROM conversation_state WHERE conversation_id = %s",
                        (conversation_id,),
                    )
                    row = cur.fetchone()
            if not row:
                return None
            raw = row[0]
            if isinstance(raw, str):
                state = json.loads(raw)
            else:
                state = raw
            if not isinstance(state, dict):
                return None
            return self._restore_context(dict(state))

    def save(self, conversation_id: str, state: Dict[str, Any]) -> None:
        payload = dict(state)
        ctx = payload.get("context")
        if hasattr(ctx, "model_dump"):
            payload["context"] = ctx.model_dump()
        payload["updated_at"] = time.time()
        payload.setdefault("created_at", payload["updated_at"])

        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO conversation_state (conversation_id, state, created_at, updated_at)
                        VALUES (%s, %s, to_timestamp(%s), to_timestamp(%s))
                        ON CONFLICT (conversation_id) DO UPDATE SET
                            state = EXCLUDED.state,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            conversation_id,
                            Json(payload),
                            payload["created_at"],
                            payload["updated_at"],
                        ),
                    )


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
        payload = _read_json_payload(self.path)
        if isinstance(payload, dict):
            self._cache = payload
            return
        logger.warning("Failed to load conversation store; resetting cache")
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

    def merge(self, payload: Dict[str, Dict[str, Any]]) -> None:
        if not isinstance(payload, dict):
            return
        with self._lock:
            for conversation_id, state in payload.items():
                if isinstance(state, dict):
                    self._cache[conversation_id] = state
            self._write_to_disk()

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
