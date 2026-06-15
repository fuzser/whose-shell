<a name=release-notes-top></a>

[English](#user-content-release-notes-english) | [中文](#user-content-release-notes-chinese)

<a name=release-notes-english></a>

## Release Notes English

Version: v0.2.0
Date: 2026-06-15
Type: preview

### Main Features

- Added persistent command history for local and SSH terminal sessions.
- Added History search, host filtering, local/SSH filtering, favorites, and re-run support.
- Added persistent Settings for terminal size, font, local shell mode, restore-tabs behavior, and theme mode.
- Improved SSH validation for host, port, username, authentication method, private key path, and default remote directory.
- Added private-key passphrase storage through the operating system keyring.
- Improved visible SSH connection, authentication, disconnect, reconnect, and default-directory feedback.
- Kept SSH reconnect behavior aligned with the existing restored-output preservation workflow.

### Bug Fixes And Hardening

- Hardened Windows local shell detection and fallback behavior.
- Preserved command favorites as a unique favorite-command view instead of duplicating repeated history entries.
- Added focused tests for command history, settings runtime behavior, secret storage, SSH phase 4 behavior, and packaging helpers.
- Validated the Windows local production artifact with packaged-app smoke testing.

### Breaking Changes

- No intentional breaking changes.

### Supported Artifacts

- `whose-shell-win-x64.exe`
- `whose-shell-linux-amd64.tar.gz`
- `whose-shell-macos-arm64.dmg`

### Optional Or Experimental Artifacts

- `whose-shell-win-arm64.exe` may be produced by manual workflow runs, but Windows ARM64 remains experimental and non-blocking.

### Known Limitations

- These preview artifacts are unsigned. Windows and macOS may show security warnings.
- Complex shell-specific command parsing is out of scope for v0.2.0.
- SFTP file management, transfer queues, and remote monitoring are roadmap items, not v0.2.0 features.
- Stable-release signing and notarization are still future release work.

### Install Or Run Notes

- Windows users can run the unsigned preview executable directly after acknowledging any operating system warning.
- Local Windows shell support depends on the packaged pywinpty helper binaries included in the artifact.

[Back to top](#user-content-release-notes-top)

<a name=release-notes-chinese></a>

## 发布说明中文

版本: v0.2.0
日期: 2026-06-15
类型: preview

### 主要功能

- 新增本地和 SSH 终端会话的持久化命令历史。
- 新增 History 搜索, host 过滤, 本地/SSH 过滤, 收藏和重新运行支持。
- 新增持久化 Settings, 支持终端尺寸, 字体, 本地 shell 模式, restore-tabs 行为和 theme mode。
- 改进 SSH host, port, username, 认证方式, 私钥路径和默认远端目录校验。
- 新增通过操作系统 keyring 保存 SSH 私钥 passphrase。
- 改进 SSH 连接, 认证, 断开, 重连和默认远端目录反馈。
- 保持 SSH reconnect 与既有 restored-output 保留流程一致。

### 修复和稳定性增强

- 加强 Windows 本地 shell 检测和 fallback 行为。
- Favorites 以唯一收藏命令视图展示, 不再被重复历史记录挤满。
- 增加命令历史, settings runtime, secret storage, SSH Phase 4 行为和 packaging helper 的聚焦测试。
- 已通过 Windows 本地生产构建 packaged-app smoke testing。

### 破坏性变更

- 无有意引入的破坏性变更。

### 支持的构建产物

- `whose-shell-win-x64.exe`
- `whose-shell-linux-amd64.tar.gz`
- `whose-shell-macos-arm64.dmg`

### 可选或实验性构建产物

- 手动 workflow 运行时可以生成 `whose-shell-win-arm64.exe`, 但 Windows ARM64 仍是实验性非阻断目标。

### 已知限制

- These preview artifacts are unsigned. Windows and macOS may show security warnings.
- 复杂 shell 专属命令解析不属于 v0.2.0 范围。
- SFTP 文件管理, 传输队列和远程监控是路线图项目, 不是 v0.2.0 功能。
- 稳定版签名和 notarization 仍是后续 release 工作。

### 安装和运行说明

- Windows 用户可以在确认操作系统安全提醒后直接运行 unsigned preview exe。
- Windows 本地 shell 支持依赖构建产物中包含的 pywinpty helper binaries。

[Back to top](#user-content-release-notes-top)
