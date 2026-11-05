import type {
  Category,
  CreatedOrder,
  CustomerOrder,
  CustomerSession,
  OrderRequest,
  Product,
  StoreConfig,
  WholesalePrice,
  WholesaleSession,
} from "./types";

const apiBase = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api")
  .replace(/\/+$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new Error("No fue posible conectar con la tienda. Intenta nuevamente.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message =
      typeof body?.detail === "string"
        ? body.detail
        : "No se pudo completar la solicitud. Revisa los datos e inténtalo otra vez.";
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function fetchProducts(search = ""): Promise<Product[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const result = await request<{ results?: Product[] } | Product[]>(
    `/products/${query}`,
  );
  return Array.isArray(result) ? result : result.results ?? [];
}

export async function fetchCategories(): Promise<Category[]> {
  const result = await request<{ results?: Category[] } | Category[]>(
    "/categories/",
  );
  return Array.isArray(result) ? result : result.results ?? [];
}

export function fetchStoreConfig(): Promise<StoreConfig> {
  return request("/store-config/");
}

async function csrfHeaders(): Promise<Record<string, string>> {
  const { csrf_token: csrfToken } = await request<{ csrf_token: string }>(
    "/csrf/",
  );
  if (!csrfToken) {
    throw new Error(
      "No se pudo obtener el token de seguridad. Recarga e inténtalo nuevamente.",
    );
  }
  return { "X-CSRFToken": csrfToken };
}

export function fetchWholesaleSession(): Promise<WholesaleSession> {
  return request("/wholesale/session/");
}

export async function loginWholesale(
  username: string,
  password: string,
): Promise<WholesaleSession> {
  const headers = await csrfHeaders();
  return request("/wholesale/login/", {
    method: "POST",
    headers,
    body: JSON.stringify({ username, password }),
  });
}

export async function logoutWholesale(): Promise<void> {
  const headers = await csrfHeaders();
  await request("/wholesale/logout/", { method: "POST", headers });
}

export async function fetchWholesalePrices(): Promise<WholesalePrice[]> {
  const result = await request<
    { results?: WholesalePrice[] } | WholesalePrice[]
  >("/wholesale/prices/");
  return Array.isArray(result) ? result : result.results ?? [];
}

export function createOrder(payload: OrderRequest): Promise<CreatedOrder> {
  return csrfHeaders().then((headers) =>
    request("/orders/", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    }),
  );
}

export function fetchCustomerSession(): Promise<CustomerSession> {
  return request("/customer/session/");
}

export async function registerCustomer(
  email: string,
  password: string,
): Promise<
  CustomerSession & { detail: string; verification_email_sent: boolean }
> {
  const headers = await csrfHeaders();
  return request("/customer/register/", {
    method: "POST",
    headers,
    body: JSON.stringify({ email, password }),
  });
}

export async function loginCustomer(
  email: string,
  password: string,
): Promise<CustomerSession> {
  const headers = await csrfHeaders();
  return request("/customer/login/", {
    method: "POST",
    headers,
    body: JSON.stringify({ email, password }),
  });
}

export async function logoutCustomer(): Promise<void> {
  const headers = await csrfHeaders();
  await request("/customer/logout/", { method: "POST", headers });
}

export async function verifyCustomerEmail(
  token: string,
  action: "verify" | "claim",
): Promise<{ detail: string; claimed_orders: number }> {
  const headers = await csrfHeaders();
  return request("/customer/verify-email/", {
    method: "POST",
    headers,
    body: JSON.stringify({ token, action }),
  });
}

export async function resendCustomerVerification(
  email: string,
): Promise<{ detail: string }> {
  const headers = await csrfHeaders();
  return request("/customer/verification/resend/", {
    method: "POST",
    headers,
    body: JSON.stringify({ email }),
  });
}

export async function requestGuestOrderClaim(): Promise<{
  detail: string;
  email_sent: boolean;
}> {
  const headers = await csrfHeaders();
  return request("/customer/orders/claim/", { method: "POST", headers });
}

export function fetchCustomerOrders(): Promise<CustomerOrder[]> {
  return request("/customer/orders/");
}

export async function requestCustomerPasswordReset(
  email: string,
): Promise<{ detail: string }> {
  const headers = await csrfHeaders();
  return request("/customer/password/reset/", {
    method: "POST",
    headers,
    body: JSON.stringify({ email }),
  });
}

export async function confirmCustomerPasswordReset(
  uid: string,
  token: string,
  password: string,
): Promise<{ detail: string }> {
  const headers = await csrfHeaders();
  return request("/customer/password/reset/confirm/", {
    method: "POST",
    headers,
    body: JSON.stringify({ uid, token, password }),
  });
}

export async function deleteCustomerAccount(password: string): Promise<void> {
  const headers = await csrfHeaders();
  await request("/customer/account/delete/", {
    method: "POST",
    headers,
    body: JSON.stringify({ password }),
  });
}

const clpFormatter = new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  });

export function formatCLP(amount: number | string | bigint): string {
  const value =
    typeof amount === "bigint"
      ? amount
      : typeof amount === "number"
        ? amount
        : BigInt(amount);
  return clpFormatter.format(value);
}

export function productSubtotal(
  product: Product,
  quantity: number,
): bigint {
  if (product.sale_unit === "unit") {
    return BigInt(product.price) * BigInt(quantity);
  }
  if (product.price_250g && quantity < 1000) {
    return (BigInt(product.price_250g) * BigInt(quantity) + 125n) / 250n;
  }
  return (BigInt(product.price) * BigInt(quantity) + 500n) / 1000n;
}

export function minimumQuantity(product: Product): number {
  if (product.sale_unit === "unit") return 1;
  return 50;
}
