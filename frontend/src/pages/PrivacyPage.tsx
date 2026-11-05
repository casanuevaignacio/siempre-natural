import { Link } from "react-router-dom";

export function PrivacyPage() {
  return (
    <main className="page-main">
      <article className="container policy-page">
        <header className="page-heading">
          <span className="section-kicker">Siempre Natural</span>
          <h1>Aviso de privacidad</h1>
          <p>
            Usamos tus datos únicamente para registrar y gestionar tus pedidos
            y coordinar su entrega y pago. No los usamos para enviarte
            publicidad.
          </p>
        </header>

        <section>
          <h2>Datos que podemos solicitar</h2>
          <ul>
            <li>Nombre y teléfono de contacto.</li>
            <li>
              Correo electrónico para registrar el pedido y, si lo solicitas,
              verificar una cuenta y vincular pedidos anteriores.
            </li>
            <li>Dirección, si solicitas despacho; RUT e indicaciones son opcionales.</li>
            <li>
              Productos y cantidades que incluyes en el pedido, junto con la
              modalidad de entrega seleccionada.
            </li>
            <li>
              Si creas una cuenta, almacenamos tu correo verificado y una
              contraseña protegida mediante el sistema de autenticación de la tienda.
            </li>
          </ul>
        </section>

        <section>
          <h2>Cómo se usan y almacenan</h2>
          <p>
            La información permite registrar el pedido, revisar disponibilidad
            y total, y coordinar retiro o despacho. Los pedidos quedan guardados
            en el sistema administrativo de la tienda para su gestión.
          </p>
          <p>
            Las cuentas solo pueden consultar pedidos vinculados a su propio
            correo verificado. No hay un borrado automático del historial.
            Puedes solicitar la eliminación de tu cuenta desde
            <Link to="/cuenta"> Mi cuenta</Link>; los pedidos vinculados se
            conservarán sin los datos que te identifican.
          </p>
          <p>
            El sitio no cobra en línea ni solicita datos de tarjetas o cuentas
            bancarias. La transferencia se coordina después de que la tienda
            confirme el pedido por WhatsApp.
          </p>
        </section>

        <section>
          <h2>Cookies técnicas</h2>
          <p>
            Se pueden usar cookies necesarias para proteger los formularios y
            mantener la sesión de acceso mayorista. No se utilizan cookies
            publicitarias.
          </p>
        </section>

        <section>
          <h2>Consultas</h2>
          <p>
            Para consultas sobre tus datos o un pedido, contáctanos por el
            correo electrónico o WhatsApp indicados al pie de esta página.
          </p>
        </section>
      </article>
    </main>
  );
}
