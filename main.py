"""
AI Employee - Main Entry Point

Starts the File System Watcher, Orchestrator, and Scheduler.
Supports zone selection for cloud/local split deployment.

Usage:
    uv run python main.py                  # Start the file watcher only
    uv run python main.py --orchestrator   # Start the orchestrator only
    uv run python main.py --scheduler      # Start full scheduler (watcher + orchestrator + jobs)
    uv run python main.py --all            # Alias for --scheduler
    uv run python main.py --once           # Process pending tasks once and exit
    uv run python main.py --zone cloud     # Override ZONE env var
"""

import os
import argparse
import logging
from pathlib import Path

from watchers.filesystem_watcher import run_watcher
from orchestrator import run_continuous, run_once

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AIEmployee")

VAULT_PATH = Path(__file__).parent / "AI_Employee_Vault"


def main():
    parser = argparse.ArgumentParser(description="AI Employee - Your Digital FTE")
    parser.add_argument(
        "--orchestrator", action="store_true",
        help="Run the orchestrator (processes Needs_Action tasks via Claude)"
    )
    parser.add_argument(
        "--scheduler", action="store_true",
        help="Run full scheduler (file watcher + Gmail watcher + orchestrator + scheduled jobs)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Alias for --scheduler"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Process pending tasks once and exit"
    )
    parser.add_argument(
        "--zone", type=str, choices=["cloud", "local"], default=None,
        help="Override ZONE env var (cloud or local)"
    )
    args = parser.parse_args()

    # Apply --zone override before any module reads ZONE
    if args.zone:
        os.environ["ZONE"] = args.zone
        # Also update the module-level ZONE in orchestrator
        import orchestrator
        orchestrator.ZONE = args.zone
        logger.info(f"Zone overridden via CLI: {args.zone}")

    zone = os.getenv("ZONE", "local")
    logger.info(f"AI Employee starting. Vault: {VAULT_PATH}  Zone: {zone}")

    if args.once:
        logger.info("Running one-time processing...")
        run_once(VAULT_PATH)
        return

    if args.scheduler or args.all:
        logger.info("Starting Scheduler (watcher + orchestrator + jobs)...")
        from scheduler import run_scheduler
        run_scheduler()

    elif args.orchestrator:
        logger.info("Starting Orchestrator only...")
        run_continuous(VAULT_PATH, interval=30)

    else:
        logger.info("Starting File Watcher only...")
        logger.info(f"Drop files into: {VAULT_PATH / 'Inbox'}")
        run_watcher(VAULT_PATH)


if __name__ == "__main__":
    main()
