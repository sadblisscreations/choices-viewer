# Dark Windows 98 theme

BG        = "#2b2b2b"
PANEL     = "#1e1e1e"
SURFACE   = "#363636"
LIGHT     = "#5c5c5c"
SHADOW    = "#1a1a1a"
DARK      = "#0a0a0a"
TEXT      = "#e0e0e0"
DISABLED  = "#808080"
SELECT    = "#004e8c"
SELECT_L  = "#3b8edb"
SELECT_D  = "#002a5c"
SELECT_TXT= "#ffffff"

EMOTION_COLORS = {
    "NEUTRAL":   "#4fc1ff",
    "HAPPY":     "#89d185",
    "ANGRY":     "#f44747",
    "SAD":       "#569cd6",
    "SURPRISED": "#ce9178",
}

_RAISED = (
    "border-top: 2px solid {light}; "
    "border-left: 2px solid {light}; "
    "border-right: 2px solid {dark}; "
    "border-bottom: 2px solid {dark};"
).format(light=LIGHT, dark=DARK)

_SUNKEN = (
    "border-top: 2px solid {dark}; "
    "border-left: 2px solid {dark}; "
    "border-right: 2px solid {light}; "
    "border-bottom: 2px solid {light};"
).format(dark=DARK, light=LIGHT)

BASE_STYLE = """
QWidget, QMainWindow, QDialog {{
    background: {bg};
    color: {text};
    font-family: "MS Shell Dlg", "Tahoma", sans-serif;
    font-size: 11px;
}}

QLabel {{
    background: transparent;
    color: {text};
}}

QPushButton {{
    background: {bg};
    color: {text};
    {_RAISED}
    padding: 3px 10px;
    font-size: 11px;
}}
QPushButton:pressed {{
    border-top: 2px solid {dark};
    border-left: 2px solid {dark};
    border-right: 2px solid {light};
    border-bottom: 2px solid {light};
    padding: 4px 9px 2px 11px;
}}
QPushButton:disabled {{
    color: {disabled};
}}
QPushButton:checked {{
    border-top: 2px solid {dark};
    border-left: 2px solid {dark};
    border-right: 2px solid {light};
    border-bottom: 2px solid {light};
    background: {bg};
}}
QPushButton#primary {{
    background: {select};
    color: {select_txt};
    border-top: 2px solid {select_l};
    border-left: 2px solid {select_l};
    border-right: 2px solid {select_d};
    border-bottom: 2px solid {select_d};
    font-weight: bold;
}}
QPushButton#primary:pressed {{
    border-top: 2px solid {select_d};
    border-left: 2px solid {select_d};
    border-right: 2px solid {select_l};
    border-bottom: 2px solid {select_l};
}}

QLineEdit {{
    background: {panel};
    color: {text};
    {_SUNKEN}
    padding: 3px 5px;
    font-size: 11px;
}}

QListWidget {{
    background: {panel};
    color: {text};
    {_SUNKEN}
    font-size: 11px;
    outline: none;
}}
QListWidget::item {{
    padding: 2px 5px;
    border: none;
}}
QListWidget::item:selected {{
    background: {select};
    color: {select_txt};
    border: 1px dotted {bg};
}}
QListWidget::item:hover {{
    background: {select};
    color: {select_txt};
}}

QComboBox {{
    background: {panel};
    color: {text};
    {_SUNKEN}
    padding: 2px 4px;
    font-size: 11px;
}}
QComboBox::drop-down {{
    background: {bg};
    {_RAISED}
    width: 18px;
    margin: 1px;
}}
QComboBox QAbstractItemView {{
    background: {panel};
    color: {text};
    {_RAISED}
    selection-background-color: {select};
    selection-color: {select_txt};
}}

QTabWidget::pane {{
    {_SUNKEN}
    background: {bg};
    top: -1px;
}}
QTabBar::tab {{
    background: {bg};
    color: {text};
    {_RAISED}
    padding: 4px 12px;
    font-size: 11px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {bg};
    border-bottom-color: {bg};
    margin-bottom: -2px;
}}
QTabBar::tab:hover {{
    background: {surface};
}}

QSlider::groove:horizontal {{
    background: {panel};
    {_SUNKEN}
    height: 8px;
}}
QSlider::handle:horizontal {{
    background: {bg};
    {_RAISED}
    width: 14px;
    height: 14px;
    margin: -4px 0;
}}
QSlider::sub-page:horizontal {{
    background: {select};
    height: 8px;
}}
QSlider::add-page:horizontal {{
    background: transparent;
    height: 8px;
}}

QScrollBar:vertical {{
    background: {panel};
    width: 16px;
    border: none;
    margin: 14px 0 14px 0;
}}
QScrollBar::handle:vertical {{
    background: {surface};
    {_RAISED}
    min-height: 24px;
    margin: 0 1px;
}}
QScrollBar::handle:vertical:hover {{
    background: {light};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    background: {bg};
    {_RAISED}
    height: 14px;
    subcontrol-origin: margin;
}}
QScrollBar::add-line:vertical {{ subcontrol-position: bottom; }}
QScrollBar::sub-line:vertical {{ subcontrol-position: top; }}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: {panel};
}}

QScrollBar:horizontal {{
    background: {panel};
    height: 16px;
    border: none;
    margin: 0 14px 0 14px;
}}
QScrollBar::handle:horizontal {{
    background: {surface};
    {_RAISED}
    min-width: 24px;
    margin: 1px 0;
}}
QScrollBar::handle:horizontal:hover {{
    background: {light};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    background: {bg};
    {_RAISED}
    width: 14px;
    subcontrol-origin: margin;
}}
QScrollBar::add-line:horizontal {{ subcontrol-position: right; }}
QScrollBar::sub-line:horizontal {{ subcontrol-position: left; }}
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: {panel};
}}

QGroupBox {{
    color: {text};
    font-weight: bold;
    font-size: 11px;
    {_RAISED}
    margin-top: 8px;
    padding-top: 6px;
    padding-bottom: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 3px;
    background: {bg};
}}

QSplitter::handle {{
    background: {bg};
    {_RAISED}
}}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:vertical   {{ height: 4px; }}

QScrollArea {{
    border: none;
    background: {bg};
}}

QMessageBox {{
    background: {bg};
}}
QMessageBox QLabel {{
    color: {text};
    font-size: 11px;
}}
QMessageBox QPushButton {{
    min-width: 60px;
}}
""".format(
    bg=BG,
    panel=PANEL,
    surface=SURFACE,
    light=LIGHT,
    shadow=SHADOW,
    dark=DARK,
    text=TEXT,
    disabled=DISABLED,
    select=SELECT,
    select_l=SELECT_L,
    select_d=SELECT_D,
    select_txt=SELECT_TXT,
    _RAISED=_RAISED,
    _SUNKEN=_SUNKEN,
)
