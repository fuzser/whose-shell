class WhoseShellError(Exception):
    """应用基础异常."""


class BackendUnavailableError(WhoseShellError):
    """后端不可用异常."""

