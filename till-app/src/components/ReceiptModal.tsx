import { useState } from "react";
import type { Receipt, SaleLineResult } from "../types";
import { formatNaira } from "../lib/format";
import { api, ApiError } from "../api/client";
import VoidReasonModal from "./VoidReasonModal";



interface Props {
  receipt: Receipt;
  onDone: () => void;
}

/**
 * Printing: this calls window.print(), which opens the browser/OS print
 * dialog against whatever printer is configured as default. A physical
 * USB or Bluetooth thermal receipt printer must be connected and installed
 * at the OS level (most ship a driver that registers them as a normal
 * system printer) for an actual receipt to come out — there is no raw
 * ESC/POS byte-level printer integration here. #print-receipt is styled
 * (see index.css @media print) to lay out like a narrow receipt slip.
 */
function printReceipt() {
  window.print();
}

export default function ReceiptModal({ receipt, onDone }: Props) {
  const lines: SaleLineResult[] = receipt.lines;
  const [voidedIds, setVoidedIds] = useState<Set<number>>(new Set());
  const [voidTarget, setVoidTarget] = useState<SaleLineResult | null>(null);
  const [voiding, setVoiding] = useState(false);
  const [voidError, setVoidError] = useState<string | null>(null);

  const activeLines = lines.filter((l) => !voidedIds.has(l.sale_item_id));
  const subtotal = activeLines.reduce((sum, l) => sum + l.line_total, 0);
  const vatAmount = Math.round(subtotal * 0.075 * 100) / 100;
  const total = Math.round((subtotal + vatAmount) * 100) / 100;

  async function handleVoidConfirm(reason: string) {
    if (!voidTarget) return;
    setVoiding(true);
    setVoidError(null);
    try {
      await api.voidSaleItem(voidTarget.sale_item_id, reason);
      setVoidedIds((prev) => new Set(prev).add(voidTarget.sale_item_id));
      setVoidTarget(null);
    } catch (e) {
      setVoidError(e instanceof ApiError ? e.message : "Could not void this item.");
    } finally {
      setVoiding(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 px-4 print:bg-white print:static">
      <div className="w-full max-w-sm bg-brand-surface rounded-3xl p-6 shadow-2xl print:shadow-none print:bg-white print:text-black print:rounded-none">
        <div id="print-receipt">
          <div className="text-center mb-4">
            <h2 className="font-bold text-lg">Colonel's Bakery &amp; Restaurant</h2>
            <p className="text-xs text-white/50 print:text-black">Sale #{receipt.sale_id} · {receipt.timestamp}</p>
            <p className="text-xs text-white/50 print:text-black">
              Served by {receipt.staff_username} · {receipt.payment_method.toUpperCase()}
            </p>
          </div>

          <div className="space-y-2 mb-4 border-t border-b border-white/10 print:border-black py-3">
            {lines.map((l) => {
              const voided = voidedIds.has(l.sale_item_id);
              return (
                <div key={l.sale_item_id} className={`flex justify-between text-sm ${voided ? "opacity-40 line-through" : ""}`}>
                  <div className="pr-2">
                    <div>
                      {l.quantity} × {l.item_name} ({l.variant_label})
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>{formatNaira(l.line_total)}</span>
                    {!voided && (
                      <button
                        onClick={() => setVoidTarget(l)}
                        className="tap-target text-xs text-brand-red border border-brand-red/40 rounded px-2 py-0.5 print:hidden"
                      >
                        Void
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="space-y-1 text-sm mb-2">
            <div className="flex justify-between text-white/60 print:text-black">
              <span>Subtotal</span>
              <span>{formatNaira(subtotal)}</span>
            </div>
            <div className="flex justify-between text-white/60 print:text-black">
              <span>VAT (7.5%)</span>
              <span>{formatNaira(vatAmount)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold pt-1">
              <span>Total</span>
              <span>{formatNaira(total)}</span>
            </div>
          </div>
        </div>

        {voidError && (
          <div className="text-brand-red text-sm bg-brand-red/10 border border-brand-red/30 rounded-lg px-3 py-2 mb-3 print:hidden">
            {voidError}
          </div>
        )}

        <div className="flex gap-3 mt-4 print:hidden">
          <button
            onClick={printReceipt}
            className="tap-target flex-1 rounded-2xl border border-white/15 py-4 font-semibold"
          >
            🖨️ Print
          </button>
          <button
            onClick={onDone}
            className="tap-target flex-1 rounded-2xl bg-brand-red py-4 font-semibold"
          >
            New Sale
          </button>
        </div>
      </div>

      {voidTarget && (
        <VoidReasonModal
          itemLabel={`${voidTarget.quantity} × ${voidTarget.item_name} (${voidTarget.variant_label})`}
          onConfirm={handleVoidConfirm}
          onClose={() => setVoidTarget(null)}
          submitting={voiding}
        />
      )}
    </div>
  );
}
