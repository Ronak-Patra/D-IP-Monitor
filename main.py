import sys
import subprocess
import re
import smtplib
from email.message import EmailMessage
import os
import time
import shutil
import tempfile
import webbrowser
from datetime import datetime, timedelta
from queue import Queue
import collections
import threading
from concurrent.futures import ThreadPoolExecutor
import ssl
import winsound

# PyQt6 UI components
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QSplitter, QTextEdit, QFileDialog, QMessageBox,
    QHeaderView, QSizePolicy, QFormLayout, QScrollArea, QTabBar,
    QMenu, QComboBox, QToolButton, QFrame, QTabWidget, QInputDialog,
    QTableWidgetSelectionRange
)
from PyQt6.QtGui import QColor, QFont, QIcon, QBrush, QPixmap, QAction, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QEvent, QPoint

# Custom modules
from ip_monitor import IpMonitor
from settings_manager import SettingsManager
from log_manager import LogManager
from diagnostics import TracerouteDialog, PortCheckerDialog, DnsLookupDialog, ContinuousPingDialog
from ip_scanner import IpRangeScannerDialog
from dashboard_widgets import MetricsBannerWidget, LatencySparklineWidget
from floating_hud import FloatingHudWidget
from webhook_notifier import WebhookNotifier
from system_tray import SystemTrayManager, StartupManager
from bulk_tools import BulkManager
from themes import get_dark_theme, get_light_theme, get_dark_palette, get_light_palette

# --- Global Queue for Critical Error Logging (Fallback) ---
_critical_error_queue = Queue()


def cleanup_orphaned_temp_files():
    """Cleans up orphaned _MEI* PyInstaller temp folders from previous runs in %TEMP%."""
    try:
        temp_dir = tempfile.gettempdir()
        current_mei = getattr(sys, '_MEIPASS', None)
        for item in os.listdir(temp_dir):
            if item.startswith("_MEI"):
                full_path = os.path.join(temp_dir, item)
                if current_mei and os.path.abspath(full_path) == os.path.abspath(current_mei):
                    continue
                try:
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass


# --- High-Performance Worker for Concurrent Ping Operations ---
class PingTask:
    """Represents a single lightweight ping task executed by the PingEngine."""
    def __init__(self, ip_address: str, count: int = 1, timeout: int = 800):
        self.ip_address = ip_address
        self.count = count
        self.timeout = timeout

    def run(self):
        """
        Executes the ping command with minimal OS overhead and returns results.
        Returns: tuple (ip_address, is_reachable, round_trip_time, packet_loss)
        """
        is_reachable = False
        round_trip_time = 0.0
        packet_loss = 100.0

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        cmd = ["ping", "-n", str(self.count), "-w", str(self.timeout), self.ip_address]

        try:
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=creation_flags
            ) as process:
                stdout, _ = process.communicate(timeout=2.5)

            if f"Reply from {self.ip_address}" in stdout or "bytes=" in stdout:
                is_reachable = True
                match = re.search(r"Average = (\d+\.?\d*)ms", stdout)
                if not match:
                    match = re.search(r"time[<=](\d+\.?\d*)ms", stdout)
                round_trip_time = float(match.group(1)) if match else 1.0

                loss_match = re.search(r"\((\d+)% loss\)", stdout)
                packet_loss = float(loss_match.group(1)) if loss_match else 0.0
            else:
                is_reachable = False
                packet_loss = 100.0
        except Exception:
            is_reachable = False
            round_trip_time = 0.0
            packet_loss = 100.0

        return self.ip_address, is_reachable, round_trip_time, packet_loss


class PingEngine(QObject):
    """
    Manages and executes concurrent ping sweeps supporting 200+ IPs without freezing.
    """
    ping_result_ready = pyqtSignal(str, bool, float, float) # ip_address, is_reachable, response_time, packet_loss

    def __init__(self, monitored_ips_ref: list, ping_interval: int, parent=None):
        super().__init__(parent)
        self._monitored_ips_ref = monitored_ips_ref
        self._ping_interval = ping_interval
        self._is_running = True
        self._thread_pool = None
        self._futures = []

    def set_ping_interval(self, interval: int):
        self._ping_interval = interval

    def run(self):
        """The main loop for PingEngine, run in a dedicated QThread."""
        # Scale concurrency up to 100 parallel workers to easily support 200+ hosts
        max_workers = min(100, max(32, (os.cpu_count() or 4) * 8))
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)

        while self._is_running:
            start_time = time.time()
            if self._monitored_ips_ref:
                # Take a thread-safe snapshot of IPs to monitor
                ips_snapshot = list(self._monitored_ips_ref)
                self._futures = [
                    self._thread_pool.submit(PingTask(monitor.ip_address, count=1, timeout=800).run)
                    for monitor in ips_snapshot
                ]

                for future in self._futures:
                    if not self._is_running:
                        break
                    try:
                        ip_address, is_reachable, round_trip_time, packet_loss = future.result()
                        self.ping_result_ready.emit(ip_address, is_reachable, round_trip_time, packet_loss)
                    except Exception as e:
                        _critical_error_queue.put(f"Error in PingEngine future: {e}")

            elapsed_time = time.time() - start_time
            sleep_time = self._ping_interval - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)

            self._futures = []

    def stop(self):
        """Gracefully stops the PingEngine."""
        self._is_running = False
        if self._thread_pool:
            for future in self._futures:
                future.cancel()
            self._thread_pool.shutdown(wait=False)


# --- Worker for Saving/Loading (I/O operations) ---
class SaveLoadWorker(QObject):
    operation_completed = pyqtSignal(str, bool, str)

    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self._settings_manager = settings_manager
        self._queue = Queue()
        self._is_running = True
        self._thread = threading.Thread(target=self._process_queue, daemon=True)

    def start_worker(self):
        self._thread.start()

    def stop_worker(self):
        self._is_running = False
        self._queue.put(None)
        self._thread.join(timeout=2)

    def save_settings_async(self):
        self._queue.put(("save_settings", None))

    def save_ips_async(self, ip_monitors: list):
        # Pass a shallow copy to prevent concurrent modification issues
        self._queue.put(("save_ips", list(ip_monitors)))

    def _process_queue(self):
        while self._is_running:
            item = self._queue.get()
            if item is None:
                break

            operation_type, data = item
            success = False
            message = ""

            try:
                if operation_type == "save_settings":
                    self._settings_manager.save_settings()
                    success = True
                    message = "Settings saved successfully."
                elif operation_type == "save_ips":
                    self._settings_manager.save_ip_monitors(data)
                    success = True
                    message = "IP monitors saved successfully."
            except Exception as e:
                success = False
                message = f"Error during '{operation_type}': {e}"
                _critical_error_queue.put(message)

            self.operation_completed.emit(operation_type, success, message)
            self._queue.task_done()


# --- Worker for Sending Emails (Async) ---
class EmailWorker(QThread):
    email_sent = pyqtSignal(str, str)
    email_error = pyqtSignal(str, str)

    def __init__(self, email_settings: dict, subject: str, body: str, ip_address: str):
        super().__init__()
        self._email_settings = email_settings
        self._subject = subject
        self._body = body
        self._ip_address = ip_address

    def run(self):
        msg = EmailMessage()
        msg['Subject'] = self._subject
        msg['From'] = self._email_settings["sender_email"]

        recipients_str = self._email_settings.get("recipient_email", "")
        recipients = [e.strip() for e in recipients_str.replace(";", ",").split(",") if e.strip()]
        if not recipients:
            self.email_error.emit("No valid recipient email address specified.", self._ip_address)
            return

        msg['To'] = ", ".join(recipients)
        msg.set_content(self._body)

        smtp_server = self._email_settings["smtp_server"]
        smtp_port = int(self._email_settings["smtp_port"])
        username = self._email_settings["username"]
        password = self._email_settings["password"]
        enable_ssl = self._email_settings["enable_ssl"]

        server = None
        context = ssl.create_default_context()

        try:
            if enable_ssl:
                if smtp_port == 465:
                    server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
                else:
                    server = smtplib.SMTP(smtp_server, smtp_port)
                    server.starttls(context=context)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port)
                if smtp_port == 587:
                    try:
                        server.starttls(context=context)
                    except Exception:
                        pass

            if username and password:
                server.login(username, password)

            server.send_message(msg)
            self.email_sent.emit(self._subject, self._ip_address)
        except Exception as e:
            self.email_error.emit(f"Failed to send email: {e}", self._ip_address)
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass


