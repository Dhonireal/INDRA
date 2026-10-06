"""
VisionPilot UI Design Tokens.

Defines typography, color palette, dimensions, and spacing based on docs/design.md.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ColorTokens:
    # Surface & Backgrounds
    bg_primary: str = "#FFFFFF"
    bg_secondary: str = "#F8FAFC"
    bg_tertiary: str = "#F1F5F9"
    bg_card: str = "#FFFFFF"
    bg_input: str = "#FFFFFF"
    bg_badge: str = "#F1F5F9"

    # Borders
    border_default: str = "#E2E8F0"
    border_focus: str = "#2563EB"
    border_subtle: str = "#F1F5F9"
    border_card: str = "#E2E8F0"

    # Brand & Action
    brand_navy: str = "#0F172A"
    accent_blue: str = "#1E40AF"
    accent_blue_hover: str = "#1D4ED8"
    accent_cyan: str = "#0284C7"
    accent_cyan_hover: str = "#0369A1"

    # Text
    text_primary: str = "#0F172A"
    text_secondary: str = "#475569"
    text_muted: str = "#94A3B8"
    text_on_accent: str = "#FFFFFF"

    # Status Indicators
    status_ready: str = "#10B981"
    status_listening: str = "#0284C7"
    status_processing: str = "#F59E0B"
    status_executing: str = "#2563EB"
    status_verifying: str = "#8B5CF6"
    status_success: str = "#10B981"
    status_error: str = "#EF4444"
    status_warning: str = "#F59E0B"


@dataclass(frozen=True)
class TypographyTokens:
    font_family_main: str = '"Segoe UI", "Segoe UI Variable", -apple-system, sans-serif'
    font_family_mono: str = '"Cascadia Code", "Consolas", monospace'

    size_title: int = 24
    size_subtitle: int = 15
    size_body: int = 13
    size_caption: int = 11
    size_badge: int = 11
    size_mono: int = 12

    weight_bold: int = 700
    weight_semibold: int = 600
    weight_medium: int = 500
    weight_regular: int = 400


@dataclass(frozen=True)
class SpacingTokens:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20
    xxl: int = 24
    xxxl: int = 32

    radius_sm: int = 6
    radius_md = 10
    radius_lg = 14
    radius_pill = 9999


colors = ColorTokens()
typography = TypographyTokens()
spacing = SpacingTokens()
