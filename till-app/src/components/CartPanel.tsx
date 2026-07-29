import { useCart } from "../contexts/CartContext";
import { formatNaira } from "../lib/format";

interface Props {
  onCheckout: () => void;
}

export default function CartPanel({ onCheckout }: Props) {
  const { lines, incrementLine, decrementLine, removeLine, subtotal, vatAmount, total } = useCart();

  return (
    <div className="flex flex-col h-full bg-brand-surface border-l border-white/10">
      <div className="px-4 py-3 border-b border-white/10">
        <h2 className="font-semibold">Current Order</h2>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {lines.length === 0 && (
          <p className="text-white/40 text-sm text-center mt-10 px-4">
            Tap a category, then an item, to start an order.
          </p>
        )}
        {lines.map((l) => (
          <div key={l.itemVariantId} className="bg-brand-surface2 rounded-xl p-3">
            <div className="flex justify-between items-start">
              <div className="pr-2">
                <div className="font-medium text-sm leading-tight">{l.itemName}</div>
                <div className="text-xs text-white/50">{l.variantLabel}</div>
              </div>
              <button
                onClick={() => removeLine(l.itemVariantId)}
                className="tap-target text-white/40 text-lg leading-none px-1"
                aria-label="Remove"
              >
                ×
              </button>
            </div>
            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => decrementLine(l.itemVariantId)}
                  className="tap-target w-8 h-8 rounded-lg bg-brand-navy border border-white/10 font-bold"
                >
                  −
                </button>
                <span className="w-6 text-center">{l.quantity}</span>
                <button
                  onClick={() => incrementLine(l.itemVariantId)}
                  className="tap-target w-8 h-8 rounded-lg bg-brand-navy border border-white/10 font-bold"
                >
                  +
                </button>
              </div>
              <span className="font-semibold text-sm">{formatNaira(l.unitPrice * l.quantity)}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-white/10 px-4 py-3 space-y-1 text-sm">
        <div className="flex justify-between text-white/60">
          <span>Subtotal</span>
          <span>{formatNaira(subtotal)}</span>
        </div>
        <div className="flex justify-between text-white/60">
          <span>VAT (7.5%)</span>
          <span>{formatNaira(vatAmount)}</span>
        </div>
        <div className="flex justify-between text-lg font-bold pt-1">
          <span>Total</span>
          <span>{formatNaira(total)}</span>
        </div>
      </div>

      <div className="p-4">
        <button
          onClick={onCheckout}
          disabled={lines.length === 0}
          className="tap-target w-full rounded-2xl bg-brand-red disabled:opacity-30 py-4 text-lg font-bold"
        >
          Checkout
        </button>
      </div>
    </div>
  );
}
