# Whose Shell

[English](#english) | [中文](#中文)

## English

Whose Shell is an open-source desktop shell tool planned for Windows, Linux, and macOS. The goal is to provide local terminals, SSH sessions, visual file management, SFTP transfers, command history, performance monitoring, and cross-platform packaging in one lightweight desktop application.

This repository now contains the first desktop implementation pieces. The long-term implementation direction is described in [WhoseShell_Development_Plan.md](WhoseShell_Development_Plan.md).

### Planned Features

- Local shell sessions for PowerShell, CMD, Bash, and Zsh
- SSH remote terminal sessions with password and private key authentication
- Multi-tab terminal workspace
- Visual local and remote file management
- SFTP upload and download with transfer progress
- Command history, favorites, search, and re-run support
- Local and remote performance monitoring
- Connection management with secure secret storage
- Cross-platform packaging for Windows, Linux, and macOS

### Current Session Features

Whose Shell currently supports a basic session workflow:

- Open a local shell session from the File menu or Sessions dock.
- Open a new SSH shell from the File menu or Sessions dock.
- Save local and SSH connection metadata in SQLite.
- SSH connections can use a custom display name.
- Store SSH passwords through the operating system keyring instead of SQLite.
- Store SSH private-key passphrases through the operating system keyring instead of SQLite.
- Validate SSH host, port, username, authentication method, private key path, and default remote directory before or during connection.
- Show visible SSH connection, authentication, disconnect, reconnect, and default-directory messages in the terminal and status bar.
- Show saved connections and recent terminal sessions in the Sessions dock.
- Recent Sessions keeps only the latest 50 session records.
- The Sessions dock refresh button briefly clears the lists before reloading them, making refresh feedback visible.
- Right-click saved SSH connections to edit configuration or delete the connection.
- Right-click terminal tabs to close, disconnect, reconnect, or edit SSH configuration.
- Drag terminal tabs to reorder them.
- Closing a terminal tab removes it from the UI immediately before backend cleanup runs.
- Terminal tabs show a green dot when connected and a red dot when disconnected.
- The terminal cursor blinks, and connection lifecycle messages are rendered in color.
- Select visible terminal text by dragging with the left mouse button.
- Right-click inside the terminal to copy selected text, paste clipboard text, or clear the console display.
- Commands submitted from local and SSH terminals are saved to the History dock.
- The History dock supports search, host filtering, local/SSH filtering, favorites, and re-running commands in the active terminal.
- Favorites view shows one row per saved favorite command, so repeated history entries for the same command do not clutter the favorite list.
- The Settings panel stores terminal columns, rows, font family, font size, default local shell mode, restore-tabs behavior, and theme mode.
- Settings persist across restarts and affect new terminal sessions.
- The File Manager dock has a local file panel with path jump, refresh, parent-folder navigation, previous-folder navigation, and right-click file actions.
- The local file right-click menu supports new folder, new file, rename, delete, copy, and paste.
- Local delete actions require confirmation before files or folders are removed.
- The File Manager remote panel can open saved SSH connections for SFTP browsing, remote path jump, refresh, parent-folder navigation, and remote file metadata display.
- The remote file right-click menu supports new folder, rename, and delete with confirmation for saved SSH connections.
- Windows local shells use `pywinpty` / ConPTY when the `terminal-windows` extra is installed, so CMD, PowerShell, and native console programs receive real terminal input/output.
- Linux and macOS local shells use a POSIX PTY backend, so Bash, Zsh, and terminal UI programs receive real terminal input/output and window size updates.
- Keep recent terminal sessions collapsed by default to preserve space in the Sessions dock.
- Reopen the Sessions dock from the View menu after it has been closed.

#### Session Storage

Session and connection metadata are stored in the application data directory using `whose-shell.sqlite3`. Passwords are stored separately through `keyring`.

#### Basic Usage

```text
File -> New Local Shell
File -> New SSH Shell
View -> Sessions
View -> History
View -> Settings
File Manager dock -> Enter local path -> Press Enter
File Manager dock -> Use Refresh / Parent / Back navigation buttons
File Manager dock -> Right-click local item -> New Folder / New File / Rename / Delete / Copy / Paste
File Manager dock -> Select saved SSH connection -> Open SFTP browser
File Manager dock -> Enter remote path -> Press Enter
File Manager dock -> Right-click remote item -> New Folder / Rename / Delete
Sessions dock -> Double-click connection
History dock -> Search command -> Double-click or Run
```

#### SSH Authentication

SSH connections support password authentication and private-key authentication. Passwords and private-key passphrases are saved through the operating system keyring, not in SQLite.

The SSH dialog validates required fields before saving or opening a connection. Connection status, authentication failures, disconnects, reconnect attempts, reconnect failures, and default remote directory failures are shown visibly so connection problems are easier to diagnose.

#### Command History

The History dock records submitted single-line commands from local and SSH terminal sessions. It stores the command text, session metadata, connection type, host, working directory when available, and timestamp in SQLite.

Use the History dock to:

- Search recent commands.
- Filter by host or by local/SSH connection type.
- Mark command text as a favorite or remove it from favorites.
- Show only favorite commands as a compact unique list.
- Re-run a selected command in the currently active connected terminal.

Complex shell-specific command parsing is intentionally out of scope for v0.2.0. The current implementation focuses on reliable single-line command capture.

#### Settings

Use the Settings panel to configure default terminal columns and rows, terminal font family and size, default local shell selection, restore-tabs behavior, and theme mode.

The default local shell mode can stay on automatic detection or use an available manual override. If a saved manual shell is unavailable, Whose Shell falls back to automatic detection instead of breaking local terminal startup.

#### File Manager

Use the File Manager dock to browse local directories, jump to a local path, refresh the current folder, go to the parent folder, or go back to the previous folder.

Use the local file panel right-click menu to create a folder, create an empty file, rename a selected local item, delete a selected local item after confirmation, copy a selected local item, or paste it into the current or selected folder. Paste does not silently overwrite an existing target.

Use the remote file panel to select a saved SSH connection, open SFTP browsing, jump to a remote path, refresh the current folder, go to the parent folder, and view remote name, size, type, modified time, and permissions when the server provides them.

The remote file panel reuses saved SSH metadata and keyring-backed password or private-key passphrase loading. The remote right-click menu supports new folder, rename, and delete after confirmation. Remote SFTP operations run in worker threads so active terminal tabs remain separate from file listing failures.

Upload, download, transfer progress, and conflict handling remain planned v0.3.0 work for the transfer phase.

#### Known Limitations

- Complex shell-specific command parsing is out of scope for v0.2.0.
- Upload/download transfer queues and remote monitoring are roadmap items, not current features.
- Release artifacts are unsigned preview builds unless a future release explicitly states signing and notarization status.

On Windows, install the terminal extra before opening local shell sessions:

```powershell
pip install -e ".[terminal-windows]"
```

#### Release Artifact Builds

GitHub Actions can build unsigned preview artifacts from tags or manual workflow runs:

- `whose-shell-win-x64.exe`
- `whose-shell-linux-amd64.tar.gz`
- `whose-shell-macos-arm64.dmg`
- `whose-shell-win-arm64.exe` is available as an experimental manual workflow option.

Local PyInstaller builds use the same packaging entrypoint:

```powershell
python -m pip install -e ".[packaging,terminal-windows]"
python packaging/pyinstaller_build.py --target win-x64
```

The v0.2.0 Windows local production artifact was validated with:

- `.\.venv\Scripts\python.exe -m compileall app packaging`
- `.\.venv\Scripts\python.exe -m pytest`
- `.\.venv\Scripts\python.exe packaging\pyinstaller_build.py`
- Manual packaged-app startup and smoke testing by the developer.

### Technical Direction

Whose Shell is planned as a Python desktop application built around:

- PySide6 QtWidgets for the desktop UI
- A custom painted terminal widget instead of `QTextEdit` or `QPlainTextEdit`
- Cross-platform terminal backends behind a shared `TerminalBackend` interface
- `pywinpty` / ConPTY for Windows local shells
- `pty` and `select` for Linux and macOS local shells
- `asyncssh` for SSH and SFTP, with `paramiko` as a possible fallback
- `psutil` for local performance monitoring
- SQLite for command history and metadata
- `keyring` for passwords and private-key passphrases
- PyInstaller for packaging
- pytest for tests

### Architecture Overview

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

### Release Roadmap

#### v0.1 Terminal Core

- Main window
- Terminal tabs
- Custom terminal widget
- Local shell backend
- Basic ANSI support

#### v0.2 SSH and History

- SSH shell
- Connection manager
- SQLite command history
- Favorites
- Basic settings

#### v0.3 File Manager

- Local file browsing
- SFTP browsing
- Upload and download
- Transfer queue

#### v0.4 Monitoring

- Local CPU, memory, disk, and network monitoring
- Process table
- Remote Linux/macOS monitoring

#### v0.5 Packaging and Polish

- Windows build
- Linux build
- macOS build
- Themes
- Keyboard shortcuts
- Documentation

### Development Priorities

1. Create the project skeleton and packaging metadata.
2. Build the main window and dock layout.
3. Implement the custom terminal widget, terminal buffer, and ANSI parser.
4. Add local terminal backends for Windows, Linux, and macOS.
5. Add SSH, SFTP, command history, monitoring, settings, packaging, and tests.

### Design Principles

- Keep terminal parsing isolated and testable.
- Keep terminal backend interfaces stable across local and remote sessions.
- Never block the UI thread with shell IO, network IO, file scanning, monitoring, or database writes.
- Use Qt model/view classes for large file lists, process tables, history tables, and session trees.
- Store secrets through the operating system keyring, not plain text SQLite fields.

### License

Whose Shell is released under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## 中文

Whose Shell 是一个面向 Windows, Linux 和 macOS 的开源桌面 shell 工具。项目目标是在一个轻量桌面应用中提供本地终端, SSH 会话, 可视化文件管理, SFTP 传输, 命令历史, 性能监控和跨平台打包能力。

本仓库已经包含第一批桌面端实现。长期开发方向见 [WhoseShell_Development_Plan.md](WhoseShell_Development_Plan.md)。

### 计划功能

- 支持 PowerShell, CMD, Bash 和 Zsh 的本地 shell 会话
- 支持密码和私钥认证的 SSH 远程终端会话
- 多标签终端工作区
- 本地和远程文件的可视化管理
- 带进度显示的 SFTP 上传和下载
- 命令历史, 收藏, 搜索和重新运行
- 本地和远程性能监控
- 使用安全密钥存储的连接管理
- Windows, Linux 和 macOS 跨平台打包

### 当前 Session 功能

当前 Whose Shell 支持基础会话流程：

- 可以通过 File 菜单或 Sessions 面板打开本地 shell 会话。
- 可以通过 File 菜单或 Sessions 面板打开新的 SSH shell。
- 本地连接和 SSH 连接元数据会保存到 SQLite。
- SSH 连接可以设置自定义显示名称。
- SSH 密码通过操作系统 keyring 保存, 不写入 SQLite 明文字段。
- SSH 私钥 passphrase 也通过操作系统 keyring 保存, 不写入 SQLite 明文字段。
- SSH host, port, username, 认证方式, 私钥路径和默认远端目录会在连接前或连接过程中校验。
- SSH 连接, 认证失败, 断开, 重连, 重连失败和默认远端目录失败会在终端和状态栏中显示清晰提示。
- Sessions 面板会显示已保存连接和最近终端会话。
- Recent Sessions 只保留最新 50 条 session 记录。
- Sessions 面板刷新按钮会先短暂清空列表再重新加载, 让刷新反馈可见。
- 可以右键已保存 SSH 连接来修改配置或删除连接。
- 可以右键终端标签来关闭, 断开连接, 重新连接或修改 SSH 配置。
- 可以拖拽终端标签调整顺序。
- 关闭终端标签时会先从 UI 中移除标签, 再执行后端清理。
- 终端标签连接时显示绿色圆点, 断开时显示红色圆点。
- 终端输入光标会闪烁, 连接生命周期提示会用彩色文字显示。
- 可以在终端内按住鼠标左键拖拽选择当前可见文本。
- 可以在终端内右键复制选中文本, 粘贴剪贴板文本, 或清理 console 显示内容。
- 本地和 SSH 终端中提交的命令会保存到 History 面板。
- History 面板支持搜索, host 过滤, 本地/SSH 过滤, 收藏, 以及把命令重新运行到当前活动终端。
- Favorites 视图按收藏命令本身去重显示, 同一条命令在不同时间运行过多次时不会挤满收藏列表。
- Settings 面板会保存终端列数, 行数, 字体, 字号, 默认本地 shell 模式, restore tabs 行为和 theme mode。
- Settings 会在重启后保留, 并影响新建终端会话。
- File Manager 面板现在包含本地文件面板, 支持路径跳转, 刷新, 返回上一级文件夹, 返回之前的文件夹和右键文件操作。
- 本地文件右键菜单支持新建文件夹, 新建文件, 重命名, 删除, 复制和粘贴。
- 本地删除操作会先要求确认, 不会直接静默删除文件或文件夹。
- File Manager 的远程面板可以打开已保存 SSH 连接来进行 SFTP 浏览, 支持远程路径跳转, 刷新, 返回上一级目录和远程文件元数据显示。
- 远程文件右键菜单支持通过已保存 SSH 连接新建文件夹, 重命名和确认后删除。
- Windows 本地 shell 在安装 `terminal-windows` extra 后使用 `pywinpty` / ConPTY, 让 CMD, PowerShell 和 Windows 本地控制台程序获得真实终端输入输出。
- Linux 和 macOS 本地 shell 使用 POSIX PTY 后端, 让 Bash, Zsh 和终端 UI 程序获得真实终端输入输出和窗口尺寸更新。
- 最近终端会话默认折叠显示, 避免占用 Sessions 面板空间。
- 如果用户关闭了 Sessions 面板, 可以通过 View 菜单重新打开。

#### Session 存储

会话和连接元数据会保存在应用数据目录中的 `whose-shell.sqlite3`。密码会通过 `keyring` 单独保存。

#### 基础用法

```text
File 菜单 -> New Local Shell
File 菜单 -> New SSH Shell
View 菜单 -> Sessions
View 菜单 -> History
View 菜单 -> Settings
File Manager 面板 -> 输入本地路径 -> 按 Enter
File Manager 面板 -> 使用 Refresh / Parent / Back 导航按钮
File Manager 面板 -> 右键本地项目 -> New Folder / New File / Rename / Delete / Copy / Paste
File Manager 面板 -> 选择已保存 SSH 连接 -> Open SFTP browser
File Manager 面板 -> 输入远程路径 -> 按 Enter
File Manager 面板 -> 右键远程项目 -> New Folder / Rename / Delete
Sessions 面板 -> 双击连接
History 面板 -> 搜索命令 -> 双击或点击 Run
```

#### SSH 认证

SSH 连接支持密码认证和私钥认证。密码和私钥 passphrase 都通过操作系统 keyring 保存, 不写入 SQLite。

SSH 对话框会在保存或打开连接前校验必要字段。连接状态, 认证失败, 断开, 重连尝试, 重连失败和默认远端目录失败都会显示出来, 方便定位连接问题。

#### 命令历史

History 面板会记录本地和 SSH 终端会话中提交的单行命令。命令文本, session 元数据, 连接类型, host, 可用时的工作目录和时间戳会保存到 SQLite。

可以在 History 面板中：

- 搜索最近命令。
- 按 host 或本地/SSH 连接类型过滤。
- 收藏命令文本或取消收藏。
- 只显示收藏命令, 并以去重后的紧凑列表展示。
- 把选中的命令重新运行到当前活动且已连接的终端。

复杂的 shell 专属命令解析不属于 v0.2.0 范围。当前实现优先保证可靠的单行命令捕获。

#### Settings

Settings 面板可配置默认终端列数和行数, 终端字体和字号, 默认本地 shell 选择, restore tabs 行为和 theme mode。

默认本地 shell 可以保持自动检测, 也可以选择当前系统可用的手动覆盖项。如果保存的手动 shell 不再可用, Whose Shell 会回退到自动检测, 不会阻断本地终端启动。

#### File Manager

File Manager 面板可以浏览本地目录, 跳转到本地路径, 刷新当前文件夹, 返回上一级文件夹, 或返回之前的文件夹。

本地文件面板的右键菜单可以新建文件夹, 新建空文件, 重命名选中的本地项目, 在确认后删除选中的本地项目, 复制选中的本地项目, 或粘贴到当前文件夹/选中文件夹。粘贴不会静默覆盖已有目标。

远程文件面板可以选择已保存 SSH 连接, 打开 SFTP 浏览, 跳转到远程路径, 刷新当前目录, 返回上一级目录, 并在服务端提供时显示远程名称, 大小, 类型, 修改时间和权限。

远程文件面板复用已保存 SSH 元数据, 并通过 keyring 加载密码或私钥 passphrase。远程右键菜单支持新建文件夹, 重命名和确认后删除。远程 SFTP 操作运行在 worker 线程中, 文件列表失败不会和活动终端标签共用生命周期。

上传, 下载, 传输进度和冲突处理仍属于 v0.3.0 transfer 阶段。

#### 已知限制

- 复杂 shell 专属命令解析不属于 v0.2.0 范围。
- 上传/下载传输队列和远程监控是路线图项目, 不是当前功能。
- 除非后续 release 明确说明签名和 notarization 状态, 当前 release artifacts 属于未签名 preview 构建。

Windows 下打开本地 shell 前, 先安装终端 extra：

```powershell
pip install -e ".[terminal-windows]"
```

#### 发布构建产物

GitHub Actions 可以在 tag 或手动 workflow 运行时生成未签名的预览构建产物：

- `whose-shell-win-x64.exe`
- `whose-shell-linux-amd64.tar.gz`
- `whose-shell-macos-arm64.dmg`
- `whose-shell-win-arm64.exe` 作为手动 workflow 的实验选项提供。

本地 PyInstaller 构建使用同一个打包入口：

```powershell
python -m pip install -e ".[packaging,terminal-windows]"
python packaging/pyinstaller_build.py --target win-x64
```

v0.2.0 Windows 本地生产构建已通过以下验证：

- `.\.venv\Scripts\python.exe -m compileall app packaging`
- `.\.venv\Scripts\python.exe -m pytest`
- `.\.venv\Scripts\python.exe packaging\pyinstaller_build.py`
- 开发人员手动启动 packaged app 并完成 smoke testing。

### 技术方向

Whose Shell 计划作为 Python 桌面应用构建, 主要技术包括：

- 使用 PySide6 QtWidgets 构建桌面 UI
- 使用自绘终端组件, 不把 `QTextEdit` 或 `QPlainTextEdit` 作为最终终端实现
- 在统一的 `TerminalBackend` 接口后封装跨平台终端后端
- Windows 本地 shell 使用 `pywinpty` / ConPTY
- Linux 和 macOS 本地 shell 使用 `pty` 和 `select`
- SSH 和 SFTP 优先使用 `asyncssh`, `paramiko` 可作为备选
- 本地性能监控使用 `psutil`
- 命令历史和元数据使用 SQLite
- 密码和私钥 passphrase 使用 `keyring`
- 使用 PyInstaller 打包
- 使用 pytest 做测试

### 架构概览

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

UI 线程只负责 Qt 渲染和用户交互。Shell IO, SSH, SFTP, 文件扫描, 性能监控和数据库写入应运行在 worker 线程或 async 服务中, 并通过 Qt signals 和 slots 与 UI 通信。

### 发布路线图

#### v0.1 Terminal Core

- 主窗口
- 终端标签页
- 自定义终端组件
- 本地 shell 后端
- 基础 ANSI 支持

#### v0.2 SSH and History

- SSH shell
- 连接管理
- SQLite 命令历史
- 收藏
- 基础设置

#### v0.3 File Manager

- 本地文件浏览
- SFTP 浏览
- 上传和下载
- 传输队列

#### v0.4 Monitoring

- 本地 CPU, 内存, 磁盘和网络监控
- 进程表
- 远程 Linux/macOS 监控

#### v0.5 Packaging and Polish

- Windows 构建
- Linux 构建
- macOS 构建
- 主题
- 快捷键
- 文档

### 开发优先级

1. 创建项目骨架和打包元数据。
2. 构建主窗口和 dock 布局。
3. 实现自定义终端组件, 终端缓冲区和 ANSI 解析器。
4. 添加 Windows, Linux 和 macOS 的本地终端后端。
5. 添加 SSH, SFTP, 命令历史, 监控, 设置, 打包和测试。

### 设计原则

- 保持终端解析逻辑隔离且可测试。
- 保持本地和远程 session 的终端后端接口稳定。
- 不要用 shell IO, 网络 IO, 文件扫描, 性能监控或数据库写入阻塞 UI 线程。
- 大型文件列表, 进程表, 历史表和 session 树使用 Qt model/view 类。
- 密钥通过操作系统 keyring 保存, 不写入 SQLite 明文字段。

### 许可证

Whose Shell 使用 Apache License 2.0 发布。详情见 [LICENSE](LICENSE)。
