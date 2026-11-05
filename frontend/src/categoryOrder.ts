import type { Category } from "./types";

const featuredCategorySlugs = [
  "frutos-secos",
  "frutos-semisecos",
  "semillas",
  "cereales",
  "condimentos",
];
const featuredCategoryOrder = new Map(
  featuredCategorySlugs.map((slug, index) => [slug, index]),
);
const spanishCollator = new Intl.Collator("es-CL", {
  numeric: true,
  sensitivity: "base",
});

export function sortCategories(categories: Category[]): Category[] {
  return categories.slice().sort((left, right) => {
    const leftOrder = featuredCategoryOrder.get(left.slug);
    const rightOrder = featuredCategoryOrder.get(right.slug);

    if (leftOrder !== undefined || rightOrder !== undefined) {
      if (leftOrder === undefined) return 1;
      if (rightOrder === undefined) return -1;
      if (leftOrder !== rightOrder) return leftOrder - rightOrder;
    }

    return spanishCollator.compare(left.name, right.name);
  });
}