# --- Model for IP Data Management ---
class IPDataModel(QObject):
    ip_added = pyqtSignal(IpMonitor)
    ip_removed = pyqtSignal(str)
    ip_updated = pyqtSignal(str)
    status_changed = pyqtSignal(IpMonitor, str, str) # monitor, old_status, new_status
    alert_triggered = pyqtSignal(str, str, int)
    sound_alert_triggered = pyqtSignal(str)
    email_alert_triggered = pyqtSignal(dict, str, str, str, bool)
    webhook_alert_triggered = pyqtSignal(str, str, bool, str) # ip, desc, is_down, downtime

    def __init__(self, settings_manager: SettingsManager, log_manager: LogManager, parent=None):
        super().__init__(parent)
        self._settings_manager = settings_manager
        self._log_manager = log_manager
        self.monitored_ips = self._settings_manager.load_ip_monitors()
        self.unreachable_ping_counts = {}

        for monitor in self.monitored_ips:
            self.unreachable_ping_counts[monitor.ip_address] = 0
            if monitor.status == "Reachable" and monitor.reachable_start_time is None:
                monitor.reachable_start_time = datetime.now()
            elif monitor.status == "Unreachable" and monitor.unreachable_start_time is None:
                monitor.unreachable_start_time = datetime.now()

    def add_ip(self, ip_address: str, description: str, tag: str = "General") -> bool:
        if any(monitor.ip_address == ip_address for monitor in self.monitored_ips):
            self.alert_triggered.emit("Duplicate IP", f"IP Address '{ip_address}' is already being monitored.", QMessageBox.Icon.Warning.value)
            return False

        new_monitor = IpMonitor(ip_address, description if description else ip_address, tag=tag)
        new_monitor.enable_email_alerts_for_ip = True
        new_monitor.enable_popup_alerts_for_ip = True
        new_monitor.enable_sound_alerts_for_ip = True

        self.monitored_ips.append(new_monitor)
        self.unreachable_ping_counts[new_monitor.ip_address] = 0
        self._log_manager.log_incident(f"Added new IP for monitoring: {ip_address} ({description}) [{tag}]")
        self.ip_added.emit(new_monitor)

        if self._settings_manager.get_setting("EMAIL", "enable_email_alerts", bool) and new_monitor.enable_email_alerts_for_ip:
            subject = f"D IP Monitor Alert: New IP Added - {ip_address}"
            body = f"The IP address {ip_address} (Description: {description}) has been added to the monitoring list."
            self.send_email_alert(subject, body, ip_address)
        return True

    def remove_ip(self, ip_address: str) -> bool:
        monitor_to_remove = next((m for m in self.monitored_ips if m.ip_address == ip_address), None)
        if monitor_to_remove:
            self.monitored_ips.remove(monitor_to_remove)
            if ip_address in self.unreachable_ping_counts:
                del self.unreachable_ping_counts[ip_address]
            self._log_manager.log_incident(f"Removed IP from monitoring: {ip_address} ({monitor_to_remove.description})")
            self.ip_removed.emit(ip_address)

            if self._settings_manager.get_setting("EMAIL", "enable_email_alerts", bool) and monitor_to_remove.enable_email_alerts_for_ip:
                subject = f"D IP Monitor Alert: IP Removed - {ip_address}"
                body = f"The IP address {ip_address} (Description: {monitor_to_remove.description}) has been removed from the monitoring list."
                self.send_email_alert(subject, body, ip_address)
            return True
        return False

    def update_ip_status(self, ip_address: str, is_reachable: bool, response_time: float, packet_loss: float):
        monitor = next((m for m in self.monitored_ips if m.ip_address == ip_address), None)
        if not monitor:
            return

        old_status = monitor.status
        monitor.add_ping_sample(is_reachable)
        monitor.total_pings += 1
        monitor.response_time = response_time
        monitor.add_latency_sample(response_time if is_reachable else 0.0)

        current_time = datetime.now()

        if not is_reachable:
            monitor.failed_pings += 1
            self.unreachable_ping_counts[ip_address] = self.unreachable_ping_counts.get(ip_address, 0) + 1
            unreachable_threshold = self._settings_manager.get_setting("MONITORING", "unreachable_threshold", int) or 3
            new_status = "Unreachable" if self.unreachable_ping_counts[ip_address] >= unreachable_threshold else monitor.status
        else:
            self.unreachable_ping_counts[ip_address] = 0
            new_status = "Reachable"

        # Check for State Transition
        if new_status != old_status:
            self._log_manager.log_incident(f"IP {ip_address} changed status from {old_status} to {new_status}.")
            self.status_changed.emit(monitor, old_status, new_status)

            if new_status == "Unreachable" and old_status != "Unreachable":
                monitor.unreachable_start_time = current_time
                monitor.email_sent_unreachable = False
                monitor.popup_shown_unreachable = False
                monitor.popup_shown_reachable = False
                monitor.email_sent_reachable = False
                monitor.reachable_start_time = None
                self._trigger_unreachable_alert(monitor)

            elif new_status == "Reachable" and old_status == "Unreachable":
                downtime_duration = "0s"
                if monitor.unreachable_start_time:
                    downtime_duration = monitor._format_duration(current_time - monitor.unreachable_start_time)
                monitor.unreachable_start_time = None
                monitor.email_sent_reachable = False
                monitor.popup_shown_reachable = False
                monitor.email_sent_unreachable = False
                monitor.popup_shown_unreachable = False
                monitor.reachable_start_time = current_time
                self._trigger_reachable_alert(monitor, downtime_duration)
            else:
                if new_status == "Reachable" and old_status == "Unknown":
                    monitor.reachable_start_time = current_time

        monitor.status = new_status
        self.ip_updated.emit(monitor.ip_address)

    def _trigger_unreachable_alert(self, monitor: IpMonitor):
        if self._settings_manager.get_setting("ALERTS", "enable_popups", bool) and monitor.enable_popup_alerts_for_ip and not monitor.popup_shown_unreachable:
            self.alert_triggered.emit("IP Unreachable!", f"Host: {monitor.ip_address} ({monitor.description}) is now UNREACHABLE!", QMessageBox.Icon.Critical.value)
            monitor.popup_shown_unreachable = True

        if self._settings_manager.get_setting("EMAIL", "enable_email_alerts", bool) and monitor.enable_email_alerts_for_ip and not monitor.email_sent_unreachable:
            subject = f"D IP Monitor Alert: IP DOWN - {monitor.ip_address}"
            body = f"The host {monitor.ip_address} ({monitor.description}) has become UNREACHABLE at {datetime.now():%Y-%m-%d %H:%M:%S}."
            self.send_email_alert(subject, body, monitor.ip_address)
            monitor.email_sent_unreachable = True

        if self._settings_manager.get_setting("ALERTS", "enable_sound_alerts", bool) and monitor.enable_sound_alerts_for_ip:
            sound_path = self._settings_manager.get_setting("ALERTS", "alert_sound_path")
            self.sound_alert_triggered.emit(sound_path)

        # Trigger Webhook
        if self._settings_manager.get_setting("WEBHOOK", "enable_webhooks", bool) and getattr(monitor, "enable_webhook_alerts_for_ip", True):
            self.webhook_alert_triggered.emit(monitor.ip_address, monitor.description, True, "")

    def _trigger_reachable_alert(self, monitor: IpMonitor, downtime_duration: str):
        if self._settings_manager.get_setting("ALERTS", "enable_popups", bool) and monitor.enable_popup_alerts_for_ip and not monitor.popup_shown_reachable:
            self.alert_triggered.emit("IP Reachable!", f"Host: {monitor.ip_address} ({monitor.description}) is REACHABLE again!\nDowntime: {downtime_duration}", QMessageBox.Icon.Information.value)
            monitor.popup_shown_reachable = True

        if self._settings_manager.get_setting("EMAIL", "enable_email_alerts", bool) and monitor.enable_email_alerts_for_ip and not monitor.email_sent_reachable:
            subject = f"D IP Monitor Alert: IP UP - {monitor.ip_address}"
            body = f"The host {monitor.ip_address} ({monitor.description}) is REACHABLE again at {datetime.now():%Y-%m-%d %H:%M:%S}.\nDowntime: {downtime_duration}."
            self.send_email_alert(subject, body, monitor.ip_address)
            monitor.email_sent_reachable = True

        # Trigger Webhook
        if self._settings_manager.get_setting("WEBHOOK", "enable_webhooks", bool) and getattr(monitor, "enable_webhook_alerts_for_ip", True):
            self.webhook_alert_triggered.emit(monitor.ip_address, monitor.description, False, downtime_duration)

    def send_email_alert(self, subject: str, body: str, ip_address: str = "N/A", is_test: bool = False):
        if not is_test and not self._settings_manager.get_setting("EMAIL", "enable_email_alerts", bool):
            return

        email_settings = {
            "smtp_server": self._settings_manager.get_setting("EMAIL", "smtp_server"),
            "smtp_port": str(self._settings_manager.get_setting("EMAIL", "smtp_port")),
            "sender_email": self._settings_manager.get_setting("EMAIL", "sender_email"),
            "recipient_email": self._settings_manager.get_setting("EMAIL", "recipient_email"),
            "username": self._settings_manager.get_setting("EMAIL", "username"),
            "password": self._settings_manager.get_setting("EMAIL", "password"),
            "enable_ssl": self._settings_manager.get_setting("EMAIL", "enable_ssl", bool)
        }

        if not all([email_settings["smtp_server"], email_settings["sender_email"], email_settings["recipient_email"]]):
            self._log_manager.log_incident(f"ERROR: Email settings incomplete. Cannot send email for {ip_address}.")
            return

        self.email_alert_triggered.emit(email_settings, subject, body, ip_address, is_test)

    def sort_monitored_ips(self, logical_index: int, sort_order: Qt.SortOrder):
        reverse_sort = (sort_order == Qt.SortOrder.DescendingOrder)
        if logical_index == 0:
            self.monitored_ips.sort(key=lambda m: m.ip_address, reverse=reverse_sort)
        elif logical_index == 1:
            self.monitored_ips.sort(key=lambda m: m.description, reverse=reverse_sort)
        elif logical_index == 2:
            self.monitored_ips.sort(key=lambda m: getattr(m, 'tag', 'General'), reverse=reverse_sort)
        elif logical_index == 3:
            status_order = {"Reachable": 0, "Unreachable": 1, "Unknown": 2}
            self.monitored_ips.sort(key=lambda m: status_order.get(m.status, 99), reverse=reverse_sort)
        elif logical_index == 4:
            self.monitored_ips.sort(key=lambda m: self._get_total_seconds(m.uptime), reverse=reverse_sort)
        elif logical_index == 5:
            self.monitored_ips.sort(key=lambda m: self._get_total_seconds(m.downtime), reverse=reverse_sort)
        elif logical_index == 6:
            self.monitored_ips.sort(key=lambda m: m.packet_loss, reverse=reverse_sort)
        elif logical_index == 7:
            self.monitored_ips.sort(key=lambda m: m.response_time, reverse=reverse_sort)
        elif logical_index == 8:
            self.monitored_ips.sort(key=lambda m: getattr(m, 'enable_email_alerts_for_ip', True), reverse=reverse_sort)
        elif logical_index == 9:
            self.monitored_ips.sort(key=lambda m: getattr(m, 'enable_popup_alerts_for_ip', True), reverse=reverse_sort)
        elif logical_index == 10:
            self.monitored_ips.sort(key=lambda m: getattr(m, 'enable_sound_alerts_for_ip', True), reverse=reverse_sort)
        elif logical_index == 11:
            self.monitored_ips.sort(key=lambda m: getattr(m, 'enable_webhook_alerts_for_ip', True), reverse=reverse_sort)

    def _get_total_seconds(self, duration_str: str) -> int:
        if duration_str == "0s" or not duration_str:
            return 0
        total_s = 0
        for part in duration_str.split(' '):
            if 'd' in part: total_s += int(part.replace('d', '')) * 86400
            elif 'h' in part: total_s += int(part.replace('h', '')) * 3600
            elif 'm' in part: total_s += int(part.replace('m', '')) * 60
            elif 's' in part: total_s += int(part.replace('s', ''))
        return total_s


