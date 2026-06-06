# Whose Shell Development Plan

## 1. Product Goal

Whose Shell is an open-source desktop shell tool for Windows, Linux, and macOS.

The application should provide:

- Local shell sessions
- SSH remote terminal sessions
- Visual local and remote file management
- SFTP upload and download
- Performance monitoring
- Command history
- Multi-tab sessions
- Connection management
- Cross-platform packaging

## 2. Technical Direction

Use PySide6 QtWidgets for the desktop UI and Python for the application core.

Recommended stack:

- UI: PySide6 QtWidgets
- Terminal UI: Custom painted terminal widget
- Windows terminal backend: pywinpty / ConPTY
- Linux and macOS terminal backend: pty / select / asyncio
- SSH and SFTP: asyncssh preferred, paramiko as fallback
- Monitoring: psutil
- Database: SQLite
- Secret storage: keyring
- Packaging: PyInstaller
- Testing: pytest

The core principle is that the UI thread only handles rendering and interaction. Shell IO, SSH, SFTP, file scanning, monitoring, and database writes must run in worker threads or async services.

## 3. Architecture

```text
whose-shell/
├─ app/
│  ├─ main.py
│  ├─ bootstrap.py
│  ├─ ui/
│  │  ├─ main_window.py
│  │  ├─ layout/
│  │  ├─ terminal/
│  │  │  ├─ terminal_widget.py
│  │  │  ├─ terminal_view.py
│  │  │  ├─ terminal_buffer.py
│  │  │  ├─ ansi_parser.py
│  │  │  └─ keymap.py
│  │  ├─ files/
│  │  ├─ monitor/
│  │  ├─ history/
│  │  ├─ sessions/
│  │  └─ settings/
│  ├─ core/
│  │  ├─ app_context.py
│  │  ├─ session_manager.py
│  │  ├─ terminal_manager.py
│  │  ├─ file_manager.py
│  │  ├─ monitor_manager.py
│  │  └─ event_bus.py
│  ├─ backends/
│  │  ├─ terminal_base.py
│  │  ├─ local_windows_backend.py
│  │  ├─ local_posix_backend.py
│  │  ├─ ssh_backend.py
│  │  └─ sftp_backend.py
│  ├─ storage/
│  │  ├─ db.py
│  │  ├─ repositories.py
│  │  ├─ migrations.py
│  │  └─ secrets.py
│  └─ common/
│     ├─ models.py
│     ├─ signals.py
│     ├─ errors.py
│     └─ platform.py
├─ tests/
├─ packaging/
├─ pyproject.toml
├─ README.md
└─ LICENSE
```

## 4. Main Window Layout

Use `QMainWindow` as the root container.

```text
QMainWindow
├─ MenuBar
├─ ToolBar
├─ Left Dock
│  ├─ Sessions
│  ├─ Favorites
│  └─ History
├─ Center
│  └─ Terminal Tabs
├─ Bottom Dock
│  ├─ File Manager
│  ├─ Monitor
│  └─ Transfer Queue
└─ StatusBar
```

Recommended QtWidgets:

- Main window: `QMainWindow`
- Split layout: `QSplitter`
- Dock panels: `QDockWidget`
- Terminal tabs: `QTabWidget`
- File views: `QTreeView` / `QTableView`
- History table: `QTableView` + `QAbstractTableModel`
- Session tree: `QTreeView`
- Monitoring charts: lightweight custom widgets painted with `QPainter`

## 5. Terminal Design

Do not use `QTextEdit` or `QPlainTextEdit` as the final terminal implementation.

Build a custom terminal widget with `QAbstractScrollArea` or `QWidget`.

```text
TerminalWidget
├─ TerminalBuffer
├─ AnsiParser
├─ KeyMapper
├─ SelectionManager
├─ ScrollbackBuffer
└─ TerminalBackend
```

`TerminalBuffer` should maintain a character grid.

Each cell should store:

- Character
- Foreground color
- Background color
- Bold state
- Italic state
- Underline state
- Inverse state
- Dirty state

Required terminal capabilities:

- Text output
- Cursor movement
- Newline and carriage return
- Backspace
- Clear screen
- Clear line
- Scrollback
- Resize
- ANSI 8 colors
- ANSI 16 colors
- ANSI 256 colors
- Ctrl+C
- Ctrl+D
- Ctrl+L
- Tab
- Arrow keys
- Home/End
- PageUp/PageDown
- Function keys
- Vim, nano, top, htop, and less compatibility as a long-term target

Do not attempt to implement every xterm private protocol in the first release, but the base ANSI/VT behavior should be designed as a real terminal state machine.

## 6. Terminal Backend Interface

All terminal backends should expose the same interface.

```python
class TerminalBackend:
    def start(self) -> None:
        ...

    def write(self, data: bytes) -> None:
        ...

    def resize(self, cols: int, rows: int) -> None:
        ...

    def stop(self) -> None:
        ...
```

Backend output should be emitted through Qt signals:

```python
output_received = Signal(bytes)
closed = Signal(int)
error = Signal(str)
```

Backend implementations:

- Windows: `LocalWindowsBackend` using pywinpty / ConPTY
- Linux/macOS: `LocalPosixBackend` using pty
- SSH: `SshTerminalBackend` using asyncssh

