import { Link, NavLink } from "react-router-dom";
import { useCart } from "../cart/CartContext";

export function Header() {
  const { count } = useCart();
  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link className="brand" to="/" aria-label="Siempre Natural, inicio">
          <img
            className="brand-logo"
            src="/logo-siempre-natural.png"
            alt=""
            width="48"
            height="48"
          />
          <span className="brand-copy">
            <strong>Siempre Natural</strong>
            <small>Superalimentos a granel</small>
          </span>
        </Link>
        <nav className="main-nav" aria-label="Navegación principal">
          <NavLink to="/">Inicio</NavLink>
          <NavLink to="/catalogo">Catálogo</NavLink>
          <NavLink to="/cuenta">Mi cuenta</NavLink>
          <NavLink to="/mayoristas">Mayoristas</NavLink>
        </nav>
        <Link className="cart-link" to="/carrito" aria-label={`Carrito, ${count} productos`}>
          <span aria-hidden="true">♧</span>
          <span>Carrito</span>
          <span className="cart-count">{count}</span>
        </Link>
      </div>
    </header>
  );
}
