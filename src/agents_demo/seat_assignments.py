from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class JsonSeatAssignmentStore:
    """
    Simple persistent seat assignment store for demo purposes.

    Stores one assignment per confirmation number so a passenger can change seats
    (the previous assignment is overwritten).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.path.exists():
            self._cache = {}
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._cache = payload
            else:
                logger.warning("Seat assignment store is not a dict; resetting")
                self._cache = {}
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load seat assignment store: %s", exc)
            self._cache = {}

    def _write_to_disk(self) -> None:
        try:
            self.path.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2))
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to persist seat assignment store: %s", exc)

    def get(self, confirmation_number: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._cache.get(confirmation_number)
            return dict(entry) if isinstance(entry, dict) else None

    def assign(self, *, confirmation_number: str, flight_number: str, seat_number: str) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            existing = self._cache.get(confirmation_number) if isinstance(self._cache.get(confirmation_number), dict) else {}
            created_at = existing.get("created_at", now)
            payload = {
                "confirmation_number": confirmation_number,
                "flight_number": flight_number,
                "seat_number": seat_number,
                "created_at": created_at,
                "updated_at": now,
            }
            self._cache[confirmation_number] = payload
            self._write_to_disk()
            return dict(payload)

    def seat_is_taken(
        self,
        *,
        flight_number: str,
        seat_number: str,
        ignore_confirmation: Optional[str] = None,
    ) -> bool:
        with self._lock:
            for confirmation, entry in self._cache.items():
                if ignore_confirmation and confirmation == ignore_confirmation:
                    continue
                if (
                    entry.get("flight_number") == flight_number
                    and entry.get("seat_number") == seat_number
                ):
                    return True
        return False

    def occupied_seats(self, *, flight_number: str) -> Set[str]:
        with self._lock:
            return {
                entry.get("seat_number")
                for entry in self._cache.values()
                if entry.get("flight_number") == flight_number and entry.get("seat_number")
            }


DATA_DIR = Path(__file__).resolve().parent / "data"
seat_assignment_store = JsonSeatAssignmentStore(DATA_DIR / "seat_assignments.json")

