import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import (
    SMTPConfigError,
    _build_config,
    _build_message,
    _sanitize_filename,
    send_export_email,
)


FULL_CONFIG = {
    "MAIL_SMTP_HOST": "smtp.gmail.com",
    "MAIL_SMTP_PORT": 587,
    "MAIL_SMTP_USERNAME": "user@gmail.com",
    "MAIL_SMTP_APP_PASSWORD": "secret-app-password",
    "MAIL_FROM_NAME": "Test Sender",
    "MAIL_FROM_ADDRESS": "sender@gmail.com",
    "MAIL_USE_TLS": "true",
    "MAIL_TIMEOUT_SECONDS": "30",
}

XLSX_BYTES = b"fake-xlsx-content"
FILENAME = "inventario_2026-01-01_a_2026-01-31.xlsx"
RECIPIENT = "recipient@example.com"


class TestBuildConfig:
    def test_full_config(self):
        cfg = _build_config(FULL_CONFIG)
        assert cfg["host"] == "smtp.gmail.com"
        assert cfg["port"] == 587
        assert cfg["username"] == "user@gmail.com"
        assert cfg["app_password"] == "secret-app-password"
        assert cfg["from_name"] == "Test Sender"
        assert cfg["from_address"] == "sender@gmail.com"
        assert cfg["use_tls"] is True
        assert cfg["timeout"] == 30

    def test_defaults(self):
        cfg = _build_config({})
        assert cfg["host"] == "smtp.gmail.com"
        assert cfg["port"] == 587
        assert cfg["from_name"] == "Sistema de Cosecha"
        assert cfg["use_tls"] is True
        assert cfg["timeout"] == 30

    def test_from_address_falls_back_to_username(self):
        cfg = _build_config({
            "MAIL_SMTP_USERNAME": "user@gmail.com",
            "MAIL_SMTP_APP_PASSWORD": "pass",
        })
        assert cfg["from_address"] == "user@gmail.com"

    def test_tls_false(self):
        cfg = _build_config({"MAIL_USE_TLS": "false"})
        assert cfg["use_tls"] is False

    def test_custom_port_and_timeout(self):
        cfg = _build_config({
            "MAIL_SMTP_PORT": "465",
            "MAIL_TIMEOUT_SECONDS": "60",
        })
        assert cfg["port"] == 465
        assert cfg["timeout"] == 60

    def test_port_zero_rejected(self):
        with pytest.raises(SMTPConfigError, match="between 1 and 65535"):
            _build_config({"MAIL_SMTP_PORT": "0"})

    def test_port_65536_rejected(self):
        with pytest.raises(SMTPConfigError, match="between 1 and 65535"):
            _build_config({"MAIL_SMTP_PORT": "65536"})

    def test_port_negative_rejected(self):
        with pytest.raises(SMTPConfigError, match="between 1 and 65535"):
            _build_config({"MAIL_SMTP_PORT": "-1"})

    def test_port_non_integer_rejected(self):
        with pytest.raises(SMTPConfigError, match="must be an integer"):
            _build_config({"MAIL_SMTP_PORT": "abc"})

    def test_timeout_zero_rejected(self):
        with pytest.raises(SMTPConfigError, match="must be positive"):
            _build_config({"MAIL_TIMEOUT_SECONDS": "0"})

    def test_timeout_negative_rejected(self):
        with pytest.raises(SMTPConfigError, match="must be positive"):
            _build_config({"MAIL_TIMEOUT_SECONDS": "-5"})

    def test_timeout_non_integer_rejected(self):
        with pytest.raises(SMTPConfigError, match="must be an integer"):
            _build_config({"MAIL_TIMEOUT_SECONDS": "fast"})

    def test_from_address_invalid_rejected(self):
        with pytest.raises(SMTPConfigError, match="not a valid email"):
            _build_config({"MAIL_FROM_ADDRESS": "not-an-email"})


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert _sanitize_filename("report.xlsx") == "report.xlsx"

    def test_strips_path(self):
        assert _sanitize_filename("/path/to/report.xlsx") == "report.xlsx"

    def test_strips_backslashes(self):
        assert _sanitize_filename("C:\\path\\report.xlsx") == "report.xlsx"

    def test_strips_crlf(self):
        assert _sanitize_filename("report\r\n.xlsx") == "report.xlsx"

    def test_strips_cr(self):
        assert _sanitize_filename("report\r.xlsx") == "report.xlsx"

    def test_adds_xlsx_extension(self):
        assert _sanitize_filename("report.csv") == "report.xlsx"

    def test_no_extension_gets_xlsx(self):
        assert _sanitize_filename("report") == "report.xlsx"

    def test_empty_becomes_export(self):
        assert _sanitize_filename("") == "export.xlsx"

    def test_whitespace_only_becomes_export(self):
        assert _sanitize_filename("   ") == "export.xlsx"

    def test_only_slashes_becomes_export(self):
        assert _sanitize_filename("///") == "export.xlsx"


