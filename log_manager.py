import os
from datetime import datetime
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition, QObject
import collections # For deque

# --- New Worker Thread for Asynchronous File Logging ---
class LogWorker(QThread):
    """
    A dedicated QThread to perform file write operations for logging.
    This prevents the main UI from freezing due to frequent disk I/O,
    especially with high-volume logging for many IPs.
    """
    # Signal emitted to indicate a message should be appended to the UI log
    append_to_ui_signal = pyqtSignal(str)

    def __init__(self, base_log_directory: str, enable_file_logging: bool):
        super().__init__()
        self.base_log_directory = base_log_directory
        self._file_logging_enabled = enable_file_logging
        self._queue = collections.deque() # Use deque for efficient appends/pops
        self._mutex = QMutex() # Protects access to the queue and _is_running
        self._wait_condition = QWaitCondition() # For signaling new items in queue
        self._is_running = True

        # Ensure base log directory exists on worker initialization
        self._ensure_log_directory_exists()

    def _ensure_log_directory_exists(self):
        """Ensures the base log directory exists, with fallback."""
        try:
            if not os.path.exists(self.base_log_directory):
                os.makedirs(self.base_log_directory)
                self.append_to_ui_signal.emit(f"Log directory created: {self.base_log_directory}")
        except Exception as e:
            fallback_path = os.path.join(os.path.expanduser("~"), "Documents", "IPMonitorLogsFallback")
            try:
                os.makedirs(fallback_path, exist_ok=True)
                self.base_log_directory = fallback_path
                self.append_to_ui_signal.emit(f"ERROR: Could not create log directory. Using fallback: {self.base_log_directory} (Reason: {e})")
            except Exception as inner_e:
                self.append_to_ui_signal.emit(f"CRITICAL ERROR: Could not create fallback log directory: {inner_e}")
                self._file_logging_enabled = False # Disable file logging if even fallback fails

    def run(self):
        """Worker's main loop: process log messages from the queue."""
        while self._is_running:
            self._mutex.lock()
            if not self._queue:
                # Wait for new items or until stop is requested
                self._wait_condition.wait(self._mutex)
            
            # Process all items currently in the queue before unlocking
            while self._queue:
                item = self._queue.popleft()
                self._mutex.unlock() # Release lock while performing I/O

                log_type = item.get("type")
                log_entry = item.get("content")
                
                if log_type == "incident" and self._file_logging_enabled:
                    self._write_to_incident_file(log_entry)
                elif log_type == "hourly" and self._file_logging_enabled:
                    self._write_to_hourly_file(log_entry)
                
                self._mutex.lock() # Re-acquire lock to check queue/wait again
            self._mutex.unlock()

    def enqueue_log(self, log_type: str, content: str):
        """Adds a log message to the queue for asynchronous processing."""
        self._mutex.lock()
        self._queue.append({"type": log_type, "content": content})
        self._wait_condition.wakeOne() # Signal the worker thread that there's new data
        self._mutex.unlock()

    def set_file_logging_enabled(self, enabled: bool):
        """Sets whether file logging is enabled or disabled for the worker."""
        self._mutex.lock()
        self._file_logging_enabled = enabled
        if enabled:
            self._ensure_log_directory_exists() # Ensure directory exists when enabling
        self._mutex.unlock()
        self.append_to_ui_signal.emit(f"File logging {'enabled' if enabled else 'disabled'}.")

    def _get_incident_log_file_path(self):
        """Returns the full path for the incident log file."""
        return os.path.join(self.base_log_directory, "incident_log.txt")

    def _rotate_file_if_needed(self, file_path: str, max_bytes: int = 5 * 1024 * 1024, backup_count: int = 3):
        """Rotates log file if it exceeds max_bytes to prevent filling disk space."""
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) >= max_bytes:
                for i in range(backup_count - 1, 0, -1):
                    sfn = f"{file_path}.{i}"
                    dfn = f"{file_path}.{i + 1}"
                    if os.path.exists(sfn):
                        if os.path.exists(dfn):
                            os.remove(dfn)
                        os.rename(sfn, dfn)
                dfn = f"{file_path}.1"
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(file_path, dfn)
        except Exception:
            pass

    def _clean_old_hourly_logs(self, max_days: int = 7):
        """Cleans hourly log files older than max_days to prevent storage accumulation."""
        try:
            now = datetime.now()
            for filename in os.listdir(self.base_log_directory):
                if filename.startswith("IPStatus_") and filename.endswith(".log"):
                    filepath = os.path.join(self.base_log_directory, filename)
                    file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if (now - file_modified).days > max_days:
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
        except Exception:
            pass

    def _write_to_incident_file(self, log_entry: str):
        """Writes a log entry to the incident log file with rotation."""
        try:
            log_file_path = self._get_incident_log_file_path()
            self._rotate_file_if_needed(log_file_path)
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            self.append_to_ui_signal.emit(f"ERROR: Could not write incident to file: {e}")

    def _write_to_hourly_file(self, log_content: str):
        """Writes hourly IP status log content to a file and purges old logs."""
        try:
            self._clean_old_hourly_logs(max_days=7)
            log_file_name = f"IPStatus_{datetime.now():%Y%m%d_%H}.log"
            log_file_path = os.path.join(self.base_log_directory, log_file_name)
            self._rotate_file_if_needed(log_file_path)
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(log_content)
        except Exception as e:
            self.append_to_ui_signal.emit(f"ERROR: Could not write hourly IP status log to file: {e}")

    def stop(self):
        """Stops the worker thread gracefully."""
        self._mutex.lock()
        self._is_running = False
        self._wait_condition.wakeOne() # Wake up the thread to check _is_running
        self._mutex.unlock()
        self.wait() # Wait for the run method to finish

