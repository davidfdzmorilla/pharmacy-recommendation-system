#!/usr/bin/env python3
"""
Test configuration and logging setup.
Run this to verify US-0.2 implementation.
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.config import config
from raspberry_app.utils.logger import setup_logging, get_logger


def test_configuration():
    """Test configuration loading."""
    print("=" * 60)
    print("TESTING CONFIGURATION")
    print("=" * 60)

    print(f"\n📁 Paths:")
    print(f"  BASE_DIR: {config.BASE_DIR}")
    print(f"  DATA_DIR: {config.DATA_DIR}")
    print(f"  LOGS_DIR: {config.LOGS_DIR}")
    print(f"  DB_PATH: {config.DB_PATH}")

    print(f"\n🤖 API Configuration:")
    print(f"  CLAUDE_MODEL: {config.CLAUDE_MODEL}")
    print(f"  MAX_TOKENS: {config.MAX_TOKENS}")
    print(f"  TEMPERATURE: {config.TEMPERATURE}")
    print(f"  API_KEY set: {'Yes' if config.ANTHROPIC_API_KEY else 'No (placeholder)'}")

    print(f"\n💾 Cache Configuration:")
    print(f"  CACHE_ENABLED: {config.CACHE_ENABLED}")
    print(f"  CACHE_TTL: {config.CACHE_TTL}s")
    print(f"  CACHE_MAX_SIZE: {config.CACHE_MAX_SIZE}")

    print(f"\n🎨 UI Configuration:")
    print(f"  WINDOW_SIZE: {config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
    print(f"  FONT: {config.FONT_FAMILY} {config.FONT_SIZE}pt")

    print(f"\n🔧 Application Settings:")
    print(f"  SIMULATION_MODE: {config.SIMULATION_MODE}")
    print(f"  DEBOUNCE_DELAY: {config.DEBOUNCE_DELAY}s")
    print(f"  LOG_LEVEL: {config.LOG_LEVEL}")

    # Validate configuration
    try:
        is_valid = config.validate()
        print(f"\n✅ Configuration validation: {'PASSED' if is_valid else 'FAILED'}")
    except ValueError as e:
        print(f"\n❌ Configuration validation FAILED: {e}")
        return False

    return True


def test_logging():
    """Test logging setup."""
    print("\n" + "=" * 60)
    print("TESTING LOGGING")
    print("=" * 60)

    # Setup logging
    logger = setup_logging(
        log_level=config.LOG_LEVEL,
        log_file=config.LOG_FILE,
        log_dir=config.LOGS_DIR
    )

    print(f"\n📝 Logger configured:")
    print(f"  Level: {logging.getLevelName(logger.level)}")
    print(f"  Handlers: {len(logger.handlers)}")
    print(f"  Log file: {config.LOGS_DIR / config.LOG_FILE}")

    # Test different log levels
    print(f"\n🧪 Testing log levels...")
    logger.debug("DEBUG: This is a debug message")
    logger.info("INFO: This is an info message")
    logger.warning("WARNING: This is a warning message")
    logger.error("ERROR: This is an error message")

    # Test module logger
    module_logger = get_logger(__name__)
    module_logger.info("Module logger working correctly")

    print(f"✅ Logging test completed")
    print(f"   Check {config.LOGS_DIR / config.LOG_FILE} for detailed logs")

    return True


def test_imports():
    """Test that imports work correctly."""
    print("\n" + "=" * 60)
    print("TESTING IMPORTS")
    print("=" * 60)

    try:
        from raspberry_app.config import Config
        print("✅ Can import Config class")

        from raspberry_app.utils.logger import setup_logging, get_logger, LoggerMixin
        print("✅ Can import logging utilities")

        from raspberry_app import __version__
        print(f"✅ Package version: {__version__}")

        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n🧪 US-0.2 VERIFICATION TEST")
    print("Testing Configuration Base Setup\n")

    results = []

    # Test imports
    results.append(("Imports", test_imports()))

    # Test configuration
    results.append(("Configuration", test_configuration()))

    # Test logging (this also uses config)
    results.append(("Logging", test_logging()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} {status}")
        if not result:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - US-0.2 VERIFIED")
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW ABOVE")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
