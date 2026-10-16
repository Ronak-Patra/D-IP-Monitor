import subprocess
import sys
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QProgressBar,
    QHeaderView, QLineEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCursor

def apply_diagnostic_theme(dialog: QDialog):
    """Applies high-contrast dark cyber theme to diagnostic dialogs so all buttons, inputs, and text are crisp and visible."""
    dialog.setStyleSheet("""
        QDialog {
            background-color: #070c16;
            color: #f1f5f9;
            font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
        }
        QLabel {
            color: #f1f5f9;
        }
        QPushButton {
            background-color: #101a2c;
            color: #f1f5f9;
            border: 1px solid #1e2e47;
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: 600;
            font-size: 12px;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #17253d;
            border-color: #00e5ff;
            color: #00e5ff;
        }
        QPushButton:pressed {
            background-color: #0a1120;
            border-color: #0284c7;
        }
        QPushButton:disabled {
            background-color: #090e18;
            color: #475569;
            border-color: #131c2e;
        }
        QLineEdit {
            background-color: #0b1220;
            color: #f1f5f9;
            border: 1px solid #1e2e47;
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 12px;
        }
        QLineEdit:focus {
            border-color: #00e5ff;
        }
        QTextEdit {
            background-color: #0f172a;
            color: #38bdf8;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 8px;
        }
        QTableWidget {
            background-color: #0b1220;
            color: #f1f5f9;
            border: 1px solid #1e2e47;
            border-radius: 6px;
            gridline-color: #16243b;
        }
        QHeaderView::section {
            background-color: #0d1627;
            color: #00e5ff;
            border: 1px solid #16243b;
            padding: 6px;
            font-weight: 700;
        }
        QProgressBar {
            background-color: #0b1220;
            border: 1px solid #1e2e47;
            border-radius: 4px;
            text-align: center;
            color: #ffffff;
            font-size: 10px;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: #0284c7;
            border-radius: 3px;
        }
        QScrollBar:vertical {
            background: #0b1220;
            width: 10px;
            margin: 0px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background: #1e2e47;
            min-height: 25px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #00e5ff;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
            width: 0px;
            background: none;
            border: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
    """)

# --- 1. TRACEROUTE ---
class TracerouteWorker(QThread):
    hop_received = pyqtSignal(int, str, str, str, str) # hop, rtt1, rtt2, rtt3, host
    raw_line_received = pyqtSignal(str)
    traceroute_finished = pyqtSignal()

    def __init__(self, target: str, max_hops: int = 30):
        super().__init__()
        self.target = target
        self.max_hops = max_hops
        self._is_running = True
        self.process = None

    def run(self):
        cmd = ["tracert", "-d", "-h", str(self.max_hops), "-w", "1000", self.target]
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )

            # Pattern for Windows tracert output lines, e.g.:
            #   1    <1 ms    <1 ms    <1 ms  192.168.1.1
            #   2     4 ms     5 ms     4 ms  10.0.0.1
            hop_pattern = re.compile(
                r"^\s*(\d+)\s+([\d<*]+\s*m?s?)\s+([\d<*]+\s*m?s?)\s+([\d<*]+\s*m?s?)\s+(.+)$"
            )

            for line in self.process.stdout:
                if not self._is_running:
                    break
                line_str = line.strip()
                self.raw_line_received.emit(line_str)

                match = hop_pattern.match(line_str)
                if match:
                    hop_num = int(match.group(1))
                    rtt1 = match.group(2).strip()
                    rtt2 = match.group(3).strip()
                    rtt3 = match.group(4).strip()
                    addr = match.group(5).strip()
                    self.hop_received.emit(hop_num, rtt1, rtt2, rtt3, addr)

            self.process.communicate()
        except Exception as e:
            self.raw_line_received.emit(f"Traceroute error: {e}")
        finally:
            self.traceroute_finished.emit()

    def stop(self):
        self._is_running = False
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass


