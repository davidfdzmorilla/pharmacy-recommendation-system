"""
Configuration module for Pharmacy Recommendation System.
Loads settings from environment variables and provides centralized config.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    DB_PATH: Path = DATA_DIR / "pharmacy.db"

    # API Configuration
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.3"))
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "10"))

    # Cache Configuration
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
    CACHE_MAX_SIZE: int = int(os.getenv("CACHE_MAX_SIZE", "100"))

    # Recommendation Settings
    MAX_RECOMMENDATIONS: int = int(os.getenv("MAX_RECOMMENDATIONS", "5"))
    MIN_RECOMMENDATIONS: int = int(os.getenv("MIN_RECOMMENDATIONS", "3"))
    DEBOUNCE_DELAY: float = float(os.getenv("DEBOUNCE_DELAY", "1.5"))  # seconds

    # UI Configuration
    WINDOW_WIDTH: int = int(os.getenv("WINDOW_WIDTH", "1024"))
    WINDOW_HEIGHT: int = int(os.getenv("WINDOW_HEIGHT", "600"))
    FONT_FAMILY: str = os.getenv("FONT_FAMILY", "Arial")
    FONT_SIZE: int = int(os.getenv("FONT_SIZE", "11"))

    # Barcode Settings
    BARCODE_LENGTH: int = int(os.getenv("BARCODE_LENGTH", "13"))  # EAN-13
    SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "false").lower() == "true"

    # Performance
    MAX_MEMORY_MB: int = int(os.getenv("MAX_MEMORY_MB", "500"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "app.log"

    def validate(self) -> bool:
        """
        Validate configuration settings.

        Returns:
            bool: True if configuration is valid

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Create directories if they don't exist
        self.DATA_DIR.mkdir(exist_ok=True, parents=True)
        self.LOGS_DIR.mkdir(exist_ok=True, parents=True)

        # Validate API key (only required in production mode)
        if not self.SIMULATION_MODE and not self.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when SIMULATION_MODE=false. "
                "Please set it in your .env file."
            )

        # Validate numeric ranges
        if self.MAX_RECOMMENDATIONS < self.MIN_RECOMMENDATIONS:
            raise ValueError(
                f"MAX_RECOMMENDATIONS ({self.MAX_RECOMMENDATIONS}) must be >= "
                f"MIN_RECOMMENDATIONS ({self.MIN_RECOMMENDATIONS})"
            )

        if self.CACHE_TTL <= 0:
            raise ValueError(f"CACHE_TTL must be positive, got {self.CACHE_TTL}")

        if self.DEBOUNCE_DELAY < 0:
            raise ValueError(f"DEBOUNCE_DELAY must be non-negative, got {self.DEBOUNCE_DELAY}")

        return True

    def __post_init__(self):
        """Post-initialization: convert string paths to Path objects if needed."""
        if not isinstance(self.BASE_DIR, Path):
            self.BASE_DIR = Path(self.BASE_DIR)
        if not isinstance(self.DATA_DIR, Path):
            self.DATA_DIR = Path(self.DATA_DIR)
        if not isinstance(self.LOGS_DIR, Path):
            self.LOGS_DIR = Path(self.LOGS_DIR)
        if not isinstance(self.DB_PATH, Path):
            self.DB_PATH = Path(self.DB_PATH)


# Global configuration instance
config = Config()
