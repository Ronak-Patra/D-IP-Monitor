from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QSizePolicy, QBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QPolygonF, QCursor

class KpiCard(QFrame):
    def __init__(self, title: str, initial_value: str, accent_color: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("kpiCard")
        self.accent_color = accent_color

        self.setStyleSheet(f"""
            QFrame#kpiCard {{
                background-color: #0c1424;
                border: 1px solid #16233b;
                border-left: 3px solid {accent_color};
                border-radius: 6px;
            }}
            QFrame#kpiCard:hover {{
                border-color: #00e5ff;
                background-color: #101c33;
            }}
        """)

        self.layout_box = QHBoxLayout(self)
        self.layout_box.setContentsMargins(8, 4, 10, 4)
        self.layout_box.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("kpiTitle")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.title_label.setStyleSheet("font-size: 10px; color: #7e8fa6; font-weight: 700; letter-spacing: 0.5px;")

        self.value_label = QLabel(initial_value)
        self.value_label.setObjectName("kpiValue")
        self.value_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.value_label.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {accent_color};")

        self.layout_box.addWidget(self.title_label)
        self.layout_box.addStretch()
        self.layout_box.addWidget(self.value_label)

    def set_sidebar_mode(self, is_sidebar: bool):
        if is_sidebar:
            self.setFixedHeight(34)
            self.title_label.setStyleSheet("font-size: 10px; color: #7e8fa6; font-weight: 700; letter-spacing: 0.5px;")
            self.value_label.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {self.accent_color};")
        else:
            self.setFixedHeight(48)
            self.title_label.setStyleSheet("font-size: 10px; color: #7e8fa6; font-weight: 700; letter-spacing: 0.6px;")
            self.value_label.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {self.accent_color};")

    def set_value(self, val: str):
        self.value_label.setText(val)


class MetricsBannerWidget(QWidget):
    position_toggle_clicked = pyqtSignal()

    def __init__(self, is_sidebar_mode: bool = False, parent=None):
        super().__init__(parent)
        self.is_sidebar_mode = is_sidebar_mode

        self.card_total = KpiCard("TOTAL HOSTS", "0", "#0284c7")
        self.card_online = KpiCard("ONLINE", "0", "#10b981")
        self.card_offline = KpiCard("OFFLINE", "0", "#ef4444")
        self.card_latency = KpiCard("AVG LATENCY", "0 ms", "#8b5cf6")
        self.card_health = KpiCard("HEALTH", "100%", "#00e5ff")

        self.btn_dock_toggle = QPushButton("⇋ Dock")
        self.btn_dock_toggle.setToolTip("Switch Dashboard between Top Banner and Sidebar")
        self.btn_dock_toggle.setFixedWidth(65)
        self.btn_dock_toggle.setStyleSheet("font-size: 11px; padding: 4px; border-radius: 4px;")
        self.btn_dock_toggle.clicked.connect(self.position_toggle_clicked.emit)

        # Header widget used in sidebar mode
        self.sidebar_header = QWidget()
        s_layout = QHBoxLayout(self.sidebar_header)
        s_layout.setContentsMargins(4, 2, 4, 4)
        title = QLabel("<b>METRICS DASHBOARD</b>")
        title.setStyleSheet("font-size: 11px; color: #00e5ff; font-weight: bold;")
        s_layout.addWidget(title)
        s_layout.addStretch()
        self.sidebar_dock_btn = QPushButton("⇋ Dock Top")
        self.sidebar_dock_btn.setToolTip("Switch to Top Banner")
        self.sidebar_dock_btn.setStyleSheet("font-size: 11px; padding: 3px 8px; border-radius: 4px;")
        self.sidebar_dock_btn.clicked.connect(self.position_toggle_clicked.emit)
        s_layout.addWidget(self.sidebar_dock_btn)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)
        self.main_layout.addWidget(self.sidebar_header)

        # Cards container with directional QBoxLayout
        self.cards_container = QWidget()
        init_direction = QBoxLayout.Direction.TopToBottom if is_sidebar_mode else QBoxLayout.Direction.LeftToRight
        self.cards_layout = QBoxLayout(init_direction, self.cards_container)
        self.cards_layout.setContentsMargins(4, 2, 4, 2)
        self.cards_layout.setSpacing(6)

        self.cards_layout.addWidget(self.card_total)
        self.cards_layout.addWidget(self.card_online)
        self.cards_layout.addWidget(self.card_offline)
        self.cards_layout.addWidget(self.card_latency)
        self.cards_layout.addWidget(self.card_health)
        self.cards_layout.addWidget(self.btn_dock_toggle)

        self.main_layout.addWidget(self.cards_container)

        self.apply_mode_ui()

    def apply_mode_ui(self):
        for card in [self.card_total, self.card_online, self.card_offline, self.card_latency, self.card_health]:
            card.set_sidebar_mode(self.is_sidebar_mode)
        if self.is_sidebar_mode:
            self.sidebar_header.setVisible(True)
            self.btn_dock_toggle.setVisible(False)
            self.cards_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.cards_layout.setSpacing(4)
        else:
            self.sidebar_header.setVisible(False)
            self.btn_dock_toggle.setVisible(True)
            self.cards_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.cards_layout.setSpacing(8)

    def set_sidebar_mode(self, is_sidebar: bool):
        self.is_sidebar_mode = is_sidebar
        self.apply_mode_ui()

    def update_metrics(self, total: int, online: int, offline: int, avg_latency: float, health_pct: float):
        self.card_total.set_value(str(total))
        self.card_online.set_value(str(online))
        self.card_offline.set_value(str(offline))
        self.card_latency.set_value(f"{avg_latency:.1f} ms" if online > 0 else "—")
        self.card_health.set_value(f"{health_pct:.1f}%")


