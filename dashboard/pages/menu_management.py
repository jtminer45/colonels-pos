from pathlib import Path

import streamlit as st

import services
from session import current_user

ASSETS_MENU_PHOTOS = Path(__file__).resolve().parent.parent.parent / "assets" / "menu_photos"

st.title("🍽️ Menu Management")
st.caption(
    "Add a seasonal item any time — a Valentine's package, Christmas cookies, a new drink — "
    "with no code change or redeploy needed. Removing something here deactivates it; it never "
    "deletes historical sales that reference it."
)
user = current_user()


def photo_display_src(base_photo_url: str | None):
    """Resolves a base_photo_url for st.image: a full URL (manager-uploaded
    photo, served by the backend) is used as-is; a bare filename is resolved
    against the local bundled copy in assets/menu_photos/."""
    if not base_photo_url:
        return None
    if base_photo_url.startswith("http"):
        return base_photo_url
    local_path = ASSETS_MENU_PHOTOS / base_photo_url
    return str(local_path) if local_path.exists() else None


tab_add, tab_manage, tab_categories = st.tabs(["➕ Add Item", "📋 Manage Items", "🏷️ Categories"])

# ----------------------------------------------------------------------
with tab_categories:
    st.subheader("Existing Categories")
    categories = services.list_categories_admin()
    for c in categories:
        col1, col2 = st.columns([1, 6])
        with col1:
            st.markdown(
                f'<div style="width:28px;height:28px;border-radius:6px;background:{c["colour_hex"]};"></div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.write(c["name"])

    st.divider()
    st.subheader("Add a New Category")
    st.caption("Only needed for something that doesn't fit the existing 7 categories.")
    with st.form("add_category_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        new_cat_name = col1.text_input("Category name", placeholder="e.g. Seasonal Specials")
        new_cat_colour = col2.color_picker("Colour", value="#607D8B")
        new_cat_sort = col3.number_input("Sort order", min_value=0, value=len(categories) + 1, step=1)
        submitted = st.form_submit_button("Add Category", type="primary")

    if submitted:
        try:
            services.create_category(new_cat_name, new_cat_colour, int(new_cat_sort), user["id"])
            st.success(f"Category '{new_cat_name}' added.")
            st.rerun()
        except services.ServiceError as e:
            st.error(str(e))

# ----------------------------------------------------------------------
with tab_add:
    categories = services.list_categories_admin()
    if not categories:
        st.info("Add a category first (see the Categories tab).")
        st.stop()

    category_options = {c["name"]: c["id"] for c in categories}

    st.subheader("New Menu Item")
    col1, col2 = st.columns(2)
    category_name = col1.selectbox("Category", options=list(category_options.keys()))
    item_name = col2.text_input("Item name", placeholder="e.g. Valz Package")

    variant_style = st.radio(
        "Pricing",
        options=["Single price", "Multiple sizes/options (e.g. Small/Large, Slice/Whole)"],
        horizontal=False,
    )

    variants: list[tuple[str, float]] = []
    if variant_style == "Single price":
        price = st.number_input("Price (₦)", min_value=0.0, step=50.0, format="%.2f")
        variants = [("Standard", price)]
    else:
        st.caption("Add each size/option and its price.")
        num_variants = st.number_input("How many options?", min_value=2, max_value=6, value=2, step=1)
        cols = st.columns(int(num_variants))
        for i, col in enumerate(cols):
            with col:
                label = st.text_input(f"Label {i + 1}", key=f"new_variant_label_{i}", placeholder="e.g. Small")
                price = st.number_input(f"Price {i + 1} (₦)", min_value=0.0, step=50.0, format="%.2f", key=f"new_variant_price_{i}")
                if label.strip():
                    variants.append((label.strip(), price))

    photo_file = st.file_uploader("Photo (optional — a generic category icon is used if skipped)", type=["jpg", "jpeg", "png", "webp"])
    if photo_file is not None:
        st.image(photo_file, width=200)

    if st.button("Add Menu Item", type="primary"):
        if not item_name.strip():
            st.error("Item name is required.")
        elif not variants or any(not label for label, _ in variants):
            st.error("At least one priced option is required, and every option needs a label.")
        else:
            try:
                photo_bytes = photo_file.getvalue() if photo_file is not None else None
                photo_content_type = photo_file.type if photo_file is not None else None
                item_id = services.create_menu_item(
                    category_options[category_name],
                    item_name.strip(),
                    has_variants=(variant_style != "Single price"),
                    created_by_user_id=user["id"],
                    photo_bytes=photo_bytes,
                    photo_content_type=photo_content_type,
                )
                for label, price in variants:
                    services.create_item_variant(item_id, label, price, user["id"])
                st.success(f"'{item_name}' added to {category_name} — it will appear on the till immediately.")
                st.rerun()
            except services.ServiceError as e:
                st.error(str(e))

# ----------------------------------------------------------------------
with tab_manage:
    categories = services.list_categories_admin()
    category_filter = st.selectbox(
        "Filter by category", options=["All"] + [c["name"] for c in categories], key="manage_filter"
    )
    cat_id_filter = None
    if category_filter != "All":
        cat_id_filter = next(c["id"] for c in categories if c["name"] == category_filter)

    items = services.list_menu_items_admin(cat_id_filter)
    if not items:
        st.info("No items yet.")
        st.stop()

    for item in items:
        status = "🟢 Active" if item["active"] else "⚪ Inactive"
        with st.expander(f"{item['name']} — {item['category_name']} — {status}"):
            col_photo, col_info = st.columns([1, 3])
            with col_photo:
                src = photo_display_src(item["base_photo_url"])
                if src:
                    st.image(src, width=140)
                else:
                    st.caption("No photo")

            with col_info:
                btn_col1, btn_col2 = st.columns(2)
                if item["active"]:
                    if btn_col1.button("Deactivate item", key=f"deactivate_{item['id']}"):
                        services.set_menu_item_active(item["id"], False, user["id"])
                        st.rerun()
                else:
                    if btn_col1.button("Reactivate item", key=f"reactivate_{item['id']}"):
                        services.set_menu_item_active(item["id"], True, user["id"])
                        st.rerun()

                st.markdown("**Variants / prices**")
                for v in item["variants"]:
                    vcol1, vcol2, vcol3, vcol4 = st.columns([2, 2, 1, 1])
                    vcol1.write(v["variant_label"])
                    new_price = vcol2.number_input(
                        "Price", min_value=0.0, step=50.0, format="%.2f",
                        value=float(v["price"]), key=f"price_{v['id']}", label_visibility="collapsed",
                    )
                    if vcol3.button("Save", key=f"save_price_{v['id']}"):
                        services.update_variant_price(v["id"], new_price, user["id"])
                        st.success("Price updated.")
                        st.rerun()
                    if v["active"]:
                        if vcol4.button("Hide", key=f"hide_variant_{v['id']}"):
                            services.set_item_variant_active(v["id"], False, user["id"])
                            st.rerun()
                    else:
                        if vcol4.button("Unhide", key=f"unhide_variant_{v['id']}"):
                            services.set_item_variant_active(v["id"], True, user["id"])
                            st.rerun()

                with st.form(f"add_variant_form_{item['id']}"):
                    st.caption("Add another size/option to this item")
                    ac1, ac2, ac3 = st.columns([2, 2, 1])
                    add_label = ac1.text_input("Label", key=f"add_variant_label_{item['id']}")
                    add_price = ac2.number_input("Price (₦)", min_value=0.0, step=50.0, format="%.2f", key=f"add_variant_price_{item['id']}")
                    add_submitted = ac3.form_submit_button("Add")
                if add_submitted:
                    try:
                        services.create_item_variant(item["id"], add_label, add_price, user["id"])
                        st.success("Variant added.")
                        st.rerun()
                    except services.ServiceError as e:
                        st.error(str(e))
