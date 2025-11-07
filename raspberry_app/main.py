#!/usr/bin/env python3
"""
Entry point for the Pharmacy Recommendation System.
Initializes the GUI application and starts the main loop.
"""
import tkinter as tk
import logging
import sys
from pathlib import Path
from tkinter import messagebox

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.config import config
from raspberry_app.ui.main_window import MainWindow
from raspberry_app.ui.styles import configure_styles
from raspberry_app.utils.logger import setup_logging


def main():
    """
    Main entry point for the application.

    Sets up logging, validates configuration, creates the GUI,
    and starts the main event loop.
    """
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Validate configuration
        logger.info("=" * 60)
        logger.info("PHARMACY RECOMMENDATION SYSTEM")
        logger.info("=" * 60)
        logger.info("Starting application...")

        config.validate()
        logger.info("Configuration validated")

        # Log important settings
        logger.info(f"Database: {config.DB_PATH}")
        logger.info(f"Simulation Mode: {config.SIMULATION_MODE}")
        logger.info(f"Cache Enabled: {config.CACHE_ENABLED}")
        logger.info(f"API Model: {config.CLAUDE_MODEL}")

        # Create root window
        root = tk.Tk()

        # Configure styles
        logger.info("Configuring UI styles...")
        configure_styles()

        # Create main window
        logger.info("Creating main window...")
        app = MainWindow(root)

        # Bind close event
        root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, app, logger))

        logger.info("Application started successfully")
        logger.info("=" * 60)

        # Start main loop
        root.mainloop()

    except ValueError as e:
        # Configuration error
        logger.error(f"Configuration error: {e}")
        messagebox.showerror(
            "Error de Configuración",
            f"Error en la configuración:\n\n{e}\n\n"
            f"Verifique el archivo .env"
        )
        sys.exit(1)

    except Exception as e:
        # Unexpected error
        logger.error(f"Fatal error: {e}", exc_info=True)
        messagebox.showerror(
            "Error Fatal",
            f"Error inesperado:\n\n{e}\n\n"
            f"Consulte los logs para más detalles"
        )
        sys.exit(1)


def on_closing(root: tk.Tk, app: MainWindow, logger: logging.Logger):
    """
    Handle application close event.

    Args:
        root: Tkinter root window
        app: MainWindow instance
        logger: Logger instance
    """
    if messagebox.askokcancel("Salir", "¿Desea salir de la aplicación?"):
        logger.info("Application closing...")

        # Cleanup
        try:
            # Close database connections
            if hasattr(app, 'db'):
                app.db = None

            # Close any open windows
            if hasattr(app, 'simulator') and app.simulator:
                app.simulator.stop()

            logger.info("Cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        finally:
            root.destroy()
            logger.info("Application closed")
            logger.info("=" * 60)


if __name__ == "__main__":
    main()
