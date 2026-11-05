import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  fetchStoreConfig,
  fetchWholesalePrices,
  fetchWholesaleSession,
  formatCLP,
  loginWholesale,
  logoutWholesale,
} from "../api";
import type { StoreConfig, WholesalePrice, WholesaleSession } from "../types";

const spanishCollator = new Intl.Collator("es-CL", {
  numeric: true,
  sensitivity: "base",
});

export function WholesalePage() {
  const [session, setSession] = useState<WholesaleSession | null>(null);
  const [prices, setPrices] = useState<WholesalePrice[]>([]);
  const [storeConfig, setStoreConfig] = useState<StoreConfig | null>(null);
  const [search, setSearch] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetchWholesaleSession(), fetchStoreConfig()])
      .then(async ([nextSession, config]) => {
        setSession(nextSession);
        setStoreConfig(config);
        if (nextSession.is_wholesale_customer) {
          setPrices(await fetchWholesalePrices());
        }
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

  const visiblePrices = useMemo(
    () =>
      prices
        .filter((item) =>
          `${item.product_name} ${item.category_name}`
            .toLocaleLowerCase("es")
            .includes(search.toLocaleLowerCase("es")),
        )
        .slice()
        .sort(
          (left, right) =>
            spanishCollator.compare(left.category_name, right.category_name) ||
            spanishCollator.compare(left.product_name, right.product_name),
        ),
    [prices, search],
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

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const nextSession = await loginWholesale(username, password);
      setSession(nextSession);
      setPassword("");
      setPrices(await fetchWholesalePrices());
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo iniciar sesión.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError("");
    try {
      await logoutWholesale();
      setSession({
        is_authenticated: false,
        is_wholesale_customer: false,
        username: "",
      });
      setPrices([]);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo cerrar la sesión.",
      );
    } finally {
      setBusy(false);
    }
  }

  const whatsappLink = storeConfig?.whatsapp_number
    ? `https://wa.me/${storeConfig.whatsapp_number}?text=${encodeURIComponent("Hola, quisiera solicitar acceso al catálogo mayorista de Siempre Natural.")}`
    : null;

  return (
    <main className="page-main">
      <section className="container page-heading">
        <span className="section-kicker">Atención a restaurantes y compras por mayor</span>
        <h1>Precios mayoristas</h1>
        <p>La lista especial está disponible para clientes mayoristas autorizados.</p>
      </section>

      <section className="container wholesale-content">
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {loading ? (
          <p className="empty-state">Verificando acceso…</p>
        ) : session?.is_wholesale_customer ? (
          <>
            <div className="wholesale-toolbar">
              <p>Sesión iniciada como <strong>{session.username}</strong></p>
              <button
                className="button button-small"
                disabled={busy}
                onClick={signOut}
                type="button"
              >
                Cerrar sesión
              </button>
            </div>
            <label className="search-field wholesale-search">
              <span aria-hidden="true">⌕</span>
              <span className="sr-only">Buscar en precios mayoristas</span>
              <input
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar un producto o categoría..."
                value={search}
              />
            </label>
            {groups.length ? (
              <div className="wholesale-groups">
                {groups.map(([category, items]) => (
                  <section className="wholesale-group" key={category}>
                    <h2>{category}</h2>
                    <div className="wholesale-table-wrap">
                      <table className="wholesale-table">
                        <thead>
                          <tr>
                            <th>Producto</th>
                            <th>Precio especial</th>
                            <th>Unidad / presentación</th>
                          </tr>
                        </thead>
                        <tbody>
                          {items.map((item) => (
                            <tr key={item.id}>
                              <td>{item.product_name}</td>
                              <td>{formatCLP(item.price)}</td>
                              <td>
                                {item.price_unit === "kg"
                                  ? "kg"
                                  : item.package_label}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <h2>No encontramos precios</h2>
                <p>Prueba con otro nombre o categoría.</p>
              </div>
            )}
            <p className="form-hint wholesale-disclaimer">
              Los precios se muestran según la lista mayorista vigente. Confirma
              disponibilidad, cantidades y condiciones de compra con la tienda.
            </p>
          </>
        ) : session?.is_authenticated ? (
          <section className="empty-state wholesale-access-message">
            <span className="empty-art" aria-hidden="true">♧</span>
            <h2>Tu cuenta aún no tiene acceso mayorista</h2>
            <p>
              Solicita autorización a Siempre Natural. Una vez aprobada, podrás
              consultar aquí los precios especiales.
            </p>
            {whatsappLink && (
              <a className="button" href={whatsappLink} rel="noreferrer" target="_blank">
                Solicitar acceso por WhatsApp
              </a>
            )}
          </section>
        ) : (
          <div className="wholesale-login-layout">
            <form className="checkout-form" onSubmit={submitLogin}>
              <h2>Ingreso para mayoristas</h2>
              <p className="form-hint">
                Acceso exclusivo para cuentas habilitadas por Siempre Natural.
              </p>
              <label>
                Usuario
                <input
                  autoComplete="username"
                  onChange={(event) => setUsername(event.target.value)}
                  required
                  value={username}
                />
              </label>
              <label>
                Contraseña
                <input
                  autoComplete="current-password"
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
              </label>
              <button className="button button-wide" disabled={busy} type="submit">
                {busy ? "Ingresando…" : "Ingresar"}
              </button>
            </form>
            <aside className="wholesale-request">
              <span className="section-kicker">¿Aún no tienes acceso?</span>
              <h2>Solicita una cuenta mayorista</h2>
              <p>
                La tienda revisará tu solicitud y habilitará el acceso a la lista
                de precios especiales. El mínimo y las condiciones de compra se
                coordinan por WhatsApp.
              </p>
              {whatsappLink && (
                <a className="text-link" href={whatsappLink} rel="noreferrer" target="_blank">
                  Contactar por WhatsApp <span aria-hidden="true">→</span>
                </a>
              )}
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}
