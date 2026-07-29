export interface Variant {
  id: number;
  variant_label: string;
  price: number;
  available: number | null;
  sold_out: boolean;
}

export interface MenuItem {
  id: number;
  name: string;
  has_variants: boolean;
  base_photo_url: string | null;
  variants: Variant[];
}

export interface Category {
  id: number;
  name: string;
  colour_hex: string;
  items: MenuItem[];
}

export interface CartLine {
  itemVariantId: number;
  itemName: string;
  variantLabel: string;
  unitPrice: number;
  quantity: number;
}

export interface SaleLineResult {
  sale_item_id: number;
  item_variant_id: number;
  item_name: string;
  variant_label: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface Receipt {
  sale_id: number;
  timestamp: string;
  staff_username: string;
  payment_method: "cash" | "card";
  lines: SaleLineResult[];
  subtotal: number;
  vat_amount: number;
  total: number;
}

export type Role = "manager" | "staff";

export interface AuthUser {
  id: number;
  username: string;
  role: Role;
}

export interface ShiftSummary {
  since: string;
  sale_count: number;
  total_sales: number;
}
