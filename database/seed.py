"""
Seeds Colonel's Bakery and Restaurant's database with the starter menu,
starter ingredients/recipes, today's opening inventory, and the first
manager account.

Safe to re-run: menu/ingredient/recipe inserts are idempotent (INSERT OR
IGNORE against unique constraints); user accounts are only created if a
username does not already exist. Run with:

    cd database && python3 seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import get_connection, init_db, today_str
from auth import hash_new_password, generate_temp_password

# Bundled locally (assets/menu_photos/) rather than fetched from a stock-photo
# API — the till app must work with zero internet dependency, so a remote
# image URL would break offline use. Stored as bare filenames; each app (the
# React PWA, the Streamlit dashboard) resolves the filename against its own
# local copy of assets/menu_photos/.
PLACEHOLDER_PHOTOS = {
    "Cakes": "cakes.svg",
    "Bread": "bread.svg",
    "Drinks": "drinks.svg",
    "Ice Cream": "ice_cream.svg",
    "Restaurant — Local Dishes": "local_dishes.svg",
    "Restaurant — Intercontinental Dishes": "intercontinental_dishes.svg",
    "Snacks & Pies": "pies.svg",
}

CATEGORIES = [
    # name, colour_hex, sort_order
    ("Cakes", "#E91E63", 1),
    ("Bread", "#C9860C", 2),
    ("Drinks", "#1E88E5", 3),
    ("Ice Cream", "#00ACC1", 4),
    ("Restaurant — Local Dishes", "#43A047", 5),
    ("Restaurant — Intercontinental Dishes", "#8E24AA", 6),
    ("Snacks & Pies", "#FB8C00", 7),
]

# category_name -> [ (item_name, [(variant_label, price), ...]) ]
MENU = {
    "Cakes": [
        ("Chocolate Cake", [("Slice", 1800), ("Cupcake", 1000), ("Whole Cake", 14000)]),
        ("Marble Cake", [("Slice", 1500), ("Cupcake", 900), ("Whole Cake", 11000)]),
        ("Lemon Cake", [("Slice", 1600), ("Cupcake", 950), ("Whole Cake", 12500)]),
    ],
    "Bread": [
        ("Whole Bread", [("Small", 700), ("Large", 1400)]),
        ("Butter Bread", [("Small", 800), ("Large", 1600)]),
        ("French Bread", [("Small", 900), ("Large", 1800)]),
    ],
    "Ice Cream": [
        ("Vanilla", [("Standard", 600)]),
        ("Chocolate", [("Standard", 600)]),
        ("Strawberry", [("Standard", 650)]),
        ("Mint", [("Standard", 650)]),
        ("Cookies & Cream", [("Standard", 700)]),
    ],
    "Drinks": [
        ("Coca-Cola", [("Small", 300), ("Medium", 500), ("Large", 700)]),
        ("Sprite", [("Small", 300), ("Medium", 500), ("Large", 700)]),
        ("Fanta", [("Small", 300), ("Medium", 500), ("Large", 700)]),
        ("Fura da Nono", [("Small", 400), ("Medium", 600), ("Large", 800)]),
        ("Water", [("Small", 150), ("Medium", 250), ("Large", 400)]),
        ("Zobo", [("Small", 300), ("Medium", 450), ("Large", 600)]),
    ],
    "Restaurant — Local Dishes": [
        ("Jollof Rice", [("Standard", 1800)]),
        ("Fried Rice", [("Standard", 1900)]),
        ("Egusi Soup", [("Standard", 2200)]),
        ("Efo Riro", [("Standard", 2000)]),
        ("Pounded Yam", [("Standard", 1800)]),
        ("Suya", [("Standard", 2500)]),
        ("Pepper Soup", [("Standard", 2200)]),
        ("Amala", [("Standard", 1700)]),
    ],
    "Restaurant — Intercontinental Dishes": [
        ("Grilled Chicken", [("Standard", 3200)]),
        ("Pasta Bolognese", [("Standard", 2800)]),
        ("Burger & Chips", [("Standard", 3000)]),
        ("Pizza", [("Standard", 4500)]),
        ("Steak", [("Standard", 5000)]),
        ("Caesar Salad", [("Standard", 2500)]),
    ],
    "Snacks & Pies": [
        ("Meat Pie", [("Standard", 500)]),
        ("Chicken Pie", [("Standard", 600)]),
    ],
}

# name, unit, current_stock, reorder_threshold
INGREDIENTS = [
    ("Flour", "kg", 50, 10),
    ("Sugar", "kg", 30, 8),
    ("Butter", "kg", 20, 5),
    ("Eggs", "unit", 200, 50),
    ("Milk", "litre", 40, 10),
    ("Cocoa Powder", "kg", 10, 3),
    ("Yeast", "kg", 5, 1),
    ("Vanilla Extract", "litre", 3, 1),
    ("Cream", "litre", 15, 4),
    ("Rice", "kg", 40, 10),
    ("Chicken", "kg", 25, 8),
    ("Beef", "kg", 20, 6),
    ("Tomato", "kg", 20, 6),
    ("Cooking Oil", "litre", 25, 6),
    ("Onion", "kg", 12, 4),
]

# (item_name, variant_label) -> [(ingredient_name, quantity_used), ...]
# Demonstrates the sale -> ingredient depletion mechanism across categories.
# Not every variant needs a hand-authored recipe for the mechanism to work —
# items with no recipe rows simply don't deplete any ingredient on sale
# (e.g. bottled Coca-Cola, bought pre-made, isn't "baked" from stock here).
RECIPES = {
    ("Chocolate Cake", "Slice"): [("Flour", 0.08), ("Sugar", 0.05), ("Butter", 0.03), ("Eggs", 0.5), ("Cocoa Powder", 0.02)],
    ("Chocolate Cake", "Cupcake"): [("Flour", 0.05), ("Sugar", 0.03), ("Butter", 0.02), ("Eggs", 0.3), ("Cocoa Powder", 0.01)],
    ("Chocolate Cake", "Whole Cake"): [("Flour", 1.2), ("Sugar", 0.8), ("Butter", 0.6), ("Eggs", 8), ("Cocoa Powder", 0.3)],
    ("Whole Bread", "Small"): [("Flour", 0.4), ("Yeast", 0.01), ("Butter", 0.02)],
    ("Whole Bread", "Large"): [("Flour", 0.8), ("Yeast", 0.02), ("Butter", 0.04)],
    ("Meat Pie", "Standard"): [("Flour", 0.1), ("Butter", 0.03), ("Beef", 0.08), ("Onion", 0.02)],
    ("Chicken Pie", "Standard"): [("Flour", 0.1), ("Butter", 0.03), ("Chicken", 0.08), ("Onion", 0.02)],
    ("Vanilla", "Standard"): [("Cream", 0.1), ("Milk", 0.05), ("Sugar", 0.03), ("Vanilla Extract", 0.005)],
    ("Jollof Rice", "Standard"): [("Rice", 0.25), ("Tomato", 0.15), ("Cooking Oil", 0.03), ("Chicken", 0.1)],
    ("Grilled Chicken", "Standard"): [("Chicken", 0.3), ("Cooking Oil", 0.02), ("Onion", 0.02)],
}

# Reasonable opening stock counts for day one, keyed by (item_name, variant_label).
DEFAULT_OPENING_COUNT = 20


def seed():
    init_db()
    conn = get_connection()
    try:
        # ---- categories ----
        for name, colour, sort_order in CATEGORIES:
            conn.execute(
                "INSERT OR IGNORE INTO categories (name, colour_hex, sort_order) VALUES (?, ?, ?)",
                (name, colour, sort_order),
            )
        conn.commit()
        category_ids = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM categories").fetchall()
        }

        # ---- menu items + variants ----
        variant_ids: dict[tuple[str, str], int] = {}
        for cat_name, items in MENU.items():
            cat_id = category_ids[cat_name]
            photo = PLACEHOLDER_PHOTOS.get(cat_name)
            for item_name, variants in items:
                has_variants = 1 if (len(variants) > 1 or variants[0][0] != "Standard") else 0
                conn.execute(
                    "INSERT OR IGNORE INTO menu_items (category_id, name, has_variants, base_photo_url) "
                    "VALUES (?, ?, ?, ?)",
                    (cat_id, item_name, has_variants, photo),
                )
                conn.commit()
                item_id = conn.execute(
                    "SELECT id FROM menu_items WHERE category_id = ? AND name = ?",
                    (cat_id, item_name),
                ).fetchone()["id"]

                for label, price in variants:
                    conn.execute(
                        "INSERT OR IGNORE INTO item_variants (menu_item_id, variant_label, price) "
                        "VALUES (?, ?, ?)",
                        (item_id, label, price),
                    )
                    conn.commit()
                    v_id = conn.execute(
                        "SELECT id FROM item_variants WHERE menu_item_id = ? AND variant_label = ?",
                        (item_id, label),
                    ).fetchone()["id"]
                    variant_ids[(item_name, label)] = v_id

        # ---- ingredients ----
        for name, unit, stock, threshold in INGREDIENTS:
            conn.execute(
                "INSERT OR IGNORE INTO ingredients (name, unit, current_stock, reorder_threshold) "
                "VALUES (?, ?, ?, ?)",
                (name, unit, stock, threshold),
            )
        conn.commit()
        ingredient_ids = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM ingredients").fetchall()
        }

        # ---- recipes ----
        for (item_name, label), lines in RECIPES.items():
            v_id = variant_ids[(item_name, label)]
            for ing_name, qty in lines:
                conn.execute(
                    "INSERT OR IGNORE INTO recipes (item_variant_id, ingredient_id, quantity_used) "
                    "VALUES (?, ?, ?)",
                    (v_id, ingredient_ids[ing_name], qty),
                )
        conn.commit()

        # ---- today's opening inventory for every variant ----
        date = today_str()
        for v_id in variant_ids.values():
            conn.execute(
                "INSERT OR IGNORE INTO inventory_daily (date, item_variant_id, opening_count) "
                "VALUES (?, ?, ?)",
                (date, v_id, DEFAULT_OPENING_COUNT),
            )
        conn.commit()

        # ---- first manager account ----
        created_accounts = []
        for username, role in [("manager", "manager"), ("staff1", "staff")]:
            existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                continue
            temp_password = generate_temp_password()
            password_hash, salt = hash_new_password(temp_password)
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, active, must_change_password) "
                "VALUES (?, ?, ?, ?, 1, 1)",
                (username, password_hash, salt, role),
            )
            created_accounts.append((username, role, temp_password))
        conn.commit()

        print("Seed complete.")
        print(f"  Categories: {len(CATEGORIES)}")
        print(f"  Menu items: {sum(len(v) for v in MENU.values())}")
        print(f"  Item variants: {len(variant_ids)}")
        print(f"  Ingredients: {len(INGREDIENTS)}")
        print(f"  Recipes: {sum(len(v) for v in RECIPES.values())}")
        if created_accounts:
            print("\n  NEW LOGIN CREDENTIALS (save these now — passwords are never stored in "
                  "recoverable form, only as one-way hashes):")
            for username, role, pw in created_accounts:
                print(f"    {role:8s} username={username:10s} temp_password={pw}  (must be changed on first login)")
        else:
            print("\n  User accounts already existed; none created.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
