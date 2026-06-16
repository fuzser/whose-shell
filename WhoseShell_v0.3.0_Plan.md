# Whose Shell v0.3.0 Plan

## 1. Version Goal

Whose Shell v0.3.0 focuses on completing the first production-usable File Manager workflow.

The target is to move the application from a terminal, SSH, history, and settings tool into a practical desktop shell that can inspect and move files between local and remote environments:

- Local files should be browsable from the File Manager dock.
- SSH connections should be reusable for remote SFTP browsing.
- Users should be able to upload and download files with visible progress.
- File operations should be safe, explicit, and recoverable where possible.
- Transfer state should be visible without blocking terminal interaction.

This version should not expand into remote performance monitoring, process management, plugin systems, cloud sync, AI command generation, or a terminal renderer rewrite. Those remain later roadmap items.

## 2. Current Baseline

The current implementation baseline includes the completed v0.2.0 scope.

Already available:

- Local shell tabs.
- SSH shell tabs.
- Saved local and SSH connection metadata.
- SSH password and private-key passphrase storage through keyring.
- SSH connection validation, reconnect handling, default remote directory handling, and visible status feedback.
- Sessions dock with saved connections and recent sessions.
- Command history with search, host filtering, local/SSH filtering, favorites, and re-run support.
- Persistent Settings panel for terminal size, font, default local shell, restore-tabs behavior, and theme mode.
- Custom terminal buffer, ANSI parsing, selection, copy, paste, resize, and reconnect behavior.
- Windows pywinpty / ConPTY local shell support.
- Linux and macOS POSIX PTY local shell support.
- GitHub Actions artifact builds for Windows x64, Linux amd64, and macOS arm64.

Current File Manager baseline:

- `FileManagerDock` exists as a two-panel dock.
- The local panel uses `QFileSystemModel`.
- The remote panel is still a placeholder.
- `app/backends/sftp_backend.py` is still a placeholder.
- `app/core/file_manager.py` is still a placeholder.
- There is no transfer queue, transfer persistence, conflict handling, or real SFTP model yet.

## 3. In Scope

### 3.1 File Manager Foundation

Replace the current File Manager placeholder with a structured local and remote file management surface.

Required work:

- Keep the two-panel File Manager layout:
  - local panel
  - remote panel
  - transfer queue/status area
- Keep local browsing based on Qt model/view APIs.
- Add path bars for local and remote panels.
- Add refresh actions for both panels.
- Add clear empty, loading, disconnected, and error states.
- Add visible connection context for the remote panel.
- Ensure all file scanning and remote IO stays outside the UI thread.

Expected behavior:

- Opening the File Manager does not block the terminal.
- The local panel can browse directories.
- The remote panel clearly shows when no SSH/SFTP connection is selected.
- Errors are visible in the panel and status bar.

### 3.2 Local File Browsing

Make the local file panel useful before remote operations are added.

Required work:

- Display local directory contents with name, size, type, and modified time where practical.
- Support local path jump.
- Support local refresh.
- Support local new folder.
- Support local rename.
- Support local delete with explicit confirmation.
- Support opening the selected local directory as the upload source.
- Avoid destructive file operations without confirmation.

Expected behavior:

- Local path changes update the view and path bar.
- Invalid or inaccessible paths show a clear message.
- New folder, rename, and delete update the view after completion.
- Local actions do not interfere with active terminal sessions.

### 3.3 SFTP Backend and Remote Browsing

Implement the first real SFTP backend using the existing SSH/asyncssh direction.

Required work:

- Build an `SftpBackend` around `asyncssh`.
- Reuse saved SSH connection metadata and keyring-backed secrets.
- Support password authentication.
- Support private-key authentication with keyring-backed passphrase loading.
- List remote directories.
- Fetch remote file metadata:
  - name
  - type
  - size
  - modified time when available
  - permissions when available
- Add a `RemoteFileModel(QAbstractTableModel)` or equivalent model/view abstraction.
- Support remote path jump.
- Support remote refresh.
- Support remote new folder.
- Support remote rename.
- Support remote delete with explicit confirmation.
- Surface connection, permission, missing path, and network errors clearly.

