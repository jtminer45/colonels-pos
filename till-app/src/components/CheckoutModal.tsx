import { useState } from "react";
import { useCart } from "../contexts/CartContext";
import { api, ApiError } from "../api/client";
import { formatNaira } from "../lib/format";
import type { Receipt } from "../types";

interface Props {
  onClose: () => void;
  onSuccess: (receipt: Receipt) => void;
}

export default function CheckoutModal({ onClose, onSuccess }: Props) {
  const { lines, subtotal, vatAmount, total } = useCart();
  const [method, setMethod] = useState<"cash" | "card" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    if (!method) return;
    setSubmitting(true);
    setError(null);
    try {
      const receipt = await api.createSale(
        lines.map((l) => ({ item_variant_id: l.itemVariantId, quantity: l.quantity })),
        method
      );
      onSuccess(receipt);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not complete the sale.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-sm bg-brand-surface rounded-3xl p-6 shadow-2xl">
        <h2 className="text-lg font-semibold mb-4">Checkout</h2>

        <div className="space-y-1 text-sm mb-5">
          <div className="flex justify-between text-white/60">
            <span>Subtotal</span>
            <span>{formatNaira(subtotal)}</span>
          </div>
          <div className="flex justify-between text-white/60">
            <span>VAT (7.5%)</span>
            <span>{formatNaira(vatAmount)}</span>
          </div>
          <div className="flex justify-between text-xl font-bold pt-1">
            <span>Total</span>
            <span>{formatNaira(total)}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-5">
          <button
            onClick={() => setMethod("cash")}
            className="tap-target rounded-2xl py-6 font-semibold border-2"
            style={{
              borderColor: method === "cash" ? "#FF3B30" : "rgba(255,255,255,0.1)",
              backgroundColor: method === "cash" ? "rgba(255,59,48,0.15)" : "transparent",
            }}
          >
            💵 Cash
          </button>
          <button
            onClick={() => setMethod("card")}
            className="tap-target rounded-2xl py-6 font-semibold border-2"
            style={{
              borderColor: method === "card" ? "#FF3B30" : "rgba(255,255,255,0.1)",
              backgroundColor: method === "card" ? "rgba(255,59,48,0.15)" : "transparent",
            }}
          >
            💳 Card
          </button>
        </div>

        {error && (
          <div className="text-brand-red text-sm bg-brand-red/10 border border-brand-red/30 rounded-lg px-3 py-2 mb-4">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={submitting}
            className="tap-target flex-1 rounded-2xl border border-white/15 py-4 font-semibold text-white/70"
          >
            Cancel
          </button>
          <button
            onClick={confirm}
            disabled={!method || submitting}
            className="tap-target flex-1 rounded-2xl bg-brand-red disabled:opacity-30 py-4 font-semibold"
          >
            {submitting ? "Processing…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
