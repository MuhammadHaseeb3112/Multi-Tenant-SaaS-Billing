"""
Public payment links for invoices.

The invoice email carries a signed link (no login needed) so the customer
can open the invoice and pay it with Stripe. The token holds the invoice
ID and the invoice's payment_link_version, signed with SECRET_KEY: it
cannot be guessed or edited, and it stops working as soon as the invoice
is emailed again (the version moves on).
"""

from django.conf import settings
from django.core import signing

TOKEN_SALT = "invoices.public-payment"

# Long enough for slow payers and the dunning reminders.
TOKEN_MAX_AGE = 60 * 60 * 24 * 180


def make_payment_token(invoice):
    return signing.dumps(
        {"i": str(invoice.id), "v": invoice.payment_link_version},
        salt=TOKEN_SALT,
    )


def read_payment_token(token):
    """Return (invoice_id, version) from the token, or None if invalid."""

    try:
        data = signing.loads(
            token,
            salt=TOKEN_SALT,
            max_age=TOKEN_MAX_AGE,
        )
    except signing.BadSignature:
        return None

    if not isinstance(data, dict) or "i" not in data or "v" not in data:
        return None

    return data["i"], data["v"]


def payment_link(invoice):
    return f"{settings.FRONTEND_URL}/pay/{make_payment_token(invoice)}"
