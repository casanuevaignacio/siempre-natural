import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { fetchStoreConfig, formatCLP } from "../api";
import type { CreatedOrder, StoreConfig } from "../types";

interface StoredOrder extends CreatedOrder {
  whatsappMessage: string;
  lines: Array<{ name: string; quantity: number; unit: string }>;
  deliveryMode: "pickup" | "shipping";
}

const defaultStore: StoreConfig = {
  name: "Siempre Natural",
  tagline: "Alimentación consciente, a tu medida",
  whatsapp_number: "",
  pickup_address: "",
  business_hours: "",
  contact_email: "",
};

export function ConfirmationPage() {
  const { orderId } = useParams();
  const location = useLocation();
  const [store, setStore] = useState(defaultStore);
  const [configError, setConfigError] = useState("");
  const order = useMemo<StoredOrder | null>(() => {
    const state = location.state as StoredOrder | null;
    return state?.id === orderId ? state : null;
  }, [location.state, orderId]);

  useEffect(() => {
    fetchStoreConfig()
      .then(setStore)
      .catch((cause: unknown) =>
        setConfigError(cause instanceof Error ? cause.message : "No se pudo consultar la configuración de WhatsApp."),
      );
  }, []);

  const whatsappUrl = order && store.whatsapp_number
    ? `https://wa.me/${store.whatsapp_number}?text=${encodeURIComponent(order.whatsappMessage)}`
    : "";

  return (
    <main className="page-main">
      <section className="container confirmation-card">
        <span className="confirmation-check" aria-hidden="true">✓</span>
        <span className="section-kicker">Pedido registrado</span>
        <h1>Gracias por tu pedido</h1>
        <p>Tu pedido quedó registrado. La tienda confirmará disponibilidad y total por WhatsApp; después te enviará los datos para transferir. No realices la transferencia antes de recibir esa confirmación.</p>
        {order ? (
          <div className="confirmation-summary">
            <div><span>Número de pedido</span><strong>{order.id}</strong></div>
            <div><span>Total registrado</span><strong>{formatCLP(order.total)}</strong></div>
          </div>
        ) : (
          <p className="form-hint">Identificador del pedido: {orderId}. Los datos del pedido no se exponen en este enlace.</p>
        )}
        {order && (
          <p className={order.email_notification_sent ? "notice notice-info" : "notice notice-error"}>
            {order.email_notification_sent
              ? "La tienda recibió un aviso por correo. Espera su confirmación antes de transferir."
              : "El pedido quedó guardado, pero no se pudo enviar el aviso por correo a la tienda. Escríbele por WhatsApp para confirmar."}
          </p>
        )}
        {order && whatsappUrl ? (
          <a className="button" href={whatsappUrl} rel="noreferrer" target="_blank">Continuar por WhatsApp <span aria-hidden="true">↗</span></a>
        ) : order ? (
          <p className="notice notice-info">{configError || "El número comercial de WhatsApp aún no está configurado."} Tu pedido ya está registrado y disponible para la tienda.</p>
        ) : null}
        <Link className="text-link confirmation-link" to="/catalogo">Volver al catálogo</Link>
      </section>
    </main>
  );
}
