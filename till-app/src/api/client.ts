import type { Category, Receipt, ShiftSummary } from "../types";

// Same laptop today (http://localhost:8000). When this moves to a Raspberry
// Pi serving multiple tablets over LAN, only this one value changes — set
// VITE_API_BASE_URL to the Pi's LAN address at build time. No other code
// in this app changes.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {}

let authToken: string | null = null;
export function setAuthToken(token: string | null) {
  authToken = token;
}

let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, "Can't reach the till server. Check that it's running on this device.");
  }

  if (res.status === 401) {
    unauthorizedHandler?.();
    throw new UnauthorizedError(401, "Your session has ended. Please log in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{
      token: string;
      user_id: number;
      username: string;
      role: string;
      must_change_password: boolean;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),

  changePassword: (new_password: string) =>
    request<{ ok: boolean }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ new_password }),
    }),

  getMenu: () => request<Category[]>("/menu"),

  createSale: (cart: { item_variant_id: number; quantity: number }[], payment_method: "cash" | "card") =>
    request<Receipt>("/sales", {
      method: "POST",
      body: JSON.stringify({ cart, payment_method }),
    }),

  voidSaleItem: (saleItemId: number, reason: string) =>
    request<{ ok: boolean }>(`/sales/void/${saleItemId}`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  shiftSummary: () => request<ShiftSummary>("/sales/shift-summary"),
};