class TracerouteDialog(QDialog):
    def __init__(self, target_ip: str, parent=None):
        super().__init__(parent)
        self.target_ip = target_ip
        self.setWindowTitle(f"Traceroute — {target_ip}")
        self.resize(750, 480)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        apply_diagnostic_theme(self)
        self.worker = None

        layout = QVBoxLayout(self)

        # Header info
        header = QLabel(f"<b>Traceroute to:</b> <span style='color:#0284c7;'>{target_ip}</span> (Max 30 hops)")
        header.setStyleSheet("font-size: 13px; margin-bottom: 4px;")
        layout.addWidget(header)

        # Table
        self.table = QTableWidget()
        headers = ["Hop", "RTT 1", "RTT 2", "RTT 3", "IP / Host"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        layout.addWidget(self.table)

        # Raw log toggle / status
        self.status_label = QLabel("Initializing traceroute...")
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.stop_trace)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.start_trace()

    def start_trace(self):
        self.worker = TracerouteWorker(self.target_ip)
        self.worker.hop_received.connect(self.on_hop_received)
        self.worker.raw_line_received.connect(lambda l: self.status_label.setText(l))
        self.worker.traceroute_finished.connect(self.on_finished)
        self.worker.start()

    def on_hop_received(self, hop: int, rtt1: str, rtt2: str, rtt3: str, addr: str):
        row = self.table.rowCount()
        self.table.insertRow(row)

        for col, val in enumerate([str(hop), rtt1, rtt2, rtt3, addr]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col < 4 else Qt.AlignmentFlag.AlignLeft)
            if "*" in val:
                item.setForeground(QColor("#ef4444")) # Red for timeouts
            elif col in (1, 2, 3) and "ms" in val:
                item.setForeground(QColor("#16a34a")) # Green for ok
            self.table.setItem(row, col, item)

        self.table.scrollToBottom()

    def on_finished(self):
        self.status_label.setText("Traceroute completed.")
        self.btn_stop.setEnabled(False)

    def stop_trace(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.status_label.setText("Traceroute stopped by user.")
            self.btn_stop.setEnabled(False)

    def closeEvent(self, event):
        self.stop_trace()
        super().closeEvent(event)


# --- 2. TCP PORT CHECKER ---
COMMON_PORTS = [
    (21, "FTP"),
    (22, "SSH"),
    (23, "Telnet"),
    (25, "SMTP"),
    (53, "DNS"),
    (80, "HTTP"),
    (110, "POP3"),
    (143, "IMAP"),
    (443, "HTTPS"),
    (445, "SMB"),
    (1433, "MSSQL"),
    (3306, "MySQL"),
    (3389, "RDP"),
    (5432, "PostgreSQL"),
    (8080, "HTTP-Proxy"),
    (8443, "HTTPS-Alt"),
]

class PortScanWorker(QThread):
    port_scanned = pyqtSignal(int, str, str, float) # port, service, status, response_ms
    scan_progress = pyqtSignal(int, int) # completed, total
    scan_finished = pyqtSignal()

    def __init__(self, target_ip: str, ports_to_scan: list):
        super().__init__()
        self.target_ip = target_ip
        self.ports_to_scan = ports_to_scan
        self._is_running = True

    def run(self):
        total = len(self.ports_to_scan)
        completed = 0

        def check_port(item):
            if not self._is_running:
                return
            port, service = item
            start = QTimer()
            import time
            t0 = time.time()
            status = "Closed"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.5)
                res = sock.connect_ex((self.target_ip, port))
                t1 = time.time()
                rtt = (t1 - t0) * 1000
                if res == 0:
                    status = "Open"
                sock.close()
            except Exception:
                rtt = 0.0
                status = "Error"

            return port, service, status, rtt

        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(check_port, p) for p in self.ports_to_scan]
            for future in futures:
                if not self._is_running:
                    break
                res = future.result()
                if res:
                    port, service, status, rtt = res
                    self.port_scanned.emit(port, service, status, rtt)
                completed += 1
                self.scan_progress.emit(completed, total)

        self.scan_finished.emit()

    def stop(self):
        self._is_running = False


