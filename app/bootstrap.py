from __future__ import annotations

from app.core.app_context import AppContext
from app.ui.main_window import MainWindow


def create_main_window() -> MainWindow:
    """创建应用上下文和主窗口."""
    context = AppContext.create_default()
    return MainWindow(context)

