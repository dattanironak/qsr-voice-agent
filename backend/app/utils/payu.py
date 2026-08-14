"""PayU hosted-checkout hash helpers.

PayU's hosted checkout (the classic `/_payment` form-POST flow) signs every request with a
SHA-512 hash built from a fixed, pipe-delimited field sequence, and expects a "reverse hash" in
the same shape (salt/key swapped) to verify the success/failure callback actually came from PayU
and wasn't forged by a customer editing form fields in their browser. See PayU's hosted checkout
integration guide for the authoritative field order — reproduced here via explicit lists (rather
than a hand-built pipe string) so the separator count can't drift out of sync with the spec.
"""

import hashlib
import secrets

# PayU reserves 10 "user-defined fields" (udf1..udf10) in the hash even though this integration
# only ever sends the first five (udf6..udf10 are always blank) — the reserved trailing pipes are
# what make the hash formula fixed-shape regardless of how many udf's an integration actually
# uses.
_BLANK_UDF_TAIL = ["", "", "", "", ""]


def generate_txnid() -> str:
    """A fresh, unique-enough transaction id for one PayU checkout attempt. PayU requires this
    be alphanumeric and <= 25 chars; well under that here."""
    return secrets.token_hex(10)  # 20 chars


def format_amount(amount: float) -> str:
    return f"{amount:.2f}"


def build_request_hash(
    *,
    salt: str,
    key: str,
    txnid: str,
    amount: str,
    productinfo: str,
    firstname: str,
    email: str,
    udf1: str = "",
    udf2: str = "",
    udf3: str = "",
    udf4: str = "",
    udf5: str = "",
) -> str:
    fields = [
        key,
        txnid,
        amount,
        productinfo,
        firstname,
        email,
        udf1,
        udf2,
        udf3,
        udf4,
        udf5,
        *_BLANK_UDF_TAIL,
        salt,
    ]
    return hashlib.sha512("|".join(fields).encode("utf-8")).hexdigest()


def build_reverse_hash(
    *,
    salt: str,
    key: str,
    txnid: str,
    amount: str,
    productinfo: str,
    firstname: str,
    email: str,
    status: str,
    udf1: str = "",
    udf2: str = "",
    udf3: str = "",
    udf4: str = "",
    udf5: str = "",
) -> str:
    """Recompute the hash PayU should have sent back on the success/failure callback. Field
    order is the request hash's field list reversed, with salt/key swapped for key/salt."""
    fields = [
        salt,
        status,
        *reversed(_BLANK_UDF_TAIL),
        udf5,
        udf4,
        udf3,
        udf2,
        udf1,
        email,
        firstname,
        productinfo,
        amount,
        txnid,
        key,
    ]
    return hashlib.sha512("|".join(fields).encode("utf-8")).hexdigest()
