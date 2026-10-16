import sys
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QFont, QCursor, QPixmap

class FloatingHudWidget(QWidget):
    """
    Compact, Always-On-Top cyber-themed semi-transparent desktop HUD widget
    displaying real-time network health metrics pills in a sleek floating telemetry bar.
    """
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(370, 105)
        self.drag_position = QPoint()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Outer Glass Container
        self.container = QFrame()
        self.container.setObjectName("hudContainer")
        self.container.setStyleSheet("""
            QFrame#hudContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f172a, stop:0.6 #0a0f1d, stop:1 #060913);
                border: 1px solid rgba(0, 229, 255, 0.45);
                border-radius: 12px;
            }
        """)

        # Soft Neon Drop Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 229, 255, 65))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(10)

        # 1. Top Title Bar with App Logo, Draggable Grip & Close Button
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 0)
        title_bar.setSpacing(6)

        # D IP Monitor Logo in Top-Left
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, 'app_icon.png')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_dir, 'app_icon.ico')

        self.logo_label = QLabel()
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pix)
            self.logo_label.setFixedSize(18, 18)
        self.logo_label.setStyleSheet("border: none; background: transparent;")
        title_bar.addWidget(self.logo_label)

        title_label = QLabel("D IP MONITOR")
        title_label.setStyleSheet("font-size: 11px; font-weight: 800; color: #00e5ff; letter-spacing: 1px; border: none;")
        title_bar.addWidget(title_label)

        hud_badge = QLabel("HUD")
        hud_badge.setStyleSheet("""
            background: rgba(0, 229, 255, 0.15);
            color: #00e5ff;
            border: 1px solid rgba(0, 229, 255, 0.3);
            border-radius: 3px;
            font-size: 9px;
            font-weight: bold;
            padding: 1px 4px;
        """)
        title_bar.addWidget(hud_badge)

        grip_label = QLabel("::: DRAG :::")
        grip_label.setStyleSheet("color: #475569; font-size: 9px; font-weight: bold; border: none; letter-spacing: 1px;")
        grip_label.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        title_bar.addWidget(grip_label)

        title_bar.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setToolTip("Hide Mini HUD")
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ef4444;
                color: #ffffff;
                border: 1px solid #ef4444;
            }
        """)
        btn_close.clicked.connect(self.hide)
        title_bar.addWidget(btn_close)

        container_layout.addLayout(title_bar)

        # 2. Telemetry Metric Pills Row
        pills_layout = QHBoxLayout()
        pills_layout.setContentsMargins(0, 0, 0, 0)
        pills_layout.setSpacing(6)

        self.pill_up = QLabel("0 UP")
        self.pill_up.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.45);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.pill_up.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pills_layout.addWidget(self.pill_up)

        self.pill_down = QLabel("0 DOWN")
        self.pill_down.setStyleSheet("""
            background-color: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.45);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.pill_down.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pills_layout.addWidget(self.pill_down)

        self.pill_rtt = QLabel("⚡ 0 ms")
        self.pill_rtt.setStyleSheet("""
            background-color: rgba(0, 229, 255, 0.12);
            color: #00e5ff;
            border: 1px solid rgba(0, 229, 255, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.pill_rtt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pills_layout.addWidget(self.pill_rtt)

        self.pill_health = QLabel("100% HEALTH")
        self.pill_health.setStyleSheet("""
            background-color: rgba(168, 85, 247, 0.12);
            color: #c084fc;
            border: 1px solid rgba(168, 85, 247, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        self.pill_health.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pills_layout.addWidget(self.pill_health)

        container_layout.addLayout(pills_layout)

        # Legacy summary_label kept hidden for backward compatibility
        self.summary_label = QLabel()
        self.summary_label.setVisible(False)

        main_layout.addWidget(self.container)

    def update_hud(self, ip_monitors: list):
        """Updates the HUD telemetry pills with live statistics."""
        total = len(ip_monitors)
        online = sum(1 for m in ip_monitors if m.status == "Reachable")
        offline = sum(1 for m in ip_monitors if m.status == "Unreachable")
        reachables = [m.response_time for m in ip_monitors if m.status == "Reachable" and m.response_time > 0]
        avg_rtt = (sum(reachables) / len(reachables)) if reachables else 0.0
        health = (online / total * 100) if total > 0 else 100.0

        self.pill_up.setText(f"{online} UP")
        self.pill_down.setText(f"{offline} DOWN")
        self.pill_rtt.setText(f"⚡ {avg_rtt:.1f}ms")
        self.pill_health.setText(f"{health:.0f}% HEALTH")

        # Keep legacy summary_label updated for any external listener
        self.summary_label.setText(f"{online} UP   {offline} DOWN   ⚡ {avg_rtt:.1f}ms")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
