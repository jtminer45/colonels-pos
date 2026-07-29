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

  // A manager-uploaded photo is stored as a full URL to the backend's
  // photo endpoint; a bundled/curated photo is a bare filename resolved
  // against this app's own public/menu_photos/ folder.
  const photoSrc = item.base_photo_url
    ? item.base_photo_url.startsWith("http")
      ? item.base_photo_url
      : `/menu_photos/${item.base_photo_url}`
    : null;

  return (
    <button
      onClick={handleTap}
      disabled={allSoldOut}
      className="tap-target relative flex flex-col rounded-2xl overflow-hidden bg-brand-surface border border-white/10 text-left shadow-lg disabled:opacity-50"
    >
      {/* Square crop handles the mixed portrait/landscape/square source
          photos consistently, centered and cropped rather than distorted. */}
      <div className="aspect-square w-full bg-brand-surface2 overflow-hidden">
        {photoSrc && (
          <img
            src={photoSrc}
            alt=""
            className="w-full h-full object-cover object-center"
            draggable={false}
            loading="lazy"
          />
        )}
      </div>
      <div className="p-3 flex-1 flex flex-col justify-between">
        <div className="font-semibold leading-tight text-[15px]">{item.name}</div>
        <div className="text-brand-red font-bold mt-1 text-sm">{priceLabel}</div>
      </div>
      {allSoldOut && (
        <div className="absolute inset-0 bg-black/75 flex items-center justify-center">
          <span className="text-white font-bold text-base tracking-wide border-2 border-white rounded-lg px-3 py-1 -rotate-6">
            SOLD OUT
          </span>
        </div>
      )}
    </button>
  );
}
