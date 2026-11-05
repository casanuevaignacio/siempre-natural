import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStoreConfig } from "../api";
import type { StoreConfig } from "../types";

export function Footer() {
  const [config, setConfig] = useState<StoreConfig>({
    name: "Siempre Natural",
    tagline: "Alimentación consciente, a tu medida",
    whatsapp_number: "",
    pickup_address: "",
    business_hours: "",
    contact_email: "",
  });
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    fetchStoreConfig()
      .then(setConfig)
      .catch((cause: unknown) =>
        setLoadError(
          cause instanceof Error
            ? cause.message
            : "No se pudieron cargar los datos de contacto.",
        ),
      );
  }, []);

  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <span>{config.name}</span>
        <div className="footer-contact">
          {config.contact_email && (
            <a className="text-link" href={`mailto:${config.contact_email}`}>
              {config.contact_email}
            </a>
          )}
          {config.whatsapp_number && (
            <a
              className="text-link"
              href={`https://wa.me/${config.whatsapp_number}`}
              rel="noreferrer"
              target="_blank"
            >
              Contactar por WhatsApp <span aria-hidden="true">↗</span>
            </a>
          )}
        </div>
        {loadError && <span role="status">{loadError}</span>}
        <Link className="text-link" to="/privacidad">Privacidad</Link>
      </div>
    </footer>
  );
}
