import type { TableOrderDetail } from "../types";
import { formatNaira } from "../lib/format";

interface Props {
  order: TableOrderDetail;
  onClose: () => void;
}

/**
 * A pre-payment bill for the table to review — NOT proof of payment. The
 * payment receipt (ReceiptModal) only appears after checkout actually
 * succeeds. Printing here uses the same window.print() approach as the
 * payment receipt — see ReceiptModal.tsx for the printer requirements.
 */
function printBill() {
  window.print();
}

export default function BillModal({ order, onClose }: Props) {
  const activeLines = order.items.filter((l) => !l.is_voided);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 px-4 print:bg-white print:static">
      <div className="w-full max-w-sm bg-brand-surface rounded-3xl p-6 shadow-2xl print:shadow-none print:bg-white print:text-black print:rounded-none">
        <div id="print-receipt">
          <div className="text-center mb-1">
            <span className="inline-block text-xs font-bold tracking-widest uppercase bg-amber-400/20 text-amber-300 print:bg-transparent print:text-black rounded px-2 py-0.5">
              Bill — Not a Receipt
            </span>
          </div>
          <div className="text-center mb-4 mt-2">
            <h2 className="font-bold text-lg">Colonels Restaurant &amp; Garden</h2>
            <p className="text-xs text-white/50 print:text-black">{order.table_label}</p>
          </div>

          <div className="space-y-2 mb-4 border-t border-b border-white/10 print:border-black py-3">
            {activeLines.map((l) => (
              <div key={l.table_order_item_id} className="flex justify-between text-sm">
                <span>
                  {l.quantity} × {l.item_name} ({l.variant_label})
                </span>
                <span>{formatNaira(l.unit_price * l.quantity)}</span>
              </div>
            ))}
          </div>

          <div className="space-y-1 text-sm mb-2">
            <div className="flex justify-between text-white/60 print:text-black">
              <span>Subtotal</span>
              <span>{formatNaira(order.subtotal)}</span>
            </div>
            <div className="flex justify-between text-white/60 print:text-black">
              <span>VAT (7.5%)</span>
              <span>{formatNaira(order.vat_amount)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold pt-1">
              <span>To Pay</span>
              <span>{formatNaira(order.total)}</span>
            </div>
          </div>
        </div>

        <div className="flex gap-3 mt-4 print:hidden">
          <button onClick={onClose} className="tap-target flex-1 rounded-2xl border border-white/15 py-4 font-semibold">
            Close
          </button>
          <button onClick={printBill} className="tap-target flex-1 rounded-2xl bg-brand-red py-4 font-semibold">
            🖨️ Print
          </button>
        </div>
      </div>
    </div>
  );
}
