"""Vault Git Sync - Keeps AI_Employee_Vault/ synced via a private Git remote.

Both cloud and local zones push/pull. Only *.md files are tracked.
Commit messages include the ZONE env var for traceability.

Usage:
    from utils.vault_sync import sync_vault, pull_only
    result = sync_vault(vault_path)     # pull + commit + push
    result = pull_only(vault_path)      # pull only (read-only sync)
"""

import os
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("VaultSync")

ZONE = os.getenv("ZONE", "local")


def run_git(vault: Path, *args: str) -> dict:
    """Run a git command inside the vault directory.

    Returns:
        dict with 'ok' (bool), 'stdout', 'stderr'.
    """
    cmd = ["git"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(vault),
            shell=(os.name == "nt"),
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        logger.error("git %s timed out (60s)", " ".join(args))
        return {"ok": False, "stdout": "", "stderr": "timeout"}
    except FileNotFoundError:
        logger.error("git not found on PATH")
        return {"ok": False, "stdout": "", "stderr": "git not found"}


def sync_vault(vault: Path) -> dict:
    """Pull (rebase), stage *.md, commit, push.

    Returns:
        dict with 'pulled', 'pushed', 'error' keys.
    """
    result = {"pulled": False, "pushed": False, "error": None}

    # Check if vault is a git repo
    if not (vault / ".git").exists():
        result["error"] = "Vault is not a git repository"
        logger.warning(result["error"])
        return result

    # Pull with rebase
    pull = run_git(vault, "pull", "--rebase", "--autostash")
    if pull["ok"]:
        result["pulled"] = True
        if pull["stdout"]:
            logger.info("Vault pull: %s", pull["stdout"][:200])
    else:
        # Pull failure is non-fatal — maybe remote is not set up yet
        if "no tracking information" in pull["stderr"] or "no such ref" in pull["stderr"]:
            logger.info("Vault has no remote tracking branch yet — skipping pull")
        else:
            logger.warning("Vault pull failed: %s", pull["stderr"][:200])

    # Stage only *.md files (top-level and subdirectories)
    add = run_git(vault, "add", "*.md", "**/*.md")
    if not add["ok"] and "did not match any files" not in add["stderr"]:
        logger.debug("git add note: %s", add["stderr"][:200])

    # Check if there are staged changes
    diff = run_git(vault, "diff", "--cached", "--quiet")
    if diff["ok"]:
        # No changes to commit
        logger.debug("No vault changes to commit")
        return result

    # Commit
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    message = f"[{ZONE}] auto-sync {timestamp}"
    commit = run_git(vault, "commit", "-m", message)
    if not commit["ok"]:
        logger.warning("Vault commit failed: %s", commit["stderr"][:200])
        result["error"] = commit["stderr"][:200]
        return result

    logger.info("Vault committed: %s", message)

    # Push
    push = run_git(vault, "push")
    if push["ok"]:
        result["pushed"] = True
        logger.info("Vault pushed to remote")
    else:
        if "no configured push destination" in push["stderr"]:
            logger.info("No push remote configured — skipping push")
        else:
            logger.warning("Vault push failed: %s", push["stderr"][:200])
            result["error"] = push["stderr"][:200]

    return result


def pull_only(vault: Path) -> dict:
    """Pull without pushing — for read-only sync."""
    result = {"pulled": False, "error": None}

    if not (vault / ".git").exists():
        result["error"] = "Vault is not a git repository"
        return result

    pull = run_git(vault, "pull", "--rebase", "--autostash")
    if pull["ok"]:
        result["pulled"] = True
        if pull["stdout"]:
            logger.info("Vault pull: %s", pull["stdout"][:200])
    else:
        if "no tracking information" not in pull["stderr"]:
            logger.warning("Vault pull failed: %s", pull["stderr"][:200])
            result["error"] = pull["stderr"][:200]

    return result
