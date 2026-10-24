import re
import socket
import subprocess
import sys
import time
import csv
import ctypes
import struct
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QProgressBar,
    QHeaderView, QCheckBox, QFileDialog, QMessageBox, QGroupBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

class RangeScanWorker(QThread):
    # ip, is_occupied, hostname, mac_address, latency_ms
    host_scanned = pyqtSignal(str, bool, str, str, float)
    progress_updated = pyqtSignal(int, int) # completed, total
    scan_finished = pyqtSignal()

    def __init__(self, ip_list: list):
        super().__init__()
        self.ip_list = ip_list
        self._is_running = True

    def run(self):
        total = len(self.ip_list)
        completed = 0

        def probe_ip(ip):
            if not self._is_running:
                return None
            
            is_occupied = False
            hostname = ""
            mac_address = "—"
            latency_ms = 0.0

            # 1. Native Windows Layer-2 SendARP Probe
            # Instantly discovers silent smartphones (iOS/Android), tablets, and IoT devices
            # that sleep or deliberately reject ICMP echo pings.
            if sys.platform == "win32":
                try:
                    iphlpapi = ctypes.windll.iphlpapi
                    dest_ip = struct.unpack('<I', socket.inet_aton(ip))[0]
                    mac_buf = (ctypes.c_ubyte * 6)()
                    mac_len = ctypes.c_ulong(6)
                    t0 = time.time()
                    res = iphlpapi.SendARP(dest_ip, 0, ctypes.byref(mac_buf), ctypes.byref(mac_len))
                    t1 = time.time()
                    if res == 0:
                        mac_bytes = bytearray(mac_buf)
                        if any(b != 0 for b in mac_bytes):
                            is_occupied = True
                            mac_address = ":".join(f"{b:02X}" for b in mac_bytes)
                            latency_ms = max(0.5, (t1 - t0) * 1000)
                except Exception:
                    pass

            # 2. ICMP Echo Ping Probe
            cmd = ["ping", "-n", "1", "-w", "750", ip]
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            try:
                t0 = time.time()
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=1.2,
                    creationflags=creationflags
                )
                t1 = time.time()
                stdout = proc.stdout

                if f"Reply from {ip}" in stdout or "bytes=" in stdout:
                    is_occupied = True
                    match = re.search(r"time[<=](\d+\.?\d*)ms", stdout, re.IGNORECASE)
                    if match:
                        latency_ms = float(match.group(1))
                    elif latency_ms <= 0.0:
                        latency_ms = max(1.0, (t1 - t0) * 1000)
            except Exception:
                pass

            # 3. Fallback TCP probe on common smartphone / local service ports
            if not is_occupied:
                for port in [80, 443, 5353, 8080]:
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(0.3)
                        r = s.connect_ex((ip, port))
                        s.close()
                        if r == 0:
                            is_occupied = True
                            latency_ms = 4.0
                            break
                    except Exception:
                        pass

            # 4. Hostname & Device Identification
            if is_occupied:
                try:
                    resolved_name, _, _ = socket.gethostbyaddr(ip)
                    hostname = resolved_name
                except Exception:
                    if mac_address != "—":
                        hostname = f"Mobile / Wi-Fi Host ({mac_address})"
                    else:
                        hostname = "Active Network Host"

            return ip, is_occupied, hostname, mac_address, latency_ms

        with ThreadPoolExecutor(max_workers=min(64, len(self.ip_list))) as pool:
            futures = [pool.submit(probe_ip, ip) for ip in self.ip_list]
            for future in futures:
                if not self._is_running:
                    break
                try:
                    res = future.result()
                    if res:
                        ip, is_occ, host, mac, rtt = res
                        self.host_scanned.emit(ip, is_occ, host, mac, rtt)
                except Exception:
                    pass
                completed += 1
                self.progress_updated.emit(completed, total)

        self.scan_finished.emit()

    def stop(self):
        self._is_running = False


