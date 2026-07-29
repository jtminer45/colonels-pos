import { useState } from "react";
import type { MenuItem, Variant } from "../types";
import { formatNaira } from "../lib/format";

interface Props {
  item: MenuItem;
  onPick: (variantId: number, variantLabel: string, price: number, quantity: number) => void;
  onClose: () => void;
}

export default function VariantSheet({ item, onPick, onClose }: Props) {
  const [selected, setSelected] = useState<Variant | null>(null);
  const [quantity, setQuantity] = useState(1);

  function selectVariant(v: Variant) {
    if (v.sold_out) return;
    setSelected(v);
    setQuantity(1);
  }

  function confirm() {
    if (!selected) return;
    onPick(selected.id, selected.variant_label, selected.price, quantity);
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full sm:max-w-md bg-brand-surface rounded-t-3xl sm:rounded-3xl p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{item.name}</h2>
          <button onClick={onClose} className="tap-target text-white/50 text-2xl leading-none px-2">
            ×
          </button>
        </div>
        <div className="space-y-3">
          {item.variants.map((v) => (
            <button
              key={v.id}
              disabled={v.sold_out}
              onClick={() => selectVariant(v)}
              className="tap-target w-full flex items-center justify-between rounded-2xl border-2 px-5 py-4 disabled:opacity-40"
              style={{
                borderColor: selected?.id === v.id ? "#C61D24" : "rgba(255,255,255,0.1)",
                backgroundColor: selected?.id === v.id ? "rgba(198,29,36,0.12)" : "#212121",
              }}
            >
              <span className="font-medium">{v.variant_label}</span>
              <span className="flex items-center gap-3">
                {v.sold_out && <span className="text-xs uppercase tracking-wide text-brand-red">Sold Out</span>}
                <span className="text-brand-red font-bold">{formatNaira(v.price)}</span>
              </span>
            </button>
          ))}
        </div>

        {selected && (
          <div className="mt-5 pt-5 border-t border-white/10">
            <div className="flex items-center justify-between">
              <span className="text-white/60 text-sm">Quantity</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  className="tap-target w-10 h-10 rounded-xl bg-brand-navy border border-white/10 font-bold text-lg"
                >
                  −
                </button>
                <span className="w-8 text-center text-lg font-semibold">{quantity}</span>
                <button
                  onClick={() => setQuantity((q) => q + 1)}
                  className="tap-target w-10 h-10 rounded-xl bg-brand-navy border border-white/10 font-bold text-lg"
                >
                  +
                </button>
              </div>
            </div>
            <button
              onClick={confirm}
              className="tap-target w-full mt-4 rounded-2xl bg-brand-red py-4 text-lg font-bold"
            >
              Add {quantity} — {formatNaira(selected.price * quantity)}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