# --- Main Application Window ---
class IPMonitorApp(QMainWindow):

    def __init__(self):
        super().__init__()
        cleanup_orphaned_temp_files()

        self.settings_manager = SettingsManager()

        # Base path detection
        if getattr(sys, 'frozen', False):
            self.base_path = sys._MEIPASS
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        # Initialize Log Display with strict memory limit (Prevents pagefile.sys leak!)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(110)
        self.log_display.document().setMaximumBlockCount(1000)

        self.log_records = collections.deque(maxlen=1000)

        self.log_manager = LogManager(
            self.settings_manager.get_setting("LOGGING", "log_directory"),
            None,
            enable_hourly_log=self.settings_manager.get_setting("LOGGING", "enable_hourly_log", bool),
            enable_file_logging=self.settings_manager.get_setting("LOGGING", "enable_file_logging", bool)
        )
        self.log_manager.log_received.connect(self.handle_incoming_log_message)

        self.ip_data_model = IPDataModel(self.settings_manager, self.log_manager)
        self.webhook_notifier = WebhookNotifier(self)

        self.ip_to_row_map = {}
        self.ips_to_update_ui = set()
        self.current_selected_ip = None
        self.active_category_filter = "All"
        self.active_diagnostic_dialogs = []

        # Concurrency Ping Engine
        self.ping_engine = PingEngine(
            self.ip_data_model.monitored_ips,
            self.settings_manager.get_setting("MONITORING", "ping_interval", int) or 10
        )
        self.ping_engine_thread = QThread()
        self.ping_engine.moveToThread(self.ping_engine_thread)
        self.ping_engine_thread.started.connect(self.ping_engine.run)
        self.ping_engine.ping_result_ready.connect(self.ip_data_model.update_ip_status)

        # Save/Load Worker (I/O thread)
        self.save_load_worker = SaveLoadWorker(self.settings_manager)
        self.save_load_thread = QThread()
        self.save_load_worker.moveToThread(self.save_load_thread)
        self.save_load_thread.started.connect(self.save_load_worker.start_worker)
        self.save_load_worker.operation_completed.connect(self._handle_save_load_completion)

        self.email_threads = {}

        # Batched UI Timer (150ms interval for 60fps rendering without UI lock)
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.setInterval(150)
        self.ui_update_timer.timeout.connect(self._process_ui_updates)

        # Autosave Timer (every 5 minutes to safeguard stats without disk churn)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(300 * 1000)
        self.autosave_timer.timeout.connect(lambda: self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips))

        self._current_sort_column = -1
        self._current_sort_order = Qt.SortOrder.AscendingOrder

        # System Tray & Startup
        icon_path = os.path.join(self.base_path, 'app_icon.png')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.base_path, 'app_icon.ico')
        self.system_tray_manager = SystemTrayManager(icon_path, self)
        self.system_tray_manager.restore_requested.connect(self.showNormal)
        self.system_tray_manager.toggle_hud_requested.connect(self.toggle_floating_hud)
        self.system_tray_manager.mute_toggled.connect(self._on_tray_mute_toggled)
        self.system_tray_manager.minimize_tray_toggled.connect(self._on_tray_minimize_toggled)
        self.system_tray_manager.exit_requested.connect(self.force_exit_app)

        # Floating Mini HUD (Starts hidden on newly opened app; user toggles on demand)
        self.floating_hud = FloatingHudWidget()
        self.floating_hud.hud_closed.connect(self._on_hud_closed)

        # UI Init
        self.init_ui()
        self.load_settings_to_ui()
        self.update_ip_status_table(full_rebuild=True)

        # Connect Signals
        self.ip_data_model.ip_added.connect(self._handle_ip_added_to_model)
        self.ip_data_model.ip_removed.connect(self._handle_ip_removed_from_model)
        self.ip_data_model.ip_updated.connect(self._handle_ip_updated_in_model)
        self.ip_data_model.status_changed.connect(self._handle_status_changed_in_model)
        self.ip_data_model.alert_triggered.connect(self.show_popup_alert)
        self.ip_data_model.sound_alert_triggered.connect(self.play_alert_sound)
        self.ip_data_model.email_alert_triggered.connect(self._send_email_alert_via_worker)
        self.ip_data_model.webhook_alert_triggered.connect(self._send_webhook_alert)

        # Start worker threads
        self.ping_engine_thread.start()
        self.save_load_thread.start()
        self.ui_update_timer.start()
        self.autosave_timer.start()

        # Apply Saved Theme (Default: Dark Neon Cyan Mode)
        is_dark = self.settings_manager.get_setting("UI", "dark_mode", bool)
        self.apply_theme(is_dark if is_dark is not None else True)

        self.log_manager.log_incident("D IP Monitor started successfully.")

    def _create_header_widget(self):
        """Creates top branding banner with logo and application title."""
        header_widget = QWidget()
        header_widget.setObjectName("headerCard")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(12)

        logo_label = QLabel()
        png_path = os.path.join(self.base_path, 'app_icon.png')
        if not os.path.exists(png_path):
            png_path = os.path.join(self.base_path, 'app_icon.ico')
        if os.path.exists(png_path):
            pixmap = QPixmap(png_path)
            if not pixmap.isNull():
                logo_label.setPixmap(pixmap.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(1)
        title_label = QLabel("D IP Monitor")
        title_label.setObjectName("brandTitle")
        title_label.setStyleSheet("font-size: 15px; font-weight: 800; color: #00e5ff; letter-spacing: 0.5px;")
        subtitle_label = QLabel("IP Monitoring Tool by D")
        subtitle_label.setStyleSheet("font-size: 10px; color: #64748b; font-weight: 500;")
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        return header_widget

    def init_ui(self):
        """Initializes the main user interface."""
        self.setWindowTitle("D IP Monitor")
        self.setGeometry(80, 80, 1260, 840)

        # Set Window Icon
        icon_path = os.path.join(self.base_path, 'app_icon.ico')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.base_path, 'app_icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Top Control & Action Bar
        top_action_bar = QHBoxLayout()
        top_action_bar.setContentsMargins(4, 2, 4, 2)
        top_action_bar.setSpacing(8)

        # Scanner button
        btn_scanner = QPushButton("🔍 IP Range Scanner")
        btn_scanner.setObjectName("btnScanner")
        btn_scanner.clicked.connect(self.open_ip_range_scanner)
        top_action_bar.addWidget(btn_scanner)

        # Floating HUD toggle button
        self.btn_toggle_hud = QPushButton("🖥 Mini HUD")
        self.btn_toggle_hud.setCheckable(True)
        self.btn_toggle_hud.setChecked(self.settings_manager.get_setting("UI", "enable_floating_hud", bool))
        self.btn_toggle_hud.clicked.connect(self.toggle_floating_hud)
        top_action_bar.addWidget(self.btn_toggle_hud)

        # Theme toggle button
        self.btn_theme_toggle = QPushButton("🌙 Dark Mode")
        self.btn_theme_toggle.clicked.connect(self.toggle_theme_mode)
        top_action_bar.addWidget(self.btn_theme_toggle)

        top_action_bar.addStretch()

        # Import & Export Buttons
        btn_import = QPushButton("📥 Import CSV/TXT")
        btn_import.clicked.connect(self.import_hosts_dialog)
        top_action_bar.addWidget(btn_import)

        btn_export = QPushButton("📤 Export CSV")
        btn_export.clicked.connect(self.export_hosts_dialog)
        top_action_bar.addWidget(btn_export)

        btn_backup = QPushButton("💾 Backup (.dipm)")
        btn_backup.clicked.connect(self.backup_profile_dialog)
        top_action_bar.addWidget(btn_backup)

        btn_restore = QPushButton("📂 Restore (.dipm)")
        btn_restore.clicked.connect(self.restore_profile_dialog)
        top_action_bar.addWidget(btn_restore)

        main_layout.addLayout(top_action_bar)

        # Metrics Banner (Top Placement by default)
        is_sidebar_pos = (self.settings_manager.get_setting("UI", "dashboard_position") == "sidebar")
        self.metrics_banner = MetricsBannerWidget(is_sidebar_mode=is_sidebar_pos)
        self.metrics_banner.position_toggle_clicked.connect(self.toggle_dashboard_dock_position)

        self.top_metrics_container = QWidget()
        top_metrics_layout = QVBoxLayout(self.top_metrics_container)
        top_metrics_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.top_metrics_container)

        # Splitter for Left Sidebar & Right Main Panel
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # --- LEFT PANEL ---
        self.left_panel_widget = QWidget()
        self.left_panel_widget.setObjectName("leftPanelWidget")
        self.left_panel_layout = QVBoxLayout(self.left_panel_widget)
        self.left_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.left_panel_layout.setContentsMargins(2, 2, 2, 2)
        self.left_panel_layout.setSpacing(8)

        self.left_panel_layout.addWidget(self._create_header_widget())

        # Sidebar metrics container
        self.sidebar_metrics_container = QWidget()
        self.sidebar_metrics_container.setObjectName("sidebarMetricsContainer")
        sidebar_metrics_layout = QVBoxLayout(self.sidebar_metrics_container)
        sidebar_metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.left_panel_layout.addWidget(self.sidebar_metrics_container)

        self.left_panel_layout.addWidget(self._create_ip_management_group())
        self.left_panel_layout.addWidget(self._create_settings_group())

        # Live Latency Sparkline Graph
        self.sparkline_widget = LatencySparklineWidget()

        # --- RIGHT PANEL ---
        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(4, 4, 4, 4)
        right_panel_layout.setSpacing(6)

        right_panel_layout.addWidget(self._create_ip_status_group())

        # Dedicated sparkline container for right panel
        self.right_panel_sparkline_container = QWidget()
        right_sparkline_layout = QVBoxLayout(self.right_panel_sparkline_container)
        right_sparkline_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.addWidget(self.right_panel_sparkline_container)

        # Application Logs Group
        right_panel_layout.addWidget(self._create_log_group())

        # Attach metrics banner and sparkline to correct container based on preference
        if is_sidebar_pos:
            self.sidebar_metrics_container.layout().addWidget(self.metrics_banner)
            self.sidebar_metrics_container.layout().addWidget(self.sparkline_widget)
        else:
            self.top_metrics_container.layout().addWidget(self.metrics_banner)
            self.right_panel_sparkline_container.layout().addWidget(self.sparkline_widget)

        # Wrap Left Panel in smooth QScrollArea
        self.left_scroll_area = QScrollArea()
        self.left_scroll_area.setObjectName("leftScrollArea")
        self.left_scroll_area.setWidgetResizable(True)
        self.left_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.left_scroll_area.viewport().setObjectName("leftScrollViewport")
        self.left_scroll_area.setWidget(self.left_panel_widget)

        self.splitter.addWidget(self.left_scroll_area)
        self.splitter.addWidget(right_panel_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([350, 910])

        main_layout.addWidget(self.splitter)

        # Hourly log timer
        self.hourly_log_timer = QTimer(self)
        self.hourly_log_timer.timeout.connect(lambda: self.log_manager.log_hourly_ip_status(self.ip_data_model.monitored_ips))
        self.hourly_log_timer.start(3600 * 1000)

    def _create_ip_management_group(self):
        """Creates the IP Management Group Box with Categories/Tags."""
        ip_group = QGroupBox("Host Management")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 14, 8, 8)
        layout.setSpacing(8)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(8)
        form_layout.setVerticalSpacing(6)

        self.ip_address_input = QLineEdit()
        self.ip_address_input.setPlaceholderText("e.g. 8.8.8.8 or gateway.local")
        form_layout.addRow("IP / Host:", self.ip_address_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("e.g. Core Switch or DNS Server")
        form_layout.addRow("Description:", self.description_input)

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("e.g. Routers, Servers, Printers")
        self.tag_input.setText("General")
        form_layout.addRow("Category / Tag:", self.tag_input)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        add_ip_button = QPushButton("＋ Add Host")
        add_ip_button.setObjectName("btnAddIp")
        add_ip_button.clicked.connect(self.add_ip_monitor_ui)
        button_layout.addWidget(add_ip_button)

        remove_ip_button = QPushButton("🗑 Remove Selected")
        remove_ip_button.setObjectName("btnRemoveIp")
        remove_ip_button.clicked.connect(self.remove_ip_monitor_ui)
        button_layout.addWidget(remove_ip_button)
        layout.addLayout(button_layout)

        ip_group.setLayout(layout)
        return ip_group

    def _create_settings_group(self):
        """Creates the Application Settings Group Box with sleek segmented tabs."""
        settings_group = QGroupBox("Application Settings")
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(6, 14, 6, 6)
        settings_layout.setSpacing(8)

        # Settings Tabs
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setObjectName("settingsTabs")

        # Tab 1: Local Alerts
        tab_alerts = QWidget()
        alerts_layout = QVBoxLayout(tab_alerts)
        alerts_layout.setContentsMargins(6, 8, 6, 6)
        alerts_layout.setSpacing(8)

        self.enable_global_popups_checkbox = QCheckBox("Enable Native Windows Toasts")
        alerts_layout.addWidget(self.enable_global_popups_checkbox)

        self.enable_global_sound_alerts_checkbox = QCheckBox("Enable Audio Alerts")
        alerts_layout.addWidget(self.enable_global_sound_alerts_checkbox)

        sound_form = QFormLayout()
        sound_form.setHorizontalSpacing(8)
        sound_form.setVerticalSpacing(6)
        self.alert_sound_path_input = QLineEdit()
        self.alert_sound_path_input.setPlaceholderText("Path to custom .wav file")
        sound_form.addRow("Sound (.wav):", self.alert_sound_path_input)
        alerts_layout.addLayout(sound_form)

        btn_browse_sound = QPushButton("📁 Browse Sound")
        btn_browse_sound.clicked.connect(self.browse_sound_file)
        alerts_layout.addWidget(btn_browse_sound)
        alerts_layout.addStretch()

        self.settings_tabs.addTab(tab_alerts, "Alerts")

        # Tab 2: Webhooks
        tab_webhooks = QWidget()
        webhook_layout = QVBoxLayout(tab_webhooks)
        webhook_layout.setContentsMargins(6, 8, 6, 6)
        webhook_layout.setSpacing(8)

        self.enable_webhooks_checkbox = QCheckBox("Enable Webhook Alerts")
        webhook_layout.addWidget(self.enable_webhooks_checkbox)

        webhook_form = QFormLayout()
        webhook_form.setHorizontalSpacing(8)
        webhook_form.setVerticalSpacing(6)

        self.webhook_type_combo = QComboBox()
        self.webhook_type_combo.addItems(["Discord", "Slack", "Teams", "Telegram", "Generic JSON"])
        self.webhook_type_combo.currentTextChanged.connect(self.on_webhook_platform_changed)
        webhook_form.addRow("Platform:", self.webhook_type_combo)

        self.webhook_url_input = QLineEdit()
        self.webhook_url_input.setPlaceholderText("https://discord.com/api/webhooks/...")
        webhook_form.addRow("Webhook URL:", self.webhook_url_input)
        webhook_layout.addLayout(webhook_form)

        btn_test_webhook = QPushButton("⚡ Test Webhook")
        btn_test_webhook.clicked.connect(self.test_webhook_settings_ui)
        webhook_layout.addWidget(btn_test_webhook)
        webhook_layout.addStretch()

        self.settings_tabs.addTab(tab_webhooks, "Webhook")

        # Tab 3: Email (SMTP) - direct layout without nested scroll trap
        tab_email = QWidget()
        email_layout = QVBoxLayout(tab_email)
        email_layout.setContentsMargins(6, 8, 6, 6)
        email_layout.setSpacing(6)

        self.enable_global_email_alerts_checkbox = QCheckBox("Enable Email Alerts")
        email_layout.addWidget(self.enable_global_email_alerts_checkbox)

        self.enable_ssl_checkbox = QCheckBox("Enable SSL/TLS")
        email_layout.addWidget(self.enable_ssl_checkbox)

        email_form = QFormLayout()
        email_form.setHorizontalSpacing(8)
        email_form.setVerticalSpacing(5)

        self.smtp_server_input = QLineEdit()
        self.smtp_server_input.setPlaceholderText("e.g. smtp.gmail.com")
        email_form.addRow("SMTP Server:", self.smtp_server_input)

        self.smtp_port_input = QLineEdit()
        self.smtp_port_input.setPlaceholderText("587")
        email_form.addRow("SMTP Port:", self.smtp_port_input)

        self.sender_email_input = QLineEdit()
        self.sender_email_input.setPlaceholderText("alerts@domain.com")
        email_form.addRow("Sender Email:", self.sender_email_input)

        self.recipient_emails_input = QLineEdit()
        self.recipient_emails_input.setPlaceholderText("admin@domain.com, ops@domain.com")
        email_form.addRow("Recipients:", self.recipient_emails_input)

        self.smtp_username_input = QLineEdit()
        self.smtp_username_input.setPlaceholderText("SMTP Username")
        email_form.addRow("Username:", self.smtp_username_input)

        self.smtp_password_input = QLineEdit()
        self.smtp_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_password_input.setPlaceholderText("Password")
        email_form.addRow("Password:", self.smtp_password_input)
        email_layout.addLayout(email_form)

        btn_test_email = QPushButton("📧 Test Email")
        btn_test_email.clicked.connect(self.test_email_settings_ui)
        email_layout.addWidget(btn_test_email)
        email_layout.addStretch()

        self.settings_tabs.addTab(tab_email, "Email")

        # Tab 4: Polling / Monitoring
        tab_polling = QWidget()
        polling_layout = QVBoxLayout(tab_polling)
        polling_layout.setContentsMargins(6, 8, 6, 6)
        polling_layout.setSpacing(8)

        polling_form = QFormLayout()
        polling_form.setHorizontalSpacing(8)
        polling_form.setVerticalSpacing(8)

        self.ping_interval_input = QLineEdit()
        self.ping_interval_input.setPlaceholderText("Seconds (e.g., 5 or 10)")
        polling_form.addRow("Ping Interval (s):", self.ping_interval_input)

        self.unreachable_threshold_input = QLineEdit()
        self.unreachable_threshold_input.setPlaceholderText("Failures before alert (e.g., 3)")
        polling_form.addRow("Down Threshold:", self.unreachable_threshold_input)
        polling_layout.addLayout(polling_form)
        polling_layout.addStretch()

        self.settings_tabs.addTab(tab_polling, "Polling")

        # Tab 5: System & Logging
        tab_system = QWidget()
        system_layout = QVBoxLayout(tab_system)
        system_layout.setContentsMargins(6, 8, 6, 6)
        system_layout.setSpacing(8)

        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setChecked(StartupManager.is_startup_enabled())
        system_layout.addWidget(self.startup_checkbox)

        self.minimize_tray_checkbox = QCheckBox("Keep running in background when closed (Minimize to tray)")
        self.minimize_tray_checkbox.setToolTip("When checked (ON): Closing the window keeps D IP Monitor running in the system tray.\nWhen unchecked (OFF): Closing the window completely exits the application.")
        self.minimize_tray_checkbox.toggled.connect(self._on_minimize_tray_checkbox_toggled)
        system_layout.addWidget(self.minimize_tray_checkbox)

        self.enable_file_logging_checkbox = QCheckBox("Auto-rotated File Logging")
        system_layout.addWidget(self.enable_file_logging_checkbox)

        self.enable_hourly_logging_checkbox = QCheckBox("Hourly Snapshots (7d pruned)")
        system_layout.addWidget(self.enable_hourly_logging_checkbox)

        sys_form = QFormLayout()
        sys_form.setHorizontalSpacing(8)
        sys_form.setVerticalSpacing(6)
        self.log_directory_input = QLineEdit()
        sys_form.addRow("Logs Path:", self.log_directory_input)
        system_layout.addLayout(sys_form)

        log_btn_layout = QHBoxLayout()
        btn_browse_log = QPushButton("📁 Browse Path")
        btn_browse_log.clicked.connect(self.browse_log_directory)
        log_btn_layout.addWidget(btn_browse_log)

        btn_open_settings_log = QPushButton("📂 Open Location")
        btn_open_settings_log.clicked.connect(self.open_log_directory)
        log_btn_layout.addWidget(btn_open_settings_log)

        system_layout.addLayout(log_btn_layout)
        system_layout.addStretch()

        self.settings_tabs.addTab(tab_system, "System")

        settings_layout.addWidget(self.settings_tabs)

        # Save Button (Prominently pinned with pointer cursor & Ctrl+S shortcut)
        self.btn_save_settings = QPushButton("💾 Save All Settings")
        self.btn_save_settings.setObjectName("btnSaveSettings")
        self.btn_save_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_settings.setMinimumHeight(36)
        self.btn_save_settings.setToolTip("Save all settings (Shortcut: Ctrl+S)")
        self.btn_save_settings.clicked.connect(self.save_settings_from_ui)
        settings_layout.addWidget(self.btn_save_settings)

        # Global Ctrl+S Shortcut to save settings from anywhere in the window
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.save_settings_from_ui)

        settings_group.setLayout(settings_layout)
        return settings_group

    def _create_ip_status_group(self):
        """Creates the Monitored IP Status Group with Category Dropdown and Column Chooser."""
        status_group = QGroupBox("Monitored Hosts && Live Status")
        layout = QVBoxLayout()

        # Search Bar, Group Filter Dropdown & Column Options
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        group_label = QLabel("Group:")
        group_label.setObjectName("categoryDropdownLabel")
        group_label.setStyleSheet("font-weight: 700; color: #7e8fa6; font-size: 11px;")

        self.category_dropdown = QComboBox()
        self.category_dropdown.setObjectName("categoryDropdown")
        self.category_dropdown.setMinimumWidth(150)
        self.category_dropdown.setMaximumWidth(220)
        self.category_dropdown.addItem("All")
        self.category_dropdown.currentTextChanged.connect(self.on_category_dropdown_changed)
        self.category_tabs = self.category_dropdown  # backward compatibility alias

        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: 700; color: #7e8fa6; font-size: 11px;")

        self.ip_table_search_input = QLineEdit()
        self.ip_table_search_input.setPlaceholderText("Filter by IP, Description, Tag or Status...")
        self.ip_table_search_input.textChanged.connect(self.filter_ip_status_table)

        self.btn_cols = QPushButton("⚙ Columns")
        self.btn_cols.setFixedWidth(100)
        self.btn_cols.setToolTip("Show / Hide Table Columns")
        self.btn_cols.clicked.connect(self.open_column_selector_menu)

        search_layout.addWidget(group_label)
        search_layout.addWidget(self.category_dropdown)
        search_layout.addSpacing(6)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.ip_table_search_input)
        search_layout.addWidget(self.btn_cols)
        layout.addLayout(search_layout)

        # Table
        self.ip_status_table = QTableWidget()
        headers = [
            "IP Address", "Description", "Tag", "Status",
            "Uptime", "Downtime", "Packet Loss", "Latency",
            "Email", "Popup", "Sound", "Webhook"
        ]
        self.ip_status_table.setColumnCount(len(headers))
        self.ip_status_table.setHorizontalHeaderLabels(headers)

        for i in range(len(headers)):
            self.ip_status_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        self.ip_status_table.horizontalHeader().setStretchLastSection(True)

        self.ip_status_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ip_status_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.ip_status_table.setAlternatingRowColors(True)
        self.ip_status_table.verticalHeader().setDefaultSectionSize(32)
        self.ip_status_table.verticalHeader().setVisible(False)
        self.ip_status_table.clicked.connect(self.on_table_item_clicked)
        self.ip_status_table.viewport().installEventFilter(self)

        # Custom Sorting
        self.ip_status_table.horizontalHeader().sectionClicked.connect(self.sort_table_column_ui)

        # Context Menu on Header for Column Chooser
        self.ip_status_table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ip_status_table.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

        # Context Menu on Table Rows for Diagnostic Tools
        self.ip_status_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ip_status_table.customContextMenuRequested.connect(self.show_host_context_menu)

        layout.addWidget(self.ip_status_table)
        status_group.setLayout(layout)
        return status_group

    def _create_log_group(self):
        """Creates the Application Logs Group with Search and Event Filtering."""
        log_group = QGroupBox("Application Logs && Event Stream")
        log_group.setFixedHeight(180)
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Log filter bar
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Filter Logs:"))

        self.log_search_input = QLineEdit()
        self.log_search_input.setPlaceholderText("Filter logs by text...")
        self.log_search_input.textChanged.connect(self.filter_log_view)
        filter_bar.addWidget(self.log_search_input)

        self.log_filter_combo = QComboBox()
        self.log_filter_combo.addItems(["All Events", "Status Changes Only", "Errors Only"])
        self.log_filter_combo.currentIndexChanged.connect(self.filter_log_view)
        filter_bar.addWidget(self.log_filter_combo)

        btn_open_log_folder = QPushButton("📂 Open Folder")
        btn_open_log_folder.clicked.connect(self.open_log_directory)
        filter_bar.addWidget(btn_open_log_folder)

        btn_clear_log = QPushButton("🗑 Clear View")
        btn_clear_log.clicked.connect(self.clear_log_view)
        filter_bar.addWidget(btn_clear_log)

        layout.addLayout(filter_bar)
        layout.addWidget(self.log_display)

        log_group.setLayout(layout)
        return log_group

    # --- THEMES & APPEARANCE ---
    def toggle_theme_mode(self):
        current_dark = self.settings_manager.get_setting("UI", "dark_mode", bool)
        new_mode = not current_dark
        self.apply_theme(new_mode)
        self.settings_manager.set_setting("UI", "dark_mode", str(new_mode))
        self.save_load_worker.save_settings_async()

    def apply_theme(self, is_dark: bool):
        palette = get_dark_palette() if is_dark else get_light_palette()
        app = QApplication.instance()
        theme_qss = get_dark_theme() if is_dark else get_light_theme()
        if app:
            app.setPalette(palette)
            app.setStyleSheet(theme_qss)
        self.setStyleSheet(theme_qss)
        self.sparkline_widget.set_dark_mode(is_dark)
        self.btn_theme_toggle.setText("☀️ Light Mode" if is_dark else "🌙 Dark Mode")
        for dlg in self.active_diagnostic_dialogs:
            try:
                dlg.setStyleSheet(theme_qss)
            except Exception:
                pass

        if hasattr(self, 'floating_hud') and self.floating_hud:
            self.floating_hud.set_theme(is_dark)

    # --- METRICS DOCK POSITION ---
    def toggle_dashboard_dock_position(self):
        current_pos = self.settings_manager.get_setting("UI", "dashboard_position") or "top"
        new_pos = "sidebar" if current_pos == "top" else "top"
        self.settings_manager.set_setting("UI", "dashboard_position", new_pos)
        self.save_load_worker.save_settings_async()

        # Re-parent the metrics banner & sparkline widget
        self.metrics_banner.setParent(None)
        self.sparkline_widget.setParent(None)

        if new_pos == "sidebar":
            self.metrics_banner.set_sidebar_mode(True)
            self.sidebar_metrics_container.layout().addWidget(self.metrics_banner)
            self.sidebar_metrics_container.layout().addWidget(self.sparkline_widget)
        else:
            self.metrics_banner.set_sidebar_mode(False)
            self.top_metrics_container.layout().addWidget(self.metrics_banner)
            self.right_panel_sparkline_container.layout().addWidget(self.sparkline_widget)

        self.metrics_banner.show()
        self.sparkline_widget.show()

    # --- FLOATING MINI HUD ---
    def _on_hud_closed(self):
        self.btn_toggle_hud.setChecked(False)
        self.settings_manager.set_setting("UI", "enable_floating_hud", "False")
        self.save_load_worker.save_settings_async()

    def toggle_floating_hud(self):
        if self.floating_hud.isVisible():
            self.floating_hud.hide()
            self.btn_toggle_hud.setChecked(False)
            self.settings_manager.set_setting("UI", "enable_floating_hud", "False")
        else:
            self.floating_hud.update_hud(self.ip_data_model.monitored_ips)
            self.floating_hud.show()
            self.btn_toggle_hud.setChecked(True)
            self.settings_manager.set_setting("UI", "enable_floating_hud", "True")
        self.save_load_worker.save_settings_async()

    # --- IP RANGE SCANNER ---
    def open_ip_range_scanner(self):
        dlg = IpRangeScannerDialog(self)
        dlg.add_hosts_requested.connect(self.batch_add_ips)
        dlg.exec()

    def batch_add_ips(self, host_tuples: list):
        added_count = 0
        for ip, desc in host_tuples:
            if self.ip_data_model.add_ip(ip, desc, tag="Scanned"):
                added_count += 1
        if added_count > 0:
            self.refresh_category_tabs()
            self.update_ip_status_table(full_rebuild=True)
            self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)
            self.log_manager.log_incident(f"Batch imported {added_count} host(s) from IP Scanner.")

    # --- DIAGNOSTIC TOOLS & BATCH CONTEXT MENU ---
    def _open_diagnostic_dialog(self, dialog_class, target_ip: str, minimized: bool = False):
        """Opens a modeless diagnostic dialog so the main window and other hosts stay 100% interactive."""
        # If already open for this IP, bring it to front or minimize as requested
        for open_dlg in self.active_diagnostic_dialogs:
            dlg_target = getattr(open_dlg, 'target_ip', getattr(open_dlg, 'target', None))
            if isinstance(open_dlg, dialog_class) and dlg_target == target_ip:
                if minimized:
                    open_dlg.showMinimized()
                else:
                    if open_dlg.isMinimized():
                        open_dlg.showNormal()
                    open_dlg.raise_()
                    open_dlg.activateWindow()
                return open_dlg

        # Pass parent=None so this window is an independent desktop window and does NOT minimize with the main app!
        dlg = dialog_class(target_ip, parent=None)
        dlg.setWindowIcon(self.windowIcon())
        is_dark = self.settings_manager.get_setting("UI", "dark_mode", bool)
        theme_qss = get_dark_theme() if (is_dark if is_dark is not None else True) else get_light_theme()
        dlg.setStyleSheet(theme_qss)
        self.active_diagnostic_dialogs.append(dlg)
        dlg.finished.connect(lambda _: self._cleanup_diagnostic_dialog(dlg))
        if minimized:
            dlg.showMinimized()
        else:
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        return dlg

    def _cleanup_diagnostic_dialog(self, dlg):
        if dlg in self.active_diagnostic_dialogs:
            self.active_diagnostic_dialogs.remove(dlg)

    def show_host_context_menu(self, pos):
        clicked_item = self.ip_status_table.itemAt(pos)
        if not clicked_item:
            return
        clicked_row = clicked_item.row()

        selected_indexes = self.ip_status_table.selectionModel().selectedRows()
        selected_rows = sorted(list(set(idx.row() for idx in selected_indexes)))

        # Allow Ctrl + Right Click to append to selection
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if clicked_row not in selected_rows:
                selected_rows.append(clicked_row)
                self.ip_status_table.setRangeSelected(
                    QTableWidgetSelectionRange(clicked_row, 0, clicked_row, self.ip_status_table.columnCount() - 1),
                    True
                )
        elif clicked_row not in selected_rows:
            self.ip_status_table.selectRow(clicked_row)
            selected_rows = [clicked_row]

        selected_ips = []
        selected_monitors = []
        for r in selected_rows:
            ip_item = self.ip_status_table.item(r, 0)
            if ip_item:
                ip_str = ip_item.text().strip()
                selected_ips.append(ip_str)
                m = next((mon for mon in self.ip_data_model.monitored_ips if mon.ip_address == ip_str), None)
                if m:
                    selected_monitors.append(m)

        if not selected_ips or not selected_monitors:
            return

        count = len(selected_monitors)
        menu = QMenu(self)

        if count == 1:
            target_ip = selected_ips[0]
            m = selected_monitors[0]
            desc = m.description if m.description and m.description != target_ip else ""
            title_text = f"🎯 Host: {target_ip} ({desc})" if desc else f"🎯 Host: {target_ip}"
            title_action = QAction(title_text, menu)
            title_action.setEnabled(False)
            menu.addAction(title_action)
            menu.addSeparator()

            # Modeless Diagnostics (Allows clicking/pinging other hosts while open!)
            act_cping = menu.addAction("Live Continuous Ping")
            act_cping.triggered.connect(lambda: self._open_diagnostic_dialog(ContinuousPingDialog, target_ip, minimized=False))

            act_cping_min = menu.addAction("🗕 Live Continuous Ping (Minimized)")
            act_cping_min.triggered.connect(lambda: self._open_diagnostic_dialog(ContinuousPingDialog, target_ip, minimized=True))

            act_trace = menu.addAction("Traceroute (tracert)")
            act_trace.triggered.connect(lambda: self._open_diagnostic_dialog(TracerouteDialog, target_ip))

            act_ports = menu.addAction("TCP Port Checker")
            act_ports.triggered.connect(lambda: self._open_diagnostic_dialog(PortCheckerDialog, target_ip))

            act_dns = menu.addAction("DNS & Reverse Lookup")
            act_dns.triggered.connect(lambda: self._open_diagnostic_dialog(DnsLookupDialog, target_ip))

            menu.addSeparator()

            # Quick Actions
            act_http = menu.addAction("Open in Browser (HTTP)")
            act_http.triggered.connect(lambda: webbrowser.open(f"http://{target_ip}"))

            act_https = menu.addAction("Open in Browser (HTTPS)")
            act_https.triggered.connect(lambda: webbrowser.open(f"https://{target_ip}"))

            act_rdp = menu.addAction("Remote Desktop (RDP)")
            act_rdp.triggered.connect(lambda: subprocess.Popen(["mstsc.exe", f"/v:{target_ip}"]))

        else:
            # Multi-host Header
            title_action = QAction(f"⚡ Batch Actions: {count} Hosts Selected", menu)
            title_action.setEnabled(False)
            menu.addAction(title_action)
            menu.addSeparator()

            # Multi-Host Diagnostics (Opens non-modal windows for all selected hosts)
            act_cping_all = menu.addAction(f"Live Continuous Ping ({count} Hosts)")
            act_cping_all.triggered.connect(lambda: self._batch_continuous_ping(selected_ips, minimized=False))

            act_cping_min_all = menu.addAction(f"🗕 Live Continuous Ping All ({count} Hosts, Minimized)")
            act_cping_min_all.triggered.connect(lambda: self._batch_continuous_ping(selected_ips, minimized=True))

            act_trace_all = menu.addAction(f"Traceroute ({count} Hosts)")
            act_trace_all.triggered.connect(lambda: self._batch_traceroute(selected_ips))

            act_ports_all = menu.addAction(f"Port Checker ({count} Hosts)")
            act_ports_all.triggered.connect(lambda: self._batch_port_checker(selected_ips))

            act_dns_all = menu.addAction(f"DNS Lookup ({count} Hosts)")
            act_dns_all.triggered.connect(lambda: self._batch_dns_lookup(selected_ips))

            menu.addSeparator()

            act_http_all = menu.addAction(f"Open All in Browser (HTTP)")
            act_http_all.triggered.connect(lambda: self._batch_open_browser(selected_ips, "http"))

            act_https_all = menu.addAction(f"Open All in Browser (HTTPS)")
            act_https_all.triggered.connect(lambda: self._batch_open_browser(selected_ips, "https"))

        menu.addSeparator()

        # Selection Options Submenu
        sel_menu = menu.addMenu("☑️ Selection Options")
        act_sel_all = sel_menu.addAction("Select All Hosts (Ctrl+A)")
        act_sel_all.triggered.connect(self.ip_status_table.selectAll)
        act_clear_sel = sel_menu.addAction("Clear Selection")
        act_clear_sel.triggered.connect(self.ip_status_table.clearSelection)

        # Batch & Single Alert Controls Submenu
        alert_menu = menu.addMenu(f"🔔 Alert Settings ({count} host{'s' if count > 1 else ''})")
        act_on_email = alert_menu.addAction("📧 Enable Email Alerts")
        act_on_email.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "email", True))
        act_off_email = alert_menu.addAction("📧 Disable Email Alerts")
        act_off_email.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "email", False))

        alert_menu.addSeparator()
        act_on_popup = alert_menu.addAction("💬 Enable Popup Alerts")
        act_on_popup.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "popup", True))
        act_off_popup = alert_menu.addAction("💬 Disable Popup Alerts")
        act_off_popup.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "popup", False))

        alert_menu.addSeparator()
        act_on_sound = alert_menu.addAction("🔊 Enable Sound Alerts")
        act_on_sound.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "sound", True))
        act_off_sound = alert_menu.addAction("🔊 Disable Sound Alerts")
        act_off_sound.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "sound", False))

        alert_menu.addSeparator()
        act_on_webhook = alert_menu.addAction("🔗 Enable Webhook Alerts")
        act_on_webhook.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "webhook", True))
        act_off_webhook = alert_menu.addAction("🔗 Disable Webhook Alerts")
        act_off_webhook.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "webhook", False))

        alert_menu.addSeparator()
        act_on_all = alert_menu.addAction("✅ Enable ALL Alerts")
        act_on_all.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "all", True))
        act_off_all = alert_menu.addAction("❌ Disable ALL Alerts")
        act_off_all.triggered.connect(lambda: self._batch_set_alert(selected_monitors, "all", False))

        # Change Group / Tag
        act_set_group = menu.addAction(f"🏷️ Set Group / Tag for {count} Host{'s' if count > 1 else ''}...")
        act_set_group.triggered.connect(lambda: self._batch_set_group_tag(selected_monitors))

        # Reset Stats
        act_reset_stats = menu.addAction(f"🔄 Reset Statistics ({count} host{'s' if count > 1 else ''})")
        act_reset_stats.triggered.connect(lambda: self._batch_reset_statistics(selected_monitors))

        menu.addSeparator()

        # Clipboard
        if count == 1:
            act_copy = menu.addAction("📋 Copy IP Address")
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(selected_ips[0]))
        else:
            clip_menu = menu.addMenu(f"📋 Copy to Clipboard ({count} hosts)")
            act_copy_ips = clip_menu.addAction("Copy IP List (One per line)")
            act_copy_ips.triggered.connect(lambda: self._batch_copy_ips(selected_ips, as_table=False))
            act_copy_csv = clip_menu.addAction("Copy Host Details (TSV Table)")
            act_copy_csv.triggered.connect(lambda: self._batch_copy_ips(selected_monitors, as_table=True))

        menu.addSeparator()

        # Removal
        remove_label = "🗑️ Remove Host" if count == 1 else f"🗑️ Remove {count} Selected Hosts"
        act_remove = menu.addAction(remove_label)
        act_remove.triggered.connect(lambda: self._batch_remove_hosts(selected_ips))

        menu.exec(self.ip_status_table.viewport().mapToGlobal(pos))

    def _batch_set_alert(self, monitors: list, alert_type: str, enabled: bool):
        for m in monitors:
            if alert_type == "email":
                m.enable_email_alerts_for_ip = enabled
            elif alert_type == "popup":
                m.enable_popup_alerts_for_ip = enabled
            elif alert_type == "sound":
                m.enable_sound_alerts_for_ip = enabled
            elif alert_type == "webhook":
                m.enable_webhook_alerts_for_ip = enabled
            elif alert_type == "all":
                m.enable_email_alerts_for_ip = enabled
                m.enable_popup_alerts_for_ip = enabled
                m.enable_sound_alerts_for_ip = enabled
                m.enable_webhook_alerts_for_ip = enabled

            if m.ip_address in self.ip_to_row_map:
                row = self.ip_to_row_map[m.ip_address]
                self._update_table_row_content(row, m)

        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)
        state_str = "enabled" if enabled else "disabled"
        self.log_manager.log_incident(f"Batch {alert_type} alerts {state_str} for {len(monitors)} host(s).")

    def _batch_set_group_tag(self, monitors: list):
        default_tag = getattr(monitors[0], 'tag', 'General') if monitors else "General"
        new_tag, ok = QInputDialog.getText(
            self, "Set Group / Tag",
            f"Enter new group/tag name for {len(monitors)} selected host(s):",
            text=default_tag
        )
        if not ok:
            return
        new_tag = new_tag.strip() or "General"
        for m in monitors:
            m.tag = new_tag
            if m.ip_address in self.ip_to_row_map:
                row = self.ip_to_row_map[m.ip_address]
                self._update_table_row_content(row, m)

        self.refresh_category_tabs()
        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)
        self.log_manager.log_incident(f"Assigned group '{new_tag}' to {len(monitors)} host(s).")

    def _batch_reset_statistics(self, monitors: list):
        count = len(monitors)
        reply = QMessageBox.question(
            self, "Reset Statistics",
            f"Are you sure you want to reset packet loss, uptime, downtime, and latency history for {count} host(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for m in monitors:
            m.total_pings = 0
            m.failed_pings = 0
            m.packet_loss = 0.0
            m.latency_history.clear()
            m.ping_history.clear()
            m.response_time = 0.0
            m.uptime = "0s"
            m.downtime = "0s"
            m.unreachable_start_time = None
            if m.status == "Reachable":
                m.reachable_start_time = datetime.now()
            if m.ip_address in self.ip_to_row_map:
                row = self.ip_to_row_map[m.ip_address]
                self._update_table_row_content(row, m)

        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)
        self.log_manager.log_incident(f"Reset telemetry statistics for {count} host(s).")

    def _batch_copy_ips(self, items: list, as_table: bool = False):
        if not items:
            return
        if not as_table:
            text = "\n".join(str(ip) for ip in items)
        else:
            lines = ["IP Address\tDescription\tTag\tStatus\tPacket Loss\tLatency\tUptime\tDowntime"]
            for m in items:
                lines.append(f"{m.ip_address}\t{m.description}\t{getattr(m, 'tag', 'General')}\t{m.status}\t{m.packet_loss:.1f}%\t{m.response_time:.1f}ms\t{m.uptime}\t{m.downtime}")
            text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        self.log_manager.log_incident(f"Copied {len(items)} host(s) data to clipboard.")

    def _batch_open_browser(self, ips: list, protocol: str = "http"):
        if len(ips) > 5:
            reply = QMessageBox.question(
                self, "Open in Browser",
                f"You have selected {len(ips)} hosts. Opening all of them will launch {len(ips)} browser tabs.\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        for ip in ips:
            webbrowser.open(f"{protocol}://{ip}")

    def _batch_continuous_ping(self, ips: list, minimized: bool = False):
        if len(ips) > 6:
            target_desc = "minimized to taskbar" if minimized else "on screen"
            reply = QMessageBox.question(
                self, "Continuous Ping",
                f"You have selected {len(ips)} hosts. Launching continuous ping will open {len(ips)} live diagnostic windows ({target_desc}).\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        for ip in ips:
            self._open_diagnostic_dialog(ContinuousPingDialog, ip, minimized=minimized)

    def _batch_traceroute(self, ips: list):
        if len(ips) > 5:
            reply = QMessageBox.question(
                self, "Traceroute",
                f"You have selected {len(ips)} hosts. Launching traceroute will open {len(ips)} diagnostic windows.\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        for ip in ips:
            self._open_diagnostic_dialog(TracerouteDialog, ip)

    def _batch_port_checker(self, ips: list):
        if len(ips) > 5:
            reply = QMessageBox.question(
                self, "Port Checker",
                f"You have selected {len(ips)} hosts. Launching port checker will open {len(ips)} diagnostic windows.\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        for ip in ips:
            self._open_diagnostic_dialog(PortCheckerDialog, ip)

    def _batch_dns_lookup(self, ips: list):
        if len(ips) > 5:
            reply = QMessageBox.question(
                self, "DNS Lookup",
                f"You have selected {len(ips)} hosts. Launching DNS lookup will open {len(ips)} diagnostic windows.\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        for ip in ips:
            self._open_diagnostic_dialog(DnsLookupDialog, ip)

    def _batch_remove_hosts(self, ips: list):
        count = len(ips)
        if count == 0:
            return
        if count == 1:
            msg = f"Are you sure you want to remove '{ips[0]}' from monitoring?"
        else:
            msg = f"Are you sure you want to remove {count} selected hosts from monitoring?"

        reply = QMessageBox.question(
            self, "Confirm Remove", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for ip in ips:
                self.ip_data_model.remove_ip(ip)

    def confirm_remove_ip(self, ip_address: str):
        self._batch_remove_hosts([ip_address])

    # --- COLUMN VISIBILITY CHOOSER ---
    def show_header_context_menu(self, pos):
        menu = QMenu(self)
        self._populate_column_menu(menu)
        menu.exec(self.ip_status_table.horizontalHeader().mapToGlobal(pos))

    def open_column_selector_menu(self):
        menu = QMenu(self)
        self._populate_column_menu(menu)
        menu_width = menu.sizeHint().width()
        pos = self.btn_cols.mapToGlobal(QPoint(self.btn_cols.width() - menu_width, self.btn_cols.height() + 2))
        menu.exec(pos)

    def _populate_column_menu(self, menu: QMenu):
        title_act = menu.addAction("Configure Columns")
        title_act.setEnabled(False)
        title_act.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        menu.addSeparator()

        for col in range(self.ip_status_table.columnCount()):
            header_text = self.ip_status_table.horizontalHeaderItem(col).text()
            act = QAction(header_text, menu)
            act.setCheckable(True)
            act.setChecked(not self.ip_status_table.isColumnHidden(col))
            act.toggled.connect(lambda checked, c=col: self.set_column_visible(c, checked))
            menu.addAction(act)

        menu.addSeparator()
        act_autofit = menu.addAction("Auto-Fit Columns")
        act_autofit.triggered.connect(self.ip_status_table.resizeColumnsToContents)

    def set_column_visible(self, col: int, visible: bool):
        self.ip_status_table.setColumnHidden(col, not visible)
        visible_cols = [str(c) for c in range(self.ip_status_table.columnCount()) if not self.ip_status_table.isColumnHidden(c)]
        self.settings_manager.set_setting("UI", "visible_columns", ",".join(visible_cols))
        self.save_load_worker.save_settings_async()

    # --- CATEGORY / TAG DROPDOWN ---
    def refresh_category_tabs(self):
        tags = sorted(list({getattr(m, 'tag', 'General') for m in self.ip_data_model.monitored_ips if getattr(m, 'tag', None)}))
        current_text = self.category_dropdown.currentText()

        self.category_dropdown.blockSignals(True)
        self.category_dropdown.clear()
        self.category_dropdown.addItem("All")
        for tag in tags:
            if tag and tag != "All":
                self.category_dropdown.addItem(tag)

        # Restore previous selection if it exists, else default to "All"
        idx = self.category_dropdown.findText(current_text)
        if idx >= 0:
            self.category_dropdown.setCurrentIndex(idx)
        else:
            self.category_dropdown.setCurrentIndex(0)
            self.active_category_filter = "All"
        self.category_dropdown.blockSignals(False)

    def on_category_dropdown_changed(self, text: str):
        self.active_category_filter = text if text else "All"
        self.filter_ip_status_table(self.ip_table_search_input.text())

    def on_category_tab_changed(self, index: int):
        self.on_category_dropdown_changed(self.category_dropdown.currentText())

    # --- TABLE SEARCH & FILTERING ---
    def filter_ip_status_table(self, text: str):
        text = text.strip().lower()
        category = self.active_category_filter

        for row in range(self.ip_status_table.rowCount()):
            ip_item = self.ip_status_table.item(row, 0)
            desc_item = self.ip_status_table.item(row, 1)
            tag_item = self.ip_status_table.item(row, 2)
            status_item = self.ip_status_table.item(row, 3)

            # Category matching
            matches_category = (category == "All") or (tag_item and tag_item.text() == category)

            # Search text matching
            matches_text = True
            if text:
                matches_text = any(item and text in item.text().lower() for item in [ip_item, desc_item, tag_item, status_item])

            self.ip_status_table.setRowHidden(row, not (matches_category and matches_text))

    # --- LOG SEARCH & FILTERING ---
    def handle_incoming_log_message(self, message: str):
        self.log_records.append(message)
        if self._message_matches_filter(message):
            self.log_display.append(message)
            self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())

    def _message_matches_filter(self, message: str) -> bool:
        search_text = self.log_search_input.text().strip().lower()
        filter_mode = self.log_filter_combo.currentText()
        msg_lower = message.lower()

        if filter_mode == "Status Changes Only":
            if not any(k in msg_lower for k in ["status", "reachable", "unreachable", "online", "offline", "is now"]):
                return False
        elif filter_mode == "Errors Only":
            if not any(k in msg_lower for k in ["error", "fail", "critical", "timed out"]):
                return False

        if search_text and search_text not in msg_lower:
            return False

        return True

    def filter_log_view(self):
        search_text = self.log_search_input.text().strip().lower()
        filter_mode = self.log_filter_combo.currentText()

        self.log_display.setUpdatesEnabled(False)
        self.log_display.clear()

        matching_lines = [msg for msg in self.log_records if self._message_matches_filter(msg)]

        if matching_lines:
            self.log_display.setPlainText("\n".join(matching_lines))
            self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
        elif search_text or filter_mode != "All Events":
            criteria = f"'{search_text}'" if search_text else f"mode '{filter_mode}'"
            self.log_display.setPlainText(f"--- No logs matching {criteria} ---")

        self.log_display.setUpdatesEnabled(True)

    def clear_log_view(self):
        self.log_records.clear()
        self.log_display.clear()

    def open_log_directory(self):
        # 1. Check UI input field
        log_dir = self.log_directory_input.text().strip() if hasattr(self, 'log_directory_input') and self.log_directory_input.text().strip() else ""
        if not log_dir or not os.path.exists(os.path.normpath(log_dir)):
            log_dir = self.settings_manager.get_setting("LOGGING", "log_directory") or ""
        if not log_dir or not os.path.exists(os.path.normpath(log_dir)):
            log_dir = getattr(self.log_manager.log_worker, 'base_log_directory', "")

        # Attempt to create directory if valid path
        if log_dir:
            try:
                os.makedirs(os.path.normpath(log_dir), exist_ok=True)
            except Exception:
                pass

        # Fallback to local workspace logs or Documents if configured path was invalid (e.g. unmounted drive)
        if not log_dir or not os.path.exists(os.path.normpath(log_dir)):
            log_dir = os.path.normpath(r"D:\AntiGravity\D IP Monitor\logs")
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                log_dir = os.path.normpath(os.path.join(os.path.expanduser("~"), "Documents", "IPMonitorLogs"))
                os.makedirs(log_dir, exist_ok=True)

        log_dir = os.path.normpath(log_dir)

        if os.path.exists(log_dir):
            if sys.platform == "win32":
                log_file = os.path.join(log_dir, "incident_log.txt")
                if os.path.exists(log_file):
                    subprocess.Popen(f'explorer /select,"{os.path.normpath(log_file)}"')
                else:
                    os.startfile(log_dir)
            else:
                subprocess.Popen(["xdg-open", log_dir])
        else:
            QMessageBox.warning(self, "Directory Not Found", f"Log directory could not be opened:\n{log_dir}")

    # --- TABLE RENDERING & BATCHED UI UPDATES ---
    def on_table_item_clicked(self, index):
        row = index.row()
        ip_item = self.ip_status_table.item(row, 0)
        desc_item = self.ip_status_table.item(row, 1)
        if ip_item:
            self.current_selected_ip = ip_item.text()
            monitor = next((m for m in self.ip_data_model.monitored_ips if m.ip_address == self.current_selected_ip), None)
            if monitor:
                desc = desc_item.text() if desc_item else monitor.description
                self.sparkline_widget.set_host_data(monitor.ip_address, desc, monitor.latency_history)

    def update_ip_status_table(self, target_ip_address: str = None, full_rebuild: bool = False):
        self.ip_status_table.setSortingEnabled(False)
        self.ip_status_table.setUpdatesEnabled(False)

        if full_rebuild:
            self.ip_to_row_map.clear()
            self.ip_status_table.setRowCount(len(self.ip_data_model.monitored_ips))
            for row, monitor in enumerate(self.ip_data_model.monitored_ips):
                self.ip_to_row_map[monitor.ip_address] = row
                self._update_table_row_content(row, monitor)
            self.refresh_category_tabs()
        elif target_ip_address and target_ip_address in self.ip_to_row_map:
            row = self.ip_to_row_map[target_ip_address]
            monitor = next((m for m in self.ip_data_model.monitored_ips if m.ip_address == target_ip_address), None)
            if monitor:
                self._update_table_row_content(row, monitor)

        self.ip_status_table.setUpdatesEnabled(True)
        self._update_dashboard_kpis()

    def _update_table_row_content(self, row: int, monitor: IpMonitor):
        # Column 0: IP Address
        self._set_or_update_item(row, 0, monitor.ip_address, Qt.AlignmentFlag.AlignLeft)

        # Column 1: Description
        self._set_or_update_item(row, 1, monitor.description, Qt.AlignmentFlag.AlignLeft)

        # Column 2: Tag / Category
        self._set_or_update_item(row, 2, getattr(monitor, 'tag', 'General'), Qt.AlignmentFlag.AlignCenter)

        # Column 3: Status
        status_item = self.ip_status_table.item(row, 3)
        is_online = (monitor.status == "Reachable")
        status_text = "● ONLINE" if is_online else "● OFFLINE"
        if not status_item:
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ip_status_table.setItem(row, 3, status_item)
        else:
            if status_item.text() != status_text:
                status_item.setText(status_text)

        status_color = QColor("#10b981") if is_online else QColor("#ef4444")
        status_item.setForeground(status_color)
        status_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

        # Column 4: Uptime
        self._set_or_update_item(row, 4, monitor.uptime, Qt.AlignmentFlag.AlignCenter)

        # Column 5: Downtime
        self._set_or_update_item(row, 5, monitor.downtime, Qt.AlignmentFlag.AlignCenter)

        # Column 6: Packet Loss (0%, 5%, 10%, 15%, 20%...)
        loss_val = int(round(monitor.packet_loss / 5.0) * 5)
        self._set_or_update_item(row, 6, f"{loss_val}%", Qt.AlignmentFlag.AlignCenter)
        loss_item = self.ip_status_table.item(row, 6)
        if loss_item:
            if loss_val == 0:
                loss_item.setForeground(QColor("#10b981"))
            elif loss_val < 50:
                loss_item.setForeground(QColor("#f59e0b"))
            else:
                loss_item.setForeground(QColor("#ef4444"))

        # Column 7: Latency
        latency_str = f"{int(monitor.response_time)} ms" if monitor.status == "Reachable" else "—"
        self._set_or_update_item(row, 7, latency_str, Qt.AlignmentFlag.AlignCenter)

        # Checkboxes: Column 8 (Email), Column 9 (Popup), Column 10 (Sound), Column 11 (Webhook)
        self._ensure_checkbox_widget(row, 8, monitor, "email", monitor.enable_email_alerts_for_ip)
        self._ensure_checkbox_widget(row, 9, monitor, "popup", monitor.enable_popup_alerts_for_ip)
        self._ensure_checkbox_widget(row, 10, monitor, "sound", monitor.enable_sound_alerts_for_ip)
        self._ensure_checkbox_widget(row, 11, monitor, "webhook", getattr(monitor, "enable_webhook_alerts_for_ip", True))

        # Row background highlight for Unreachable hosts
        row_bg = QColor("#450a0a" if self.settings_manager.get_setting("UI", "dark_mode", bool) else "#fee2e2") if monitor.status == "Unreachable" else QColor(0,0,0,0)
        for col in range(self.ip_status_table.columnCount()):
            it = self.ip_status_table.item(row, col)
            if it:
                it.setData(Qt.ItemDataRole.BackgroundRole, QBrush(row_bg))

    def _set_or_update_item(self, row: int, col: int, text: str, alignment: Qt.AlignmentFlag):
        item = self.ip_status_table.item(row, col)
        if not item:
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(alignment)
            self.ip_status_table.setItem(row, col, item)
        elif item.text() != text:
            item.setText(text)

    def _ensure_checkbox_widget(self, row: int, col: int, monitor: IpMonitor, setting_name: str, current_val: bool):
        chk = self.ip_status_table.cellWidget(row, col)
        if not isinstance(chk, QCheckBox):
            chk = QCheckBox()
            chk.setStyleSheet("margin-left: 12px;")
            chk.stateChanged.connect(self._on_cell_checkbox_toggled)
            self.ip_status_table.setCellWidget(row, col, chk)

        # Always bind current IP address and setting name as dynamic Qt properties
        chk.setProperty("ip_address", monitor.ip_address)
        chk.setProperty("setting_name", setting_name)

        if chk.isChecked() != current_val:
            chk.blockSignals(True)
            chk.setChecked(current_val)
            chk.blockSignals(False)

    def _on_cell_checkbox_toggled(self, state: int):
        sender = self.sender()
        if not sender:
            return
        ip = sender.property("ip_address")
        setting = sender.property("setting_name")
        if not ip or not setting:
            return

        is_checked = (state == Qt.CheckState.Checked.value)
        monitor = next((m for m in self.ip_data_model.monitored_ips if m.ip_address == ip), None)
        if monitor:
            if setting == "email":
                monitor.enable_email_alerts_for_ip = is_checked
            elif setting == "popup":
                monitor.enable_popup_alerts_for_ip = is_checked
            elif setting == "sound":
                monitor.enable_sound_alerts_for_ip = is_checked
            elif setting == "webhook":
                monitor.enable_webhook_alerts_for_ip = is_checked
            self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)

    def _process_ui_updates(self):
        """Batched UI processor run by QTimer every 150ms to ensure 0% freeze."""
        if not self.ips_to_update_ui:
            return

        ips_to_process = list(self.ips_to_update_ui)
        self.ips_to_update_ui.clear()

        self.ip_status_table.setUpdatesEnabled(False)
        for ip_address in ips_to_process:
            if ip_address in self.ip_to_row_map:
                row = self.ip_to_row_map[ip_address]
                monitor = next((m for m in self.ip_data_model.monitored_ips if m.ip_address == ip_address), None)
                if monitor:
                    self._update_table_row_content(row, monitor)
                    if self.current_selected_ip == ip_address:
                        self.sparkline_widget.set_host_data(monitor.ip_address, monitor.description, monitor.latency_history)
        self.ip_status_table.setUpdatesEnabled(True)

        self._update_dashboard_kpis()
        if self.floating_hud.isVisible():
            self.floating_hud.update_hud(self.ip_data_model.monitored_ips)

    def _update_dashboard_kpis(self):
        monitors = self.ip_data_model.monitored_ips
        total = len(monitors)
        online = sum(1 for m in monitors if m.status == "Reachable")
        offline = sum(1 for m in monitors if m.status == "Unreachable")
        reachables = [m.response_time for m in monitors if m.status == "Reachable" and m.response_time > 0]
        avg_rtt = (sum(reachables) / len(reachables)) if reachables else 0.0
        health = (online / total * 100) if total > 0 else 100.0

        self.metrics_banner.update_metrics(total, online, offline, avg_rtt, health)
        self.system_tray_manager.update_tray_icon(has_offline_hosts=(offline > 0))

    # --- MODEL SIGNAL HANDLERS ---
    def _handle_ip_added_to_model(self, monitor: IpMonitor):
        self.update_ip_status_table(full_rebuild=True)
        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)

    def _handle_ip_removed_from_model(self, ip_address: str):
        self.update_ip_status_table(full_rebuild=True)
        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)

    def _handle_ip_updated_in_model(self, ip_address: str):
        # Add to batched UI update set; do NOT save to disk on every ping tick
        self.ips_to_update_ui.add(ip_address)

    def _handle_status_changed_in_model(self, monitor: IpMonitor, old_status: str, new_status: str):
        # Save to disk on real state transition
        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)
        # Windows native toast via system tray
        if self.settings_manager.get_setting("ALERTS", "enable_popups", bool) and getattr(monitor, "enable_popup_alerts_for_ip", True):
            is_down = (new_status == "Unreachable")
            title = "⚠️ Host Down!" if is_down else "🟢 Host Recovered"
            msg = f"{monitor.ip_address} ({monitor.description}) is {new_status}!"
            self.system_tray_manager.show_toast(title, msg, is_warning=is_down)

    def on_webhook_platform_changed(self, new_platform: str):
        """Swaps active input text to the individual URL saved for this platform."""
        if not hasattr(self, 'platform_webhook_urls'):
            self.platform_webhook_urls = {}

        # Save whatever was in the input for the previous platform
        if hasattr(self, '_current_webhook_platform') and self._current_webhook_platform:
            self.platform_webhook_urls[self._current_webhook_platform] = self.webhook_url_input.text().strip()

        self._current_webhook_platform = new_platform
        url = self.platform_webhook_urls.get(new_platform, "")
        self.webhook_url_input.blockSignals(True)
        self.webhook_url_input.setText(url)
        self.webhook_url_input.blockSignals(False)

        placeholders = {
            "Discord": "https://discord.com/api/webhooks/...",
            "Slack": "https://hooks.slack.com/services/...",
            "Teams": "https://outlook.office.com/webhook/...",
            "Telegram": "https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<ID>",
            "Generic JSON": "https://api.yourdomain.com/webhook"
        }
        self.webhook_url_input.setPlaceholderText(placeholders.get(new_platform, "https://..."))

    def _send_webhook_alert(self, host_ip: str, host_desc: str, is_down: bool, downtime: str):
        if not self.settings_manager.get_setting("WEBHOOK", "enable_webhooks", bool):
            return
        w_type = self.settings_manager.get_setting("WEBHOOK", "webhook_type") or "Discord"
        url = self.settings_manager.get_webhook_url_for_platform(w_type)
        if not url:
            url = self.settings_manager.get_setting("WEBHOOK", "webhook_url")
        if url:
            self.webhook_notifier.send_notification_async(url, w_type, host_ip, host_desc, is_down, downtime)

    # --- BULK CSV / TXT & .DIPM BACKUP ---
    def import_hosts_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Hosts (CSV / TXT)", "", "Data Files (*.csv *.txt)")
        if not path:
            return
        try:
            hosts = BulkManager.import_hosts_from_file(path)
            added = 0
            for ip, desc, tag in hosts:
                if self.ip_data_model.add_ip(ip, desc, tag=tag):
                    added += 1
            if added > 0:
                self.refresh_category_tabs()
                self.update_ip_status_table(full_rebuild=True)
                self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)
            QMessageBox.information(self, "Import Complete", f"Successfully imported {added} host(s).")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")

    def export_hosts_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Hosts to CSV", "D_IP_Monitor_Hosts.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            BulkManager.export_hosts_to_csv(self.ip_data_model.monitored_ips, path)
            QMessageBox.information(self, "Export Complete", f"Saved hosts list to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def backup_profile_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Backup Profile", "DIPMonitor_Backup.dipm", "D IP Monitor Profile (*.dipm)")
        if not path:
            return
        try:
            settings_dict = {sec: dict(self.settings_manager.config[sec]) for sec in self.settings_manager.config.sections()}
            BulkManager.export_profile_dipm(path, settings_dict, self.ip_data_model.monitored_ips)
            QMessageBox.information(self, "Backup Complete", f"Profile backup saved successfully:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Failed to backup profile: {e}")

    def restore_profile_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore Backup Profile", "", "D IP Monitor Profile (*.dipm)")
        if not path:
            return
        try:
            settings_dict, hosts_data = BulkManager.import_profile_dipm(path)
            for sec, options in settings_dict.items():
                for k, v in options.items():
                    self.settings_manager.set_setting(sec, k, str(v))
            self.settings_manager.save_settings()

            self.ip_data_model.monitored_ips = [IpMonitor.from_dict(h) for h in hosts_data]
            self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)

            self.load_settings_to_ui()
            self.refresh_category_tabs()
            self.update_ip_status_table(full_rebuild=True)
            QMessageBox.information(self, "Restore Complete", f"Restored profile with {len(hosts_data)} host(s).")
        except Exception as e:
            QMessageBox.critical(self, "Restore Error", f"Failed to restore profile: {e}")

    # --- SETTINGS LOAD / SAVE ---
    def load_settings_to_ui(self):
        self.smtp_server_input.setText(self.settings_manager.get_setting("EMAIL", "smtp_server"))
        self.smtp_port_input.setText(self.settings_manager.get_setting("EMAIL", "smtp_port"))
        self.sender_email_input.setText(self.settings_manager.get_setting("EMAIL", "sender_email"))
        self.recipient_emails_input.setText(self.settings_manager.get_setting("EMAIL", "recipient_email"))
        self.smtp_username_input.setText(self.settings_manager.get_setting("EMAIL", "username"))
        self.smtp_password_input.setText(self.settings_manager.get_setting("EMAIL", "password"))
        self.enable_ssl_checkbox.setChecked(self.settings_manager.get_setting("EMAIL", "enable_ssl", bool))
        self.enable_global_email_alerts_checkbox.setChecked(self.settings_manager.get_setting("EMAIL", "enable_email_alerts", bool))

        # Webhooks
        self.enable_webhooks_checkbox.setChecked(self.settings_manager.get_setting("WEBHOOK", "enable_webhooks", bool))
        self.platform_webhook_urls = {}
        for p in ["Discord", "Slack", "Teams", "Telegram", "Generic JSON"]:
            self.platform_webhook_urls[p] = self.settings_manager.get_webhook_url_for_platform(p)

        w_type = self.settings_manager.get_setting("WEBHOOK", "webhook_type") or "Discord"
        self._current_webhook_platform = w_type
        self.webhook_type_combo.blockSignals(True)
        idx = self.webhook_type_combo.findText(w_type)
        if idx >= 0:
            self.webhook_type_combo.setCurrentIndex(idx)
        self.webhook_type_combo.blockSignals(False)
        self.webhook_url_input.setText(self.platform_webhook_urls.get(w_type, ""))

        # Alerts
        self.enable_global_popups_checkbox.setChecked(self.settings_manager.get_setting("ALERTS", "enable_popups", bool))
        self.enable_global_sound_alerts_checkbox.setChecked(self.settings_manager.get_setting("ALERTS", "enable_sound_alerts", bool))
        self.alert_sound_path_input.setText(self.settings_manager.get_setting("ALERTS", "alert_sound_path"))

        # Monitoring
        self.ping_interval_input.setText(str(self.settings_manager.get_setting("MONITORING", "ping_interval") or 10))
        self.unreachable_threshold_input.setText(str(self.settings_manager.get_setting("MONITORING", "unreachable_threshold") or 3))

        # Logging & System
        self.log_directory_input.setText(self.settings_manager.get_setting("LOGGING", "log_directory"))
        self.enable_file_logging_checkbox.setChecked(self.settings_manager.get_setting("LOGGING", "enable_file_logging", bool))
        self.enable_hourly_logging_checkbox.setChecked(self.settings_manager.get_setting("LOGGING", "enable_hourly_log", bool))

        self.startup_checkbox.setChecked(StartupManager.is_startup_enabled())
        min_to_tray = self.settings_manager.get_setting("UI", "minimize_to_tray", bool)
        self.minimize_tray_checkbox.setChecked(min_to_tray)
        self.system_tray_manager.set_minimize_to_tray_checked(min_to_tray)

        # Restore column visibility
        vis_cols_str = self.settings_manager.get_setting("UI", "visible_columns")
        if vis_cols_str:
            vis_cols = set(vis_cols_str.split(","))
            if "11" not in vis_cols and len(vis_cols) >= 10:
                vis_cols.add("11")
            for c in range(self.ip_status_table.columnCount()):
                self.ip_status_table.setColumnHidden(c, str(c) not in vis_cols)

    def save_settings_from_ui(self):
        # Email settings
        self.settings_manager.set_setting("EMAIL", "smtp_server", self.smtp_server_input.text().strip())
        self.settings_manager.set_setting("EMAIL", "smtp_port", self.smtp_port_input.text().strip())
        self.settings_manager.set_setting("EMAIL", "sender_email", self.sender_email_input.text().strip())
        self.settings_manager.set_setting("EMAIL", "recipient_email", self.recipient_emails_input.text().strip())
        self.settings_manager.set_setting("EMAIL", "username", self.smtp_username_input.text().strip())
        self.settings_manager.set_setting("EMAIL", "password", self.smtp_password_input.text().strip())
        self.settings_manager.set_setting("EMAIL", "enable_ssl", self.enable_ssl_checkbox.isChecked())
        self.settings_manager.set_setting("EMAIL", "enable_email_alerts", self.enable_global_email_alerts_checkbox.isChecked())

        # Webhook: Save all individual platform URLs
        active_type = self.webhook_type_combo.currentText()
        entered_webhook_url = self.webhook_url_input.text().strip()
        if not hasattr(self, 'platform_webhook_urls'):
            self.platform_webhook_urls = {}
        self.platform_webhook_urls[active_type] = entered_webhook_url

        for p, u in self.platform_webhook_urls.items():
            self.settings_manager.set_webhook_url_for_platform(p, u)

        self.settings_manager.set_setting("WEBHOOK", "webhook_type", active_type)
        self.settings_manager.set_setting("WEBHOOK", "webhook_url", entered_webhook_url)

        # Auto-check Enable Webhooks if a valid URL was provided
        if entered_webhook_url and not self.enable_webhooks_checkbox.isChecked():
            self.enable_webhooks_checkbox.setChecked(True)
        self.settings_manager.set_setting("WEBHOOK", "enable_webhooks", self.enable_webhooks_checkbox.isChecked())

        # Local Alerts
        self.settings_manager.set_setting("ALERTS", "enable_popups", self.enable_global_popups_checkbox.isChecked())
        self.settings_manager.set_setting("ALERTS", "enable_sound_alerts", self.enable_global_sound_alerts_checkbox.isChecked())
        self.settings_manager.set_setting("ALERTS", "alert_sound_path", self.alert_sound_path_input.text().strip())

        # Polling (validate inputs and auto-focus invalid tab on error)
        try:
            raw_interval = self.ping_interval_input.text().strip()
            interval = int(raw_interval) if raw_interval else 10
            if interval <= 0: raise ValueError
            self.settings_manager.set_setting("MONITORING", "ping_interval", interval)
            self.ping_engine.set_ping_interval(interval)
        except ValueError:
            self.settings_tabs.setCurrentIndex(3)  # Polling tab
            self.ping_interval_input.setFocus()
            QMessageBox.warning(self, "Invalid Input", "Ping Interval must be a positive integer.")
            return

        try:
            raw_thresh = self.unreachable_threshold_input.text().strip()
            threshold = int(raw_thresh) if raw_thresh else 3
            if threshold <= 0: raise ValueError
            self.settings_manager.set_setting("MONITORING", "unreachable_threshold", threshold)
        except ValueError:
            self.settings_tabs.setCurrentIndex(3)  # Polling tab
            self.unreachable_threshold_input.setFocus()
            QMessageBox.warning(self, "Invalid Input", "Threshold must be a positive integer.")
            return

        # System & Startup
        StartupManager.set_startup_enabled(self.startup_checkbox.isChecked())
        self.settings_manager.set_setting("UI", "minimize_to_tray", self.minimize_tray_checkbox.isChecked())

        new_log_dir = self.log_directory_input.text().strip()
        self.settings_manager.set_setting("LOGGING", "log_directory", new_log_dir)
        self.log_manager.set_log_directory(new_log_dir)
        self.log_manager.set_file_logging_enabled(self.enable_file_logging_checkbox.isChecked())
        self.log_manager.set_hourly_logging_enabled(self.enable_hourly_logging_checkbox.isChecked())

        # 1. Direct synchronous write to guarantee instant persistence on disk
        self.settings_manager.save_settings()
        self.save_load_worker.save_settings_async()
        self.log_manager.log_incident("Application settings and Webhook configuration saved successfully.")

        # 2. Dynamic visual feedback on the Save button
        if hasattr(self, 'btn_save_settings'):
            self.btn_save_settings.setText("✅ Settings Saved!")
            self.btn_save_settings.setStyleSheet("""
                QPushButton#btnSaveSettings {
                    background-color: #065f46 !important;
                    border: 1px solid #10b981 !important;
                    color: #ecfdf5 !important;
                    font-weight: 700;
                }
            """)
            QTimer.singleShot(2500, self._reset_save_button_style)

        # 3. Desktop Toast Confirmation
        if hasattr(self, 'system_tray_manager'):
            self.system_tray_manager.show_toast("Settings Saved", "All application settings & webhooks were saved successfully.", False)

    def _reset_save_button_style(self):
        if hasattr(self, 'btn_save_settings'):
            self.btn_save_settings.setText("💾 Save All Settings")
            self.btn_save_settings.setStyleSheet("")

    def test_webhook_settings_ui(self):
        url = self.webhook_url_input.text().strip()
        w_type = self.webhook_type_combo.currentText()
        if not url:
            QMessageBox.warning(self, "Missing URL", f"Please enter a Webhook URL for {w_type} first.")
            return
        self.webhook_notifier.send_notification_async(url, w_type, "TestHost (127.0.0.1)", "Test Webhook", False, "0s")
        QMessageBox.information(self, "Webhook Sent", f"Test webhook dispatched to {w_type}.")

    def test_email_settings_ui(self):
        sender = self.sender_email_input.text().strip()
        smtp_srv = self.smtp_server_input.text().strip()
        port = self.smtp_port_input.text().strip()
        recipients = self.recipient_emails_input.text().strip()

        if not all([sender, smtp_srv, port, recipients]):
            QMessageBox.warning(self, "Missing Fields", "Sender, SMTP Server, Port, and Recipients must be filled.")
            return

        subject = "D IP Monitor - Test Email"
        body = "This is a test notification from your D IP Monitor application."
        self.ip_data_model.send_email_alert(subject, body, "TestEmail", is_test=True)

    def _send_email_alert_via_worker(self, email_settings: dict, subject: str, body: str, ip_address: str, is_test: bool):
        worker = EmailWorker(email_settings, subject, body, ip_address)
        if is_test:
            worker.email_sent.connect(lambda sub, ip: QMessageBox.information(self, "Email Sent", "Test email was sent successfully! Check your inbox."))
            worker.email_error.connect(lambda err, ip: QMessageBox.critical(self, "Email Failed", f"Failed to send test email:\n{err}"))
        worker.email_sent.connect(lambda sub, ip: self.log_manager.log_incident(f"Email sent successfully for: {ip}"))
        worker.email_error.connect(lambda err, ip: self.log_manager.log_incident(f"ERROR: Email failed for {ip}: {err}"))
        self.email_threads[ip_address] = worker
        worker.start()

    # --- UI INTERACTION HANDLERS ---
    def add_ip_monitor_ui(self):
        ip = self.ip_address_input.text().strip()
        desc = self.description_input.text().strip()
        tag = self.tag_input.text().strip() or "General"

        if not ip:
            QMessageBox.warning(self, "Input Error", "IP Address cannot be empty.")
            return

        if self.ip_data_model.add_ip(ip, desc, tag=tag):
            self.refresh_category_tabs()
            self.ip_address_input.clear()
            self.description_input.clear()

    def remove_ip_monitor_ui(self):
        selected_indexes = self.ip_status_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Selection Error", "Please select one or more hosts to remove.")
            return

        selected_ips = []
        for idx in selected_indexes:
            ip_item = self.ip_status_table.item(idx.row(), 0)
            if ip_item:
                selected_ips.append(ip_item.text().strip())

        if selected_ips:
            self._batch_remove_hosts(selected_ips)

    def toggle_ip_alert_setting_ui(self, row: int, monitor: IpMonitor, setting: str, state: int):
        is_checked = (state == Qt.CheckState.Checked.value)
        if setting == "email":
            monitor.enable_email_alerts_for_ip = is_checked
        elif setting == "popup":
            monitor.enable_popup_alerts_for_ip = is_checked
        elif setting == "sound":
            monitor.enable_sound_alerts_for_ip = is_checked
        elif setting == "webhook":
            monitor.enable_webhook_alerts_for_ip = is_checked
        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)

    def sort_table_column_ui(self, logical_index: int):
        new_order = Qt.SortOrder.AscendingOrder
        if logical_index == self._current_sort_column:
            new_order = Qt.SortOrder.DescendingOrder if self._current_sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder

        self._current_sort_column = logical_index
        self._current_sort_order = new_order
        self.ip_status_table.horizontalHeader().setSortIndicator(logical_index, new_order)
        self.ip_data_model.sort_monitored_ips(logical_index, new_order)
        self.update_ip_status_table(full_rebuild=True)

    def browse_sound_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Sound File", "", "Wave Audio Files (*.wav)")
        if path:
            self.alert_sound_path_input.setText(path)

    def browse_log_directory(self):
        current_dir = self.log_directory_input.text().strip()
        if not current_dir or not os.path.exists(os.path.normpath(current_dir)):
            current_dir = self.settings_manager.get_setting("LOGGING", "log_directory") or ""
        if not current_dir or not os.path.exists(os.path.normpath(current_dir)):
            current_dir = getattr(self.log_manager.log_worker, 'base_log_directory', "")
        if not current_dir or not os.path.exists(os.path.normpath(current_dir)):
            current_dir = r"D:\AntiGravity\D IP Monitor\logs"
        if not os.path.exists(os.path.normpath(current_dir)):
            current_dir = os.path.expanduser("~")

        current_dir = os.path.normpath(current_dir)
        path = QFileDialog.getExistingDirectory(self, "Select Log Directory", current_dir)
        if path:
            self.log_directory_input.setText(os.path.normpath(path))

    def show_popup_alert(self, title: str, message: str, icon_int: int):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon(icon_int))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        QTimer.singleShot(3500, msg_box.close)
        msg_box.open()

    def play_alert_sound(self, sound_path: str):
        if sound_path and os.path.exists(sound_path) and sound_path.lower().endswith('.wav'):
            try:
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except Exception:
                pass
        try:
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            try:
                winsound.Beep(880, 250)
            except Exception:
                try:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                except Exception:
                    pass

    def _on_tray_mute_toggled(self, is_muted: bool):
        self.enable_global_sound_alerts_checkbox.setChecked(not is_muted)
        self.save_settings_from_ui()

    def _on_tray_minimize_toggled(self, is_enabled: bool):
        """Synchronizes tray menu toggle with UI checkbox and persists to disk."""
        self.minimize_tray_checkbox.blockSignals(True)
        self.minimize_tray_checkbox.setChecked(is_enabled)
        self.minimize_tray_checkbox.blockSignals(False)
        self.settings_manager.set_setting("UI", "minimize_to_tray", str(is_enabled))
        self.settings_manager.save_settings()
        self.save_load_worker.save_settings_async()
        status_msg = "enabled (runs in background on close)" if is_enabled else "disabled (exits completely on close)"
        self.log_manager.log_incident(f"Background running on close {status_msg}.")

    def _on_minimize_tray_checkbox_toggled(self, is_enabled: bool):
        """Synchronizes UI checkbox toggle with tray context menu and persists to disk."""
        self.system_tray_manager.set_minimize_to_tray_checked(is_enabled)
        self.settings_manager.set_setting("UI", "minimize_to_tray", str(is_enabled))
        self.settings_manager.save_settings()
        self.save_load_worker.save_settings_async()

    def _handle_save_load_completion(self, op_type: str, success: bool, msg: str):
        if not success:
            self.log_manager.log_incident(f"ERROR: {op_type} failed: {msg}")

    def eventFilter(self, source, event):
        if source == self.ip_status_table.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            index = self.ip_status_table.indexAt(event.pos())
            if not index.isValid():
                self.ip_status_table.clearSelection()
        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        # Check if user wants to keep running in background (system tray)
        keep_running = self.settings_manager.get_setting("UI", "minimize_to_tray", bool)

        if keep_running:
            event.ignore()
            self.hide()
            self.system_tray_manager.show_toast(
                "D IP Monitor Running in Background",
                "Monitoring continues in the system tray. Right-click the tray icon to Exit.",
                False
            )
            return

        self.force_exit_app()
        event.accept()

    def force_exit_app(self):
        """Clean shutdown of all worker threads, timers, and persistence."""
        self.ui_update_timer.stop()
        self.autosave_timer.stop()
        self.hourly_log_timer.stop()

        self.save_load_worker.save_ips_async(self.ip_data_model.monitored_ips)
        time.sleep(0.3)

        self.ping_engine.stop()
        self.ping_engine_thread.quit()
        self.ping_engine_thread.wait(2000)

        self.save_load_worker.stop_worker()
        self.save_load_thread.quit()
        self.save_load_thread.wait(2000)

        self.log_manager.shutdown()
        if self.floating_hud:
            self.floating_hud.close()

        for dlg in list(self.active_diagnostic_dialogs):
            try:
                dlg.close()
            except Exception:
                pass
        self.active_diagnostic_dialogs.clear()

        QApplication.quit()


# Custom Exception Handler
def show_exception_and_exit(exc_type, exc_value, exc_traceback):
    import traceback
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        with open("critical_error_fallback.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] CRITICAL ERROR: {error_message}\n")
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


if __name__ == "__main__":
    sys.excepthook = show_exception_and_exit

    # Windows AppUserModelID for taskbar icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dipmonitor.network.app.2.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("D IP Monitor")

    # Global App Icon
    base_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    app_icon_path = os.path.join(base_dir, 'app_icon.png')
    if not os.path.exists(app_icon_path):
        app_icon_path = os.path.join(base_dir, 'app_icon.ico')
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))

    window = IPMonitorApp()
    window.show()
    sys.exit(app.exec())
