"""
Application Configuration
"""
try:
    from secretsconfig import SECRET_KEY, DATABASE_PATH
except ImportError:
    raise ImportError(
        "secretsconfig.py not found! Rename secrets.example.py to secretsconfig.py and configure it."
    )

# =============================================================================
# SESSION CLEANUP INTERVAL (hours)
# =============================================================================
CLEANUP_INTERVAL = 2
  
# =============================================================================
# FILE UPLOAD SETTINGS
# =============================================================================
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# =============================================================================
# PLOT DEFAULTS
# =============================================================================
PLOT_BASE_WIDTH_PER_TICK = 1
PLOT_MIN_PANEL_WIDTH = 2.0
PLOT_PANEL_HEIGHT = 5.0