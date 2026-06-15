# Whose Shell v0.2.0 Plan

## 1. Version Goal

Whose Shell v0.2.0 focuses on completing the SSH, command history, and basic settings workflow.

The target is to move the application from a usable terminal preview toward a daily-use desktop shell:

- SSH connections should be easier to configure, reconnect, and diagnose.
- Commands typed in terminals should be recorded, searchable, favoritable, and runnable again.
- User settings should be stored persistently and affect terminal defaults.

This version should not expand into full SFTP file management, transfer queues, or remote monitoring. Those remain later roadmap items.

## 2. Current Baseline

The current released baseline is v0.1.1.

Already available:

- Local shell tabs.
- SSH shell tabs.
- Saved local and SSH connection metadata.
- SSH password storage through keyring.
- Sessions dock with saved connections and recent sessions.
- Active terminal tab restore.
- Custom terminal buffer, ANSI parsing, selection, copy, paste, resize, and reconnect behavior.
- Windows pywinpty / ConPTY local shell support.
- Linux and macOS POSIX PTY local shell support.
- GitHub Actions artifact builds for Windows x64, Linux amd64, and macOS arm64.

Completed v0.2.0 scope:

- Command history panel now supports single-line command capture, search, filtering, favorites, and re-run actions.
- Settings panel now persists terminal defaults and restore behavior.
- SQLite schema now includes commands, favorites, and settings.
- SSH private-key passphrase handling now uses keyring, matching password storage behavior.
- SSH connection, authentication, disconnect, reconnect, and default-directory feedback are now visible to users.
- Monitor and SFTP panels are intentionally incomplete.

## 3. In Scope

### 3.1 SSH Completion

Implement a stronger SSH workflow around the existing SSH terminal support.

Required work:

- Validate SSH connection fields before saving or opening:
  - display name
  - host
  - port
  - username
  - authentication method
  - private key path when key authentication is used
- Store private-key passphrases through keyring.
- Never store passwords or private-key passphrases in SQLite.
- Show clear terminal and status bar messages for:
  - connection start
  - successful connection
  - authentication failure
  - connection failure
  - disconnect
  - reconnect start
  - reconnect failure
- Apply default remote directory after connecting.
- Display a clear warning if the default directory cannot be entered.
- Keep open tab titles in sync after editing saved SSH connection names.
- Keep existing reconnect behavior that preserves previous SSH output.

### 3.2 Command History

Replace the placeholder History dock with a usable command history workflow.

Required work:

- Add a `commands` table.
- Add a `favorites` table.
- Capture submitted terminal commands from the input path.
- Record at least:
  - command text
  - session id
  - connection id
  - connection type
  - host
  - cwd, when available
  - started timestamp
  - exit code, if available
- Support local and SSH sessions.
- Start with reliable single-line command capture.
- Avoid complex shell-specific parsing in this version.

History UI requirements:

- Replace the placeholder label with a table.
- Show recent commands newest first.
- Add text search.
- Add connection or host filtering.
- Add favorite and unfavorite actions.
- Show favorites separately or through a filter.
- Double-click or context-menu action to re-run a command in the active terminal.
- Refresh history after a command is recorded.

### 3.3 Basic Settings

Replace the placeholder Settings panel with persistent settings.

Required work:

- Add a `settings` table.
- Add repository helpers for reading and writing settings.
- Add Settings UI to the main window menu or dock.
- Store and apply:
  - default terminal columns
  - default terminal rows
  - terminal font family
  - terminal font size
  - default local shell preference, with automatic system detection as the default
  - restore tabs on startup
  - theme mode: `system`, `light`, or `dark`

Expected behavior:

- Settings persist after restart.
- Font changes apply to open terminals when practical.
- Default terminal size applies before new backends start.
- Default local shell preference automatically reads system information and adapts to the best available shell.
- Manual shell preference overrides are validated and fall back safely when unavailable.
- Restore-tabs setting controls whether active tabs are saved and restored.
- Settings that require restart should say so clearly.

### 3.4 Regression Hardening

Do not rewrite the terminal renderer in this version, but protect the current behavior.

Required regression checks:

- Windows PowerShell input works.
- Windows CMD input works.
- Backspace deletes one character.
- Ctrl+C interrupts local commands.
- SSH connect, disconnect, and reconnect work.
- SSH reconnect keeps previous output visible.
- Resize does not truncate restored text.
- ANSI colors still render.
- Chinese and other wide characters still align and copy correctly.
- Selection and copy preserve expected text.
- App restart restores or does not restore tabs according to settings.

### 3.5 Documentation

Update user-facing documentation after implementation.

Required README updates:

- v0.2.0 current features.
- SSH authentication and keyring behavior.
- Command history usage.
- Favorites and re-run behavior.
- Settings usage.
- Known limitations.
- English first, Chinese second.

## 4. Out of Scope