class LogManager(QObject):
    """
    Handles logging of application incidents and hourly IP statuses.
    Manages a separate worker thread for file writing to keep the UI responsive.
    """
    log_received = pyqtSignal(str)

    def __init__(self, base_log_directory: str, text_edit_widget: QTextEdit = None,
                 enable_hourly_log: bool = True, enable_file_logging: bool = True):
        super().__init__()
        self.text_edit_widget = text_edit_widget
        self._hourly_logging_enabled = enable_hourly_log

        # Initialize and start the LogWorker thread for file operations
        self.log_worker = LogWorker(base_log_directory, enable_file_logging)
        # Connect worker's signal to UI log update slot
        self.log_worker.append_to_ui_signal.connect(self._append_to_ui_log)
        self.log_worker.start() # Start the logging thread

    def set_log_directory(self, new_directory: str):
        """Updates the base log directory for the LogManager (and worker)."""
        self.log_worker.base_log_directory = new_directory
        self.log_worker._ensure_log_directory_exists() # Re-check directory existence
        self._append_to_ui_log(f"Log directory updated to: {new_directory}")

    def set_file_logging_enabled(self, enabled: bool):
        """Sets whether file logging is enabled or disabled via the worker."""
        self.log_worker.set_file_logging_enabled(enabled)

    def set_hourly_logging_enabled(self, enabled: bool):
        """Sets whether hourly logging is enabled or disabled."""
        self._hourly_logging_enabled = enabled
        self._append_to_ui_log(f"Hourly logging {'enabled' if enabled else 'disabled'}.")

    def log_incident(self, message: str):
        """
        Logs an incident message to the UI log and queues it for file logging.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self._append_to_ui_log(log_entry) # Always append to UI immediately
        self.log_worker.enqueue_log("incident", log_entry) # Queue for file

    def _append_to_ui_log(self, message: str):
        """Appends a message to the QTextEdit widget or emits signal."""
        self.log_received.emit(message)
        if self.text_edit_widget and self.receivers(self.log_received) <= 1:
            self.text_edit_widget.append(message)
            self.text_edit_widget.verticalScrollBar().setValue(self.text_edit_widget.verticalScrollBar().maximum())

    def log_hourly_ip_status(self, ip_monitors: list):
        """
        Logs the current status of all monitored IPs to a separate, hourly log file.
        This method is called periodically by a QTimer, and queues the write operation.
        """
        if not self.log_worker._file_logging_enabled or not self._hourly_logging_enabled:
            return

        log_content = []
        log_content.append(f"--- IP Status Log - {datetime.now():%Y-%m-%d %H:%M:%S} ---")
        log_content.append("------------------------------------")
        for monitor in ip_monitors:
            log_content.append(
                f"IP: {monitor.ip_address:<15} Description: {monitor.description:<20} "
                f"Status: {monitor.status:<12} Downtime: {monitor.downtime:<10} "
                f"Uptime: {monitor.uptime:<10} Response Time: {monitor.response_time:<8.2f}ms"
            )
        log_content.append("------------------------------------")
        log_content.append("\n") # Add an empty line for visual separation between hourly entries

        self.log_worker.enqueue_log("hourly", "\n".join(log_content))
        self._append_to_ui_log("Hourly IP status log queued for saving.")

    def shutdown(self):
        """Call this method when the application is closing to stop the log worker."""
        if self.log_worker.isRunning():
            self.log_worker.stop()
