import type { TableSummary } from "../types";
import { formatNaira } from "../lib/format";

interface Props {
  table: TableSummary;
  onSelect: () => void;
}

const STATUS_STYLE: Record<TableSummary["status"], { border: string; bg: string; label: string }> = {
  empty: { border: "border-white/15", bg: "bg-brand-surface", label: "Empty" },
  open: { border: "border-brand-red", bg: "bg-brand-red/10", label: "Occupied" },
  bill_requested: { border: "border-amber-400", bg: "bg-amber-400/10", label: "Bill Requested" },
  closed: { border: "border-white/15", bg: "bg-brand-surface", label: "Empty" },
};

export default function TableTile({ table, onSelect }: Props) {
  const style = STATUS_STYLE[table.status];

  return (
    <button
      onClick={onSelect}
      className={`tap-target aspect-square rounded-2xl border-2 ${style.border} ${style.bg} p-4 flex flex-col items-center justify-center text-center shadow-md`}
    >
      <div className="text-lg font-bold">{table.label}</div>
      <div className="text-xs mt-1 uppercase tracking-wide text-white/50">{style.label}</div>
      {table.status !== "empty" && (
        <>
          <div className="text-brand-red font-bold mt-2">{formatNaira(table.running_total)}</div>
          <div className="text-[11px] text-white/40">{table.item_count} item{table.item_count === 1 ? "" : "s"}</div>
        </>
      )}
    </button>
  );
}