Expected behavior:

- A saved SSH connection can be opened for SFTP browsing without re-entering stored secrets.
- Remote directory listing does not block the UI thread.
- Authentication and permission failures are visible and actionable.
- Remote browsing is separated from the terminal backend lifecycle so a failed file listing does not crash or corrupt an active terminal tab.

### 3.4 Upload, Download, and Transfer Queue

Add the first safe transfer workflow.

Required work:

- Add transfer queue data structures and UI.
- Support upload from local panel to remote panel.
- Support download from remote panel to local panel.
- Show transfer progress.
- Show transfer status:
  - queued
  - running
  - completed
  - failed
  - canceled, if cancellation is implemented
- Show source path, target path, direction, transferred bytes, total bytes when known, and error message when failed.
- Add conflict handling for existing target files:
  - skip
  - overwrite
  - rename/copy as new name
- Keep transfers off the UI thread.
- Refresh affected panels after successful transfer.

Expected behavior:

- Upload and download work for individual files.
- Directory transfer can remain out of scope unless implemented safely with recursive progress.
- Existing target conflicts do not silently overwrite files.
- Failed transfers leave a readable failure reason.
- Terminal input, SSH terminal output, History, and Settings remain responsive during transfers.

### 3.5 Safety, Persistence, and Limits

Keep v0.3.0 safe and bounded.

Required work:

- Add a `file_transfers` table only if transfer history or restart visibility is needed in this version.
- Do not store remote passwords or private-key passphrases in SQLite.
- Do not silently delete local or remote files.
- Apply conservative size and directory recursion limits if recursive operations are introduced.
- Use explicit status messages for long-running operations.
- Document known limitations.

Expected behavior:

- Secrets remain in keyring.
- SQLite stores only metadata.
- Destructive operations require confirmation.
- Transfer failures are recoverable by retrying manually.

### 3.6 Documentation

Update user-facing documentation after implementation.

Required README updates:

- v0.3.0 current features.
- File Manager usage.
- Local file browsing operations.
- SFTP browsing behavior.
- Upload and download workflow.
- Transfer queue behavior.
- Conflict handling behavior.
- Known limitations.
- English first, Chinese second.

## 4. Out of Scope

Do not include these in v0.3.0:

- Remote performance monitoring.
- Process table or remote process management.
- Full recursive directory synchronization.
- Background scheduled sync.
- Cloud sync.
- File diff/merge tools.
- Terminal renderer rewrite.
- Advanced shell-specific command parsing.
- Full xterm private protocol support.
- Plugin system.
- AI command generation.
- Stable-release signing and notarization, unless handled as a separate release task.

## 5. Proposed File Changes

Expected files to change:

- `app/backends/sftp_backend.py`
  - Replace placeholder with asyncssh-backed SFTP operations.
- `app/core/file_manager.py`
  - Coordinate local file actions, remote file actions, and transfer queue operations.
- `app/ui/files/file_manager_dock.py`
  - Replace the placeholder remote panel with a real local/remote file manager surface.
- `app/common/models.py`
  - Add file item, remote file item, transfer item, transfer status, and conflict policy models if useful.
- `app/storage/migrations.py`
  - Add `file_transfers` schema only if v0.3.0 stores transfer history or restart-visible transfer records.
- `app/storage/repositories.py`
  - Add transfer repository only if transfer metadata is persisted.
- `app/core/session_manager.py`
  - Expose saved SSH connection and secret-loading helpers needed by SFTP without duplicating secret logic.
- `app/core/app_context.py`
  - Wire file manager services if a shared manager is introduced.
- `app/ui/main_window.py`
  - Wire File Manager actions, status messages, and dock lifecycle behavior.
- `README.md`
  - Update bilingual user documentation after implementation.
- `tests/`
  - Add focused tests for SFTP backend contracts, remote model behavior, transfer queue state, conflict handling, and non-blocking manager behavior.

Files that should not be modified unless specifically needed:

- `.agents/skills/*/SKILL.md`
- release checklist skill files
- unrelated terminal renderer internals
- unrelated History and Settings behavior

## 6. Five-Phase Delivery Plan

