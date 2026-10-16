import os
import sys
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PyQt6.QtCore import Qt, QObject, pyqtSignal

class StartupManager:
    """Manages Windows startup registry entry for D IP Monitor."""
    REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "DIPMonitor"

    @classmethod
    def is_startup_enabled(cls) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_KEY, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, cls.APP_NAME)
            winreg.CloseKey(key)
            return bool(val)
        except Exception:
            return False

    @classmethod
    def set_startup_enabled(cls, enabled: bool):
        if sys.platform != "win32":
            return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_KEY, 0, winreg.KEY_SET_VALUE)
            if enabled:
                # If frozen, use the executable path. Otherwise use python with main.py
                if getattr(sys, 'frozen', False):
                    exe_path = f'"{sys.executable}"'
                else:
                    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
                    exe_path = f'"{sys.executable}" "{main_py}"'
                winreg.SetValueEx(key, cls.APP_NAME, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, cls.APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Error updating Windows startup registry: {e}")


class SystemTrayManager(QObject):
    """
    Manages the D IP Monitor System Tray icon, dynamic status badges,
    context menu, and native Windows toast notifications.
    """
    restore_requested = pyqtSignal()
    toggle_hud_requested = pyqtSignal()
    mute_toggled = pyqtSignal(bool)
    exit_requested = pyqtSignal()

    def __init__(self, base_icon_path: str, parent=None):
        super().__init__(parent)
        self.base_icon_path = base_icon_path
        self.tray_icon = QSystemTrayIcon(parent)
        self.is_offline_state = False

        self._init_menu()
        self.update_tray_icon(has_offline_hosts=False)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _init_menu(self):
        self.menu = QMenu()

        self.action_restore = QAction("Open D IP Monitor", self.menu)
        self.action_restore.triggered.connect(self.restore_requested.emit)
        self.menu.addAction(self.action_restore)

        self.action_hud = QAction("Toggle Floating HUD", self.menu)
        self.action_hud.triggered.connect(self.toggle_hud_requested.emit)
        self.menu.addAction(self.action_hud)

        self.action_mute = QAction("Mute Sound Alerts", self.menu)
        self.action_mute.setCheckable(True)
        self.action_mute.toggled.connect(self.mute_toggled.emit)
        self.menu.addAction(self.action_mute)

        self.menu.addSeparator()

        self.action_exit = QAction("Exit D IP Monitor", self.menu)
        self.action_exit.triggered.connect(self.exit_requested.emit)
        self.menu.addAction(self.action_exit)

        self.tray_icon.setContextMenu(self.menu)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_requested.emit()

    def update_tray_icon(self, has_offline_hosts: bool):
        """Paints a dynamic red indicator badge if any host is unreachable."""
        self.is_offline_state = has_offline_hosts
        if not os.path.exists(self.base_icon_path):
            return

        pixmap = QPixmap(self.base_icon_path).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if has_offline_hosts:
            # Paint a small red dot badge on bottom right
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#ef4444"))
            painter.setPen(QColor("#ffffff"))
            painter.drawEllipse(20, 20, 10, 10)
            painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))
        status_tip = "D IP Monitor — ⚠️ Hosts Down" if has_offline_hosts else "D IP Monitor — All Systems Online 🟢"
        self.tray_icon.setToolTip(status_tip)

    def show_toast(self, title: str, message: str, is_warning: bool = False):
        """Displays a native Windows toast notification."""
        icon = QSystemTrayIcon.MessageIcon.Warning if is_warning else QSystemTrayIcon.MessageIcon.Information
        self.tray_icon.showMessage(title, message, icon, 4000)
