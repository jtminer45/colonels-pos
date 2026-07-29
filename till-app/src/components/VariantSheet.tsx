import type { MenuItem } from "../types";
import { formatNaira } from "../lib/format";

interface Props {
  item: MenuItem;
  onPick: (variantId: number, variantLabel: string, price: number) => void;
  onClose: () => void;
}

export default function VariantSheet({ item, onPick, onClose }: Props) {
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
              onClick={() => onPick(v.id, v.variant_label, v.price)}
              className="tap-target w-full flex items-center justify-between rounded-2xl bg-brand-surface2 border border-white/10 px-5 py-4 disabled:opacity-40"
            >
              <span className="font-medium">{v.variant_label}</span>
              <span className="flex items-center gap-3">
                {v.sold_out && <span className="text-xs uppercase tracking-wide text-brand-red">Sold Out</span>}
                <span className="text-brand-red font-bold">{formatNaira(v.price)}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
