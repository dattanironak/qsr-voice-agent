import type { Cart } from "../types";

interface CartPanelProps {
  cart: Cart;
  connected: boolean;
  canMutate: boolean;
  error: string | null;
  onChangeQuantity: (lineId: number, quantity: number) => void;
  onRemoveLine: (lineId: number) => void;
}

export function CartPanel({ cart, connected, canMutate, error, onChangeQuantity, onRemoveLine }: CartPanelProps) {
  return (
    <div className="panel cart-panel">
      <h2>Your order</h2>

      {!connected && (
        <p className="muted-text">Connect to voice ordering to start building your cart.</p>
      )}

      {connected && !canMutate && (
        <p className="muted-text">Waiting for the assistant to join…</p>
      )}

      {connected && cart.items.length === 0 && (
        <p className="muted-text">Your cart is empty — talk to the assistant or tap an item to add it.</p>
      )}

      {error && <p className="error-text cart-error">{error.replaceAll("_", " ")}</p>}

      {cart.items.length > 0 && (
        <ul className="cart-lines">
          {cart.items.map((line) => (
            <li key={line.line_id} className="cart-line">
              <div className="cart-line-main">
                <div className="cart-line-qty-stepper">
                  <button
                    type="button"
                    disabled={!canMutate}
                    onClick={() => onChangeQuantity(line.line_id, line.quantity - 1)}
                    aria-label={`Decrease quantity of ${line.name}`}
                  >
                    −
                  </button>
                  <span>{line.quantity}</span>
                  <button
                    type="button"
                    disabled={!canMutate}
                    onClick={() => onChangeQuantity(line.line_id, line.quantity + 1)}
                    aria-label={`Increase quantity of ${line.name}`}
                  >
                    +
                  </button>
                </div>
                <span className="cart-line-name">{line.name}</span>
                <span className="cart-line-total">₹{line.line_total.toFixed(2)}</span>
                <button
                  type="button"
                  className="cart-line-remove"
                  disabled={!canMutate}
                  onClick={() => onRemoveLine(line.line_id)}
                  aria-label={`Remove ${line.name} from cart`}
                >
                  ×
                </button>
              </div>
              {line.customizations.length > 0 && (
                <ul className="cart-line-customizations">
                  {line.customizations.map((c, i) => (
                    <li key={i}>
                      {c.option_name} ({c.group_name})
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="cart-subtotal">
        <span>Subtotal</span>
        <span>₹{cart.subtotal.toFixed(2)}</span>
      </div>
    </div>
  );
}
