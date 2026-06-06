# Whose Shell

Whose Shell is an open-source desktop shell tool planned for Windows, Linux, and macOS. The goal is to provide local terminals, SSH sessions, visual file management, SFTP transfers, command history, performance monitoring, and cross-platform packaging in one lightweight desktop application.

This repository is currently in the planning stage. The implementation direction is described in [WhoseShell_Development_Plan.md](WhoseShell_Development_Plan.md).

## Planned Features

- Local shell sessions for PowerShell, CMD, Bash, and Zsh
- SSH remote terminal sessions with password and private key authentication
- Multi-tab terminal workspace
- Visual local and remote file management
- SFTP upload and download with transfer progress
- Command history, favorites, search, and re-run support
- Local and remote performance monitoring
- Connection management with secure secret storage
- Cross-platform packaging for Windows, Linux, and macOS

## Technical Direction

Whose Shell is planned as a Python desktop application built around:

- PySide6 QtWidgets for the desktop UI
- A custom painted terminal widget instead of `QTextEdit` or `QPlainTextEdit`
- Cross-platform terminal backends behind a shared `TerminalBackend` interface
- `pywinpty` / ConPTY for Windows local shells
- `pty`, `select`, and async services for Linux and macOS shells
- `asyncssh` for SSH and SFTP, with `paramiko` as a possible fallback
- `psutil` for local performance monitoring
- SQLite for command history and metadata
- `keyring` for passwords and private-key passphrases
- PyInstaller for packaging
- pytest for tests

## Architecture Overview

```text
whose-shell/
+-- app/
|   +-- main.py
|   +-- bootstrap.py
|   +-- ui/
|   |   +-- main_window.py
|   |   +-- terminal/
|   |   +-- files/
|   |   +-- monitor/
|   |   +-- history/
|   |   +-- sessions/
|   |   +-- settings/
|   +-- core/
|   +-- backends/
|   +-- storage/
|   +-- common/
+-- tests/
+-- packaging/
+-- pyproject.toml
+-- README.md
+-- LICENSE
```

The UI thread should only handle Qt rendering and user interaction. Shell IO, SSH, SFTP, file scanning, monitoring, and database writes should run in worker threads or async services and communicate with the UI through Qt signals and slots.

## Release Roadmap

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

## Development Priorities

1. Create the project skeleton and packaging metadata.
2. Build the main window and dock layout.
3. Implement the custom terminal widget, terminal buffer, and ANSI parser.
4. Add local terminal backends for Windows, Linux, and macOS.
5. Add SSH, SFTP, command history, monitoring, settings, packaging, and tests.

## Design Principles

- Keep terminal parsing isolated and testable.
- Keep terminal backend interfaces stable across local and remote sessions.
- Never block the UI thread with shell IO, network IO, file scanning, monitoring, or database writes.
- Use Qt model/view classes for large file lists, process tables, history tables, and session trees.
- Store secrets through the operating system keyring, not plain text SQLite fields.

## License

Whose Shell is released under the MIT License. See [LICENSE](LICENSE) for details.