v0.3.0 should be delivered in five controlled phases. Each phase should leave the application runnable and should have its own verification gate before moving on.

### Phase 1: File Manager Data and Service Foundation [done]

Goal:

- Define the file manager contracts before building UI behavior.
- Keep existing terminal, SSH, History, and Settings behavior unchanged.

Primary scope:

- Add file item and transfer item model types where they reduce ambiguity.
- Define transfer status and conflict policy values.
- Decide whether transfer records are in-memory only or persisted in SQLite.
- If persistence is needed, add an idempotent `file_transfers` migration and repository.
- Build the initial `FileManager` service boundary.
- Add local filesystem helper methods behind the service boundary.

Expected file areas:

- `app/common/models.py`
- `app/core/file_manager.py`
- `app/storage/migrations.py`, only if transfer persistence is included
- `app/storage/repositories.py`, only if transfer persistence is included
- `tests/`

Acceptance gate:

- File and transfer models have clear fields and status transitions.
- Migrations are idempotent if introduced.
- Existing v0.2.0 databases can open without data loss.
- Local filesystem helper tests cover valid paths, invalid paths, and permission-style failures where practical.
- `compileall` and focused service/storage tests pass.

### Phase 2: Local File Panel [todo]

Goal:

- Make the local half of File Manager useful and safe.

Primary scope:

- Replace the minimal local tree with a polished local file panel.
- Add local path bar.
- Add refresh.
- Add local new folder.
- Add local rename.
- Add local delete with confirmation.
- Add clear status messages.
- Keep focus and caret behavior correct: text caret appears only in editable controls and the terminal.

Expected file areas:

- `app/ui/files/file_manager_dock.py`
- `app/core/file_manager.py`
- `app/ui/main_window.py`
- `tests/`

Acceptance gate:

- Local browsing works from the File Manager dock.
- Path jump updates the local view.
- Refresh reloads the local view.
- New folder, rename, and delete work with explicit user intent.
- Invalid local paths and failed file operations show clear messages.
- Existing terminal input, selection, copy, History, and Settings behavior are not regressed.

### Phase 3: SFTP Backend and Remote File Panel [todo]

Goal:

- Replace the remote placeholder with real SFTP browsing.

Primary scope:

- Implement asyncssh-backed `SftpBackend`.
- Reuse saved SSH connection metadata.
- Load secrets through existing keyring helpers.
- Add remote directory listing.
- Add remote file metadata mapping.
- Add remote file model.
- Add remote path bar and refresh.
- Add connection selection or open-from-saved-connection flow.
- Add remote new folder, rename, and delete with confirmation.

Expected file areas:

- `app/backends/sftp_backend.py`
- `app/core/file_manager.py`
- `app/ui/files/file_manager_dock.py`
- `app/core/session_manager.py`
- `app/storage/secrets.py`, only if new helper boundaries are needed
- `tests/`

Acceptance gate:

- Password-backed saved SSH connections can open SFTP browsing.
- Private-key-backed saved SSH connections can open SFTP browsing.
- Remote listing works without blocking the UI.
- Remote path jump and refresh work.
- Remote new folder, rename, and delete work with confirmation.
- Bad host, bad auth, missing path, permission failure, and network failure produce clear visible messages.
- A failed SFTP operation does not corrupt active SSH terminal tabs.

### Phase 4: Upload, Download, Conflict Handling, and Transfer Queue [todo]

Goal:

- Deliver the core v0.3.0 file transfer workflow.

Primary scope:

- Add transfer queue UI.
- Add upload from local panel to remote panel.
- Add download from remote panel to local panel.
- Add progress reporting.
- Add completed and failed transfer states.
- Add conflict handling:
  - skip
  - overwrite
  - rename/copy as new name
- Add retry behavior only if it can be implemented without ambiguous state.
- Refresh affected local or remote panels after successful transfer.

Expected file areas:

- `app/core/file_manager.py`
- `app/backends/sftp_backend.py`
- `app/ui/files/file_manager_dock.py`
- `app/common/models.py`
- `app/storage/repositories.py`, only if transfer history is persisted
- `tests/`

Acceptance gate:

