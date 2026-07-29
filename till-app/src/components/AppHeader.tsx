import { useAuth } from "../contexts/AuthContext";
import { useShiftSummary } from "../hooks/useShiftSummary";
import { formatNaira } from "../lib/format";

export type AppMode = "quick" | "tables";

interface Props {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
}

export default function AppHeader({ mode, onModeChange }: Props) {
  const { user, logout } = useAuth();
  const { summary } = useShiftSummary();

  async function handleClockOut() {
    if (!confirm("Clock out and end this shift?")) return;
    await logout();
  }

  return (
    <header className="flex items-center justify-between px-4 py-3 bg-brand-surface border-b border-white/10 shrink-0 gap-4">
      <div className="flex items-center gap-3 shrink-0">
        <img src="/logo.png" alt="" className="w-9 h-9 rounded-lg object-cover" />
        <div>
          <div className="font-semibold text-sm leading-tight">Colonels Restaurant &amp; Garden</div>
          <div className="text-xs text-white/40">{user?.username}</div>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-brand-navy rounded-xl p-1 shrink-0">
        <button
          onClick={() => onModeChange("quick")}
          className={`tap-target px-4 py-2 rounded-lg text-sm font-semibold ${
            mode === "quick" ? "bg-brand-red text-white" : "text-white/50"
          }`}
        >
          Quick Sale
        </button>
        <button
          onClick={() => onModeChange("tables")}
          className={`tap-target px-4 py-2 rounded-lg text-sm font-semibold ${
            mode === "tables" ? "bg-brand-red text-white" : "text-white/50"
          }`}
        >
          Tables
        </button>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <div className="text-right">
          <div className="text-xs text-white/40">This Shift</div>
          <div className="font-semibold text-sm">
            {summary ? formatNaira(summary.total_sales) : "—"}
            <span className="text-white/40 font-normal"> · {summary?.sale_count ?? 0} sales</span>
          </div>
        </div>
        <button
          onClick={handleClockOut}
          className="tap-target rounded-xl border border-brand-red text-brand-red px-4 py-2 text-sm font-semibold"
        >
          Clock Out
        </button>
      </div>
    </header>
  );
}
