"""
QSS Dark Theme — UAV-CD-APP
=============================
Premium dark theme inspired by modern engineering tools.
Colour palette:
  Background:    #1e1e2e (deep navy)
  Surface:       #2a2a3e (card background)
  Border:        #3a3a5c
  Accent:        #7c6af7 (purple-blue)
  Text Primary:  #e0e0f0
  Text Muted:    #888aaa
  Success:       #2ecc71
  Warning:       #f39c12
  Error:         #e74c3c
"""

QSS_DARK = """
/* ── Global ─────────────────────────────────────────────────────────── */
QWidget {
    background-color: #1e1e2e;
    color: #e0e0f0;
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
}

/* ── Main Window ─────────────────────────────────────────────────────── */
QMainWindow {
    background-color: #1e1e2e;
}

/* ── Scroll Areas ────────────────────────────────────────────────────── */
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    background: #2a2a3e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #5a5a8a;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #7c6af7; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ── Tab Widget ──────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #3a3a5c;
    border-top: 2px solid #7c6af7;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #2a2a3e;
    color: #888aaa;
    padding: 8px 18px;
    border: 1px solid #3a3a5c;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #e0e0f0;
    border-top: 2px solid #7c6af7;
}
QTabBar::tab:hover:!selected { background-color: #32324a; color: #c0c0e0; }

/* ── Cards / Frames ──────────────────────────────────────────────────── */
QFrame#ResultCard {
    background-color: #2a2a3e;
    border: 1px solid #3a3a5c;
    border-radius: 8px;
}
QFrame#Card {
    background-color: #2a2a3e;
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    padding: 8px;
}

/* ── Labels ──────────────────────────────────────────────────────────── */
QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 600;
    color: #b0b0d8;
    padding-bottom: 4px;
    border-bottom: 1px solid #3a3a5c;
}
QLabel#InputLabel       { color: #888aaa; font-size: 12px; }
QLabel#SliderLabel      { color: #888aaa; font-size: 12px; }
QLabel#SliderValueLabel { color: #e0e0f0; font-size: 12px; font-weight: 600; }
QLabel#ResultCardLabel  { color: #888aaa; font-size: 11px; text-transform: uppercase; background: transparent; }
QLabel#ResultCardValue  { color: #e0e0f0; font-size: 18px; font-weight: 700; background: transparent; }
QLabel#ResultCardUnit   { color: #888aaa; font-size: 13px; margin-bottom: 4px; background: transparent; }
QLabel#ErrorLabel       { color: #e74c3c; font-size: 11px; }
QLabel#AlertBanner      {
    background-color: #3d1a1a;
    color: #e74c3c;
    border: 1px solid #e74c3c;
    border-radius: 6px;
    padding: 6px 12px;
}

/* ── Inputs ──────────────────────────────────────────────────────────── */
QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit {
    background-color: #2a2a3e;
    border: 1px solid #3a3a5c;
    border-radius: 5px;
    padding: 4px 8px;
    color: #e0e0f0;
    selection-background-color: #7c6af7;
}
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {
    border-color: #7c6af7;
}
QDoubleSpinBox[state="error"], QSpinBox[state="error"] {
    border-color: #e74c3c;
    background-color: #3d1a1a;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: #3a3a5c;
    border: none;
    width: 16px;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: #7c6af7;
}

/* ── ComboBox ─────────────────────────────────────────────────────────── */
QComboBox {
    background-color: #2a2a3e;
    border: 1px solid #3a3a5c;
    border-radius: 5px;
    padding: 4px 8px;
    color: #e0e0f0;
}
QComboBox:focus { border-color: #7c6af7; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid #888aaa; }
QComboBox QAbstractItemView {
    background-color: #2a2a3e;
    border: 1px solid #5a5a8a;
    selection-background-color: #7c6af7;
    color: #e0e0f0;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #7c6af7;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 600;
}
QPushButton:hover    { background-color: #9580ff; }
QPushButton:pressed  { background-color: #5a4ad0; }
QPushButton:disabled { background-color: #3a3a5c; color: #666688; }
QPushButton#DangerButton { background-color: #e74c3c; }
QPushButton#DangerButton:hover { background-color: #ff6b6b; }
QPushButton#SecondaryButton {
    background-color: transparent;
    border: 1px solid #5a5a8a;
    color: #b0b0d8;
}
QPushButton#SecondaryButton:hover { border-color: #7c6af7; color: #e0e0f0; }

/* ── Slider ──────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 4px;
    background: #3a3a5c;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #7c6af7;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #9580ff; }
QSlider::sub-page:horizontal {
    background: #7c6af7;
    border-radius: 2px;
}

/* ── Table ──────────────────────────────────────────────────────────── */
QTableWidget {
    background-color: #1e1e2e;
    gridline-color: #3a3a5c;
    border: 1px solid #3a3a5c;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #2a2a3e;
    color: #b0b0d8;
    border: none;
    border-bottom: 1px solid #3a3a5c;
    padding: 6px;
    font-weight: 600;
    font-size: 12px;
}
QTableWidget::item { padding: 4px 8px; border: none; }
QTableWidget::item:selected { background-color: #7c6af7; }

/* ── Menu Bar ─────────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #1a1a28;
    color: #b0b0d8;
    border-bottom: 1px solid #3a3a5c;
}
QMenuBar::item:selected { background-color: #2a2a3e; color: #e0e0f0; }
QMenu {
    background-color: #2a2a3e;
    border: 1px solid #5a5a8a;
    border-radius: 6px;
}
QMenu::item:selected { background-color: #7c6af7; color: #ffffff; }
QMenu::separator { height: 1px; background: #3a3a5c; }

/* ── Status Bar ──────────────────────────────────────────────────────── */
QStatusBar {
    background-color: #1a1a28;
    color: #888aaa;
    border-top: 1px solid #3a3a5c;
    font-size: 12px;
}
QStatusBar::item { border: none; }

/* ── ToolTip ─────────────────────────────────────────────────────────── */
QToolTip {
    background-color: #2a2a3e;
    color: #e0e0f0;
    border: 1px solid #5a5a8a;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── Group Box ───────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    color: #888aaa;
    font-size: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    color: #b0b0d8;
}

/* ── CheckBox / RadioButton ─────────────────────────────────────────── */
QCheckBox, QRadioButton { color: #e0e0f0; spacing: 6px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 1px solid #5a5a8a;
    border-radius: 3px;
    background: #2a2a3e;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #7c6af7;
    border-color: #7c6af7;
}
"""

