"""
Task State Manager - Tracks multi-step task progress for the Ralph Wiggum loop.

When a multi-step task is active, the stop hook reads .task_state.json
to decide whether Claude should keep working or be allowed to exit.

Usage:
    from skills.task_state import start_multi_step_task, complete_step, is_task_active

    start_multi_step_task(vault, "deploy_report", [
        {"id": "gather", "description": "Gather weekly data"},
        {"id": "generate", "description": "Generate report"},
        {"id": "save", "description": "Save to Briefings/"},
    ])

    complete_step(vault, "gather")
    # ... after all steps done, clear_task_state(vault)
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("TaskState")

STATE_FILENAME = ".task_state.json"
MAX_ITERATIONS = 10


def _state_path(vault: Path) -> Path:
    return vault / STATE_FILENAME


def start_multi_step_task(vault: Path, name: str, steps: list[dict]) -> dict:
    """Create a .task_state.json for a multi-step task.

    Each step dict should have at minimum: {"id": "...", "description": "..."}.
    """
    state = {
        "task_name": name,
        "created": datetime.now(timezone.utc).isoformat(),
        "iteration": 0,
        "max_iterations": MAX_ITERATIONS,
        "steps": [
            {
                "id": s["id"],
                "description": s.get("description", s["id"]),
                "completed": False,
            }
            for s in steps
        ],
    }
    _state_path(vault).write_text(json.dumps(state, indent=2), encoding="utf-8")
    logger.info(f"Started multi-step task: {name} ({len(steps)} steps)")
    return state


def complete_step(vault: Path, step_id: str) -> dict | None:
    """Mark a step as completed. Returns updated state or None if not found."""
    sp = _state_path(vault)
    if not sp.exists():
        logger.warning("No active task state.")
        return None

    state = json.loads(sp.read_text(encoding="utf-8"))
    for step in state["steps"]:
        if step["id"] == step_id:
            step["completed"] = True
            break
    else:
        logger.warning(f"Step '{step_id}' not found in task state.")
        return state

    sp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    logger.info(f"Completed step: {step_id}")
    return state


def get_task_state(vault: Path) -> dict | None:
    """Read the current task state, or None if no active task."""
    sp = _state_path(vault)
    if not sp.exists():
        return None
    try:
        return json.loads(sp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def increment_iteration(vault: Path) -> dict | None:
    """Increment the iteration counter. Returns updated state."""
    sp = _state_path(vault)
    if not sp.exists():
        return None
    state = json.loads(sp.read_text(encoding="utf-8"))
    state["iteration"] = state.get("iteration", 0) + 1
    sp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def is_task_active(vault: Path) -> bool:
    """True if there's an active task with incomplete steps."""
    state = get_task_state(vault)
    if not state:
        return False
    return any(not s["completed"] for s in state.get("steps", []))


def incomplete_steps(vault: Path) -> list[dict]:
    """Return list of steps not yet completed."""
    state = get_task_state(vault)
    if not state:
        return []
    return [s for s in state.get("steps", []) if not s["completed"]]


def clear_task_state(vault: Path):
    """Remove the task state file (task is done)."""
    sp = _state_path(vault)
    if sp.exists():
        sp.unlink()
        logger.info("Task state cleared.")