- Upload of a single file works.
- Download of a single file works.
- Progress is visible while transfer is running.
- Existing target files are not overwritten silently.
- Failed transfers show a readable reason.
- The UI remains responsive during transfers.
- Terminal, History, Settings, and Sessions behavior remain stable during active transfers.

### Phase 5: Stabilization, Documentation, and Release Readiness [todo]

Goal:

- Freeze v0.3.0 scope, harden file workflows, update documentation, and prepare release readiness without publishing prematurely.

Primary scope:

- Run automated tests.
- Add or adjust focused tests for final file manager wiring.
- Run manual local and SFTP smoke checks.
- Update README in English and Chinese.
- Update known limitations.
- Confirm version bump requirements.
- Confirm release artifact rules.
- Keep signing and notarization listed as future stable-release work unless implemented separately.

Expected file areas:

- `README.md`
- `pyproject.toml`, only when ready to bump to `0.3.0`
- `tests/`
- release notes draft, only when preparing release

Acceptance gate:

- `compileall` passes.
- `pytest` passes.
- Local File Manager manual checks pass on Windows.
- SFTP browsing manual checks pass.
- Upload and download manual checks pass.
- Conflict handling manual checks pass.
- Packaged Windows app can open the File Manager and start a local shell.
- README matches implemented behavior.
- GitHub Actions required artifact builds pass before release:
  - Windows x64
  - Linux amd64
  - macOS arm64
- Release remains unpublished until the release checklist is satisfied.

## 7. Testing Plan

Automated checks:

```powershell
.\.venv\Scripts\python.exe -m compileall app packaging
.\.venv\Scripts\python.exe -m pytest
```

Focused test areas:

- File manager service handles valid and invalid local paths.
- Local new folder, rename, and delete behavior is isolated and testable.
- SFTP backend maps remote entries into stable file item models.
- SFTP backend surfaces authentication, permission, missing path, and network failures.
- Remote file model renders entries in stable order and handles empty directories.
- Transfer queue transitions through queued, running, completed, and failed states.
- Conflict policy handling prevents silent overwrites.
- Transfer progress events update queue state without touching QWidget instances from worker code.
- Existing SSH terminal reconnect and command history behavior remain intact.

Manual checks:

- Open File Manager.
- Browse local directories.
- Jump to a local path.
- Refresh local files.
- Create, rename, and delete a local test folder after confirmation.
- Open remote SFTP browsing from a saved password SSH connection.
- Open remote SFTP browsing from a saved private-key SSH connection.
- Browse remote directories.
- Jump to a remote path.
- Refresh remote files.
- Create, rename, and delete a remote test folder after confirmation.
- Upload a small file.
- Download a small file.
- Try an upload/download conflict and verify skip, overwrite, and rename behavior.
- Disconnect or fail the remote connection and verify a clear error state.
- Confirm active terminal tabs remain usable while File Manager operations run.
- Validate Windows packaged build can start a local shell and open File Manager.

## 8. Release Readiness Criteria

v0.3.0 is ready when:

- Local file browsing works from the File Manager dock.
- Remote SFTP browsing works through saved SSH connections.
- Upload and download work for single files.
- Transfer progress and failure states are visible.
- Conflict handling prevents silent overwrite.
- Destructive local and remote file operations require explicit confirmation.
- Secrets remain stored through keyring, not SQLite.
- Terminal, SSH, History, Settings, and Sessions behavior are not regressed.
- README is updated in English and Chinese.
- `compileall` passes.
- `pytest` passes.
- Required GitHub Actions artifact builds pass:
  - Windows x64
  - Linux amd64
  - macOS arm64
- Release notes include known limitations and unsigned preview warnings if released as preview.

## 9. Versioning Notes

When the implementation is complete:

- Project version should become `0.3.0`.
- Git tag should be `v0.3.0`.
- GitHub Release title should be `Whose Shell v0.3.0`.
- Required artifact names remain:
  - `whose-shell-win-x64.exe`
  - `whose-shell-linux-amd64.tar.gz`
  - `whose-shell-macos-arm64.dmg`

Do not create or publish the release until local validation, tests, packaged artifact smoke testing, and required CI artifact builds have passed.
