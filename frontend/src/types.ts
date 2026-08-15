// Mirrors 02-menu-feature.md `GET /menu` response shape.
export interface CustomizationOption {
  id: string;
  name: string;
  price_delta: number;
  is_available: boolean;
  sort_order: number;
}

export interface CustomizationGroup {
  id: string;
  name: string;
  is_required: boolean;
  max_choices: number;
  sort_order: number;
  options: CustomizationOption[];
}

export interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  price: number;
  is_available: boolean;
  image_url: string | null;
  sort_order: number;
  customization_groups: CustomizationGroup[];
}

export interface MenuCategory {
  id: string;
  name: string;
  sort_order: number;
  is_available: boolean;
  items: MenuItem[];
}

export interface Menu {
  categories: MenuCategory[];
}

// Mirrors 05-web-frontend.md `POST /session/token` response shape.
export interface SessionToken {
  livekit_url: string;
  room_name: string;
  token: string;
  order_session_id: string;
}

// Mirrors 04-order-cart-feature.md cart state shape.
export interface CartLineCustomization {
  group_name: string;
  option_name: string;
  price_delta: number;
}

export interface CartLine {
  line_id: number;
  menu_item_id: string;
  name: string;
  quantity: number;
  customizations: CartLineCustomization[];
  unit_price: number;
  line_total: number;
}

export interface Cart {
  items: CartLine[];
  subtotal: number;
}

export const EMPTY_CART: Cart = { items: [], subtotal: 0 };

// Data message published by the agent on topic "cart_update" (04-order-cart-feature.md).
export interface CartUpdateMessage {
  type: "cart_update";
  cart: Cart;
}

// A single customization pick made in the UI before it's confirmed/added.
export interface SelectedOption {
  groupId: string;
  groupName: string;
  optionId: string;
  optionName: string;
  priceDelta: number;
}

// Mirrors backend OrderOut (06-checkout-payu.md). `status` is one of "pending_payment" | "paid"
// | "payment_failed".
export interface OrderItem {
  id: string;
  menu_item_id: string;
  name: string;
  quantity: number;
  unit_price: number;
  customizations: CartLineCustomization[];
  line_total: number;
}

export interface Payment {
  id: string;
  provider: string;
  provider_ref: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Order {
  id: string;
  status: "pending_payment" | "paid" | "payment_failed" | string;
  pickup_token: string;
  subtotal: number;
  total: number;
  created_at: string;
  paid_at: string | null;
  items: OrderItem[];
  payments: Payment[];
}

// Data message published by the agent on topic "order_update" once complete_order runs, and
// again once payment resolves.
export interface OrderUpdateMessage {
  type: "order_created" | "order_status";
  order: {
    id: string;
    pickup_token: string;
    total: number;
    status: string;
  };
}

// Mirrors backend PayuCheckoutOut — a signed set of form fields to auto-submit as a POST to
// PayU's hosted checkout, restricted to UPI.
export interface PayuCheckout {
  action_url: string;
  fields: Record<string, string>;
}
