from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal

from app.common.models import ManagedTerminalSession, SshConnectionConfig
from app.core.session_manager import SessionManager


class TerminalRuntimeState(str, Enum):
    """终端运行态, 用于统一驱动 UI 和 session 落库."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class _TerminalRuntime:
    managed_session: ManagedTerminalSession
    state: TerminalRuntimeState
    close_recorded: bool = False


class TerminalManager(QObject):
    """统一管理活动终端的启动, 断开, 重连和关闭."""

    state_changed = Signal(int, str)
    closed = Signal(int, int)
    status_message = Signal(str)

    def __init__(self, session_manager: SessionManager) -> None:
        super().__init__()
        self._session_manager = session_manager
        self._runtimes: dict[int, _TerminalRuntime] = {}

    def create_local_terminal(self) -> ManagedTerminalSession:
        managed_session = self._session_manager.create_local_terminal()
        self._register(managed_session)
        return managed_session

    def create_ssh_terminal(self, config: SshConnectionConfig) -> ManagedTerminalSession:
        managed_session = self._session_manager.create_ssh_terminal(config)
        self._register(managed_session)
        return managed_session

    def create_terminal_from_connection(self, connection_id: int) -> ManagedTerminalSession:
        managed_session = self._session_manager.create_terminal_from_connection(connection_id)
        self._register(managed_session)
        return managed_session

    def start(self, session_id: int) -> None:
        runtime = self._runtime(session_id)
        if runtime.state in {TerminalRuntimeState.CONNECTING, TerminalRuntimeState.CONNECTED}:
            return
        self.status_message.emit(f"Session #{session_id} connecting.")
        self._set_state(session_id, TerminalRuntimeState.CONNECTING)
        runtime.managed_session.backend.start()

    def disconnect(self, session_id: int) -> bool:
        runtime = self._runtime(session_id)
        if runtime.state in {
            TerminalRuntimeState.DISCONNECTING,
            TerminalRuntimeState.DISCONNECTED,
            TerminalRuntimeState.CLOSING,
            TerminalRuntimeState.CLOSED,
        }:
            return False
        self.status_message.emit(f"Session #{session_id} disconnecting.")
        self._set_state(session_id, TerminalRuntimeState.DISCONNECTING)
        runtime.managed_session.backend.stop()
        self._record_closed(session_id)
        return True

    def mark_disconnected(self, session_id: int, exit_code: int | None = None) -> None:
        """把已注册但未启动的终端标记为断开, 常用于恢复历史标签页."""
        self._record_closed(session_id, exit_code)
        self._set_state(session_id, TerminalRuntimeState.DISCONNECTED)

    def reconnect(self, session_id: int) -> None:
        runtime = self._runtime(session_id)
        if runtime.state in {
            TerminalRuntimeState.CONNECTING,
            TerminalRuntimeState.CONNECTED,
            TerminalRuntimeState.DISCONNECTING,
            TerminalRuntimeState.CLOSING,
        }:
            return
        runtime.close_recorded = False
        self._session_manager.reopen_session(session_id)
        self.status_message.emit(f"Session #{session_id} reconnecting.")
        self._set_state(session_id, TerminalRuntimeState.CONNECTING)
        runtime.managed_session.backend.start()

    def refresh_ssh_connection_config(self, connection_id: int) -> None:
        config = self._session_manager.ssh_config_from_connection(connection_id)
        for runtime in self._runtimes.values():
            if runtime.managed_session.session.connection_id != connection_id:
                continue
            reconfigure = getattr(runtime.managed_session.backend, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(config)

    def close(self, session_id: int) -> bool:
        runtime = self._runtime(session_id)
        was_active = runtime.state not in {
            TerminalRuntimeState.DISCONNECTED,
            TerminalRuntimeState.CLOSED,
        }
        self._set_state(session_id, TerminalRuntimeState.CLOSING)
        self._record_closed(session_id)
        if was_active:
            runtime.managed_session.backend.stop()
        if not was_active:
            self._set_state(session_id, TerminalRuntimeState.CLOSED)
            self.closed.emit(session_id, 0)
            self.unregister(session_id)
        return was_active

    def unregister(self, session_id: int) -> None:
        self._runtimes.pop(session_id, None)

    def is_connected(self, session_id: int) -> bool:
        runtime = self._runtimes.get(session_id)
        return runtime is not None and runtime.state == TerminalRuntimeState.CONNECTED

    def _register(self, managed_session: ManagedTerminalSession) -> None:
        session_id = managed_session.session.id
        if session_id in self._runtimes:
            return
        runtime = _TerminalRuntime(
            managed_session=managed_session,
            state=TerminalRuntimeState.DISCONNECTED,
        )
        self._runtimes[session_id] = runtime
        managed_session.backend.connected.connect(lambda session_id=session_id: self._handle_connected(session_id))
        managed_session.backend.closed.connect(
            lambda exit_code, session_id=session_id: self._handle_backend_closed(session_id, exit_code)
        )
        managed_session.backend.error.connect(
            lambda message, session_id=session_id: self._handle_backend_error(session_id, message)
        )

    def _runtime(self, session_id: int) -> _TerminalRuntime:
        runtime = self._runtimes.get(session_id)
        if runtime is None:
            raise ValueError(f"Terminal runtime is not registered: {session_id}")
        return runtime

    def _handle_connected(self, session_id: int) -> None:
        runtime = self._runtimes.get(session_id)
        if runtime is None:
            return
        runtime.close_recorded = False
        self.status_message.emit(f"Session #{session_id} connected.")
        self._set_state(session_id, TerminalRuntimeState.CONNECTED)

    def _handle_backend_closed(self, session_id: int, exit_code: int) -> None:
        runtime = self._runtimes.get(session_id)
        if runtime is None:
            return
        self._record_closed(session_id, exit_code)
        target_state = (
            TerminalRuntimeState.CLOSED
            if runtime.state == TerminalRuntimeState.CLOSING
            else TerminalRuntimeState.DISCONNECTED
        )
        self._set_state(session_id, target_state)
        self.closed.emit(session_id, exit_code)
        if target_state == TerminalRuntimeState.CLOSED:
            self.unregister(session_id)
        else:
            self.status_message.emit(f"Session #{session_id} disconnected.")

    def _handle_backend_error(self, session_id: int, message: str) -> None:
        self.status_message.emit(f"Session #{session_id}: {message}")

    def _record_closed(self, session_id: int, exit_code: int | None = None) -> None:
        runtime = self._runtime(session_id)
        if runtime.close_recorded:
            return
        runtime.close_recorded = True
        self._session_manager.close_session(session_id, exit_code)

    def _set_state(self, session_id: int, state: TerminalRuntimeState) -> None:
        runtime = self._runtime(session_id)
        if runtime.state == state:
            return
        runtime.state = state
        self.state_changed.emit(session_id, state.value)
