"""Thin audit-logging wrapper that enforces consistent field naming.

Every module should call ``log(vault, ...)`` from here instead of
reaching into ``orchestrator.log_action`` directly.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("utils.audit")

# Required fields in every audit entry.
_REQUIRED = {"action_type", "actor"}


def log(vault: Path, *, action_type: str, actor: str, **extra) -> None:
    """Append an audit entry to today's log file.

    Args:
        vault: Root of the Obsidian vault.
        action_type: Machine-readable action name (e.g. ``task_processed``).
        actor: Who performed the action (e.g. ``orchestrator``, ``scheduler``).
        **extra: Any additional fields (``file``, ``result``, ``details``, …).
    """
    logs_dir = vault / "Logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    entries: list[dict] = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": actor,
        **extra,
    }
    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    logger.debug("Logged %s by %s", action_type, actor)
