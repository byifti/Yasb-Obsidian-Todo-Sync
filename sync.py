"""
sync.py — Obsidian ↔ YASB Todo Sync
=====================================
Watches both todo.json (YASB) and your Obsidian .md task file for changes
and keeps them in sync bidirectionally, in real time.

Configuration lives in config.ini — edit that file, not this one.
Run setup.bat once to install dependencies and register the autostart task.
"""

import sys

# ── Python version check ──────────────────────────────────────────────────────
if sys.version_info < (3, 7):
    print("ERROR: Python 3.7 or higher is required.")
    print(f"       You are running Python {sys.version.split()[0]}")
    print("       Download the latest version at https://www.python.org/downloads/")
    print("       Make sure to check 'Add Python to PATH' during installation.")
    sys.exit(1)

import json
import time
import logging
import re
import hashlib
import random
import threading
import subprocess
import configparser
from typing import Optional, List
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Load config.ini ───────────────────────────────────────────────────────────

_HERE = Path(__file__).parent.resolve()
_CONFIG_PATH = _HERE / "config.ini"

if not _CONFIG_PATH.exists():
    print(f"ERROR: config.ini not found at {_CONFIG_PATH}")
    print("Please make sure config.ini is in the same folder as sync.py and your paths are filled in.")
    sys.exit(1)

_cfg = configparser.ConfigParser()
_cfg.read(_CONFIG_PATH, encoding="utf-8")

try:
    OBSIDIAN_MD   = Path(_cfg["paths"]["obsidian_md"]).expanduser()
    YASB_JSON     = Path(_cfg["paths"]["yasb_json"]).expanduser()
    DEBOUNCE_SECS = float(_cfg.get("settings", "debounce_secs", fallback="0.4"))
    LOG_FILE      = Path(_cfg.get("settings", "log_file", fallback=str(_HERE / "sync.log"))).expanduser()
except KeyError as e:
    print(f"ERROR: Missing required config key: {e}")
    print("Please check your config.ini has both obsidian_md and yasb_json filled in.")
    sys.exit(1)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Sync state ────────────────────────────────────────────────────────────────

_writing_json   = False
_writing_md     = False
_last_md_hash   = ""
_last_json_hash = ""


def _file_hash(path: Path) -> str:
    """MD5 of file contents, or empty string if file missing."""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _new_id() -> int:
    """Generate a unique integer ID matching YASB's format."""
    return random.randint(1_000_000_000, 9_999_999_999)

# ── MD ↔ JSON parsers / writers ───────────────────────────────────────────────

def _strip_wiki_links(text: str) -> str:
    """
    Convert Obsidian [[wiki links]] to plain text.
    [[Page Name]]       → Page Name
    [[Page|Alias]]      → Alias
    """
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text


def parse_md(path: Path, existing_tasks: Optional[List] = None) -> List:
    """
    Read the Obsidian .md file and return task dicts in YASB's format:
        id          int
        title       str
        description str
        category    str
        created_at  ISO datetime str
        completed   bool
        order       int

    Preserves IDs and metadata for existing tasks matched by title.
    Strips Obsidian [[wiki links]] to plain text.
    """
    tasks = []
    if not path.exists():
        log.warning("MD file not found: %s", path)
        return tasks

    existing_by_title = {}
    if existing_tasks:
        for t in existing_tasks:
            existing_by_title[t.get("title", "")] = t

    task_re = re.compile(r"^- \[( |x|X)\] (.+)$")

    with open(path, encoding="utf-8") as f:
        for order, line in enumerate(f):
            m = task_re.match(line.rstrip("\n"))
            if m:
                checked  = m.group(1).lower() == "x"
                title    = _strip_wiki_links(m.group(2).strip())
                existing = existing_by_title.get(title)
                tasks.append({
                    "id":          existing["id"] if existing else _new_id(),
                    "title":       title,
                    "description": existing.get("description", "") if existing else "",
                    "category":    existing.get("category", "default") if existing else "default",
                    "created_at":  existing.get("created_at", datetime.now().isoformat()) if existing else datetime.now().isoformat(),
                    "completed":   checked,
                    "order":       existing.get("order", order) if existing else order,
                })
    return tasks


def write_md(path: Path, tasks: List) -> None:
    """
    Write task list back to the Obsidian .md file.
    Unchecked tasks first, checked tasks below — matches YASB widget layout.
    """
    unchecked = [t for t in tasks if not t.get("completed")]
    checked   = [t for t in tasks if t.get("completed")]

    lines = []
    for t in unchecked:
        lines.append(f"- [ ] {t['title']}")
    for t in checked:
        lines.append(f"- [x] {t['title']}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")


def read_json(path: Path) -> List:
    """Read YASB todo.json; return empty list if missing or malformed."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log.error("Failed to read JSON: %s", e)
        return []


def write_json(path: Path, tasks: List) -> None:
    """Write task list to YASB todo.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

