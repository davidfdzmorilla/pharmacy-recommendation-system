#!/usr/bin/env python3
"""
Script to fix EAN-13 checksums in the database.

Recalculates the correct checksum digit for all products using the GS1 algorithm.
"""
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.barcode.validator import calculate_ean13_checksum, validate_ean13
from raspberry_app.config import config


def fix_ean_checksums(db_path: Path):
    """
    Fix EAN-13 checksums for all products in database.

    Args:
        db_path: Path to SQLite database
    """
    print("=" * 60)
    print("FIX EAN-13 CHECKSUMS")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get all products
        cursor.execute("SELECT id, ean, name FROM products ORDER BY id")
        products = cursor.fetchall()

        print(f"\nFound {len(products)} products to check\n")

        fixed_count = 0
        already_valid_count = 0
        errors = []

        for product in products:
            product_id = product['id']
            old_ean = product['ean']
            name = product['name']

            # Check if already valid
            if validate_ean13(old_ean):
                already_valid_count += 1
                print(f"✅ {old_ean} - {name[:40]} (already valid)")
                continue

            # Extract first 12 digits
            if len(old_ean) != 13:
                error_msg = f"EAN {old_ean} has invalid length {len(old_ean)} (expected 13)"
                errors.append(error_msg)
                print(f"❌ {old_ean} - {name[:40]} - {error_msg}")
                continue

            ean_base = old_ean[:12]

            # Calculate correct checksum
            try:
                correct_checksum = calculate_ean13_checksum(ean_base)
                new_ean = ean_base + str(correct_checksum)

                # Verify the new EAN is valid
                if not validate_ean13(new_ean):
                    error_msg = f"Generated EAN {new_ean} is still invalid"
                    errors.append(error_msg)
                    print(f"❌ {old_ean} - {name[:40]} - {error_msg}")
                    continue

                # Update database
                cursor.execute(
                    "UPDATE products SET ean = ? WHERE id = ?",
                    (new_ean, product_id)
                )

                fixed_count += 1
                print(f"🔧 {old_ean} -> {new_ean} - {name[:40]}")

            except Exception as e:
                error_msg = f"Error processing EAN {old_ean}: {str(e)}"
                errors.append(error_msg)
                print(f"❌ {old_ean} - {name[:40]} - {error_msg}")

        # Commit changes
        conn.commit()

        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total products:       {len(products)}")
        print(f"Already valid:        {already_valid_count}")
        print(f"Fixed:                {fixed_count}")
        print(f"Errors:               {len(errors)}")

        if errors:
            print("\nErrors encountered:")
            for error in errors:
                print(f"  - {error}")

        print("\n✅ Database updated successfully")

        # Verify all EANs are now valid
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        cursor.execute("SELECT ean FROM products")
        all_eans = [row['ean'] for row in cursor.fetchall()]

        invalid_eans = [ean for ean in all_eans if not validate_ean13(ean)]

        if invalid_eans:
            print(f"\n⚠️  WARNING: {len(invalid_eans)} EANs are still invalid:")
            for ean in invalid_eans[:10]:  # Show first 10
                print(f"  - {ean}")
        else:
            print(f"\n✅ All {len(all_eans)} EANs are now valid!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = config.DB_PATH

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run 'python scripts/init_database.py' first")
        sys.exit(1)

    fix_ean_checksums(db_path)
