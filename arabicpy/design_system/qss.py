"""Al-Baa Design System -- stylesheet builder.

Self-contained: standard library + PySide6 only, no `arabicpy` imports
(see `tokens.py` for why).
"""

from .tokens import RADIUS, SPACING, TYPOGRAPHY, Palette


def _font(style):
    return f"font-family: {style.family}; font-size: {style.size}px; font-weight: {style.weight};"


def build_app_stylesheet(palette: Palette, *, radius=RADIUS, spacing=SPACING, typography=TYPOGRAPHY, overrides: str = "") -> str:
    """Return the base Al-Baa QSS for `palette`, with `overrides` appended last.

    Qt resolves same-selector rules by order of appearance, so appending
    `overrides` after the base rules is enough for a project's own QSS to
    win without any extra specificity tricks -- this is the primary
    style-override mechanism for generated projects.
    """
    body = typography["body"]
    title = typography["title"]
    subtitle = typography["subtitle"]
    caption = typography["caption"]
    pad_sm = spacing["sm"]
    pad_md = spacing["md"]
    pad_lg = spacing["lg"]

    base = f"""
    QMainWindow, QDialog {{
        background: {palette.canvas};
        color: {palette.text};
        {_font(body)}
    }}

    QWidget {{
        color: {palette.text};
        {_font(body)}
    }}

    QToolBar {{
        background: {palette.surface};
        border: none;
        border-bottom: 1px solid {palette.border};
        padding: {spacing["xs"]}px {pad_sm}px;
        spacing: {spacing["xs"]}px;
    }}
    QToolBar QToolButton {{
        background: transparent;
        color: {palette.text};
        border: none;
        border-radius: {radius["sm"]}px;
        padding: {spacing["xs"]}px {pad_sm}px;
    }}
    QToolBar QToolButton:hover {{
        background: {palette.surface_alt};
    }}
    QToolBar QToolButton:pressed {{
        background: {palette.selection};
    }}

    QStatusBar {{
        background: {palette.surface};
        border-top: 1px solid {palette.border};
        color: {palette.text_muted};
        {_font(caption)}
    }}
    QStatusBar::item {{ border: none; }}

    QMenuBar {{
        background: {palette.surface};
        color: {palette.text};
        border-bottom: 1px solid {palette.border};
    }}
    QMenuBar::item {{
        background: transparent;
        padding: {spacing["xs"]}px {pad_sm}px;
    }}
    QMenuBar::item:selected {{
        background: {palette.surface_alt};
        border-radius: {radius["sm"]}px;
    }}
    QMenu {{
        background: {palette.surface};
        color: {palette.text};
        border: 1px solid {palette.border};
        border-radius: {radius["sm"]}px;
        padding: {spacing["xs"]}px;
    }}
    QMenu::item {{
        padding: {spacing["xs"]}px {pad_md}px;
        border-radius: {radius["sm"]}px;
    }}
    QMenu::item:selected {{
        background: {palette.accent};
        color: {palette.text_on_accent};
    }}

    #sidebar {{
        background: {palette.surface};
        border-right: 1px solid {palette.border};
    }}
    #sidebarTitle {{
        color: {palette.text_muted};
        {_font(caption)}
        padding: {pad_md}px {pad_md}px {spacing["xs"]}px {pad_md}px;
    }}
    QPushButton#sidebarButton {{
        background: transparent;
        color: {palette.text};
        text-align: left;
        border: none;
        border-radius: {radius["sm"]}px;
        padding: {pad_sm}px {pad_md}px;
        {_font(body)}
    }}
    QPushButton#sidebarButton:hover {{
        background: {palette.surface_alt};
    }}
    QPushButton#sidebarButton[active="true"] {{
        background: {palette.selection};
        color: {palette.text_on_accent};
    }}

    QPushButton#primaryButton {{
        background: {palette.accent};
        color: {palette.text_on_accent};
        border: none;
        border-radius: {radius["sm"]}px;
        padding: {pad_sm}px {pad_lg}px;
        {_font(body)}
    }}
    QPushButton#primaryButton:hover {{ background: {palette.accent_hover}; }}
    QPushButton#primaryButton:pressed {{ background: {palette.accent_pressed}; }}
    QPushButton#primaryButton:disabled {{ background: {palette.border}; color: {palette.text_dim}; }}

    QPushButton#secondaryButton {{
        background: transparent;
        color: {palette.text};
        border: 1px solid {palette.border};
        border-radius: {radius["sm"]}px;
        padding: {pad_sm}px {pad_lg}px;
        {_font(body)}
    }}
    QPushButton#secondaryButton:hover {{ background: {palette.surface_alt}; border-color: {palette.accent}; }}
    QPushButton#secondaryButton:disabled {{ color: {palette.text_dim}; }}

    QPushButton#dangerButton {{
        background: {palette.danger};
        color: {palette.text_on_accent};
        border: none;
        border-radius: {radius["sm"]}px;
        padding: {pad_sm}px {pad_lg}px;
        {_font(body)}
    }}
    QPushButton#dangerButton:hover {{ background: {palette.danger_hover}; }}

    QFrame#card {{
        background: {palette.surface};
        border: 1px solid {palette.border};
        border-radius: {radius["lg"]}px;
    }}
    QLabel#cardTitle {{
        color: {palette.text};
        {_font(subtitle)}
    }}

    QLabel#pageTitle {{
        color: {palette.text};
        {_font(title)}
        padding: {pad_lg}px {pad_lg}px {pad_sm}px {pad_lg}px;
    }}

    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
        background: {palette.surface};
        color: {palette.text};
        border: 1px solid {palette.border};
        border-radius: {radius["sm"]}px;
        padding: {spacing["xs"]}px {pad_sm}px;
        selection-background-color: {palette.selection};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border-color: {palette.accent};
    }}
    QLineEdit:disabled, QComboBox:disabled {{
        color: {palette.text_dim};
        background: {palette.surface_alt};
    }}

    QCheckBox, QRadioButton {{
        color: {palette.text};
        {_font(body)}
    }}

    QSplitter::handle {{
        background: {palette.border};
    }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    QStackedWidget {{
        background: {palette.canvas};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {palette.border};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {palette.text_dim};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """

    return f"{base}\n{overrides}\n"
