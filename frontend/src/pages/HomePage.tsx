import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { fetchCategories, fetchStoreConfig } from "../api";
import { sortCategories } from "../categoryOrder";
import type { Category, StoreConfig } from "../types";

const emptyConfig: StoreConfig = {
  name: "Siempre Natural",
  tagline: "Alimentación consciente, a tu medida",
  whatsapp_number: "",
  pickup_address: "",
  business_hours: "",
  contact_email: "",
};

export function HomePage() {
  const [config, setConfig] = useState(emptyConfig);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadError, setLoadError] = useState("");
  const sortedCategories = sortCategories(categories);

  useEffect(() => {
    Promise.all([fetchStoreConfig(), fetchCategories()])
      .then(([nextConfig, nextCategories]) => {
        setConfig(nextConfig);
        setCategories(nextCategories);
      })
      .catch((cause: unknown) =>
        setLoadError(cause instanceof Error ? cause.message : "No se pudo cargar la información de la tienda."),
      );
  }, []);

  return (
    <main>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-content">
            <span className="eyebrow"><span /> Alimentación natural para cada día</span>
            <h1>{config.tagline}</h1>
            <p>
              Descubre frutos secos, semillas y otros productos a granel para
              disfrutar de una alimentación más natural.
            </p>
            <Link className="button" to="/catalogo">Explorar catálogo <span aria-hidden="true">→</span></Link>
            <div className="hero-note">
              <span className="note-icon" aria-hidden="true">✳</span>
              <span>Encuentra opciones para sumar bienestar a tu día a día.</span>
            </div>
            {loadError && <p className="home-error" role="status">{loadError}</p>}
          </div>
          <div className="hero-art">
            <img
              alt="Selección de frutos secos, semillas, especias, miel y aceites naturales a granel"
              className="hero-illustration"
              src="/images/despensa-portada.webp"
            />
          </div>
        </div>
      </section>

      <section className="container intro-section">
        <div>
          <span className="section-kicker">Bienvenidos a {config.name}</span>
          <h2>Compra a tu manera,<br /><em>sin prisa.</em></h2>
        </div>
        <p>
          Explora nuestra selección de productos a granel y elige las opciones
          que mejor acompañan tu día a día.
        </p>
      </section>

      <section className="container home-categories">
        <div className="category-heading">
          <div>
            <span className="section-kicker">Explora</span>
            <h2>Categorías</h2>
          </div>
          <Link className="text-link" to="/catalogo">Ver catálogo <span aria-hidden="true">→</span></Link>
        </div>
        {categories.length ? (
          <div className="category-list">
            {sortedCategories.map((category) => (
              <Link className="category-chip" key={category.id} to={`/catalogo?categoria=${encodeURIComponent(category.slug)}`}>
                <span aria-hidden="true">✳</span>{category.name}
              </Link>
            ))}
          </div>
        ) : (
          <p className="category-empty">Consulta el catálogo para ver los productos disponibles.</p>
        )}
      </section>

      <section className="container wellness-gallery" aria-labelledby="wellness-title">
        <div className="wellness-heading">
          <span className="section-kicker">Inspiración natural</span>
          <h2 id="wellness-title">Bienestar a tu propio ritmo</h2>
          <p>Alimentos nobles, conexión con la naturaleza y una vida activa.</p>
        </div>
        <div className="wellness-grid">
          <article className="wellness-card">
            <img
              alt="Mujer disfrutando un desayuno de frutas, semillas y cereales al aire libre"
              loading="lazy"
              src="/images/alimentacion-consciente.webp"
            />
            <h3>Alimentación consciente</h3>
          </article>
          <article className="wellness-card">
            <img
              alt="Afiche de Siempre Natural sobre energía natural, alimentación consciente y desafíos sin límites"
              loading="lazy"
              src="/images/energia-natural.webp"
            />
            <h3>Energía natural</h3>
          </article>
          <article className="wellness-card">
            <img
              alt="Niños compartiendo frutas, semillas y un desayuno saludable en familia"
              loading="lazy"
              src="/images/vida-sana-en-familia.webp"
            />
            <h3>Vida sana en familia</h3>
          </article>
        </div>
      </section>

      <section className="delivery-section">
        <div className="container delivery-content">
          <div className="delivery-icon" aria-hidden="true">⌂</div>
          <div>
            <span className="section-kicker">Modalidades de entrega</span>
            <h2>Despacho o retiro</h2>
            <p>
              {config.pickup_address
                ? `Retira tu pedido en ${config.pickup_address}. `
                : "Retiro disponible. "}
              {config.business_hours
                ? `Atendemos ${config.business_hours}. `
                : ""}
              Coordina cobertura y costos del despacho por WhatsApp.
            </p>
          </div>
          <Link className="text-link" to="/catalogo">Ver catálogo <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </main>
  );
}
