import { useCallback, useEffect, useState } from "react";
import { useMenu } from "../hooks/useMenu";
import { api, ApiError } from "../api/client";
import CategoryTile from "../components/CategoryTile";
import ItemTile from "../components/ItemTile";
import VariantSheet from "../components/VariantSheet";
import TableOrderPanel from "../components/TableOrderPanel";
import BillModal from "../components/BillModal";
import CheckoutModal, { type PaymentMethod } from "../components/CheckoutModal";
import ReceiptModal from "../components/ReceiptModal";
import type { MenuItem, Receipt, TableOrderDetail } from "../types";

interface Props {
  tableId: number;
  onBack: () => void;
}

export default function TableOrderPage({ tableId, onBack }: Props) {
  const { categories, loading: menuLoading, error: menuError, refetch: refetchMenu } = useMenu();

  const [order, setOrder] = useState<TableOrderDetail | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const [variantSheetItem, setVariantSheetItem] = useState<MenuItem | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const [billOpen, setBillOpen] = useState(false);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);

  const activeCategory = categories.find((c) => c.id === activeCategoryId) ?? categories[0] ?? null;

  const refetchOrder = useCallback(async () => {
    try {
      const data = await api.getTableOrder(tableId);
      setOrder(data);
      setOrderError(null);
    } catch (e) {
      setOrderError(e instanceof Error ? e.message : "Failed to load this table's order.");
    }
  }, [tableId]);

  useEffect(() => {
    refetchOrder();
  }, [refetchOrder]);

  async function handlePrintBill() {
    setBillOpen(true);
    try {
      await api.requestTableBill(tableId);
      refetchOrder(); // reflects the "Bill Requested" status back on the Tables grid
    } catch {
      // Non-critical — the bill still opens/prints even if the status flag fails to save.
    }
  }

  async function addItem(itemVariantId: number, quantity: number) {
    setAddError(null);
    try {
      await api.addTableItem(tableId, itemVariantId, quantity);
      await refetchOrder();
      refetchMenu(); // availability changed
    } catch (e) {
      setAddError(e instanceof ApiError ? e.message : "Could not add this item.");
    }
  }

  function handleAddSingleVariant(item: MenuItem) {
    const v = item.variants[0];
    if (!v || v.sold_out) return;
    addItem(v.id, 1);
  }

  function handlePickVariant(variantId: number, _variantLabel: string, _price: number, quantity: number) {
    addItem(variantId, quantity);
    setVariantSheetItem(null);
  }

  async function handleConfirmCheckout(method: PaymentMethod): Promise<Receipt> {
    return api.checkoutTable(tableId, method);
  }

  function handleCheckoutSuccess(r: Receipt) {
    setReceipt(r);
    setCheckoutOpen(false);
  }

  function handleReceiptDone() {
    setReceipt(null);
    onBack(); // table is now free — back to the grid
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden">
      <header className="flex items-center gap-4 px-4 py-3 bg-brand-surface border-b border-white/10 shrink-0">
        <button onClick={onBack} className="tap-target rounded-xl border border-white/20 px-3 py-2 text-sm font-semibold">
          ← Tables
        </button>
        <h1 className="font-semibold text-lg">{order?.table_label ?? "Table"}</h1>
      </header>

      {(menuError || orderError || addError) && (
        <div className="bg-brand-red/15 text-brand-red text-sm px-4 py-2">
          {addError || orderError || menuError}
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
            {menuLoading && <p className="text-white/40 text-center mt-10">Loading menu…</p>}
            {!menuLoading && activeCategory && (
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
          {order && (
            <TableOrderPanel
              order={order}
              onChanged={refetchOrder}
              onPrintBill={handlePrintBill}
              onCheckout={() => setCheckoutOpen(true)}
            />
          )}
        </div>
      </div>

      {variantSheetItem && (
        <VariantSheet item={variantSheetItem} onPick={handlePickVariant} onClose={() => setVariantSheetItem(null)} />
      )}
      {billOpen && order && <BillModal order={order} onClose={() => setBillOpen(false)} />}
      {checkoutOpen && order && (
        <CheckoutModal
          title={`Checkout — ${order.table_label}`}
          subtotal={order.subtotal}
          vatAmount={order.vat_amount}
          total={order.total}
          onConfirm={handleConfirmCheckout}
          onClose={() => setCheckoutOpen(false)}
          onSuccess={handleCheckoutSuccess}
        />
      )}
      {receipt && <ReceiptModal receipt={receipt} onDone={handleReceiptDone} />}
    </div>
  );
}
