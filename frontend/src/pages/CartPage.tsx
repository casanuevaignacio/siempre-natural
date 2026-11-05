import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  createOrder,
  fetchCustomerSession,
  formatCLP,
  minimumQuantity,
  productSubtotal,
} from "../api";
import { useCart } from "../cart/CartContext";
import type { OrderRequest } from "../types";

export function CartPage() {
  const { lines, total, update, remove, clear } = useCart();
  const navigate = useNavigate();
  const [deliveryMode, setDeliveryMode] = useState<"pickup" | "shipping">("pickup");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerSessionLoading, setCustomerSessionLoading] = useState(true);
  const [customerSessionError, setCustomerSessionError] = useState("");
  const hasValidQuantities = lines.every(
    ({ product, quantity }) => quantity >= minimumQuantity(product),
  );
  const [form, setForm] = useState({
    customer_name: "",
    customer_phone: "",
    customer_email: "",
    customer_rut: "",
    delivery_address: "",
    notes: "",
  });

  useEffect(() => {
    fetchCustomerSession()
      .then((session) => {
        if (session.is_authenticated) {
          setCustomerEmail(session.email);
          setForm((current) => ({ ...current, customer_email: session.email }));
        }
      })
      .catch((cause: unknown) => {
        setCustomerEmail("");
        setCustomerSessionError(
          cause instanceof Error
            ? cause.message
            : "No se pudo consultar la sesión de cliente.",
        );
      })
      .finally(() => setCustomerSessionLoading(false));
  }, []);

  function updateField(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload: OrderRequest = {
      ...form,
      delivery_mode: deliveryMode,
      items: lines.map(({ product, quantity }) =>
        product.sale_unit === "kg"
          ? { product_id: product.id, quantity_grams: quantity }
          : { product_id: product.id, quantity_units: quantity },
      ),
    };
    try {
      const order = await createOrder(payload);
      const message = [
        `Hola, registré el pedido ${order.id}.`,
        ...lines.map(({ product, quantity }) =>
          `• ${product.name}: ${quantity} ${product.sale_unit === "kg" ? "g" : "un."}`,
        ),
        `Total informado: ${formatCLP(order.total)}`,
        `Entrega: ${deliveryMode === "pickup" ? "retiro" : "despacho"}`,
      ].join("\n");
      const storedOrder = {
        ...order,
        whatsappMessage: message,
        lines: lines.map(({ product, quantity }) => ({ name: product.name, quantity, unit: product.sale_unit })),
        deliveryMode,
      };
      clear();
      navigate(`/confirmacion/${order.id}`, { state: storedOrder });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No fue posible registrar el pedido.");
    } finally {
      setBusy(false);
    }
  }

  if (!lines.length) {
    return (
      <main className="page-main">
        <section className="container empty-state cart-empty">
          <span className="empty-art" aria-hidden="true">♧</span>
          <h1>Tu carrito está vacío</h1>
          <p>Explora el catálogo para agregar productos disponibles.</p>
          <Link className="button" to="/catalogo">Ir al catálogo</Link>
        </section>
      </main>
    );
  }

  return (
    <main className="page-main">
      <section className="container page-heading">
        <span className="section-kicker">Un último paso</span>
        <h1>Tu carrito</h1>
        <p>El precio final se valida nuevamente al registrar el pedido.</p>
      </section>
      <div className="container checkout-layout">
        <section className="cart-items" aria-label="Productos en el carrito">
          {lines.map(({ product, quantity }) => (
            <article className="cart-item" key={product.id}>
              <div className="cart-item-info">
                <h2>{product.name}</h2>
                <span>
                  {product.sale_unit === "kg" && product.price_250g
                    ? `${formatCLP(product.price_250g)} / 250 g · ${formatCLP(product.price)} / kg`
                    : `${formatCLP(product.price)} / ${product.sale_unit === "kg" ? "kg" : product.package_label || "unidad"}`}
                </span>
              </div>
              <label>
                <span className="sr-only">Cantidad de {product.name}</span>
                <input
                  min={minimumQuantity(product)}
                  onChange={(event) => update(product.id, Number(event.target.value))}
                  type="number"
                  value={quantity}
                />
              </label>
              <strong>
                {quantity >= minimumQuantity(product)
                  ? formatCLP(productSubtotal(product, quantity))
                  : `Mínimo ${minimumQuantity(product)} ${product.sale_unit === "kg" ? "g" : "un."}`}
              </strong>
              <button className="remove-button" onClick={() => remove(product.id)} type="button">Quitar</button>
            </article>
          ))}
          <div className="cart-total"><span>Total estimado</span><strong>{hasValidQuantities ? formatCLP(total) : "Completa las cantidades mínimas"}</strong></div>
          <p className="form-hint">El total es estimado y el costo de despacho se confirma por WhatsApp. No se realiza un cobro en línea.</p>
        </section>

        <form className="checkout-form" onSubmit={submit}>
          <h2>Datos para tu pedido</h2>
          {customerSessionError && (
            <div className="notice notice-error" role="status">
              No se pudo comprobar si tienes una cuenta. Puedes continuar como
              invitado ingresando el correo asociado a tu pedido. {customerSessionError}
            </div>
          )}
          <label>Nombre completo <input autoComplete="name" maxLength={160} onChange={(event) => updateField("customer_name", event.target.value)} required value={form.customer_name} /></label>
          <label>Teléfono de contacto <input autoComplete="tel" maxLength={32} onChange={(event) => updateField("customer_phone", event.target.value)} required value={form.customer_phone} /></label>
          <label>
            Correo electrónico
            <input
              autoComplete="email"
              onChange={(event) => updateField("customer_email", event.target.value)}
              readOnly={Boolean(customerEmail)}
              required
              type="email"
              value={form.customer_email}
            />
          </label>
          {!customerSessionLoading && !customerEmail && (
            <p className="form-hint">
              El correo es necesario para coordinar el pedido y, si luego creas
              una cuenta verificada con esta dirección, añadirlo a tu historial.
              ¿Ya tienes cuenta? <Link to="/cuenta">Inicia sesión</Link>.
            </p>
          )}
          <label>RUT <span className="optional">(opcional)</span><input autoComplete="off" maxLength={16} onChange={(event) => updateField("customer_rut", event.target.value)} value={form.customer_rut} /></label>
          <fieldset>
            <legend>Modalidad de entrega</legend>
            <label className="radio-option"><input checked={deliveryMode === "pickup"} onChange={() => setDeliveryMode("pickup")} type="radio" value="pickup" /> Retiro</label>
            <label className="radio-option"><input checked={deliveryMode === "shipping"} onChange={() => setDeliveryMode("shipping")} type="radio" value="shipping" /> Despacho</label>
          </fieldset>
          {deliveryMode === "shipping" && (
            <label>Dirección para despacho <textarea maxLength={250} onChange={(event) => updateField("delivery_address", event.target.value)} required value={form.delivery_address} /></label>
          )}
          <label>Indicaciones <span className="optional">(opcional)</span><textarea maxLength={500} onChange={(event) => updateField("notes", event.target.value)} value={form.notes} /></label>
          {error && <div className="notice notice-error" role="alert">{error}</div>}
          <button className="button button-wide" disabled={busy || !hasValidQuantities} type="submit">{busy ? "Registrando pedido…" : "Registrar pedido"}</button>
          <p className="form-hint">La tienda confirmará disponibilidad y total por WhatsApp. Luego recibirás los datos para transferir; no transfieras antes de esa confirmación.</p>
        </form>
      </div>
    </main>
  );
}
