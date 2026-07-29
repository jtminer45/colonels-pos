import { createContext, useContext, useState, useMemo, type ReactNode } from "react";
import type { CartLine } from "../types";

const VAT_RATE = 0.075;

interface CartContextValue {
  lines: CartLine[];
  addLine: (line: Omit<CartLine, "quantity">, quantity?: number) => void;
  incrementLine: (itemVariantId: number) => void;
  decrementLine: (itemVariantId: number) => void;
  removeLine: (itemVariantId: number) => void;
  clear: () => void;
  subtotal: number;
  vatAmount: number;
  total: number;
}

const CartContext = createContext<CartContextValue | undefined>(undefined);

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);

  function addLine(line: Omit<CartLine, "quantity">, quantity = 1) {
    setLines((prev) => {
      const existing = prev.find((l) => l.itemVariantId === line.itemVariantId);
      if (existing) {
        return prev.map((l) =>
          l.itemVariantId === line.itemVariantId ? { ...l, quantity: l.quantity + quantity } : l
        );
      }
      return [...prev, { ...line, quantity }];
    });
  }

  function incrementLine(itemVariantId: number) {
    setLines((prev) =>
      prev.map((l) => (l.itemVariantId === itemVariantId ? { ...l, quantity: l.quantity + 1 } : l))
    );
  }

  function decrementLine(itemVariantId: number) {
    setLines((prev) =>
      prev
        .map((l) => (l.itemVariantId === itemVariantId ? { ...l, quantity: l.quantity - 1 } : l))
        .filter((l) => l.quantity > 0)
    );
  }

  function removeLine(itemVariantId: number) {
    setLines((prev) => prev.filter((l) => l.itemVariantId !== itemVariantId));
  }

  function clear() {
    setLines([]);
  }

  const subtotal = useMemo(() => round2(lines.reduce((sum, l) => sum + l.unitPrice * l.quantity, 0)), [lines]);
  const vatAmount = useMemo(() => round2(subtotal * VAT_RATE), [subtotal]);
  const total = useMemo(() => round2(subtotal + vatAmount), [subtotal, vatAmount]);

  return (
    <CartContext.Provider
      value={{ lines, addLine, incrementLine, decrementLine, removeLine, clear, subtotal, vatAmount, total }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}