class PortCheckerDialog(QDialog):
    def __init__(self, target_ip: str, parent=None):
        super().__init__(parent)
        self.target_ip = target_ip
        self.setWindowTitle(f"TCP Port Checker — {target_ip}")
        self.resize(650, 520)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        apply_diagnostic_theme(self)
        self.worker = None

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"<b>Scanning Ports on:</b> <span style='color:#0284c7;'>{target_ip}</span>")
        header.setStyleSheet("font-size: 13px; margin-bottom: 2px;")
        layout.addWidget(header)

        # Custom port row
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Add Custom Port:"))
        self.custom_port_input = QLineEdit()
        self.custom_port_input.setPlaceholderText("e.g. 8000, 9000-9005")
        btn_scan_custom = QPushButton("Scan Custom")
        btn_scan_custom.clicked.connect(self.scan_custom_ports)
        custom_layout.addWidget(self.custom_port_input)
        custom_layout.addWidget(btn_scan_custom)
        layout.addLayout(custom_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { height: 14px; text-align: center; }")
        layout.addWidget(self.progress_bar)

        # Table
        self.table = QTableWidget()
        headers = ["Port", "Service", "Status", "Latency"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self.status_label = QLabel("Scanning common service ports...")
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        btn_layout.addWidget(self.status_label)
        btn_layout.addStretch()
        self.btn_rescan = QPushButton("Rescan Common")
        self.btn_rescan.clicked.connect(lambda: self.start_scan(COMMON_PORTS))
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_rescan)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.start_scan(COMMON_PORTS)

    def start_scan(self, ports: list):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(500)

        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(ports))
        self.status_label.setText(f"Scanning {len(ports)} ports...")
        self.btn_rescan.setEnabled(False)

        self.worker = PortScanWorker(self.target_ip, ports)
        self.worker.port_scanned.connect(self.on_port_result)
        self.worker.scan_progress.connect(lambda done, tot: self.progress_bar.setValue(done))
        self.worker.scan_finished.connect(self.on_scan_finished)
        self.worker.start()

    def on_port_result(self, port: int, service: str, status: str, rtt: float):
        row = self.table.rowCount()
        self.table.insertRow(row)

        p_item = QTableWidgetItem(str(port))
        s_item = QTableWidgetItem(service)
        st_item = QTableWidgetItem(status)
        r_item = QTableWidgetItem(f"{rtt:.1f} ms" if status == "Open" else "—")

        if status == "Open":
            st_item.setForeground(QColor("#16a34a"))
            st_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        else:
            st_item.setForeground(QColor("#94a3b8"))

        self.table.setItem(row, 0, p_item)
        self.table.setItem(row, 1, s_item)
        self.table.setItem(row, 2, st_item)
        self.table.setItem(row, 3, r_item)

    def on_scan_finished(self):
        self.status_label.setText("Port scan finished.")
        self.btn_rescan.setEnabled(True)

    def scan_custom_ports(self):
        text = self.custom_port_input.text().strip()
        if not text:
            return
        ports = []
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    s, e = map(int, part.split("-"))
                    ports.extend([(p, f"Custom-{p}") for p in range(max(1, s), min(65535, e) + 1)])
                except ValueError:
                    pass
            elif part.isdigit():
                p = int(part)
                if 1 <= p <= 65535:
                    ports.append((p, f"Custom-{p}"))
        if ports:
            self.start_scan(ports)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        super().closeEvent(event)


