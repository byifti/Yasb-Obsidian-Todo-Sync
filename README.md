# Obsidian ↔ YASB Todo Sync

A lightweight background script that keeps [YASB](https://github.com/amnweb/yasb)'s built-in Todo widget in sync with an Obsidian `.md` task file — bidirectionally, in real time.

## How it works

```
Obsidian  ──writes──▶  To Do List.md  ──▶  sync.py  ──▶  todo.json  ──▶  YASB
YASB      ──writes──▶  todo.json      ──▶  sync.py  ──▶  To Do List.md  ──▶  Obsidian
```

`sync.py` watches both files using `watchdog`. Any change in either is reflected in the other within ~400ms. When Obsidian changes are detected, YASB is automatically reloaded via `yasbc reload`. An MD5 hash guard and ignore-flag system prevent infinite sync loops.

On startup, the `.md` file is always treated as the source of truth.

---

## Requirements

- **Python 3.7+** installed and added to your system PATH
  - Download at [python.org/downloads](https://www.python.org/downloads/)
  - During installation, check **"Add Python to PATH"**
- **YASB** installed with the built-in Todo widget enabled
- **watchdog** Python library (installed automatically by `setup.bat`)

---

## Setup

### 1. Configure your paths

Open `config.ini` and replace the placeholder paths with your own:

```ini
[paths]
obsidian_md = C:\path\to\your\Obsidian\Vault\To Do List.md
yasb_json   = C:\Users\<username>\.config\yasb\todo.json
```

- `obsidian_md` — full path to your Obsidian `.md` task file
- `yasb_json` — replace `<username>` with your Windows username. This is YASB's default `todo.json` location.

### 2. Configure YASB

Add the Todo widget to your `config.yaml` if you haven't already:

```yaml
todo:
  type: "yasb.todo.TodoWidget"
  options:
    label: "<span>\uf0ae</span> {count}/{completed}"
    callbacks:
      on_left: toggle_menu
```

Then add `- todo` to your bar's widget list and reload YASB.

### 3. Run setup

Right-click `setup.bat` → **Run as Administrator**.

This will:
- Check your `config.ini` paths are filled in
- Install the `watchdog` dependency via pip
- Register `sync.py` as a Windows startup task

### 4. Start syncing

Run `start_sync.bat` to start immediately without rebooting.

Check `sync.log` in the same folder to confirm it's running — you should see startup lines and then silence until a file changes.

---

## File structure

```
YasbPlusObsidianTodo/
├── sync.py          ← main sync script
├── config.ini       ← edit this with your paths
├── setup.bat        ← first-time setup (run once as Admin)
├── start_sync.bat   ← manual launcher
├── .gitignore
├── sync.log         ← auto-created at runtime
└── README.md
```

---

## Obsidian task format

Standard Obsidian checkbox syntax:

```markdown
- [ ] Buy groceries
- [ ] Reply to emails
- [x] Finish project proposal
```

Obsidian `[[wiki links]]` are automatically stripped to plain text on sync.

Unchecked tasks appear first in both YASB and the `.md` file. Checked tasks appear below.

> **Note:** The `.md` file should contain only task lines. Headings, notes, or other content are ignored on read and will be removed on write-back from YASB.

---

## Configuration options

All options live in `config.ini`:

| Key | Description | Default |
|-----|-------------|---------|
| `paths.obsidian_md` | Full path to your Obsidian task file | *(required)* |
| `paths.yasb_json` | Full path to YASB's todo.json | *(required)* |
| `settings.debounce_secs` | Delay before syncing after a change | `0.4` |
| `settings.log_file` | Path to log file | `sync.log` in script folder |

---

## Troubleshooting

- **`pip install failed`** — Make sure Python is installed and added to PATH. Re-run the installer from [python.org](https://www.python.org/downloads/) and check "Add Python to PATH".
- **Nothing syncing?** — Check `sync.log` for errors. Make sure the script is running (`pythonw` process in Task Manager).
- **YASB not updating from Obsidian?** — Make sure `yasbc` is in your PATH — it's installed alongside YASB.
- **Obsidian not updating from YASB?** — Obsidian hot-reloads open files, changes should appear within a second.
- **Sync loop?** — Shouldn't happen, but if it does increase `debounce_secs` in `config.ini`.

---

## Version history

- **v1.0** — Bidirectional sync, debounce, loop prevention, auto YASB reload, Task Scheduler autostart
- **v2.0** *(planned)* — Subtask support, custom theming
