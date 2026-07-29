import type { Category } from "../types";

interface Props {
  category: Category;
  active: boolean;
  onSelect: () => void;
}

export default function CategoryTile({ category, active, onSelect }: Props) {
  return (
    <button
      onClick={onSelect}
      className="tap-target shrink-0 rounded-2xl px-5 py-4 min-w-[140px] text-left font-semibold text-white shadow-md"
      style={{
        backgroundColor: category.colour_hex,
        outline: active ? "3px solid white" : "none",
        opacity: active ? 1 : 0.85,
      }}
    >
      <div className="text-base leading-tight">{category.name}</div>
      <div className="text-xs opacity-80 mt-1">{category.items.length} items</div>
    </button>
  );
}
