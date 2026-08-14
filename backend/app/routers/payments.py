"""PayU hosted-checkout integration, restricted to UPI only.

Flow:
1. Frontend calls `POST /orders/{order_id}/payu/qr` to get a signed set of form fields.
2. Frontend auto-submits those fields as a POST to PayU's hosted `/_payment` page (in a new tab,
   so the customer's UPI app of choice can scan the QR PayU renders there) — `enforce_paymethod`
   restricts that page to showing only the UPI/QR payment option.
3. PayU redirects the customer's browser back to our `surl` (success) or `furl` (failure) with a
   signed form POST. We verify the reverse hash (proof it actually came from PayU, not a customer
   editing form fields), update the Order/Payment, and redirect the browser on to a frontend
   receipt page.

Note: `enforce_paymethod=upi` is PayU's documented "restrict payment options" hosted-checkout
parameter — confirm it's enabled the same way on your live PayU merchant dashboard before
relying on it in production; sandbox behavior can differ per account configuration.
"""

import hmac
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import receipts
from app.config import Settings, get_settings
from app.database import get_db
from app.models import Order, Payment
from app.schemas import PayuCheckoutOut
from app.utils import payu

logger = logging.getLogger("qsr-backend.payments")

router = APIRouter(tags=["payments"])

# Anonymous walk-up kiosk order — no login/contact capture, so PayU's mandatory
# firstname/email/phone fields get fixed placeholder values rather than real customer data.
_GUEST_FIRSTNAME = "Guest"
_GUEST_PHONE = "9999999999"


def _require_payu_settings(settings: Settings) -> tuple[str, str]:
    if not settings.payu_merchant_key or not settings.payu_merchant_salt:
        raise HTTPException(status_code=500, detail="PayU is not configured on the server")
    return settings.payu_merchant_key, settings.payu_merchant_salt


@router.post("/orders/{order_id}/payu/qr", response_model=PayuCheckoutOut)
def create_payu_checkout(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    key, salt = _require_payu_settings(settings)

    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None:
        raise HTTPException(404, "Order not found")
    if order.status == "paid":
        raise HTTPException(400, "Order is already paid")

    txnid = payu.generate_txnid()
    amount = payu.format_amount(order.total)
    productinfo = f"QSR order {order.pickup_token}"
    email = f"guest-{txnid}@qsr-agent.local"

    request_hash = payu.build_request_hash(
        salt=salt,
        key=key,
        txnid=txnid,
        amount=amount,
        productinfo=productinfo,
        firstname=_GUEST_FIRSTNAME,
        email=email,
    )

    db.add(Payment(order_id=order.id, provider="payu", provider_ref=txnid, status="initiated"))
    db.commit()

    fields = {
        "key": key,
        "txnid": txnid,
        "amount": amount,
        "productinfo": productinfo,
        "firstname": _GUEST_FIRSTNAME,
        "email": email,
        "phone": _GUEST_PHONE,
        "surl": f"{settings.backend_public_base_url}/payments/payu/success",
        "furl": f"{settings.backend_public_base_url}/payments/payu/failure",
        "hash": request_hash,
        "enforce_paymethod": "upi",
    }
    return PayuCheckoutOut(action_url=settings.payu_payment_url, fields=fields)


async def _handle_payu_callback(request: Request, db: Session, settings: Settings) -> RedirectResponse:
    form = await request.form()
    txnid = str(form.get("txnid", ""))
    status = str(form.get("status", ""))
    amount = str(form.get("amount", ""))
    productinfo = str(form.get("productinfo", ""))
    firstname = str(form.get("firstname", ""))
    email = str(form.get("email", ""))
    received_hash = str(form.get("hash", ""))

    frontend_base = settings.frontend_public_base_url

    payment = db.execute(
        select(Payment)
        .options(selectinload(Payment.order).selectinload(Order.items))
        .where(Payment.provider == "payu", Payment.provider_ref == txnid)
    ).scalar_one_or_none()
    if payment is None:
        logger.error("PayU callback for unknown txnid=%s", txnid)
        return RedirectResponse(f"{frontend_base}/order/unknown?status=failed", status_code=302)

    key, salt = _require_payu_settings(settings)
    expected_hash = payu.build_reverse_hash(
        salt=salt,
        key=key,
        txnid=txnid,
        amount=amount,
        productinfo=productinfo,
        firstname=firstname,
        email=email,
        status=status,
    )
    hash_valid = bool(received_hash) and hmac.compare_digest(expected_hash, received_hash)
    if not hash_valid:
        logger.error("PayU callback hash mismatch for txnid=%s (possible tampering)", txnid)

    order = payment.order
    payment.raw_webhook_json = dict(form)

    receipt_saved = False
    if hash_valid and status == "success":
        payment.status = "success"
        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)
        redirect_status = "success"
        # Render while `order.items` is still attached and unexpired, before db.commit() below
        # expires session state.
        receipts.save_receipt(order)
        receipt_saved = True
    else:
        payment.status = "failure" if hash_valid else "hash_mismatch"
        order.status = "payment_failed"
        redirect_status = "failed"

    order_id = order.id
    db.commit()

    if receipt_saved and settings.auto_open_receipt:
        receipt_url = f"{settings.backend_public_base_url}/receipts/{order_id}.html"
        receipts.open_receipt_in_chrome(receipt_url)

    return RedirectResponse(f"{frontend_base}/order/{order_id}?status={redirect_status}", status_code=302)


@router.post("/payments/payu/success")
async def payu_success(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    return await _handle_payu_callback(request, db, settings)


@router.post("/payments/payu/failure")
async def payu_failure(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    return await _handle_payu_callback(request, db, settings)