QSS_LIGHT = """
/* ── Global ─────────────────────────────────────────────────────────── */
QWidget {
    background-color: #f5f5fa;
    color: #1a1a2e;
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
}

QMainWindow { background-color: #f5f5fa; }

QScrollBar:vertical {
    background: #e0e0ec;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #a0a0c0;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #6c5ce7; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QTabWidget::pane {
    border: 1px solid #d0d0e0;
    border-top: 2px solid #6c5ce7;
    background-color: #f5f5fa;
}
QTabBar::tab {
    background-color: #e8e8f5;
    color: #666688;
    padding: 8px 18px;
    border: 1px solid #d0d0e0;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #f5f5fa;
    color: #1a1a2e;
    border-top: 2px solid #6c5ce7;
}
QTabBar::tab:hover:!selected { background-color: #dcdcee; }

QFrame#ResultCard {
    background-color: #ffffff;
    border: 1px solid #d0d0e0;
    border-radius: 8px;
}
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #d0d0e0;
    border-radius: 8px;
    padding: 8px;
}

QLabel#SectionTitle {
    font-size: 15px; font-weight: 600; color: #444466;
    padding-bottom: 4px; border-bottom: 1px solid #d0d0e0;
}
QLabel#InputLabel    { color: #666688; font-size: 12px; }
QLabel#SliderLabel   { color: #666688; font-size: 12px; }
QLabel#SliderValueLabel { color: #1a1a2e; font-size: 12px; font-weight: 600; }
QLabel#ResultCardLabel  { color: #888aaa; font-size: 11px; text-transform: uppercase; background: transparent; }
QLabel#ResultCardValue  { color: #1a1a2e; font-size: 18px; font-weight: 700; background: transparent; }
QLabel#ResultCardUnit   { color: #888aaa; font-size: 13px; margin-bottom: 4px; background: transparent; }
QLabel#ErrorLabel       { color: #e74c3c; font-size: 11px; }

QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #c0c0d8;
    border-radius: 5px;
    padding: 4px 8px;
    color: #1a1a2e;
}
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus { border-color: #6c5ce7; }
QDoubleSpinBox[state="error"] { border-color: #e74c3c; background-color: #fff0f0; }

QComboBox {
    background-color: #ffffff; border: 1px solid #c0c0d8;
    border-radius: 5px; padding: 4px 8px; color: #1a1a2e;
}
QComboBox:focus { border-color: #6c5ce7; }
QComboBox QAbstractItemView {
    background-color: #ffffff; border: 1px solid #c0c0d8;
    selection-background-color: #6c5ce7; color: #1a1a2e;
}

QPushButton {
    background-color: #6c5ce7; color: #ffffff;
    border: none; border-radius: 6px;
    padding: 7px 18px; font-weight: 600;
}
QPushButton:hover    { background-color: #7c6cf7; }
QPushButton:pressed  { background-color: #5a4ad0; }
QPushButton:disabled { background-color: #d0d0e0; color: #aaaacc; }
QPushButton#SecondaryButton {
    background-color: transparent; border: 1px solid #aaaacc; color: #444466;
}
QPushButton#SecondaryButton:hover { border-color: #6c5ce7; color: #1a1a2e; }

QSlider::groove:horizontal { height: 4px; background: #d0d0e0; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #6c5ce7; width: 14px; height: 14px;
    margin: -5px 0; border-radius: 7px;
}
QSlider::sub-page:horizontal { background: #6c5ce7; border-radius: 2px; }

QTableWidget { background-color: #ffffff; gridline-color: #d0d0e0; border: 1px solid #d0d0e0; border-radius: 6px; }
QHeaderView::section { background-color: #eeeef8; color: #444466; border: none; border-bottom: 1px solid #d0d0e0; padding: 6px; font-weight: 600; }

QMenuBar { background-color: #eeeef8; color: #444466; border-bottom: 1px solid #d0d0e0; }
QMenuBar::item:selected { background-color: #dcdcee; }
QMenu { background-color: #ffffff; border: 1px solid #c0c0d8; border-radius: 6px; }
QMenu::item:selected { background-color: #6c5ce7; color: #ffffff; }

QStatusBar { background-color: #eeeef8; color: #888aaa; border-top: 1px solid #d0d0e0; font-size: 12px; }
QGroupBox { border: 1px solid #d0d0e0; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { color: #666688; left: 10px; }
QCheckBox, QRadioButton { color: #1a1a2e; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid #aaaacc; border-radius: 3px; background: #ffffff;
}
QCheckBox::indicator:checked { background: #6c5ce7; border-color: #6c5ce7; }
"""
