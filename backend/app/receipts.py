"""Printable order receipts.

There's no physical receipt printer wired up yet, so a paid order gets a plain HTML receipt
saved to disk (styled for an 80mm thermal-printer width) and opened in a new browser tab —
staff can print it from there (Cmd/Ctrl+P) same as they will once a real printer is connected.
This only makes sense when the backend process runs on the same machine as the counter's
screen; see `Settings.auto_open_receipt`.
"""

import logging
import webbrowser
from html import escape
from pathlib import Path

from app.models import Order

logger = logging.getLogger("qsr-backend.receipts")

RECEIPTS_DIR = Path(__file__).resolve().parent / "static" / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Receipt {pickup_token}</title>
<style>
  @page {{ size: 80mm auto; margin: 4mm; }}
  body {{
    font-family: "SF Mono", "Courier New", monospace;
    width: 78mm;
    margin: 0 auto;
    padding: 8px;
    color: #000;
    font-size: 13px;
  }}
  h1 {{ font-size: 16px; text-align: center; margin: 0 0 4px; }}
  .subtitle {{ text-align: center; font-size: 11px; margin-bottom: 10px; }}
  .divider {{ border-top: 1px dashed #000; margin: 8px 0; }}
  .pickup-token {{
    text-align: center;
    font-size: 28px;
    font-weight: bold;
    letter-spacing: 4px;
    margin: 10px 0;
  }}
  .pickup-label {{ text-align: center; font-size: 11px; text-transform: uppercase; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 2px 0; vertical-align: top; }}
  .qty {{ width: 24px; }}
  .price {{ text-align: right; white-space: nowrap; }}
  .customization {{ font-size: 11px; padding-left: 24px; color: #333; }}
  .totals td {{ padding-top: 6px; font-weight: bold; }}
  .footer {{ text-align: center; font-size: 11px; margin-top: 14px; }}
  @media print {{
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
  <h1>QSR Order Receipt</h1>
  <div class="subtitle">{created_at}</div>
  <div class="divider"></div>
  <div class="pickup-label">Pickup code</div>
  <div class="pickup-token">{pickup_token}</div>
  <div class="divider"></div>
  <table>
    {item_rows}
  </table>
  <div class="divider"></div>
  <table>
    <tr class="totals"><td>Total</td><td class="price">Rs {total}</td></tr>
  </table>
  <div class="divider"></div>
  <div class="footer">
    Order #{order_id_short}<br>
    Paid via UPI &middot; PayU
  </div>
  <p class="no-print" style="text-align:center; margin-top:16px;">
    <button onclick="window.print()">Print</button>
  </p>
</body>
</html>
"""


def _item_row(item) -> str:
    customizations = "".join(
        f'<tr><td></td><td colspan="2" class="customization">{escape(c["option_name"])}</td></tr>'
        for c in item.customizations_json
    )
    line_total = f"{item.unit_price * item.qty:.2f}"
    return (
        f'<tr><td class="qty">{item.qty}x</td>'
        f"<td>{escape(item.menu_item_name_snapshot)}</td>"
        f'<td class="price">Rs {line_total}</td></tr>'
        f"{customizations}"
    )


def render_receipt_html(order: Order) -> str:
    return _TEMPLATE.format(
        pickup_token=escape(order.pickup_token),
        created_at=order.created_at.strftime("%d %b %Y, %I:%M %p"),
        item_rows="\n    ".join(_item_row(item) for item in order.items),
        total=f"{order.total:.2f}",
        order_id_short=str(order.id)[:8],
    )


def save_receipt(order: Order) -> Path:
    path = RECEIPTS_DIR / f"{order.id}.html"
    path.write_text(render_receipt_html(order), encoding="utf-8")
    return path


def open_receipt_in_chrome(url: str) -> None:
    """Best-effort — a failure here must never fail the payment callback it's called from."""
    try:
        try:
            browser = webbrowser.get("chrome")
        except webbrowser.Error:
            browser = webbrowser.get()
        browser.open_new_tab(url)
    except Exception:
        logger.exception("failed to auto-open receipt in browser")