# --- 3. DNS / REVERSE DNS LOOKUP ---
class DnsLookupDialog(QDialog):
    def __init__(self, target: str, parent=None):
        super().__init__(parent)
        self.target = target
        self.setWindowTitle(f"DNS & Reverse Lookup — {target}")
        self.resize(520, 380)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        apply_diagnostic_theme(self)

        layout = QVBoxLayout(self)

        header = QLabel(f"<b>DNS Intelligence for:</b> <span style='color:#0284c7;'>{target}</span>")
        header.setStyleSheet("font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(header)

        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setFont(QFont("Consolas", 10))
        self.result_display.setStyleSheet("background-color: #0f172a; color: #38bdf8; border: 1px solid #1e293b; border-radius: 6px; padding: 10px;")
        layout.addWidget(self.result_display)

        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.perform_lookup)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.perform_lookup()

    def perform_lookup(self):
        self.result_display.clear()
        self.result_display.append(f"Querying DNS records for: {self.target} ...\n" + "-" * 50)

        # Forward Lookup
        try:
            hostname, aliases, ip_addresses = socket.gethostbyname_ex(self.target)
            self.result_display.append(f"[FORWARD LOOKUP]")
            self.result_display.append(f"  Primary Hostname : {hostname}")
            self.result_display.append(f"  Aliases          : {', '.join(aliases) if aliases else 'None'}")
            self.result_display.append(f"  Resolved IPs     : {', '.join(ip_addresses)}\n")
        except Exception as e:
            self.result_display.append(f"[FORWARD LOOKUP] Failed: {e}\n")

        # Reverse Lookup
        try:
            rev_name, rev_aliases, rev_ips = socket.gethostbyaddr(self.target)
            self.result_display.append(f"[REVERSE PTR LOOKUP]")
            self.result_display.append(f"  Reverse Hostname : {rev_name}")
            self.result_display.append(f"  Aliases          : {', '.join(rev_aliases) if rev_aliases else 'None'}")
            self.result_display.append(f"  Addresses        : {', '.join(rev_ips)}\n")
        except Exception as e:
            self.result_display.append(f"[REVERSE PTR LOOKUP] Failed: {e}\n")

        self.result_display.append("-" * 50)
        self.result_display.append("Lookup completed.")


# --- 4. CONTINUOUS PING STREAM WINDOW ---
class ContinuousPingWorker(QThread):
    ping_output_line = pyqtSignal(str, bool, float) # line, is_success, rtt
    finished = pyqtSignal()

    def __init__(self, target_ip: str):
        super().__init__()
        self.target_ip = target_ip
        self._is_running = True
        self.process = None

    def run(self):
        cmd = ["ping", "-t", self.target_ip]
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )

            rtt_pattern = re.compile(r"time[<=](\d+\.?\d*)ms", re.IGNORECASE)

            for line in self.process.stdout:
                if not self._is_running:
                    break
                line_str = line.strip()
                if not line_str:
                    continue
                match = rtt_pattern.search(line_str)
                is_success = bool(match) or ("Reply from" in line_str)
                rtt = float(match.group(1)) if match else 0.0
                self.ping_output_line.emit(line_str, is_success, rtt)

            self.process.communicate()
        except Exception as e:
            self.ping_output_line.emit(f"Continuous ping error: {e}", False, 0.0)
        finally:
            self.finished.emit()

    def stop(self):
        self._is_running = False
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass


