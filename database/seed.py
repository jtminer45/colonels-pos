"""
Seeds/curates Colonel's Bakery and Restaurant's database: the menu (with
real per-item photos), starter ingredients/recipes, today's opening
inventory, and the first manager account.

Safe to re-run — and re-run on every backend boot (see backend/main.py):
- Menu items/variants are upserted (ON CONFLICT ... DO UPDATE), so editing
  MENU below and redeploying is how the curated menu/prices/photos reach
  the live database — there is no separate manual migration step.
- Items that exist in the database but are no longer listed in MENU are
  deactivated (not deleted — historical sales referencing them must keep
  resolving), so removing an item here removes it from the till/dashboard
  without touching sales history.
- User accounts are only created if a username does not already exist.

Run manually with:  cd database && python3 seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import get_connection, init_db, today_str
from auth import hash_new_password, generate_temp_password

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

# Prices below are deliberately generic placeholders (flat per category) —
# the real menu photos came in before real pricing did. Update via the
# dashboard's Menu Management page whenever real prices are ready; there is
# no need to touch this file for a price change.
CAKE_VARIANTS = [("Slice", 1500), ("Cupcake", 900)]
# "Big Cake" is its own menu item (not a per-flavour "Whole Cake" variant) —
# one whole-cake option across the board rather than one per flavour.
BIG_CAKE_VARIANTS = [("Standard", 12000)]
BREAD_VARIANTS = [("Small", 700), ("Large", 1400)]
DRINK_VARIANTS = [("Small", 300), ("Medium", 500), ("Large", 700)]
# Per-scoop price — quantity selected on the till IS the scoop count.
ICE_CREAM_VARIANTS = [("Cup", 600), ("Cone", 650)]
STANDARD_SNACK = [("Standard", 600)]
STANDARD_LOCAL = [("Standard", 2000)]
STANDARD_INTERCONTINENTAL = [("Standard", 3000)]

# category_name -> [ (item_name, photo_filename, [(variant_label, price), ...]) ]
MENU = {
    "Cakes": [
        ("Chocolate Cake", "chocolate-cake.jpg", CAKE_VARIANTS),
        ("Marble Cake", "marble-cake.jpg", CAKE_VARIANTS),
        ("Lemon Cake", "lemon-cake.jpg", CAKE_VARIANTS),
        ("Vanilla Cake", "vanilla-cake.jpg", CAKE_VARIANTS),
        ("Red Velvet Cake", "red-velvet-cake.jpg", CAKE_VARIANTS),
        ("Big Cake", "big-cake.jpg", BIG_CAKE_VARIANTS),
    ],
    "Bread": [
        ("Butter Bread", "butter-bread.jpg", BREAD_VARIANTS),
        ("French Bread", "french-bread.jpg", BREAD_VARIANTS),
        ("Coconut Bread", "coconut-bread.jpg", BREAD_VARIANTS),
        ("Plain Bread", "plain-bread.jpg", BREAD_VARIANTS),
        ("Burger Buns", "burger-buns.jpg", BREAD_VARIANTS),
    ],
    # Cup/Cone is the container choice; price is PER SCOOP — the quantity
    # the customer picks on the till/table order IS the scoop count (e.g.
    # 3x "Vanilla — Cup" = 3 scoops in one cup, priced per scoop).
    "Ice Cream": [
        ("Vanilla", "vanilla-ice-cream.jpg", ICE_CREAM_VARIANTS),
        ("Chocolate", "chocolate-ice-cream.jpg", ICE_CREAM_VARIANTS),
        ("Strawberry", "strawberry-ice-cream.jpg", ICE_CREAM_VARIANTS),
        ("Bubble Gum", "bubble-gum-ice-cream.jpg", ICE_CREAM_VARIANTS),
    ],
    "Drinks": [
        ("Coca-Cola", "coca-cola.jpg", DRINK_VARIANTS),
        ("Fanta", "fanta.jpg", DRINK_VARIANTS),
        ("Sprite", "sprite.jpg", DRINK_VARIANTS),
        ("Fura da Nono", "fura-da-nono.jpg", DRINK_VARIANTS),
        ("Water", "water.jpg", DRINK_VARIANTS),
        ("Zobo", "zobo.jpg", DRINK_VARIANTS),
        ("Coffee", "coffee.jpg", DRINK_VARIANTS),
        ("Tea", "tea.jpg", DRINK_VARIANTS),
    ],
    "Snacks & Pies": [
        ("Meat Pie", "meat-pie.jpg", STANDARD_SNACK),
        ("Chicken Pie", "chicken-pie.jpg", STANDARD_SNACK),
        ("Jam Doughnuts", "jam-doughnuts.jpg", STANDARD_SNACK),
        ("Plain Doughnut", "plain-doughnut.jpg", STANDARD_SNACK),
        ("Samosa", "samosa.jpg", STANDARD_SNACK),
        ("Spring Rolls", "spring-rolls.jpg", STANDARD_SNACK),
        ("Cinnamon Rolls", "cinnamon-rolls.jpg", STANDARD_SNACK),
        ("Chips", "chips.jpg", STANDARD_SNACK),
    ],
    "Restaurant — Local Dishes": [
        ("Jollof Rice", "jollof-rice.jpg", STANDARD_LOCAL),
        ("Fried Rice", "fried-rice.jpg", STANDARD_LOCAL),
        ("White Rice", "white-rice.jpg", STANDARD_LOCAL),
        ("Egusi Soup", "egusi-soup.jpg", STANDARD_LOCAL),
        ("Okra Soup", "okra-soup.jpg", STANDARD_LOCAL),
        ("Amala", "amala.jpg", STANDARD_LOCAL),
        ("Liver Sauce", "liver-sauce.jpg", STANDARD_LOCAL),
        ("Stew", "stew.jpg", STANDARD_LOCAL),
        ("Cow Meat", "cow-meat.jpg", STANDARD_LOCAL),
        ("Goat Meat", "goat-meat.jpg", STANDARD_LOCAL),
        ("Fried Chicken", "fried-chicken.jpg", STANDARD_LOCAL),
        ("Potatoes", "potatoes.jpg", STANDARD_LOCAL),
    ],
    "Restaurant — Intercontinental Dishes": [
        ("Grilled Chicken", "grilled-chicken.jpg", STANDARD_INTERCONTINENTAL),
        ("Pasta Bolognese", "pasta-bolognese.jpg", STANDARD_INTERCONTINENTAL),
        ("Burger & Chips", "burger-and-chips.jpg", STANDARD_INTERCONTINENTAL),
        ("Cheese Burger", "cheese-burger.jpg", STANDARD_INTERCONTINENTAL),
        ("Caesar Salad", "caesar-salad.jpg", STANDARD_INTERCONTINENTAL),
        ("Shawarma", "shawarma.jpg", STANDARD_INTERCONTINENTAL),
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
    ("Big Cake", "Standard"): [("Flour", 1.2), ("Sugar", 0.8), ("Butter", 0.6), ("Eggs", 8), ("Cocoa Powder", 0.3)],
    ("Plain Bread", "Small"): [("Flour", 0.4), ("Yeast", 0.01), ("Butter", 0.02)],
    ("Plain Bread", "Large"): [("Flour", 0.8), ("Yeast", 0.02), ("Butter", 0.04)],
    ("Meat Pie", "Standard"): [("Flour", 0.1), ("Butter", 0.03), ("Beef", 0.08), ("Onion", 0.02)],
    ("Chicken Pie", "Standard"): [("Flour", 0.1), ("Butter", 0.03), ("Chicken", 0.08), ("Onion", 0.02)],
    # Per scoop, regardless of cup or cone.
    ("Vanilla", "Cup"): [("Cream", 0.1), ("Milk", 0.05), ("Sugar", 0.03), ("Vanilla Extract", 0.005)],
    ("Vanilla", "Cone"): [("Cream", 0.1), ("Milk", 0.05), ("Sugar", 0.03), ("Vanilla Extract", 0.005)],
    ("Jollof Rice", "Standard"): [("Rice", 0.25), ("Tomato", 0.15), ("Cooking Oil", 0.03), ("Chicken", 0.1)],
    ("Grilled Chicken", "Standard"): [("Chicken", 0.3), ("Cooking Oil", 0.02), ("Onion", 0.02)],
}

# Reasonable opening stock counts for day one, keyed by (item_name, variant_label).
DEFAULT_OPENING_COUNT = 20

NUM_TABLES = 10


def seed():
    init_db()
    conn = get_connection()
    try:
        # ---- categories ----
        for name, colour, sort_order in CATEGORIES:
            conn.execute(
                "INSERT INTO categories (name, colour_hex, sort_order) VALUES (?, ?, ?) "
                "ON CONFLICT (name) DO NOTHING",
                (name, colour, sort_order),
            )
        conn.commit()
        category_ids = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM categories").fetchall()
        }

        # ---- menu items + variants (upsert: editing MENU above and
        # redeploying is how photo/price changes reach the live database) ----
        variant_ids: dict[tuple[str, str], int] = {}
        kept_item_ids: set[int] = set()
        kept_variant_ids: set[int] = set()
        for cat_name, items in MENU.items():
            cat_id = category_ids[cat_name]
            for item_name, photo, variants in items:
                has_variants = 1 if (len(variants) > 1 or variants[0][0] != "Standard") else 0
                conn.execute(
                    "INSERT INTO menu_items (category_id, name, has_variants, base_photo_url, active) "
                    "VALUES (?, ?, ?, ?, 1) "
                    "ON CONFLICT (category_id, name) DO UPDATE SET "
                    "has_variants = EXCLUDED.has_variants, base_photo_url = EXCLUDED.base_photo_url, active = 1",
                    (cat_id, item_name, has_variants, photo),
                )
                conn.commit()
                item_id = conn.execute(
                    "SELECT id FROM menu_items WHERE category_id = ? AND name = ?",
                    (cat_id, item_name),
                ).fetchone()["id"]
                kept_item_ids.add(item_id)

                for label, price in variants:
                    conn.execute(
                        "INSERT INTO item_variants (menu_item_id, variant_label, price, active) "
                        "VALUES (?, ?, ?, 1) "
                        "ON CONFLICT (menu_item_id, variant_label) DO UPDATE SET "
                        "price = EXCLUDED.price, active = 1",
                        (item_id, label, price),
                    )
                    conn.commit()
                    v_id = conn.execute(
                        "SELECT id FROM item_variants WHERE menu_item_id = ? AND variant_label = ?",
                        (item_id, label),
                    ).fetchone()["id"]
                    variant_ids[(item_name, label)] = v_id
                    kept_variant_ids.add(v_id)

        # ---- deactivate items/variants no longer listed in MENU (never
        # hard-deleted — historical sales must keep resolving to a valid
        # item_variant). Two levels: whole items removed entirely (e.g. an
        # item dropped from MENU), and orphaned variants within items that
        # are kept (e.g. removing "Whole Cake" from CAKE_VARIANTS while
        # keeping the cake items themselves). ----
        existing_items = conn.execute("SELECT id FROM menu_items").fetchall()
        stale_item_ids = [row["id"] for row in existing_items if row["id"] not in kept_item_ids]
        for item_id in stale_item_ids:
            conn.execute("UPDATE menu_items SET active = 0 WHERE id = ?", (item_id,))
            conn.execute("UPDATE item_variants SET active = 0 WHERE menu_item_id = ?", (item_id,))

        existing_variants = conn.execute(
            "SELECT id FROM item_variants WHERE menu_item_id IN "
            f"({','.join('?' * len(kept_item_ids))})",
            tuple(kept_item_ids),
        ).fetchall() if kept_item_ids else []
        stale_variant_ids = [row["id"] for row in existing_variants if row["id"] not in kept_variant_ids]
        for v_id in stale_variant_ids:
            conn.execute("UPDATE item_variants SET active = 0 WHERE id = ?", (v_id,))
        conn.commit()

        # ---- restaurant tables ----
        for i in range(1, NUM_TABLES + 1):
            conn.execute(
                "INSERT INTO restaurant_tables (label, sort_order) VALUES (?, ?) "
                "ON CONFLICT (label) DO NOTHING",
                (f"Table {i}", i),
            )
        conn.commit()

        # ---- ingredients ----
        for name, unit, stock, threshold in INGREDIENTS:
            conn.execute(
                "INSERT INTO ingredients (name, unit, current_stock, reorder_threshold) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (name) DO NOTHING",
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
                    "INSERT INTO recipes (item_variant_id, ingredient_id, quantity_used) "
                    "VALUES (?, ?, ?) ON CONFLICT (item_variant_id, ingredient_id) DO NOTHING",
                    (v_id, ingredient_ids[ing_name], qty),
                )
        conn.commit()

        # ---- today's opening inventory for every variant ----
        date = today_str()
        for v_id in variant_ids.values():
            conn.execute(
                "INSERT INTO inventory_daily (date, item_variant_id, opening_count) "
                "VALUES (?, ?, ?) ON CONFLICT (date, item_variant_id) DO NOTHING",
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
        print(f"  Menu items: {sum(len(v) for v in MENU.values())} ({len(stale_item_ids)} deactivated)")
        print(f"  Item variants: {len(variant_ids)} ({len(stale_variant_ids)} orphaned variants deactivated)")
        print(f"  Ingredients: {len(INGREDIENTS)}")
        print(f"  Recipes: {sum(len(v) for v in RECIPES.values())}")
        print(f"  Restaurant tables: {NUM_TABLES}")
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
