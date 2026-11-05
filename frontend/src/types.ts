export type SaleUnit = "kg" | "unit";

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string;
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  description: string;
  category: Category;
  image_url: string | null;
  price: string;
  price_250g: string | null;
  sale_unit: SaleUnit;
  package_label: string;
}

export interface StoreConfig {
  name: string;
  tagline: string;
  whatsapp_number: string;
  pickup_address: string;
  business_hours: string;
  contact_email: string;
}

export interface WholesaleSession {
  is_authenticated: boolean;
  is_wholesale_customer: boolean;
  username: string;
}

export interface WholesalePrice {
  id: number;
  product_name: string;
  category_name: string;
  price_list: string;
  price: string;
  price_unit: "kg" | "package";
  package_label: string;
}

export interface OrderRequest {
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  customer_rut: string;
  delivery_mode: "pickup" | "shipping";
  delivery_address: string;
  notes: string;
  items: Array<{
    product_id: number;
    quantity_grams?: number;
    quantity_units?: number;
  }>;
}

export interface CreatedOrder {
  id: string;
  created_at: string;
  total: string;
  status: string;
  email_notification_sent: boolean;
}

export interface CustomerSession {
  is_authenticated: boolean;
  email: string;
  email_verified: boolean;
}

export interface CustomerOrder {
  id: string;
  created_at: string;
  total: string;
  status: string;
  delivery_mode: string;
  items: Array<{
    name: string;
    quantity_grams: number;
    quantity_units: number;
    subtotal: string;
  }>;
}
