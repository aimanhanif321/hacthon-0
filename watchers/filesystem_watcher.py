"""
File System Watcher - monitors the /Inbox folder for new files
and creates action items in /Needs_Action for Claude to process.

Usage:
    python -m watchers.filesystem_watcher
"""

import sys
import time
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("FileSystemWatcher")

# Default vault path - relative to project root
DEFAULT_VAULT = Path(__file__).parent.parent / "AI_Employee_Vault"


class InboxHandler(FileSystemEventHandler):
    """Watches /Inbox and creates action files in /Needs_Action."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.needs_action = vault_path / "Needs_Action"
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.processed: set[str] = set()

    def _should_skip(self, path: Path) -> bool:
        """Skip temp files, hidden files, and already-processed files."""
        if path.name.startswith("."):
            return True
        if ".tmp" in path.name:
            return True
        if path.name in self.processed:
            return True
        if not path.exists():
            return True
        return False

    def on_created(self, event):
        if event.is_directory:
            return
        source = Path(event.src_path)
        if self._should_skip(source):
            return
        self._process(source)

    def on_moved(self, event):
        """Catch rename/move events (e.g. temp file renamed to final name)."""
        if event.is_directory:
            return
        source = Path(event.dest_path)
        if self._should_skip(source):
            return
        self._process(source)

    def _process(self, source: Path):
        self.processed.add(source.name)
        logger.info(f"New file detected: {source.name}")
        try:
            self._create_action_file(source)
        except Exception as e:
            logger.error(f"Failed to process {source.name}: {e}")

    def _create_action_file(self, source: Path):
        """Create a .md action file in /Needs_Action with metadata."""
        now = datetime.now(timezone.utc).isoformat()
        safe_name = source.stem.replace(" ", "_")
        action_filename = f"FILE_{safe_name}_{datetime.now().strftime('%H%M%S')}.md"
        action_path = self.needs_action / action_filename

        # Determine priority based on file extension
        priority = self._classify_priority(source)

        # Copy the original file to Needs_Action
        dest_file = self.needs_action / source.name
        shutil.copy2(source, dest_file)

        # Create the metadata/action markdown file
        content = f"""---
type: file_drop
original_name: {source.name}
file_extension: {source.suffix}
size_bytes: {source.stat().st_size}
created: {now}
priority: {priority}
status: pending
copied_to: {dest_file.name}
---

# New File: {source.name}

A new file was dropped in the Inbox for processing.

## File Details
- **Name**: {source.name}
- **Type**: {source.suffix or 'unknown'}
- **Size**: {source.stat().st_size} bytes
- **Detected at**: {now}

## Suggested Actions
- [ ] Review file contents
- [ ] Categorize and file appropriately
- [ ] Process any required actions
- [ ] Move to /Done when complete
"""
        action_path.write_text(content, encoding="utf-8")
        logger.info(f"Action file created: {action_filename}")

    def _classify_priority(self, source: Path) -> str:
        """Simple priority classification based on file type."""
        high_priority = {".pdf", ".xlsx", ".csv", ".docx"}
        medium_priority = {".txt", ".md", ".json"}

        if source.suffix.lower() in high_priority:
            return "high"
        elif source.suffix.lower() in medium_priority:
            return "medium"
        return "low"


def run_watcher(vault_path: Path | None = None):
    """Start the filesystem watcher on the vault's Inbox folder."""
    vault = vault_path or DEFAULT_VAULT
    inbox = vault / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    logger.info(f"Watching: {inbox}")
    logger.info(f"Actions go to: {vault / 'Needs_Action'}")
    logger.info("Press Ctrl+C to stop")

    handler = InboxHandler(vault)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()

    observer.join()
    logger.info("Watcher stopped.")


if __name__ == "__main__":
    custom_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_watcher(custom_path)
