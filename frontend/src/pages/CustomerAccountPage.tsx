import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  confirmCustomerPasswordReset,
  deleteCustomerAccount,
  fetchCustomerOrders,
  fetchCustomerSession,
  formatCLP,
  loginCustomer,
  logoutCustomer,
  registerCustomer,
  requestCustomerPasswordReset,
  requestGuestOrderClaim,
  resendCustomerVerification,
  verifyCustomerEmail,
} from "../api";
import type { CustomerOrder, CustomerSession } from "../types";

type AccountMode = "login" | "register" | "forgot-password";

const emptySession: CustomerSession = {
  is_authenticated: false,
  email: "",
  email_verified: false,
};

function orderQuantity(item: CustomerOrder["items"][number]) {
  return item.quantity_grams
    ? `${item.quantity_grams} g`
    : `${item.quantity_units} un.`;
}

export function CustomerAccountPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const query = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  );
  const verificationToken = query.get("token") ?? "";
  const verificationAction = query.get("action") === "claim" ? "claim" : "verify";
  const resetUid = query.get("uid") ?? "";
  const resetToken = query.get("token") ?? "";

  const [session, setSession] = useState(emptySession);
  const [orders, setOrders] = useState<CustomerOrder[]>([]);
  const [mode, setMode] = useState<AccountMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    let active = true;
    fetchCustomerSession()
      .then(async (nextSession) => {
        if (!active) return;
        setSession(nextSession);
        if (nextSession.is_authenticated) setEmail(nextSession.email);
        if (nextSession.is_authenticated) {
          setOrders(await fetchCustomerOrders());
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            cause instanceof Error
              ? cause.message
              : "No se pudo consultar la sesión de cliente.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!verificationToken || resetUid) return;
    let active = true;
    setBusy(true);
    verifyCustomerEmail(verificationToken, verificationAction)
      .then((result) => {
        if (active) {
          setNotice(`${result.detail} Pedidos añadidos: ${result.claimed_orders}.`);
        }
        return fetchCustomerSession();
      })
      .then(async (nextSession) => {
        if (!active) return;
        setSession(nextSession);
        if (nextSession.is_authenticated) {
          setOrders(await fetchCustomerOrders());
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            cause instanceof Error
              ? cause.message
              : "No se pudo verificar el correo.",
          );
        }
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [resetUid, verificationAction, verificationToken]);

  async function submitAccountForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "register") {
        if (password !== passwordConfirmation) {
          throw new Error("Las contraseñas no coinciden.");
        }
        const result = await registerCustomer(email, password);
        setSession({
          is_authenticated: result.is_authenticated,
          email: result.email,
          email_verified: result.email_verified,
        });
        setOrders([]);
        setNotice(
          result.verification_email_sent
            ? "Cuenta creada. Ya puedes comprar; confirma tu correo solo para consultar y vincular pedidos anteriores o recuperar tu contraseña."
            : "Cuenta creada y sesión iniciada. Puedes comprar desde ahora. Para consultar pedidos anteriores o recuperar la contraseña, la tienda deberá habilitar el envío de correos.",
        );
        setPassword("");
        setPasswordConfirmation("");
      } else if (mode === "forgot-password") {
        const result = await requestCustomerPasswordReset(email);
        setNotice(result.detail);
      } else {
        const nextSession = await loginCustomer(email, password);
        setSession(nextSession);
        setOrders(await fetchCustomerOrders());
        setPassword("");
        setNotice(
          nextSession.email_verified
            ? "Sesión iniciada."
            : "Sesión iniciada. Tus pedidos de esta cuenta están disponibles sin confirmar el correo. Para vincular pedidos de invitado o recuperar la contraseña, confirma tu correo.",
        );
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo completar la solicitud.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitPasswordReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (password !== passwordConfirmation) {
        throw new Error("Las contraseñas no coinciden.");
      }
      const result = await confirmCustomerPasswordReset(
        resetUid,
        resetToken,
        password,
      );
      setNotice(result.detail);
      setPassword("");
      setPasswordConfirmation("");
      navigate("/cuenta", { replace: true });
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo cambiar la contraseña.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitLogout() {
    setBusy(true);
    setError("");
    try {
      await logoutCustomer();
      setSession(emptySession);
      setOrders([]);
      setNotice("Sesión cerrada.");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "No se pudo cerrar la sesión.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitClaimRequest() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await requestGuestOrderClaim();
      setNotice(
        result.email_sent
          ? "Te enviamos un enlace para vincular pedidos anteriores hechos con este correo."
          : "No se pudo enviar el enlace. El pedido permanece guardado; hay que configurar el correo para reclamarlo.",
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo solicitar el enlace.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitDeleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await deleteCustomerAccount(deletePassword);
      setSession(emptySession);
      setOrders([]);
      setNotice(
        "La cuenta se eliminó. Los datos personales de los pedidos se anonimizaron.",
      );
      setConfirmDelete(false);
      setDeletePassword("");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo eliminar la cuenta.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitResendVerification() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await resendCustomerVerification(email);
      setNotice(result.detail);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo solicitar otro enlace.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <main className="page-main">
        <section className="container"><p>Consultando tu cuenta…</p></section>
      </main>
    );
  }

  return (
    <main className="page-main">
      <section className="container page-heading">
        <span className="section-kicker">Siempre Natural</span>
        <h1>Mi cuenta</h1>
        <p>Accede a tu historial de pedidos y administra tus datos.</p>
      </section>

      <section className="container account-content">
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {notice && <div className="notice notice-info" role="status">{notice}</div>}
        {busy && verificationToken && !resetUid && (
          <p>Verificando el enlace…</p>
        )}

        {resetUid && resetToken ? (
          <form className="checkout-form account-form" onSubmit={submitPasswordReset}>
            <h2>Crear una contraseña nueva</h2>
            <label>
              Nueva contraseña
              <input
                autoComplete="new-password"
                minLength={8}
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </label>
            <label>
              Repite la contraseña
              <input
                autoComplete="new-password"
                onChange={(event) => setPasswordConfirmation(event.target.value)}
                required
                type="password"
                value={passwordConfirmation}
              />
            </label>
            <button className="button" disabled={busy} type="submit">
              {busy ? "Guardando…" : "Actualizar contraseña"}
            </button>
          </form>
        ) : session.is_authenticated ? (
          <>
            <div className="account-toolbar">
              <p>Sesión iniciada como <strong>{session.email}</strong></p>
              <button
                className="button button-small"
                disabled={busy}
                onClick={submitLogout}
                type="button"
              >
                Cerrar sesión
              </button>
            </div>

            <div className="account-actions">
              {session.email_verified ? (
                <button
                  className="text-link"
                  disabled={busy}
                  onClick={submitClaimRequest}
                  type="button"
                >
                  Buscar pedidos anteriores con este correo
                </button>
              ) : (
                <div className="notice notice-info" role="status">
                  Tus pedidos hechos con la sesión iniciada aparecen abajo. Confirma
                  el correo solo para vincular pedidos anteriores hechos como invitado
                  o recuperar tu contraseña.
                  <button
                    className="account-secondary-action"
                    disabled={busy}
                    onClick={submitResendVerification}
                    type="button"
                  >
                    Enviarme un enlace de confirmación
                  </button>
                </div>
              )}
              <Link className="text-link" to="/catalogo">Seguir comprando</Link>
            </div>

            <h2 className="account-section-title">Historial de compras</h2>
            {orders.length ? (
              <div className="account-orders">
                {orders.map((order) => (
                  <article className="account-order" key={order.id}>
                    <div className="account-order-heading">
                      <strong>Pedido {order.id}</strong>
                      <span>
                        {new Intl.DateTimeFormat("es-CL", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        }).format(new Date(order.created_at))}
                      </span>
                    </div>
                    <p>{order.status} · {order.delivery_mode}</p>
                    <ul>
                      {order.items.map((item, index) => (
                        <li key={`${order.id}-${index}`}>
                          {item.name} · {orderQuantity(item)} · {formatCLP(item.subtotal)}
                        </li>
                      ))}
                    </ul>
                    <strong>Total: {formatCLP(order.total)}</strong>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-state">
                Todavía no hay pedidos hechos con esta cuenta.
                {!session.email_verified &&
                  " Para vincular pedidos anteriores hechos como invitado, confirma tu correo."}
              </p>
            )}

            <section className="account-delete">
              <h2>Eliminar cuenta</h2>
              <p>
                Se eliminará tu cuenta y se anonimizarán los datos personales
                asociados a tus pedidos. Se conservarán productos, importes y
                estados sin identificarte.
              </p>
              <form className="account-delete-form" onSubmit={submitDeleteAccount}>
                {confirmDelete && (
                  <label>
                    Confirma tu contraseña para continuar
                    <input
                      autoComplete="current-password"
                      onChange={(event) => setDeletePassword(event.target.value)}
                      required
                      type="password"
                      value={deletePassword}
                    />
                  </label>
                )}
                <button className="remove-button" disabled={busy} type="submit">
                  {confirmDelete
                    ? "Confirmar eliminación de cuenta"
                    : "Solicitar eliminación de cuenta"}
                </button>
              </form>
            </section>
          </>
        ) : (
          <div className="account-layout">
            <form className="checkout-form account-form" onSubmit={submitAccountForm}>
              <h2>
                {mode === "register"
                  ? "Crear cuenta"
                  : mode === "forgot-password"
                    ? "Recuperar contraseña"
                    : "Iniciar sesión"}
              </h2>
              <label>
                Correo electrónico
                <input
                  autoComplete="email"
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  type="email"
                  value={email}
                />
              </label>
              {mode !== "forgot-password" && (
                <label>
                  Contraseña
                  <input
                    autoComplete={mode === "register" ? "new-password" : "current-password"}
                    minLength={8}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    type="password"
                    value={password}
                  />
                </label>
              )}
              {mode === "register" && (
                <>
                  <label>
                    Repite la contraseña
                    <input
                      autoComplete="new-password"
                      onChange={(event) => setPasswordConfirmation(event.target.value)}
                      required
                      type="password"
                      value={passwordConfirmation}
                    />
                  </label>
                  <p className="form-hint">
                    No necesitas confirmar tu correo para crear la cuenta ni comprar.
                    La confirmación es opcional y sirve para vincular pedidos de
                    invitado y recuperar la contraseña.
                  </p>
                </>
              )}
              <button className="button button-wide" disabled={busy} type="submit">
                {busy
                  ? "Procesando…"
                  : mode === "register"
                    ? "Crear cuenta"
                    : mode === "forgot-password"
                      ? "Enviar instrucciones"
                      : "Iniciar sesión"}
              </button>
              {mode === "login" && (
                <button
                  className="account-secondary-action"
                  disabled={busy}
                  onClick={() => setMode("forgot-password")}
                  type="button"
                >
                  Olvidé mi contraseña
                </button>
              )}
              {mode !== "login" && (
                <button
                  className="account-secondary-action"
                  disabled={busy}
                  onClick={() => setMode("login")}
                  type="button"
                >
                  Volver a iniciar sesión
                </button>
              )}
              {mode !== "forgot-password" && (
                <button
                  className="account-secondary-action"
                  disabled={busy}
                  onClick={submitResendVerification}
                  type="button"
                >
                  Reenviar confirmación de correo
                </button>
              )}
            </form>
            <aside className="account-info">
              <span className="section-kicker">Tu historial, en un solo lugar</span>
              <h2>Consulta tus compras</h2>
              <p>
                Crea una cuenta fácilmente. Confirmar el correo es opcional y solo
                se necesita para vincular pedidos anteriores hechos como invitado y
                recuperar la contraseña.
              </p>
              {mode !== "register" && (
                <button
                  className="text-link"
                  onClick={() => setMode("register")}
                  type="button"
                >
                  Crear una cuenta <span aria-hidden="true">→</span>
                </button>
              )}
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}
