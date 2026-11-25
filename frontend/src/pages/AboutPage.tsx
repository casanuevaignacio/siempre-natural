import { useEffect } from "react";
import { Link } from "react-router-dom";

const values = [
  {
    title: "Alimentación consciente",
    caption: "Elegir mejor lo que comemos.",
    image: "/images/alimentacion-consciente.webp",
    alt: "Alimentos naturales dispuestos en frascos para una despensa consciente",
  },
  {
    title: "Compromiso ambiental",
    caption: "Reducir, reutilizar y reciclar.",
    image: "/images/impact-reutiliza.webp",
    alt: "Envases reutilizables para comprar alimentos a granel",
  },
  {
    title: "Deporte y movimiento",
    caption: "Apoyar el deporte y la vida activa.",
    image: "/images/about-surf.webp",
    alt: "Surfista en una ola junto a la costa",
  },
  {
    title: "Comunidad y naturaleza",
    caption: "Crecer junto a iniciativas locales.",
    image: "/images/about-climbing.webp",
    alt: "Deportista escalando una roca al aire libre",
  },
];

const philosophy = [
  {
    title: "Alimentación consciente",
    text: "Promover hábitos saludables y acercar alimentos de calidad a las personas.",
    mark: "✿",
    tone: "food",
  },
  {
    title: "Compromiso ambiental",
    text: "Reducir el uso de plásticos, fomentar el reciclaje y avanzar hacia un consumo más responsable.",
    mark: "↻",
    tone: "environment",
  },
  {
    title: "Vida en movimiento",
    text: "Apoyar el deporte, la actividad física y las iniciativas locales.",
    mark: "↗",
    tone: "movement",
  },
  {
    title: "Comunidad",
    text: "Conectar personas, emprendimientos y actividades que comparten una visión de bienestar.",
    mark: "◉",
    tone: "community",
  },
];

export function AboutPage() {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = "Quiénes somos | Superalimentos a Granel";
    let description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    const previousDescription = description?.content;
    const createdDescription = !description;
    if (!description) {
      description = document.createElement("meta");
      description.name = "description";
      document.head.append(description);
    }
    description.content =
      "Conoce Superalimentos a Granel: alimentación consciente, compromiso ambiental, deporte y comunidad para una vida más saludable.";
    return () => {
      document.title = previousTitle;
      if (createdDescription) description?.remove();
      else if (description && previousDescription !== undefined) description.content = previousDescription;
    };
  }, []);

  return (
    <main className="page-main about-page">
      <section className="container about-hero" aria-labelledby="about-title">
        <div className="about-hero-copy">
          <span className="about-hero-kicker">Alimentación · naturaleza · comunidad</span>
          <h1 id="about-title">Alimentarse mejor, vivir consciente y cuidar nuestro entorno.</h1>
          <p>
            En <strong>Superalimentos a Granel</strong> creemos que una vida más
            saludable comienza con pequeñas decisiones que, en conjunto, pueden
            generar grandes cambios.
          </p>
          <a className="about-hero-link" href="#nuestra-filosofia">Conoce nuestra filosofía <span aria-hidden="true">↓</span></a>
        </div>
        <div className="about-hero-visual">
          <img src="/images/despensa-portada.webp" alt="Alimentos naturales a granel en una despensa" />
          <div className="about-hero-note">
            <span aria-hidden="true">“</span>
            <p>No se trata solamente de lo que comemos, sino de cómo vivimos, cómo nos movemos y cómo cuidamos el lugar donde vivimos.</p>
          </div>
        </div>
      </section>

      <section className="about-story-section">
        <div className="container about-story">
          <figure className="about-story-visual">
            <img src="/images/vida-sana-inicio.webp" alt="Alimentos naturales compartidos junto a un paisaje costero" loading="lazy" />
            <figcaption>Pequeñas elecciones.<br /><em>Grandes cambios.</em></figcaption>
          </figure>
          <div className="about-story-copy">
            <span className="about-story-kicker">Quiénes somos</span>
            <h2>Una historia que nace de <em>elegir mejor.</em></h2>
            <p className="about-story-lead">
            Somos un emprendimiento que busca acercar la alimentación saludable
            y consciente a las personas, ofreciendo una variedad de frutos secos,
            semillas, cereales, harinas, legumbres, aceites y otros alimentos que
            contribuyen a una mejor calidad de vida.
            </p>
            <p className="about-story-body">
            Nuestro propósito va más allá de la alimentación. Creemos en una forma
            de vivir más consciente, respetuosa con nuestro entorno y conectada con
            la naturaleza. Nos preocupa el impacto que generamos en el medioambiente,
            por eso buscamos reducir el uso de plásticos en nuestras entregas y
            fomentar hábitos responsables, como la reutilización y el reciclaje.
            </p>
            <p className="about-story-body">
            También creemos que una vida saludable se construye con movimiento,
            deporte y conexión con nuestro entorno. Hemos apoyado a deportistas
            locales de surf y escalada, y auspiciado competencias y encuentros de
            surf, escalada, SUP, vóleibol playa, fútbol y otras actividades al aire libre.
            </p>
            <div className="about-story-signoff"><span aria-hidden="true">✳</span> Bienestar que compartimos, entorno que cuidamos.</div>
          </div>
        </div>
      </section>

      <section className="about-values-section" aria-labelledby="values-title">
        <div className="container">
          <header className="about-section-heading">
            <span className="section-kicker">Lo que nos mueve</span>
            <h2 id="values-title">Una forma consciente de vivir</h2>
            <p>Nos motiva ser parte de una comunidad que cuida la naturaleza, se mantiene activa y busca el bienestar colectivo.</p>
          </header>
          <div className="about-values-grid">
            {values.map((value, index) => (
              <article className="about-value-card" key={value.title}>
                <img src={value.image} alt={value.alt} loading={index > 1 ? "lazy" : "eager"} />
                <div><h3>{value.title}</h3><p>{value.caption}</p></div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="container about-philosophy" id="nuestra-filosofia">
        <header className="about-section-heading">
          <span className="section-kicker">Nuestra filosofía</span>
          <h2>Valores que se viven cada día</h2>
        </header>
        <div className="about-philosophy-grid">
          {philosophy.map((item) => (
            <article className={`about-philosophy-card about-philosophy-${item.tone}`} key={item.title}>
              <span className="about-philosophy-mark" aria-hidden="true">{item.mark}</span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="about-purpose-section">
        <div className="container about-purpose">
          <span className="about-purpose-mark" aria-hidden="true">✳</span>
          <span className="section-kicker">Nuestro propósito</span>
          <h2>Creemos que cada elección cuenta.</h2>
          <p>
            Queremos aportar, desde nuestro lugar, a generar una mayor conciencia
            sobre cómo nos alimentamos, cómo cuidamos nuestro planeta y cómo vivimos.
            Desde elegir alimentos más saludables hasta reutilizar un envase, reciclar
            o dedicar tiempo al deporte y la naturaleza.
          </p>
          <strong>Superalimentos a Granel: más que alimentación saludable, una forma consciente de vivir.</strong>
          <Link className="button" to="/catalogo">Explora nuestros productos <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </main>
  );
}