class ContinuousPingDialog(QDialog):
    def __init__(self, target_ip: str, parent=None):
        super().__init__(parent)
        self.target_ip = target_ip
        self.setWindowTitle(f"Live Continuous Ping — {target_ip}")
        self.resize(680, 480)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        apply_diagnostic_theme(self)
        self.worker = None

        self.sent_count = 0
        self.received_count = 0
        self.rtt_list = []

        layout = QVBoxLayout(self)

        # Header summary bar with Pin on Top & Auto-Scroll toggles
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        self.stats_label = QLabel("Sent: 0 | Received: 0 | Lost: 0 (0%) | Avg: 0ms")
        self.stats_label.setStyleSheet("font-weight: bold; color: #0284c7; font-size: 12px;")
        header_layout.addWidget(self.stats_label)
        header_layout.addStretch()

        self.btn_autoscroll = QPushButton("⬇ Auto-Scroll")
        self.btn_autoscroll.setCheckable(True)
        self.btn_autoscroll.setChecked(True)
        self.btn_autoscroll.setFixedWidth(105)
        self.btn_autoscroll.setStyleSheet("""
            QPushButton {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 3px 6px;
                color: #94a3b8;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: #00e5ff;
                color: #00e5ff;
            }
            QPushButton:checked {
                background-color: #064e3b;
                border-color: #10b981;
                color: #34d399;
                font-weight: bold;
            }
        """)
        self.btn_autoscroll.toggled.connect(self.toggle_autoscroll)
        header_layout.addWidget(self.btn_autoscroll)

        self.btn_pin = QPushButton("📌 Pin on Top")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setFixedWidth(105)
        self.btn_pin.setStyleSheet("""
            QPushButton {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 3px 6px;
                color: #94a3b8;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: #00e5ff;
                color: #00e5ff;
            }
            QPushButton:checked {
                background-color: #0284c7;
                border-color: #00e5ff;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        self.btn_pin.toggled.connect(self.toggle_pin_on_top)
        header_layout.addWidget(self.btn_pin)
        layout.addLayout(header_layout)

        # Terminal text display
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Consolas", 10))
        self.terminal.setStyleSheet(
            "background-color: #0f172a; color: #38bdf8; border: 1px solid #1e293b; border-radius: 6px; padding: 10px;"
        )
        self.terminal.document().setMaximumBlockCount(3000)
        layout.addWidget(self.terminal)

        # Floating "▼ Latest" action button inside terminal
        self.btn_scroll_latest = QPushButton("▼ Latest", self.terminal)
        self.btn_scroll_latest.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scroll_latest.setFixedHeight(28)
        self.btn_scroll_latest.setToolTip("Scroll directly to latest ping")
        self.btn_scroll_latest.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #00e5ff;
                border-radius: 14px;
                padding: 4px 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                border-color: #ffffff;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #0284c7;
            }
        """)
        self.btn_scroll_latest.clicked.connect(self.scroll_to_latest)
        self.btn_scroll_latest.hide()
        self.terminal.verticalScrollBar().valueChanged.connect(self._on_terminal_scroll)

        # Bottom action buttons with dedicated high-contrast styles
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_pause = QPushButton("Stop")
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.clicked.connect(self.toggle_stream)
        self._set_pause_button_style(is_running=True)

        btn_clear = QPushButton("Clear")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_stream)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #101a2c;
                color: #e2e8f0;
                border: 1px solid #1e2e47;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 12px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #17253d;
                border-color: #00e5ff;
                color: #00e5ff;
            }
        """)

        btn_min = QPushButton("Minimize")
        btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_min.setToolTip("Minimize to Windows taskbar while pinging in background")
        btn_min.clicked.connect(self.showMinimized)
        btn_min.setStyleSheet("""
            QPushButton {
                background-color: #101a2c;
                color: #e2e8f0;
                border: 1px solid #1e2e47;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 12px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #17253d;
                border-color: #00e5ff;
                color: #00e5ff;
            }
        """)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #101a2c;
                color: #e2e8f0;
                border: 1px solid #1e2e47;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 12px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                border-color: #ef4444;
                color: #ffffff;
            }
        """)

        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_min)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.start_stream()

    def start_stream(self):
        self.worker = ContinuousPingWorker(self.target_ip)
        self.worker.ping_output_line.connect(self.on_ping_line)
        self.worker.finished.connect(lambda: self._set_pause_button_style(is_running=False))
        self.worker.start()
        self._set_pause_button_style(is_running=True)

    def toggle_stream(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._set_pause_button_style(is_running=False)
        else:
            self.start_stream()

    def _set_pause_button_style(self, is_running: bool):
        if is_running:
            self.btn_pause.setText("Stop")
            self.btn_pause.setStyleSheet("""
                QPushButton {
                    background-color: #1e141a;
                    color: #f87171;
                    border: 1px solid #7f1d1d;
                    border-radius: 6px;
                    padding: 6px 18px;
                    font-weight: 700;
                    font-size: 12px;
                    min-height: 22px;
                }
                QPushButton:hover {
                    background-color: #991b1b;
                    border-color: #ef4444;
                    color: #ffffff;
                }
            """)
        else:
            self.btn_pause.setText("Resume")
            self.btn_pause.setStyleSheet("""
                QPushButton {
                    background-color: #062b1b;
                    color: #4ade80;
                    border: 1px solid #047857;
                    border-radius: 6px;
                    padding: 6px 18px;
                    font-weight: 700;
                    font-size: 12px;
                    min-height: 22px;
                }
                QPushButton:hover {
                    background-color: #059669;
                    border-color: #10b981;
                    color: #ffffff;
                }
            """)

    def clear_stream(self):
        self.terminal.clear()
        self.sent_count = 0
        self.received_count = 0
        self.rtt_list.clear()
        self.update_stats()

    def on_ping_line(self, line: str, is_success: bool, rtt: float):
        self.sent_count += 1
        if is_success:
            self.received_count += 1
            if rtt > 0:
                self.rtt_list.append(rtt)
            # Green output for success
            color = "#4ade80"
        else:
            # Red output for timeout/failure
            color = "#f87171"

        vbar = self.terminal.verticalScrollBar()
        was_at_bottom = vbar.value() >= (vbar.maximum() - 25)
        prev_pos = vbar.value()

        # Insert at the end using text cursor cleanly on its own block
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self.terminal.document().characterCount() > 1:
            cursor.insertBlock()
        cursor.insertHtml(f"<span style='color:{color}; font-family:Consolas, monospace;'>{line}</span>")

        if self.btn_autoscroll.isChecked() and was_at_bottom:
            vbar.setValue(vbar.maximum())
            self.btn_scroll_latest.hide()
        else:
            # Keep user's exact scroll position untouched when scrolled into the middle!
            vbar.setValue(prev_pos)
            self._reposition_scroll_latest_btn()
            self.btn_scroll_latest.show()

        self.update_stats()

    def scroll_to_latest(self):
        self.btn_autoscroll.setChecked(True)
        vbar = self.terminal.verticalScrollBar()
        vbar.setValue(vbar.maximum())
        self.btn_scroll_latest.hide()

    def _on_terminal_scroll(self, val):
        vbar = self.terminal.verticalScrollBar()
        if val >= (vbar.maximum() - 25):
            self.btn_scroll_latest.hide()
        else:
            self._reposition_scroll_latest_btn()
            self.btn_scroll_latest.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_scroll_latest_btn()

    def _reposition_scroll_latest_btn(self):
        if not hasattr(self, 'terminal') or not hasattr(self, 'btn_scroll_latest'):
            return
        t_w = self.terminal.width()
        t_h = self.terminal.height()
        btn_w = self.btn_scroll_latest.width() or 80
        btn_h = self.btn_scroll_latest.height() or 28
        # Float in the bottom-right corner of the terminal, leaving space for scrollbar
        self.btn_scroll_latest.move(max(10, t_w - btn_w - 20), max(10, t_h - btn_h - 15))

    def toggle_autoscroll(self, checked: bool):
        if checked:
            self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())
            self.btn_scroll_latest.hide()

    def update_stats(self):
        lost = self.sent_count - self.received_count
        loss_pct = (lost / self.sent_count * 100) if self.sent_count > 0 else 0
        avg_rtt = (sum(self.rtt_list) / len(self.rtt_list)) if self.rtt_list else 0
        self.stats_label.setText(
            f"Sent: {self.sent_count} | Received: {self.received_count} | Lost: {lost} ({loss_pct:.1f}%) | Avg RTT: {avg_rtt:.1f}ms"
        )

    def toggle_pin_on_top(self, checked: bool):
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
            self.btn_pin.setText("📌 Pinned")
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
            self.btn_pin.setText("📌 Pin on Top")
        self.setWindowFlags(flags)
        self.show()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        super().closeEvent(event)
