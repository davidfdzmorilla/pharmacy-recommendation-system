#!/usr/bin/env python3
"""
Script to classify products as OTC or prescription-required.

Based on Spanish medication regulation (Real Decreto 1345/2007).

Key principles for prescription requirement in Spain:
- Antibiotics (ALL require prescription)
- High-dose NSAIDs (e.g., Ibuprofeno >400mg, Dexketoprofeno, Enantyum)
- Opioid analgesics (Codeína combinations)
- Proton pump inhibitors >20mg or >14 days (Omeprazol)
- Antiemetics (Metoclopramida/Primperan)
- Strong antidiarrheals (Loperamida >2mg single dose)
- Topical antibiotics (Fucidine, Silvederma)
- Strong anti-inflammatory patches (Voltadol)
- Prescription antihistamines (some Desloratadina, Bilastina)
- Pediatric formulations of certain drugs

OTC (Over The Counter) products:
- Low-dose analgesics (Paracetamol, Ibuprofeno ≤400mg, Aspirina)
- Antacids and digestive aids
- Vitamins and supplements
- Dermatology creams (non-antibiotic)
- First aid supplies
- Hair care products
- Oral hygiene products
- Homeopathic products
- Sports/muscle creams (non-prescription)
"""
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from raspberry_app.config import config


# Products requiring prescription in Spain
PRESCRIPTION_REQUIRED = {
    # Analgésicos - HIGH DOSE or with Codeine
    3: "Nolotil (Metamizol) - prescription required",
    5: "Enantyum (Dexketoprofeno) - prescription NSAID",
    6: "Paracetamol + Codeína - opioid combination",
    37: "Voltadol parche (Diclofenaco) - prescription transdermal",

    # Digestivos - Prescription PPIs and antiemetics
    11: "Omeprazol 20mg 28 cápsulas - long-term PPI",
    13: "Primperan (Metoclopramida) - prescription antiemetic",
    14: "Fortasec (Loperamida 2mg) - prescription strength",

    # Dermatología - Topical antibiotics
    33: "Fucidine (Ácido fusídico) - topical antibiotic",
    38: "Silvederma (Sulfadiazina argéntica) - prescription antiseptic",
    39: "Thrombocid pomada - prescription strength",

    # Respiratorio - Some require prescription
    42: "Bisolvon (Bromhexina) - prescription mucolytic",
    46: "Cinfatos (Cloperastina) - prescription antitussive",
    48: "Strefen (Flurbiprofeno) - prescription throat spray",

    # Antihistamínicos - Some newer ones
    50: "Aerius (Desloratadina) - prescription antihistamine",
    54: "Bilaxten (Bilastina) - prescription antihistamine",

    # Oftalmología - Vasoconstrictors
    58: "Vizol (Nafazolina) - can require prescription",

    # Infantil - High-dose pediatric formulations
    86: "Espidifen niños (Ibuprofeno arginina) - prescription pediatric"
}


def classify_products(db_path: Path, dry_run: bool = False):
    """
    Classify all products as OTC or prescription-required.

    Args:
        db_path: Path to SQLite database
        dry_run: If True, only show classification without updating
    """
    print("=" * 70)
    print("CLASSIFY PRESCRIPTION PRODUCTS - Spanish Regulation Compliance")
    print("=" * 70)
    print(f"\nDatabase: {db_path}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will update database)'}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(products)")
        columns = [col['name'] for col in cursor.fetchall()]

        if 'requires_prescription' not in columns:
            print("\n⚠️  Column 'requires_prescription' does not exist!")
            print("Run migration first:")
            print("  sqlite3 data/pharmacy.db < raspberry_app/database/migrations/001_add_prescription_field.sql")
            return

        # Get all products
        cursor.execute("SELECT id, name, active_ingredient, category FROM products ORDER BY id")
        products = cursor.fetchall()

        print(f"\n📦 Found {len(products)} products to classify\n")

        # Classification counters
        otc_count = 0
        prescription_count = 0

        print("CLASSIFICATION RESULTS:")
        print("-" * 70)

        for product in products:
            product_id = product['id']
            name = product['name']
            ingredient = product['active_ingredient']
            category = product['category']

            # Determine if prescription required
            requires_rx = product_id in PRESCRIPTION_REQUIRED
            reason = PRESCRIPTION_REQUIRED.get(product_id, "OTC - venta libre")

            if requires_rx:
                prescription_count += 1
                status_icon = "🔴 RX"
            else:
                otc_count += 1
                status_icon = "🟢 OTC"

            # Print classification
            print(f"{status_icon} | ID {product_id:3d} | {name[:45]:45s} | {reason[:20]}")

            # Update database (if not dry run)
            if not dry_run:
                cursor.execute(
                    "UPDATE products SET requires_prescription = ? WHERE id = ?",
                    (1 if requires_rx else 0, product_id)
                )

        # Commit changes
        if not dry_run:
            conn.commit()
            print("\n✅ Database updated successfully")
        else:
            print("\n⚠️  DRY RUN - No changes made")

        # Print summary
        print("\n" + "=" * 70)
        print("CLASSIFICATION SUMMARY")
        print("=" * 70)
        print(f"Total products:           {len(products)}")
        print(f"🟢 OTC (venta libre):     {otc_count} ({otc_count/len(products)*100:.1f}%)")
        print(f"🔴 Prescription required: {prescription_count} ({prescription_count/len(products)*100:.1f}%)")

        # Verify classification
        if not dry_run:
            print("\n" + "=" * 70)
            print("VERIFICATION")
            print("=" * 70)

            cursor.execute("SELECT COUNT(*) as total FROM products WHERE requires_prescription = 0")
            otc_in_db = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as total FROM products WHERE requires_prescription = 1")
            rx_in_db = cursor.fetchone()['total']

            print(f"✅ OTC products in DB:          {otc_in_db}")
            print(f"✅ Prescription products in DB: {rx_in_db}")

            if otc_in_db == otc_count and rx_in_db == prescription_count:
                print("\n✅ Classification verified successfully!")
            else:
                print("\n⚠️  Warning: Mismatch in counts!")

        # Show examples by category
        print("\n" + "=" * 70)
        print("PRESCRIPTION PRODUCTS BY CATEGORY")
        print("=" * 70)

        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM products
            WHERE requires_prescription = 1
            GROUP BY category
            ORDER BY count DESC
        """)

        rx_by_category = cursor.fetchall()
        if rx_by_category:
            for row in rx_by_category:
                print(f"  {row['category']:25s} : {row['count']} products")
        else:
            print("  No prescription products found")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Classify pharmacy products as OTC or prescription-required"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show classification without updating database"
    )

    args = parser.parse_args()

    db_path = config.DB_PATH

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run 'python scripts/init_database.py' first")
        sys.exit(1)

    classify_products(db_path, dry_run=args.dry_run)
