import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate


_XLSX_MIME_TYPE = "vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9]"
    r"[a-zA-Z0-9._%+\-]*"
    r"@[a-zA-Z0-9]"
    r"[a-zA-Z0-9.\-]*"
    r"\.[a-zA-Z]{2,}$"
)


class SMTPConfigError(Exception):
    """Raised when required SMTP configuration is missing."""


def _build_config(app_config):
    """Extract mail configuration from Flask app config."""
    smtp_host = app_config.get("MAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_username = app_config.get("MAIL_SMTP_USERNAME")
    smtp_app_password = app_config.get("MAIL_SMTP_APP_PASSWORD")
    mail_from_name = app_config.get("MAIL_FROM_NAME", "Sistema de Cosecha")
    mail_from_address = app_config.get("MAIL_FROM_ADDRESS") or smtp_username
    use_tls = str(app_config.get("MAIL_USE_TLS", "true")).lower() == "true"

    try:
        port = int(app_config.get("MAIL_SMTP_PORT", 587))
    except (TypeError, ValueError):
        raise SMTPConfigError("MAIL_SMTP_PORT must be an integer")
    if not (1 <= port <= 65535):
        raise SMTPConfigError("MAIL_SMTP_PORT must be between 1 and 65535")

    try:
        timeout = int(app_config.get("MAIL_TIMEOUT_SECONDS", 30))
    except (TypeError, ValueError):
        raise SMTPConfigError("MAIL_TIMEOUT_SECONDS must be an integer")
    if timeout <= 0:
        raise SMTPConfigError("MAIL_TIMEOUT_SECONDS must be positive")

    if mail_from_address and not _EMAIL_RE.match(mail_from_address):
        raise SMTPConfigError("MAIL_FROM_ADDRESS is not a valid email address")

    return {
        "host": smtp_host,
        "port": port,
        "username": smtp_username,
        "app_password": smtp_app_password,
        "from_name": mail_from_name,
        "from_address": mail_from_address,
        "use_tls": use_tls,
        "timeout": timeout,
    }


def _sanitize_filename(filename):
    """Sanitize a filename for use as an email attachment.

    - Removes path separators and CR/LF
    - Ensures .xlsx extension
    - Returns a safe basename
    """
    name = os.path.basename(filename)
    name = name.replace("\r", "").replace("\n", "")
    name = name.replace("\\", "").replace("/", "")
    name = name.strip()
    if not name:
        name = "export.xlsx"
    if not name.lower().endswith(".xlsx"):
        name = name.rsplit(".", 1)[0] + ".xlsx" if "." in name else name + ".xlsx"
    return name


def _build_message(recipient, filename, xlsx_bytes, cfg):
    """Build an EmailMessage with the Excel attachment."""
    msg = EmailMessage()
    msg["Subject"] = f"Exportación de inventario — {filename}"
    msg["From"] = f"{cfg['from_name']} <{cfg['from_address']}>"
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(
        "Adjunto encontrará el archivo Excel con la exportación de inventario.\n\n"
        f"Archivo: {filename}\n\n"
        "Este correo fue enviado automáticamente por el Sistema de Cosecha."
    )

    msg.add_attachment(
        xlsx_bytes,
        maintype="application",
        subtype=_XLSX_MIME_TYPE,
        filename=filename,
    )

    return msg


def send_export_email(recipient, filename, xlsx_bytes, app_config):
    """Send an Excel export file via SMTP.

    Args:
        recipient: Destination email address.
        filename: Attachment filename (must end in .xlsx).
        xlsx_bytes: Raw bytes of the Excel file.
        app_config: Flask app.config mapping.

    Raises:
        SMTPConfigError: If required SMTP settings are missing.
        smtplib.SMTPException: On any SMTP failure.
    """
    if not xlsx_bytes:
        raise SMTPConfigError("Export file is empty")

    cfg = _build_config(app_config)

    if not cfg["username"] or not cfg["app_password"]:
        raise SMTPConfigError("SMTP configuration is incomplete")

    safe_filename = _sanitize_filename(filename)
    msg = _build_message(recipient, safe_filename, xlsx_bytes, cfg)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=cfg["timeout"]) as server:
            server.ehlo()
            if cfg["use_tls"]:
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()
            server.login(cfg["username"], cfg["app_password"])
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    except smtplib.SMTPException:
        raise
    except OSError:
        raise
