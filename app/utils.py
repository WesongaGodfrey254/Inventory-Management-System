from functools import wraps
import html
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from flask import abort, current_app
from flask_login import current_user

# How many times to try a connection before giving up. Gmail occasionally
# drops the first connection on a slow network, so a retry makes receipts
# far more reliable without user intervention.
SMTP_ATTEMPTS = 3
SMTP_TIMEOUT = 15


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (current_user.is_authenticated and current_user.is_admin):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def mail_config_problem():
    """Return a human-readable reason when receipts cannot be emailed."""
    config = current_app.config
    if not config.get("MAIL_SERVER"):
        return (
            "MAIL_SERVER is not set. Fill in the MAIL_* values in .env "
            "and restart the app."
        )
    if not config.get("MAIL_USERNAME") or not config.get("MAIL_PASSWORD"):
        return (
            "MAIL_USERNAME / MAIL_PASSWORD are missing. Fill in the MAIL_* "
            "values in .env and restart the app."
        )
    return None


def shop_display_name(user):
    """Return the name of the shop that recorded the sale.

    Every notification is branded with the shop the customer actually bought
    from (the account that owns the sale), never the generic app name. Older
    accounts created before shop names were required fall back to the
    username, then to a safe default.
    """
    if user is not None:
        for value in (getattr(user, "shop_name", None), getattr(user, "username", None)):
            value = (value or "").strip()
            if value:
                return value
    return "My Shop"


def _receipt_parts(sale):
    """Build the plain-text and HTML bodies for a sale receipt."""
    customer = sale.customer
    shop_name = shop_display_name(sale.user)

    lines = [
        f"Hello {customer.name},",
        "",
        f"Thank you for shopping at {shop_name}.",
        "",
        f"Receipt number: {sale.receipt_number}",
        f"Date: {sale.created_at}",
        "",
        "Items:",
    ]
    rows = []
    for item in sale.items:
        product_name = item.product.name if item.product else "Product"
        lines.append(
            f"  - {product_name} x {item.quantity} @ {item.unit_price} = {item.subtotal}"
        )
        rows.append(
            "<tr>"
            f"<td>{html.escape(product_name)}</td>"
            f"<td style=\"text-align:right\">{item.quantity}</td>"
            f"<td style=\"text-align:right\">{item.unit_price}</td>"
            f"<td style=\"text-align:right\">{item.subtotal}</td>"
            "</tr>"
        )
    lines.extend(["", f"Total: {sale.total_amount}", "", f"Thank you, {shop_name}"])

    body = "\n".join(lines)
    html_body = (
        "<html><body style=\"font-family:Arial,Helvetica,sans-serif;color:#222\">"
        f"<h2 style=\"margin-bottom:4px\">{html.escape(shop_name)}</h2>"
        f"<p>Hello {html.escape(customer.name)},</p>"
        f"<p>Thank you for shopping at <strong>{html.escape(shop_name)}</strong>.</p>"
        f"<p><strong>Receipt number:</strong> {html.escape(str(sale.receipt_number))}<br>"
        f"<strong>Date:</strong> {html.escape(str(sale.created_at))}</p>"
        "<table cellpadding=\"6\" cellspacing=\"0\" border=\"0\" "
        "style=\"border-collapse:collapse;min-width:420px\">"
        "<thead><tr style=\"background:#f2f2f2\">"
        "<th align=\"left\">Item</th><th align=\"right\">Qty</th>"
        "<th align=\"right\">Unit price</th><th align=\"right\">Subtotal</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "<tfoot><tr><th colspan=\"3\" align=\"right\">Total</th>"
        f"<th align=\"right\">{sale.total_amount}</th></tr></tfoot>"
        "</table>"
        f"<p>Thank you,<br>{html.escape(shop_name)}</p>"
        "</body></html>"
    )
    return shop_name, body, html_body


