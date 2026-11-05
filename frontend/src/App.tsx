import { Route, Routes } from "react-router-dom";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { CartPage } from "./pages/CartPage";
import { CatalogPage } from "./pages/CatalogPage";
import { ConfirmationPage } from "./pages/ConfirmationPage";
import { CustomerAccountPage } from "./pages/CustomerAccountPage";
import { HomePage } from "./pages/HomePage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { WholesalePage } from "./pages/WholesalePage";

export function App() {
  return (
    <>
      <Header />
      <Routes>
        <Route element={<HomePage />} path="/" />
        <Route element={<CatalogPage />} path="/catalogo" />
        <Route element={<CustomerAccountPage />} path="/cuenta/*" />
        <Route element={<WholesalePage />} path="/mayoristas" />
        <Route element={<CartPage />} path="/carrito" />
        <Route element={<ConfirmationPage />} path="/confirmacion/:orderId" />
        <Route element={<PrivacyPage />} path="/privacidad" />
        <Route element={<HomePage />} path="*" />
      </Routes>
      <Footer />
    </>
  );
}
