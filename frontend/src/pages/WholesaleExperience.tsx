import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchStoreConfig,
  fetchWholesalePrices,
  formatCLP,
} from "../api";
import type { StoreConfig, WholesalePrice } from "../types";

type PurchaseOption = { label: string; total: number };
type WholesaleCartLine = {
  key: string;
  item: WholesalePrice;
  option: PurchaseOption;
  quantity: number;
};

const spanishCollator = new Intl.Collator("es-CL", {
  numeric: true,
  sensitivity: "base",
});

function purchaseOptions(item: WholesalePrice): PurchaseOption[] {
  const options: PurchaseOption[] = [];
  const isKilogram = item.price_unit === "kg";
  const base = item.price === null ? null : Number(item.price);
  if (base !== null && Number.isFinite(base) && base > 0) {
    options.push({ label: isKilogram ? "1 kg" : "1 unidad", total: base });
  }
  const price250g = item.price_250g === null ? null : Number(item.price_250g);
  if (isKilogram && price250g !== null && price250g > 0) {
    options.push({ label: "250 g", total: price250g });
  }
  const price5kg = item.price_5kg === null ? null : Number(item.price_5kg);
  if (isKilogram && price5kg !== null && price5kg > 0) {
    options.push({ label: "5 kg", total: price5kg * 5 });
  }
  const price10kg = item.price_10kg === null ? null : Number(item.price_10kg);
  if (isKilogram && price10kg !== null && price10kg > 0) {
    options.push({ label: "10 kg", total: price10kg * 10 });
  }
  const closedPrice = item.closed_price === null ? null : Number(item.closed_price);
  const match = item.closed_format.match(/^(\d+(?:[.,]\d+)?)\s*([kKuU])$/);
  if (closedPrice !== null && closedPrice > 0 && match) {
    const quantity = Number(match[1].replace(",", "."));
    const isKgFormat = match[2].toLocaleLowerCase("es") === "k";
    const format = isKgFormat ? `${quantity} kg` : `${quantity} unidades`;
    options.push({
      label: `Cerrado · ${format}`,
      total: closedPrice * quantity,
    });
  }
  return options;
}

function formatTotal(cart: WholesaleCartLine[]) {
  return cart.reduce((sum, line) => sum + line.option.total * line.quantity, 0);
}

