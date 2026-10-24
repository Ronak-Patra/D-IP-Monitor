# themes.py — Professional Dark Neon Cyan & Clean SaaS Light Themes for D IP Monitor
from PyQt6.QtGui import QPalette, QColor

def get_dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#070c16"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0b1220"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#0d1627"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#0b1220"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#101a2c"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e2e8f0"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#00e5ff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0284c7"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#00e5ff"))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#38bdf8"))
    return palette

def get_light_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1e293b"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#0284c7"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0284c7"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#0284c7"))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#0369a1"))
    return palette

def get_dark_theme() -> str:
    return """
    /* D IP Monitor — Professional Dark Cyber & Neon Cyan Theme */
    QMainWindow, QDialog {
        background-color: #070c16;
        color: #f1f5f9;
        font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
    }

    /* Total Dark Canvas Protection: Force all base containers and scroll viewports to deep dark */
    #centralWidget, #leftPanelWidget, #leftScrollArea, #leftScrollViewport,
    QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
        background-color: #070c16;
        border: none;
    }

    QWidget {
        color: #f1f5f9;
        font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
    }

    /* Brand Header Card */
    #headerCard {
        background-color: #0b1220;
        border: 1px solid #16243b;
        border-radius: 8px;
    }

    /* Clean Card Containers */
    QGroupBox {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.6px;
        color: #00e5ff;
        border: 1px solid #16243b;
        border-radius: 8px;
        background-color: #0b1220;
        margin-top: 10px;
        padding-top: 18px;
        padding-left: 8px;
        padding-right: 8px;
        padding-bottom: 8px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        top: 2px;
        padding: 1px 7px;
        color: #00e5ff;
        background-color: #0d172a;
        border: 1px solid #1a2f4c;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    /* Settings Tabs inside Application Settings */
    QTabWidget#settingsTabs::pane {
        border: 1px solid #16243b;
        background-color: #080e1a;
        border-radius: 6px;
        top: -1px;
        padding: 4px;
    }

    QTabWidget#settingsTabs QTabBar::tab {
        background: #0a1120;
        color: #64748b;
        border: 1px solid #142033;
        border-bottom: none;
        padding: 4px 6px;
        margin-right: 2px;
        border-top-left-radius: 5px;
        border-top-right-radius: 5px;
        font-weight: 600;
        font-size: 11px;
    }

    QTabWidget#settingsTabs QTabBar::tab:hover:!selected {
        background: #0f1c30;
        color: #00e5ff;
        border-color: #1a2f4c;
    }

    QTabWidget#settingsTabs QTabBar::tab:selected {
        background: #080e1a;
        color: #00e5ff;
        border: 1px solid #16243b;
        border-bottom: 2px solid #00e5ff;
    }

    /* KPI Telemetry Cards */
    QFrame#kpiCard {
        background-color: #0d1627;
        border: 1px solid #1a273e;
        border-radius: 7px;
    }
    QFrame#kpiCard:hover {
        border-color: #00e5ff;
        background-color: #101c33;
    }

    /* Clean Input Fields */
    QLineEdit, QComboBox, QSpinBox {
        border: 1px solid #1c2b44;
        border-radius: 6px;
        padding: 6px 10px;
        background-color: #0a1120;
        color: #f8fafc;
        font-size: 12px;
        selection-background-color: #0284c7;
    }

    QLineEdit:hover, QComboBox:hover {
        border-color: #2b4166;
    }

    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #00e5ff;
        background-color: #0d172b;
    }


    QComboBox QAbstractItemView {
        background-color: #0c1424;
        border: 1px solid #1e2e47;
        selection-background-color: #0284c7;
        selection-color: #ffffff;
        padding: 4px;
        border-radius: 6px;
    }

    /* Modern Toolbar & Action Buttons */
    QPushButton {
        background-color: #101a2c;
        color: #e2e8f0;
        border: 1px solid #1e2e47;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 600;
        font-size: 12px;
        min-height: 18px;
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

    QPushButton:checked {
        background-color: #0284c7;
        color: #ffffff;
        border-color: #00e5ff;
        font-weight: 700;
    }

    QPushButton:disabled {
        background-color: #090e18;
        color: #475569;
        border-color: #131c2e;
    }

    /* Modern Sleek Progress Bar */
    QProgressBar {
        background-color: #0a1120;
        border: 1px solid #16243b;
        border-radius: 6px;
        min-height: 12px;
        max-height: 14px;
        text-align: center;
        color: #f1f5f9;
        font-size: 10px;
        font-weight: 700;
    }

    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #00e5ff);
        border-radius: 5px;
    }

    #btnStartScan {
        background-color: #0284c7;
        border: 1px solid #38bdf8;
        color: #ffffff;
        font-weight: 700;
    }
    #btnStartScan:hover {
        background-color: #0369a1;
        border-color: #00e5ff;
    }
    #btnStartScan:disabled {
        background-color: #0a1322;
        border-color: #16243b;
        color: #475569;
    }

    #btnStopScan {
        background-color: #7f1d1d;
        border: 1px solid #ef4444;
        color: #ffffff;
        font-weight: 700;
    }
    #btnStopScan:hover {
        background-color: #991b1b;
        border-color: #f87171;
    }
    #btnStopScan:disabled {
        background-color: #090e18;
        border-color: #131c2e;
        color: #475569;
    }

    /* Accent Actions */
    #btnAddIp {
        background-color: #059669;
        border: 1px solid #10b981;
        color: #ffffff;
        font-weight: 700;
    }
    #btnAddIp:hover {
        background-color: #10b981;
        border-color: #34d399;
    }

    #btnRemoveIp {
        background-color: #991b1b;
        border: 1px solid #ef4444;
        color: #ffffff;
        font-weight: 700;
    }
    #btnRemoveIp:hover {
        background-color: #dc2626;
        border-color: #f87171;
    }

    #btnSaveSettings {
        background-color: #0284c7;
        border: 1px solid #38bdf8;
        color: #ffffff;
        font-weight: 700;
        padding: 7px 14px;
    }
    #btnSaveSettings:hover {
        background-color: #0369a1;
        border-color: #00e5ff;
    }

    #btnScanner {
        background-color: #0284c7;
        border: 1px solid #38bdf8;
        color: #ffffff;
        font-weight: 700;
    }
    #btnScanner:hover {
        background-color: #0369a1;
        border-color: #00e5ff;
    }

    /* Checkboxes */
    QCheckBox {
        spacing: 7px;
        color: #94a3b8;
        font-size: 12px;
    }

    QCheckBox::indicator {
        width: 14px;
        height: 14px;
        border: 1px solid #22344f;
        border-radius: 3px;
        background-color: #09101d;
    }

    QCheckBox::indicator:hover {
        border-color: #00e5ff;
    }

    QCheckBox::indicator:checked {
        background-color: #00e5ff;
        border-color: #00e5ff;
    }

    /* Labels */
    QFormLayout QLabel {
        color: #94a3b8;
        font-size: 11px;
        font-weight: 600;
    }

    /* Clean Enterprise Data Table */
    QTableWidget {
        border: 1px solid #16233b;
        border-radius: 8px;
        background-color: #080f1d;
        alternate-background-color: #0c1424;
        gridline-color: #131e33;
        color: #f1f5f9;
        selection-background-color: #112844;
        selection-color: #38bdf8;
        font-size: 12px;
    }

    QTableWidget::item {
        padding: 6px 10px;
        border-bottom: 1px solid #0e1728;
    }

    QTableWidget::item:selected {
        background-color: #112844;
        color: #38bdf8;
    }

    QHeaderView::section {
        background-color: #0c1424;
        color: #94a3b8;
        padding: 7px 10px;
        border: none;
        border-bottom: 2px solid #00e5ff;
        border-right: 1px solid #16233b;
        font-weight: 700;
        font-size: 11px;
        letter-spacing: 0.5px;
    }

    /* Terminal Logs */
    QTextEdit {
        border: 1px solid #16243b;
        border-radius: 8px;
        padding: 8px;
        background-color: #050a14;
        color: #38bdf8;
        font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
        font-size: 11px;
        line-height: 1.4;
    }

    /* Scrollbars */
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 6px;
        margin: 1px;
    }

    QScrollBar::handle:vertical {
        background: #1c2b42;
        border-radius: 3px;
        min-height: 25px;
    }

    QScrollBar::handle:vertical:hover {
        background: #00e5ff;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
        background: none;
    }

    QScrollBar:horizontal {
        border: none;
        background: transparent;
        height: 6px;
        margin: 1px;
    }

    QScrollBar::handle:horizontal {
        background: #1c2b42;
        border-radius: 3px;
        min-width: 25px;
    }

    QScrollBar::handle:horizontal:hover {
        background: #00e5ff;
    }

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
        background: none;
    }

    /* Category Pill Tabs */
    QTabBar {
        background: transparent;
        qproperty-drawBase: 0;
    }

    QTabBar::tab {
        background: #0c1424;
        color: #8da2be;
        border: 1px solid #17243c;
        padding: 6px 16px;
        margin-right: 4px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
    }

    QTabBar::tab:hover:!selected {
        background: #121e33;
        color: #00e5ff;
        border-color: #1e3152;
    }

    QTabBar::tab:selected {
        background: #0284c7;
        color: #ffffff;
        border: 1px solid #38bdf8;
    }

    /* Splitter */
    QSplitter::handle {
        background-color: #101a2c;
        width: 3px;
    }
    QSplitter::handle:hover {
        background-color: #00e5ff;
    }

    /* Menus & Tooltips */
    QMenu {
        background-color: #0c1424;
        border: 1px solid #1c2d47;
        border-radius: 8px;
        padding: 4px;
        color: #f1f5f9;
    }

    QMenu::item {
        padding: 6px 20px;
        border-radius: 4px;
    }

    QMenu::item:selected {
        background-color: #0284c7;
        color: #ffffff;
    }

    QMenu::separator {
        height: 1px;
        background-color: #17243c;
        margin: 4px 0;
    }

    QToolTip {
        background-color: #0c1424;
        color: #00e5ff;
        border: 1px solid #1c2d47;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
    }
    """


