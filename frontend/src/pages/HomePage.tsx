import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
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

const bulkSlides = [
  {
    src: "/images/despensa-natural.webp",
    alt: "Selección de productos naturales a granel",
    title: "Natural en cada detalle",
    description: "Ingredientes para acompañar tus recetas de todos los días.",
  },
  {
    src: "/images/products/almendras.jpg",
    alt: "Almendras disponibles en el catálogo",
    title: "Frutos secos",
    description: "Opciones versátiles para tus colaciones y preparaciones.",
  },
  {
    src: "/images/products/quinoa.jpg",
    alt: "Quinua disponible en el catálogo",
    title: "Semillas y cereales",
    description: "Variedad natural para sumar a tu mesa.",
  },
  {
    src: "/images/products/caju.jpg",
    alt: "Castañas de cajú disponibles en el catálogo",
    title: "Sabores para compartir",
    description: "Encuentra frutos secos para tus recetas y colaciones.",
  },
  {
    src: "/images/products/avena.jpg",
    alt: "Avena disponible en el catálogo",
    title: "Un básico de todos los días",
    description: "Ideas sencillas para desayunos y preparaciones caseras.",
  },
  {
    src: "/images/products/pistacho.jpg",
    alt: "Pistachos disponibles en el catálogo",
    title: "Descubre nuevas opciones",
    description: "Explora productos y elige tus favoritos a granel.",
  },
  {
    src: "/images/products/te.jpg",
    alt: "Té disponible en el catálogo",
    title: "Una pausa natural",
    description: "Explora sabores para disfrutar a tu manera.",
  },
  {
    src: "/images/products/te-chai.jpg",
    alt: "Té chai disponible en el catálogo",
    title: "Una pausa con sabor",
    description: "Acompaña tu día con una taza de algo especial.",
  },
];