export function WholesaleExperience() {
  const [prices, setPrices] = useState<WholesalePrice[]>([]);
  const [storeConfig, setStoreConfig] = useState<StoreConfig | null>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [note, setNote] = useState("");
  const [cart, setCart] = useState<WholesaleCartLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const cartDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    Promise.all([fetchWholesalePrices(), fetchStoreConfig()])
      .then(([nextPrices, config]) => {
        setPrices(nextPrices);
        setStoreConfig(config);
      })
      .catch((cause: unknown) =>
        setError(
          cause instanceof Error
            ? cause.message
            : "No se pudo consultar la lista mayorista.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(() => {
    const seen = new Map<string, number>();
    prices.forEach((item) => {
      if (!seen.has(item.category_name)) {
        seen.set(item.category_name, item.category_sort_order);
      }
    });
    return [...seen.entries()].sort(
      ([leftName, leftOrder], [rightName, rightOrder]) =>
        leftOrder - rightOrder || spanishCollator.compare(leftName, rightName),
    );
  }, [prices]);

  const visiblePrices = useMemo(
    () =>
      prices
        .filter((item) => {
          const matchesSearch = `${item.product_name} ${item.category_name}`
            .toLocaleLowerCase("es")
            .includes(search.trim().toLocaleLowerCase("es"));
          return matchesSearch && (!categoryFilter || item.category_name === categoryFilter);
        })
        .slice()
        .sort(
          (left, right) =>
            left.category_sort_order - right.category_sort_order ||
            spanishCollator.compare(left.category_name, right.category_name) ||
            spanishCollator.compare(left.product_name, right.product_name),
        ),
    [prices, search, categoryFilter],
  );

  const groups = useMemo(() => {
    const grouped = new Map<string, WholesalePrice[]>();
    visiblePrices.forEach((item) => {
      const current = grouped.get(item.category_name) ?? [];
      current.push(item);
      grouped.set(item.category_name, current);
    });
    return [...grouped.entries()];
  }, [visiblePrices]);

  function addToCart(item: WholesalePrice, option: PurchaseOption) {
    const key = `${item.id}:${option.label}`;
    setCart((current) => {
      const existing = current.find((line) => line.key === key);
      if (existing) {
        return current.map((line) =>
          line.key === key ? { ...line, quantity: line.quantity + 1 } : line,
        );
      }
      return [...current, { key, item, option, quantity: 1 }];
    });
  }

  function changeQuantity(key: string, amount: number) {
    setCart((current) =>
      current
        .map((line) =>
          line.key === key ? { ...line, quantity: line.quantity + amount } : line,
        )
        .filter((line) => line.quantity > 0),
    );
  }

  function sendOrder() {
    const number = storeConfig?.whatsapp_number.replace(/\D/g, "") ?? "";
    if (!number || cart.length === 0) return;
    const lines = cart.map(
      (line) =>
        `- ${line.quantity} x ${line.item.product_name} (${line.option.label}) = ${formatCLP(line.option.total * line.quantity)}`,
    );
    const message = [
      "Hola, quiero hacer este pedido mayorista a Siempre Natural:",
      "",
      ...lines,
      "",
      `Subtotal de productos: ${formatCLP(formatTotal(cart))}`,
      note.trim() ? `Nota: ${note.trim()}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    window.open(
      `https://wa.me/${number}?text=${encodeURIComponent(message)}`,
      "_blank",
      "noopener,noreferrer",
    );
  }

  const cartQuantity = cart.reduce((sum, line) => sum + line.quantity, 0);
  const hasFilters = Boolean(search.trim() || categoryFilter);

  return (
    <main className="wholesale-page">
      <header className="wholesale-hero">
        <div className="wholesale-hero-inner">
          <img className="wholesale-logo" src="/logo-siempre-natural.png" alt="Logo Siempre Natural" />
          <div className="wholesale-brand-copy">
            <p className="wholesale-brand-name">SIEMPRE NATURAL</p>
            <h1>Lista de precios mayorista</h1>
            <p className="wholesale-subtitle">Precios en pesos chilenos (CLP)</p>
          </div>
          <span className="wholesale-currency">CLP</span>
        </div>
      </header>

      <div className="wholesale-wrap">
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {loading ? (
          <p className="wholesale-intro" role="status">Cargando la lista mayorista…</p>
        ) : (
          <>
            <p className="wholesale-intro">
              Precios mayoristas disponibles para todos. Busca un producto o explora las categorías.
            </p>
            <div className="wholesale-account-bar">
              <p>Lista de precios mayorista de acceso público.</p>
            </div>
            <div className="wholesale-tools" role="search">
              <label className="wholesale-search-box">
                <span aria-hidden="true">⌕</span>
                <span className="sr-only">Buscar producto</span>
                <input
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Buscar producto"
                  type="search"
                  value={search}
                />
              </label>
              <label className="wholesale-select-box">
                <span className="sr-only">Filtrar por categoría</span>
                <select onChange={(event) => setCategoryFilter(event.target.value)} value={categoryFilter}>
                  <option value="">Todas las categorías</option>
                  {categories.map(([category]) => (
                    <option key={category} value={category}>{category}</option>
                  ))}
                </select>
              </label>
            </div>
            <p className="wholesale-result-count" aria-live="polite">
              {hasFilters
                ? `${visiblePrices.length} productos`
                : `${prices.length} productos en ${categories.length} categorías`}
            </p>

            {groups.length ? (
              <div className="wholesale-categories">
                {groups.map(([category, items], index) => (
                  <details className="wholesale-category" open={index === 0 || hasFilters} key={category}>
                    <summary>
                      <span>{category}</span>
                      <span className="wholesale-category-count">{items.length} productos</span>
                    </summary>
                    <div className="wholesale-cards">
                      {items.map((item) => {
                        const options = purchaseOptions(item);
                        const unavailable = options.length === 0;
                        return (
                          <article className="wholesale-card" key={item.id}>
                            <div className="wholesale-card-top">
                              <h2>{item.product_name}</h2>
                              <div className="wholesale-main-price">
                                <strong>{unavailable ? "No disponible" : formatCLP(item.price ?? "")}</strong>
                                <span>{unavailable ? "temporalmente" : item.price_unit === "kg" ? "por kg" : "por unidad"}</span>
                              </div>
                            </div>
                            {unavailable ? (
                              <p className="wholesale-unavailable">No se puede agregar al pedido por ahora.</p>
                            ) : (
                              <div className="wholesale-options" aria-label={`Opciones de compra para ${item.product_name}`}>
                                {options.map((option) => (
                                  <button
                                    className="wholesale-option"
                                    key={option.label}
                                    onClick={() => addToCart(item, option)}
                                    type="button"
                                  >
                                    {option.label} · {formatCLP(option.total)}
                                  </button>
                                ))}
                              </div>
                            )}
                          </article>
                        );
                      })}
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <div className="wholesale-empty">
                <h2>No encontramos productos con esos filtros</h2>
                <p>Prueba con otro nombre o categoría.</p>
              </div>
            )}
            <p className="wholesale-disclaimer">
              Los precios se muestran según la lista mayorista vigente. Confirma disponibilidad,
              cantidades y condiciones de compra con la tienda.
            </p>

            <button
              className="wholesale-cart-float"
              onClick={() => cartDialog.current?.showModal()}
              type="button"
            >
              <span className="wholesale-cart-copy">
                <strong>{cartQuantity ? `${cartQuantity} ${cartQuantity === 1 ? "producto" : "productos"} en tu pedido` : "Tu pedido está vacío"}</strong>
                <span>{cartQuantity ? `Subtotal: ${formatCLP(formatTotal(cart))}` : "Elige un formato para agregar productos"}</span>
              </span>
              <span className="wholesale-cart-cta">Ver pedido</span>
            </button>

            <dialog
              className="wholesale-cart-dialog"
              onClick={(event) => {
                if (event.target === event.currentTarget) cartDialog.current?.close();
              }}
              ref={cartDialog}
            >
              <div className="wholesale-cart-head">
                <h2>Tu pedido</h2>
                <button className="wholesale-cart-close" onClick={() => cartDialog.current?.close()} type="button" aria-label="Cerrar">
                  ×
                </button>
              </div>
              <div className="wholesale-cart-body">
                {cart.length ? cart.map((line) => (
                  <div className="wholesale-cart-line" key={line.key}>
                    <div>
                      <p>{line.item.product_name}</p>
                      <span>{line.option.label} · {formatCLP(line.option.total)} c/u</span>
                      <div className="wholesale-quantity-controls">
                        <button onClick={() => changeQuantity(line.key, -1)} type="button" aria-label={`Quitar una unidad de ${line.item.product_name}`}>−</button>
                        <strong>{line.quantity}</strong>
                        <button onClick={() => changeQuantity(line.key, 1)} type="button" aria-label={`Agregar una unidad de ${line.item.product_name}`}>+</button>
                        <button className="wholesale-remove" onClick={() => setCart((current) => current.filter((item) => item.key !== line.key))} type="button">Quitar</button>
                      </div>
                    </div>
                    <strong className="wholesale-line-total">{formatCLP(line.option.total * line.quantity)}</strong>
                  </div>
                )) : (
                  <p className="wholesale-cart-empty">Todavía no agregas productos.</p>
                )}
              </div>
              <div className="wholesale-cart-foot">
                <div className="wholesale-subtotal">
                  <span>Subtotal de productos</span>
                  <strong>{formatCLP(formatTotal(cart))}</strong>
                </div>
                <label className="sr-only" htmlFor="wholesale-order-note">Nota para la tienda (opcional)</label>
                <textarea
                  id="wholesale-order-note"
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Nota para la tienda (opcional)"
                  value={note}
                />
                <button
                  className="wholesale-send-order"
                  disabled={!cart.length || !storeConfig?.whatsapp_number}
                  onClick={sendOrder}
                  type="button"
                >
                  Enviar pedido por WhatsApp
                </button>
                <p>
                  {storeConfig?.whatsapp_number
                    ? "Se abrirá WhatsApp con el detalle para que confirmes el envío."
                    : "El número de WhatsApp de la tienda aún no está configurado."}
                </p>
              </div>
            </dialog>
          </>
        )}
        <footer className="wholesale-footer">Siempre Natural · Lista mayorista en CLP</footer>
      </div>
    </main>
  );
}
