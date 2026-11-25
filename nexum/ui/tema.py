"""Tema visual compacto, limpio y con modo oscuro."""
from PySide6.QtGui import QColor, QPalette

ACENTO = "#2563eb"


def aplicar(app, oscuro: bool = False):
    app.setStyle("Fusion")
    p = QPalette()
    if oscuro:
        fondo, base, texto, borde, alt = "#1e2127", "#262a32", "#e6e9ef", "#3a3f4a", "#2c313a"
    else:
        fondo, base, texto, borde, alt = "#f4f5f7", "#ffffff", "#1f2430", "#d5d9e0", "#f0f2f6"
    for rol, col in ((QPalette.Window, fondo), (QPalette.Base, base), (QPalette.AlternateBase, alt),
                     (QPalette.Text, texto), (QPalette.WindowText, texto), (QPalette.ButtonText, texto),
                     (QPalette.Button, base), (QPalette.ToolTipBase, base), (QPalette.ToolTipText, texto),
                     (QPalette.Highlight, ACENTO), (QPalette.HighlightedText, "#ffffff")):
        p.setColor(rol, QColor(col))
    app.setPalette(p)
    app.setStyleSheet(f"""
    * {{ font-size: 10pt; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {{
        padding: 3px 6px; border: 1px solid {borde}; border-radius: 4px; background: {base}; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
        border: 1px solid {ACENTO}; }}
    QPushButton {{ padding: 5px 12px; border: 1px solid {borde}; border-radius: 4px; background: {base}; }}
    QPushButton:hover {{ border-color: {ACENTO}; }}
    QPushButton:disabled {{ color: #9aa0ab; }}
    QPushButton#primario {{ background: {ACENTO}; color: white; border: none; font-weight: 600; }}
    QPushButton#primario:disabled {{ background: #9db7ee; }}
    QTableWidget, QTreeWidget, QListWidget {{ border: 1px solid {borde}; gridline-color: {borde}; alternate-background-color: {alt}; }}
    QHeaderView::section {{ background: {alt}; padding: 4px 6px; border: none; border-bottom: 1px solid {borde}; font-weight: 600; }}
    QGroupBox {{ border: 1px solid {borde}; border-radius: 6px; margin-top: 10px; padding-top: 8px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; font-weight: 600; }}
    QTabBar::tab {{ padding: 6px 14px; border: 1px solid {borde}; border-bottom: none; background: {alt}; margin-right: 2px;
                    border-top-left-radius: 4px; border-top-right-radius: 4px; }}
    QTabBar::tab:selected {{ background: {base}; font-weight: 600; }}
    QLabel#total {{ font-size: 28pt; font-weight: 700; color: {ACENTO}; }}
    QLabel#ok {{ color: #16a34a; font-weight: 600; }}
    QLabel#error {{ color: #dc2626; font-weight: 600; }}
    QLabel#suave {{ color: #8a90a0; }}
    QStatusBar {{ border-top: 1px solid {borde}; }}
    """)