# ── Sync functions ────────────────────────────────────────────────────────────

def reload_yasb() -> None:
    """Tell YASB to reload via its CLI tool yasbc."""
    try:
        subprocess.Popen(
            ["yasbc", "reload", "--silent"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log.info("YASB reload triggered via yasbc")
    except FileNotFoundError:
        log.warning("yasbc not found in PATH — YASB reload skipped")
    except Exception as e:
        log.warning("YASB reload failed: %s", e)


def md_to_json() -> None:
    """Obsidian changed → update todo.json and reload YASB."""
    global _writing_json, _last_md_hash, _last_json_hash

    current_hash = _file_hash(OBSIDIAN_MD)
    if current_hash == _last_md_hash:
        log.debug("MD unchanged (hash match) — skipping")
        return
    _last_md_hash = current_hash

    log.info("MD → JSON sync triggered")
    existing = read_json(YASB_JSON)
    tasks = parse_md(OBSIDIAN_MD, existing_tasks=existing)
    _writing_json = True
    try:
        write_json(YASB_JSON, tasks)
        _last_json_hash = _file_hash(YASB_JSON)
        log.info("Wrote %d task(s) to todo.json", len(tasks))
        reload_yasb()
    finally:
        time.sleep(0.15)
        _writing_json = False


def json_to_md() -> None:
    """YASB changed → update Obsidian .md."""
    global _writing_md, _last_json_hash, _last_md_hash

    current_hash = _file_hash(YASB_JSON)
    if current_hash == _last_json_hash:
        log.debug("JSON unchanged (hash match) — skipping")
        return
    _last_json_hash = current_hash

    log.info("JSON → MD sync triggered")
    tasks = read_json(YASB_JSON)
    _writing_md = True
    try:
        write_md(OBSIDIAN_MD, tasks)
        _last_md_hash = _file_hash(OBSIDIAN_MD)
        log.info("Wrote %d task(s) to %s", len(tasks), OBSIDIAN_MD.name)
    finally:
        time.sleep(0.15)
        _writing_md = False

# ── Debounced file event handler ──────────────────────────────────────────────

class DebounceHandler(FileSystemEventHandler):
    def __init__(self, target_path: Path, callback):
        super().__init__()
        self.target   = target_path.resolve()
        self.callback = callback
        self._timer   = None

    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).resolve() != self.target:
            return
        self._schedule()

    def on_created(self, event):
        # Some editors (and Obsidian) do delete+create on save
        if event.is_directory:
            return
        if Path(event.src_path).resolve() != self.target:
            return
        self._schedule()

    def _schedule(self):
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(DEBOUNCE_SECS, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self):
        self.callback()
        self._timer = None


class MDHandler(DebounceHandler):
    def _fire(self):
        if _writing_md:
            log.debug("Skipping MD event — we wrote it")
            return
        super()._fire()


class JSONHandler(DebounceHandler):
    def _fire(self):
        if _writing_json:
            log.debug("Skipping JSON event — we wrote it")
            return
        super()._fire()

# ── Startup ───────────────────────────────────────────────────────────────────

def initial_sync() -> None:
    """Sync on startup. MD is always treated as source of truth."""
    global _last_md_hash, _last_json_hash

    md_exists   = OBSIDIAN_MD.exists()
    json_exists = YASB_JSON.exists()

    if md_exists and json_exists:
        log.info("Both files exist — MD is source of truth, syncing MD → JSON")
        md_to_json()
    elif md_exists and not json_exists:
        log.info("Only MD exists — creating todo.json from it")
        md_to_json()
    elif json_exists and not md_exists:
        log.info("Only JSON exists — creating MD from it")
        json_to_md()
    else:
        log.info("Neither file exists — creating empty todo.json")
        write_json(YASB_JSON, [])

    # Seed hashes so watchdog events don't immediately re-fire after startup
    _last_md_hash   = _file_hash(OBSIDIAN_MD)
    _last_json_hash = _file_hash(YASB_JSON)


def main():
    log.info("=" * 60)
    log.info("Obsidian <-> YASB Todo Sync starting")
    log.info("  MD   : %s", OBSIDIAN_MD)
    log.info("  JSON : %s", YASB_JSON)
    log.info("=" * 60)

    YASB_JSON.parent.mkdir(parents=True, exist_ok=True)
    initial_sync()

    observer = Observer()

    md_handler = MDHandler(OBSIDIAN_MD, md_to_json)
    observer.schedule(md_handler, str(OBSIDIAN_MD.parent), recursive=False)

    json_handler = JSONHandler(YASB_JSON, json_to_md)
    observer.schedule(json_handler, str(YASB_JSON.parent), recursive=False)

    observer.start()
    log.info("Watching for changes... (Ctrl+C to stop)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopped by user")
    finally:
        observer.stop()
        observer.join()
        log.info("Observer shut down cleanly")


if __name__ == "__main__":
    main()
