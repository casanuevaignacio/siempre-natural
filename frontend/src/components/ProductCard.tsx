import { useState } from "react";
import { formatCLP, minimumQuantity } from "../api";
import { useCart } from "../cart/CartContext";
import type { Product } from "../types";

const productImages: Record<string, string> = {
  "ajo-en-escamas": "/images/products/ajo-en-escama.jpg",
  "almendras-enteras": "/images/products/almendras.jpg",
  "almendras-laminadas": "/images/products/almendras.jpg",
  "almendras-segunda": "/images/products/almendras.jpg",
  "h-almendras": "/images/products/almendras.jpg",
  "h-almendras-sp": "/images/products/almendras.jpg",
  "arroz-basmati": "/images/products/arroz-basmati.jpg",
  "avellana-chilena": "/images/products/avellana-chilena.jpg",
  "avellana-europea": "/images/products/avellana-europea.jpg",
  "avena-entera": "/images/products/avena.jpg",
  "avena-entera-sin-gluten": "/images/products/avena.jpg",
  "avena-instantanea": "/images/products/avena.jpg",
  "h-avena": "/images/products/avena.jpg",
  "castanas-de-caju": "/images/products/caju.jpg",
  "canela-entera": "/images/products/canela-rama.jpg",
  "damasco-turco": "/images/products/damasco-turco.jpg",
  "datiles-sc": "/images/products/datiles.jpg",
  "garbanzos-sin-piel": "/images/products/garbanzos.jpg",
  "bayas-de-goji": "/images/products/goji.jpg",
  "lentejas-rojas": "/images/products/lentejas-rojas.jpg",
  "mani-tostado-con-o-sin-sal": "/images/products/mani.jpg",
  maravilla: "/images/products/maravilla.jpg",
  "nueces-mariposa": "/images/products/nueces.jpg",
  pistachos: "/images/products/pistacho.jpg",
  "platano-chips": "/images/products/platano-chips.jpg",
  "poroto-berry": "/images/products/porotos.jpg",
  "poroto-blanco": "/images/products/porotos.jpg",
  "poroto-burro-tortola": "/images/products/porotos.jpg",
  "poroto-de-soja": "/images/products/porotos.jpg",
  "poroto-mung": "/images/products/poroto-mug.jpg",
  "poroto-negro": "/images/products/porotos.jpg",
  "quinua-blanca": "/images/products/quinoa.jpg",
  "quinua-mix": "/images/products/quinoa.jpg",
  "quinua-roja-y-negra": "/images/products/quinoa.jpg",
  "h-quinua": "/images/products/quinoa.jpg",
  "quinua-pop-endulzada": "/images/products/quinoa-pop.jpg",
  "quinua-pop-natural": "/images/products/quinoa-pop.jpg",
  "sal-de-mar": "/images/products/sal-de-mar.jpg",
  "sal-del-himalaya": "/images/products/sal-himalaya.jpg",
  zapallo: "/images/products/semilla-de-zapallo.jpg",
  "sesamo-blanco": "/images/products/sesamo.jpg",
  "te-chai": "/images/products/te-chai.jpg",
  "te-rooibos": "/images/products/te.jpg",
  "tomates-deshidratados": "/images/products/tomate-deshidratado.jpg",
};

export function ProductCard({ product }: { product: Product }) {
  const { add } = useCart();
  const [quantity, setQuantity] = useState("");
  const [added, setAdded] = useState(false);
  const quantityNumber = Number(quantity);
  const minimum = minimumQuantity(product);
  const validQuantity =
    Number.isSafeInteger(quantityNumber) && quantityNumber >= minimum;
  const categoryImage: Record<string, string> = {
    aceites: "/images/producto-aceites-dulces.svg",
    endulzantes: "/images/producto-aceites-dulces.svg",
    "banados-en-chocolate-vegano": "/images/producto-chocolate.svg",
    "chocolate-vegano-y-mas": "/images/producto-chocolate.svg",
    "frutos-secos": "/images/producto-frutos-semillas.svg",
    "frutos-semi-secos": "/images/producto-frutos-semillas.svg",
    semillas: "/images/producto-frutos-semillas.svg",
    "cafe-te-y-especias": "/images/producto-especias-cereales.svg",
    cereales: "/images/producto-especias-cereales.svg",
    condimentos: "/images/producto-especias-cereales.svg",
    legumbres: "/images/producto-especias-cereales.svg",
    harinas: "/images/producto-especias-cereales.svg",
  };
  const placeholderImage =
    categoryImage[product.category.slug] ?? "/images/productos-organicos.svg";
  const image = product.image_url || productImages[product.slug];

  function addProduct() {
    if (!validQuantity) return;
    add(product, quantityNumber);
    setAdded(true);
    window.setTimeout(() => setAdded(false), 1800);
  }

  return (
    <article className="product-card">
      <div className="product-image">
        {image ? (
          <img src={image} alt={product.name} loading="lazy" />
        ) : (
          <img
            alt=""
            aria-hidden="true"
            className="product-placeholder-image"
            loading="lazy"
            src={placeholderImage}
          />
        )}
        <span className="product-category">{product.category.name}</span>
      </div>
      <div className="product-copy">
        <h3>{product.name}</h3>
        <p>{product.description || "Producto disponible en el catálogo."}</p>
        <strong className="product-price">
          {product.sale_unit === "kg" && product.price_250g ? (
            <>
              Desde {formatCLP(product.price_250g)} <small>/ 250 g</small>
              <small> · {formatCLP(product.price)} / kg</small>
            </>
          ) : (
            <>
              Desde {formatCLP(product.price)}{" "}
              <small>
                /{product.sale_unit === "kg" ? "kg" : product.package_label || "unidad"}
              </small>
            </>
          )}
        </strong>
        <div className="product-action">
          <label className="sr-only" htmlFor={`quantity-${product.id}`}>
            {product.sale_unit === "kg" ? "Cantidad en gramos" : "Cantidad de unidades"} de {product.name}
          </label>
          <input
            id={`quantity-${product.id}`}
            inputMode="numeric"
            min={minimum}
            onChange={(event) => setQuantity(event.target.value)}
            placeholder={
              product.sale_unit === "kg"
                ? `Gramos (mín. ${minimum})`
                : "Unidades"
            }
            step="1"
            type="number"
            value={quantity}
          />
          <button className="button button-small" disabled={!validQuantity} onClick={addProduct} type="button">
            {added ? "Agregado" : "Agregar"}
          </button>
        </div>
      </div>
    </article>
  );
}
