import type { MenuItem } from "../types";
import { formatNaira } from "../lib/format";

interface Props {
  item: MenuItem;
  onAddSingleVariant: (item: MenuItem) => void;
  onOpenVariants: (item: MenuItem) => void;
}

export default function ItemTile({ item, onAddSingleVariant, onOpenVariants }: Props) {
  const allSoldOut = item.variants.length > 0 && item.variants.every((v) => v.sold_out);
  const singleVariant = item.variants.length === 1;
  const prices = item.variants.map((v) => v.price);
  const priceLabel =
    singleVariant || prices.length === 0
      ? formatNaira(prices[0] ?? 0)
      : `${formatNaira(Math.min(...prices))} – ${formatNaira(Math.max(...prices))}`;

  function handleTap() {
    if (allSoldOut) return;
    if (singleVariant) {
      onAddSingleVariant(item);
    } else {
      onOpenVariants(item);
    }
  }

  return (
    <button
      onClick={handleTap}
      disabled={allSoldOut}
      className="tap-target relative rounded-2xl overflow-hidden bg-brand-surface border border-white/10 text-left shadow-md disabled:opacity-50"
    >
      <div className="aspect-[4/3] w-full bg-brand-surface2">
        {item.base_photo_url && (
          <img
            src={`/menu_photos/${item.base_photo_url}`}
            alt=""
            className="w-full h-full object-cover"
            draggable={false}
          />
        )}
      </div>
      <div className="p-3">
        <div className="font-semibold leading-tight">{item.name}</div>
        <div className="text-brand-red font-bold mt-1">{priceLabel}</div>
      </div>
      {allSoldOut && (
        <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
          <span className="text-white font-bold text-lg tracking-wide border-2 border-white rounded-lg px-3 py-1 -rotate-6">
            SOLD OUT
          </span>
        </div>
      )}
    </button>
  );
}
