import { useState } from "react";

interface Props {
  itemLabel: string;
  onConfirm: (reason: string) => void;
  onClose: () => void;
  submitting: boolean;
}

const COMMON_REASONS = ["Rang up wrong item", "Customer changed mind", "Duplicate entry", "Other"];

export default function VoidReasonModal({ itemLabel, onConfirm, onClose, submitting }: Props) {
  const [reason, setReason] = useState("");
  const [customReason, setCustomReason] = useState("");

  const finalReason = reason === "Other" ? customReason : reason;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-sm bg-brand-surface rounded-3xl p-6 shadow-2xl">
        <h2 className="text-lg font-semibold mb-1">Void Item</h2>
        <p className="text-sm text-white/50 mb-4">{itemLabel}</p>

        <div className="space-y-2 mb-4">
          {COMMON_REASONS.map((r) => (
            <button
              key={r}
              onClick={() => setReason(r)}
              className="tap-target w-full text-left rounded-xl border px-4 py-3"
              style={{
                borderColor: reason === r ? "#C61D24" : "rgba(255,255,255,0.1)",
                backgroundColor: reason === r ? "rgba(198,29,36,0.15)" : "transparent",
              }}
            >
              {r}
            </button>
          ))}
        </div>

        {reason === "Other" && (
          <input
            className="w-full rounded-xl bg-brand-surface2 border border-white/10 px-4 py-3 mb-4 outline-none focus:border-brand-red"
            placeholder="Reason for void"
            value={customReason}
            onChange={(e) => setCustomReason(e.target.value)}
          />
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={submitting}
            className="tap-target flex-1 rounded-2xl border border-white/15 py-3 font-semibold text-white/70"
          >
            Cancel
          </button>
          <button
            onClick={() => finalReason.trim() && onConfirm(finalReason.trim())}
            disabled={!finalReason.trim() || submitting}
            className="tap-target flex-1 rounded-2xl bg-brand-red disabled:opacity-30 py-3 font-semibold"
          >
            {submitting ? "Voiding…" : "Confirm Void"}
          </button>
        </div>
      </div>
    </div>
  );
}
