"""
UI styles and theme configuration for the pharmacy system.
Defines colors, fonts, and ttk style configurations.
"""
from tkinter import ttk
from raspberry_app.config import config


# Color palette
COLORS = {
    'primary': '#2E86AB',      # Blue
    'secondary': '#A23B72',    # Purple
    'success': '#06A77D',      # Green
    'warning': '#F18F01',      # Orange
    'danger': '#C73E1D',       # Red
    'light': '#F4F4F4',        # Light gray
    'dark': '#2D2D2D',         # Dark gray
    'white': '#FFFFFF',
    'border': '#CCCCCC',

    # Priority colors
    'high_priority': '#C73E1D',
    'medium_priority': '#F18F01',
    'low_priority': '#06A77D',

    # State colors
    'loading': '#2E86AB',
    'error': '#C73E1D',
    'empty': '#999999',
}


def configure_styles():
    """
    Configure global ttk styles for the application.

    Call this once at application startup before creating any widgets.

    Example:
        >>> import tkinter as tk
        >>> from raspberry_app.ui.styles import configure_styles
        >>> root = tk.Tk()
        >>> configure_styles()
    """
    style = ttk.Style()

    # Use clam theme as base
    style.theme_use('clam')

    # Configure default ttk widgets
    _configure_default_styles(style)

    # Configure custom styles
    _configure_cart_styles(style)
    _configure_recommendation_styles(style)
    _configure_button_styles(style)
    _configure_label_styles(style)


def _configure_default_styles(style: ttk.Style):
    """Configure base ttk widget styles."""

    # Default font
    default_font = (config.FONT_FAMILY, config.FONT_SIZE)

    # TFrame
    style.configure('TFrame',
                   background=COLORS['white'])

    # TLabel
    style.configure('TLabel',
                   background=COLORS['white'],
                   foreground=COLORS['dark'],
                   font=default_font)

    # TButton
    style.configure('TButton',
                   font=default_font,
                   padding=10)

    # TEntry
    style.configure('TEntry',
                   fieldbackground=COLORS['white'],
                   font=default_font)


def _configure_cart_styles(style: ttk.Style):
    """Configure styles for cart widget."""

    # Treeview for cart items
    style.configure('Cart.Treeview',
                   background=COLORS['white'],
                   foreground=COLORS['dark'],
                   fieldbackground=COLORS['white'],
                   font=(config.FONT_FAMILY, config.FONT_SIZE),
                   rowheight=35)

    style.configure('Cart.Treeview.Heading',
                   background=COLORS['primary'],
                   foreground=COLORS['white'],
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                   relief='flat')

    # Map for alternating row colors
    style.map('Cart.Treeview',
             background=[('selected', COLORS['primary'])],
             foreground=[('selected', COLORS['white'])])


def _configure_recommendation_styles(style: ttk.Style):
    """Configure styles for recommendation widgets."""

    # Base recommendation frame
    style.configure('Recommendation.TFrame',
                   background=COLORS['light'],
                   borderwidth=1,
                   relief='solid')

    # High priority recommendation
    style.configure('HighPriority.TFrame',
                   background='#FFE5E5',  # Light red
                   borderwidth=2,
                   relief='solid')

    # Medium priority recommendation
    style.configure('MediumPriority.TFrame',
                   background='#FFF4E5',  # Light orange
                   borderwidth=2,
                   relief='solid')

    # Low priority recommendation
    style.configure('LowPriority.TFrame',
                   background='#E5F9F0',  # Light green
                   borderwidth=2,
                   relief='solid')

    # Recommendation title
    style.configure('RecommendationTitle.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE + 2, 'bold'),
                   background=COLORS['light'])

    # Recommendation text
    style.configure('RecommendationText.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE),
                   background=COLORS['light'])


def _configure_button_styles(style: ttk.Style):
    """Configure button styles."""

    # Primary button
    style.configure('Primary.TButton',
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                   background=COLORS['primary'],
                   foreground=COLORS['white'],
                   padding=10)

    style.map('Primary.TButton',
             background=[('active', '#1f5c7a'), ('pressed', '#164560')])

    # Success button
    style.configure('Success.TButton',
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                   background=COLORS['success'],
                   foreground=COLORS['white'],
                   padding=10)

    style.map('Success.TButton',
             background=[('active', '#058661'), ('pressed', '#047550')])

    # Danger button
    style.configure('Danger.TButton',
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                   background=COLORS['danger'],
                   foreground=COLORS['white'],
                   padding=10)

    style.map('Danger.TButton',
             background=[('active', '#a33118'), ('pressed', '#8a2914')])