Do not include these in v0.2.0:

- Full SFTP file manager.
- Upload and download transfer queue.
- Remote file conflict handling.
- Remote monitoring.
- Process table beyond any existing local monitor work.
- Advanced shell-specific command parsing.
- Full xterm private protocol support.
- Plugin system.
- Cloud sync.
- AI command generation.
- Stable-release signing and notarization.

## 5. Proposed File Changes

Expected files to change:

- `app/storage/migrations.py`
  - Add `commands`, `favorites`, and `settings` schema.
- `app/storage/repositories.py`
  - Add command history, favorites, and settings repositories.
- `app/storage/secrets.py`
  - Add private-key passphrase storage helpers.
- `app/common/models.py`
  - Add models for command records, favorite commands, settings, and SSH auth details if needed.
- `app/core/session_manager.py`
  - Load and save SSH passphrases.
  - Expose command recording and setting access where appropriate.
- `app/core/terminal_manager.py`
  - Coordinate command lifecycle events if command recording belongs at manager level.
- `app/ui/terminal/terminal_view.py`
  - Emit submitted command events from the input path.
  - Support re-running commands from History.
- `app/ui/history/history_dock.py`
  - Replace placeholder UI with table, search, filters, favorites, and re-run actions.
- `app/ui/settings/settings_panel.py`
  - Replace placeholder module with a real settings widget.
- `app/ui/sessions/ssh_connection_dialog.py`
  - Improve validation and passphrase inputs.
- `app/ui/main_window.py`
  - Wire History, Settings, and command re-run actions.
- `README.md`
  - Update bilingual user documentation after implementation.
- `tests/`
  - Add focused tests for schema, repositories, command capture, settings persistence, and SSH config handling.

Files that should not be modified unless specifically needed:

- `.agents/skills/*/SKILL.md`
- release checklist skill files
- unrelated packaging logic

## 6. Five-Phase Delivery Plan

v0.2.0 should be delivered in five controlled phases. Each phase should leave the application runnable and should have its own verification gate before moving on.

### Phase 1: Data Foundation [done]

Goal:

- Add the persistent storage needed by History, Favorites, Settings, and SSH passphrases.
- Keep the UI behavior unchanged except for any safe internal wiring required by repositories.

Primary scope:

- Add `commands`, `favorites`, and `settings` tables.
- Add command history repository methods.
- Add favorite command repository methods.
- Add settings repository methods and default values.
- Add private-key passphrase helpers to the secret store.
- Add model types only where they reduce ambiguity in repository and UI contracts.

Expected file areas:

- `app/storage/migrations.py`
- `app/storage/repositories.py`
- `app/storage/secrets.py`
- `app/common/models.py`
- `tests/`

Acceptance gate:

- Migrations are idempotent.
- Existing v0.1.1 databases can open without data loss.
- Commands can be inserted, searched, listed, and favorited through repository tests.
- Settings return defaults when no row exists and persist changes.
- SSH passphrase helper tests prove secrets are not stored in SQLite.
- `compileall` and focused repository tests pass.

### Phase 2: Basic Settings [done]

Goal:

- Replace the Settings placeholder with persistent settings that affect terminal startup and restore behavior.

Primary scope:

- Build the first real Settings panel.
- Add controls for terminal columns, terminal rows, font family, font size, default local shell mode, restore tabs on startup, and theme mode.
- Treat default local shell preference as a Phase 2 fix, not just a setting field:
  - use `auto` as the default setting value;
  - read the current platform, environment variables, and available executable paths before creating a local terminal;
  - on Windows, automatically prefer available shells in this order: `pwsh.exe`, `powershell.exe`, `cmd.exe`;
  - on Linux and macOS, automatically prefer the detected `$SHELL`, then `/bin/sh`;
  - show the resolved automatic shell in the Settings UI so the user can see what will be used;
  - allow a manual override only from shells available on the current system;
  - if a saved manual shell is no longer available, show a clear status message, reset to `auto`, and fall back to the detected platform default.
- Wire settings into new terminal creation.
- Respect the restore-tabs setting during startup and shutdown.
- Apply font settings to open terminals when practical.
- Mark restart-required settings clearly when immediate application is not practical.

Expected file areas:

- `app/ui/settings/settings_panel.py`
- `app/ui/main_window.py`
- `app/core/session_manager.py`
- `app/core/terminal_manager.py`
- `app/ui/terminal/terminal_view.py`
- `tests/`

Acceptance gate:

- Settings can be changed from the UI and survive restart.
- New local and SSH terminals use the configured default size and font.
- New local terminals automatically use the best detected shell when shell mode is `auto`.
- New local terminals use the manual shell override only when that shell is available on the current system.
- Invalid or unavailable saved shell preferences do not break terminal startup, reset to `auto`, and fall back visibly.
- Restore tabs can be enabled and disabled.
- Existing terminal behavior is not regressed.
- Focus behavior remains correct: text caret appears only in editable controls and the terminal.