class LatencySparklineWidget(QWidget):
    """
    Renders an animated, high-DPI smooth sparkline graph showing the last 30
    ping response times for the selected host.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(95)
        self.setMaximumHeight(130)
        self.target_name = "No Host Selected"
        self.target_ip = ""
        self.samples = [] # list of floats
        self.is_dark_mode = False
        self.setMouseTracking(True)
        self.hover_index = -1
        self.cached_points = []

    def set_host_data(self, ip: str, desc: str, samples: list):
        self.target_ip = ip
        self.target_name = f"{ip} ({desc})" if desc and desc != ip else ip
        self.samples = list(samples) if samples else []
        if self.hover_index >= len(self.samples):
            self.hover_index = -1
            self.setToolTip("")
            self.unsetCursor()
        self.update()

    def set_dark_mode(self, is_dark: bool):
        self.is_dark_mode = is_dark
        self.update()

    def mouseMoveEvent(self, event):
        if not self.samples or not self.cached_points:
            if self.hover_index != -1:
                self.hover_index = -1
                self.setToolTip("")
                self.unsetCursor()
                self.update()
            return super().mouseMoveEvent(event)

        pos = event.position()
        mx = pos.x()
        my = pos.y()

        # Find closest point horizontally
        closest_idx = -1
        min_dist = float('inf')
        for i, pt in enumerate(self.cached_points):
            dist = abs(pt.x() - mx)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i

        # Calculate spacing threshold
        threshold = max(35.0, (self.width() / max(1, len(self.samples))))
        if closest_idx != -1 and min_dist <= threshold:
            if self.hover_index != closest_idx:
                self.hover_index = closest_idx
                val = self.samples[closest_idx]
                total = len(self.samples)
                age = total - 1 - closest_idx
                time_str = "Latest Ping" if age == 0 else f"{age} pings ago"

                sample_num = age + 1
                if val < 0:
                    status_str = "TIMEOUT / LOST"
                    status_color = "#ef4444"
                    lat_str = "No Reply (100% loss)"
                else:
                    status_str = "ONLINE"
                    status_color = "#22c55e"
                    lat_str = "<1 ms" if (0 <= val < 1.0) else f"{val:.1f} ms"

                tooltip_html = (
                    f"<div style='font-family: Segoe UI, sans-serif; font-size: 11px; padding: 4px; line-height: 1.4;'>"
                    f"<b style='color: #00e5ff;'>{self.target_name}</b><br/>"
                    f"Sample: <b style='color: #94a3b8;'>#{sample_num} of {total}</b> ({time_str})<br/>"
                    f"Status: <b style='color: {status_color};'>{status_str}</b><br/>"
                    f"Latency: <b style='color: #f8fafc;'>{lat_str}</b>"
                    f"</div>"
                )
                self.setToolTip(tooltip_html)
                self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
                self.update()
        else:
            if self.hover_index != -1:
                self.hover_index = -1
                self.setToolTip("")
                self.unsetCursor()
                self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self.hover_index != -1:
            self.hover_index = -1
            self.setToolTip("")
            self.unsetCursor()
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        bg_color = QColor("#0b1329") if self.is_dark_mode else QColor("#f8fafc")
        border_color = QColor("#1e293b") if self.is_dark_mode else QColor("#e2e8f0")
        text_color = QColor("#94a3b8") if self.is_dark_mode else QColor("#64748b")
        accent_color = QColor("#00e5ff") if self.is_dark_mode else QColor("#0284c7")

        # Background rounded rect
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        # Draw Header Info (adaptive elided text)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#38bdf8" if self.is_dark_mode else "#0369a1")))
        title_str = painter.fontMetrics().elidedText(f"Live Latency Trend: {self.target_name}", Qt.TextElideMode.ElideRight, w - 24)
        painter.drawText(12, 18, title_str)

        if not self.samples:
            self.cached_points = []
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(text_color))
            no_host_str = painter.fontMetrics().elidedText("Select a host to view real-time latency history (last 30 pings)", Qt.TextElideMode.ElideRight, w - 24)
            painter.drawText(12, 45, no_host_str)
            return

        # Compute min, max, avg
        valid_samples = [s for s in self.samples if s >= 0]
        curr_sample = valid_samples[-1] if valid_samples else 0.0
        min_s = min(valid_samples) if valid_samples else 0.0
        max_s = max(valid_samples) if valid_samples else 1.0
        avg_s = (sum(valid_samples) / len(valid_samples)) if valid_samples else 0.0

        # Stats sub-header (adaptive format & elided)
        painter.setFont(QFont("Segoe UI", 8))
        if 0 <= self.hover_index < len(self.samples):
            h_val = self.samples[self.hover_index]
            total = len(self.samples)
            age = total - 1 - self.hover_index
            sample_num = age + 1
            age_str = "Latest Ping" if age == 0 else f"{age} pings ago"
            if h_val < 0:
                val_display = "TIMEOUT / LOST"
            elif 0 <= h_val < 1.0:
                val_display = "<1ms" if h_val <= 0.5 else f"{h_val:.1f}ms"
            else:
                val_display = f"{h_val:.1f}ms"
            painter.setPen(QPen(QColor("#00e5ff" if self.is_dark_mode else "#0284c7")))
            stats_text = f"#{sample_num}/{total} ({age_str}): {val_display} | Cur: {curr_sample:.1f}ms | Avg: {avg_s:.1f}ms"
        else:
            painter.setPen(QPen(text_color))
            if w < 330:
                stats_text = f"Cur: {curr_sample:.1f}ms | Avg: {avg_s:.1f}ms | Max: {max_s:.1f}ms"
            else:
                stats_text = f"Current: {curr_sample:.1f}ms  |  Avg: {avg_s:.1f}ms  |  Min: {min_s:.1f}ms  |  Max: {max_s:.1f}ms"
        stats_elided = painter.fontMetrics().elidedText(stats_text, Qt.TextElideMode.ElideRight, w - 24)
        painter.drawText(12, 33, stats_elided)

        # Plot Area bounds
        plot_x = 12
        plot_y = 42
        plot_w = w - 24
        plot_h = h - plot_y - 10

        if plot_w <= 10 or plot_h <= 10:
            self.cached_points = []
            return

        # Grid lines (mid and base)
        painter.setPen(QPen(QColor("#1e293b" if self.is_dark_mode else "#e2e8f0"), 1, Qt.PenStyle.DotLine))
        painter.drawLine(plot_x, int(plot_y + plot_h / 2), plot_x + plot_w, int(plot_y + plot_h / 2))
        painter.drawLine(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h)

        # Map samples to coordinates
        display_max = max(max_s * 1.25, 10.0) # buffer so curve doesn't hit top edge
        points = []
        n = len(self.samples)
        dx = plot_w / max(1, n - 1) if n > 1 else plot_w

        for i, val in enumerate(self.samples):
            px = plot_x + i * dx
            if val < 0:
                py = plot_y + plot_h # timeout/loss sits on bottom baseline
            else:
                ratio = min(1.0, max(0.0, val) / display_max)
                py = (plot_y + plot_h) - (ratio * plot_h)
            points.append(QPointF(px, py))

        self.cached_points = list(points)

        if not points:
            return

        # Gradient fill under the curve
        grad_color_top = QColor(0, 229, 255, 60 if self.is_dark_mode else 35)
        grad_color_bot = QColor(0, 229, 255, 0)
        gradient = QLinearGradient(plot_x, plot_y, plot_x, plot_y + plot_h)
        gradient.setColorAt(0, grad_color_top)
        gradient.setColorAt(1, grad_color_bot)

        poly_points = [QPointF(points[0].x(), plot_y + plot_h)] + points + [QPointF(points[-1].x(), plot_y + plot_h)]
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF(poly_points))

        # Draw Sparkline Stroke
        curve_pen = QPen(accent_color, 2)
        curve_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        curve_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(curve_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])

        # Draw point dots (red for timeout/loss, accent for successful)
        painter.setPen(QPen(QColor("#ffffff"), 1))
        for idx_pt, p in enumerate(points):
            pt_val = self.samples[idx_pt] if idx_pt < len(self.samples) else 0.0
            pt_color = QColor("#ef4444") if pt_val < 0 else accent_color
            painter.setBrush(QBrush(pt_color))
            painter.drawEllipse(p, 2.5, 2.5)

        # Highlight current (last) point
        last_pt = points[-1]
        painter.setBrush(QBrush(QColor("#22c55e"))) # Green glowing dot
        painter.drawEllipse(last_pt, 4.0, 4.0)

        # Draw Hover Tracking Overlay (Crosshair, Glow Ring, and Floating Chip)
        if 0 <= self.hover_index < len(points):
            hover_pt = points[self.hover_index]
            hover_val = self.samples[self.hover_index]

            # 1. Vertical tracking crosshair line
            cross_pen = QPen(QColor(0, 229, 255, 160), 1.2, Qt.PenStyle.DashLine)
            painter.setPen(cross_pen)
            painter.drawLine(QPointF(hover_pt.x(), plot_y), QPointF(hover_pt.x(), plot_y + plot_h))

            # 2. Glowing outer halo ring
            halo_color = QColor(239, 68, 68, 90) if hover_val < 0 else QColor(0, 229, 255, 90)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(halo_color))
            painter.drawEllipse(hover_pt, 8.0, 8.0)

            # Core highlighted dot
            core_color = QColor("#ef4444") if hover_val < 0 else QColor("#00e5ff")
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(QBrush(core_color))
            painter.drawEllipse(hover_pt, 4.0, 4.0)

            # 3. Floating on-canvas badge/chip
            if hover_val < 0:
                badge_text = "LOST"
            elif 0 <= hover_val < 1.0:
                badge_text = "<1ms" if hover_val <= 0.5 else f"{hover_val:.1f}ms"
            else:
                badge_text = f"{hover_val:.1f}ms"
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(badge_text)
            text_h = fm.height()
            badge_w = text_w + 14
            badge_h = text_h + 4

            # Position badge centered over hover_pt, clamped horizontally
            badge_x = hover_pt.x() - (badge_w / 2.0)
            badge_x = max(float(plot_x), min(badge_x, float(plot_x + plot_w - badge_w)))

            # Place above point if room, else below
            if hover_pt.y() - badge_h - 6 >= plot_y:
                badge_y = hover_pt.y() - badge_h - 6
            else:
                badge_y = hover_pt.y() + 8

            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)

            # Chip background & border
            badge_bg = QColor(11, 19, 41, 235) if self.is_dark_mode else QColor(255, 255, 255, 240)
            badge_border = QColor("#ef4444") if hover_val < 0 else (QColor("#00e5ff") if self.is_dark_mode else QColor("#0284c7"))
            badge_fg = QColor("#fca5a5") if hover_val < 0 else (QColor("#00e5ff") if self.is_dark_mode else QColor("#0369a1"))

            painter.setBrush(QBrush(badge_bg))
            painter.setPen(QPen(badge_border, 1.2))
            painter.drawRoundedRect(badge_rect, 4.0, 4.0)

            painter.setPen(QPen(badge_fg))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