class TestBuildMessage:
    def test_subject_contains_filename(self):
        cfg = _build_config(FULL_CONFIG)
        msg = _build_message(RECIPIENT, FILENAME, XLSX_BYTES, cfg)
        assert FILENAME in msg["Subject"]

    def test_from_header(self):
        cfg = _build_config(FULL_CONFIG)
        msg = _build_message(RECIPIENT, FILENAME, XLSX_BYTES, cfg)
        assert "Test Sender <sender@gmail.com>" in msg["From"]

    def test_to_header(self):
        cfg = _build_config(FULL_CONFIG)
        msg = _build_message(RECIPIENT, FILENAME, XLSX_BYTES, cfg)
        assert msg["To"] == RECIPIENT

    def test_date_header_present(self):
        cfg = _build_config(FULL_CONFIG)
        msg = _build_message(RECIPIENT, FILENAME, XLSX_BYTES, cfg)
        assert msg["Date"] is not None

    def test_text_content(self):
        cfg = _build_config(FULL_CONFIG)
        msg = _build_message(RECIPIENT, FILENAME, XLSX_BYTES, cfg)
        body = msg.get_body(preferencelist=("plain",)).get_content()
        assert "adjunto" in body.lower()
        assert FILENAME in body

    def test_xlsx_attachment(self):
        cfg = _build_config(FULL_CONFIG)
        msg = _build_message(RECIPIENT, FILENAME, XLSX_BYTES, cfg)

        attachments = list(msg.iter_attachments())
        assert len(attachments) == 1

        att = attachments[0]
        assert att.get_filename() == FILENAME
        assert att.get_content_type() == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert att.get_payload(decode=True) == XLSX_BYTES


class TestSendExportEmail:
    @patch("app.services.email_service.smtplib.SMTP")
    def test_starttls_executed(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        mock_server.starttls.assert_called_once()

    @patch("app.services.email_service.smtplib.SMTP")
    def test_ehlo_called_before_starttls(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        assert mock_server.ehlo.call_count == 2
        mock_server.ehlo.assert_any_call()
        starttls_idx = mock_server.starttls.call_count
        ehlo_idx = 0
        for i, call in enumerate(mock_server.method_calls):
            if call[0] == "ehlo":
                ehlo_idx = i
            if call[0] == "starttls":
                assert ehlo_idx < i

    @patch("app.services.email_service.smtplib.SMTP")
    def test_ssl_context_used(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        call_kwargs = mock_server.starttls.call_args
        assert "context" in call_kwargs.kwargs

    @patch("app.services.email_service.smtplib.SMTP")
    def test_login_executed(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        mock_server.login.assert_called_once_with(
            "user@gmail.com", "secret-app-password"
        )

    @patch("app.services.email_service.smtplib.SMTP")
    def test_send_message_called_once(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        mock_server.send_message.assert_called_once()

    @patch("app.services.email_service.smtplib.SMTP")
    def test_recipient_correct(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["To"] == RECIPIENT

    @patch("app.services.email_service.smtplib.SMTP")
    def test_attachment_correct(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        sent_msg = mock_server.send_message.call_args[0][0]
        attachments = list(sent_msg.iter_attachments())
        assert len(attachments) == 1
        assert attachments[0].get_payload(decode=True) == XLSX_BYTES

    @patch("app.services.email_service.smtplib.SMTP")
    def test_mime_type_correct(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        sent_msg = mock_server.send_message.call_args[0][0]
        att = list(sent_msg.iter_attachments())[0]
        assert att.get_content_type() == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @patch("app.services.email_service.smtplib.SMTP")
    def test_timeout_applied(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=30)

    def test_missing_username_raises_config_error(self):
        config = {**FULL_CONFIG, "MAIL_SMTP_USERNAME": None}
        with pytest.raises(SMTPConfigError):
            send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, config)

    def test_missing_password_raises_config_error(self):
        config = {**FULL_CONFIG, "MAIL_SMTP_APP_PASSWORD": None}
        with pytest.raises(SMTPConfigError):
            send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, config)

    def test_empty_xlsx_bytes_raises_config_error(self):
        with pytest.raises(SMTPConfigError, match="empty"):
            send_export_email(RECIPIENT, FILENAME, b"", FULL_CONFIG)

    @patch("app.services.email_service.smtplib.SMTP")
    def test_auth_failure_raises(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(smtplib.SMTPAuthenticationError):
            send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

    @patch("app.services.email_service.smtplib.SMTP")
    def test_smtp_failure_raises(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Connection lost")
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(smtplib.SMTPException):
            send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

    @patch("app.services.email_service.smtplib.SMTP")
    def test_os_error_raises(self, mock_smtp_cls):
        mock_smtp_cls.return_value.__enter__ = MagicMock(side_effect=OSError("Network"))
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(OSError):
            send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

    @patch("app.services.email_service.smtplib.SMTP")
    def test_no_real_connection(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, FILENAME, XLSX_BYTES, FULL_CONFIG)

        mock_smtp_cls.assert_called_once()
        args = mock_smtp_cls.call_args
        assert args[0][0] == "smtp.gmail.com"

    @patch("app.services.email_service.smtplib.SMTP")
    def test_filename_sanitized_in_attachment(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_export_email(RECIPIENT, "../etc/passwd.xlsx", XLSX_BYTES, FULL_CONFIG)

        sent_msg = mock_server.send_message.call_args[0][0]
        att = list(sent_msg.iter_attachments())[0]
        assert att.get_filename() == "passwd.xlsx"