### Phase 3: Command History and Favorites [done]

Goal:

- Replace the History placeholder with a usable command history workflow.

Primary scope:

- Capture submitted single-line commands from the terminal input path.
- Record commands for local and SSH sessions.
- Refresh History after commands are recorded.
- Build the History dock table.
- Add search.
- Add connection or host filtering.
- Add favorite and unfavorite actions.
- Add re-run action into the active terminal.

Expected file areas:

- `app/ui/terminal/terminal_view.py`
- `app/ui/history/history_dock.py`
- `app/ui/main_window.py`
- `app/core/session_manager.py`
- `app/core/terminal_manager.py`
- `app/storage/repositories.py`
- `tests/`

Acceptance gate:

- Running a local command records it in History.
- Running an SSH command records it in History.
- Search and filtering work.
- Favorite and unfavorite work.
- Re-run sends the command to the active terminal without changing unrelated tabs.
- Empty commands and prompt-editing artifacts are not recorded as useful commands.
- Complex shell-specific parsing remains out of scope and is documented as a known limitation.

### Phase 4: SSH Completion and Error Feedback [done]

Goal:

- Finish the SSH workflow promised by v0.2.0 without destabilizing the terminal core.

Primary scope:

- Improve SSH dialog validation.
- Add passphrase input for private-key authentication.
- Save and load SSH passphrases through keyring.
- Improve visible connection, authentication, disconnect, and reconnect messages.
- Apply default remote directory after connection.
- Warn when the default remote directory cannot be entered.
- Preserve existing reconnect output behavior.
- Keep open tab titles synced after saved SSH connection edits.

Expected file areas:

- `app/ui/sessions/ssh_connection_dialog.py`
- `app/backends/ssh_backend.py`
- `app/storage/secrets.py`
- `app/core/session_manager.py`
- `app/core/terminal_manager.py`
- `app/ui/main_window.py`
- `tests/`

Acceptance gate:

- Password SSH works.
- Private-key SSH works.
- Private-key passphrase is stored through keyring and not SQLite.
- Bad host, bad port, bad auth, and missing key path produce clear user-visible messages.
- Reconnect failure leaves the tab in a coherent disconnected state.
- Default remote directory success and failure are visible.
- Existing SSH restore and reconnect content preservation still work.

### Phase 5: Stabilization, Documentation, and Release Readiness [done]

Goal:

- Freeze the feature scope, harden regressions, update documentation, and prepare the release without publishing prematurely.

Primary scope:

- Run terminal regression checks.
- Add or adjust focused tests for the final wiring.
- Update README in English and Chinese.
- Update known limitations.
- Confirm version bump requirements.
- Confirm release artifact rules.
- Keep signing and notarization listed as future stable-release work unless implemented.

Expected file areas:

- `README.md`
- `pyproject.toml`, only when ready to bump to `0.2.0`
- `tests/`
- release notes draft, only when preparing release

Acceptance gate:

- `compileall` passes.
- `pytest` passes.
- Manual local terminal checks pass on Windows.
- SSH manual checks pass.
- History and Settings manual checks pass.
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

- Migration creates new tables idempotently.
- Command repository can create, list, search, and favorite commands.
- Settings repository returns defaults and persists changes.
- Secret store saves and deletes SSH passphrases through keyring helpers.
- History re-run sends the expected command text to the active terminal.
- Restore-tabs setting changes startup restore behavior.
- Default local shell preference detects the platform default shell automatically, supports valid manual overrides, resets unavailable overrides to `auto`, and does not break local terminal startup.

Manual checks:

- Open local PowerShell.
- Run several commands and confirm they appear in History.
- Search and filter History.
- Favorite and unfavorite commands.
- Re-run a command from History.
- Open SSH connection with password authentication.
- Open SSH connection with private-key authentication.
- Test SSH reconnect after disconnect.
- Confirm passphrases are not stored in SQLite.
- Change terminal font and restart.
- Toggle restore tabs and restart.
- Validate Windows packaged build can start a local shell.

## 8. Release Readiness Criteria

v0.2.0 is ready when:

- SSH password and private-key passphrase handling is secure.
- SSH failures are visible and understandable.
- Command history works for local and SSH terminals.
- Favorites and re-run work from the History dock.
- Settings persist and affect new terminal sessions.
- Restore-tabs behavior follows the setting.
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

- Project version should become `0.2.0`.
- Git tag should be `v0.2.0`.
- GitHub Release title should be `Whose Shell v0.2.0`.
- Required artifact names remain:
  - `whose-shell-win-x64.exe`
  - `whose-shell-linux-amd64.tar.gz`
  - `whose-shell-macos-arm64.dmg`

Do not create or publish the release until local validation, tests, and required CI artifact builds have passed.
