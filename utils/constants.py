# --- Design System Constants ---

# 1. Color Palette
# Naming convention: ROLE_COLOR_STATE
# Example: BUTTON_PRIMARY_HOVER

# Backgrounds
COLOR_BACKGROUND_PRIMARY = "#242729"  # Main window background
COLOR_BACKGROUND_SECONDARY = "#2B2D30"  # Card backgrounds
COLOR_BACKGROUND_TERTIARY = "#36393E"   # Input fields, dropdowns

# Text
COLOR_TEXT_PRIMARY = "#F0F0F0"        # Main text, titles
COLOR_TEXT_SECONDARY = "#A0A0A0"      # Descriptions, subtitles, placeholders
COLOR_TEXT_DISABLED = "#6A6E73"       # Disabled text

# Accent Colors (for buttons, links, and highlights)
COLOR_ACCENT_PRIMARY = "#5865F2"      # Main interactive color (Discord-like blue)
COLOR_ACCENT_PRIMARY_HOVER = "#4F5BD4"
COLOR_ACCENT_PRIMARY_DISABLED = "#474F78"

# Semantic Colors (for status indicators, notifications)
COLOR_SUCCESS = "#3BA55D"
COLOR_WARNING = "#FAA81A"
COLOR_ERROR = "#ED4245"

# Borders and Dividers
COLOR_BORDER = "#40444B"

# --- 2. Typography ---
# Using Segoe UI for a modern, clean look.
# Naming convention: FONT_ROLE_SIZE
FONT_TITLE = ('Segoe UI Semibold', 24)
FONT_HEADING = ('Segoe UI Semibold', 16)
FONT_SUBHEADING = ('Segoe UI', 14)
FONT_BODY = ('Segoe UI', 12)
FONT_BUTTON = ('Segoe UI Semibold', 12)
FONT_CONSOLE = ('Consolas', 11)

# --- 3. Sizing and Spacing ---
# Using a base unit of 8px for consistent spacing.
# Naming convention: SIZE_ROLE_UNIT
SIZE_PADDING_XL = 20
SIZE_PADDING_L = 15
SIZE_PADDING_M = 10
SIZE_PADDING_S = 5

SIZE_CORNER_RADIUS = 8
SIZE_BORDER_WIDTH = 1

# --- Legacy Constants (for compatibility during refactoring) ---
# These can be removed once the new system is fully implemented.
PRIMARY_BG = COLOR_BACKGROUND_PRIMARY
SECONDARY_BG = COLOR_BACKGROUND_SECONDARY
TERTIARY_BG = COLOR_BACKGROUND_TERTIARY
ACCENT_COLOR = COLOR_ACCENT_PRIMARY
ACCENT_HOVER = COLOR_ACCENT_PRIMARY_HOVER
SUCCESS_COLOR = COLOR_SUCCESS
TEXT_PRIMARY = COLOR_TEXT_PRIMARY
TEXT_SECONDARY = COLOR_TEXT_SECONDARY
ERROR_FG_CUSTOM = COLOR_ERROR
WARNING_FG_CUSTOM = COLOR_WARNING

FONT_UI_NORMAL = FONT_BODY
FONT_UI_BOLD = ('Segoe UI Semibold', 13) # Kept for specific cases if needed
FONT_UI_HEADER = FONT_HEADING
FONT_UI_TITLE = FONT_TITLE
FONT_CONSOLE_CUSTOM = FONT_CONSOLE
