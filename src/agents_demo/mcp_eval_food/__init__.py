from __future__ import annotations

import logging

from agents import set_tracing_disabled
from langfuse import get_client

langfuse_client = get_client()
if not langfuse_client.auth_check():
    raise RuntimeError("Langfuse auth failed - check your keys/host")

set_tracing_disabled(True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
