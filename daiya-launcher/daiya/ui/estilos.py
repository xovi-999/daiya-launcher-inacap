"""Hoja de estilos (QSS) de la interfaz: tema oscuro con acento cian."""

ACENTO = "#3BC9DB"
QSS = f"""
* {{ font-family: 'Segoe UI', 'DejaVu Sans', sans-serif; font-size: 13px; color: #E6E8EE; }}
QMainWindow, QDialog, QWidget#fondo {{ background: #17181D; }}
QWidget#lateral {{ background: #111216; border-right: 1px solid #262833; }}
QLabel#logo {{ font-size: 20px; font-weight: 700; color: {ACENTO}; padding: 6px 4px; }}
QLabel#titulo {{ font-size: 22px; font-weight: 700; }}
QLabel#subtitulo {{ color: #9AA0AE; }}
QLabel#cuenta {{ color: #9AA0AE; padding: 4px; }}
QListWidget {{ background: transparent; border: none; outline: 0; }}
QListWidget::item {{ padding: 10px 8px; border-radius: 8px; margin: 2px 0; }}
QListWidget::item:selected {{ background: #23303A; color: {ACENTO}; }}
QPushButton {{ background: #262833; border: 1px solid #333645; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {ACENTO}; }}
QPushButton#primario {{ background: {ACENTO}; color: #0E1A1D; font-weight: 700; border: none; padding: 9px 22px; }}
QFrame#zona {{ border: 2px dashed #3A3E4E; border-radius: 12px; background: #1C1E25; }}
QFrame#zona[activa="true"] {{ border-color: {ACENTO}; background: #1D2A30; }}
QLabel#zonaTexto {{ color: #9AA0AE; font-size: 14px; }}
QTabWidget::pane {{ border: 1px solid #262833; border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: #9AA0AE; }}
QTabBar::tab:selected {{ color: {ACENTO}; border-bottom: 2px solid {ACENTO}; }}
QTableWidget {{ background: #17181D; gridline-color: #262833; border: none; alternate-background-color: #1B1C22; }}
QHeaderView::section {{ background: #1C1E25; border: none; padding: 6px; color: #9AA0AE; }}
QPlainTextEdit {{ background: #0F1013; font-family: 'DejaVu Sans Mono', monospace; font-size: 12px; border: none; }}
QLabel#banner[nivel="ok"] {{ background: #173126; color: #7EE2A8; border-radius: 8px; padding: 8px 12px; }}
QLabel#banner[nivel="aviso"] {{ background: #352C14; color: #F5C66B; border-radius: 8px; padding: 8px 12px; }}
QLabel#banner[nivel="error"] {{ background: #3A1A1E; color: #FF8A8A; border-radius: 8px; padding: 8px 12px; }}
QLineEdit, QComboBox, QSpinBox {{ background: #1C1E25; border: 1px solid #333645; border-radius: 6px; padding: 5px; }}
"""
