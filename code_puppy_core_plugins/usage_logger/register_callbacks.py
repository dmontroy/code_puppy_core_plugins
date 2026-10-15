"""Append one JSON record per completed run to a text log file.

The log is newline-delimited JSON so external monitors can tail it without
parsing human-oriented console output.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_puppy.callbacks import register_callback

logger = logging.getLogger(__name__)
_WRITE_LOCK = threading.Lock()
_LOG_FILE_NAME = "model_usage.jsonl"


def _log_path() -> Path:
    from code_puppy.error_logging import get_logs_dir

    return Path(get_logs_dir()) / _LOG_FILE_NAME


def _ensure_log_dir() -> None:
    from code_puppy.error_logging import _ensure_logs_dir

    _ensure_logs_dir()


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


async def _on_agent_run_end(
    agent_name: str,
    model_name: str,
    session_id: str | None = None,
    success: bool = True,
    error: Exception | None = None,
    response_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_name": agent_name,
        "model": model_name,
        "session_id": session_id,
        "success": bool(success),
        "error_type": type(error).__name__ if error else None,
        "error_message": str(error) if error else None,
        "response_chars": len(response_text or ""),
        "usage": {
            "input_tokens": _int_or_none((metadata or {}).get("usage_input_tokens")),
            "output_tokens": _int_or_none((metadata or {}).get("usage_output_tokens")),
            "total_tokens": _int_or_none((metadata or {}).get("usage_total_tokens")),
            "cached_read_tokens": _int_or_none(
                (metadata or {}).get("usage_cached_read_tokens")
            ),
            "cached_write_tokens": _int_or_none(
                (metadata or {}).get("usage_cached_write_tokens")
            ),
            "thought_tokens": _int_or_none(
                (metadata or {}).get("usage_thought_tokens")
            ),
        },
    }

    try:
        _ensure_log_dir()
        payload = json.dumps(entry, sort_keys=True, ensure_ascii=True)
        with _WRITE_LOCK:
            with _log_path().open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
    except Exception:
        logger.debug("usage_logger: failed to append usage log", exc_info=True)


register_callback("agent_run_end", _on_agent_run_end)