class IpRangeScannerDialog(QDialog):
    # Emits list of tuples: [(ip, description), ...] to add to main window
    add_hosts_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IP Range & Allocation Scanner — Occupied vs. Free IPs")
        self.resize(920, 640)
        self.worker = None
        self.results = [] # list of dicts

        layout = QVBoxLayout(self)

        # Range Input Form
        range_group = QGroupBox("Subnet Scan Configuration")
        range_layout = QHBoxLayout(range_group)
        range_layout.setContentsMargins(12, 10, 12, 10)
        range_layout.setSpacing(8)

        lbl_start = QLabel("Start IP:")
        lbl_start.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        range_layout.addWidget(lbl_start)

        self.start_ip_input = QLineEdit("192.168.1.1")
        self.start_ip_input.setFixedWidth(125)
        range_layout.addWidget(self.start_ip_input)

        range_layout.addSpacing(10)

        lbl_end = QLabel("End IP:")
        lbl_end.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        range_layout.addWidget(lbl_end)

        self.end_ip_input = QLineEdit("192.168.1.254")
        self.end_ip_input.setFixedWidth(125)
        range_layout.addWidget(self.end_ip_input)

        range_layout.addSpacing(10)

        btn_detect_subnet = QPushButton("Auto-Detect Subnet")
        btn_detect_subnet.clicked.connect(self.auto_detect_subnet)
        range_layout.addWidget(btn_detect_subnet)

        self.btn_start = QPushButton("Start Scan")
        self.btn_start.setObjectName("btnStartScan")
        self.btn_start.clicked.connect(self.start_scan)
        range_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btnStopScan")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_scan)
        range_layout.addWidget(self.btn_stop)

        range_layout.addStretch()

        layout.addWidget(range_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("scanProgressBar")
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Summary KPIs & Filter Bar
        filter_layout = QHBoxLayout()
        self.kpi_label = QLabel("Ready to scan.")
        self.kpi_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #38bdf8;")
        filter_layout.addWidget(self.kpi_label)

        filter_layout.addStretch()
        filter_layout.addWidget(QLabel("Filter:"))

        self.btn_filter_all = QPushButton("All")
        self.btn_filter_all.setCheckable(True)
        self.btn_filter_all.setChecked(True)
        self.btn_filter_all.clicked.connect(lambda: self.apply_filter("all"))

        self.btn_filter_occ = QPushButton("Occupied Only")
        self.btn_filter_occ.setCheckable(True)
        self.btn_filter_occ.clicked.connect(lambda: self.apply_filter("occupied"))

        self.btn_filter_free = QPushButton("Free Only")
        self.btn_filter_free.setCheckable(True)
        self.btn_filter_free.clicked.connect(lambda: self.apply_filter("free"))

        filter_layout.addWidget(self.btn_filter_all)
        filter_layout.addWidget(self.btn_filter_occ)
        filter_layout.addWidget(self.btn_filter_free)
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        headers = ["Select", "IP Address", "Status", "Hostname / Device", "MAC Address", "Response Time"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 75)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 260)
        self.table.setColumnWidth(4, 150)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Bottom Actions
        bottom_layout = QHBoxLayout()
        btn_select_occupied = QPushButton("Select All Occupied")
        btn_select_occupied.clicked.connect(self.select_all_occupied)
        bottom_layout.addWidget(btn_select_occupied)

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.clicked.connect(self.deselect_all)
        bottom_layout.addWidget(btn_deselect_all)

        btn_export = QPushButton("Export to CSV")
        btn_export.clicked.connect(self.export_csv)
        bottom_layout.addWidget(btn_export)

        bottom_layout.addStretch()

        self.btn_add_to_monitor = QPushButton("Add Selected to D IP Monitor")
        self.btn_add_to_monitor.setStyleSheet("font-weight: bold; background-color: #10b981; color: white;")
        self.btn_add_to_monitor.clicked.connect(self.add_selected_to_monitor)
        bottom_layout.addWidget(self.btn_add_to_monitor)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(btn_close)

        layout.addLayout(bottom_layout)

        # Automatically auto-detect active local subnet on dialog launch
        self.auto_detect_subnet()

    def auto_detect_subnet(self):
        """Attempts to find the active local IPv4 address and automatically fill the /24 subnet."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            parts = local_ip.split(".")
            if len(parts) == 4:
                prefix = f"{parts[0]}.{parts[1]}.{parts[2]}"
                self.start_ip_input.setText(f"{prefix}.1")
                self.end_ip_input.setText(f"{prefix}.254")
                self.kpi_label.setText(f"Active Wi-Fi Subnet Detected: {prefix}.0/24 (Host: {local_ip})")
        except Exception:
            pass

    def _ip_to_int(self, ip_str: str) -> int:
        parts = [int(p) for p in ip_str.split(".")]
        return (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]

    def _int_to_ip(self, ip_int: int) -> str:
        return f"{(ip_int >> 24) & 255}.{(ip_int >> 16) & 255}.{(ip_int >> 8) & 255}.{ip_int & 255}"

    def start_scan(self):
        start_ip = self.start_ip_input.text().strip()
        end_ip = self.end_ip_input.text().strip()

        try:
            start_int = self._ip_to_int(start_ip)
            end_int = self._ip_to_int(end_ip)
            if start_int > end_int:
                QMessageBox.warning(self, "Invalid Range", "Start IP must be less than or equal to End IP.")
                return
            count = end_int - start_int + 1
            if count > 1024:
                QMessageBox.warning(self, "Range Too Large", "Maximum supported scan range is 1024 IPs at once.")
                return
        except Exception:
            QMessageBox.warning(self, "Invalid IP", "Could not parse IP addresses. Please verify format.")
            return

        ip_list = [self._int_to_ip(i) for i in range(start_int, end_int + 1)]

        self.table.setRowCount(0)
        self.results.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(ip_list))
        self.kpi_label.setText(f"Scanning {len(ip_list)} IPs via ARP + ICMP dual-engine...")

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.worker = RangeScanWorker(ip_list)
        self.worker.host_scanned.connect(self.on_host_scanned)
        self.worker.progress_updated.connect(lambda done, tot: self.progress_bar.setValue(done))
        self.worker.scan_finished.connect(self.on_scan_finished)
        self.worker.start()

    def on_host_scanned(self, ip: str, is_occupied: bool, hostname: str, mac: str, latency: float):
        self.results.append({
            "ip": ip,
            "is_occupied": is_occupied,
            "hostname": hostname,
            "mac": mac,
            "latency": latency
        })

        row = self.table.rowCount()
        self.table.insertRow(row)

        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Checked if is_occupied else Qt.CheckState.Unchecked)
        self.table.setItem(row, 0, chk_item)

        ip_item = QTableWidgetItem(ip)
        self.table.setItem(row, 1, ip_item)

        status_text = "● Occupied" if is_occupied else "○ Free"
        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(QColor("#10b981" if is_occupied else "#64748b"))
        status_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if is_occupied else QFont.Weight.Normal))
        self.table.setItem(row, 2, status_item)

        host_item = QTableWidgetItem(hostname if is_occupied else "—")
        self.table.setItem(row, 3, host_item)

        mac_item = QTableWidgetItem(mac if is_occupied else "—")
        mac_item.setFont(QFont("Segoe UI", 9))
        self.table.setItem(row, 4, mac_item)

        rtt_text = f"{latency:.1f} ms" if is_occupied else "—"
        rtt_item = QTableWidgetItem(rtt_text)
        self.table.setItem(row, 5, rtt_item)

        self.update_kpi_text()

    def update_kpi_text(self):
        total = len(self.results)
        occupied = sum(1 for r in self.results if r["is_occupied"])
        free = total - occupied
        occ_pct = (occupied / total * 100) if total > 0 else 0
        free_pct = (free / total * 100) if total > 0 else 0
        self.kpi_label.setText(
            f"Total: {total} | ● Occupied: {occupied} ({occ_pct:.1f}%) | ○ Free: {free} ({free_pct:.1f}%)"
        )

    def on_scan_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.update_kpi_text()

    def stop_scan(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.btn_start.setEnabled(True)

    def apply_filter(self, filter_type: str):
        self.btn_filter_all.setChecked(filter_type == "all")
        self.btn_filter_occ.setChecked(filter_type == "occupied")
        self.btn_filter_free.setChecked(filter_type == "free")

        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            if not status_item:
                continue
            is_occ = "Occupied" in status_item.text()
            if filter_type == "all":
                self.table.setRowHidden(row, False)
            elif filter_type == "occupied":
                self.table.setRowHidden(row, not is_occ)
            elif filter_type == "free":
                self.table.setRowHidden(row, is_occ)

    def select_all_occupied(self):
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            chk_item = self.table.item(row, 0)
            if status_item and chk_item:
                if "Occupied" in status_item.text():
                    chk_item.setCheckState(Qt.CheckState.Checked)
                else:
                    chk_item.setCheckState(Qt.CheckState.Unchecked)

    def deselect_all(self):
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item:
                chk_item.setCheckState(Qt.CheckState.Unchecked)

    def add_selected_to_monitor(self):
        selected = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            ip_item = self.table.item(row, 1)
            host_item = self.table.item(row, 3)
            mac_item = self.table.item(row, 4)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked and ip_item:
                ip = ip_item.text()
                desc = host_item.text() if host_item and host_item.text() != "—" else ""
                if not desc and mac_item and mac_item.text() != "—":
                    desc = f"Device ({mac_item.text()})"
                if not desc:
                    desc = ip
                selected.append((ip, desc))

        if not selected:
            QMessageBox.information(self, "No Selection", "Please check at least one IP to add.")
            return

        self.add_hosts_requested.emit(selected)
        QMessageBox.information(self, "Hosts Added", f"Queued {len(selected)} host(s) for monitoring.")
        self.close()

    def export_csv(self):
        if not self.results:
            QMessageBox.warning(self, "No Data", "No scan results available to export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save IP Allocation Report", "IP_Allocation_Report.csv", "CSV Files (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["IP Address", "Status", "Hostname / Device", "MAC Address", "Response Time (ms)"])
                for r in self.results:
                    writer.writerow([
                        r["ip"],
                        "Occupied" if r["is_occupied"] else "Free",
                        r["hostname"] if r["is_occupied"] else "",
                        r["mac"] if r["is_occupied"] else "",
                        f"{r['latency']:.1f}" if r["is_occupied"] else ""
                    ])
            QMessageBox.information(self, "Export Successful", f"Saved report to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save CSV: {e}")

    def closeEvent(self, event):
        self.stop_scan()
        super().closeEvent(event)
