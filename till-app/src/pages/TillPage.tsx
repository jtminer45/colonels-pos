import { useState } from "react";
import { useCart } from "../contexts/CartContext";
import { useMenu } from "../hooks/useMenu";
import { useShiftSummary } from "../hooks/useShiftSummary";
import { api } from "../api/client";
import AppHeader, { type AppMode } from "../components/AppHeader";
import CategoryTile from "../components/CategoryTile";
import ItemTile from "../components/ItemTile";
import VariantSheet from "../components/VariantSheet";
import CartPanel from "../components/CartPanel";
import CheckoutModal, { type PaymentMethod } from "../components/CheckoutModal";
import ReceiptModal from "../components/ReceiptModal";
import type { MenuItem, Receipt } from "../types";

interface Props {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
}

export default function TillPage({ mode, onModeChange }: Props) {
  const { categories, loading, error, refetch } = useMenu();
  const { refetch: refetchShift } = useShiftSummary();
  const { lines, subtotal, vatAmount, total, addLine, clear } = useCart();

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

  function handlePickVariant(variantId: number, variantLabel: string, price: number, quantity: number) {
    if (!variantSheetItem) return;
    addLine({ itemVariantId: variantId, itemName: variantSheetItem.name, variantLabel, unitPrice: price }, quantity);
    setVariantSheetItem(null);
  }

  async function handleConfirmSale(method: PaymentMethod): Promise<Receipt> {
    return api.createSale(
      lines.map((l) => ({ item_variant_id: l.itemVariantId, quantity: l.quantity })),
      method
    );
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

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden">
      <AppHeader mode={mode} onModeChange={onModeChange} />

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
      {checkoutOpen && (
        <CheckoutModal
          subtotal={subtotal}
          vatAmount={vatAmount}
          total={total}
          onConfirm={handleConfirmSale}
          onClose={() => setCheckoutOpen(false)}
          onSuccess={handleSaleSuccess}
        />
      )}
      {receipt && <ReceiptModal receipt={receipt} onDone={handleReceiptDone} />}
    </div>
  );
}
