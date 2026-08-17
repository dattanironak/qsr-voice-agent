import type { CustomizationGroup, CustomizationOption, MenuCategory, MenuItem, Order } from "../types";
import { clearToken, getToken, UnauthorizedError } from "./auth";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export interface CategoryInput {
  name: string;
  sort_order: number;
  is_available: boolean;
}

export interface ItemInput {
  name: string;
  description: string | null;
  price: number;
  is_available: boolean;
  image_url: string | null;
  sort_order: number;
}

export interface GroupInput {
  name: string;
  is_required: boolean;
  max_choices: number;
  sort_order: number;
}

export interface OptionInput {
  name: string;
  price_delta: number;
  is_available: boolean;
  sort_order: number;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BACKEND_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (res.status === 401) {
    clearToken();
    throw new UnauthorizedError("Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new Error(detail ?? `${options?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

export const fetchAdminCategories = () => request<MenuCategory[]>("/admin/categories");

export const fetchAdminOrders = () => request<Order[]>("/admin/orders");

export const createCategory = (data: CategoryInput) =>
  request<MenuCategory>("/admin/categories", { method: "POST", body: JSON.stringify(data) });

export const updateCategory = (id: string, data: Partial<CategoryInput>) =>
  request<MenuCategory>(`/admin/categories/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteCategory = (id: string) =>
  request<void>(`/admin/categories/${id}`, { method: "DELETE" });

export const createItem = (categoryId: string, data: ItemInput) =>
  request<MenuItem>(`/admin/categories/${categoryId}/items`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateItem = (id: string, data: Partial<ItemInput & { category_id: string }>) =>
  request<MenuItem>(`/admin/items/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteItem = (id: string) => request<void>(`/admin/items/${id}`, { method: "DELETE" });

export const createGroup = (itemId: string, data: GroupInput) =>
  request<CustomizationGroup>(`/admin/items/${itemId}/groups`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateGroup = (id: string, data: Partial<GroupInput>) =>
  request<CustomizationGroup>(`/admin/groups/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteGroup = (id: string) => request<void>(`/admin/groups/${id}`, { method: "DELETE" });

export const createOption = (groupId: string, data: OptionInput) =>
  request<CustomizationOption>(`/admin/groups/${groupId}/options`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateOption = (id: string, data: Partial<OptionInput>) =>
  request<CustomizationOption>(`/admin/options/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteOption = (id: string) =>
  request<void>(`/admin/options/${id}`, { method: "DELETE" });

export async function uploadImage(file: File): Promise<{ url: string }> {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BACKEND_URL}/admin/uploads`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });
  if (res.status === 401) {
    clearToken();
    throw new UnauthorizedError("Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new Error(detail ?? `Upload failed: ${res.status}`);
  }
  return res.json();
}
