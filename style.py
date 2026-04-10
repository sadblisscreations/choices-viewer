DARK_BG  = "#1e1e2e"
PANEL_BG = "#181825"
BORDER   = "#313244"
TEXT     = "#cdd6f4"
SUBTLE   = "#585b70"
ACCENT   = "#89b4fa"
GREEN    = "#a6e3a1"

EMOTION_COLORS = {
    "NEUTRAL":   "#89b4fa",
    "HAPPY":     "#a6e3a1",
    "ANGRY":     "#f38ba8",
    "SAD":       "#74c7ec",
    "SURPRISED": "#fab387",
}

BASE_STYLE = f"""
QDialog, QMainWindow, QWidget {{ background: {DARK_BG}; color: {TEXT}; }}
QSplitter::handle              {{ background: {BORDER}; width: 1px; }}
QScrollArea                    {{ border: none; background: {PANEL_BG}; }}
QScrollBar:vertical            {{ background: {PANEL_BG}; width: 8px; border: none; }}
QScrollBar::handle:vertical    {{ background: #45475a; border-radius: 4px; min-height: 20px; }}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical  {{ height: 0; }}
QScrollBar:horizontal          {{ background: {PANEL_BG}; height: 8px; border: none; }}
QScrollBar::handle:horizontal  {{ background: #45475a; border-radius: 4px; min-width: 20px; }}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{ width: 0; }}
QListWidget                    {{
    background: {PANEL_BG}; border: 1px solid {BORDER};
    font-size: 12px; outline: none;
}}
QListWidget::item              {{ padding: 5px 10px; border-bottom: 1px solid {BORDER}; }}
QListWidget::item:selected     {{ background: {ACCENT}; color: {DARK_BG}; }}
QListWidget::item:hover        {{ background: #313244; }}
QLineEdit                      {{
    background: {PANEL_BG}; border: 1px solid #45475a;
    padding: 7px 10px; border-radius: 5px; font-size: 12px; color: {TEXT};
}}
QLineEdit:focus                {{ border-color: {ACCENT}; }}
QPushButton                    {{
    background: #313244; border: 1px solid #45475a; border-radius: 5px;
    padding: 6px 12px; font-size: 12px; color: {TEXT};
}}
QPushButton:hover              {{ background: #45475a; }}
QPushButton:pressed            {{ background: #585b70; }}
QPushButton:disabled           {{ color: {SUBTLE}; border-color: {BORDER}; }}
QPushButton#primary            {{
    background: {ACCENT}; border-color: {ACCENT}; color: {DARK_BG}; font-weight: bold;
}}
QPushButton#primary:hover      {{ background: #b9d1fb; }}
QPushButton#primary:disabled   {{ background: #313244; color: {SUBTLE}; border-color: {BORDER}; }}
QComboBox                      {{
    background: {PANEL_BG}; border: 1px solid #45475a; border-radius: 4px;
    padding: 5px 8px 5px 10px; font-size: 12px; color: {TEXT};
}}
QComboBox:hover                {{ border-color: {ACCENT}; }}
QComboBox:disabled             {{ color: {SUBTLE}; border-color: {BORDER}; }}
QComboBox::drop-down           {{ border: none; width: 22px; }}
QComboBox QAbstractItemView    {{
    background: #313244; border: 1px solid {BORDER}; outline: none;
    selection-background-color: {ACCENT}; selection-color: {DARK_BG}; color: {TEXT};
}}
QTabWidget::pane               {{ border: 1px solid {BORDER}; background: {DARK_BG}; }}
QTabBar::tab                   {{
    background: {PANEL_BG}; color: {SUBTLE}; padding: 9px 24px; font-size: 13px;
    border: 1px solid {BORDER}; border-bottom: none; margin-right: 2px;
    border-top-left-radius: 5px; border-top-right-radius: 5px;
}}
QTabBar::tab:selected          {{ background: {DARK_BG}; color: {TEXT}; border-bottom-color: {DARK_BG}; }}
QTabBar::tab:hover             {{ color: {TEXT}; background: #252535; }}
QSlider::groove:horizontal     {{ background: {BORDER}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal     {{ background: {ACCENT}; width: 14px; height: 14px; margin: -5px 0;
                                   border-radius: 7px; }}
QSlider::sub-page:horizontal   {{ background: {ACCENT}; height: 4px; border-radius: 2px; }}
QSlider:disabled::handle:horizontal {{ background: {SUBTLE}; }}
QSlider:disabled::sub-page:horizontal {{ background: {BORDER}; }}
"""
