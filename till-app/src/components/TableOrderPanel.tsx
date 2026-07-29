import { useState } from "react";
import type { TableOrderDetail, TableOrderLine } from "../types";
import { formatNaira } from "../lib/format";
import { api, ApiError } from "../api/client";
import VoidReasonModal from "./VoidReasonModal";

interface Props {
  order: TableOrderDetail;
  onChanged: () => void;
  onPrintBill: () => void;
  onCheckout: () => void;
}

export default function TableOrderPanel({ order, onChanged, onPrintBill, onCheckout }: Props) {
  const [voidTarget, setVoidTarget] = useState<TableOrderLine | null>(null);
  const [voiding, setVoiding] = useState(false);
  const [voidError, setVoidError] = useState<string | null>(null);

  const activeLines = order.items.filter((l) => !l.is_voided);

  async function handleVoidConfirm(reason: string) {
    if (!voidTarget) return;
    setVoiding(true);
    setVoidError(null);
    try {
      await api.voidTableItem(voidTarget.table_order_item_id, reason);
      setVoidTarget(null);
      onChanged();
    } catch (e) {
      setVoidError(e instanceof ApiError ? e.message : "Could not void this item.");
    } finally {
      setVoiding(false);
    }
  }

  return (
    <div className="flex flex-col h-full bg-brand-surface border-l border-white/10">
      <div className="px-4 py-3 border-b border-white/10">
        <h2 className="font-semibold">{order.table_label ?? "Table"}'s Order</h2>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {activeLines.length === 0 && (
          <p className="text-white/40 text-sm text-center mt-10 px-4">
            Tap a category, then an item, to add it to this table's order.
          </p>
        )}
        {activeLines.map((l) => (
          <div key={l.table_order_item_id} className="bg-brand-surface2 rounded-xl p-3">
            <div className="flex justify-between items-start">
              <div className="pr-2">
                <div className="font-medium text-sm leading-tight">{l.item_name}</div>
                <div className="text-xs text-white/50">{l.variant_label}</div>
              </div>
              <button
                onClick={() => setVoidTarget(l)}
                className="tap-target text-xs text-brand-red border border-brand-red/40 rounded px-2 py-0.5"
              >
                Void
              </button>
            </div>
            <div className="flex items-center justify-between mt-2 text-sm">
              <span className="text-white/50">Qty {l.quantity}</span>
              <span className="font-semibold">{formatNaira(l.unit_price * l.quantity)}</span>
            </div>
          </div>
        ))}
      </div>

      {voidError && (
        <div className="text-brand-red text-sm bg-brand-red/10 border border-brand-red/30 rounded-lg mx-3 px-3 py-2">
          {voidError}
        </div>
      )}

      <div className="border-t border-white/10 px-4 py-3 space-y-1 text-sm">
        <div className="flex justify-between text-white/60">
          <span>Subtotal</span>
          <span>{formatNaira(order.subtotal)}</span>
        </div>
        <div className="flex justify-between text-white/60">
          <span>VAT (7.5%)</span>
          <span>{formatNaira(order.vat_amount)}</span>
        </div>
        <div className="flex justify-between text-lg font-bold pt-1">
          <span>Total</span>
          <span>{formatNaira(order.total)}</span>
        </div>
      </div>

      <div className="p-4 space-y-2">
        <button
          onClick={onPrintBill}
          disabled={activeLines.length === 0}
          className="tap-target w-full rounded-2xl border border-white/20 disabled:opacity-30 py-3 text-sm font-semibold"
        >
          🧾 Print Bill
        </button>
        <button
          onClick={onCheckout}
          disabled={activeLines.length === 0}
          className="tap-target w-full rounded-2xl bg-brand-red disabled:opacity-30 py-4 text-lg font-bold"
        >
          Checkout
        </button>
      </div>

      {voidTarget && (
        <VoidReasonModal
          itemLabel={`${voidTarget.quantity} × ${voidTarget.item_name} (${voidTarget.variant_label})`}
          onConfirm={handleVoidConfirm}
          onClose={() => setVoidTarget(null)}
          submitting={voiding}
        />
      )}
    </div>
  );
}
