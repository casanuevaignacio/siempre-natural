import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchCategories, fetchProducts } from "../api";
import { sortCategories } from "../categoryOrder";
import { ProductCard } from "../components/ProductCard";
import type { Category, Product } from "../types";

export function CatalogPage() {
  const [searchParams] = useSearchParams();
  const spanishCollator = new Intl.Collator("es-CL", {
    numeric: true,
    sensitivity: "base",
  });
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(() => searchParams.get("categoria") ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchCategories(), fetchProducts()])
      .then(([nextCategories, nextProducts]) => {
        setCategories(nextCategories);
        setProducts(nextProducts);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "No se pudo cargar el catálogo."),
      )
      .finally(() => setLoading(false));
  }, []);

  const visibleProducts = products
    .filter((product) => {
      const matchesText = product.name.toLocaleLowerCase("es").includes(search.toLocaleLowerCase("es"));
      return matchesText && (!category || product.category.slug === category);
    })
    .sort((left, right) => spanishCollator.compare(left.name, right.name));

  const sortedCategories = sortCategories(categories);
  const productGroups = sortedCategories
    .filter((item) => !category || item.slug === category)
    .map((item) => ({
      category: item,
      products: visibleProducts.filter((product) => product.category.slug === item.slug),
    }))
    .filter((group) => group.products.length > 0);

  return (
    <main className="page-main">
      <section className="container page-heading">
        <span className="section-kicker">Descubre lo que tenemos</span>
        <h1>Nuestro catálogo</h1>
        <p>Productos disponibles y precios confirmados por la tienda.</p>
      </section>
      <section className="container catalog-content">
        <div className="catalog-tools">
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <span className="sr-only">Buscar productos</span>
            <input onChange={(event) => setSearch(event.target.value)} placeholder="Buscar un producto..." value={search} />
          </label>
          <label className="category-select">
            <span className="sr-only">Filtrar por categoría</span>
            <select onChange={(event) => setCategory(event.target.value)} value={category}>
              <option value="">Todas las categorías</option>
              {sortedCategories.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}
            </select>
          </label>
        </div>
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {loading ? (
          <p className="empty-state">Cargando catálogo…</p>
        ) : visibleProducts.length ? (
          <div className="catalog-groups">
            {productGroups.map((group) => (
              <section className="catalog-group" key={group.category.id}>
                <div className="catalog-group-heading">
                  <h2>{group.category.name}</h2>
                  <span>{group.products.length} {group.products.length === 1 ? "producto" : "productos"}</span>
                </div>
                <div className="product-grid">
                  {group.products.map((product) => <ProductCard key={product.id} product={product} />)}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <span className="empty-art" aria-hidden="true">✳</span>
            <h2>{products.length ? "No encontramos productos" : "Aún no hay productos disponibles"}</h2>
            <p>{products.length ? "Prueba con otra búsqueda o categoría." : "En este momento no hay productos publicados. Vuelve a consultar más adelante."}</p>
          </div>
        )}
      </section>
    </main>
  );
}
