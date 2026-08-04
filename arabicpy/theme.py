"""Al-Baa's design-token system: two themes (Dark, Light) built from one set
of tokens instead of hardcoded colors, plus small helpers for elevation
shadows, panel/tab motion, and optional frosted-glass panel surfaces.

Qt has no cross-widget backdrop blur, so "frosted glass" here is simulated:
translucent rgba surfaces layered over the window's own background, with a
soft light top-edge to read as a glass edge. Surfaces that must stay fully
opaque and high-contrast (the code editor, output/terminal text) set their
own solid background, which wins over the generic transparent rule.
"""

from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect

DARK = "dark"
LIGHT = "light"
MODES = (DARK, LIGHT)

RADIUS = {"sm": 6, "md": 10, "lg": 14, "xl": 20}

# (blur, x-offset, y-offset, alpha out of 255)
ELEVATION = {
    "sm": (18, 0, 4, 60),
    "md": (30, 0, 10, 85),
    "lg": (46, 0, 16, 110),
}


def rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha:.2f})"


@dataclass(frozen=True)
class Palette:
    mode: str
    canvas: str                 # flat window background
    surface: str                 # opaque, high-contrast (editor, flat fallback panels)
    surface_alt: str             # opaque secondary surface (headers/gutters, flat fallback)
    surface_glass_hex: str       # base color for translucent glass panels
    glass_alpha: float
    glass_alpha_strong: float    # composer/header — a touch more opaque for legibility
    border: str
    border_glass: str            # soft light rgba edge highlight
    text: str
    text_muted: str
    text_dim: str
    text_on_accent: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent2: str                  # Al-Baa's signature secondary sheen color
    success: str
    success_hover: str
    danger: str
    danger_hover: str
    shadow: str
    selection: str


PALETTES = {
    DARK: Palette(
        mode=DARK,
        canvas="#15171c",
        surface="#1b1e24",
        surface_alt="#20242c",
        surface_glass_hex="#242938",
        glass_alpha=0.72,
        glass_alpha_strong=0.86,
        border="#2c313c",
        border_glass="rgba(255,255,255,0.08)",
        text="#e7e9ef",
        text_muted="#a7adba",
        text_dim="#6b7280",
        text_on_accent="#ffffff",
        accent="#6C8CFF",
        accent_hover="#7f9bff",
        accent_pressed="#5877e0",
        accent2="#3DDBC0",
        success="#3ecf8e",
        success_hover="#4fe0a0",
        danger="#ef5350",
        danger_hover="#f4726f",
        shadow="#000000",
        selection="#33507a",
    ),
    LIGHT: Palette(
        mode=LIGHT,
        canvas="#eef1f6",
        surface="#ffffff",
        surface_alt="#f3f6f9",
        surface_glass_hex="#ffffff",
        glass_alpha=0.62,
        glass_alpha_strong=0.82,
        border="#dbe0e8",
        border_glass="rgba(17,24,39,0.06)",
        text="#191c22",
        text_muted="#5b6472",
        text_dim="#8891a1",
        text_on_accent="#ffffff",
        accent="#4C6FEF",
        accent_hover="#3d5ce0",
        accent_pressed="#3049b8",
        accent2="#14A98A",
        success="#1f9d63",
        success_hover="#249e6c",
        danger="#d1453b",
        danger_hover="#e0554b",
        shadow="#94a3b8",
        selection="#bcdcf7",
    ),
}


def glass_fill(palette, glass_effects, strong=False):
    """A translucent gradient sheen when glass effects are on, else a flat opaque fallback."""
    if not glass_effects:
        return palette.surface_alt
    alpha = palette.glass_alpha_strong if strong else palette.glass_alpha
    top_alpha = min(1.0, alpha + 0.14)
    base = palette.surface_glass_hex
    return (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {rgba(base, top_alpha)}, stop:1 {rgba(base, alpha)})"
    )


def flat_glass_fill(palette, glass_effects, strong=False):
    """A single flat translucent tone (no gradient) for chrome bars that sit
    edge-to-edge with other bars of very different heights -- glass_fill's
    gradient is normalized to each widget's own height, so a short bar and a
    tall bar using the "same" gradient still render visibly different tones
    where they touch. A flat fill has no such mismatch."""
    if not glass_effects:
        return palette.surface_alt
    alpha = palette.glass_alpha_strong if strong else palette.glass_alpha
    return rgba(palette.surface_glass_hex, alpha)


