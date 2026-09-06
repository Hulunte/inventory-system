"""Tests for printer_service.py Windows abstraction (all mocked)."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.printer_service import (
    PrinterError,
    PrinterUnavailableError,
    get_default_printer_safe,
    get_printer_status_safe,
    is_available,
    list_printers_safe,
    print_raw,
    validate_printer_name,
)


class TestIsAvailable:
    def test_returns_bool(self):
        result = is_available()
        assert isinstance(result, bool)


class TestListPrintersSafe:
    def test_returns_list(self):
        result = list_printers_safe()
        assert isinstance(result, list)

    @patch("app.services.printer_service._win32print", None)
    def test_unavailable_returns_empty(self):
        result = list_printers_safe()
        assert result == []


class TestGetDefaultPrinterSafe:
    def test_returns_str_or_none(self):
        result = get_default_printer_safe()
        assert result is None or isinstance(result, str)

    @patch("app.services.printer_service._win32print", None)
    def test_unavailable_returns_none(self):
        result = get_default_printer_safe()
        assert result is None


class TestGetPrinterStatusSafe:
    @patch("app.services.printer_service._win32print", None)
    def test_unavailable_returns_message(self):
        result = get_printer_status_safe("AnyPrinter")
        assert "no disponible" in result.lower()


class TestPrintRaw:
    @patch("app.services.printer_service._win32print", None)
    def test_unavailable_raises(self):
        with pytest.raises(PrinterUnavailableError):
            print_raw("TestPrinter", b"data")

    @patch("app.services.printer_service._win32print")
    def test_empty_data_raises(self, mock_win32print):
        mock_win32print.PRINTER_ENUM_LOCAL = 1
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 2
        mock_win32print.EnumPrinters.return_value = [("0", "1", "TestPrinter")]
        mock_win32print.GetDefaultPrinter.return_value = "TestPrinter"
        with pytest.raises(PrinterError, match="vacios"):
            print_raw("TestPrinter", b"")

    @patch("app.services.printer_service._win32print")
    def test_unknown_printer_raises(self, mock_win32print):
        mock_win32print.PRINTER_ENUM_LOCAL = 1
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 2
        mock_win32print.EnumPrinters.return_value = [("0", "1", "OtherPrinter")]
        mock_win32print.GetDefaultPrinter.return_value = "OtherPrinter"
        with pytest.raises(PrinterError, match="no encontrada"):
            print_raw("TestPrinter", b"data")

    @patch("app.services.printer_service._win32print")
    def test_full_print_sequence(self, mock_win32print):
        mock_win32print.PRINTER_ENUM_LOCAL = 1
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 2
        mock_win32print.EnumPrinters.return_value = [("0", "1", "TestPrinter")]
        mock_win32print.GetDefaultPrinter.return_value = "TestPrinter"

        mock_handle = MagicMock()
        mock_win32print.OpenPrinter.return_value = mock_handle
        mock_win32print.StartDocPrinter.return_value = 1
        mock_win32print.WritePrinter.return_value = 5

        print_raw("TestPrinter", b"hello")

        mock_win32print.OpenPrinter.assert_called_once_with("TestPrinter")
        mock_win32print.StartDocPrinter.assert_called_once()
        mock_win32print.StartPagePrinter.assert_called_once_with(mock_handle)
        mock_win32print.WritePrinter.assert_called_once_with(mock_handle, b"hello")
        mock_win32print.EndPagePrinter.assert_called_once_with(mock_handle)
        mock_win32print.EndDocPrinter.assert_called_once_with(mock_handle)
        mock_win32print.ClosePrinter.assert_called_once_with(mock_handle)

    @patch("app.services.printer_service._win32print")
    def test_partial_write_raises(self, mock_win32print):
        mock_win32print.PRINTER_ENUM_LOCAL = 1
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 2
        mock_win32print.EnumPrinters.return_value = [("0", "1", "TestPrinter")]
        mock_win32print.GetDefaultPrinter.return_value = "TestPrinter"

        mock_handle = MagicMock()
        mock_win32print.OpenPrinter.return_value = mock_handle
        mock_win32print.StartDocPrinter.return_value = 1
        mock_win32print.WritePrinter.return_value = 3

        with pytest.raises(PrinterError, match="incompleta"):
            print_raw("TestPrinter", b"hello")

    @patch("app.services.printer_service._win32print")
    def test_cleanup_on_write_error(self, mock_win32print):
        mock_win32print.PRINTER_ENUM_LOCAL = 1
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 2
        mock_win32print.EnumPrinters.return_value = [("0", "1", "TestPrinter")]
        mock_win32print.GetDefaultPrinter.return_value = "TestPrinter"

        mock_handle = MagicMock()
        mock_win32print.OpenPrinter.return_value = mock_handle
        mock_win32print.StartDocPrinter.return_value = 1
        mock_win32print.WritePrinter.side_effect = Exception("Write failed")

        with pytest.raises(PrinterError):
            print_raw("TestPrinter", b"hello")

        mock_win32print.EndDocPrinter.assert_called_once()
        mock_win32print.ClosePrinter.assert_called_once()

    @patch("app.services.printer_service._win32print")
    def test_cleanup_on_doc_error(self, mock_win32print):
        mock_win32print.PRINTER_ENUM_LOCAL = 1
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 2
        mock_win32print.EnumPrinters.return_value = [("0", "1", "TestPrinter")]
        mock_win32print.GetDefaultPrinter.return_value = "TestPrinter"

        mock_handle = MagicMock()
        mock_win32print.OpenPrinter.return_value = mock_handle
        mock_win32print.StartDocPrinter.side_effect = Exception("Doc failed")

        with pytest.raises(PrinterError):
            print_raw("TestPrinter", b"hello")

        mock_win32print.ClosePrinter.assert_called_once()

    @patch("app.services.printer_service._win32print")
    def test_no_internal_info_leaked(self, mock_win32print):
        mock_win32print.PRINTER_ENUM_LOCAL = 1
        mock_win32print.PRINTER_ENUM_CONNECTIONS = 2
        mock_win32print.EnumPrinters.return_value = [("0", "1", "TestPrinter")]
        mock_win32print.GetDefaultPrinter.return_value = "TestPrinter"

        mock_handle = MagicMock()
        mock_win32print.OpenPrinter.return_value = mock_handle
        mock_win32print.StartDocPrinter.return_value = 1
        mock_win32print.WritePrinter.return_value = 5

        try:
            print_raw("TestPrinter", b"data")
        except PrinterError as e:
            assert "Port" not in str(e)
            assert "USB" not in str(e)
            assert "VID" not in str(e)
