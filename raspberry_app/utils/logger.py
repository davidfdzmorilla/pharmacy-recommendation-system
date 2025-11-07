"""
Logging configuration for Pharmacy Recommendation System.
Provides centralized logging setup with file and console handlers.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: Optional[Path] = None,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Configure application logging with file and console handlers.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Name of the log file (default: app.log)
        log_dir: Directory for log files (default: logs/)
        log_format: Format string for log messages

    Returns:
        logging.Logger: Configured root logger

    Example:
        >>> from raspberry_app.utils.logger import setup_logging
        >>> logger = setup_logging(log_level="DEBUG")
        >>> logger.info("Application started")
    """
    # Default values
    if log_file is None:
        log_file = "app.log"

    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"

    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Ensure log directory exists
    log_dir.mkdir(exist_ok=True, parents=True)
    log_path = log_dir / log_file

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    formatter = logging.Formatter(log_format)

    # File handler - logs everything
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler - logs INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(max(numeric_level, logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Log startup message
    logger.info(f"Logging configured: level={log_level}, file={log_path}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Name of the logger (typically __name__)

    Returns:
        logging.Logger: Logger instance

    Example:
        >>> from raspberry_app.utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.debug("Debug message")
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class to add logging capability to any class.

    Example:
        >>> class MyClass(LoggerMixin):
        ...     def my_method(self):
        ...         self.logger.info("Method called")
    """

    @property
    def logger(self) -> logging.Logger:
        """Get logger instance for this class."""
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return logging.getLogger(name)


# Example usage and testing
if __name__ == "__main__":
    # Test logger setup
    logger = setup_logging(log_level="DEBUG")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Test module logger
    module_logger = get_logger(__name__)
    module_logger.info("Module logger test")

    # Test mixin
    class TestClass(LoggerMixin):
        def test_method(self):
            self.logger.info("Testing LoggerMixin")

    test_obj = TestClass()
    test_obj.test_method()

    print("\nLogger testing completed. Check logs/app.log for output.")
