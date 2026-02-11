"""
Ralph Wiggum Stop Hook — keeps Claude working until all task steps are done.

Claude Code calls this hook when it's about to stop. If there are incomplete
steps in .task_state.json, the hook blocks the exit so Claude continues.

Safety: hard limit of 10 iterations prevents infinite loops.

Output: JSON to stdout — {"decision": "block", "reason": "..."} or
        {"decision": "allow"}.
"""

import json
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent / "AI_Employee_Vault"
STATE_FILE = VAULT / ".task_state.json"
MAX_ITERATIONS = 10


def main():
    if not STATE_FILE.exists():
        print(json.dumps({"decision": "allow"}))
        return

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(json.dumps({"decision": "allow"}))
        return

    steps = state.get("steps", [])
    incomplete = [s for s in steps if not s.get("completed")]
    iteration = state.get("iteration", 0)

    # Safety: hard limit on iterations
    if iteration >= MAX_ITERATIONS:
        print(json.dumps({
            "decision": "allow",
            "reason": f"Hit max iterations ({MAX_ITERATIONS}). Allowing exit to prevent infinite loop.",
        }))
        return

    if not incomplete:
        # All steps done — allow exit
        print(json.dumps({"decision": "allow"}))
        return

    # Increment iteration counter
    state["iteration"] = iteration + 1
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    remaining = ", ".join(s["description"] for s in incomplete)
    print(json.dumps({
        "decision": "block",
        "reason": f"Task '{state.get('task_name', 'unknown')}' has {len(incomplete)} incomplete step(s): {remaining}. (iteration {iteration + 1}/{MAX_ITERATIONS})",
    }))


if __name__ == "__main__":
    main()