## 7. Threading Model

Use this split:

```text
UI Thread:
- All QtWidgets
- TerminalWidget paintEvent
- User input
- Selection
- Menu and toolbar actions

Worker Threads / Async Services:
- Local shell IO
- SSH IO
- SFTP transfer
- File scanning
- Performance sampling
- SQLite write queue
```

Rules:

- Worker threads must not directly touch QWidget instances.
- Workers communicate with the UI using Qt signals and slots.
- Expensive work must never run in the UI thread.
- Database writes should use a queue to avoid blocking interaction.

## 8. File Manager

Use a two-panel file manager.

```text
FileManagerDock
├─ LocalPanel
└─ RemotePanel
```

Local files:

- Use `QFileSystemModel`
- Display with `QTreeView` or `QTableView`

Remote files:

- Use a custom `RemoteFileModel(QAbstractTableModel)`
- Load data through SFTP backend

Required features:

- Local browsing
- Remote SFTP browsing
- Upload
- Download
- Delete
- Rename
- New folder
- Refresh
- Path jump
- Drag upload
- Transfer queue
- Conflict handling
- Transfer progress

## 9. Performance Monitoring

Local monitoring:

- Use `psutil`

Remote monitoring:

- Use SSH commands and platform-specific parsers

Linux:

- `/proc`
- `df`
- `free`
- `ps`

macOS:

- `vm_stat`
- `df`
- `ps`
- `top -l 1`

Monitor panel:

```text
MonitorDock
├─ CPU
├─ Memory
├─ Disk
├─ Network
└─ Process Table
```

Use lightweight `QPainter` charts instead of heavy rendering libraries.

## 10. Command History

Use SQLite for command history and metadata.

Suggested tables:

- `connections`
- `sessions`
- `commands`
- `favorites`
- `file_transfers`
- `settings`

Suggested `commands` fields:

```text
id
session_id
connection_id
shell_type
host
cwd
command_text
exit_code
started_at
ended_at
duration_ms
```

Required features:

- Automatic recording
- Search
- Filter by host
- Filter by session
- Favorite commands
- Re-run command from history
- Export history

Command extraction can start by analyzing the terminal input stream, then later be improved for PowerShell, Bash, Zsh, and Fish.

## 11. Connection Management

Supported connection types:

- Local PowerShell
- Local CMD
- Local Bash
- Local Zsh
- SSH password login
- SSH private key login

Connection configuration:

- Host
- Port
- Username
- Authentication method
- Private key path
- Default directory
- Environment variables
- Terminal size
- Theme

Secret handling:

- Store metadata in SQLite.
- Store passwords and private-key passphrases through `keyring`.
- Never store secrets as plain text in SQLite.

## 12. Implementation Order

Recommended order:

1. Project skeleton and packaging metadata
2. Main window and dock layout
3. Custom terminal widget
4. Terminal buffer
5. ANSI parser
6. Windows pywinpty backend
7. Linux/macOS pty backend
8. SSH terminal backend
9. SQLite history and connection management
10. Local file manager
11. SFTP remote file manager
12. Transfer queue
13. Local performance monitoring
14. Remote performance monitoring
15. Settings, themes, and shortcuts
16. PyInstaller packaging
17. pytest unit and integration tests

## 13. Release Milestones

### v0.1 Terminal Core

- Main window
- Terminal tabs
- Custom terminal widget
- Local shell backend
- Basic ANSI support

### v0.2 SSH and History

- SSH shell
- Connection manager
- SQLite command history
- Favorites
- Basic settings

### v0.3 File Manager

- Local file browsing
- SFTP browsing
- Upload and download
- Transfer queue

### v0.4 Monitoring

- Local CPU, memory, disk, and network monitoring
- Process table
- Remote Linux/macOS monitoring

### v0.5 Packaging and Polish

- Windows build
- Linux build
- macOS build
- Themes
- Keyboard shortcuts
- Documentation

## 14. Key Risks

Terminal emulation is the hardest part of the project.

Main risks:

- ANSI/VT parser complexity
- Full-screen TUI compatibility
- Wide character handling
- Clipboard and selection behavior
- Resize behavior
- Cross-platform PTY differences
- SSH latency and reconnect handling
- Large directory SFTP performance

Risk control:

- Keep terminal parsing isolated.
- Test ANSI parser independently.
- Keep backend interface stable.
- Use model/view classes for large file and history tables.
- Avoid blocking the UI thread.

## 15. Non-Goals for the First Release

Avoid these in the first production-quality release:

- GPU-heavy rendering
- Complex animations
- Plugin system
- Cloud sync
- Full xterm private protocol coverage
- Built-in collaborative terminal sharing
- AI command generation

These can be added after the shell, SSH, SFTP, monitoring, and history features are stable.

## 16. Final Direction

The project should be built as:

```text
PySide6 QtWidgets
+ custom painted terminal widget
+ cross-platform TerminalBackend
+ asyncssh/SFTP
+ psutil
+ SQLite/keyring
```

This direction supports the target feature set while keeping the UI responsive, lightweight, and suitable for a serious cross-platform desktop tool.