def _configure_label_styles(style: ttk.Style):
    """Configure label styles."""

    # Title label
    style.configure('Title.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE + 6, 'bold'),
                   foreground=COLORS['primary'],
                   background=COLORS['white'])

    # Subtitle label
    style.configure('Subtitle.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE + 2, 'bold'),
                   foreground=COLORS['dark'],
                   background=COLORS['white'])

    # Total label
    style.configure('Total.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE + 4, 'bold'),
                   foreground=COLORS['success'],
                   background=COLORS['white'])

    # Priority labels
    style.configure('HighPriority.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                   foreground=COLORS['high_priority'],
                   background=COLORS['light'])

    style.configure('MediumPriority.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                   foreground=COLORS['medium_priority'],
                   background=COLORS['light'])

    style.configure('LowPriority.TLabel',
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                   foreground=COLORS['low_priority'],
                   background=COLORS['light'])

    # Status labels
    style.configure('Loading.TLabel',
                   foreground=COLORS['loading'],
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'italic'))

    style.configure('Error.TLabel',
                   foreground=COLORS['error'],
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'))

    style.configure('Success.TLabel',
                   foreground=COLORS['success'],
                   font=(config.FONT_FAMILY, config.FONT_SIZE))

    style.configure('Empty.TLabel',
                   foreground=COLORS['empty'],
                   font=(config.FONT_FAMILY, config.FONT_SIZE, 'italic'))


def get_priority_style(priority: str) -> str:
    """
    Get style name for a given priority level.

    Args:
        priority: 'high', 'medium', or 'low'

    Returns:
        Style name string for ttk widgets

    Example:
        >>> style = get_priority_style('high')
        >>> label = ttk.Label(parent, text="High Priority", style=style)
    """
    priority_map = {
        'high': 'HighPriority.TLabel',
        'medium': 'MediumPriority.TLabel',
        'low': 'LowPriority.TLabel'
    }
    return priority_map.get(priority.lower(), 'TLabel')


def get_priority_frame_style(priority: str) -> str:
    """
    Get frame style name for a given priority level.

    Args:
        priority: 'high', 'medium', or 'low'

    Returns:
        Style name string for ttk Frame

    Example:
        >>> style = get_priority_frame_style('high')
        >>> frame = ttk.Frame(parent, style=style)
    """
    priority_map = {
        'high': 'HighPriority.TFrame',
        'medium': 'MediumPriority.TFrame',
        'low': 'LowPriority.TFrame'
    }
    return priority_map.get(priority.lower(), 'Recommendation.TFrame')


def get_priority_color(priority: str) -> str:
    """
    Get color hex code for a given priority level.

    Args:
        priority: 'high', 'medium', or 'low'

    Returns:
        Hex color string

    Example:
        >>> color = get_priority_color('high')
        >>> canvas.create_text(x, y, fill=color)
    """
    priority_map = {
        'high': COLORS['high_priority'],
        'medium': COLORS['medium_priority'],
        'low': COLORS['low_priority']
    }
    return priority_map.get(priority.lower(), COLORS['dark'])


# Example usage and testing
if __name__ == "__main__":
    import tkinter as tk

    print("=" * 60)
    print("TESTING STYLES")
    print("=" * 60)

    root = tk.Tk()
    root.title("Style Test")
    root.geometry("400x300")

    # Configure styles
    configure_styles()

    # Test frame
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)

    # Test labels
    ttk.Label(frame, text="Title Style", style='Title.TLabel').pack(pady=5)
    ttk.Label(frame, text="Subtitle Style", style='Subtitle.TLabel').pack(pady=5)
    ttk.Label(frame, text="High Priority", style='HighPriority.TLabel').pack(pady=5)
    ttk.Label(frame, text="Medium Priority", style='MediumPriority.TLabel').pack(pady=5)
    ttk.Label(frame, text="Low Priority", style='LowPriority.TLabel').pack(pady=5)

    # Test buttons
    button_frame = ttk.Frame(frame)
    button_frame.pack(pady=10)

    ttk.Button(button_frame, text="Primary", style='Primary.TButton').pack(side='left', padx=5)
    ttk.Button(button_frame, text="Success", style='Success.TButton').pack(side='left', padx=5)
    ttk.Button(button_frame, text="Danger", style='Danger.TButton').pack(side='left', padx=5)

    print("✅ Styles configured and displayed")
    print("Close window to exit...")

    root.mainloop()
