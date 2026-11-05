import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { productSubtotal } from "../api";
import type { Product } from "../types";

export interface CartLine {
  product: Product;
  quantity: number;
}

interface CartContextValue {
  lines: CartLine[];
  count: number;
  total: bigint;
  add: (product: Product, quantity: number) => void;
  update: (productId: number, quantity: number) => void;
  remove: (productId: number) => void;
  clear: () => void;
}

const storageKey = "superalimentos-cart";
const CartContext = createContext<CartContextValue | null>(null);

function readCart(): CartLine[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    if (!Array.isArray(saved)) return [];
    return saved.filter(
      (line): line is CartLine =>
        typeof line?.product?.id === "number" &&
        typeof line?.product?.price === "string" &&
        typeof line?.quantity === "number",
    );
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(readCart);

  const persist = useCallback((next: CartLine[]) => {
    setLines(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
  }, []);

  const add = useCallback(
    (product: Product, quantity: number) => {
      if (!Number.isSafeInteger(quantity) || quantity <= 0) return;
      const current = lines.find((line) => line.product.id === product.id);
      persist(
        current
          ? lines.map((line) =>
              line.product.id === product.id
                ? { product, quantity: line.quantity + quantity }
                : line,
            )
          : [...lines, { product, quantity }],
      );
    },
    [lines, persist],
  );

  const update = useCallback(
    (productId: number, quantity: number) => {
      if (!Number.isSafeInteger(quantity) || quantity <= 0) {
        persist(lines.filter((line) => line.product.id !== productId));
        return;
      }
      persist(
        lines.map((line) =>
          line.product.id === productId ? { ...line, quantity } : line,
        ),
      );
    },
    [lines, persist],
  );

  const remove = useCallback(
    (productId: number) =>
      persist(lines.filter((line) => line.product.id !== productId)),
    [lines, persist],
  );

  const clear = useCallback(() => persist([]), [persist]);

  const value = useMemo(
    () => ({
      lines,
      count: lines.length,
      total: lines.reduce(
        (sum, line) => sum + productSubtotal(line.product, line.quantity),
        0n,
      ),
      add,
      update,
      remove,
      clear,
    }),
    [lines, add, update, remove, clear],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const value = useContext(CartContext);
  if (!value) throw new Error("useCart debe usarse dentro de CartProvider.");
  return value;
}