def _build_message(sale):
    customer = sale.customer
    config = current_app.config
    shop_name, body, html_body = _receipt_parts(sale)

    sender = config.get("MAIL_DEFAULT_SENDER")
    message = EmailMessage()
    message["Subject"] = f"Receipt {sale.receipt_number} from {shop_name}"
    # Show the shop name next to the address, e.g. "BUDA SHOP <shop@gmail.com>",
    # so the customer recognises the shop in their inbox.
    message["From"] = formataddr((shop_name, sender)) if sender else shop_name
    message["To"] = customer.email
    message["Reply-To"] = formataddr((shop_name, sender)) if sender else shop_name
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    message.set_content(body)
    message.add_alternative(html_body, subtype="html")
    return message


def _send_once(message):
    """Open a fresh SMTP connection and deliver one message."""
    config = current_app.config
    port = int(config.get("MAIL_PORT") or 587)
    use_ssl = bool(config.get("MAIL_USE_SSL"))
    use_tls = bool(config.get("MAIL_USE_TLS"))
    context = ssl.create_default_context()

    if use_ssl:
        smtp = smtplib.SMTP_SSL(
            config["MAIL_SERVER"], port, timeout=SMTP_TIMEOUT, context=context
        )
    else:
        smtp = smtplib.SMTP(config["MAIL_SERVER"], port, timeout=SMTP_TIMEOUT)

    with smtp:
        if use_tls and not use_ssl:
            smtp.starttls(context=context)
        smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
        smtp.send_message(message)


def send_sale_notification_detailed(sale):
    """Email a receipt and return ``(sent, reason)``.

    ``reason`` is ``None`` on success, otherwise a message suitable for
    showing to the user. Delivery is retried a few times for transient
    network/server errors.
    """
    customer = getattr(sale, "customer", None)
    if customer is None or not customer.email:
        current_app.logger.info(
            "Sale %s: customer has no email address, notification skipped",
            sale.receipt_number,
        )
        return False, "This sale has no customer email address."

    problem = mail_config_problem()
    if problem:
        current_app.logger.warning(
            "Sale %s: email to %s skipped. %s",
            sale.receipt_number,
            customer.email,
            problem,
        )
        return False, problem

    try:
        message = _build_message(sale)
    except Exception:
        current_app.logger.exception(
            "Sale %s: could not build the receipt email", sale.receipt_number
        )
        return False, "The receipt could not be prepared. Check the server log."

    last_error = None
    for attempt in range(1, SMTP_ATTEMPTS + 1):
        try:
            _send_once(message)
            last_error = None
            break
        except smtplib.SMTPAuthenticationError:
            current_app.logger.exception(
                "Sale %s: SMTP login failed for %s",
                sale.receipt_number,
                current_app.config.get("MAIL_USERNAME"),
            )
            return False, (
                "The mail server rejected the login. Check MAIL_USERNAME and "
                "the Gmail App Password in .env, then restart the app."
            )
        except smtplib.SMTPRecipientsRefused:
            current_app.logger.exception(
                "Sale %s: recipient %s was refused",
                sale.receipt_number,
                customer.email,
            )
            return False, f"The mail server rejected the address {customer.email}."
        except (smtplib.SMTPException, OSError) as exc:
            last_error = exc
            current_app.logger.warning(
                "Sale %s: email attempt %s/%s to %s failed: %s",
                sale.receipt_number,
                attempt,
                SMTP_ATTEMPTS,
                customer.email,
                exc,
            )
            if attempt < SMTP_ATTEMPTS:
                time.sleep(attempt)
        except Exception:
            current_app.logger.exception(
                "Sale %s: failed to send email to %s",
                sale.receipt_number,
                customer.email,
            )
            return False, "The receipt could not be sent. Check the server log."

    if last_error is not None:
        current_app.logger.error(
            "Sale %s: failed to send email to %s after %s attempts",
            sale.receipt_number,
            customer.email,
            SMTP_ATTEMPTS,
            exc_info=(
                type(last_error),
                last_error,
                last_error.__traceback__,
            ),
        )
        return False, (
            "Could not reach the mail server after "
            f"{SMTP_ATTEMPTS} attempts. Check the internet connection and try again."
        )

    current_app.logger.info(
        "Sale %s: receipt emailed to %s", sale.receipt_number, customer.email
    )
    return True, None


def send_sale_notification(sale):
    """Backwards-compatible wrapper: return only whether delivery worked."""
    return send_sale_notification_detailed(sale)[0]
