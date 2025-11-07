#!/usr/bin/env python3
"""
Initialize pharmacy database with schema.
Creates empty database structure ready for product import.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.config import config
from raspberry_app.database.db_manager import DatabaseManager
from raspberry_app.utils.logger import setup_logging, get_logger


def main():
    """Initialize database."""
    # Setup logging
    setup_logging(log_level=config.LOG_LEVEL, log_dir=config.LOGS_DIR)
    logger = get_logger(__name__)

    print("=" * 60)
    print("PHARMACY DATABASE INITIALIZATION")
    print("=" * 60)

    # Ensure data directory exists
    config.DATA_DIR.mkdir(exist_ok=True, parents=True)

    # Check if database already exists
    if config.DB_PATH.exists():
        response = input(f"\nDatabase already exists at {config.DB_PATH}\n"
                        "Do you want to recreate it? (y/N): ")
        if response.lower() != 'y':
            print("Initialization cancelled.")
            return 0

        # Backup existing database
        backup_path = config.DB_PATH.with_suffix('.db.backup')
        config.DB_PATH.rename(backup_path)
        print(f"✅ Existing database backed up to {backup_path}")

    # Initialize database
    try:
        db = DatabaseManager()
        db.init_database()
        print(f"\n✅ Database initialized successfully")
        print(f"   Location: {config.DB_PATH}")

        # Verify tables were created
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """)
            tables = [row['name'] for row in cursor.fetchall()]

        print(f"\n📊 Created tables:")
        for table in tables:
            print(f"   - {table}")

        print(f"\n✅ Database is ready for product import")
        print(f"   Next step: python scripts/import_products.py")

        logger.info("Database initialized successfully")
        return 0

    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        logger.error(f"Database initialization failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
