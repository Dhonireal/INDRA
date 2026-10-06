"""
VisionPilot Qt Style Sheets (QSS) Theme Generator.

Implements clean, professional, AI-desktop assistant styling based on design.md
using the design tokens.
"""
from app.ui.styles.tokens import colors, typography, spacing


def get_stylesheet() -> str:
    """Returns the complete global application stylesheet."""
    return f"""
    /* Global Window & Typography */
    QMainWindow, QWidget {{
        background-color: {colors.bg_primary};
        color: {colors.text_primary};
        font-family: {typography.font_family_main};
        font-size: {typography.size_body}px;
    }}

    /* Card Panels */
    QFrame[class="card"] {{
        background-color: {colors.bg_card};
        border: 1px solid {colors.border_card};
        border-radius: {spacing.radius_md}px;
        padding: {spacing.lg}px;
    }}

    QFrame[class="card-subtle"] {{
        background-color: {colors.bg_secondary};
        border: 1px solid {colors.border_default};
        border-radius: {spacing.radius_md}px;
        padding: {spacing.md}px;
    }}

    /* Headers & Status Bar */
    QFrame[class="header"] {{
        background-color: {colors.bg_primary};
        border-bottom: 1px solid {colors.border_default};
        padding: {spacing.sm}px {spacing.lg}px;
    }}

    QFrame[class="footer"] {{
        background-color: {colors.bg_secondary};
        border-top: 1px solid {colors.border_default};
        padding: {spacing.xs}px {spacing.lg}px;
    }}

    /* Buttons */
    QPushButton {{
        font-weight: {typography.weight_medium};
        font-size: {typography.size_body}px;
        border-radius: {spacing.radius_sm}px;
        padding: 8px 16px;
        border: 1px solid {colors.border_default};
        background-color: {colors.bg_primary};
        color: {colors.text_primary};
    }}

    QPushButton:hover {{
        background-color: {colors.bg_tertiary};
        border-color: {colors.accent_blue};
    }}

    QPushButton:pressed {{
        background-color: {colors.border_default};
    }}

    QPushButton:disabled {{
        background-color: {colors.bg_tertiary};
        color: {colors.text_muted};
        border-color: {colors.border_subtle};
    }}

    /* Primary Action Button */
    QPushButton[class="primary"] {{
        background-color: {colors.accent_blue};
        color: {colors.text_on_accent};
        border: 1px solid {colors.accent_blue};
        font-weight: {typography.weight_semibold};
    }}

    QPushButton[class="primary"]:hover {{
        background-color: {colors.accent_blue_hover};
        border-color: {colors.accent_blue_hover};
    }}

    QPushButton[class="primary"]:disabled {{
        background-color: #93C5FD;
        border-color: #93C5FD;
        color: #FFFFFF;
    }}

    /* Subtle/Icon Button */
    QPushButton[class="icon-btn"] {{
        background-color: transparent;
        border: 1px solid transparent;
        padding: 6px;
        border-radius: {spacing.radius_sm}px;
    }}

    QPushButton[class="icon-btn"]:hover {{
        background-color: {colors.bg_tertiary};
        border-color: {colors.border_default};
    }}

    /* Microphone Button */
    QPushButton[class="mic-btn"] {{
        background-color: {colors.bg_secondary};
        border: 1px solid {colors.border_default};
        border-radius: 20px;
        min-width: 40px;
        max-width: 40px;
        min-height: 40px;
        max-height: 40px;
        font-size: 16px;
    }}

    QPushButton[class="mic-btn"]:hover {{
        background-color: {colors.bg_tertiary};
        border-color: {colors.accent_cyan};
    }}

    /* Input Fields */
    QTextEdit, QLineEdit {{
        background-color: {colors.bg_input};
        color: {colors.text_primary};
        border: 1.5px solid {colors.border_default};
        border-radius: {spacing.radius_md}px;
        padding: 10px 14px;
        font-size: 14px;
        selection-background-color: {colors.accent_blue};
        selection-color: {colors.text_on_accent};
    }}

    QTextEdit:focus, QLineEdit:focus {{
        border-color: {colors.border_focus};
    }}

    QTextEdit:disabled, QLineEdit:disabled {{
        background-color: {colors.bg_tertiary};
        color: {colors.text_muted};
    }}

    /* Progress Bar */
    QProgressBar {{
        border: 1px solid {colors.border_default};
        border-radius: 4px;
        text-align: center;
        background-color: {colors.bg_tertiary};
        height: 8px;
        font-size: 9px;
        color: transparent;
    }}

    QProgressBar::chunk {{
        background-color: {colors.accent_cyan};
        border-radius: 3px;
    }}

    /* Status Pill / Badges */
    QLabel[class="badge"] {{
        background-color: {colors.bg_badge};
        color: {colors.text_secondary};
        border-radius: {spacing.radius_sm}px;
        padding: 3px 8px;
        font-size: {typography.size_badge}px;
        font-weight: {typography.weight_medium};
    }}

    QLabel[class="badge-ready"] {{
        background-color: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }}

    QLabel[class="badge-active"] {{
        background-color: #EFF6FF;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }}

    QLabel[class="badge-warning"] {{
        background-color: #FFFBEB;
        color: #92400E;
        border: 1px solid #FDE68A;
    }}

    QLabel[class="badge-error"] {{
        background-color: #FEF2F2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {colors.text_muted};
        min-height: 20px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {colors.text_secondary};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Tab Widget in Settings */
    QTabWidget::pane {{
        border: 1px solid {colors.border_default};
        background: {colors.bg_primary};
        border-radius: {spacing.radius_md}px;
        top: -1px;
    }}

    QTabBar::tab {{
        background: {colors.bg_secondary};
        border: 1px solid {colors.border_default};
        border-bottom-color: {colors.border_default};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 16px;
        margin-right: 4px;
        font-weight: {typography.weight_medium};
        color: {colors.text_secondary};
    }}

    QTabBar::tab:selected {{
        background: {colors.bg_primary};
        border-color: {colors.border_default};
        border-bottom-color: {colors.bg_primary};
        color: {colors.accent_blue};
    }}

    QTabBar::tab:hover:!selected {{
        background: {colors.bg_tertiary};
    }}
    """
