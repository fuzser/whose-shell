from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.bootstrap import create_main_window


def main() -> int:
    """启动桌面应用入口."""
    app = QApplication(sys.argv)
    app.setApplicationName("Whose Shell")
    app.setOrganizationName("Whose Shell")

    window = create_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

