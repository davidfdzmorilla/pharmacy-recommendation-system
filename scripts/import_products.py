#!/usr/bin/env python3
"""
Import sample products from JSON file into database.
Populates the database with 100 pharmaceutical products.
"""
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.config import config
from raspberry_app.database.db_manager import DatabaseManager
from raspberry_app.database.models import Product
from raspberry_app.utils.logger import setup_logging, get_logger


def main():
    """Import products from JSON file."""
    # Setup logging
    setup_logging(log_level=config.LOG_LEVEL, log_dir=config.LOGS_DIR)
    logger = get_logger(__name__)

    print("=" * 60)
    print("PRODUCT IMPORT")
    print("=" * 60)

    # Check if database exists
    if not config.DB_PATH.exists():
        print(f"\n❌ Database not found at {config.DB_PATH}")
        print("   Run 'python scripts/init_database.py' first")
        return 1

    # Load products from JSON
    json_path = config.DATA_DIR / "sample_products.json"
    if not json_path.exists():
        print(f"\n❌ Products file not found: {json_path}")
        return 1

    try:
        with json_path.open('r', encoding='utf-8') as f:
            products_data = json.load(f)

        print(f"\n📦 Found {len(products_data)} products to import")

        # Initialize database manager
        db = DatabaseManager()

        # Check if products already exist
        existing_products = db.get_all_products()
        if existing_products:
            response = input(f"\nDatabase already contains {len(existing_products)} products\n"
                           "Do you want to clear and reimport? (y/N): ")
            if response.lower() != 'y':
                print("Import cancelled.")
                return 0

            # Clear existing products
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM products")
                print(f"✅ Cleared {len(existing_products)} existing products")

        # Import products
        imported_count = 0
        errors = []

        for product_data in products_data:
            try:
                product = Product(
                    ean=product_data['ean'],
                    name=product_data['name'],
                    price=product_data['price'],
                    category=product_data['category'],
                    active_ingredient=product_data.get('active_ingredient'),
                    description=product_data.get('description'),
                    stock=product_data.get('stock', 0)
                )
                db.add_product(product)
                imported_count += 1
                print(f"   ✓ {product.name[:50]:<50} (€{product.price:.2f})")

            except Exception as e:
                errors.append((product_data.get('name', 'Unknown'), str(e)))
                print(f"   ✗ Failed to import {product_data.get('name', 'Unknown')}: {e}")

        # Summary
        print(f"\n" + "=" * 60)
        print(f"IMPORT SUMMARY")
        print(f"=" * 60)
        print(f"✅ Successfully imported: {imported_count} products")

        if errors:
            print(f"❌ Failed imports: {len(errors)}")
            for name, error in errors:
                print(f"   - {name}: {error}")

        # Statistics by category
        all_products = db.get_all_products()
        categories = {}
        for product in all_products:
            categories[product.category] = categories.get(product.category, 0) + 1

        print(f"\n📊 Products by category:")
        for category, count in sorted(categories.items()):
            print(f"   {category:<30} {count:>3} products")

        print(f"\n✅ Database ready for use!")
        logger.info(f"Imported {imported_count} products successfully")
        return 0

    except json.JSONDecodeError as e:
        print(f"\n❌ Error parsing JSON file: {e}")
        logger.error(f"JSON parsing error: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        logger.error(f"Product import failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