def apply_elevation(widget, palette, level="md", enabled=True):
    """Attach (or remove) a soft drop shadow for layered depth. Qt allows only one
    graphics effect per widget, so disabling clears it rather than zeroing it out."""
    if not enabled:
        widget.setGraphicsEffect(None)
        return
    blur, dx, dy, alpha = ELEVATION[level]
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(dx, dy)
    color = QColor(palette.shadow)
    color.setAlpha(alpha)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)


def fade_in(widget, duration=180):
    """A quick opacity fade-in, used for panel reveals and tab-switch content."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._albaa_fade_anim = anim
    anim.start()
    return anim


def animate_panel(widget, target_width, duration=180, splitter=None, on_finished=None):
    """Slide a panel open/closed instead of an instant show/hide.

    If `splitter` is given, the panel is a QSplitter child and its width is
    driven through splitter.setSizes() (a plain setFixedWidth would fight the
    splitter's own layout). Otherwise the widget is animated directly, which
    is correct for panels placed straight in a box layout (e.g. the AI panel).
    """
    previous = getattr(widget, "_albaa_panel_anim", None)
    if previous is not None:
        previous.stop()
    showing = target_width > 0

    # A drop-shadow/blur QGraphicsEffect forces Qt to re-render an offscreen
    # buffer on every single frame of the resize, which is what makes the
    # slide stutter. Drop it for the duration of the animation and put the
    # same effect instance back once the width settles.
    suspended_effect = widget.graphicsEffect()
    if suspended_effect is not None:
        widget.setGraphicsEffect(None)

    if splitter is not None:
        index = splitter.indexOf(widget)
        sizes = splitter.sizes()
        total = sum(sizes) or (target_width + 400)
        start_width = sizes[index] if widget.isVisible() else 0
        if showing:
            widget.show()

        def _apply(value, splitter=splitter, index=index, total=total):
            new_sizes = splitter.sizes()
            new_sizes[index] = value
            if len(new_sizes) == 2:
                new_sizes[1 - index] = max(0, total - value)
            splitter.setSizes(new_sizes)
    else:
        start_width = widget.width() if widget.isVisible() else 0
        if showing:
            # A hidden fixed-width panel must be pinned to its animation's
            # first frame before show(). Otherwise the surrounding layout can
            # expand it to all available space until valueChanged first runs.
            widget.setFixedWidth(start_width)
            widget.show()

        def _apply(value, widget=widget):
            widget.setFixedWidth(value)

    anim = QVariantAnimation(widget)
    anim.setDuration(duration)
    anim.setStartValue(start_width)
    anim.setEndValue(target_width)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.valueChanged.connect(_apply)

    def _finish():
        if not showing:
            widget.hide()
        elif splitter is None:
            widget.setFixedWidth(target_width)
        if suspended_effect is not None:
            widget.setGraphicsEffect(suspended_effect)
        if on_finished:
            on_finished()

    anim.finished.connect(_finish)
    widget._albaa_panel_anim = anim
    anim.start()
    return anim


def build_stylesheet(mode, glass_effects=True):
    palette = PALETTES.get(mode, PALETTES[DARK])
    p = palette

    window_bg = p.canvas
    title_bg = flat_glass_fill(p, glass_effects)
    sidebar_bg = glass_fill(p, glass_effects)
    ai_panel_bg = glass_fill(p, glass_effects)
    ai_header_bg = glass_fill(p, glass_effects, strong=True)
    ai_history_bg = glass_fill(p, glass_effects)
    ai_composer_bg = glass_fill(p, glass_effects, strong=True)
    tabbar_bg = glass_fill(p, glass_effects)

    close_hover_bg = p.danger

    return f"""
    QMainWindow {{ background: {window_bg}; }}
    QWidget {{ background: transparent; color: {p.text}; font-family: 'Tahoma'; font-size: 13px; }}
    #appCanvas {{ background: {window_bg}; }}

    #titleBar {{ background: {title_bg}; border-bottom: 1px solid {p.border_glass}; }}
    #titleLogo {{ background: {p.accent}; color: {p.text_on_accent}; border-radius: 6px; font-weight: 800; font-size: 12px; }}
    #windowButton, #closeButton {{ border: none; border-radius: 0; background: transparent; color: {p.text_muted}; font-size: 17px; }}
    #windowButton:hover {{ background: {p.border_glass}; color: {p.text}; }}
    #closeButton:hover {{ background: {close_hover_bg}; color: {p.text_on_accent}; }}

    #menuItem {{ background: transparent; border: none; padding: 3px 8px; color: {p.text}; font-size: 12px; }}
    #menuItem::menu-indicator {{ image: none; width: 0px; }}
    #menuItem:hover, #toolButton:hover, #themeButton:hover {{ background: {p.border_glass if glass_effects else p.border}; }}
    #menuItem:pressed, #toolButton:pressed, #themeButton:pressed {{ background: {rgba(p.accent, 0.22)}; }}
    #toolButton, #themeButton {{ background: transparent; border: none; border-radius: {RADIUS["sm"]}px; padding: 4px 8px; color: {p.text}; font-size: 12px; }}
    #titleSearchBox {{ background: {p.canvas}; color: {p.text}; border: 1px solid {p.border}; border-radius: {RADIUS["sm"]}px; padding: 3px 10px; font-size: 12px; }}
    #titleSearchBox:hover {{ border: 1px solid {p.border_glass if glass_effects else p.text_dim}; }}
    #titleSearchBox:focus {{ border: 1px solid {p.accent}; }}

    QMenu {{ background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.border}; border-radius: {RADIUS["md"]}px; padding: 4px; }}
    QMenu::item {{ background: transparent; padding: 7px 28px 7px 14px; border-radius: {RADIUS["sm"]}px; margin: 1px 2px; }}
    QMenu::item:selected {{ background: {p.accent}; color: {p.text_on_accent}; }}
    QMenu::item:disabled {{ color: {p.text_dim}; }}
    QMenu::separator {{ height: 1px; background: {p.border}; margin: 4px 10px; }}

    #runButton {{ background: {p.success}; color: {p.text_on_accent}; border: none; border-radius: {RADIUS["sm"]}px; padding: 4px 12px; font-weight: 600; font-size: 12px; }}
    #runButton:hover {{ background: {p.success_hover}; }}
    #aiButton {{ background: {p.accent}; color: {p.text_on_accent}; border: none; border-radius: {RADIUS["sm"]}px; padding: 4px 10px; font-weight: 600; font-size: 12px; }}
    #aiButton:hover {{ background: {p.accent_hover}; }}
    #aiButton:pressed {{ background: {p.accent_pressed}; }}

    #aiChatPanel {{ background: {ai_panel_bg}; border-left: 1px solid {p.border_glass}; }}
    #aiChatHeader {{ background: {ai_header_bg}; border-bottom: 1px solid {p.border_glass}; border-radius: 0; }}
    #aiChatAvatar {{ background: {p.accent}; color: {p.text_on_accent}; border-radius: 6px; font-size: 13px; font-weight: 800; }}
    #aiChatTitle {{ color: {p.text}; font-size: 13px; font-weight: 700; padding: 0; background: transparent; }}
    #aiChatSubtitle {{ color: {p.text_muted}; font-size: 10px; background: transparent; }}
    #aiChatHistory {{ background: {ai_history_bg}; border: 1px solid {p.border_glass}; border-radius: {RADIUS["lg"]}px; color: {p.text}; padding: 5px; }}
    #aiComposer {{ background: {ai_composer_bg}; border: 1px solid {p.border_glass}; border-radius: {RADIUS["xl"] - 2}px; }}
    #aiChatInput {{ background: transparent; color: {p.text}; border: none; padding: 2px; }}
    #aiThinking {{ color: {p.text_muted}; padding: 2px 8px; font-size: 11px; }}
    #aiAttachButton {{ background: transparent; color: {p.text_muted}; border: 1px solid {p.border}; border-radius: 13px; font-size: 15px; font-weight: 700; padding: 0; outline: none; }}
    #aiAttachButton:hover, #aiAttachButton:pressed {{ background: {p.border_glass}; color: {p.text}; border: 1px solid {p.border}; outline: none; }}
    #aiAttachButton:focus {{ border: 1px solid {p.border}; outline: none; }}
    #aiSendButton {{ background: {p.accent}; color: {p.text_on_accent}; border: none; border-radius: 15px; font-size: 14px; font-weight: 700; outline: none; }}
    #aiSendButton:hover {{ background: {p.accent_hover}; }}
    #aiSendButton:pressed, #aiSendButton:focus {{ outline: none; }}
    #aiSendButton:disabled {{ background: {rgba(p.accent, 0.35)}; }}
    #aiCloseButton {{ background: transparent; color: {p.text}; border: none; border-radius: {RADIUS["sm"]}px; font-size: 15px; padding: 5px 9px; }}
    #aiCloseButton:hover {{ background: {p.border_glass}; }}

    #activityBar {{ background: {title_bg}; min-width: 48px; max-width: 48px; }}
    #activityButton {{ background: transparent; color: {p.text_muted}; border: none; border-radius: 0; font-size: 20px; padding: 11px; }}
    #activityButton:hover {{ background: {p.border_glass if glass_effects else p.border}; color: {p.text}; }}
    #activityButton:checked {{ background: transparent; border-left: 2px solid {p.accent}; color: {p.text}; }}
    #activityButton:checked:hover {{ background: {p.border_glass if glass_effects else p.border}; }}
    #settingsButton {{ background: transparent; color: {p.text}; border: none; font-size: 19px; padding: 11px; }}
    #settingsButton:hover {{ background: {p.border_glass if glass_effects else p.border}; }}

    #sideBar {{ background: {sidebar_bg}; border-right: 1px solid {p.border_glass}; }}
    #panelTitle {{ color: {p.text_muted}; font-size: 11px; font-weight: 600; padding: 12px 14px 5px; background: transparent; }}
    #fileList {{ background: transparent; border: none; outline: none; color: {p.text}; padding: 2px 6px; }}
    #fileList::item {{ padding: 6px 8px; border-radius: {RADIUS["sm"]}px; }}
    #fileList::item:selected {{ background: {p.border_glass if glass_effects else p.border}; color: {p.text}; }}
    #fileTree {{ background: transparent; border: none; outline: none; color: {p.text}; padding: 2px 6px; }}
    #fileTree::item {{ padding: 4px 6px; border-radius: {RADIUS["sm"]}px; }}
    #fileTree::item:selected {{ background: {p.border_glass if glass_effects else p.border}; color: {p.text}; }}
    #newFilePanel {{ background: transparent; }}
    #languageCard {{ background: transparent; border: none; border-bottom: 1px solid {p.border}; }}
    #languageCard:hover {{ background: {p.border_glass if glass_effects else p.border}; }}
    #languageCardTitle {{ color: {p.text}; font-weight: 600; font-size: 13px; background: transparent; }}
    #languageCardDescription {{ color: {p.text_muted}; font-size: 11px; background: transparent; }}

    #tabBar {{ background: {tabbar_bg}; border-bottom: 1px solid {p.border}; }}
    #activeTab {{ background: {p.surface}; color: {p.text}; border-top: 1px solid {p.accent}; padding: 10px 16px; }}
    #pythonTabSpacer {{ background: {p.surface}; border-bottom: 1px solid {p.surface}; }}
    #codeEditor {{ background: {p.surface}; color: {p.text}; border: none; selection-background-color: {p.selection}; font-family: 'Segoe UI'; font-size: 15px; }}
    #codePaneTitle {{ background: {p.surface_alt}; color: {p.text}; border-bottom: 1px solid {p.border}; padding: 4px 12px; font-weight: 600; }}
    #pythonPreview {{ background: {p.surface}; color: {p.text}; border: none; selection-background-color: {p.selection}; font-family: 'Segoe UI'; font-size: 15px; }}

    #outputHeader {{ background: {p.surface_alt}; border-top: 1px solid {p.border}; }}
    #outputTabButton {{ background: transparent; border: none; border-bottom: 2px solid transparent; color: {p.text_muted}; font-weight: 600; font-size: 11px; padding: 7px 12px; }}
    #outputTabButton:hover {{ color: {p.text}; }}
    #outputTabButton:checked {{ color: {p.text}; border-bottom: 2px solid {p.accent}; }}
    #output {{ background: {p.surface}; color: {p.text}; border: none; font-family: 'Tahoma'; font-size: 14px; padding: 9px; }}
    #terminalPanel {{ background: {p.surface}; }}
    #terminalOutput {{ background: {p.surface}; color: {p.text}; border: none; padding: 9px; }}
    #terminalInputRow {{ background: {p.surface}; }}
    #terminalPrompt {{ color: {p.accent2}; font-weight: 700; font-family: 'Consolas'; background: transparent; }}
    #terminalInput {{ background: transparent; color: {p.text}; border: none; padding: 4px 0; }}

    #statusBar {{ background: {p.accent}; color: {p.text_on_accent}; }}
    #statusLabel {{ background: transparent; color: {p.text_on_accent}; padding: 3px 10px; font-size: 12px; }}

    #androidDesigner {{ background: {p.canvas}; }}
    #designerPanel {{ background: {p.surface_alt}; border: none; }}
    #designerTitle {{ color: {p.text}; font-weight: 600; padding: 8px; background: transparent; }}
    #designerTool {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: {RADIUS["sm"]}px; padding: 8px; text-align: right; }}
    #designerTool:hover {{ background: {p.border_glass if glass_effects else p.border}; border-color: {p.accent}; }}
    #designerCanvas {{ background: {p.canvas}; border: none; }}
    #canvasFrame {{ background: #fafafa; border: 1px solid {p.border}; }}
    #canvasTitle {{ background: #202124; color: white; padding: 10px; font-weight: 600; }}
    #canvasNavigation {{ background: #050505; border-top: 1px solid #2f3336; min-height: 48px; max-height: 48px; }}
    #canvasNavigationButton {{ background: transparent; color: #f2f2f2; border: none; padding: 6px 2px; font-size: 10px; }}
    #canvasNavigationButton:hover {{ background: #16181c; border-radius: 12px; }}
    #designerItem {{ background: transparent; border: 2px solid transparent; border-radius: {RADIUS["sm"]}px; }}
    #designerItem[selected="true"] {{ border-color: {p.accent}; background: {rgba(p.accent, 0.12)}; }}
    #designerItem QLabel, #designerItem QLineEdit, #designerItem QPushButton {{ color: #202124; background: #ffffff; border: 1px solid #bdbdbd; border-radius: {RADIUS["sm"]}px; padding: 8px; }}
    #designerItem QPushButton {{ background: #1976d2; color: white; }}
    #designerDelete {{ background: {p.danger}; color: {p.text_on_accent}; border: none; border-radius: {RADIUS["sm"]}px; padding: 7px; }}

    QSplitter::handle {{ background: {p.border}; }}
    QSplitter::handle:hover {{ background: {p.accent}; }}
    QTabWidget QTabBar {{ background: {p.surface_alt}; }}
    QTabWidget QTabBar::tab {{ background: {p.surface_alt}; color: {p.text_muted}; border: none; border-top: 2px solid transparent; padding: 5px 12px; font-size: 12px; }}
    QTabWidget QTabBar::tab:selected {{ background: {p.surface}; color: {p.text}; border-top: 2px solid {p.accent}; }}
    QTabWidget QTabBar::tab:hover {{ background: {p.border_glass if glass_effects else p.border}; color: {p.text}; }}
    #tabCloseButton {{ background: transparent; color: {p.text_muted}; border: none; border-radius: {RADIUS["sm"]}px; font-size: 13px; font-weight: 600; padding: 0; }}
    #tabCloseButton:hover {{ background: {p.border_glass if glass_effects else p.border}; color: {p.text}; }}

    #ragLibraryPage {{ background: {p.surface}; }}
    #ragLibraryHeader {{ color: {p.text}; font-size: 15px; font-weight: 700; padding: 4px 2px; background: transparent; }}
    #ragLibraryCount {{ color: {p.text_muted}; font-size: 12px; padding: 4px 2px; background: transparent; }}
    #ragLibraryList {{ background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: {RADIUS["md"]}px; outline: none; color: {p.text}; padding: 4px; }}
    #ragLibraryList::item {{ padding: 10px; border-radius: {RADIUS["sm"]}px; margin: 2px 0; }}
    #ragLibraryList::item:selected {{ background: {p.selection}; color: {p.text}; }}
    #ragLibraryList::item:hover {{ background: {p.border_glass if glass_effects else p.border}; }}
    #ragLibraryEmpty {{ color: {p.text_muted}; font-size: 13px; background: transparent; }}
    #ragRemoveButton {{ background: transparent; color: {p.danger}; border: 1px solid {rgba(p.danger, 0.4)}; border-radius: {RADIUS["sm"]}px; padding: 6px 12px; }}
    #ragRemoveButton:hover {{ background: {rgba(p.danger, 0.16)}; color: {p.danger_hover}; border-color: {p.danger}; }}
    #ragRemoveButton:disabled {{ color: {p.text_dim}; border-color: {p.border}; }}
    """