def get_light_theme() -> str:
    return """
    /* D IP Monitor — Crisp Modern SaaS Light Theme */
    QMainWindow, QDialog {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
    }

    /* Base Containers & Viewports */
    #centralWidget, #leftPanelWidget, #leftScrollArea, #leftScrollViewport,
    QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
        background-color: #f8fafc;
        border: none;
    }

    QWidget {
        color: #0f172a;
        font-family: 'Segoe UI', 'Inter', -apple-system, sans-serif;
    }

    /* Brand Header Card */
    #headerCard {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }

    QGroupBox {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.6px;
        color: #0284c7;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background-color: #ffffff;
        margin-top: 10px;
        padding-top: 18px;
        padding-left: 8px;
        padding-right: 8px;
        padding-bottom: 8px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        top: 2px;
        padding: 1px 7px;
        color: #0284c7;
        background-color: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    /* Settings Tabs inside Application Settings */
    QTabWidget#settingsTabs::pane {
        border: 1px solid #e2e8f0;
        background-color: #ffffff;
        border-radius: 6px;
        top: -1px;
        padding: 4px;
    }

    QTabWidget#settingsTabs QTabBar::tab {
        background: #f1f5f9;
        color: #64748b;
        border: 1px solid #e2e8f0;
        border-bottom: none;
        padding: 5px 9px;
        margin-right: 2px;
        border-top-left-radius: 5px;
        border-top-right-radius: 5px;
        font-weight: 600;
        font-size: 11px;
    }

    QTabWidget#settingsTabs QTabBar::tab:hover:!selected {
        background: #e2e8f0;
        color: #0284c7;
    }

    QTabWidget#settingsTabs QTabBar::tab:selected {
        background: #ffffff;
        color: #0284c7;
        border: 1px solid #cbd5e1;
        border-bottom: 2px solid #0284c7;
    }

    /* KPI Cards */
    QFrame#kpiCard {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 7px;
    }
    QFrame#kpiCard:hover {
        border-color: #0284c7;
        background-color: #f1f5f9;
    }

    /* Text Inputs */
    QLineEdit, QComboBox, QSpinBox {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 6px 10px;
        background-color: #ffffff;
        color: #0f172a;
        font-size: 12px;
        selection-background-color: #bae6fd;
    }

    QLineEdit:hover, QComboBox:hover {
        border-color: #94a3b8;
    }

    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #0284c7;
        background-color: #f8fafc;
    }


    QComboBox QAbstractItemView {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        selection-background-color: #e0f2fe;
        selection-color: #0369a1;
        padding: 4px;
        border-radius: 6px;
    }

    /* Action Buttons */
    QPushButton {
        background-color: #f1f5f9;
        color: #1e293b;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 600;
        font-size: 12px;
        min-height: 18px;
    }

    QPushButton:hover {
        background-color: #e2e8f0;
        border-color: #0284c7;
        color: #0284c7;
    }

    QPushButton:pressed {
        background-color: #cbd5e1;
        border-color: #0369a1;
    }

    QPushButton:checked {
        background-color: #0284c7;
        color: #ffffff;
        border-color: #0369a1;
        font-weight: 700;
    }

    /* Modern Sleek Progress Bar */
    QProgressBar {
        background-color: #e2e8f0;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        min-height: 12px;
        max-height: 14px;
        text-align: center;
        color: #0f172a;
        font-size: 10px;
        font-weight: 700;
    }

    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
        border-radius: 5px;
    }

    #btnStartScan {
        background-color: #0284c7;
        border: 1px solid #0369a1;
        color: #ffffff;
        font-weight: 700;
    }
    #btnStartScan:hover {
        background-color: #0369a1;
        border-color: #0284c7;
    }
    #btnStartScan:disabled {
        background-color: #f1f5f9;
        border-color: #e2e8f0;
        color: #94a3b8;
    }

    #btnStopScan {
        background-color: #dc2626;
        border: 1px solid #b91c1c;
        color: #ffffff;
        font-weight: 700;
    }
    #btnStopScan:hover {
        background-color: #b91c1c;
        border-color: #991b1b;
    }
    #btnStopScan:disabled {
        background-color: #f1f5f9;
        border-color: #e2e8f0;
        color: #94a3b8;
    }

    /* Primary Accent Buttons */
    #btnAddIp {
        background-color: #059669;
        border: 1px solid #10b981;
        color: #ffffff;
        font-weight: 700;
    }
    #btnAddIp:hover {
        background-color: #10b981;
    }

    #btnRemoveIp {
        background-color: #dc2626;
        border: 1px solid #ef4444;
        color: #ffffff;
        font-weight: 700;
    }
    #btnRemoveIp:hover {
        background-color: #ef4444;
    }

    #btnSaveSettings {
        background-color: #0284c7;
        border: 1px solid #0369a1;
        color: #ffffff;
        font-weight: 700;
        padding: 7px 14px;
    }
    #btnSaveSettings:hover {
        background-color: #0369a1;
    }

    #btnScanner {
        background-color: #0284c7;
        border: 1px solid #0369a1;
        color: #ffffff;
        font-weight: 700;
    }
    #btnScanner:hover {
        background-color: #0369a1;
    }

    /* Checkboxes */
    QCheckBox {
        spacing: 7px;
        color: #475569;
        font-size: 12px;
    }

    QCheckBox::indicator {
        width: 14px;
        height: 14px;
        border: 1px solid #cbd5e1;
        border-radius: 3px;
        background-color: #ffffff;
    }

    QCheckBox::indicator:hover {
        border-color: #0284c7;
    }

    QCheckBox::indicator:checked {
        background-color: #0284c7;
        border-color: #0284c7;
    }

    /* Labels */
    QFormLayout QLabel {
        color: #475569;
        font-size: 11px;
        font-weight: 600;
    }

    /* Table Widget */
    QTableWidget {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background-color: #ffffff;
        alternate-background-color: #f8fafc;
        gridline-color: #f1f5f9;
        color: #0f172a;
        selection-background-color: #e0f2fe;
        selection-color: #0369a1;
        font-size: 12px;
    }

    QTableWidget::item {
        padding: 6px 10px;
        border-bottom: 1px solid #f1f5f9;
    }

    QHeaderView::section {
        background-color: #f1f5f9;
        color: #475569;
        padding: 7px 10px;
        border: none;
        border-bottom: 2px solid #0284c7;
        border-right: 1px solid #e2e8f0;
        font-weight: 700;
        font-size: 11px;
        letter-spacing: 0.5px;
    }

    /* Terminal Logs */
    QTextEdit {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 8px;
        background-color: #0f172a;
        color: #38bdf8;
        font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
        font-size: 11px;
        line-height: 1.4;
    }

    /* Scrollbars */
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 6px;
        margin: 1px;
    }

    QScrollBar::handle:vertical {
        background: #cbd5e1;
        border-radius: 3px;
        min-height: 25px;
    }

    QScrollBar::handle:vertical:hover {
        background: #0284c7;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
        background: none;
    }

    QScrollBar:horizontal {
        border: none;
        background: transparent;
        height: 6px;
        margin: 1px;
    }

    QScrollBar::handle:horizontal {
        background: #cbd5e1;
        border-radius: 3px;
        min-width: 25px;
    }

    QScrollBar::handle:horizontal:hover {
        background: #0284c7;
    }

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
        background: none;
    }

    /* Category Pill Tabs */
    QTabBar {
        background: transparent;
        qproperty-drawBase: 0;
    }

    QTabBar::tab {
        background: #f1f5f9;
        color: #64748b;
        border: 1px solid #e2e8f0;
        padding: 6px 16px;
        margin-right: 4px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12px;
    }

    QTabBar::tab:hover:!selected {
        background: #e2e8f0;
        color: #0284c7;
    }

    QTabBar::tab:selected {
        background: #0284c7;
        color: #ffffff;
        border: 1px solid #0369a1;
    }

    /* Splitter */
    QSplitter::handle {
        background-color: #e2e8f0;
        width: 3px;
    }
    QSplitter::handle:hover {
        background-color: #0284c7;
    }

    /* Menus & Tooltips */
    QMenu {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 4px;
        color: #0f172a;
    }

    QMenu::item {
        padding: 6px 20px;
        border-radius: 4px;
    }

    QMenu::item:selected {
        background-color: #0284c7;
        color: #ffffff;
    }

    QMenu::separator {
        height: 1px;
        background-color: #e2e8f0;
        margin: 4px 0;
    }

    QToolTip {
        background-color: #1e293b;
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
    }
    """