export function HomePage() {
  const [config, setConfig] = useState(emptyConfig);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadError, setLoadError] = useState("");
  const categoryCarousel = useRef<HTMLDivElement>(null);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [pauseSlides, setPauseSlides] = useState(false);
  const sortedCategories = sortCategories(categories);
  const currentSlide = bulkSlides[currentSlideIndex];

  function scrollCategories(direction: -1 | 1) {
    const carousel = categoryCarousel.current;
    if (!carousel) return;

    carousel.scrollBy({
      left: direction * Math.min(carousel.clientWidth * 0.8, 600),
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  }

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

  useEffect(() => {
    if (
      pauseSlides ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      setCurrentSlideIndex((index) => (index + 1) % bulkSlides.length);
    }, 5000);

    return () => window.clearInterval(timer);
  }, [pauseSlides]);

  return (
    <main>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-content">
            <span className="eyebrow"><span /> Bienvenidos a {config.name}</span>
            <h1>{config.tagline}</h1>
            <p>
              Compra a tu manera, sin prisa. Descubre nuestra selección de
              frutos secos, semillas y productos a granel para tu día a día.
            </p>
            <Link className="button" to="/catalogo">Explorar catálogo <span aria-hidden="true">→</span></Link>
            {loadError && <p className="home-error" role="status">{loadError}</p>}
          </div>
          <section
            aria-label="Productos a granel destacados"
            aria-roledescription="carrusel de imágenes"
            className="bulk-showcase"
            onBlur={(event) => {
              const nextTarget = event.relatedTarget;
              if (
                (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) &&
                !event.currentTarget.matches(":hover")
              ) {
                setPauseSlides(false);
              }
            }}
            onFocusCapture={() => setPauseSlides(true)}
            onMouseEnter={() => setPauseSlides(true)}
            onMouseLeave={(event) => {
              if (!event.currentTarget.matches(":focus-within")) {
                setPauseSlides(false);
              }
            }}
          >
            <img
              alt={currentSlide.alt}
              className="bulk-showcase-image"
              key={currentSlide.src}
              onError={(event) => {
                const image = event.currentTarget;
                if (image.dataset.fallbackApplied !== "true") {
                  image.dataset.fallbackApplied = "true";
                  image.alt = "Selección de productos naturales a granel";
                  image.src = "/images/despensa-portada.webp";
                }
              }}
              src={currentSlide.src}
            />
            <div className="bulk-showcase-shade" />
            <div className="bulk-showcase-caption">
              <span className="bulk-showcase-index">
                {String(currentSlideIndex + 1).padStart(2, "0")} / {String(bulkSlides.length).padStart(2, "0")}
              </span>
              <h3>{currentSlide.title}</h3>
              <p>{currentSlide.description}</p>
            </div>
            <div className="bulk-showcase-controls">
              <button
                aria-label="Mostrar imagen anterior"
                className="bulk-showcase-arrow"
                onClick={() =>
                  setCurrentSlideIndex((index) => (index - 1 + bulkSlides.length) % bulkSlides.length)
                }
                type="button"
              >
                <span aria-hidden="true">←</span>
              </button>
              <div className="bulk-showcase-dots" aria-label="Seleccionar imagen">
                {bulkSlides.map((slide, index) => (
                  <button
                    aria-current={index === currentSlideIndex ? "true" : undefined}
                    aria-label={`Mostrar imagen: ${slide.title}`}
                    className="bulk-showcase-dot"
                    key={slide.src}
                    onClick={() => setCurrentSlideIndex(index)}
                    type="button"
                  />
                ))}
              </div>
              <button
                aria-label="Mostrar imagen siguiente"
                className="bulk-showcase-arrow"
                onClick={() =>
                  setCurrentSlideIndex((index) => (index + 1) % bulkSlides.length)
                }
                type="button"
              >
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </section>
        </div>
      </section>

      <section className="container home-categories">
        <div className="category-heading">
          <div>
            <span className="section-kicker">Explora</span>
            <h2>Categorías</h2>
          </div>
          <div className="category-controls">
            <Link className="text-link" to="/catalogo">Ver catálogo <span aria-hidden="true">→</span></Link>
            {categories.length > 1 && (
              <div className="category-arrows">
                <button
                  aria-label="Desplazar categorías hacia la izquierda"
                  aria-controls="category-carousel"
                  className="category-arrow"
                  onClick={() => scrollCategories(-1)}
                  type="button"
                >
                  <span aria-hidden="true">←</span>
                </button>
                <button
                  aria-label="Desplazar categorías hacia la derecha"
                  aria-controls="category-carousel"
                  className="category-arrow"
                  onClick={() => scrollCategories(1)}
                  type="button"
                >
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            )}
          </div>
        </div>
        {categories.length ? (
          <div
            aria-label="Categorías de productos"
            className="category-carousel"
            id="category-carousel"
            ref={categoryCarousel}
            role="region"
            tabIndex={0}
          >
            {sortedCategories.map((category) => (
              <Link
                className="category-card"
                key={category.id}
                to={`/catalogo?categoria=${encodeURIComponent(category.slug)}`}
              >
                <span aria-hidden="true" className="category-card-icon">✳</span>
                <span className="category-card-name">{category.name}</span>
                <span className="category-card-description">
                  {category.description || "Descubre opciones naturales para tu día."}
                </span>
                <span aria-hidden="true" className="category-card-arrow">↗</span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="category-empty">Consulta el catálogo para ver los productos disponibles.</p>
        )}
      </section>

      <section className="container impact-section" aria-labelledby="impact-title">
        <div className="wellness-heading">
          <span className="section-kicker">Pequeños hábitos, gran impacto</span>
          <h2 id="impact-title">Más vida consciente, menos residuos.</h2>
          <p>
            Elegir productos a granel puede ayudar a reducir envases
            innecesarios. Reutiliza, recicla y disfruta una alimentación más
            natural: cada hábito suma.
          </p>
        </div>
        <div className="impact-grid">
          <article className="impact-card impact-card-green">
            <span aria-hidden="true" className="impact-icon">✳</span>
            <span className="impact-step">01 · COMPRA CONSCIENTE</span>
            <h3>Compra a granel</h3>
            <p>Elige la cantidad que necesitas y disfruta productos naturales a tu medida.</p>
          </article>
          <article className="impact-card impact-card-lime">
            <span aria-hidden="true" className="impact-icon">↻</span>
            <span className="impact-step">02 · REUTILIZA</span>
            <h3>Menos plástico, más vida</h3>
            <p>Cuando puedas, prefiere envases reutilizables para tus compras cotidianas.</p>
          </article>
          <article className="impact-card impact-card-cream">
            <span aria-hidden="true" className="impact-icon">♻</span>
            <span className="impact-step">03 · RECICLA</span>
            <h3>Un ciclo más natural</h3>
            <p>Separa y recicla los envases que uses según las opciones de tu comunidad.</p>
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
