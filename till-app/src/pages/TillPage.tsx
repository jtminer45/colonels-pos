import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useCart } from "../contexts/CartContext";
import { useMenu } from "../hooks/useMenu";
import { useShiftSummary } from "../hooks/useShiftSummary";
import CategoryTile from "../components/CategoryTile";
import ItemTile from "../components/ItemTile";
import VariantSheet from "../components/VariantSheet";
import CartPanel from "../components/CartPanel";
import CheckoutModal from "../components/CheckoutModal";
import ReceiptModal from "../components/ReceiptModal";
import { formatNaira } from "../lib/format";
import type { MenuItem, Receipt } from "../types";

export default function TillPage() {
  const { user, logout } = useAuth();
  const { categories, loading, error, refetch } = useMenu();
  const { summary, refetch: refetchShift } = useShiftSummary();
  const { addLine, clear } = useCart();

  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const [variantSheetItem, setVariantSheetItem] = useState<MenuItem | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);

  const activeCategory = categories.find((c) => c.id === activeCategoryId) ?? categories[0] ?? null;

  function handleAddSingleVariant(item: MenuItem) {
    const v = item.variants[0];
    if (!v || v.sold_out) return;
    addLine({ itemVariantId: v.id, itemName: item.name, variantLabel: v.variant_label, unitPrice: v.price });
  }

  function handlePickVariant(variantId: number, variantLabel: string, price: number) {
    if (!variantSheetItem) return;
    addLine({ itemVariantId: variantId, itemName: variantSheetItem.name, variantLabel, unitPrice: price });
    setVariantSheetItem(null);
  }

  async function handleSaleSuccess(r: Receipt) {
    setReceipt(r);
    setCheckoutOpen(false);
    clear();
    refetchShift();
    refetch(); // menu availability changed
  }

  function handleReceiptDone() {
    setReceipt(null);
  }

  async function handleClockOut() {
    if (!confirm("Clock out and end this shift?")) return;
    await logout();
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden">
      <header className="flex items-center justify-between px-4 py-3 bg-brand-surface border-b border-white/10 shrink-0">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="" className="w-9 h-9 rounded-lg" />
          <div>
            <div className="font-semibold text-sm leading-tight">Colonel's Bakery &amp; Restaurant</div>
            <div className="text-xs text-white/40">{user?.username}</div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-white/40">This Shift</div>
            <div className="font-semibold">
              {summary ? formatNaira(summary.total_sales) : "—"}
              <span className="text-white/40 font-normal"> · {summary?.sale_count ?? 0} sales</span>
            </div>
          </div>
          <button
            onClick={handleClockOut}
            className="tap-target rounded-xl border border-brand-red text-brand-red px-4 py-2 text-sm font-semibold"
          >
            Clock Out
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-brand-red/15 text-brand-red text-sm px-4 py-2 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={refetch} className="tap-target underline">
            Retry
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex gap-3 overflow-x-auto px-4 py-3 shrink-0">
            {categories.map((c) => (
              <CategoryTile
                key={c.id}
                category={c}
                active={activeCategory?.id === c.id}
                onSelect={() => setActiveCategoryId(c.id)}
              />
            ))}
          </div>

          <div className="flex-1 overflow-y-auto px-4 pb-4">
            {loading && <p className="text-white/40 text-center mt-10">Loading menu…</p>}
            {!loading && activeCategory && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                {activeCategory.items.map((item) => (
                  <ItemTile
                    key={item.id}
                    item={item}
                    onAddSingleVariant={handleAddSingleVariant}
                    onOpenVariants={setVariantSheetItem}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="w-[340px] shrink-0">
          <CartPanel onCheckout={() => setCheckoutOpen(true)} />
        </div>
      </div>

      {variantSheetItem && (
        <VariantSheet item={variantSheetItem} onPick={handlePickVariant} onClose={() => setVariantSheetItem(null)} />
      )}
      {checkoutOpen && <CheckoutModal onClose={() => setCheckoutOpen(false)} onSuccess={handleSaleSuccess} />}
      {receipt && <ReceiptModal receipt={receipt} onDone={handleReceiptDone} />}
    </div>
  );
}
